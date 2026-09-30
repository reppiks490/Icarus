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
_UNDEF_PRICE = (1 << 63) - 1


@dataclass(frozen=True)
class TradeTick:
    ts_event: int                  # whole seconds for coarse filtering/UI compatibility
    ts_event_ns: int               # original Databento nanosecond event timestamp
    price: float
    size: int
    side: str = ""
    action: str = "T"
    sequence: int = 0
    instrument_id: int = 0


class Databento:
    """Continuous CME feed backed by Databento Historical + Live APIs."""

    # Source/transport granularities in seconds. This includes every minute/hour
    # chart interval exposed by ICARUS (1/2/3/5/10/15/20/30/45/60/120/180/240m)
    # plus native 1-second data. D/W chart alignment remains owned by the engine calendar.
    GRANULARITIES = (1, 2, 5, 10, 15, 20, 30, 60, 120, 180, 240, 300, 600, 900, 1200, 1800, 2700, 3600, 7200, 10800, 14400, 86400)
    DATASET = _DATASET

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
        self._live: Dict[str, Any] = {}
        self._live_started: set[str] = set()
        self._subscriptions: Dict[str, set[str]] = collections.defaultdict(set)
        self._ready: Dict[str, threading.Event] = collections.defaultdict(threading.Event)
        self._second_bars: Dict[str, Deque[Bar]] = collections.defaultdict(
            lambda: collections.deque(maxlen=max(60, int(max_live_seconds)))
        )
        self._bar_seen: Dict[str, set[int]] = collections.defaultdict(set)
        self._trades: Dict[str, Deque[TradeTick]] = collections.defaultdict(
            lambda: collections.deque(maxlen=max(1000, int(max_trades)))
        )
        self._trade_seen: Dict[str, set[Tuple[int, int, int]]] = collections.defaultdict(set)
        self._trade_seen_order: Dict[str, Deque[Tuple[int, int, int]]] = collections.defaultdict(
            lambda: collections.deque(maxlen=max(1000, int(max_trades)))
        )
        # Keep each market-depth schema in its own bounded queue. Filtering one
        # shared queue on read is not sufficient because a busy MBO stream could
        # evict MBP-10 rows (or vice versa) before the caller ever sees them.
        self._depth: Dict[Tuple[str, str], Deque[Dict[str, Any]]] = collections.defaultdict(
            lambda: collections.deque(maxlen=max(1000, int(max_depth)))
        )
        self._last_price: Dict[str, float] = {}
        self._feed_time: Dict[str, int] = {}
        self._meta: Dict[str, Dict[str, Any]] = {}
        self._errors: Dict[str, str] = {}
        # Parser/callback exceptions indicate an adapter correctness failure, not a
        # transient gateway message. Keep them sticky until the session is stopped.
        self._callback_errors: Dict[str, str] = {}
        self._recovery_required: Dict[str, str] = {}
        self._recovery_count: Dict[str, int] = collections.defaultdict(int)
        self._historical_seed_attempt: Dict[str, int] = {}
        self._historical_seed_error: Dict[str, str] = {}
        self._reconnect_gaps: Dict[str, Deque[Dict[str, str]]] = collections.defaultdict(
            lambda: collections.deque(maxlen=100)
        )
        # Databento documents that an already-running continuous subscription is
        # not automatically remapped when the smart symbol rolls. Cache the
        # no-cost daily symbology resolution and rotate only when its instrument
        # ID changes.
        self._resolution_day: Dict[str, str] = {}
        self._resolved_instrument: Dict[str, int] = {}
        self._roll_count: Dict[str, int] = collections.defaultdict(int)
        self.requests = 0
        self.resolution_requests = 0

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
            "live_roll_verified": True,
            "live_roll_verification": "daily_symbology_resolution_and_session_rotation",
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
        """Return a real Databento price, or None for DBN's undefined-price sentinel."""
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
        return TradeTick(
            ts_event=ts_ns // 1_000_000_000,
            ts_event_ns=ts_ns,
            price=cls._price(record, "price"),
            size=int(getattr(record, "size", 0) or 0),
            side=str(getattr(record, "side", "") or ""),
            action=str(getattr(record, "action", "T") or "T"),
            sequence=int(getattr(record, "sequence", 0) or 0),
            instrument_id=int(getattr(record, "instrument_id", 0) or 0),
        )

    @classmethod
    def _event_record(cls, record: Any) -> Dict[str, Any]:
        ts_ns = int(getattr(record, "ts_event")) if hasattr(record, "ts_event") else None
        levels = getattr(record, "levels", None)
        schema = "mbp-10" if levels is not None else ("mbo" if hasattr(record, "order_id") else "unknown")
        out: Dict[str, Any] = {
            "ts_event": (ts_ns // 1_000_000_000) if ts_ns is not None else None,
            "ts_event_ns": ts_ns,
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

    @staticmethod
    def _utc_day() -> str:
        return datetime.now(timezone.utc).date().isoformat()

    def _resolve_continuous_instrument(self, symbol: str, day: str) -> Optional[int]:
        """Resolve today's smart symbol to its actual instrument ID.

        Historical.symbology.resolve is free and is the authoritative way to
        detect a Databento continuous-contract roll. Test doubles without the
        symbology service return None and retain the legacy mocked behavior.
        """
        symbology = getattr(self._historical, "symbology", None)
        resolver = getattr(symbology, "resolve", None)
        if not callable(resolver):
            return None
        continuous = self.continuous_symbol(symbol, self.roll_rule)
        self.resolution_requests += 1
        try:
            result = resolver(
                dataset=self.dataset,
                symbols=continuous,
                stype_in="continuous",
                stype_out="instrument_id",
                start_date=day,
            )
        except Exception as ex:
            raise RuntimeError(
                f"Databento continuous symbology resolution failed for {continuous} on {day}: "
                f"{type(ex).__name__}: {ex}"
            ) from ex
        rows = (result.get("result", {}) or {}).get(continuous, []) if isinstance(result, dict) else []
        if not rows:
            message = result.get("message", "no mapping") if isinstance(result, dict) else "invalid response"
            raise RuntimeError(f"Databento continuous symbology did not resolve {continuous} on {day}: {message}")
        try:
            return int(rows[-1]["s"])
        except (KeyError, TypeError, ValueError) as ex:
            raise RuntimeError(f"Databento returned an invalid instrument mapping for {continuous} on {day}") from ex

    def _purge_replay_overlap(self, symbol: str, replay_from: int) -> None:
        """Remove events in a window that a replacement session will replay."""
        key = str(symbol)
        with self._lock:
            bars = self._second_bars[key]
            kept_bars = [b for b in bars if b.ts < int(replay_from)]
            bars.clear()
            bars.extend(kept_bars)
            self._bar_seen[key] = {b.ts for b in bars}

            trades = self._trades[key]
            kept_trades = [t for t in trades if t.ts_event < int(replay_from)]
            trades.clear()
            trades.extend(kept_trades)
            order = self._trade_seen_order[key]
            order.clear()
            seen: set[Tuple[int, int, int]] = set()
            for tick in trades:
                k = (tick.instrument_id, tick.ts_event_ns, tick.sequence)
                if k not in seen:
                    order.append(k)
                    seen.add(k)
            self._trade_seen[key] = seen

            # Depth events are contract-specific and are not replayed by the
            # controlled-roll session. Clear them so callers cannot mistake an
            # old-contract book for the newly mapped contract.
            self._depth[(key, "mbp-10")].clear()
            self._depth[(key, "mbo")].clear()
            self._feed_time[key] = 0
            self._last_price.pop(key, None)

    def _recover_data_gap(self, symbol: str) -> Tuple[set[str], Optional[int]]:
        """Restart/replay after Databento reports skipped records from slow reading."""
        key = str(symbol)
        with self._lock:
            reason = self._recovery_required.pop(key, None)
            if not reason or key not in self._live_started:
                return set(), None
            schemas = set(self._subscriptions.get(key, set()))
            feed_time = int(self._feed_time.get(key, 0))
        now = int(time.time())
        replay_from = max(now - 23 * 3600, feed_time - 120) if feed_time else max(0, now - 120)
        self._purge_replay_overlap(key, replay_from)
        self.stop_live(key)
        with self._lock:
            self._recovery_count[key] += 1
            meta = dict(self._meta.get(key, {}))
            meta.update({
                "recovery_count": self._recovery_count[key],
                "last_recovery_ts": now,
                "last_recovery_reason": reason,
                "recovery_pending": False,
            })
            self._meta[key] = meta
        return schemas, replay_from

    def _refresh_continuous_mapping(self, symbol: str) -> Tuple[set[str], Optional[int]]:
        """Rotate a live session when Databento's daily smart-symbol mapping changes.

        Returns the schemas/start timestamp that a replacement session should
        replay. Databento has no unsubscribe operation, so a clean reconnect is
        required to drop the old physical contract.
        """
        key = str(symbol)
        day = self._utc_day()
        with self._lock:
            if self._resolution_day.get(key) == day:
                return set(), None
        current = self._resolve_continuous_instrument(symbol, day)
        if current is None:
            return set(), None
        with self._lock:
            # Another caller may have completed the same daily check while the
            # resolver request was in flight.
            if self._resolution_day.get(key) == day:
                return set(), None
            previous = self._resolved_instrument.get(key)
            self._resolution_day[key] = day
            self._resolved_instrument[key] = current
            live = key in self._live_started
            schemas = set(self._subscriptions.get(key, set()))
            feed_time = int(self._feed_time.get(key, 0))
        if not live or previous is None or previous == current:
            with self._lock:
                meta = dict(self._meta.get(key, {}))
                meta.update({"resolution_date": day, "resolved_instrument_id": current})
                self._meta[key] = meta
            return set(), None

        # Replace a bounded overlap so any old physical-contract events received
        # after the mapping date changed cannot survive timestamp dedupe. The live
        # API supports up to 24 hours of replay; two minutes is enough to cover
        # normal poll/reconnect latency while keeping recovery small.
        now = int(time.time())
        replay_from = max(now - 23 * 3600, feed_time - 120) if feed_time else max(0, now - 120)
        self._purge_replay_overlap(key, replay_from)
        self.stop_live(key)
        with self._lock:
            self._roll_count[key] += 1
            meta = dict(self._meta.get(key, {}))
            meta.update({
                "resolution_date": day,
                "resolved_instrument_id": current,
                "previous_instrument_id": previous,
                "roll_count": self._roll_count[key],
                "last_roll_ts": now,
            })
            self._meta[key] = meta
        return schemas, replay_from

    def _live_callback(self, symbol: str, record: Any) -> None:
        now_sec = self._ts_sec(record) if hasattr(record, "ts_event") else int(time.time())
        with self._lock:
            # ErrorMsg records are delivered through the same callback as market data.
            # Since 2026 symbol-resolution failures can be non-fatal at the gateway,
            # so fail closed here instead of silently waiting on an unresolved stream.
            if hasattr(record, "err"):
                code = int(getattr(record, "code", 0) or 0)
                err = str(getattr(record, "err", "") or "Databento live error")
                msg = f"Databento live error code={code}: {err}"
                self._errors[symbol] = msg
                # Error code 7 means the gateway skipped records to recover from a
                # slow reader. It is non-fatal, but continuing would leave a silent
                # hole in bars/ticks. Force a bounded replay on the next API poll.
                if code == 7:
                    self._recovery_required[symbol] = msg
                elif code != 4:
                    # SymbolResolutionFailed (4) may resolve later; all other
                    # gateway errors are sticky until the session is replaced.
                    self._callback_errors[symbol] = msg
                self._ready[symbol].set()
                meta = dict(self._meta.get(symbol, {}))
                meta.update({
                    "regularMarketTime": self._feed_time.get(symbol, 0),
                    "provider": "databento",
                    "dataset": self.dataset,
                    "continuous_symbol": self.continuous_symbol(symbol, self.roll_rule),
                    "live_error": msg,
                })
                self._meta[symbol] = meta
                return
            # SystemMsg is informational but slow-reader warnings and replay
            # completion are useful operational evidence.
            if hasattr(record, "msg") and hasattr(record, "code"):
                code = int(getattr(record, "code", 0) or 0)
                meta = dict(self._meta.get(symbol, {}))
                meta.update({
                    "regularMarketTime": self._feed_time.get(symbol, 0),
                    "provider": "databento",
                    "dataset": self.dataset,
                    "continuous_symbol": self.continuous_symbol(symbol, self.roll_rule),
                })
                if code == 2:
                    meta["slow_reader_warning"] = str(getattr(record, "msg", "") or "slow reader")
                    meta["slow_reader_warning_ts"] = int(time.time())
                elif code == 3:
                    meta["last_replay_completed_ts"] = int(time.time())
                    meta.pop("slow_reader_warning", None)
                    meta.pop("slow_reader_warning_ts", None)
                self._meta[symbol] = meta
                return
            # SymbolMappingMsg is the live proof of which physical contract the
            # smart symbol resolved to. It is metadata, not market readiness.
            if all(hasattr(record, key) for key in ("stype_in_symbol", "stype_out_symbol", "instrument_id")):
                meta = dict(self._meta.get(symbol, {}))
                meta.update({
                    "provider": "databento",
                    "dataset": self.dataset,
                    "continuous_symbol": str(getattr(record, "stype_in_symbol")),
                    "active_contract": str(getattr(record, "stype_out_symbol")),
                    "active_instrument_id": int(getattr(record, "instrument_id")),
                    "mapping_start_ts": int(getattr(record, "start_ts", 0) or 0),
                    "mapping_end_ts": int(getattr(record, "end_ts", 0) or 0),
                })
                if symbol in self._errors and symbol not in self._callback_errors:
                    self._errors.pop(symbol, None)
                    meta.pop("live_error", None)
                self._meta[symbol] = meta
                return
            market_event = False
            # OHLCV record
            if all(hasattr(record, key) for key in ("open", "high", "low", "close", "volume")):
                b = self._ohlcv_record(record)
                rows = self._second_bars[symbol]
                seen = self._bar_seen[symbol]
                if b.ts not in seen:
                    if rows.maxlen is not None and len(rows) >= rows.maxlen and rows:
                        seen.discard(rows[0].ts)
                    rows.append(b)
                    seen.add(b.ts)
                self._last_price[symbol] = b.c
                market_event = True
            else:
                # The trades, MBP-10 and MBO schemas can describe the same economic
                # trade. Keep the public raw-tick stream sourced only from the
                # Databento trades schema; otherwise subscribing to depth would
                # double-count MBO/MBP trade actions.
                depth_schema: Optional[str] = None
                if hasattr(record, "levels"):
                    depth_schema = "mbp-10"
                elif hasattr(record, "order_id"):
                    depth_schema = "mbo"
                if depth_schema is not None:
                    event = self._event_record(record)
                    self._depth[(symbol, depth_schema)].append(event)
                    market_event = True
                elif hasattr(record, "price") and hasattr(record, "size") and str(getattr(record, "action", "T") or "T") == "T":
                    tick = self._trade_record(record)
                    key = (tick.instrument_id, tick.ts_event_ns, tick.sequence)
                    seen = self._trade_seen[symbol]
                    order = self._trade_seen_order[symbol]
                    if key not in seen:
                        if order.maxlen is not None and len(order) >= order.maxlen and order:
                            seen.discard(order[0])
                        self._trades[symbol].append(tick)
                        order.append(key)
                        seen.add(key)
                    self._last_price[symbol] = tick.price
                    market_event = True
            if market_event:
                self._feed_time[symbol] = max(now_sec, self._feed_time.get(symbol, 0))
                self._ready[symbol].set()
                if symbol not in self._callback_errors and symbol not in self._recovery_required:
                    self._errors.pop(symbol, None)
            meta = dict(self._meta.get(symbol, {}))
            meta.update({
                "regularMarketTime": self._feed_time.get(symbol, 0),
                "provider": "databento",
                "dataset": self.dataset,
                "continuous_symbol": self.continuous_symbol(symbol, self.roll_rule),
            })
            live_error = (
                self._callback_errors.get(symbol)
                or self._recovery_required.get(symbol)
                or self._errors.get(symbol)
            )
            if live_error:
                meta["live_error"] = live_error
            else:
                meta.pop("live_error", None)
            self._meta[symbol] = meta

    def _record_live_exception(self, symbol: str, ex: BaseException) -> None:
        """Publish asynchronous SDK failures to the synchronous engine poll path."""
        key = str(symbol)
        with self._lock:
            msg = f"Databento callback exception: {type(ex).__name__}: {ex}"
            self._callback_errors[key] = msg
            self._errors[key] = msg
            self._ready[key].set()
            meta = dict(self._meta.get(key, {}))
            meta["live_error"] = msg
            self._meta[key] = meta

    def _raise_live_error(self, symbol: str) -> None:
        with self._lock:
            key = str(symbol)
            err = self._callback_errors.get(key) or self._errors.get(key)
        if err:
            raise RuntimeError(err)

    def _record_reconnect(self, symbol: str, previous: Any, resumed: Any) -> None:
        # Keep this callback non-blocking. Databento exposes the last timestamp from
        # the old session and the first timestamp of the resumed session specifically
        # so clients can detect/recover gaps. Mark recovery here; the next normal
        # engine/API poll performs the bounded stop/replay/dedup cycle.
        key = str(symbol)
        row = {"previous": str(previous), "resumed": str(resumed)}
        reason = f"Databento reconnect gap previous={row['previous']} resumed={row['resumed']}"
        with self._lock:
            self._reconnect_gaps[key].append(row)
            self._recovery_required[key] = reason
            meta = dict(self._meta.get(key, {}))
            meta["last_reconnect_gap"] = row
            meta["reconnect_count"] = len(self._reconnect_gaps[key])
            meta["recovery_pending"] = True
            meta["live_error"] = reason
            self._meta[key] = meta

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
        if include_depth and include_depth not in ("mbp-10", "mbo"):
            raise ValueError("include_depth must be 'mbp-10' or 'mbo'")
        recovery_schemas, recovery_start = self._recover_data_gap(symbol)
        desired.update(recovery_schemas)
        if recovery_start is not None:
            start_ts = recovery_start if start_ts is None else min(int(start_ts), int(recovery_start))
        rollover_schemas, rollover_start = self._refresh_continuous_mapping(symbol)
        desired.update(rollover_schemas)
        if rollover_start is not None:
            start_ts = rollover_start if start_ts is None else min(int(start_ts), int(rollover_start))
        if include_depth:
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
                        symbols=self.continuous_symbol(symbol, self.roll_rule),
                        stype_in="continuous",
                    )
                    self._subscriptions[key].add(schema)
                return client
            client = self._live_factory()
            kwargs: Dict[str, Any] = {
                "dataset": self.dataset,
                "symbols": self.continuous_symbol(symbol, self.roll_rule),
                "stype_in": "continuous",
            }
            try:
                for schema in sorted(desired):
                    sub_kwargs = dict(kwargs)
                    if start_ts is not None and schema in ("ohlcv-1s", "trades"):
                        # Reconnect replay is useful for stateless tape/bar schemas.
                        # Depth is deliberately restarted at live-now; MBO state is
                        # available through mbo_snapshot(), and replaying L2/L3 here
                        # would duplicate event history after a controlled roll.
                        sub_kwargs["start"] = self._iso(start_ts)
                    client.subscribe(schema=schema, **sub_kwargs)
                    self._subscriptions[key].add(schema)
                record_cb = lambda rec, s=key: self._live_callback(s, rec)
                error_cb = lambda ex, s=key: self._record_live_exception(s, ex)
                try:
                    client.add_callback(record_cb, exception_callback=error_cb)
                except TypeError:
                    # Some older SDK shims/fakes accept the exception callback only
                    # positionally. Support both without weakening real SDK behavior.
                    client.add_callback(record_cb, error_cb)
                if hasattr(client, "add_reconnect_callback"):
                    reconnect_cb = lambda previous, resumed, s=key: self._record_reconnect(s, previous, resumed)
                    try:
                        client.add_reconnect_callback(reconnect_cb, exception_callback=error_cb)
                    except TypeError:
                        client.add_reconnect_callback(reconnect_cb)
                client.start()
            except Exception:
                try:
                    client.stop()
                except Exception:
                    pass
                self._subscriptions.pop(key, None)
                self._ready.pop(key, None)
                raise
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
                if hasattr(client, "block_for_close"):
                    client.block_for_close(timeout=5.0)
            finally:
                with self._lock:
                    self._live.pop(key, None)
                    self._live_started.discard(key)
                    self._subscriptions.pop(key, None)
                    self._ready.pop(key, None)
                    self._errors.pop(key, None)
                    self._callback_errors.pop(key, None)
                    self._recovery_required.pop(key, None)

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
        key = str(symbol)
        with self._lock:
            rows = list(self._second_bars[key])
            ft = int(self._feed_time.get(key, 0))
            px = self._last_price.get(key)
        if since_ts is not None:
            rows = [b for b in rows if b.ts >= int(since_ts) - max(2, int(granularity))]
        bars = rows if int(granularity) == 1 else self._aggregate(rows, int(granularity))
        if bars or ft:
            return bars, ft, px

        # A fresh live session can legitimately be silent at a CME close, during
        # maintenance, or while reconnecting. Seed the feed clock/mark from
        # Historical, but throttle empty/error seeds so a weekend cannot become a
        # paid historical request every engine poll.
        with self._lock:
            last_seed = int(self._historical_seed_attempt.get(key, 0))
            cached_seed_error = self._historical_seed_error.get(key)
        if last_seed and now - last_seed < 300:
            if cached_seed_error:
                raise RuntimeError(cached_seed_error)
            return bars, ft, px

        g = int(granularity)
        hist_start = int(since_ts or (now - max(900, g * 10)))
        with self._lock:
            self._historical_seed_attempt[key] = now
            self._historical_seed_error.pop(key, None)
        try:
            bars = self.candles(symbol, g, max(0, hist_start - 2 * g), now)
        except Exception as ex:
            msg = f"Databento historical seed failed for {symbol}: {type(ex).__name__}: {ex}"
            with self._lock:
                self._historical_seed_error[key] = msg
                meta = dict(self._meta.get(key, {}))
                meta.update({
                    "historical_seed_attempt_ts": now,
                    "historical_seed_error": msg,
                })
                self._meta[key] = meta
            raise RuntimeError(msg) from ex
        if bars:
            px = bars[-1].c
            ft = bars[-1].ts + g
            with self._lock:
                self._historical_seed_error.pop(key, None)
                self._last_price[key] = px
                self._feed_time[key] = max(self._feed_time.get(key, 0), ft)
                meta = dict(self._meta.get(key, {}))
                meta.update({
                    "regularMarketTime": self._feed_time[key],
                    "provider": "databento",
                    "dataset": self.dataset,
                    "continuous_symbol": self.continuous_symbol(symbol, self.roll_rule),
                    "historical_seed": True,
                    "historical_seed_attempt_ts": now,
                    "historical_seed_empty": False,
                })
                meta.pop("historical_seed_error", None)
                self._meta[key] = meta
                ft = self._feed_time[key]
        else:
            with self._lock:
                meta = dict(self._meta.get(key, {}))
                meta.update({
                    "provider": "databento",
                    "dataset": self.dataset,
                    "continuous_symbol": self.continuous_symbol(symbol, self.roll_rule),
                    "historical_seed_attempt_ts": now,
                    "historical_seed_empty": True,
                })
                meta.pop("historical_seed_error", None)
                self._meta[key] = meta
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
        return rows[-max(0, int(limit)):]

    def depth_events(self, symbol: str, *, schema: str = "mbp-10", limit: int = 2000) -> List[Dict[str, Any]]:
        if schema not in ("mbp-10", "mbo"):
            raise ValueError("schema must be 'mbp-10' or 'mbo'")
        self.start_live(symbol, include_depth=schema)
        self._raise_live_error(symbol)
        with self._lock:
            rows = list(self._depth[(str(symbol), schema)])
        return rows[-max(0, int(limit)):]

    def mbo_snapshot(self, symbol: str, timeout: float = 5.0) -> List[Dict[str, Any]]:
        """Return a live MBO snapshot. Databento marks the final snapshot record F_LAST."""
        client = self._live_factory()
        done = threading.Event()
        rows: List[Dict[str, Any]] = []
        error: List[str] = []
        flags_enum = getattr(self._sdk, "RecordFlags", None)
        last_flag = int(getattr(flags_enum, "F_LAST", 0) or 0)
        snapshot_flag = int(getattr(flags_enum, "F_SNAPSHOT", 0) or 0)
        if not last_flag:
            raise RuntimeError("Databento SDK does not expose RecordFlags.F_LAST; refusing an unbounded MBO snapshot")

        def callback(record: Any) -> None:
            if hasattr(record, "err"):
                code = int(getattr(record, "code", 0) or 0)
                err = str(getattr(record, "err", "") or "Databento MBO snapshot error")
                error.append(f"Databento MBO snapshot error code={code}: {err}")
                done.set()
                return
            # Snapshot subscriptions also emit symbol/system messages and can
            # immediately continue with realtime records. Return only MBO order
            # records that belong to the snapshot itself.
            if not hasattr(record, "order_id"):
                return
            flags = int(getattr(record, "flags", 0) or 0)
            if snapshot_flag and not (flags & snapshot_flag):
                return
            row = self._event_record(record)
            row["snapshot"] = True
            rows.append(row)
            if flags & last_flag:
                done.set()

        client.subscribe(
            dataset=self.dataset,
            schema="mbo",
            symbols=self.continuous_symbol(symbol, self.roll_rule),
            stype_in="continuous",
            snapshot=True,
        )
        def snapshot_error(ex: BaseException) -> None:
            error.append(f"Databento MBO snapshot exception: {type(ex).__name__}: {ex}")
            done.set()

        try:
            client.add_callback(callback, exception_callback=snapshot_error)
        except TypeError:
            client.add_callback(callback, snapshot_error)
        try:
            client.start()
            done.wait(max(0.1, float(timeout)))
        finally:
            try:
                client.stop()
            finally:
                if hasattr(client, "block_for_close"):
                    client.block_for_close(timeout=5.0)
        if error:
            raise RuntimeError(error[0])
        if not done.is_set():
            raise TimeoutError(f"Databento MBO snapshot timed out for {symbol}")
        return rows
