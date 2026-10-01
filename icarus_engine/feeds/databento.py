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

import bisect
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
_UNDEF_PRICE = (1 << 63) - 1
_GLBX_HISTORY_START_TS = int(datetime(2010, 6, 6, tzinfo=timezone.utc).timestamp())


@dataclass(frozen=True)
class TradeTick:
    ts_event: int                  # whole seconds for coarse filtering/UI compatibility
    ts_event_ns: int               # original Databento nanosecond event timestamp
    price: float
    size: int
    side: str = ""
    action: str = "T"
    sequence: int = 0
    ts_recv_ns: int = 0             # Databento receive time; monotonic per symbol and safe for replay ordering


class Databento:
    """Continuous CME feed backed by Databento Historical + Live APIs."""

    GRANULARITIES = (1, 2, 5, 10, 15, 20, 30, 60, 120, 180, 240, 300, 600, 900, 1200, 1800, 3600, 14400, 86400)
    DATASET = _DATASET
    HISTORICAL_START_TS = _GLBX_HISTORY_START_TS

    def __init__(
        self,
        api_key: Optional[str] = None,
        dataset: Optional[str] = None,
        *,
        roll_rule: Optional[str] = None,
        sdk: Any = None,
        historical: Any = None,
        live_factory: Any = None,
        max_live_seconds: int = 6 * 3600,
        max_trades: int = 200_000,
        max_depth: int = 20_000,
    ):
        self.api_key = api_key or os.environ.get("DATABENTO_API_KEY") or ""
        self.dataset = (dataset or os.environ.get("DATABENTO_DATASET") or _DATASET).strip()
        self.roll_rule = (roll_rule or os.environ.get("DATABENTO_ROLL_RULE") or "v").strip().lower()
        if self.dataset != _DATASET:
            raise ValueError(f"Databento CME futures adapter requires {_DATASET}, got {self.dataset!r}")
        if self.roll_rule not in ("v", "n", "c"):
            raise ValueError("DATABENTO_ROLL_RULE must be v, n, or c")
        self._sdk = sdk or self._load_sdk()
        if not self.api_key and historical is None:
            raise RuntimeError(
                "Databento feed requires DATABENTO_API_KEY (or api_key=...). "
                "Install the SDK with: pip install -e '.[databento]'"
            )
        self._historical = historical if historical is not None else self._sdk.Historical(self.api_key)
        self._live_factory = live_factory or (lambda: self._sdk.Live(
            key=self.api_key,
            heartbeat_interval_s=10,
            reconnect_policy="reconnect",
            slow_reader_behavior="warn",
        ))
        self._lock = threading.RLock()
        self._session_lock = threading.RLock()
        self._depth_session_lock = threading.RLock()
        self._snapshot_lock = threading.Lock()
        # Core OHLCV/trades share one Live session per Databento dataset. Optional
        # MBP-10 and MBO each use their own shared schema session so a fatal entitlement
        # or subscription error cannot terminate core data or the other book schema.
        self._shared_live: Any = None
        self._shared_started = False
        self._core_broken = False
        self._core_error_code: Optional[int] = None
        self._live: Dict[str, Any] = {}  # compatibility/status view: active symbol -> shared client
        self._live_started: set[str] = set()
        # Desired schemas survive socket replacement; _subscriptions describes only
        # what is attached to the current shared client.
        self._wanted_subscriptions: Dict[str, set[str]] = collections.defaultdict(set)
        self._subscriptions: Dict[str, set[str]] = collections.defaultdict(set)
        self._continuous_to_symbol: Dict[str, str] = {}
        self._instrument_to_symbol: Dict[int, str] = {}
        self._depth_live: Dict[str, Any] = {}
        self._depth_started: set[str] = set()
        self._depth_live_symbols: Dict[str, set[str]] = collections.defaultdict(set)
        self._depth_wanted: Dict[str, set[str]] = collections.defaultdict(set)
        self._depth_subscriptions: Dict[str, set[str]] = collections.defaultdict(set)
        self._depth_continuous_to_symbol: Dict[str, Dict[str, str]] = collections.defaultdict(dict)
        self._depth_instrument_to_symbol: Dict[str, Dict[int, str]] = collections.defaultdict(dict)
        self._depth_errors: Dict[Tuple[str, str], str] = {}
        self._depth_error_code: Dict[str, int] = {}
        self._depth_ready: Dict[Tuple[str, str], threading.Event] = collections.defaultdict(threading.Event)
        self._depth_broken: set[str] = set()
        self._ready: Dict[str, threading.Event] = collections.defaultdict(threading.Event)
        self._second_bars: Dict[str, Deque[Bar]] = collections.defaultdict(
            lambda: collections.deque(maxlen=max(60, int(max_live_seconds)))
        )
        self._trades: Dict[str, Deque[TradeTick]] = collections.defaultdict(
            lambda: collections.deque(maxlen=max(1000, int(max_trades)))
        )
        # Multiple Databento schemas can report the same trade event (for example
        # trades + MBO/MBP-10). Keep the public tick tape event-unique instead of
        # double-counting one exchange trade when depth is enabled.
        self._trade_seen: Dict[str, set[Tuple[int, float, int, str, int]]] = collections.defaultdict(set)
        self._depth: Dict[Tuple[str, str], Deque[Dict[str, Any]]] = collections.defaultdict(
            lambda: collections.deque(maxlen=max(1000, int(max_depth)))
        )
        self._depth_seen: Dict[Tuple[str, str], set[Tuple[Any, ...]]] = collections.defaultdict(set)
        self._last_price: Dict[str, float] = {}
        self._last_price_order_ns: Dict[str, int] = {}
        self._feed_time: Dict[str, int] = {}
        self._meta: Dict[str, Dict[str, Any]] = {}
        self._errors: Dict[str, str] = {}
        self._reconnect_gaps: Dict[str, Deque[Dict[str, str]]] = collections.defaultdict(
            lambda: collections.deque(maxlen=100)
        )
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
        # Route through the ICARUS registry so aliases such as BTCF, M2K1!,
        # CME_MINI:NQ1!, and provider =F symbols all resolve to the same
        # continuous futures root. Unknown/spot symbols fail closed.
        from ..assets import resolve
        spec = resolve(str(symbol))
        if spec.kind != "futures":
            raise ValueError(f"Databento GLBX adapter only accepts registered futures, got {symbol!r}")
        ticker = str(spec.ticker).upper()
        if not ticker.endswith("=F"):
            raise ValueError(f"{spec.symbol}: Databento futures identity must use a continuous provider ticker")
        return ticker[:-2]

    @classmethod
    def continuous_symbol(cls, symbol: str, roll_rule: Optional[str] = None) -> str:
        """Databento continuous front contract using c/n/v smart symbology."""
        rule = (roll_rule or os.environ.get("DATABENTO_ROLL_RULE") or "v").strip().lower()
        if rule not in ("v", "n", "c"):
            raise ValueError("Databento continuous roll rule must be v, n, or c")
        return f"{cls.root(symbol)}.{rule}.0"

    @classmethod
    def parent_symbol(cls, symbol: str) -> str:
        return f"{cls.root(symbol)}.FUT"

    def capabilities(self) -> Dict[str, Any]:
        rule_name = {"v": "volume_front", "n": "open_interest_front", "c": "calendar_front"}[self.roll_rule]
        return {
            "provider": "databento",
            "dataset": self.dataset,
            "continuous_futures": True,
            "continuous_rule": rule_name,
            "continuous_rule_code": self.roll_rule,
            "live_session_model": "shared_core_plus_schema_isolated_depth_per_dataset",
            "persistent_live_sessions_max": 3,
            "snapshot_sessions_serialized": True,
            "live_symbol_routing": "SymbolMappingMsg/instrument_id",
            "depth_failure_isolation": True,
            "depth_schema_isolation": True,
            "continuous_live_refresh": "automatic_utc_day",
            "cme_session_daily_weekly": True,
            "native_ohlcv_1d_basis": "utc",
            "session_daily_source": "ohlcv-1h",
            "historical_start": "2010-06-06",
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
    def _optional_price(record: Any, field: str) -> Optional[float]:
        """Return a real Databento price, or None for the DBN undefined-price sentinel."""
        pretty = getattr(record, f"pretty_{field}", None)
        if pretty is not None:
            try:
                x = float(pretty)
                if math.isfinite(x):
                    return x
            except (TypeError, ValueError):
                pass
        raw = getattr(record, field)
        try:
            raw_i = int(raw)
        except (TypeError, ValueError, OverflowError):
            return None
        if raw_i == _UNDEF_PRICE:
            return None
        x = float(raw_i) / _PRICE_SCALE
        return x if math.isfinite(x) else None

    @classmethod
    def _price(cls, record: Any, field: str) -> float:
        x = cls._optional_price(record, field)
        if x is None:
            raise ValueError(f"undefined/invalid Databento {field}={getattr(record, field, None)!r}")
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
        ts_ns = int(getattr(record, "ts_event"))
        ts_recv_ns = int(getattr(record, "ts_recv", ts_ns) or ts_ns)
        return TradeTick(
            ts_event=ts_ns // 1_000_000_000,
            ts_event_ns=ts_ns,
            price=cls._price(record, "price"),
            size=int(getattr(record, "size", 0) or 0),
            side=str(getattr(record, "side", "") or ""),
            action=str(getattr(record, "action", "T") or "T"),
            sequence=int(getattr(record, "sequence", 0) or 0),
            ts_recv_ns=ts_recv_ns,
        )

    def _upsert_second_bar_locked(self, symbol: str, bar: Bar) -> bool:
        """Insert/replace one second bar in timestamp order, including replay backfill."""
        q = self._second_bars[symbol]
        if not q or bar.ts > q[-1].ts:
            q.append(bar)
            return True
        if bar.ts == q[-1].ts:
            q[-1] = bar
            return True
        rows = list(q)
        stamps = [row.ts for row in rows]
        pos = bisect.bisect_left(stamps, bar.ts)
        if pos < len(rows) and rows[pos].ts == bar.ts:
            rows[pos] = bar
        else:
            rows.insert(pos, bar)
        if q.maxlen is not None and len(rows) > q.maxlen:
            rows = rows[-q.maxlen:]
        q.clear()
        q.extend(rows)
        return bool(rows and rows[0].ts <= bar.ts <= rows[-1].ts and any(x.ts == bar.ts for x in rows))

    @staticmethod
    def _depth_key(row: Dict[str, Any]) -> Tuple[Any, ...]:
        return (
            row.get("schema"),
            row.get("ts_recv_ns"),
            row.get("ts_event_ns"),
            row.get("sequence"),
            row.get("action"),
            row.get("order_id"),
            row.get("price"),
        )

    @staticmethod
    def _depth_order_key(row: Dict[str, Any]) -> Tuple[int, int, int]:
        return (
            int(row.get("ts_recv_ns") or row.get("ts_event_ns") or 0),
            int(row.get("ts_event_ns") or 0),
            int(row.get("sequence") or 0),
        )

    def _append_depth_locked(self, symbol: str, row: Dict[str, Any]) -> bool:
        schema = str(row.get("schema") or "unknown")
        bucket = (str(symbol), schema)
        key = self._depth_key(row)
        seen = self._depth_seen[bucket]
        if key in seen:
            return False
        q = self._depth[bucket]
        order = self._depth_order_key(row)
        if not q or order >= self._depth_order_key(q[-1]):
            q.append(row)
            seen.add(key)
            if q.maxlen is not None and len(seen) > len(q):
                # deque maxlen may have evicted the oldest row.
                self._depth_seen[bucket] = {self._depth_key(x) for x in q}
            return True
        rows = list(q)
        orders = [self._depth_order_key(x) for x in rows]
        pos = bisect.bisect_right(orders, order)
        rows.insert(pos, row)
        if q.maxlen is not None and len(rows) > q.maxlen:
            rows = rows[-q.maxlen:]
        q.clear()
        q.extend(rows)
        self._depth_seen[bucket] = {self._depth_key(x) for x in rows}
        return key in self._depth_seen[bucket]

    @staticmethod
    def _trade_key(tick: TradeTick) -> Tuple[int, float, int, str, int]:
        return (tick.ts_event_ns, tick.price, tick.size, tick.side, tick.sequence)

    @staticmethod
    def _trade_order_key(tick: TradeTick) -> Tuple[int, int, int]:
        return (tick.ts_recv_ns, tick.ts_event_ns, tick.sequence)

    def _append_trade_locked(self, symbol: str, tick: TradeTick) -> bool:
        """Insert one exchange trade once, ordered by Databento receive time."""
        key = self._trade_key(tick)
        seen = self._trade_seen[symbol]
        if key in seen:
            return False
        q = self._trades[symbol]
        order = self._trade_order_key(tick)
        if not q or order >= self._trade_order_key(q[-1]):
            q.append(tick)
            seen.add(key)
            if q.maxlen is not None and len(seen) > len(q):
                self._trade_seen[symbol] = {self._trade_key(x) for x in q}
            return True
        rows = list(q)
        orders = [self._trade_order_key(x) for x in rows]
        pos = bisect.bisect_right(orders, order)
        rows.insert(pos, tick)
        if q.maxlen is not None and len(rows) > q.maxlen:
            rows = rows[-q.maxlen:]
        q.clear()
        q.extend(rows)
        self._trade_seen[symbol] = {self._trade_key(x) for x in rows}
        return key in self._trade_seen[symbol]

    @classmethod
    def _event_record(cls, record: Any) -> Dict[str, Any]:
        ts_ns = int(getattr(record, "ts_event")) if hasattr(record, "ts_event") else None
        ts_recv_raw = getattr(record, "ts_recv", None)
        ts_recv_ns = int(ts_recv_raw) if ts_recv_raw is not None else ts_ns
        levels = getattr(record, "levels", None)
        schema = "mbp-10" if levels is not None else ("mbo" if hasattr(record, "order_id") else "unknown")
        out: Dict[str, Any] = {
            "ts_event": (ts_ns // 1_000_000_000) if ts_ns is not None else None,
            "ts_event_ns": ts_ns,
            "ts_recv_ns": ts_recv_ns,
            "schema": schema,
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
            out["price"] = cls._optional_price(record, "price")
        # MBP-10 records expose levels; preserve a JSON-friendly view without taking
        # a hard dependency on one databento-dbn concrete level class.
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
                                if pretty is not None and math.isfinite(float(pretty)):
                                    value = float(pretty)
                                else:
                                    raw_i = int(value)
                                    value = None if raw_i == _UNDEF_PRICE else float(raw_i) / _PRICE_SCALE
                            except (TypeError, ValueError, OverflowError):
                                value = None
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
            symbols=self.continuous_symbol(symbol, self.roll_rule),
            stype_in="continuous",
            start=self._iso(start_ts),
            end=self._iso(end_ts),
        )

    def _session_bars(self, symbol: str, minutes: int, start_ts: int, end_ts: int) -> List[Bar]:
        """Build CME-session daily/weekly bars from UTC-hourly Databento records."""
        from ..assets import resolve
        from ..calendar import get_calendar

        if int(minutes) < 1440:
            raise ValueError("session bars require a daily-or-higher timeframe")
        spec = resolve(str(symbol))
        cal = get_calendar(spec.calendar, spec.anchor_et, session=spec.session, group=spec.group)
        start = max(int(start_ts), self.HISTORICAL_START_TS)
        end = int(end_ts)
        if end <= start:
            return []

        store = self._get_range(symbol, "ohlcv-1h", start, end)
        buckets: Dict[int, Bar] = {}
        for rec in store:
            b = self._ohlcv_record(rec)
            if b.ts < start or b.ts >= end or not cal.is_open(b.ts):
                continue
            bucket = cal.bucket_start(b.ts, int(minutes))
            prev = buckets.get(bucket)
            if prev is None:
                buckets[bucket] = Bar(bucket, b.o, b.h, b.l, b.c, b.v)
            else:
                buckets[bucket] = Bar(bucket, prev.o, max(prev.h, b.h), min(prev.l, b.l), b.c, prev.v + b.v)
        return [buckets[k] for k in sorted(buckets)]

    def candles(self, symbol: str, granularity: int, start_ts: int, end_ts: int) -> List[Bar]:
        g = int(granularity)
        # Databento's native ohlcv-1d is UTC-date based. ICARUS futures charts use
        # CME session days/weeks, so aggregate those timeframes from hourly records.
        if g in (86400, 7 * 86400):
            return self._session_bars(symbol, g // 60, int(start_ts), int(end_ts))
        if g > 86400:
            raise ValueError(f"Databento session-aligned higher timeframe {g}s is unsupported; use 1D or 1W")
        start = max(int(start_ts), self.HISTORICAL_START_TS)
        end = int(end_ts)
        if end <= start:
            return []
        base_sec, schema = self._schema_for(g)
        store = self._get_range(symbol, schema, start, end)
        bars = [self._ohlcv_record(rec) for rec in store]
        bars = [b for b in bars if start <= b.ts < end]
        if g != base_sec:
            bars = self._aggregate(bars, g)
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
        key = str(symbol)
        with self._lock:
            out = dict(self._meta.get(key, {}))
            depth_errors = {
                schema: err for (sym, schema), err in self._depth_errors.items() if sym == key
            }
            if depth_errors:
                out["depth_errors"] = depth_errors
                out["depth_error"] = "; ".join(f"{schema}: {err}" for schema, err in sorted(depth_errors.items()))
            out["core_session_ok"] = not self._core_broken
            if self._core_error_code is not None:
                out["core_error_code"] = self._core_error_code
            out["depth_session_ok"] = not self._depth_broken
            out["depth_schema_health"] = {
                schema: schema not in self._depth_broken for schema in ("mbp-10", "mbo")
            }
            if self._depth_error_code:
                out["depth_error_codes"] = dict(self._depth_error_code)
            return out

    def _live_callback(self, symbol: str, record: Any) -> None:
        now_sec = self._ts_sec(record) if hasattr(record, "ts_event") else int(time.time())
        with self._lock:
            # ErrorMsg records are delivered through the same callback as market data.
            # Since 2026 symbol-resolution failures can be non-fatal at the gateway,
            # so fail closed here instead of silently waiting on an unresolved stream.
            if hasattr(record, "err"):
                code = int(getattr(record, "code", 0) or 0)
                err = str(getattr(record, "err", "") or "Databento live error")
                self._errors[symbol] = f"Databento live error code={code}: {err}"
                # Codes 1/2/3/5/6/8 are fatal at the gateway. Code 7 means records
                # were skipped, which is also an integrity failure for ICARUS even
                # though Databento may keep the connection open.
                if code in (1, 2, 3, 5, 6, 7, 8):
                    self._core_broken = True
                    self._core_error_code = code
                self._ready[symbol].set()
                self._meta[symbol] = {
                    "regularMarketTime": self._feed_time.get(symbol, 0),
                    "provider": "databento",
                    "dataset": self.dataset,
                    "continuous_symbol": self.continuous_symbol(symbol, self.roll_rule),
                    "live_error": self._errors[symbol],
                }
                return
            market_event = False
            # OHLCV record
            if all(hasattr(record, key) for key in ("open", "high", "low", "close", "volume")):
                b = self._ohlcv_record(record)
                if self._upsert_second_bar_locked(symbol, b):
                    # Databento OHLCV ts_event is the bar start. Do not stamp a
                    # synthetic end-of-second receive time: a genuine trade received
                    # later in the same second must be allowed to become the live mark.
                    bar_order_ns = int(b.ts) * 1_000_000_000
                    if bar_order_ns >= self._last_price_order_ns.get(symbol, 0):
                        self._last_price[symbol] = b.c
                        self._last_price_order_ns[symbol] = bar_order_ns
                    market_event = True
            else:
                # MBO trade records are both trades and order-book events; keep both views.
                if hasattr(record, "price") and hasattr(record, "size") and str(getattr(record, "action", "T") or "T") == "T":
                    tick = self._trade_record(record)
                    if self._append_trade_locked(symbol, tick):
                        if tick.ts_recv_ns >= self._last_price_order_ns.get(symbol, 0):
                            self._last_price[symbol] = tick.price
                            self._last_price_order_ns[symbol] = tick.ts_recv_ns
                        market_event = True
                if hasattr(record, "levels") or hasattr(record, "order_id"):
                    if self._append_depth_locked(symbol, self._event_record(record)):
                        market_event = True
            if market_event:
                self._feed_time[symbol] = max(now_sec, self._feed_time.get(symbol, 0))
                self._ready[symbol].set()
                if not self._core_broken:
                    self._errors.pop(symbol, None)
            self._meta[symbol] = {
                "regularMarketTime": self._feed_time.get(symbol, 0),
                "provider": "databento",
                "dataset": self.dataset,
                "continuous_symbol": self.continuous_symbol(symbol, self.roll_rule),
            }
            if symbol in self._errors:
                self._meta[symbol]["live_error"] = self._errors[symbol]

    def _dispatch_live(self, symbol: str, record: Any) -> None:
        """Contain record-conversion failures inside feed health instead of killing the reader."""
        try:
            self._live_callback(symbol, record)
        except Exception as ex:
            with self._lock:
                self._errors[str(symbol)] = f"Databento record error: {type(ex).__name__}: {ex}"
                self._ready[str(symbol)].set()
                meta = dict(self._meta.get(str(symbol), {}))
                meta.update({
                    "regularMarketTime": self._feed_time.get(str(symbol), 0),
                    "provider": "databento",
                    "dataset": self.dataset,
                    "continuous_symbol": self.continuous_symbol(symbol, self.roll_rule),
                    "live_error": self._errors[str(symbol)],
                })
                self._meta[str(symbol)] = meta

    @staticmethod
    def _instrument_id(record: Any) -> Optional[int]:
        value = getattr(record, "instrument_id", None)
        if value is None:
            value = getattr(getattr(record, "hd", None), "instrument_id", None)
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError, OverflowError):
            return None

    @staticmethod
    def _mapping_symbol(record: Any) -> str:
        value = getattr(record, "stype_in_symbol", "")
        if isinstance(value, bytes):
            value = value.split(b"\0", 1)[0].decode("utf-8", "replace")
        return str(value or "").split("\0", 1)[0].strip()

    def _dispatch_shared_live(self, record: Any) -> None:
        """Route one record from the shared GLBX.MDP3 session to its ICARUS symbol."""
        mapping = self._mapping_symbol(record)
        iid = self._instrument_id(record)
        if mapping:
            with self._lock:
                key = self._continuous_to_symbol.get(mapping)
                if key is not None and iid is not None:
                    self._instrument_to_symbol[iid] = key
            return

        # ErrorMsg has no guaranteed instrument mapping. Route symbol-specific errors
        # by their continuous symbol when possible; otherwise fail closed for all
        # active subscriptions because the shared session's integrity is uncertain.
        if hasattr(record, "err"):
            code = int(getattr(record, "code", 0) or 0)
            err = str(getattr(record, "err", "") or "")
            session_broken = code in (1, 2, 3, 5, 6, 7, 8)
            with self._lock:
                active = set(self._live_started)
                if session_broken:
                    # These errors are fatal at the gateway, or (code 7) imply an
                    # irreversible data-integrity gap. Every symbol on the shared
                    # session must fail closed even if the message names only one.
                    targets = list(active)
                else:
                    targets = [key for cont, key in self._continuous_to_symbol.items()
                               if key in active and cont and cont in err]
                    if not targets:
                        targets = list(active)
                    if code == 4:
                        # A symbol-resolution failure rejects that subscription but
                        # leaves the shared session alive. Re-arm the desired core
                        # schemas so the next poll retries only the affected symbol.
                        for key in targets:
                            self._subscriptions[key].clear()
            for key in targets:
                self._dispatch_live(key, record)
            return

        with self._lock:
            key = self._instrument_to_symbol.get(iid) if iid is not None else None
            if key is not None and key not in self._live_started:
                key = None
            if key is None and iid is None and len(self._live_started) == 1:
                # Defensive compatibility only for records that carry no instrument ID.
                # Never guess when Databento supplied an unknown ID: that could route a
                # detached/foreign contract into the wrong remaining asset.
                key = next(iter(self._live_started))
        if key is not None:
            self._dispatch_live(key, record)

    def _record_reconnect_all(self, previous: Any, resumed: Any) -> None:
        with self._lock:
            # A real transport reconnect creates a new integrity boundary. Keep the
            # prior error visible until a valid market event arrives, but allow that
            # event to clear the broken-state latch.
            self._core_broken = False
            self._core_error_code = None
            symbols = list(self._live_started)
        for symbol in symbols:
            self._record_reconnect(symbol, previous, resumed)

    def _dispatch_depth_live(self, schema: str, record: Any) -> None:
        """Route one isolated depth-schema session without touching other transports."""
        mapping = self._mapping_symbol(record)
        iid = self._instrument_id(record)
        if mapping:
            with self._lock:
                key = self._depth_continuous_to_symbol[schema].get(mapping)
                if key is not None and iid is not None:
                    self._depth_instrument_to_symbol[schema][iid] = key
            return

        if hasattr(record, "err"):
            code = int(getattr(record, "code", 0) or 0)
            err = str(getattr(record, "err", "") or f"Databento {schema} depth error")
            fatal = code in (1, 2, 3, 5, 6, 7, 8)
            with self._lock:
                active = set(self._depth_live_symbols[schema])
                if fatal:
                    targets = list(active)
                else:
                    targets = [key for cont, key in self._depth_continuous_to_symbol[schema].items()
                               if key in active and cont and cont in err]
                    if not targets:
                        targets = list(active)
                message = f"Databento {schema} depth error code={code}: {err}"
                for key in targets:
                    self._depth_errors[(key, schema)] = message
                    self._depth_ready[(key, schema)].set()
                    if code == 4:
                        # Symbol resolution is non-fatal and scoped. Re-arm only this
                        # schema/symbol so a later explicit request can resubscribe it.
                        self._depth_subscriptions[schema].discard(key)
                if fatal:
                    self._depth_broken.add(schema)
                    self._depth_error_code[schema] = code
            return

        with self._lock:
            key = self._depth_instrument_to_symbol[schema].get(iid) if iid is not None else None
            if key is not None and key not in self._depth_live_symbols[schema]:
                key = None
            if key is None and iid is None and len(self._depth_live_symbols[schema]) == 1:
                key = next(iter(self._depth_live_symbols[schema]))
        if key is None:
            return

        try:
            if hasattr(record, "levels") or hasattr(record, "order_id"):
                row = self._event_record(record)
                if str(row.get("schema") or "") != schema:
                    return
                with self._lock:
                    self._append_depth_locked(key, row)
                    if schema not in self._depth_broken:
                        self._depth_errors.pop((key, schema), None)
                    self._depth_ready[(key, schema)].set()
        except Exception as ex:
            with self._lock:
                self._depth_errors[(key, schema)] = (
                    f"Databento {schema} depth record error: {type(ex).__name__}: {ex}"
                )
                self._depth_ready[(key, schema)].set()

    def _raise_depth_error(self, symbol: str, schema: str) -> None:
        key = (str(symbol), str(schema))
        with self._lock:
            err = self._depth_errors.get(key)
            broken = schema in self._depth_broken
        if err:
            raise RuntimeError(err)
        if broken:
            raise RuntimeError(f"Databento {schema} depth session is in a fatal/integrity error state")

    def _record_depth_reconnect_all(self, schema: str, previous: Any, resumed: Any) -> None:
        with self._lock:
            self._depth_broken.discard(schema)
            self._depth_error_code.pop(schema, None)
            symbols = list(self._depth_live_symbols[schema])
        for symbol in symbols:
            self._record_reconnect(symbol, previous, resumed)

    def _prepare_depth_live(
        self,
        symbols: Sequence[str],
        schema: str,
        *,
        start_ts: Optional[int] = None,
    ) -> Any:
        if schema not in ("mbp-10", "mbo"):
            raise ValueError("schema must be 'mbp-10' or 'mbo'")
        keys = [(str(symbol), self.continuous_symbol(symbol, self.roll_rule)) for symbol in symbols]
        if not keys:
            return self._depth_live.get(schema)

        with self._depth_session_lock:
            with self._lock:
                broken = schema in self._depth_broken
                code = self._depth_error_code.get(schema)
            if broken and code in (6, 7, 8):
                self._refresh_depth_schema_live(schema, start_ts=max(0, int(time.time()) - 300))
            with self._lock:
                if schema in self._depth_broken:
                    detail = next(
                        (self._depth_errors.get((key, schema)) for key, _ in keys
                         if self._depth_errors.get((key, schema))),
                        None,
                    )
                    raise RuntimeError(detail or f"Databento {schema} depth session is in a fatal error state")
                client = self._depth_live.get(schema)
                if client is None:
                    client = self._live_factory()
                    client.add_callback(lambda record, sc=schema: self._dispatch_depth_live(sc, record))
                    if hasattr(client, "add_reconnect_callback"):
                        client.add_reconnect_callback(
                            lambda previous, resumed, sc=schema:
                            self._record_depth_reconnect_all(sc, previous, resumed)
                        )
                    self._depth_live[schema] = client

            try:
                with self._lock:
                    for key, continuous in keys:
                        self._depth_wanted[key].add(schema)
                        self._depth_continuous_to_symbol[schema][continuous] = key
                        if key in self._depth_subscriptions[schema]:
                            self._depth_live_symbols[schema].add(key)
                            continue
                        self._depth_ready[(key, schema)].clear()
                        self._depth_errors.pop((key, schema), None)
                        kwargs: Dict[str, Any] = {
                            "dataset": self.dataset,
                            "schema": schema,
                            "symbols": continuous,
                            "stype_in": "continuous",
                        }
                        if start_ts is not None and schema not in self._depth_started:
                            kwargs["start"] = self._iso(start_ts)
                        client.subscribe(**kwargs)
                        self._depth_subscriptions[schema].add(key)
                        self._depth_live_symbols[schema].add(key)

                    if schema not in self._depth_started:
                        client.start()
                        self._depth_started.add(schema)
                return client
            except Exception as ex:
                with self._lock:
                    for key, _ in keys:
                        self._depth_errors[(key, schema)] = (
                            f"Databento {schema} depth session error: {type(ex).__name__}: {ex}"
                        )
                        self._depth_ready[(key, schema)].set()
                    started = schema in self._depth_started
                    if not started:
                        self._depth_live.pop(schema, None)
                        self._depth_live_symbols[schema].clear()
                        self._depth_subscriptions[schema].clear()
                        self._depth_continuous_to_symbol[schema].clear()
                        self._depth_instrument_to_symbol[schema].clear()
                if not started:
                    try:
                        if hasattr(client, "terminate"):
                            client.terminate()
                    except Exception:
                        pass
                raise

    def _stop_depth_schema_unlocked(self, schema: str) -> None:
        client = None
        with self._lock:
            client = self._depth_live.pop(schema, None)
            self._depth_started.discard(schema)
            self._depth_broken.discard(schema)
            self._depth_error_code.pop(schema, None)
            symbols = set(self._depth_live_symbols.pop(schema, set()))
            self._depth_subscriptions.pop(schema, None)
            self._depth_continuous_to_symbol.pop(schema, None)
            self._depth_instrument_to_symbol.pop(schema, None)
            for key in symbols:
                self._depth_ready.pop((key, schema), None)
                self._depth_errors.pop((key, schema), None)
                self._depth_wanted[key].discard(schema)
                if not self._depth_wanted[key]:
                    self._depth_wanted.pop(key, None)

        if client is not None:
            try:
                client.stop()
                if hasattr(client, "block_for_close"):
                    client.block_for_close(timeout=5.0)
            except Exception as stop_ex:
                try:
                    client.terminate()
                    if hasattr(client, "block_for_close"):
                        client.block_for_close(timeout=5.0)
                except Exception:
                    raise stop_ex

    def _stop_depth_unlocked(self, symbol: Optional[str] = None) -> None:
        if symbol is None:
            for schema in list(self._depth_live):
                self._stop_depth_schema_unlocked(schema)
            return

        key = str(symbol)
        schemas_to_stop: List[str] = []
        with self._lock:
            for schema, symbols in list(self._depth_live_symbols.items()):
                symbols.discard(key)
                self._depth_ready.pop((key, schema), None)
                self._depth_errors.pop((key, schema), None)
                self._depth_wanted[key].discard(schema)
                if not symbols and schema in self._depth_live:
                    schemas_to_stop.append(schema)
            if not self._depth_wanted.get(key):
                self._depth_wanted.pop(key, None)
        for schema in schemas_to_stop:
            self._stop_depth_schema_unlocked(schema)

    def _refresh_depth_schema_live(self, schema: str, *, start_ts: Optional[int] = None) -> Any:
        with self._depth_session_lock:
            with self._lock:
                active = list(self._depth_live_symbols[schema])
            self._stop_depth_schema_unlocked(schema)
            if not active:
                return None

            client = self._live_factory()
            client.add_callback(lambda record, sc=schema: self._dispatch_depth_live(sc, record))
            if hasattr(client, "add_reconnect_callback"):
                client.add_reconnect_callback(
                    lambda previous, resumed, sc=schema:
                    self._record_depth_reconnect_all(sc, previous, resumed)
                )
            with self._lock:
                self._depth_live[schema] = client
                self._depth_broken.discard(schema)
                self._depth_error_code.pop(schema, None)
            try:
                with self._lock:
                    for key in active:
                        continuous = self.continuous_symbol(key, self.roll_rule)
                        self._depth_wanted[key].add(schema)
                        self._depth_continuous_to_symbol[schema][continuous] = key
                        self._depth_ready[(key, schema)].clear()
                        kwargs: Dict[str, Any] = {
                            "dataset": self.dataset,
                            "schema": schema,
                            "symbols": continuous,
                            "stype_in": "continuous",
                        }
                        if start_ts is not None:
                            kwargs["start"] = self._iso(start_ts)
                        client.subscribe(**kwargs)
                        self._depth_subscriptions[schema].add(key)
                        self._depth_live_symbols[schema].add(key)
                    client.start()
                    self._depth_started.add(schema)
                return client
            except Exception as ex:
                try:
                    if hasattr(client, "terminate"):
                        client.terminate()
                except Exception:
                    pass
                with self._lock:
                    self._depth_live.pop(schema, None)
                    self._depth_started.discard(schema)
                    self._depth_broken.add(schema)
                    self._depth_error_code[schema] = 6
                    self._depth_live_symbols[schema].update(active)
                    self._depth_subscriptions[schema].clear()
                    self._depth_continuous_to_symbol[schema].clear()
                    self._depth_instrument_to_symbol[schema].clear()
                    message = f"Databento {schema} depth refresh error: {type(ex).__name__}: {ex}"
                    for key in active:
                        self._depth_errors[(key, schema)] = message
                        self._depth_ready[(key, schema)].set()
                raise

    def _refresh_depth_live(self, *, start_ts: Optional[int] = None) -> None:
        with self._depth_session_lock:
            with self._lock:
                schemas = [schema for schema, symbols in self._depth_live_symbols.items() if symbols]
            for schema in schemas:
                try:
                    self._refresh_depth_schema_live(schema, start_ts=start_ts)
                except Exception:
                    # Keep refreshing independent schemas; each failure remains visible
                    # through per-schema depth health and is retried on explicit demand.
                    continue

    def _raise_live_error(self, symbol: str) -> None:
        with self._lock:
            err = self._errors.get(str(symbol))
            broken = self._core_broken
        if err:
            raise RuntimeError(err)
        if broken:
            raise RuntimeError("Databento core live session is in a fatal/integrity error state")

    def _record_reconnect(self, symbol: str, previous: Any, resumed: Any) -> None:
        row = {"previous": str(previous), "resumed": str(resumed)}
        with self._lock:
            self._reconnect_gaps[str(symbol)].append(row)
            meta = dict(self._meta.get(str(symbol), {}))
            meta["last_reconnect_gap"] = row
            meta["reconnect_count"] = len(self._reconnect_gaps[str(symbol)])
            self._meta[str(symbol)] = meta

    def _prepare_live_unlocked(
        self,
        symbols: Sequence[str],
        *,
        schemas: Sequence[str] = ("ohlcv-1s", "trades"),
        start_ts: Optional[int] = None,
        include_depth: Optional[str] = None,
    ) -> Any:
        """Subscribe many futures on one dataset session, then start it once.

        ICARUS calls this before historical warm-up so live buffers accumulate while
        replay runs. Additional symbols may be attached after start, but Databento's
        replay start parameter is intentionally omitted for those subscriptions.
        """
        desired = {str(s) for s in schemas if str(s) not in ("mbp-10", "mbo")}
        if include_depth and include_depth not in ("mbp-10", "mbo"):
            raise ValueError("include_depth must be 'mbp-10' or 'mbo'")
        keys = [(str(symbol), self.continuous_symbol(symbol, self.roll_rule)) for symbol in symbols]
        with self._lock:
            for key, _ in keys:
                self._wanted_subscriptions[key].update(desired)
        if not keys:
            return self._shared_live

        with self._lock:
            client = self._shared_live
            if client is None:
                client = self._live_factory()
                client.add_callback(self._dispatch_shared_live)
                if hasattr(client, "add_reconnect_callback"):
                    client.add_reconnect_callback(self._record_reconnect_all)
                self._shared_live = client

            try:
                for key, continuous in keys:
                    self._continuous_to_symbol[continuous] = key
                    wanted = set(self._wanted_subscriptions[key])
                    missing = wanted - self._subscriptions[key]
                    for schema in sorted(missing):
                        kwargs: Dict[str, Any] = {
                            "dataset": self.dataset,
                            "schema": schema,
                            "symbols": continuous,
                            "stype_in": "continuous",
                        }
                        if start_ts is not None and not self._shared_started:
                            kwargs["start"] = self._iso(start_ts)
                        client.subscribe(**kwargs)
                        self._subscriptions[key].add(schema)
                    self._live[key] = client
                    self._live_started.add(key)

                if not self._shared_started:
                    client.start()
                    self._shared_started = True
                return client
            except Exception:
                # Before a session has started, any subscribe/start failure leaves the
                # client construction ambiguous. Discard it atomically so the next
                # attempt begins from a fresh Live client instead of reusing poison state.
                if not self._shared_started:
                    try:
                        if hasattr(client, "terminate"):
                            client.terminate()
                    except Exception:
                        pass
                    self._shared_live = None
                    self._live.clear()
                    self._live_started.clear()
                    self._subscriptions.clear()
                    self._continuous_to_symbol.clear()
                    self._instrument_to_symbol.clear()
                    self._ready.clear()
                    self._errors.clear()
                raise

    def prepare_live(
        self,
        symbols: Sequence[str],
        *,
        schemas: Sequence[str] = ("ohlcv-1s", "trades"),
        start_ts: Optional[int] = None,
        include_depth: Optional[str] = None,
    ) -> Any:
        with self._session_lock:
            with self._lock:
                broken = self._core_broken
                code = self._core_error_code
                active = list(self._live_started)
            if broken and code in (6, 7, 8):
                retry_symbols = list(dict.fromkeys(active + [str(x) for x in symbols]))
                self._refresh_core_live(
                    retry_symbols,
                    start_ts=max(0, int(time.time()) - 300),
                )
            client = self._prepare_live_unlocked(
                symbols, schemas=schemas, start_ts=start_ts, include_depth=None
            )
        if include_depth:
            self._prepare_depth_live(symbols, include_depth, start_ts=start_ts)
        return client

    def _refresh_core_live(self, symbols: Sequence[str], *, start_ts: Optional[int] = None) -> Any:
        """Atomically re-resolve continuous symbols on a fresh shared Live session.

        Each active symbol keeps its exact core OHLCV/trades schema set. Optional
        depth schemas are refreshed independently on their isolated session.
        """
        with self._session_lock:
            with self._lock:
                wanted = {
                    str(symbol): set(self._wanted_subscriptions.get(str(symbol), {"ohlcv-1s", "trades"}))
                    for symbol in symbols
                }
            self._stop_live_unlocked()
            if not wanted:
                return None

            client = self._live_factory()
            client.add_callback(self._dispatch_shared_live)
            if hasattr(client, "add_reconnect_callback"):
                client.add_reconnect_callback(self._record_reconnect_all)
            with self._lock:
                self._shared_live = client
                self._core_broken = False
                self._core_error_code = None
            try:
                with self._lock:
                    for key, desired in wanted.items():
                        continuous = self.continuous_symbol(key, self.roll_rule)
                        self._continuous_to_symbol[continuous] = key
                        self._wanted_subscriptions[key].update(desired)
                        for schema in sorted(desired):
                            kwargs: Dict[str, Any] = {
                                "dataset": self.dataset,
                                "schema": schema,
                                "symbols": continuous,
                                "stype_in": "continuous",
                            }
                            if start_ts is not None:
                                kwargs["start"] = self._iso(start_ts)
                            client.subscribe(**kwargs)
                            self._subscriptions[key].add(schema)
                        self._live[key] = client
                        self._live_started.add(key)
                    client.start()
                    self._shared_started = True
                return client
            except Exception:
                try:
                    if hasattr(client, "terminate"):
                        client.terminate()
                except Exception:
                    pass
                with self._lock:
                    self._shared_live = None
                    self._shared_started = False
                    self._core_broken = True
                    self._core_error_code = 6
                    self._live.clear()
                    self._live_started.clear()
                    self._subscriptions.clear()
                    self._continuous_to_symbol.clear()
                    self._instrument_to_symbol.clear()
                    self._ready.clear()
                    self._errors.clear()
                raise

    def refresh_live(self, symbols: Sequence[str], *, start_ts: Optional[int] = None) -> Any:
        core = self._refresh_core_live(symbols, start_ts=start_ts)
        try:
            self._refresh_depth_live(start_ts=start_ts)
        except Exception:
            # Depth is an optional, separately reported fault domain. Do not make a
            # failed book refresh cause the healthy core continuous session to churn.
            pass
        return core

    def start_live(
        self,
        symbol: str,
        *,
        schemas: Sequence[str] = ("ohlcv-1s", "trades"),
        start_ts: Optional[int] = None,
        include_depth: Optional[str] = None,
    ) -> Any:
        return self.prepare_live(
            [symbol], schemas=schemas, start_ts=start_ts, include_depth=include_depth
        )

    def _stop_live_unlocked(self, symbol: Optional[str] = None) -> None:
        client = None
        with self._lock:
            if symbol is not None:
                key = str(symbol)
                self._live.pop(key, None)
                self._live_started.discard(key)
                self._ready.pop(key, None)
                self._errors.pop(key, None)
                # Databento has no per-subscription unsubscribe on a running session.
                # Keep gateway subscriptions + instrument mappings so remove/re-add does
                # not create duplicate subscriptions (which would double-count OHLCV).
                # _dispatch_shared_live gates delivery on _live_started, so detached
                # assets are ignored locally while their gateway subscription persists.
                if self._live_started:
                    return
            client = self._shared_live
            self._shared_live = None
            self._shared_started = False
            self._core_broken = False
            self._core_error_code = None
            self._live.clear()
            self._live_started.clear()
            self._subscriptions.clear()
            self._continuous_to_symbol.clear()
            self._instrument_to_symbol.clear()
            self._ready.clear()
            self._errors.clear()

        if client is not None:
            try:
                client.stop()
                if hasattr(client, "block_for_close"):
                    client.block_for_close(timeout=5.0)
            except Exception as stop_ex:
                try:
                    client.terminate()
                    if hasattr(client, "block_for_close"):
                        client.block_for_close(timeout=5.0)
                except Exception:
                    raise stop_ex

    def stop_live(self, symbol: Optional[str] = None) -> None:
        with self._session_lock:
            self._stop_live_unlocked(symbol)
        with self._depth_session_lock:
            self._stop_depth_unlocked(symbol)

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
        self._raise_live_error(symbol)
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
        self._ready[str(symbol)].wait(timeout=2.0)
        self._raise_live_error(symbol)
        with self._lock:
            return self._last_price.get(str(symbol))

    def trades(self, symbol: str, since_ts: Optional[int] = None, limit: int = 10_000) -> List[TradeTick]:
        self.start_live(symbol, schemas=("ohlcv-1s", "trades"))
        self._raise_live_error(symbol)
        with self._lock:
            rows = list(self._trades[str(symbol)])
        if since_ts is not None:
            rows = [x for x in rows if x.ts_event >= int(since_ts)]
        rows.sort(key=lambda x: (x.ts_recv_ns, x.ts_event_ns, x.sequence))
        return rows[-max(0, int(limit)):]

    def depth_events(self, symbol: str, *, schema: str = "mbp-10", limit: int = 2000) -> List[Dict[str, Any]]:
        if schema not in ("mbp-10", "mbo"):
            raise ValueError("schema must be 'mbp-10' or 'mbo'")
        key = str(symbol)
        self._prepare_depth_live([key], schema)
        with self._lock:
            ready = self._depth_ready[(key, schema)]
        if not ready.is_set():
            ready.wait(timeout=2.0)
        self._raise_depth_error(key, schema)
        with self._lock:
            rows = list(self._depth[(key, schema)])
        rows.sort(key=lambda row: (
            int(row.get("ts_recv_ns") or row.get("ts_event_ns") or 0),
            int(row.get("ts_event_ns") or 0),
            int(row.get("sequence") or 0),
        ))
        return rows[-max(0, int(limit)):]

    def mbo_snapshot(self, symbol: str, timeout: float = 5.0) -> List[Dict[str, Any]]:
        """Return a live MBO snapshot. Databento marks the final snapshot record F_LAST."""
        with self._snapshot_lock:
            return self._mbo_snapshot_locked(symbol, timeout)

    def _mbo_snapshot_locked(self, symbol: str, timeout: float) -> List[Dict[str, Any]]:
        # Snapshot requests use a temporary fourth session at peak (core + MBP-10 +
        # MBO + snapshot). Serialize them so concurrent HTTP/MCP callers cannot
        # multiply sessions or race close/timeout handling.
        last_flag = int(getattr(getattr(self._sdk, "RecordFlags", object), "F_LAST", 0) or 0)
        if not last_flag:
            raise RuntimeError("Databento SDK does not expose RecordFlags.F_LAST; cannot verify MBO snapshot completeness")

        client = self._live_factory()
        done = threading.Event()
        rows: List[Dict[str, Any]] = []
        error: List[str] = []

        def callback(record: Any) -> None:
            if done.is_set():
                return
            try:
                if hasattr(record, "err"):
                    code = int(getattr(record, "code", 0) or 0)
                    err = str(getattr(record, "err", "") or "Databento MBO snapshot error")
                    error.append(f"Databento MBO snapshot error code={code}: {err}")
                    done.set()
                    return
                # Snapshot streams also contain SymbolMappingMsg/SystemMsg records.
                # Only MBO records are part of the order-book snapshot returned to callers.
                if not hasattr(record, "order_id"):
                    return
                row = self._event_record(record)
                if row.get("schema") != "mbo":
                    return
                rows.append(row)
                flags = int(getattr(record, "flags", 0) or 0)
                if flags & last_flag:
                    done.set()
            except Exception as ex:
                error.append(f"Databento MBO snapshot record error: {type(ex).__name__}: {ex}")
                done.set()

        completed = False
        try:
            client.subscribe(
                dataset=self.dataset,
                schema="mbo",
                symbols=self.continuous_symbol(symbol, self.roll_rule),
                stype_in="continuous",
                snapshot=True,
            )
            client.add_callback(callback)
            client.start()
            completed = done.wait(max(0.1, float(timeout)))
        finally:
            try:
                client.stop()
                if hasattr(client, "block_for_close"):
                    client.block_for_close(timeout=5.0)
            except Exception as stop_ex:
                try:
                    client.terminate()
                    if hasattr(client, "block_for_close"):
                        client.block_for_close(timeout=5.0)
                except Exception:
                    raise stop_ex
        if error:
            raise RuntimeError(error[0])
        if not completed:
            raise TimeoutError(f"Databento MBO snapshot timed out for {symbol}")
        return rows
