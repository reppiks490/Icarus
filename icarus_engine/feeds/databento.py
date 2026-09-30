"""Databento CME Globex adapter for ICARUS.

Uses Databento continuous futures symbology (ROOT.v.0 = highest prior-day
volume) so ICARUS never needs a dated contract rollover table.

The existing engine consumes minute/sub-minute OHLCV through a small feed
interface. Databento natively supplies 1-second, 1-minute, 1-hour and 1-day
OHLCV; arbitrary whole-minute requests are losslessly aggregated from 1-minute
records. Live data is buffered from ohlcv-1s and aggregated for the current
minute path without fabricating trades or bars.
"""
from __future__ import annotations

import collections
import os
import threading
import time
from typing import Any, Deque, Dict, Iterable, List, Optional, Tuple

from ..pine.timeframe import Bar


DATASET = "GLBX.MDP3"
_NATIVE_SCHEMAS = {1: "ohlcv-1s", 60: "ohlcv-1m", 3600: "ohlcv-1h", 86400: "ohlcv-1d"}


def databento_feed_mode() -> bool:
    return os.environ.get("ICARUS_FEED", "").strip().lower() in ("databento", "db")


def continuous_symbol(product: str) -> str:
    """Map ICARUS/Yahoo/provider identities to Databento volume continuous ROOT.v.0."""
    s = str(product).strip().upper()
    if ":" in s:
        s = s.split(":", 1)[1]
    if s.endswith("1!"):
        s = s[:-2]
    if s.endswith("=F"):
        s = s[:-2]
    if s.endswith(".V.0"):
        return s[:-4] + ".v.0"
    if "." in s:
        # Already a Databento smart symbol such as ES.c.0 / NQ.v.0.
        parts = s.split(".")
        if len(parts) == 3 and parts[1].lower() in ("c", "n", "v") and parts[2].isdigit():
            return f"{parts[0]}.{parts[1].lower()}.{parts[2]}"
    if not s or not s.replace("_", "").isalnum():
        raise ValueError(f"unsupported Databento futures symbol {product!r}")
    return f"{s}.v.0"


def _to_bar(record: Any) -> Optional[Bar]:
    """Convert an OHLCV DBN record without depending on pandas."""
    if not hasattr(record, "ts_event"):
        return None
    fields = ("pretty_open", "pretty_high", "pretty_low", "pretty_close")
    if not all(hasattr(record, f) for f in fields):
        return None
    try:
        return Bar(
            int(record.ts_event) // 1_000_000_000,
            float(record.pretty_open),
            float(record.pretty_high),
            float(record.pretty_low),
            float(record.pretty_close),
            float(getattr(record, "volume", 0) or 0),
        )
    except (TypeError, ValueError):
        return None


def _aggregate(bars: Iterable[Bar], seconds: int) -> List[Bar]:
    seconds = int(seconds)
    if seconds <= 0:
        raise ValueError("aggregation interval must be positive")
    out: List[Bar] = []
    cur = None
    for b in sorted(bars, key=lambda x: x.ts):
        bucket = (b.ts // seconds) * seconds
        if cur is None or cur[0] != bucket:
            if cur is not None:
                out.append(Bar(*cur))
            cur = [bucket, b.o, b.h, b.l, b.c, b.v]
        else:
            cur[2] = max(cur[2], b.h)
            cur[3] = min(cur[3], b.l)
            cur[4] = b.c
            cur[5] += b.v
    if cur is not None:
        out.append(Bar(*cur))
    return out


class Databento:
    """Historical + live Databento feed compatible with the ICARUS feed interface."""

    GRANULARITIES = tuple(sorted(_NATIVE_SCHEMAS))
    DATASET = DATASET

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        dataset: str = DATASET,
        live: bool = True,
        db_module: Any = None,
        historical_client: Any = None,
        live_factory: Any = None,
        live_buffer_seconds: int = 7200,
    ):
        self.api_key = api_key or os.environ.get("DATABENTO_API_KEY") or None
        self.dataset = dataset
        self.live_enabled = bool(live)
        self._db = db_module
        self._historical = historical_client
        self._live_factory = live_factory
        self._live_clients: Dict[str, Any] = {}
        self._live_errors: Dict[str, str] = {}
        self._seconds: Dict[str, Deque[Bar]] = {}
        self._last_price: Dict[str, float] = {}
        self._feed_time: Dict[str, int] = {}
        self._meta: Dict[str, dict] = {}
        self._lock = threading.RLock()
        self._max_seconds = max(60, int(live_buffer_seconds))

    @property
    def capabilities(self) -> Dict[str, Any]:
        return {
            "provider": "databento",
            "dataset": self.dataset,
            "continuous_symbology": True,
            "continuous_roll_rule": "volume",
            "native_ohlcv_seconds": [1, 60, 3600, 86400],
            "native_seconds": True,
            "trades_schema": True,
            "mbo_schema": True,
            "mbp_schemas": True,
            "engine_chart_seconds": False,
            "note": "Databento provides genuine 1-second/trade/book data; ICARUS chart aggregation remains minute-based until the sub-minute engine path is enabled.",
        }

    def _module(self):
        if self._db is None:
            try:
                import databento as db  # type: ignore
            except Exception as ex:
                raise RuntimeError(
                    "Databento feed requested but the SDK is not installed; install ICARUS with .[marketdata]"
                ) from ex
            self._db = db
        return self._db

    def _history(self):
        if self._historical is None:
            db = self._module()
            self._historical = db.Historical(self.api_key) if self.api_key else db.Historical()
        return self._historical

    def _schema_for(self, granularity: int) -> Tuple[str, int]:
        g = int(granularity)
        if g in _NATIVE_SCHEMAS:
            return _NATIVE_SCHEMAS[g], g
        if g >= 60 and g % 60 == 0:
            return "ohlcv-1m", 60
        raise ValueError(f"Databento OHLCV granularity {g}s is unsupported; use 1s or whole-minute bars")

    def _request(self, product: str, schema: str, start_ts: int, end_ts: int):
        return self._history().timeseries.get_range(
            dataset=self.dataset,
            schema=schema,
            stype_in="continuous",
            symbols=[continuous_symbol(product)],
            start=int(start_ts) * 1_000_000_000,
            end=int(end_ts) * 1_000_000_000,
        )

    def candles(self, product: str, granularity: int, start_ts: int, end_ts: int) -> List[Bar]:
        if int(end_ts) <= int(start_ts):
            return []
        schema, native = self._schema_for(granularity)
        store = self._request(product, schema, int(start_ts), int(end_ts))
        rows: Dict[int, Bar] = {}
        for rec in store:
            b = _to_bar(rec)
            if b is not None and int(start_ts) <= b.ts < int(end_ts):
                rows[b.ts] = b
        bars = [rows[k] for k in sorted(rows)]
        return bars if native == int(granularity) else _aggregate(bars, int(granularity))

    def seconds(self, product: str, start_ts: int, end_ts: int) -> List[Bar]:
        """Historical genuine 1-second bars; no interpolation."""
        return self.candles(product, 1, start_ts, end_ts)

    def daily_volume(self, product: str, days: int = 5) -> List[Tuple[int, float, float]]:
        now = int(time.time())
        rows = self.candles(product, 86400, now - max(2, int(days) + 2) * 86400, now)
        return [(b.ts, b.c, b.v) for b in rows[-max(1, int(days)):]]

    def ticker(self, product: str) -> Optional[float]:
        with self._lock:
            if product in self._last_price:
                return self._last_price[product]
        now = int(time.time())
        rows = self.candles(product, 60, now - 15 * 60, now)
        if not rows:
            return None
        px = rows[-1].c
        with self._lock:
            self._last_price[product] = px
        return px

    def _live_client(self, product: str):
        with self._lock:
            if product in self._live_clients:
                return self._live_clients[product]
        db = self._module()
        factory = self._live_factory or db.Live
        client = factory(key=self.api_key, reconnect_policy="reconnect") if self.api_key else factory(reconnect_policy="reconnect")
        smart = continuous_symbol(product)
        buf: Deque[Bar] = collections.deque(maxlen=self._max_seconds)
        with self._lock:
            self._seconds.setdefault(product, buf)

        def on_record(record):
            b = _to_bar(record)
            if b is None:
                return
            with self._lock:
                self._seconds[product].append(b)
                self._last_price[product] = b.c
                self._feed_time[product] = max(self._feed_time.get(product, 0), b.ts + 1)
                self._meta[product] = {"regularMarketTime": self._feed_time[product], "databento_symbol": smart}

        def on_error(ex):
            with self._lock:
                self._live_errors[product] = str(ex)

        client.subscribe(
            dataset=self.dataset,
            schema="ohlcv-1s",
            stype_in="continuous",
            symbols=[smart],
        )
        client.add_callback(on_record, exception_callback=on_error)
        client.start()
        with self._lock:
            self._live_clients[product] = client
        return client

    def recent_ex(self, product: str, granularity: int = 60, since_ts: Optional[int] = None) -> Tuple[List[Bar], int, Optional[float]]:
        g = int(granularity)
        if self.live_enabled:
            try:
                self._live_client(product)
            except Exception as ex:
                with self._lock:
                    self._live_errors[product] = str(ex)

        now = int(time.time())
        with self._lock:
            sec = list(self._seconds.get(product, ()))
            ft = int(self._feed_time.get(product, 0))
            px = self._last_price.get(product)

        if sec:
            start = int(since_ts or (sec[0].ts - g))
            selected = [b for b in sec if b.ts >= max(0, start - g)]
            bars = selected if g == 1 else _aggregate(selected, g)
            return bars, ft or (sec[-1].ts + 1), px or sec[-1].c

        # Historical fallback covers startup/reconnect before the first live event.
        start = int(since_ts or (now - max(900, g * 10)))
        try:
            bars = self.candles(product, g, max(0, start - g * 2), now)
        except Exception:
            bars = []
        if bars:
            px = bars[-1].c
            ft = bars[-1].ts + g
            with self._lock:
                self._last_price[product] = px
                self._feed_time[product] = max(self._feed_time.get(product, 0), ft)
                self._meta[product] = {"regularMarketTime": self._feed_time[product], "databento_symbol": continuous_symbol(product)}
        return bars, ft, px

    def recent(self, product: str, granularity: int = 60) -> List[Bar]:
        return self.recent_ex(product, granularity)[0]

    def close(self) -> None:
        with self._lock:
            clients = list(self._live_clients.values())
            self._live_clients.clear()
        for client in clients:
            try:
                client.stop()
            except Exception:
                try:
                    client.terminate()
                except Exception:
                    pass
