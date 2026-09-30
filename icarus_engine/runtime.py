"""Live runtime: one AssetRunner per asset (feed → sub-bars → timeframe chains → strategy →
broker emulator), a Portfolio that owns them, and the journal.

Warm-up is built exactly like live operation: every chart bar after `T_w` (the
start of the warm-up window, aligned to a session boundary of the asset's
calendar) is aggregated from the finest sub-bars the feed offers, so there is no
seam between history and realtime. Slower timeframes get deeper native history
before `T_w` so their SuperTrend/ADX are seeded before the chart bars start.
All fetched sub-bars are kept in memory, so changing inputs re-warms an asset in
seconds without touching the network.
"""
from __future__ import annotations

import collections
import copy
import csv
import dataclasses
import io
import json
import math
import os
import re
import sqlite3
import threading
import time
from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Deque, Dict, List, Optional, Tuple

from .assets import AssetSpec, apply_chart_config, chart_capabilities, normalize_chart_timeframe, resolve, validate_chart_config
from .calendar import get_calendar
from .emulator import Emulator, Fill
from .feeds import Coinbase, Kraken
from .feeds.bars import HistoryHub, detect_granularity, file_feed_mode, find_history, parse_ohlcv_csv, read_text_csv  # Grok (xAI) — 2026-09-20
from .feeds.databento import Databento
from .feeds.yahoo import Yahoo
from .pine.series import NAN, na
from .pine.timeframe import Aggregator, Bar, tf_minutes
from .strategy.inputs import Inputs, crypto_profile
from .strategy.meta import load_meta
from .strategy.pulse import PulseStrategy
from .strategy.security import TFChain


def _session_mode(cal) -> str:
    """Human/reporting session mode; 24/7 calendars must never masquerade as ETH."""
    return "24/7" if getattr(cal, "open_24_7", False) else str(getattr(cal, "session", "eth"))


def _clean(x: Any) -> Any:
    """NaN / Inf → None so json.dumps(..., allow_nan=False) cannot empty-reply."""
    item = getattr(x, "item", None)
    if callable(item) and not isinstance(x, (bytes, str, dict, list, tuple, int, float, bool)):
        try:
            if getattr(x, "shape", None) == ():
                return _clean(item())
        except Exception:
            return None
    if isinstance(x, float):
        return None if x != x or x in (float("inf"), float("-inf")) else x
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    return x


# ──────────────────────────────────────────────────────────────────────
# Journal
# ──────────────────────────────────────────────────────────────────────
class Journal:
    """SQLite journal (WAL) + small in-memory tails for the dashboard."""

    def __init__(self, path: str):
        self.path = path
        self._lock = threading.RLock()
        self.con = sqlite3.connect(path, check_same_thread=False)
        self.con.execute("PRAGMA journal_mode=WAL")
        self.con.executescript("""
        CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY, symbol TEXT, entry_id TEXT, direction INTEGER, qty INTEGER,
            entry_price REAL, entry_ts INTEGER, exit_price REAL, exit_ts INTEGER, exit_comment TEXT, profit REAL, live INTEGER);
        CREATE TABLE IF NOT EXISTS fills (id INTEGER PRIMARY KEY, symbol TEXT, ts INTEGER, entry_id TEXT, side TEXT, qty INTEGER,
            price REAL, kind TEXT, comment TEXT, profit REAL, position_after INTEGER, live INTEGER);
        CREATE TABLE IF NOT EXISTS equity (ts REAL, equity REAL);
        CREATE TABLE IF NOT EXISTS log (ts REAL, level TEXT, msg TEXT);
        """)
        self.run_id = int(time.time())                        # every process start is a run; rows carry it (audit D2)
        for table, col, typ in (("trades", "piece", "INTEGER DEFAULT 0"), ("trades", "run_id", "INTEGER DEFAULT 0"),
                                ("fills", "run_id", "INTEGER DEFAULT 0"), ("log", "run_id", "INTEGER DEFAULT 0")):
            cols = [r[1] for r in self.con.execute(f"PRAGMA table_info({table})")]
            if col not in cols:
                self.con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {typ}")
        # warm-up replays are journaled once per run: a unique index keeps repeats out (INSERT OR IGNORE below).
        # `piece` distinguishes two pieces of one position that close identically on the same bar (audit D1);
        # fills are distinguished by the position they leave behind.
        self.con.executescript("""
        DROP INDEX IF EXISTS trades_uq; DROP INDEX IF EXISTS fills_uq;
        DELETE FROM trades WHERE rowid NOT IN (SELECT MIN(rowid) FROM trades GROUP BY run_id,symbol,entry_id,direction,qty,entry_price,entry_ts,exit_price,exit_ts,exit_comment,piece);
        DELETE FROM fills WHERE rowid NOT IN (SELECT MIN(rowid) FROM fills GROUP BY run_id,symbol,ts,entry_id,side,qty,price,kind,comment,position_after);
        CREATE UNIQUE INDEX IF NOT EXISTS trades_uq2 ON trades (run_id,symbol,entry_id,direction,qty,entry_price,entry_ts,exit_price,exit_ts,exit_comment,piece);
        CREATE UNIQUE INDEX IF NOT EXISTS fills_uq2 ON fills (run_id,symbol,ts,entry_id,side,qty,price,kind,comment,position_after);
        """)
        self.con.execute("DELETE FROM log WHERE ts < ?", (time.time() - 14 * 86400,))
        self.con.commit()
        self.log_tail: Deque[Dict[str, Any]] = collections.deque(maxlen=400)

    def log(self, level: str, msg: str) -> None:
        row = {"ts": time.time(), "level": level, "msg": msg}
        with self._lock:
            self.log_tail.append(row)
            self.con.execute("INSERT INTO log (ts,level,msg,run_id) VALUES (?,?,?,?)", (row["ts"], level, msg, self.run_id))
            self.con.commit()

    def add_trade(self, symbol: str, t, live: bool, piece: int = 0) -> None:
        with self._lock:
            self.con.execute("INSERT OR IGNORE INTO trades (symbol,entry_id,direction,qty,entry_price,entry_ts,exit_price,exit_ts,exit_comment,profit,live,piece,run_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                             (symbol, t.entry_id, t.direction, t.qty, t.entry_price, t.entry_ts, t.exit_price, t.exit_ts, t.exit_comment, t.profit, int(live), int(piece), self.run_id))
            self.con.commit()

    def add_fill(self, symbol: str, f: Fill, live: bool) -> None:
        with self._lock:
            self.con.execute("INSERT OR IGNORE INTO fills (symbol,ts,entry_id,side,qty,price,kind,comment,profit,position_after,live,run_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                             (symbol, f.ts, f.entry_id, f.side, f.qty, f.price, f.kind, f.comment, f.profit, f.position_after, int(live), self.run_id))
            self.con.commit()

    def add_equity(self, equity: float) -> None:
        with self._lock:
            self.con.execute("INSERT INTO equity VALUES (?,?)", (time.time(), equity))
            self.con.commit()

    def export_trades_csv(self, path: str, *, live_only: bool = False) -> int:
        with self._lock:
            return write_paper_csv(self.con, path, live_only=live_only)

    def equity_series(self, since_sec: float = 86400.0, max_points: int = 600, *, since_ts: Optional[float] = None) -> List[Dict[str, float]]:
        cutoff = float(since_ts) if since_ts is not None else (time.time() - since_sec)
        with self._lock:
            rows = self.con.execute("SELECT ts, equity FROM equity WHERE ts >= ? ORDER BY ts", (cutoff,)).fetchall()
        if len(rows) > max_points:
            step = len(rows) / max_points
            rows = [rows[int(k * step)] for k in range(max_points)] + [rows[-1]]
        return [{"ts": r[0], "equity": r[1]} for r in rows]


def export_paper_book(db_path: str, out_path: str, *, live_only: bool = False) -> int:
    """Read-only dump of the paper book. Safe while the engine holds the WAL.

    Grok (xAI) — 2026-09-20. Do not construct ``Journal(db)`` for export: that
    migrates schema and DELETEs duplicate rows on a live file.
    """
    abs_db = os.path.abspath(db_path)
    uri = "file:" + abs_db.replace("\\", "/") + "?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    try:
        return write_paper_csv(con, out_path, live_only=live_only)
    finally:
        con.close()


def write_paper_csv(con: sqlite3.Connection, path: str, *, live_only: bool = False) -> int:
    """Write the paper book. Not a broker statement. Not CME.

    Grok (xAI) — 2026-09-20. Journal ``live=0`` is replay; ``live=1`` records fills processed live. In-memory epoch metrics reset on successful warm/re-warm.
    """
    from datetime import datetime, timezone
    try:
        from zoneinfo import ZoneInfo
        ny = ZoneInfo("America/New_York")
    except Exception:
        ny = timezone.utc

    def iso(ts: int) -> str:
        if not ts:
            return ""
        return datetime.fromtimestamp(int(ts), tz=ny).isoformat()

    q = "SELECT run_id,live,symbol,direction,qty,entry_id,entry_ts,entry_price,exit_ts,exit_price,exit_comment,profit,piece FROM trades"
    if live_only:
        q += " WHERE live=1"
    q += " ORDER BY exit_ts, id"
    rows = con.execute(q).fetchall()
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow([
            "run_id", "live", "symbol", "side", "qty", "entry_id",
            "entry_ts", "entry_time_et", "entry_price",
            "exit_ts", "exit_time_et", "exit_price", "exit_comment", "profit", "piece",
            "disclaimer",
        ])
        disclaimer = "Icarus paper emulator — not a broker statement, not CME"
        for r in rows:
            run_id, live, symbol, direction, qty, entry_id, entry_ts, entry_price, exit_ts, exit_price, exit_comment, profit, piece = r
            side = "long" if int(direction or 0) > 0 else "short"
            w.writerow([
                run_id, int(live or 0), symbol, side, qty, entry_id,
                entry_ts, iso(entry_ts), entry_price,
                exit_ts, iso(exit_ts), exit_price, exit_comment, profit, piece,
                disclaimer,
            ])
    return len(rows)


# ──────────────────────────────────────────────────────────────────────
# Inputs resolution (defaults → profile → preset → inputs.json → inputs.<SYM>.json)
# ──────────────────────────────────────────────────────────────────────
def _read_json(path: str) -> Dict[str, Any]:
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        try:
            d = json.load(fh, parse_constant=_no_constants)
        except ValueError as ex:
            raise ValueError(f"{os.path.basename(path)}: not valid JSON ({ex})") from None
    if not isinstance(d, dict):
        raise ValueError(f"{os.path.basename(path)}: expected a JSON object")
    return d


def _no_constants(name: str):
    raise ValueError(f"{name} is not allowed in inputs")


_PRESET_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9 _.+\-]{0,60}")
_INPUT_TYPES = {f.name: str(f.type) for f in dataclasses.fields(Inputs)}
_UNCHANGED = object()


def preset_path(base_dir: str, name: str) -> str:
    """presets/<name>.json, confined to the presets directory."""
    if not name or not _PRESET_RE.fullmatch(str(name)):
        raise ValueError(f"bad preset name {name!r}")
    root = os.path.realpath(os.path.join(base_dir, "presets"))
    p = os.path.realpath(os.path.join(root, f"{name}.json"))
    if os.path.commonpath([root, p]) != root:
        raise ValueError(f"bad preset name {name!r}")
    return p


def validate_values(vals: Dict[str, Any]) -> None:
    """Type/range/option checks for input values (dataclass field types + the Pine's min/max/options)."""
    meta = {e["name"]: e for e in load_meta()}
    for k, v in list(vals.items()):
        t = _INPUT_TYPES.get(k, "")
        if t == "bool" and not isinstance(v, bool):
            raise ValueError(f"{k}: expected true/false, got {v!r}")
        if t == "int" and (isinstance(v, bool) or not isinstance(v, int)):
            if isinstance(v, float) and v.is_integer():
                vals[k] = v = int(v)
            else:
                raise ValueError(f"{k}: expected an integer, got {v!r}")
        if t == "float":
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                raise ValueError(f"{k}: expected a finite number, got {v!r}")
        if t == "str" and not isinstance(v, str):
            raise ValueError(f"{k}: expected a string, got {v!r}")
        e = meta.get(k)
        if e:
            if e.get("options") and v not in e["options"]:
                raise ValueError(f"{k}: must be one of {e['options']}")
            if isinstance(v, (int, float)) and not isinstance(v, bool):
                if e.get("minval") is not None and v < e["minval"]:
                    raise ValueError(f"{k}: below the script's minimum {e['minval']}")
                if e.get("maxval") is not None and v > e["maxval"]:
                    raise ValueError(f"{k}: above the script's maximum {e['maxval']}")
            if e.get("kind") == "timeframe":
                tf_minutes(v)
            if e.get("kind") == "session" and not re.fullmatch(r"\d{4}-\d{4}", str(v)):
                raise ValueError(f"{k}: sessions are HHMM-HHMM")


def resolve_inputs(spec: AssetSpec, base_dir: str, profile: str = "nq", preset: Optional[str] = None,
                   extra: Optional[Dict[str, Any]] = None, *, skip_asset_overrides: bool = False,
                   extra_label: str = "override") -> Tuple[Inputs, Dict[str, Any], List[str]]:
    """Returns (inputs, preset_meta, sources). Values later in the chain override earlier ones."""
    base = (crypto_profile(0.0, spec.mintick) if profile == "crypto" else Inputs()).to_dict()
    known = set(base)
    sources: List[str] = [f"profile:{profile}"]
    meta: Dict[str, Any] = {}

    def apply(d: Dict[str, Any], label: str) -> None:
        nonlocal meta
        if not d:
            return
        m = d.get("_meta")
        if isinstance(m, dict):
            meta = {**meta, **m}
        vals = {k: v for k, v in d.items() if not k.startswith("_")}
        bad = [k for k in vals if k not in known]
        if bad:
            raise ValueError(f"{label}: unknown input names {bad}")
        validate_values(vals)
        base.update(vals)
        sources.append(f"{label} ({len(vals)})")

    name = preset or spec.preset
    if name:
        apply(_read_json(preset_path(base_dir, name)), f"preset:{name}")
    apply(_read_json(os.path.join(base_dir, "inputs.json")), "inputs.json")
    if not skip_asset_overrides:
        apply(_read_json(os.path.join(base_dir, f"inputs.{spec.symbol}.json")), f"inputs.{spec.symbol}.json")
    if extra:
        apply(dict(extra), extra_label)
    return Inputs(**base), meta, sources


def apply_spec_meta(spec: AssetSpec, meta: Optional[Dict[str, Any]]) -> AssetSpec:
    """Apply Properties metadata without overriding explicit startup/API pins."""
    out = replace(spec)
    meta = meta or {}
    pins = set(getattr(out, "config_pins", ()) or ())
    chart = {k: meta[k] for k in ("chart_type", "fill_on", "security_source")
             if k not in pins and meta.get(k) not in (None, "")}
    if "timeframe" not in pins and meta.get("timeframe") not in (None, ""):
        chart["timeframe"] = meta["timeframe"]
    out = apply_chart_config(out, chart)
    if "slippage_ticks" not in pins and meta.get("slippage_ticks") is not None:
        out.slippage_ticks = int(meta["slippage_ticks"])
    if "commission" not in pins and meta.get("commission") is not None:
        out.commission = float(meta["commission"])
    if "capital" not in pins and meta.get("capital") is not None:
        out.capital = float(meta["capital"])
    if "session" not in pins and meta.get("session") in ("rth", "eth") and out.calendar == "cme":
        out.session = str(meta["session"])
    return out


class HeikinAshi:
    """TradingView Heikin Ashi transform, computed on the chart timeframe. TradingView quantises the HA
    series to the symbol's tick (every HA open/close in the owner's export is a tick multiple; the audit's
    rounded replay reproduces 11/15 known HA opens exactly vs 0/15 unrounded), so `mintick` rounds each
    recursion step; `mintick=None` keeps the exact arithmetic."""
    def __init__(self, mintick: Optional[float] = None):
        self.prev_open = NAN
        self.prev_close = NAN
        self.mintick = mintick

    def _q(self, x: float) -> float:
        return round(round(x / self.mintick) * self.mintick, 10) if self.mintick else x

    def transform(self, b: Bar) -> Bar:
        ha_close = self._q((b.o + b.h + b.l + b.c) / 4.0)
        ha_open = self._q((b.o + b.c) / 2.0 if na(self.prev_open) else (self.prev_open + self.prev_close) / 2.0)
        ha_high = max(b.h, ha_open, ha_close)
        ha_low = min(b.l, ha_open, ha_close)
        self.prev_open, self.prev_close = ha_open, ha_close
        return Bar(b.ts, ha_open, ha_high, ha_low, ha_close, b.v)


# ──────────────────────────────────────────────────────────────────────
# AssetRunner
# ──────────────────────────────────────────────────────────────────────
@dataclass
class RunnerConfig:
    spec: AssetSpec
    inputs: Inputs
    warmup_bars: int = 1200
    pts_ref_price: float = 0.0        # NQ price used to rescale *_pts inputs to this asset (0 = literal points)
    sources: Optional[List[str]] = None
    profile: str = "nq"
    preset: Optional[str] = None
    fixed_pts_scale: Optional[float] = None  # cached replay scale; never fetch a current reference
    mintick: Optional[float] = None          # cached replay tick; avoid product metadata network calls
    scale_known_at: Optional[int] = None    # actual receipt/computation time, never inferred from a price's date
    base_dir: Optional[str] = None          # Grok (xAI) — plant root; warmup looks here, not cwd
    base_spec: Optional[AssetSpec] = None    # startup/API-pinned baseline before preset/global/asset metadata


class AssetRunner:
    def __init__(self, cfg: RunnerConfig, journal: Journal, feeds: Optional[Dict[str, Any]] = None):
        self.cfg = cfg
        self.spec = cfg.spec
        if self.cfg.base_spec is None:
            self.cfg.base_spec = replace(cfg.spec)
        self.symbol = self.spec.symbol
        self.journal = journal
        feeds = feeds or {}
        self.feed = feeds.get(self.spec.feed) or (Yahoo() if self.spec.feed == "yahoo" else Coinbase())
        self.kraken = Kraken()
        self.cal = get_calendar(self.spec.calendar, self.spec.anchor_et, session=self.spec.session, group=self.spec.group)
        self.chart_minutes = tf_minutes(self.spec.chart_tf)
        self.mintick = cfg.mintick if cfg.mintick is not None else (self.spec.mintick if self.spec.feed == "yahoo" else self.feed.mintick(self.spec.ticker))
        # Active futures never resolve to expiring month-coded contracts. The provider-native
        # continuous ticker is the live/data ticker; tv_symbol carries the TradingView 1! identity.
        self.live_ticker = self.spec.ticker                 # compatibility alias: always provider-native continuous for futures
        self.feed_time: float = 0.0                         # the feed's own clock (Yahoo: regularMarketTime)
        self.feed_delay: float = 0.0
        self.inputs_base: Inputs = cfg.inputs
        self.inputs: Inputs = cfg.inputs
        self.pts_scale = cfg.fixed_pts_scale if cfg.fixed_pts_scale is not None else 1.0
        self.last_price: Optional[float] = None
        self.last_price_ts: float = 0.0
        self.last_bar_wall: float = 0.0
        self.subbars: List[Tuple[Bar, int]] = []            # everything fed since T_w (for fast re-warm)
        self.deep: Dict[int, List[Tuple[Bar, int]]] = {}    # chain minutes → deep history (before T_w)
        self.T_w: Optional[int] = None
        self._build_engine()
        self.bar_index = -1
        self.bars: Deque[Bar] = collections.deque(maxlen=900)
        self.overlays: Deque[Dict[str, Any]] = collections.deque(maxlen=900)
        self.state: Dict[str, Any] = {}
        self.live_from_ts: Optional[int] = None
        self.live_closed_start: int = 0               # exact closed-trade boundary; avoids bar-start timestamp misclassification
        self.last_sub_ts: Optional[int] = None
        self._file_waiting: bool = False
        self._fills_seen = 0
        self._closed_seen = 0
        self.paused = False
        self.errors = 0
        self.last_error = ""
        self.feed_error = ""
        self.runtime_error = ""
        self.last_poll_ok = 0.0
        self.warm = False
        self.rewarming = False
        self._removed = False
        self.lock = threading.RLock()
        self.recent_fills: Deque[Dict[str, Any]] = collections.deque(maxlen=300)
        self.recent_events: Deque[Dict[str, Any]] = collections.deque(maxlen=300)

    # ── engine construction (also used by re-warm) ──
    def _build_engine(self) -> None:
        sp = self.spec
        self.chart_minutes = tf_minutes(sp.chart_tf)
        self.cal = get_calendar(sp.calendar, sp.anchor_et, session=sp.session, group=sp.group)   # a preset may switch the chart session
        self.em = Emulator(sp.capital, sp.commission, self.mintick, sp.multiplier, pyramiding=2, slippage_ticks=sp.slippage_ticks)
        self.strat: Optional[PulseStrategy] = None
        ib = self.inputs_base
        self.htf_tfs = [tf_minutes(t) for t in (ib.htf_tf_1, ib.htf_tf_2, ib.htf_tf_3, ib.htf_tf_4, ib.htf_tf_5)]
        ha_chains = sp.chart_type == "heikin_ashi" and sp.security_source == "chart"      # TradingView: request.security on an HA chart returns HA data
        self.chains: Dict[int, TFChain] = {m: TFChain(m, self.cal.bucket_start, self.cal.bucket_end, ha=ha_chains, ltf_intrabar=ib.ltf_intrabar, mintick=self.mintick)
                                           for m in sorted(set(self.htf_tfs + [2, 5]))}
        self.chart_agg = Aggregator(self.chart_minutes, self.cal.bucket_start, self.cal.bucket_end)
        self.ha = HeikinAshi(mintick=self.mintick) if sp.chart_type == "heikin_ashi" else None
        self._real_ohlc_warned = False

    def _asset_ref_price(self, fallback: float) -> float:
        """The asset's last completed daily close (the same instant as the NQ reference) - reproducible run to run."""
        if self.spec.feed == "yahoo":
            try:
                rows = self.feed.daily_volume(self.spec.ticker, 6)
                so = self.cal.bucket_start(int(time.time()), 1440)
                done = [r for r in rows if r[0] < so]
                if done:
                    return float(done[-1][1])
            except Exception as ex:
                self.journal.log("WARN", f"[{self.symbol}] daily close for point scaling unavailable ({ex}); using the first bar")
        return fallback

    def _init_strategy(self, price: float) -> None:
        inp = self.inputs_base
        if self.cfg.fixed_pts_scale is not None:
            k = self.cfg.fixed_pts_scale
        else:
            price = self._asset_ref_price(price) if self.cfg.pts_ref_price > 0 else price
            k = price / self.cfg.pts_ref_price if self.cfg.pts_ref_price > 0 and price > 0 else 1.0
            if self.cfg.pts_ref_price > 0:
                self.cfg.scale_known_at = math.ceil(time.time())
        if self.cfg.pts_ref_price > 0 or self.cfg.fixed_pts_scale is not None:
            self.pts_scale = k
            if abs(k - 1.0) > 1e-6:
                inp = replace(inp, tp1_pts=inp.tp1_pts * k, tp2_pts=inp.tp2_pts * k, sl_pts=inp.sl_pts * k,
                              be_offset_pts=max(self.mintick, inp.be_offset_pts * k))
                self.journal.log("INFO", f"[{self.symbol}] NQ-point inputs rescaled x{k:.4g}: tp1 {inp.tp1_pts:.6g} tp2 {inp.tp2_pts:.6g} sl {inp.sl_pts:.6g}")
        if abs(inp.point_value - self.spec.multiplier) > 1e-9 and inp.point_value == Inputs().point_value:
            inp = replace(inp, point_value=self.spec.multiplier)          # the Pine's 20 = NQ; Risk-$ sizing needs this asset's $/point
        self.inputs = inp
        self.strat = PulseStrategy(inp, self.em, mintick=self.mintick, tf_minutes=self.chart_minutes, session_key=self.cal.session_id)

    # ── core bar path ──
    def _on_chart_bar(self, real: Bar, live: bool) -> None:
        if self.strat is None:
            self._init_strategy(real.c)
        ha_bar = self.ha.transform(real) if self.ha else None
        # "Use Real OHLC for Calculations": the script re-requests its own symbol with request.security(syminfo.tickerid, ...)
        # which, on a Heikin Ashi chart, returns HA data again (the ticker id carries the HA modifier) - a no-op in
        # TradingView (security_source="chart"). security_source="standard" honours the toggle's intent (real bars).
        if ha_bar is not None and self.inputs_base.use_real_ohlc and self.spec.security_source == "standard":
            chart = real
        else:
            chart = ha_bar or real
            if ha_bar is not None and self.inputs_base.use_real_ohlc and not self._real_ohlc_warned:
                self._real_ohlc_warned = True
                self.journal.log("WARN", f"[{self.symbol}] use_real_ohlc is on but TradingView's request.security(syminfo.tickerid) returns Heikin Ashi data on an HA chart - ignored (security_source=chart); set security_source=standard to use real bars")
        fill_bar = (ha_bar or real) if self.spec.fill_on == "chart" else real
        self.bar_index += 1
        self.strat.paused = self.paused
        if self.paused:
            self._cancel_pending_entries()
        self.em.process_bar(fill_bar, self.bar_index)
        htf = [self.chains[m].htf_values(chart.ts) for m in self.htf_tfs]
        t_close = self.cal.bucket_end(chart.ts, self.chart_minutes)
        ltf = [self.chains[2].ltf_values(chart.ts, self.chart_minutes, t_close), self.chains[5].ltf_values(chart.ts, self.chart_minutes, t_close)]
        st = self.strat.on_bar(chart, self.bar_index, htf, ltf, time_close=t_close)
        self.state = st
        self.bars.append(chart)
        self.last_bar_wall = time.time()
        self.overlays.append({"ts": chart.ts, "st": st["rate_st_line"], "up": st["rate_uptrend"], "tp1": st["tp1_price"], "tp2": st["tp2_price"],
                              "sl": st["sl_price"], "vwap": st["vwap"], "kf": st["kf_level"], "pos": st["rate_qty_open"] * (1 if st["rate_pos_long"] else -1),
                              "tide_hi": st["tide_hi"], "tide_lo": st["tide_lo"], "pulse": max(st["pulse_l"], st["pulse_s"]), "real_c": real.c})
        for f in self.em.fills[self._fills_seen:]:
            self.recent_fills.append({"ts": f.ts, "bar": f.bar, "id": f.entry_id, "side": f.side, "qty": f.qty, "price": f.price,
                                      "kind": f.kind, "comment": f.comment, "profit": f.profit, "pos": f.position_after, "live": live})
            if live or not self.rewarming:
                self.journal.add_fill(self.symbol, f, live)
            if live:
                self.journal.log("INFO", f"[{self.symbol}] FILL {f.side.upper()} {f.qty} @ {f.price:.6g} {f.kind} {f.comment}" + (f" P&L {f.profit:+.2f}" if f.profit is not None else "") + f" -> pos {f.position_after:+d}")
        self._fills_seen = len(self.em.fills)
        for idx in range(self._closed_seen, len(self.em.closed)):
            t = self.em.closed[idx]
            if live or not self.rewarming:
                key = (t.entry_id, t.entry_ts, t.exit_ts, t.exit_comment, t.qty, t.exit_price)
                piece = sum(1 for u in self.em.closed[:idx] if (u.entry_id, u.entry_ts, u.exit_ts, u.exit_comment, u.qty, u.exit_price) == key)
                self.journal.add_trade(self.symbol, t, live, piece)
        self._closed_seen = len(self.em.closed)
        for ev in self.strat.events:
            self.recent_events.append(dict(ev, live=live))
            if live:
                self.journal.log("INFO", f"[{self.symbol}] {ev['text']}")
        self.strat.events.clear()

    def on_sub_bar(self, b: Bar, sub_minutes: int, live: bool, record: bool = True) -> None:
        """Feed one sub-bar (1m or 5m) to every chain and the chart aggregator."""
        with self.lock:
            if self.last_sub_ts is not None and b.ts <= self.last_sub_ts:
                return
            if not self.cal.is_open(b.ts):                    # bars outside the session (Yahoo sometimes returns them) are ignored
                return
            self.last_sub_ts = b.ts
            if record:
                self.subbars.append((b, sub_minutes))
            intraday = self.cal.intraday_open(b.ts)             # RTH charts: intraday bars exist 09:30-16:15 ET only
            for ch in self.chains.values():
                if sub_minutes <= ch.minutes and ch.minutes % sub_minutes == 0 and (ch.minutes >= 1440 or intraday):
                    ch.push_sub_bar(b, sub_minutes)
            if intraday and self.chart_minutes % sub_minutes == 0:
                for cb in self.chart_agg.push(b, sub_minutes):
                    self._on_chart_bar(cb, live)
            self.last_price = b.c

    # ── warm-up ──
    def warmup(self, now_ts: Optional[int] = None) -> None:
        now = int(now_ts or time.time())
        span = self.cfg.warmup_bars * self.chart_minutes * 60
        if not self.cal.open_24_7:
            if getattr(self.cal, "session", "eth") == "rth":  # ~20 bars per trading day (09:30-16:15 ET), 5 days a week
                per_day = max(1, 405 // self.chart_minutes)
                span = int(self.cfg.warmup_bars / per_day * 7 / 5 * 86400) + 3 * 86400
            else:                                             # 5 sessions of 23h per week → stretch the calendar window
                span = int(span * 7 / 5 * 24 / 23) + 86400
        T_w = self.cal.bucket_start(now - span, 1440)
        self.T_w = T_w
        base = self.cfg.base_dir or os.getcwd()
        hist, minutes = find_history(base, self.symbol, self.chart_minutes)  # Grok (xAI) — 2026-09-20: prefer history/ over Yahoo; plant root over cwd
        if hist:
            src = f"history/{os.path.basename(hist)} ({minutes}m)"
        elif file_feed_mode():
            src = f"HistoryHub ({base}/history) — no CSV yet, Yahoo is not contacted"
        else:
            src = self.spec.feed
        self.journal.log("INFO", f"[{self.symbol}] warm-up from {time.strftime('%Y-%m-%d %H:%M', time.gmtime(T_w))}Z ({self.cfg.warmup_bars} x {self.chart_minutes}m bars, {src}) mintick={self.mintick} x{self.spec.multiplier} slip={self.spec.slippage_ticks}t chart={self.spec.chart_type} fills={self.spec.fill_on} session={_session_mode(self.cal)} security={self.spec.security_source}" + (f" continuous={self.spec.tv_symbol or self.spec.ticker}" if self.spec.kind == "futures" else ""))
        if hist:
            self._warmup_from_csv(hist, now, source_minutes=minutes)
            self._file_waiting = False
        elif file_feed_mode():
            self._file_waiting = True
            self.journal.log("WARN", f"[{self.symbol}] ICARUS_FEED=file and no history/{self.symbol}_*m.csv — waiting for drop ingest; Yahoo is not contacted")
        elif self.spec.feed == "yahoo":
            self._warmup_yahoo(T_w, now)  # same interface for Yahoo or Databento continuous futures
        else:
            self._warmup_coinbase(T_w, now)
        self.live_from_ts = now
        self.live_closed_start = len(self.em.closed)
        self.warm = True
        if file_feed_mode() and self.last_sub_ts is None and not self._file_waiting:
            self.last_sub_ts = now  # a later drop must not replay years of history as live fills
        if self.last_price is None:
            self.last_price = self.feed.ticker(self.spec.ticker)
        self.journal.log("INFO", f"[{self.symbol}] warm-up done: {self.bar_index + 1} chart bars, {len(self.em.closed)} historical trades, net {self.em.netprofit:+.2f}; market {self.cal.describe(now)}")

    def _closed_only(self, bars: List[Bar], ticker: str) -> List[Bar]:
        """Drop the feed's still-forming minute: closed <=> ts + 60 <= the feed's clock (regularMarketTime)."""
        ft = int((getattr(self.feed, "_meta", {}).get(ticker) or {}).get("regularMarketTime") or 0)
        if ft:
            self.feed_time = ft
            return [b for b in bars if b.ts + 60 <= ft]
        return bars[:-1] if bars else bars

    def _push_deep(self, ch: TFChain, b: Bar, sub_min: int) -> None:
        if not self.cal.is_open(b.ts):
            return
        if ch.minutes < 1440 and not self.cal.intraday_open(b.ts):
            return
        if ch.minutes < 1440 and self.cal.bucket_start(b.ts, sub_min) != b.ts:
            return                                                # a native bar not aligned to this chart's buckets (e.g. :00 hourly on a :30 chain)
        ch.push_sub_bar(b, sub_min)

    def _feed_deep(self, minutes_list: List[int], bars: List[Bar], sub_min: int) -> None:
        for m in minutes_list:
            ch = self.chains.get(m)
            if ch is None:
                continue
            self.deep.setdefault(m, []).extend((b, sub_min) for b in bars)
            for b in bars:
                self._push_deep(ch, b, sub_min)

    def _warmup_coinbase(self, T_w: int, now: int) -> None:
        cb = self.feed
        deep = {10080: (86400, 800 * 86400), 1440: (86400, 400 * 86400), 240: (3600, 45 * 86400), 120: (3600, 45 * 86400), 60: (3600, 45 * 86400),
                30: (900, 8 * 86400), 20: (300, 5 * 86400), 15: (900, 8 * 86400), 10: (300, 5 * 86400)}
        cache: Dict[Tuple[int, int], List[Bar]] = {}
        for m in self.chains:
            if m not in deep:
                continue
            g, depth = deep[m]
            key = (g, depth)
            if key not in cache:
                cache[key] = cb.candles(self.spec.ticker, g, T_w - depth, T_w)
            self._feed_deep([m], cache[key], g // 60)
        ones = cb.candles(self.spec.ticker, 60, T_w, now - 60)
        self.journal.log("INFO", f"[{self.symbol}] {len(ones)} one-minute candles fetched; replaying")
        for b in ones:
            self.on_sub_bar(b, 1, live=False)

    def _warmup_yahoo(self, T_w: int, now: int) -> None:
        y: Yahoo = self.feed
        tk = self.spec.ticker                                 # provider-native continuous symbol (e.g. NQ=F)
        tki = self.spec.ticker                                # intraday also stays continuous; no month-coded expiry contract
        daily = y.candles(tk, 86400, T_w - 900 * 86400, T_w)
        daily = [Bar(self.cal.bucket_start(b.ts, 1440), b.o, b.h, b.l, b.c, b.v) for b in daily]   # stamp at the session open
        self._feed_deep([m for m in self.chains if m >= 1440], daily, 1440)
        rth = getattr(self.cal, "session", "eth") == "rth"
        if rth:                                               # RTH hourly buckets sit at :30 - build them from 15-minute bars (60 days)
            hourly = []
        else:
            hourly = y.candles(tki, 3600, max(T_w - 400 * 86400, now - 729 * 86400), T_w)
            self._feed_deep([m for m in self.chains if 60 <= m < 1440], hourly, 60)
        q15 = y.candles(tki, 900, max(T_w - 40 * 86400, now - 59 * 86400), T_w)
        self._feed_deep([m for m in self.chains if 15 <= m < 1440 and m % 15 == 0 and (rth or m < 60)], q15, 15)
        fives_deep = y.candles(tki, 300, max(T_w - 20 * 86400, now - 59 * 86400), T_w)
        self._feed_deep([m for m in self.chains if 5 <= m < 15 and m % 5 == 0], fives_deep, 5)
        one_from = max(T_w, now - 29 * 86400)
        fives = y.candles(tki, 300, T_w, one_from) if one_from > T_w else []
        ones = self._closed_only(y.candles(tki, 60, one_from, now), tki)
        self.journal.log("INFO", f"[{self.symbol}] deep {len(daily)}d/{len(hourly)}h/{len(q15)}x15m/{len(fives_deep)}x5m; {len(fives)} five-minute + {len(ones)} one-minute sub-bars; replaying")
        for b in fives:
            self.on_sub_bar(b, 5, live=False)
        for b in ones:
            if fives and b.ts < fives[-1].ts + 300:
                continue
            self.on_sub_bar(b, 1, live=False)

    def _warmup_from_csv(self, path: str, now: int, source_minutes: Optional[int] = None) -> None:
        """Warm up from a TradingView Supercharts export (or canonical history/*.csv).

        Grok (xAI) — 2026-09-20. Prefer a 1-minute dump: HTF/LTF chains then
        aggregate the same way live 1m sub-bars do. A chart-TF export is accepted
        as a fallback (HTF built from those coarser bars). The live feed, if it
        answers, fills the tail after the last exported bar. No interpolated ticks.
        """
        rows = parse_ohlcv_csv(read_text_csv(path))
        if source_minutes is None:
            source_minutes = max(1, detect_granularity(rows) // 60)
        source_minutes = int(source_minutes)
        span = (
            time.strftime("%Y-%m-%d", time.gmtime(rows[0].ts)) + " → " +
            time.strftime("%Y-%m-%d", time.gmtime(rows[-1].ts))
        ) if rows else "-"
        how = "HTF chains from 1m" if source_minutes == 1 else "chart bars from the export, HTF built from them"
        self.journal.log("INFO", f"[{self.symbol}] history/{os.path.basename(path)}: {len(rows)} {source_minutes}m bars ({span}); {how}")
        for b in rows:
            self.on_sub_bar(b, source_minutes, live=False)
        if rows:
            self.T_w = rows[0].ts
            if file_feed_mode():
                return  # Grok (xAI) — offline plant: the CSV is the whole tape; do not call Yahoo for a tail
            tail_from = rows[-1].ts + source_minutes * 60
            try:
                ones = self.feed.candles(self.spec.ticker, 60, max(tail_from, now - 29 * 86400), now)
                if self.spec.feed == "yahoo":
                    ones = self._closed_only(ones, self.spec.ticker)
                for b in ones:
                    if b.ts < tail_from:
                        continue
                    self.on_sub_bar(b, 1, live=False)
            except Exception as ex:
                self.journal.log("WARN", f"[{self.symbol}] could not fetch the 1-minute tail after the export: {ex}")

    def configuration_snapshot(self) -> Dict[str, Any]:
        """Exact in-memory state needed to make a failed configuration change a no-op."""
        return {
            "spec": copy.deepcopy(self.spec),
            "cfg_inputs": self.cfg.inputs,
            "cfg_sources": list(self.cfg.sources or []),
            "cfg_fixed_pts_scale": self.cfg.fixed_pts_scale,
            "cfg_scale_known_at": self.cfg.scale_known_at,
            "cfg_preset": self.cfg.preset,
            "inputs_base": self.inputs_base,
            "inputs": self.inputs,
            "pts_scale": self.pts_scale,
            "cal": self.cal,
            "chart_minutes": self.chart_minutes,
            "em": self.em,
            "strat": self.strat,
            "htf_tfs": list(self.htf_tfs),
            "chains": self.chains,
            "chart_agg": self.chart_agg,
            "ha": self.ha,
            "_real_ohlc_warned": self._real_ohlc_warned,
            "bar_index": self.bar_index,
            "bars": collections.deque(self.bars, maxlen=self.bars.maxlen),
            "overlays": collections.deque(self.overlays, maxlen=self.overlays.maxlen),
            "state": self.state,
            "live_from_ts": self.live_from_ts,
            "live_closed_start": self.live_closed_start,
            "last_sub_ts": self.last_sub_ts,
            "last_price": self.last_price,
            "last_price_ts": self.last_price_ts,
            "last_bar_wall": self.last_bar_wall,
            "_fills_seen": self._fills_seen,
            "_closed_seen": self._closed_seen,
            "recent_fills": collections.deque(self.recent_fills, maxlen=self.recent_fills.maxlen),
            "recent_events": collections.deque(self.recent_events, maxlen=self.recent_events.maxlen),
            "runtime_error": self.runtime_error,
            "last_error": self.last_error,
        }

    def restore_configuration_snapshot(self, snap: Dict[str, Any]) -> None:
        """Restore a snapshot without replaying, preserving exact paper accounting."""
        self.spec.__dict__.clear()
        self.spec.__dict__.update(copy.deepcopy(snap["spec"].__dict__))
        self.cfg.spec = self.spec
        self.cfg.inputs = snap["cfg_inputs"]
        self.cfg.sources = list(snap["cfg_sources"])
        self.cfg.fixed_pts_scale = snap["cfg_fixed_pts_scale"]
        self.cfg.scale_known_at = snap["cfg_scale_known_at"]
        self.cfg.preset = snap["cfg_preset"]
        self.inputs_base = snap["inputs_base"]
        self.inputs = snap["inputs"]
        self.pts_scale = snap["pts_scale"]
        for name in ("cal", "chart_minutes", "em", "strat", "chains", "chart_agg", "ha", "_real_ohlc_warned",
                     "bar_index", "state", "live_from_ts", "live_closed_start", "last_sub_ts", "last_price",
                     "last_price_ts", "last_bar_wall", "_fills_seen", "_closed_seen", "runtime_error", "last_error"):
            setattr(self, name, snap[name])
        self.htf_tfs = list(snap["htf_tfs"])
        self.bars = collections.deque(snap["bars"], maxlen=snap["bars"].maxlen)
        self.overlays = collections.deque(snap["overlays"], maxlen=snap["overlays"].maxlen)
        self.recent_fills = collections.deque(snap["recent_fills"], maxlen=snap["recent_fills"].maxlen)
        self.recent_events = collections.deque(snap["recent_events"], maxlen=snap["recent_events"].maxlen)
        self.rewarming = False

    # ── re-warm with new inputs (no network) ──
    def rewarm(self, inputs: Inputs, sources: Optional[List[str]] = None, *, reset_live_boundary: bool = False) -> None:
        with self.lock:
            self.ensure_configurable()
            self.ensure_cached_timeframes(inputs)
            self.rewarming = True
            try:
                self.cfg.fixed_pts_scale = self.pts_scale
                self.cfg.inputs = inputs
                self.inputs_base = inputs
                if sources is not None:
                    self.cfg.sources = sources
                self._build_engine()
                self.bar_index = -1
                self.bars.clear(); self.overlays.clear(); self.recent_fills.clear(); self.recent_events.clear()
                self._fills_seen = 0; self._closed_seen = 0; self.last_sub_ts = None; self.state = {}
                for m, rows in self.deep.items():
                    ch = self.chains.get(m)
                    if ch:
                        for b, sub in rows:
                            self._push_deep(ch, b, sub)
                for b, sub in list(self.subbars):
                    self.on_sub_bar(b, sub, live=False, record=False)
                if reset_live_boundary:
                    self.live_from_ts = int(time.time())
                    self.live_closed_start = len(self.em.closed)
                self.journal.log("INFO", f"[{self.symbol}] re-warmed with new inputs: {self.bar_index + 1} chart bars, {len(self.em.closed)} historical trades, net {self.em.netprofit:+.2f}")
                self.runtime_error = ""
                self.last_error = self.feed_error
            finally:
                self.rewarming = False

    # ── live polling ──
    def _feed_delay_at(self, now: int) -> float:
        """The feed's lag behind the wall clock - meaningful only while the market trades (the feed clock stops at the close)."""
        if self.spec.feed != "yahoo" or not self.cal.is_open(now):
            return 0.0
        return self.feed_delay

    def _feed_failed(self, message):
        with self.lock:
            self.errors += 1
            self.feed_error = str(message)
            self.last_error = self.runtime_error or self.feed_error

    def poll(self) -> None:
        now = time.time()
        if file_feed_mode() and self._file_waiting:
            base = self.cfg.base_dir or os.getcwd()
            hist, minutes = find_history(base, self.symbol, self.chart_minutes)
            if hist:
                self._warmup_from_csv(hist, int(now), source_minutes=minutes)
                self._file_waiting = False
                if self.last_price is None:
                    self.last_price = self.feed.ticker(self.spec.ticker)
            return
        feed_now = now
        px = None
        try:
            if self.spec.feed == "yahoo":
                bars, ft, px = self.feed.recent_ex(self.spec.ticker, 60, since_ts=self.last_sub_ts)
                if not ft:                                          # no feed clock in the response: the last aligned minute is the only safe clock
                    ft = (bars[-1].ts + 60) if bars else int(self.feed_time or 0)
                if not ft:
                    self._feed_failed("feed returned no clock and no bars"); return
                self.feed_time = ft
                feed_now = ft                                       # Yahoo is ~10 min behind: close bars on ITS clock, never the wall clock
                self.feed_delay = now - ft
            else:
                bars = self.feed.recent(self.spec.ticker, 60)
        except Exception as ex:
            if self.spec.feed == "coinbase":
                try:
                    bars = self.kraken.recent(self.spec.ticker, 1)
                except Exception as ex2:
                    self._feed_failed(f"{ex} / {ex2}"); return
            else:
                self._feed_failed(str(ex)); return
        closed_before = feed_now if self.spec.feed == "yahoo" else now - 5      # Coinbase is realtime: a minute is closed 5 s after its end
        new = [b for b in bars if (self.last_sub_ts is None or b.ts > self.last_sub_ts) and b.ts + 60 <= closed_before]
        for b in new:
            self.on_sub_bar(b, 1, live=True)
        with self.lock:
            for ch in self.chains.values():
                ch.flush_if_stale(feed_now - 45)
            stale = self.chart_agg.flush_if_stale(feed_now - 45)
            if stale is not None:
                self._on_chart_bar(stale, True)
        if px is None and bars:
            px = bars[-1].c
        if px:
            self.last_price = px
            self.last_price_ts = feed_now
        self.last_poll_ok = now
        with self.lock:
            if self.feed_error and self.last_error == self.feed_error:
                self.last_error = self.runtime_error
            self.feed_error = ""

    # ── admin ──
    def _cancel_pending_entries(self) -> int:
        """Caller holds lock. Keep exits/close orders protecting existing positions."""
        pending = list(self.em._pending_entries)
        ids = {p.id for p in pending}
        self.em._pending_entries.clear()
        for eid, order in list(self.em._exits.items()):
            if order.from_entry in ids and not self.em.qty_open(order.from_entry):
                self.em._exits.pop(eid)
        self.em._pending_closes[:] = [c for c in self.em._pending_closes
                                     if c.entry_id not in ids or self.em.qty_open(c.entry_id)]
        if self.strat is not None:
            # RATE snapshots are appended when intent is submitted. Filled/closed
            # positions still own the earlier queue entries; only remove the tail.
            for _ in (p for p in pending if p.id in ("Long", "Short")):
                if self.strat.w_slot_queue:
                    self.strat.w_slot_queue.pop()
                if self.strat.tod_hour_queue:
                    self.strat.tod_hour_queue.pop()
            self.strat.rate_pend_dir = 0
            self.strat.rate_pend_bar = -999
        return len(pending)

    def set_paused(self, paused: bool) -> int:
        with self.lock:
            if not paused and getattr(self, "_activation_quarantine", None):
                raise ValueError(f"{self.symbol}: activation recovery is required before resuming entries")
            self.paused = paused
            if self.strat is not None:
                self.strat.paused = paused
            return self._cancel_pending_entries() if paused else 0

    def ensure_configurable(self, *, allow_overlay: bool = False) -> None:
        """Must be called while holding lock, before any configuration mutation."""
        if not allow_overlay and (getattr(self, "_activation_version_id", None)
                                  or getattr(self, "_activation_quarantine", None)):
            raise ValueError(f"{self.symbol}: roll back or recover the activation overlay before changing configuration")
        if not self.warm:
            raise ValueError(f"{self.symbol}: initial warm-up must finish before changing configuration")
        if self.em.open or self.em._pending_entries or self.em._pending_closes:
            raise ValueError(f"{self.symbol}: flatten open positions and cancel pending orders before changing configuration")
        if self.rewarming:
            raise ValueError(f"{self.symbol}: configuration replay already running")

    def ensure_cached_timeframes(self, inputs: Inputs) -> None:
        requested = {tf_minutes(getattr(inputs, f"htf_tf_{n}")) for n in range(1, 6)}
        available = set(self.chains) | {m for m, rows in self.deep.items() if rows}
        missing = requested - available
        if missing:
            raise ValueError(f"{self.symbol}: cached history unavailable for requested HTF minutes {sorted(missing)}; fetch compatible history first")


    def ensure_cached_chart_timeframe(self, timeframe: object) -> str:
        """Prove the cache contains genuine bars fine enough for the requested chart.

        Mixed caches are valid: e.g. Yahoo may retain older 5m bars for HTF state
        plus a recent 1m tail. For a 1m/2m chart the 5m rows still feed compatible
        HTF chains, while the chart aggregator naturally ignores them. No finer
        chart bars are synthesized from coarser data.
        """
        tf = normalize_chart_timeframe(timeframe)
        minutes = tf_minutes(tf)
        if minutes == self.chart_minutes:
            return tf
        if not self.subbars:
            raise ValueError(f"{self.symbol}: no cached sub-bars are available to rebuild a {tf} chart")
        compatible = [(b, int(sub)) for b, sub in self.subbars if int(sub) <= minutes and minutes % int(sub) == 0]
        if not compatible:
            have = sorted({int(sub) for _, sub in self.subbars})
            raise ValueError(
                f"{self.symbol}: cached source bars {have}m cannot be losslessly rebuilt as {tf}; "
                "load 1-minute history first"
            )
        return tf

    def chart_capability_view(self) -> Dict[str, Any]:
        """Static engine support plus what the current cached tape can rebuild now."""
        caps = dict(chart_capabilities())
        have = sorted({int(sub) for _, sub in self.subbars})
        available: List[str] = []
        for tf in caps["timeframes"]:
            minutes = tf_minutes(tf)
            if minutes == self.chart_minutes or any(sub <= minutes and minutes % sub == 0 for sub in have):
                available.append(tf)
        caps["available_from_cache"] = available
        caps["cached_source_resolutions_minutes"] = have
        caps["current_timeframe"] = self.spec.chart_tf
        raw = self.feed.capabilities() if hasattr(self.feed, "capabilities") else {}
        caps["raw_feed_provider"] = raw.get("provider") if isinstance(raw, dict) else None
        caps["raw_seconds"] = bool(raw.get("ohlcv_seconds")) if isinstance(raw, dict) else False
        caps["raw_ticks"] = bool(raw.get("ticks")) if isinstance(raw, dict) else False
        caps["raw_depth"] = bool(raw.get("mbp_10") or raw.get("mbo")) if isinstance(raw, dict) else False
        caps["raw_minimum_resolution_seconds"] = raw.get("minimum_ohlcv_resolution_seconds") if isinstance(raw, dict) else None
        if caps["raw_seconds"] or caps["raw_ticks"]:
            caps["note"] = (
                "Strategy charts remain minute-based; the active Databento feed exposes genuine raw "
                "1-second OHLCV/ticks/depth through the market-data API/MCP without synthesizing tick bars."
            )
        return caps

    def flatten(self, reason: str = "manual") -> int:
        with self.lock:
            cancelled = self._cancel_pending_entries()
            n = 0
            for t in list(self.em.open):
                self.em.close(t.entry_id, comment="FLAT_" + reason.upper()[:8])
                n += 1
            if self.last_price and self.em.open:
                fake = Bar(int(time.time()), self.last_price, self.last_price, self.last_price, self.last_price, 0.0)
                self.em.process_bar(fake, self.bar_index)
            self.journal.log("WARN", f"[{self.symbol}] FLATTEN ({reason}): {n} position(s), {cancelled} pending entry intent(s) cancelled")
            return n

    def export_csv(self) -> str:
        with self.lock:
            return self._export_csv()

    def _export_csv(self) -> str:
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["Trade #", "Type", "Date/Time (UTC)", "Signal", "Price", "Contracts", "Profit", "Cum. Profit", "Live"])
        cum = 0.0
        for k, t in enumerate(self.em.closed, 1):
            cum += t.profit
            side = "long" if t.direction > 0 else "short"
            live = int(self.live_from_ts is not None and (k - 1) >= self.live_closed_start)
            w.writerow([k, f"Entry {side}", time.strftime("%Y-%m-%d %H:%M", time.gmtime(t.entry_ts)), t.entry_comment or t.entry_id, f"{t.entry_price:.10g}", t.qty, "", "", live])
            w.writerow([k, f"Exit {side}", time.strftime("%Y-%m-%d %H:%M", time.gmtime(t.exit_ts)), t.exit_comment, f"{t.exit_price:.10g}", t.qty, f"{t.profit:.2f}", f"{cum:.2f}", live])
        return buf.getvalue()

    # ── views ──
    def market(self) -> Dict[str, Any]:
        now = int(time.time())
        return {"open": self.cal.is_open(now), "calendar": self.cal.name, "describe": self.cal.describe(now),
                "next_open": self.cal.next_open(now), "session": self.cal.session_id(now)}

    def summary(self) -> Dict[str, Any]:
        with self.lock:
            return self._summary()

    def _summary(self) -> Dict[str, Any]:
        st = self.state or {}
        mark = self.last_price or (self.bars[-1].c if self.bars else None)
        open_trades = [{"id": t.entry_id, "dir": t.direction, "qty": t.qty, "qty_orig": t.qty_orig, "entry": t.entry_price, "entry_ts": t.entry_ts,
                        "upl": (t.direction * (mark - t.entry_price) * t.qty * self.em.contract_size) if mark else None} for t in self.em.open]
        live_trades = self.em.closed[self.live_closed_start:] if self.live_from_ts is not None else []
        wins = sum(1 for t in self.em.closed if t.profit > 0)
        forming = self.chart_agg.forming_bar()
        feed_meta = self.feed.meta(self.spec.ticker) if hasattr(self.feed, "meta") else {}
        return _clean({
            "symbol": self.symbol, "name": self.spec.name, "product": self.spec.ticker, "feed": self.spec.feed, "kind": self.spec.kind,
            "continuous_contract": bool(self.spec.kind == "futures"), "contract_policy": "continuous_only" if self.spec.kind == "futures" else "not_applicable",
            "continuous_symbol": self.spec.tv_symbol or self.spec.ticker,
            "provider_symbol": self.spec.ticker,
            "feed_provider": ("databento" if type(self.feed).__name__ == "Databento" else self.spec.feed),
            "feed_capabilities": (self.feed.capabilities() if hasattr(self.feed, "capabilities") else {}),
            "feed_meta": feed_meta,
            "active_contract": feed_meta.get("active_contract"),
            "active_instrument_id": feed_meta.get("active_instrument_id") or feed_meta.get("resolved_instrument_id"),
            "continuous_roll_count": feed_meta.get("roll_count", 0),
            "session_mode": _session_mode(self.cal), "security_source": self.spec.security_source,
            "tf": self.chart_minutes, "mintick": self.mintick, "contract_size": self.em.contract_size, "multiplier": self.spec.multiplier,
            "chart_type": self.spec.chart_type, "fill_on": self.spec.fill_on, "slippage_ticks": self.spec.slippage_ticks,
            "calculation_basis": {
                "timeframe": self.spec.chart_tf, "timeframe_minutes": self.chart_minutes,
                "chart_type": self.spec.chart_type, "fill_on": self.spec.fill_on,
                "security_source": self.spec.security_source, "session": _session_mode(self.cal),
            },
            "chart_capabilities": self.chart_capability_view(),
            "preset": self.cfg.preset or self.spec.preset, "inputs_sources": self.cfg.sources or [], "pts_scale": self.pts_scale,
            "price": mark, "price_age": (time.time() - self.last_price_ts) if self.last_price_ts else None,
            "feed_delay": self._feed_delay_at(int(time.time())),
            "warm": self.warm, "rewarming": self.rewarming, "paused": self.paused, "errors": self.errors, "last_error": self.last_error,
            "poll_age": (time.time() - self.last_poll_ok) if self.last_poll_ok else None,
            "bar_age": (time.time() - self.last_bar_wall) if self.last_bar_wall else None,
            "bar_index": self.bar_index, "last_bar_ts": self.bars[-1].ts if self.bars else None,
            "market": self.market(),
            "forming": (forming.__dict__ if forming else None),
            "equity": self.em.equity(mark), "capital": self.spec.capital, "netprofit": self.em.netprofit,
            "open_profit": self.em.open_profit(mark) if mark else 0.0, "position": self.em.position_size,
            "open_trades": open_trades, "exits": self.em.live_exits(), "pending": self.em.pending_view(),
            "trades_total": len(self.em.closed), "wins_total": wins,
            "live_trades": len(live_trades), "live_profit": sum(t.profit for t in live_trades),
            "state": {k: st.get(k) for k in ("ts", "c", "rate_uptrend", "rate_st_line", "rate_regime", "rate_regime_str", "hurst", "fdi",
                                             "rate_adx", "atr14", "armed_long", "armed_short", "bars_since_flip", "htf_dirs", "htf_bull", "htf_bear",
                                             "ltf", "votes", "final_l", "final_s", "eff_thresh", "gate_long", "gate_short", "conf_long", "conf_short",
                                             "entry_allowed", "in_session", "diverge_veto_l", "diverge_veto_s", "cycle_rising", "phase_deg", "vwap", "kf_vel",
                                             "pe_norm", "trc", "po3", "struct_bias", "pd_zone", "tide_hi", "tide_lo", "tide_broke_above",
                                             "tide_broke_below", "tide_inrange_closes", "pulse_l", "pulse_s", "pulse_state", "shock_mult",
                                             "families_l", "families_s", "rate_qty_open", "rate_pos_long", "rate_avg_price", "rate_qty_plan",
                                             "rate_tp1_done", "rate_be_armed", "runner_stop", "runner_tag", "tp1_price", "tp2_price", "sl_price",
                                             "h4_qty_open", "h4_pos_long", "h4_avg_price", "exec", "bars_since_stop", "daily_pnl",
                                             "w_trade_count", "active_votes", "avg_weight", "tp1_dist", "tp2_dist", "sl_dist")},
            "chains": {str(m): ch.state() for m, ch in self.chains.items()},
            "htf_tfs": self.htf_tfs,
        })

    def chart(self, n: int = 240) -> Dict[str, Any]:
        with self.lock:
            return self._chart(n)

    def _chart(self, n: int = 240) -> Dict[str, Any]:
        bars = list(self.bars)[-n:]
        ov = list(self.overlays)[-n:]
        fills = [f for f in self.recent_fills if bars and f["ts"] >= bars[0].ts]
        forming = self.chart_agg.forming_bar()
        f_row = None
        if forming:
            f_row = [forming.ts, forming.o, forming.h, forming.l, self.last_price or forming.c, forming.v]
        elif bars and self.last_price and self.last_price_ts and self.cal.intraday_open(int(self.last_price_ts)):
            nb = self.cal.bucket_start(int(self.last_price_ts), self.chart_minutes)
            if nb > bars[-1].ts:
                f_row = [nb, self.last_price, self.last_price, self.last_price, self.last_price, 0.0]
        return _clean({"symbol": self.symbol, "tf": self.chart_minutes, "mintick": self.mintick,
                       "chart_type": self.spec.chart_type, "fill_on": self.spec.fill_on,
                       "security_source": self.spec.security_source, "session": _session_mode(self.cal),
                       "bars": [[b.ts, b.o, b.h, b.l, b.c, b.v] for b in bars], "forming": f_row,
                       "overlays": ov, "fills": fills, "live_from": self.live_from_ts})

    def trades(self, limit: int = 100) -> List[Dict[str, Any]]:
        out = []
        start = max(0, len(self.em.closed) - limit)
        for idx, t in enumerate(self.em.closed[start:], start=start):
            out.append({"id": t.entry_id, "dir": t.direction, "qty": t.qty, "entry": t.entry_price, "entry_ts": t.entry_ts, "exit": t.exit_price,
                        "exit_ts": t.exit_ts, "comment": t.exit_comment, "profit": t.profit, "kind": t.exit_kind,
                        "live": self.live_from_ts is not None and idx >= self.live_closed_start})
        return out


# ──────────────────────────────────────────────────────────────────────
# Portfolio
# ──────────────────────────────────────────────────────────────────────
class Portfolio:
    def __init__(self, journal: Journal, base_dir: str, poll_sec: float = 5.0, profile: str = "nq",
                 preset: Optional[str] = None, warmup_bars: int = 1200, pts_ref_symbol: str = "NQ"):
        self.journal = journal
        self.base_dir = base_dir
        self.poll_sec = poll_sec
        self.profile = profile
        self.preset = preset
        self.warmup_bars = warmup_bars
        self.pts_ref_symbol = pts_ref_symbol
        self.pts_ref_price = 0.0
        # ICARUS_FEED selects the market-data transport without changing stable AssetSpec
        # identities. Futures remain continuous-only regardless of provider.
        requested_feed = os.environ.get("ICARUS_FEED", "").strip().lower()
        if file_feed_mode():
            hub = HistoryHub(base_dir)
            self.feeds: Dict[str, Any] = {"yahoo": hub, "coinbase": hub}
            self.feed_mode = "file"
            journal.log("INFO", f"ICARUS_FEED=file — HistoryHub at {base_dir}/history; Yahoo/Coinbase are not contacted")
        elif requested_feed == "databento":
            db_feed = Databento()
            self.feeds = {"yahoo": db_feed, "coinbase": Coinbase()}
            self.feed_mode = "databento"
            journal.log("INFO", "ICARUS_FEED=databento — CME futures use Databento GLBX.MDP3 volume-front continuous contracts")
        else:
            self.feeds = {"yahoo": Yahoo(), "coinbase": Coinbase()}
            self.feed_mode = "live"
        self.runners: Dict[str, AssetRunner] = {}
        self.order: List[str] = []
        self.started = time.time()
        self.equity_epoch = self.started                 # paper equity chart covers only the active engine epoch
        self.paused = False
        self._threads: Dict[str, threading.Thread] = {}
        self._stop = threading.Event()
        self._lock = threading.RLock()

    # ── assets ──
    def _ref_price(self, now: Optional[int] = None) -> float:
        if self.pts_ref_price > 0:
            return self.pts_ref_price
        try:
            from .assets import resolve
            ref = resolve(self.pts_ref_symbol)
            feed = self.feeds[ref.feed]
            px = None
            if ref.feed == "yahoo":                            # last COMPLETED session's close: reproducible run to run, immune to Yahoo's mid-session roll
                rows = feed.daily_volume(ref.ticker, 6)
                so = get_calendar("cme").bucket_start(int(now or time.time()), 1440)
                done = [r for r in rows if r[0] < so]
                px = done[-1][1] if done else None
            if not px:
                px = feed.ticker(ref.ticker)
            if px:
                self.pts_ref_price = float(px)
                self.journal.log("INFO", f"point-scaling reference: {ref.symbol} = {px:.6g} (last completed session close)")
        except Exception as ex:
            self.journal.log("WARN", f"could not fetch the NQ reference price ({ex}); *_pts inputs are used literally")
        return self.pts_ref_price

    def make_runner(self, spec: AssetSpec) -> AssetRunner:
        if self.feed_mode == "file" and spec.kind == "futures":
            self.journal.log("INFO", f"[{spec.symbol}] continuous futures identity preserved in file mode ({spec.tv_symbol or spec.ticker}); no expiry-contract roller")
        base_spec = replace(spec)
        inputs, meta, sources = resolve_inputs(spec, self.base_dir, self.profile, self.preset)
        if meta:
            spec = apply_spec_meta(spec, meta)
        scale = self._ref_price() if (spec.symbol != self.pts_ref_symbol) else 0.0
        cfg = RunnerConfig(spec=spec, inputs=inputs, warmup_bars=self.warmup_bars, sources=sources, profile=self.profile,
                           preset=self.preset or spec.preset, pts_ref_price=scale, base_dir=self.base_dir,
                           base_spec=base_spec)
        return AssetRunner(cfg, self.journal, self.feeds)

    def add_asset(self, spec: AssetSpec, start: bool = True) -> AssetRunner:
        with self._lock:
            if spec.symbol in self.runners:
                raise ValueError(f"{spec.symbol} already running")
        r = self.make_runner(spec)                            # may touch the network (tick size, NQ reference price)
        with self._lock:
            if spec.symbol in self.runners:
                raise ValueError(f"{spec.symbol} already running")
            self.runners[spec.symbol] = r
            self.order.append(spec.symbol)
            if start:
                self._spawn(r)
            return r

    def remove_asset(self, symbol: str) -> bool:
        key = resolve(symbol).symbol
        with self._lock:
            r = self.runners.pop(key, None)
            if not r:
                return False
            self.order = [s for s in self.order if s != key]
            r.paused = True
            r._removed = True
            self.journal.log("WARN", f"[{key}] removed from the engine")
            return True

    def preset_for(self, r: AssetRunner) -> Optional[str]:
        """The asset's current preset: set per asset (dashboard 'Apply preset', GC:NAME token) else the portfolio's."""
        return r.cfg.preset or r.spec.preset or self.preset

    def rewarm_asset(self, symbol: str, overrides: Optional[Dict[str, Any]] = None, persist: bool = False,
                     *, preset: Any = _UNCHANGED, reset: bool = False,
                     chart: Optional[Dict[str, Any]] = None) -> AssetRunner:
        """Atomically apply strategy/chart configuration, then persist only after replay succeeds."""
        key = resolve(symbol).symbol
        r = self.runners[key]
        with r.lock:
            r.ensure_configurable()
            requested_chart = validate_chart_config(chart)

            # Rebuild from the startup baseline every time. This makes reset deterministic:
            # preset/global/asset metadata are reapplied in order instead of leaking stale
            # chart/session/cost values from the previous runtime object.
            spec = replace(r.cfg.base_spec or r.spec)
            spec.preset = r.spec.preset
            if preset is not _UNCHANGED:
                spec.preset = preset
            name = self.preset_for(r) if preset is _UNCHANGED else preset or self.preset

            inputs, meta, sources = resolve_inputs(spec, self.base_dir, self.profile, name, overrides,
                                                  skip_asset_overrides=reset)
            spec = apply_spec_meta(spec, meta)
            spec = apply_chart_config(spec, requested_chart)

            path = os.path.join(self.base_dir, f"inputs.{r.symbol}.json")
            pending_file: Optional[Dict[str, Any]] = None
            delete_file = bool(reset and os.path.exists(path))

            if persist and (overrides is not None or requested_chart):
                # Build the exact next file in memory and resolve against that candidate.
                # Nothing reaches disk until the paper-engine replay has completed.
                pending_file = _read_json(path)
                if overrides:
                    pending_file.update(overrides)
                if requested_chart:
                    m = pending_file.get("_meta")
                    m = dict(m) if isinstance(m, dict) else {}
                    m.update(requested_chart)
                    pending_file["_meta"] = m
                inputs, meta, sources = resolve_inputs(
                    spec, self.base_dir, self.profile, name, pending_file,
                    skip_asset_overrides=True, extra_label=f"inputs.{r.symbol}.json"
                )
                spec = apply_spec_meta(spec, meta)
                spec = apply_chart_config(spec, requested_chart)

            r.ensure_cached_timeframes(inputs)
            spec.chart_tf = r.ensure_cached_chart_timeframe(spec.chart_tf)

            runtime_before = r.configuration_snapshot()
            tmp = path + ".tmp"
            try:
                for field in ("chart_tf", "chart_type", "fill_on", "security_source", "slippage_ticks",
                              "commission", "capital", "session", "preset", "config_pins"):
                    setattr(r.spec, field, getattr(spec, field))
                if preset is not _UNCHANGED:
                    r.cfg.preset = spec.preset
                r.rewarm(inputs, sources, reset_live_boundary=True)

                # Commit persistence after the successful replay. A failed replay therefore
                # cannot leave the next process start on a configuration the live engine rejected.
                if pending_file is not None:
                    with open(tmp, "w", encoding="utf-8") as fh:
                        json.dump(pending_file, fh, indent=1, ensure_ascii=False)
                    os.replace(tmp, path)
                elif delete_file:
                    os.remove(path)
                self.equity_epoch = time.time()
            except Exception:
                try:
                    if os.path.exists(tmp):
                        os.remove(tmp)
                except OSError:
                    pass
                r.restore_configuration_snapshot(runtime_before)
                raise
        return r

    # ── threads ──
    def _spawn(self, r: AssetRunner) -> None:
        t = threading.Thread(target=self._run, args=(r,), daemon=True, name=f"runner-{r.symbol}")
        t.start()
        self._threads[r.symbol] = t

    def start(self) -> None:
        for s in list(self.order):
            self._spawn(self.runners[s])
        threading.Thread(target=self._sampler, daemon=True, name="equity-sampler").start()

    def _run(self, r: AssetRunner) -> None:
        try:
            r.warmup()
            from .activation_runtime import load_startup_overlay
            load_startup_overlay(self, r)
        except Exception as ex:
            r.errors += 1
            r.last_error = f"warm-up failed: {type(ex).__name__}: {ex}"
            r.runtime_error = r.last_error
            r.warm = True                                     # failed, but not "warming" - the portfolio's all-warm checks must not wait for it
            self.journal.log("ERROR", f"[{r.symbol}] {r.last_error}")
            return
        interval = self.poll_sec if r.spec.feed == "coinbase" else max(self.poll_sec, 15.0)
        while not self._stop.is_set() and not r._removed:
            try:
                if not r.rewarming:
                    r.poll()
            except Exception as ex:
                r.errors += 1
                r.last_error = f"{type(ex).__name__}: {ex}"
                r.runtime_error = r.last_error
                self.journal.log("ERROR", f"[{r.symbol}] poll: {r.last_error}")
            self._stop.wait(interval)

    def _sampler(self) -> None:
        while not self._stop.is_set():
            try:
                if self.runners and all(r.warm for r in self.runners.values()):
                    self.journal.add_equity(self.equity())
            except Exception:
                pass
            self._stop.wait(20)

    def stop(self) -> None:
        self._stop.set()
        # Paid/live adapters own background network sessions. Close each distinct
        # feed once so supervised restarts do not leak Databento connections.
        seen = set()
        for feed in self.feeds.values():
            if id(feed) in seen:
                continue
            seen.add(id(feed))
            try:
                if hasattr(feed, "stop_live"):
                    feed.stop_live()
                elif hasattr(feed, "close"):
                    feed.close()
            except Exception as ex:
                self.journal.log("WARN", f"feed shutdown: {type(ex).__name__}: {ex}")

    # ── views ──
    def equity(self) -> float:
        return sum(r.em.equity(r.last_price) for r in self.runners.values())

    def runner_list(self) -> List[AssetRunner]:
        return [self.runners[s] for s in self.order if s in self.runners]

    def status(self) -> Dict[str, Any]:
        rs = [r.summary() for r in self.runner_list()]
        eq = sum(x["equity"] or 0.0 for x in rs)
        cap = sum(r.spec.capital for r in self.runner_list())
        live_profit = sum(x["live_profit"] for x in rs)
        return _clean({
            "now": time.time(), "uptime_sec": time.time() - self.started, "paused": self.paused,
            "equity": eq, "capital": cap, "net": eq - cap, "live_profit": live_profit,
            "open_profit": sum(x["open_profit"] or 0.0 for x in rs), "positions": sum(1 for x in rs if x["position"]),
            "assets": rs, "log": list(self.journal.log_tail)[-80:],
            "equity_epoch": self.equity_epoch,
            "equity_series": self.journal.equity_series(max_points=600, since_ts=max(self.started, self.equity_epoch)),
            "all_warm": all(r.warm for r in self.runners.values()) if self.runners else False,
            "preset": self.preset, "profile": self.profile, "pts_ref": {"symbol": self.pts_ref_symbol, "price": self.pts_ref_price},
        })
