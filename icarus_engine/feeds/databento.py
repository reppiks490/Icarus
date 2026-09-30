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


class Databento:
    """Continuous CME feed backed by Databento Historical + Live APIs."""

    GRANULARITIES = (1, 2, 5, 10, 15, 20, 30, 60, 120, 180, 240, 300, 600, 900, 1200, 1800, 3600, 14400, 86400)
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
        self._session_lock = threading.RLock()
        # One Live client/session per Databento dataset. Databento explicitly supports
        # many symbols/schemas on one session; this avoids exhausting team session limits
        # when ICARUS runs its full registered futures universe.
        self._shared_live: Any = None
        self._shared_started = False
        self._live: Dict[str, Any] = {}  # compatibility/status view: active symbol -> shared client
        self._live_started: set[str] = set()
        # Desired schemas survive socket replacement; _subscriptions describes only
        # what is attached to the current shared client.
        self._wanted_subscriptions: Dict[str, set[str]] = collections.defaultdict(set)
        self._subscriptions: Dict[str, set[str]] = collections.defaultdict(set)
        self._continuous_to_symbol: Dict[str, str] = {}
        self._instrument_to_symbol: Dict[int, str] = {}
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
        self._depth: Dict[str, Deque[Dict[str, Any]]] = collections.defaultdict(
            lambda: collections.deque(maxlen=max(1000, int(max_depth)))
        )
        self._last_price: Dict[str, float] = {}
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
            "live_session_model": "shared_per_dataset",
            "live_symbol_routing": "SymbolMappingMsg/instrument_id",
            "continuous_live_refresh": "automatic_utc_day",
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
        return TradeTick(
            ts_event=ts_ns // 1_000_000_000,
            ts_event_ns=ts_ns,
            price=cls._price(record, "price"),
            size=int(getattr(record, "size", 0) or 0),
            side=str(getattr(record, "side", "") or ""),
            action=str(getattr(record, "action", "T") or "T"),
            sequence=int(getattr(record, "sequence", 0) or 0),
        )

    @staticmethod
    def _trade_key(tick: TradeTick) -> Tuple[int, float, int, str, int]:
        return (tick.ts_event_ns, tick.price, tick.size, tick.side, tick.sequence)

    def _append_trade_locked(self, symbol: str, tick: TradeTick) -> bool:
        """Append one exchange trade once even when several live schemas report it.

        Caller must hold self._lock. The dedupe set is kept in exact lockstep
        with the bounded deque so it cannot grow without bound.
        """
        key = self._trade_key(tick)
        seen = self._trade_seen[symbol]
        if key in seen:
            return False
        q = self._trades[symbol]
        if q and tick.ts_event_ns < q[-1].ts_event_ns:
            return False
        if q.maxlen is not None and len(q) >= q.maxlen and q:
            seen.discard(self._trade_key(q[0]))
        q.append(tick)
        seen.add(key)
        return True

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
                q = self._second_bars[symbol]
                accepted = False
                if not q or b.ts > q[-1].ts:
                    q.append(b)
                    accepted = True
                elif b.ts == q[-1].ts:
                    q[-1] = b
                    accepted = True
                # Older replay rows are already buffered; ignore them rather than
                # duplicating one-second volume or rewinding the live mark.
                if accepted:
                    self._last_price[symbol] = b.c
                    market_event = True
            else:
                # MBO trade records are both trades and order-book events; keep both views.
                if hasattr(record, "price") and hasattr(record, "size") and str(getattr(record, "action", "T") or "T") == "T":
                    tick = self._trade_record(record)
                    if self._append_trade_locked(symbol, tick):
                        self._last_price[symbol] = tick.price
                        market_event = True
                if hasattr(record, "levels") or hasattr(record, "order_id"):
                    self._depth[symbol].append(self._event_record(record))
                    market_event = True
            if market_event:
                self._feed_time[symbol] = max(now_sec, self._feed_time.get(symbol, 0))
                self._ready[symbol].set()
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
            err = str(getattr(record, "err", "") or "")
            with self._lock:
                active = set(self._live_started)
                targets = [key for cont, key in self._continuous_to_symbol.items()
                           if key in active and cont and cont in err]
                if not targets:
                    targets = list(active)
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
            symbols = list(self._live_started)
        for symbol in symbols:
            self._record_reconnect(symbol, previous, resumed)

    def _raise_live_error(self, symbol: str) -> None:
        with self._lock:
            err = self._errors.get(str(symbol))
        if err:
            raise RuntimeError(err)

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
        desired = {str(s) for s in schemas}
        if include_depth:
            if include_depth not in ("mbp-10", "mbo"):
                raise ValueError("include_depth must be 'mbp-10' or 'mbo'")
            desired.add(include_depth)
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
            return self._prepare_live_unlocked(
                symbols, schemas=schemas, start_ts=start_ts, include_depth=include_depth
            )

    def refresh_live(self, symbols: Sequence[str], *, start_ts: Optional[int] = None) -> Any:
        """Atomically re-resolve continuous symbols on a fresh shared Live session.

        Each active symbol keeps its exact schema set. This is important for depth:
        an NQ MBO request must not silently disappear at the daily continuous refresh,
        and it must not accidentally broaden MBO to every futures symbol.
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
                    self._live.clear()
                    self._live_started.clear()
                    self._subscriptions.clear()
                    self._continuous_to_symbol.clear()
                    self._instrument_to_symbol.clear()
                    self._ready.clear()
                    self._errors.clear()
                raise

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
        return rows[-max(0, int(limit)):]

    def depth_events(self, symbol: str, *, schema: str = "mbp-10", limit: int = 2000) -> List[Dict[str, Any]]:
        if schema not in ("mbp-10", "mbo"):
            raise ValueError("schema must be 'mbp-10' or 'mbo'")
        self.start_live(symbol, include_depth=schema)
        self._raise_live_error(symbol)
        with self._lock:
            rows = [row for row in self._depth[str(symbol)] if row.get("schema") == schema]
        return rows[-max(0, int(limit)):]

    def mbo_snapshot(self, symbol: str, timeout: float = 5.0) -> List[Dict[str, Any]]:
        """Return a live MBO snapshot. Databento marks the final snapshot record F_LAST."""
        client = self._live_factory()
        done = threading.Event()
        rows: List[Dict[str, Any]] = []
        error: List[str] = []
        last_flag = int(getattr(getattr(self._sdk, "RecordFlags", object), "F_LAST", 0) or 0)

        def callback(record: Any) -> None:
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
            if last_flag and flags & last_flag:
                done.set()

        client.subscribe(
            dataset=self.dataset,
            schema="mbo",
            symbols=self.continuous_symbol(symbol, self.roll_rule),
            stype_in="continuous",
            snapshot=True,
        )
        client.add_callback(callback)
        client.start()
        try:
            done.wait(max(0.1, float(timeout)))
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
        if last_flag and not done.is_set():
            raise TimeoutError(f"Databento MBO snapshot timed out for {symbol}")
        return rows
