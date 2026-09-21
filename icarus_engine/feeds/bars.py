# Grok (xAI) — 2026-09-20. Whole file. TV Supercharts ingest / FileFeed / HistoryHub.
# Do not scrape TradingView. Do not invent ticks.
"""Local OHLCV store. No network, no interpolated ticks.

Drop a TradingView Supercharts → Export chart data CSV into ``history/``
and the engine will warm up from those bars instead of Yahoo.

Canonical on-disk format (UTC epoch seconds of the bar OPEN)::

    ts,open,high,low,close,volume

Accepted on ingest: unix seconds, unix milliseconds, ISO-8601 (with or
without timezone), or ``YYYY-MM-DD HH:MM``. Naive timestamps are read in
``tz`` (default America/New_York — CME RTH charts). Empty / zero-volume
placeholder rows are kept: they are real minutes, unlike Yahoo's drops.

``ICARUS_FEED=file`` swaps Yahoo for :class:`HistoryHub` (plant offline mode).
"""
from __future__ import annotations

import csv
import io
import os
import re
import statistics
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Tuple

from ..pine.timeframe import Bar

try:
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore

_NY = ZoneInfo("America/New_York") if ZoneInfo is not None else timezone.utc

_TIME_KEYS = ("ts", "time", "datetime", "date", "timestamp", "<date>")
_OPEN_KEYS = ("open", "o", "<open>")
_HIGH_KEYS = ("high", "h", "<high>")
_LOW_KEYS = ("low", "l", "<low>")
_CLOSE_KEYS = ("close", "c", "<close>")
_VOL_KEYS = ("volume", "vol", "v", "<vol>")
_COMMON_TF = (60, 120, 180, 240, 300, 600, 900, 1200, 1800, 3600, 14400, 86400)


def read_text_csv(path: str) -> str:
    """Read a chart export. Handles UTF-8, BOM, UTF-16 (Excel), latin-1.

    Grok (xAI) — 2026-09-20. Does not scrape; only reads a file the owner already has.
    """
    with open(path, "rb") as fh:
        raw = fh.read()
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16")
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


_HIST_NAME = re.compile(r"^(.+)_(\d+)m\.csv$", re.I)


def file_feed_mode() -> bool:
    """True when the engine must not contact Yahoo/Coinbase.

    Grok (xAI) — 2026-09-20. Set by ``icarus-plant start --offline`` or
    ``ICARUS_FEED=file``.
    """
    return os.environ.get("ICARUS_FEED", "").strip().lower() in ("file", "history", "csv", "offline")


def _col(cols: Dict[str, str], names: Tuple[str, ...]) -> Optional[str]:
    for n in names:
        if n in cols:
            return cols[n]
    return None


def parse_timestamp(raw: str, tz) -> Optional[int]:
    s = (raw or "").strip().strip('"')
    if not s:
        return None
    if s.replace(".", "", 1).isdigit():
        n = float(s)
        if n > 1e12:  # milliseconds
            n /= 1000.0
        elif n > 1e10:  # microseconds leftover
            n /= 1e6
        ts = int(n)
        return ts if 946684800 <= ts <= 4102444800 else None  # 2000..2100
    s = s.replace("Z", "+00:00")
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%d.%m.%Y %H:%M",
    ):
        try:
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=tz)
            return int(dt.timestamp())
        except ValueError:
            continue
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=tz)
        return int(dt.timestamp())
    except ValueError:
        return None


def parse_ohlcv_csv(text: str, *, tz=None) -> List[Bar]:
    """Parse a TradingView / generic OHLCV CSV into Bars. Drops unparsable rows, not empty minutes."""
    tz = tz or _NY
    raw = text.lstrip("\ufeff")
    sample = raw[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        class _D(csv.excel):
            delimiter = ";" if raw.count(";") > raw.count(",") else ","
        dialect = _D
    reader = csv.DictReader(io.StringIO(raw), dialect=dialect)
    if not reader.fieldnames:
        return []
    if len(reader.fieldnames) == 1 and (";" in reader.fieldnames[0] or "\t" in reader.fieldnames[0]):
        delim = ";" if ";" in reader.fieldnames[0] else "\t"
        class _D2(csv.excel):
            delimiter = delim
        reader = csv.DictReader(io.StringIO(raw), dialect=_D2)
        if not reader.fieldnames:
            return []
    cols = {c.strip().lower(): c for c in reader.fieldnames}
    ct = _col(cols, _TIME_KEYS) or reader.fieldnames[0]
    co = _col(cols, _OPEN_KEYS)
    ch = _col(cols, _HIGH_KEYS)
    cl = _col(cols, _LOW_KEYS)
    cc = _col(cols, _CLOSE_KEYS)
    cv = _col(cols, _VOL_KEYS)
    if not all((co, ch, cl, cc)):
        raise ValueError("CSV needs open/high/low/close columns (TradingView chart export)")
    out: Dict[int, Bar] = {}
    for row in reader:
        ts = parse_timestamp(row.get(ct, ""), tz)
        if ts is None:
            continue
        try:
            o, h, l, c = float(row[co]), float(row[ch]), float(row[cl]), float(row[cc])
        except (TypeError, ValueError, KeyError):
            continue
        if not all(map(lambda x: x == x and abs(x) < 1e15, (o, h, l, c))):
            continue
        try:
            v = float(row[cv] or 0.0) if cv else 0.0
        except (TypeError, ValueError):
            v = 0.0
        out[ts] = Bar(ts, o, h, l, c, v)
    return [out[k] for k in sorted(out)]


def detect_granularity(bars: List[Bar]) -> int:
    """Median positive delta, snapped to a common bar size (seconds)."""
    if len(bars) < 2:
        return 60
    deltas = [b.ts - a.ts for a, b in zip(bars, bars[1:]) if b.ts > a.ts]
    if not deltas:
        return 60
    med = int(statistics.median(deltas))
    return min(_COMMON_TF, key=lambda t: abs(t - med))


def merge_bars(existing: Iterable[Bar], incoming: Iterable[Bar]) -> List[Bar]:
    """Union by bar-open timestamp. Incoming wins on a collision. No invented rows.

    Grok (xAI) — 2026-09-20. Essential's 10K-bar export is a sliding window;
    merging successive Supercharts dumps accumulates history the owner already paid for.
    """
    by: Dict[int, Bar] = {b.ts: b for b in existing}
    by.update({b.ts: b for b in incoming})
    return [by[k] for k in sorted(by)]


def write_canonical(path: str, bars: Iterable[Bar]) -> int:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    rows = list(bars)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["ts", "open", "high", "low", "close", "volume"])
        for b in rows:
            w.writerow([b.ts, b.o, b.h, b.l, b.c, b.v])
    return len(rows)


def history_path(base_dir: str, symbol: str, minutes: int) -> str:
    return os.path.join(base_dir, "history", f"{symbol.upper()}_{int(minutes)}m.csv")


def find_history(base_dir: str, symbol: str, chart_minutes: int) -> Tuple[Optional[str], Optional[int]]:
    """Prefer 1-minute dumps (HTF chains aggregate cleanly); else the chart-TF export.

    Grok (xAI) — 2026-09-20: if neither 1m nor chart-TF exists, pick the finest
    ``history/{SYM}_{N}m.csv`` still on disk. Never invent a finer bar.
    """
    one = history_path(base_dir, symbol, 1)
    chart = history_path(base_dir, symbol, chart_minutes)
    if os.path.isfile(one):
        return one, 1
    if os.path.isfile(chart):
        return chart, chart_minutes
    hist = os.path.join(base_dir, "history")
    if not os.path.isdir(hist):
        return None, None
    want = symbol.upper() + "_"
    found: List[Tuple[int, str]] = []
    for name in os.listdir(hist):
        m = _HIST_NAME.match(name)
        if not m or m.group(1).upper() != symbol.upper():
            continue
        path = os.path.join(hist, name)
        if os.path.isfile(path):
            found.append((int(m.group(2)), path))
    if not found:
        return None, None
    found.sort()
    return found[0][1], found[0][0]


class FileFeed:
    """Yahoo-shaped interface over canonical CSVs. Used for tests and offline replay.

    Grok (xAI) — 2026-09-20: reloads when the on-disk mtime advances (drop ingest).
    Does not split a coarser bar into minutes (that would invent ticks).
    """

    GRANULARITIES = (60, 120, 300, 900, 1800, 3600, 86400)

    def __init__(self, bars: Optional[List[Bar]] = None, mintick: float = 0.25, path: Optional[str] = None):
        self._bars = list(bars or [])
        self._mintick = float(mintick)
        self._path = path
        self._mtime = os.path.getmtime(path) if path and os.path.isfile(path) else 0.0
        self._granularity = detect_granularity(self._bars) if len(self._bars) >= 2 else 60

    @classmethod
    def from_csv(cls, path: str, *, tz=None, mintick: float = 0.25) -> "FileFeed":
        return cls(parse_ohlcv_csv(read_text_csv(path), tz=tz), mintick=mintick, path=path)

    def _maybe_reload(self) -> None:
        if not self._path or not os.path.isfile(self._path):
            return
        mt = os.path.getmtime(self._path)
        if mt <= self._mtime:
            return
        self._bars = parse_ohlcv_csv(read_text_csv(self._path))
        self._mtime = mt
        self._granularity = detect_granularity(self._bars) if len(self._bars) >= 2 else 60

    def mintick(self, symbol: str) -> float:
        return self._mintick

    def ticker(self, symbol: str) -> Optional[float]:
        self._maybe_reload()
        return self._bars[-1].c if self._bars else None

    def candles(self, symbol: str, granularity: int, start_ts: int, end_ts: int) -> List[Bar]:
        self._maybe_reload()
        src = int(self._granularity or 60)
        g = int(granularity)
        if g < src:
            return []  # cannot invent a finer bar from a coarser dump
        if g == src:
            return [b for b in self._bars if start_ts <= b.ts < end_ts]
        buckets: Dict[int, Bar] = {}
        span = g
        for b in self._bars:
            if not (start_ts <= b.ts < end_ts):
                continue
            bk = (b.ts // span) * span
            prev = buckets.get(bk)
            if prev is None:
                buckets[bk] = Bar(bk, b.o, b.h, b.l, b.c, b.v)
            else:
                buckets[bk] = Bar(bk, prev.o, max(prev.h, b.h), min(prev.l, b.l), b.c, prev.v + b.v)
        return [buckets[k] for k in sorted(buckets)]

    def recent_ex(self, symbol: str, granularity: int = 60, since_ts: Optional[int] = None):
        bars = self.candles(symbol, granularity, since_ts or 0, 2**31 - 1)
        if bars:
            ft = bars[-1].ts + int(granularity)
            px = bars[-1].c
            return bars, ft, px
        # Coarser dump (e.g. 20m only): do not claim 1m bars, but still report a clock + last price
        # so poll() does not treat an honest gap as a feed failure.
        self._maybe_reload()
        if self._bars:
            g = int(self._granularity or 60)
            last = self._bars[-1]
            return [], last.ts + g, last.c
        return [], 0, None

    def recent(self, symbol: str, granularity: int = 60) -> List[Bar]:
        return self.recent_ex(symbol, granularity)[0]

    def daily_volume(self, symbol: str, days: int = 5) -> List[Tuple[int, float, float]]:
        daily = self.candles(symbol, 86400, 0, 2**31 - 1)
        tail = daily[-max(days, 2):]
        return [(b.ts, b.c, b.v) for b in tail]


def _hub_symbol(ticker: str) -> str:
    """Map a feed ticker (NQ=F, NQU26.CME, CME_MINI:NQ1!) onto a registry symbol."""
    from ..assets import REGISTRY
    raw = (ticker or "").upper().split(":")[-1]
    for spec in REGISTRY.values():
        if spec.ticker.upper() == raw or spec.symbol == raw:
            return spec.symbol
    stem = raw.split(".")[0]
    if stem.endswith("=F"):
        stem = stem[:-2]
    prefixes = sorted((s.symbol for s in REGISTRY.values()), key=len, reverse=True)
    for sym in prefixes:
        if stem == sym or stem.startswith(sym):
            return sym
    return stem


class HistoryHub:
    """Yahoo-shaped multiplex over ``history/{SYM}_*m.csv``. Grok (xAI) — 2026-09-20.

    Used when ``ICARUS_FEED=file``. Does not call Yahoo. New bars arrive when
    ``icarus-plant ingest-drop`` (or ``ingest-bars``) rewrites the CSV; FileFeed
    reloads on mtime.
    """

    GRANULARITIES = FileFeed.GRANULARITIES

    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self._feeds: Dict[str, FileFeed] = {}

    def _feed(self, ticker: str) -> FileFeed:
        from ..assets import REGISTRY
        sym = _hub_symbol(ticker)
        spec = REGISTRY.get(sym)
        mintick = spec.mintick if spec else 0.25
        path, _ = find_history(self.base_dir, sym, 1)
        if path is None:
            path, _ = find_history(self.base_dir, sym, 20)
        prev = self._feeds.get(sym)
        if path is None:
            return prev or FileFeed([], mintick=mintick)
        if prev is None or prev._path != path:
            prev = FileFeed.from_csv(path, mintick=mintick)
            self._feeds[sym] = prev
        else:
            prev._maybe_reload()
        return prev

    def mintick(self, ticker: str) -> float:
        return self._feed(ticker).mintick(ticker)

    def ticker(self, ticker: str) -> Optional[float]:
        return self._feed(ticker).ticker(ticker)

    def candles(self, ticker: str, granularity: int, start_ts: int, end_ts: int) -> List[Bar]:
        return self._feed(ticker).candles(ticker, granularity, start_ts, end_ts)

    def recent_ex(self, ticker: str, granularity: int = 60, since_ts: Optional[int] = None):
        return self._feed(ticker).recent_ex(ticker, granularity, since_ts)

    def recent(self, ticker: str, granularity: int = 60) -> List[Bar]:
        return self._feed(ticker).recent(ticker, granularity)

    def daily_volume(self, ticker: str, days: int = 5):
        return self._feed(ticker).daily_volume(ticker, days)
