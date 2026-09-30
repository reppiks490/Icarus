"""Databento CME/Globex feed for ICARUS.

This adapter is deliberately continuous-contract only. ICARUS registry futures use
provider/chart identities such as NQ=F / CME_MINI:NQ1!; Databento is requested with
its volume-based front continuous symbology (for example NQ.v.0, stype_in=continuous).

Historical:
  - ohlcv-1s / ohlcv-1m / ohlcv-1h / ohlcv-1d
  - arbitrary integer-second OHLCV is losslessly aggregated from the nearest native
    Databento OHLCV schema without inventing trades.

Live:
  - ohlcv-1s
  - trades
  - mbp-10 (L2)
  - mbo (L3), including snapshot=True through mbo_snapshot()

The SDK is optional. Install ICARUS with .[databento] and provide
DATABENTO_API_KEY. Tests inject a fake SDK and never require credentials/network.
"""
from __future__ import annotations

import collections
import math
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Deque, Dict, Iterable, List, Optional, Sequence, Tuple

from ..pine.timeframe import Bar

_DATASET = "GLBX.MDP3"
_NATIVE_SCHEMAS = {
    1: "ohlcv-1s",
    60: "ohlcv-1m",
    3600: "ohlcv-1h",
    86400: "ohlcv-1d",
}
_PRICE_SCALE = 1_000_000_000.0


@dataclass(frozen=True)
class TradeTick:
    ts_event: int
    price: float
    size: int
    side: str = ""
    action: str = "T"
    sequence: int = 0


class Databento:
    """Continuous CME feed backed by Databento Historical + Live APIs."""

    GRANULARITIES = (1, 60, 300, 900, 1800, 3600, 86400)
    DATASET = _DATASET

    def __init__(
        self,
        api_key: Optional[str] = None,
        dataset: str = _DATASET,
        *,
        sdk: Any = None,
        historical: Any = None,
        live_factory: Any = None,
        max_live_seconds: int = 6 * 3600,
        max_trades: int = 200_000,
        max_depth: int = 20_000,
    ):
        self.api_key = api_key or os.environ.get("DATABENTO_API_KEY") or ""
        self.dataset = dataset
        self._sdk = sdk or self._load_sdk()
        if not self.api_key and historical is None:
            raise RuntimeError(
                "Databento feed requires DATABENTO_API_KEY (or api_key=...). "
                "Install the SDK with: pip install -e '.[databento]'"
            )
        self._historical = historical if historical is not None else self._sdk.Historical(self.api_key)
        self._live_factory = live_factory or (lambda: self._sdk.Live(key=self.api_key))
        self._lock = threading.RLock()
        self._live: Dict[str, Any] = {}
        self._live_started: set[str] = set()
        self._subscriptions: Dict[str, set[str]] = collections.defaultdict(set)
        self._ready: Dict[str, threading.Event] = collections.defaultdict(threading.Event)
        self._second_bars: Dict[str, Deque[Bar]] = collections.defaultdict(
            lambda: collections.deque(maxlen=max(60, int(max_live_seconds)))
        )
        self._trades: Dict[str, Deque[TradeTick]] = collections.defaultdict(
            lambda: collections.deque(maxlen=max(1000, int(max_trades)))
        )
        self._depth: Dict[str, Deque[Dict[str, Any]]] = collections.defaultdict(
            lambda: collections.deque(maxlen=max(1000, int(max_depth)))
        )
        self._last_price: Dict[str, float] = {}
        self._feed_time: Dict[str, int] = {}
        self._meta: Dict[str, Dict[str, Any]] = {}
        self.requests = 0

    @staticmethod
    def _load_sdk():
        try:
            import databento as db  # type: ignore
            return db
        except Exception as ex:
            raise RuntimeError(
                "Databento SDK is not installed. Install ICARUS with: pip install -e '.[databento]'"
            ) from ex

    @staticmethod
    def root(symbol: str) -> str:
        s = str(symbol).strip().upper()
        if ":" in s:
            s = s.split(":")[-1]
        for suffix in ("=F", "1!", "1"):
            if s.endswith(suffix):
                s = s[: -len(suffix)]
                break
        if not s or not all(ch.isalnum() for ch in s):
            raise ValueError(f"unsupported Databento futures symbol {symbol!r}")
        return s

    @classmethod
    def continuous_symbol(cls, symbol: str) -> str:
        """Databento volume-based front month, closest to TradingView's volume-roll 1!."""
        return f"{cls.root(symbol)}.v.0"

    @classmethod
    def parent_symbol(cls, symbol: str) -> str:
        return f"{cls.root(symbol)}.FUT"

    @staticmethod
    def capabilities() -> Dict[str, Any]:
        return {
            "provider": "databento",
            "dataset": _DATASET,
            "continuous_futures": True,
            "continuous_rule": "volume_front",
            "ohlcv_seconds": True,
            "minimum_ohlcv_resolution_seconds": 1,
            "trades": True,
            "ticks": True,
            "mbp_10": True,
            "mbo": True,
            "mbo_snapshot": True,
            "schemas": ["ohlcv-1s", "ohlcv-1m", "ohlcv-1h", "ohlcv-1d", "trades", "mbp-10", "mbo"],
        }

    @staticmethod
    def _iso(ts: int | float) -> str:
        return datetime.fromtimestamp(float(ts), timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _price(record: Any, field: str) -> float:
        pretty = getattr(record, f"pretty_{field}", None)
        if pretty is not None:
            try:
                x = float(pretty)
                if math.isfinite(x):
                    return x
            except (TypeError, ValueError):
                pass
        raw = getattr(record, field)
        x = float(raw) / _PRICE_SCALE
        if not math.isfinite(x):
            raise ValueError(f"invalid Databento {field}={raw!r}")
        return x

    @staticmethod
    def _ts_sec(record: Any) -> int:
        ns = int(getattr(record, "ts_event"))
        return ns // 1_000_000_000

    @classmethod
    def _ohlcv_record(cls, record: Any) -> Bar:
        return Bar(
            cls._ts_sec(record),
            cls._price(record, "open"),
            cls._price(record, "high"),
            cls._price(record, "low"),
            cls._price(record, "close"),
            float(getattr(record, "volume", 0) or 0),
        )

    @classmethod
    def _trade_record(cls, record: Any) -> TradeTick:
        return TradeTick(
            ts_event=cls._ts_sec(record),
            price=cls._price(record, "price"),
            size=int(getattr(record, "size", 0) or 0),
            side=str(getattr(record, "side", "") or ""),
            action=str(getattr(record, "action", "T") or "T"),
            sequence=int(getattr(record, "sequence", 0) or 0),
        )

    @classmethod
    def _event_record(cls, record: Any) -> Dict[str, Any]:
        out: Dict[str, Any] = {
            "ts_event": cls._ts_sec(record) if hasattr(record, "ts_event") else None,
            "type": type(record).__name__,
        }
        for key in ("action", "side", "size", "depth", "order_id", "sequence", "flags", "instrument_id"):
            if hasattr(record, key):
                v = getattr(record, key)
                try:
                    v = int(v)
                except (TypeError, ValueError):
                    v = str(v)
                out[key] = v
        if hasattr(record, "price"):
            try:
                out["price"] = cls._price(record, "price")
            except Exception:
                pass
        # MBP-10 records expose levels; preserve a JSON-friendly view without taking
        # a hard dependency on one databento-dbn concrete level class.
        levels = getattr(record, "levels", None)
        if levels is not None:
            clean = []
            for lvl in levels:
                row = {}
                for key in ("bid_px", "ask_px", "bid_sz", "ask_sz", "bid_ct", "ask_ct"):
                    if hasattr(lvl, key):
                        value = getattr(lvl, key)
                        if key.endswith("_px"):
                            try:
                                pretty = getattr(lvl, f"pretty_{key}", None)
                                value = float(pretty) if pretty is not None else float(value) / _PRICE_SCALE
                            except Exception:
                                continue
                        else:
                            try:
                                value = int(value)
                            except Exception:
                                value = str(value)
                        row[key] = value
                clean.append(row)
            out["levels"] = clean
        return out

    @staticmethod
    def _schema_for(granularity: int) -> Tuple[int, str]:
        g = int(granularity)
        if g <= 0:
            raise ValueError("granularity must be positive seconds")
        if g in _NATIVE_SCHEMAS:
            return g, _NATIVE_SCHEMAS[g]
        if g < 60:
            return 1, "ohlcv-1s"
        if g % 60 == 0 and g < 3600:
            return 60, "ohlcv-1m"
        if g % 3600 == 0 and g < 86400:
            return 3600, "ohlcv-1h"
        if g % 86400 == 0:
            return 86400, "ohlcv-1d"
        raise ValueError(f"Databento cannot losslessly aggregate OHLCV to {g}s")

    @staticmethod
    def _aggregate(bars: Iterable[Bar], seconds: int) -> List[Bar]:
        out: List[Bar] = []
        bucket: Optional[int] = None
        o = h = l = c = v = 0.0
        for b in sorted(bars, key=lambda x: x.ts):
            k = b.ts - (b.ts % seconds)
            if bucket is None or k != bucket:
                if bucket is not None:
                    out.append(Bar(bucket, o, h, l, c, v))
                bucket = k
                o, h, l, c, v = b.o, b.h, b.l, b.c, b.v
            else:
                h = max(h, b.h)
                l = min(l, b.l)
                c = b.c
                v += b.v
        if bucket is not None:
            out.append(Bar(bucket, o, h, l, c, v))
        return out

    def _get_range(self, symbol: str, schema: str, start_ts: int, end_ts: int):
        self.requests += 1
        return self._historical.timeseries.get_range(
            dataset=self.dataset,
            schema=schema,
            symbols=self.continuous_symbol(symbol),
            stype_in="continuous",
            start=self._iso(start_ts),
            end=self._iso(end_ts),
        )

    def candles(self, symbol: str, granularity: int, start_ts: int, end_ts: int) -> List[Bar]:
        base_sec, schema = self._schema_for(granularity)
        store = self._get_range(symbol, schema, int(start_ts), int(end_ts))
        bars = [self._ohlcv_record(rec) for rec in store]
        bars = [b for b in bars if int(start_ts) <= b.ts < int(end_ts)]
        if int(granularity) != base_sec:
            bars = self._aggregate(bars, int(granularity))
        return bars

    def daily_volume(self, symbol: str, days: int = 5) -> List[Tuple[int, float, float]]:
        end = int(time.time())
        start = end - max(2, int(days) + 2) * 86400
        return [(b.ts, b.c, b.v) for b in self.candles(symbol, 86400, start, end)]

    def mintick(self, symbol: str) -> float:
        from ..assets import REGISTRY
        root = self.root(symbol)
        for spec in REGISTRY.values():
            if spec.kind == "futures" and self.root(spec.ticker) == root:
                return spec.mintick
        raise ValueError(f"tick size for {symbol} unknown - add it to assets.REGISTRY")

    def meta(self, symbol: str) -> Dict[str, Any]:
        with self._lock:
            return dict(self._meta.get(symbol, {}))

    def _live_callback(self, symbol: str, record: Any) -> None:
        now_sec = self._ts_sec(record) if hasattr(record, "ts_event") else int(time.time())
        with self._lock:
            self._feed_time[symbol] = max(now_sec, self._feed_time.get(symbol, 0))
            # OHLCV record
            if all(hasattr(record, key) for key in ("open", "high", "low", "close", "volume")):
                b = self._ohlcv_record(record)
                self._second_bars[symbol].append(b)
                self._last_price[symbol] = b.c
            else:
                # MBO trade records are both trades and order-book events; keep both views.
                if hasattr(record, "price") and hasattr(record, "size") and str(getattr(record, "action", "T") or "T") == "T":
                    tick = self._trade_record(record)
                    self._trades[symbol].append(tick)
                    self._last_price[symbol] = tick.price
                if hasattr(record, "levels") or hasattr(record, "order_id"):
                    self._depth[symbol].append(self._event_record(record))
            self._ready[symbol].set()
            self._meta[symbol] = {
                "regularMarketTime": self._feed_time[symbol],
                "provider": "databento",
                "dataset": self.dataset,
                "continuous_symbol": self.continuous_symbol(symbol),
            }

    def start_live(
        self,
        symbol: str,
        *,
        schemas: Sequence[str] = ("ohlcv-1s", "trades"),
        start_ts: Optional[int] = None,
        include_depth: Optional[str] = None,
    ) -> Any:
        key = str(symbol)
        desired = {str(s) for s in schemas}
        if include_depth:
            if include_depth not in ("mbp-10", "mbo"):
                raise ValueError("include_depth must be 'mbp-10' or 'mbo'")
            desired.add(include_depth)
        with self._lock:
            if key in self._live_started:
                client = self._live[key]
                missing = desired - self._subscriptions[key]
                # Databento allows additional live subscriptions after start as long as
                # they don't request historical replay. Add only genuinely missing schemas.
                for schema in sorted(missing):
                    client.subscribe(
                        dataset=self.dataset,
                        schema=schema,
                        symbols=self.continuous_symbol(symbol),
                        stype_in="continuous",
                    )
                    self._subscriptions[key].add(schema)
                return client
            client = self._live_factory()
            kwargs: Dict[str, Any] = {
                "dataset": self.dataset,
                "symbols": self.continuous_symbol(symbol),
                "stype_in": "continuous",
            }
            if start_ts is not None:
                # Live replay is limited by Databento to the recent intraday window.
                kwargs["start"] = self._iso(start_ts)
            for schema in sorted(desired):
                client.subscribe(schema=schema, **kwargs)
                self._subscriptions[key].add(schema)
            client.add_callback(lambda rec, s=key: self._live_callback(s, rec))
            client.start()
            self._live[key] = client
            self._live_started.add(key)
            return client

    def stop_live(self, symbol: Optional[str] = None) -> None:
        with self._lock:
            keys = [symbol] if symbol is not None else list(self._live)
            clients = [(k, self._live.get(k)) for k in keys]
        for key, client in clients:
            if client is None:
                continue
            try:
                client.stop()
            finally:
                with self._lock:
                    self._live.pop(key, None)
                    self._live_started.discard(key)
                    self._subscriptions.pop(key, None)
                    self._ready.pop(key, None)

    def recent_ex(
        self,
        symbol: str,
        granularity: int = 60,
        since_ts: Optional[int] = None,
    ) -> Tuple[List[Bar], int, Optional[float]]:
        if int(granularity) < 1:
            raise ValueError("granularity must be >= 1 second")
        now = int(time.time())
        start = max(now - 23 * 3600, int(since_ts or (now - 900)) - 120)
        self.start_live(symbol, start_ts=start)
        self._ready[str(symbol)].wait(timeout=2.0)
        with self._lock:
            rows = list(self._second_bars[str(symbol)])
            ft = int(self._feed_time.get(str(symbol), 0))
            px = self._last_price.get(str(symbol))
        if since_ts is not None:
            rows = [b for b in rows if b.ts >= int(since_ts) - max(2, int(granularity))]
        bars = rows if int(granularity) == 1 else self._aggregate(rows, int(granularity))
        return bars, ft, px

    def recent(self, symbol: str, granularity: int = 60) -> List[Bar]:
        return self.recent_ex(symbol, granularity)[0]

    def ticker(self, symbol: str) -> Optional[float]:
        self.start_live(symbol)
        with self._lock:
            return self._last_price.get(str(symbol))

    def trades(self, symbol: str, since_ts: Optional[int] = None, limit: int = 10_000) -> List[TradeTick]:
        self.start_live(symbol, schemas=("ohlcv-1s", "trades"))
        with self._lock:
            rows = list(self._trades[str(symbol)])
        if since_ts is not None:
            rows = [x for x in rows if x.ts_event >= int(since_ts)]
        return rows[-max(0, int(limit)):]

    def depth_events(self, symbol: str, *, schema: str = "mbp-10", limit: int = 2000) -> List[Dict[str, Any]]:
        if schema not in ("mbp-10", "mbo"):
            raise ValueError("schema must be 'mbp-10' or 'mbo'")
        self.start_live(symbol, include_depth=schema)
        with self._lock:
            rows = list(self._depth[str(symbol)])
        return rows[-max(0, int(limit)):]

    def mbo_snapshot(self, symbol: str, timeout: float = 5.0) -> List[Dict[str, Any]]:
        """Return a live MBO snapshot. Databento marks the final snapshot record F_LAST."""
        client = self._live_factory()
        done = threading.Event()
        rows: List[Dict[str, Any]] = []
        last_flag = int(getattr(getattr(self._sdk, "RecordFlags", object), "F_LAST", 0) or 0)

        def callback(record: Any) -> None:
            rows.append(self._event_record(record))
            flags = int(getattr(record, "flags", 0) or 0)
            if last_flag and flags & last_flag:
                done.set()

        client.subscribe(
            dataset=self.dataset,
            schema="mbo",
            symbols=self.continuous_symbol(symbol),
            stype_in="continuous",
            snapshot=True,
        )
        client.add_callback(callback)
        client.start()
        try:
            done.wait(max(0.1, float(timeout)))
        finally:
            client.stop()
        if last_flag and not done.is_set():
            raise TimeoutError(f"Databento MBO snapshot timed out for {symbol}")
        return rows
