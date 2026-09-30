"""Authentic trade-event adapters for sub-minute ICARUS charts.

Futures:
  Databento GLBX.MDP3 trades using continuous volume-ranked symbology ROOT.v.0.
  The live session is automatically renewed so smart symbology is re-resolved;
  the caller never supplies or maintains expiry/month contracts.

Crypto:
  Coinbase Exchange public trades REST, normalized to immutable TradeEvent rows.

No adapter interpolates, expands, or fabricates trades. Seconds and tick charts
remain capability-gated unless one of these adapters is actually available.
"""
from __future__ import annotations

import collections
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import math
import os
import queue
import threading
import time
import urllib.parse
import urllib.request
from typing import Deque, Iterable, List, Optional

from ..microstructure import TradeEvent
from ..pine.timeframe import Bar

_UA = {"User-Agent": "icarus-engine/0.1 (+paper trading event adapter)"}


def _iso_ns(ns: int) -> str:
    sec, rem = divmod(int(ns), 1_000_000_000)
    dt = datetime.fromtimestamp(sec, tz=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + f".{rem:09d}Z"


def _price_ticks(value, mintick: float) -> int:
    if not mintick or not math.isfinite(float(mintick)) or float(mintick) <= 0:
        raise ValueError("mintick must be positive")
    try:
        q = Decimal(str(value)) / Decimal(str(mintick))
    except (InvalidOperation, ValueError) as ex:
        raise ValueError(f"invalid trade price {value!r}") from ex
    nearest = q.to_integral_value()
    if abs(q - nearest) > Decimal("0.000001"):
        raise ValueError(f"trade price {value!r} is not aligned to mintick {mintick}")
    return int(nearest)


def _coinbase_event(product: str, row: dict, received_ns: int, mintick: float) -> TradeEvent:
    trade_id = row.get("trade_id")
    if type(trade_id) is not int or trade_id < 0:
        raise ValueError("Coinbase trade_id must be a non-negative integer")
    dt = datetime.fromisoformat(str(row.get("time", "")).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("Coinbase trade timestamp lacks timezone")
    epoch = dt.astimezone(timezone.utc) - datetime(1970, 1, 1, tzinfo=timezone.utc)
    event_ns = (epoch.days * 86400 + epoch.seconds) * 1_000_000_000 + epoch.microseconds * 1000
    received_ns = max(int(received_ns), event_ns)
    qty = float(row["size"])
    side = row.get("side")
    if side not in ("buy", "sell"):
        aggressor = "unknown"
    else:
        # Coinbase Exchange REST "side" is the maker side, so aggressor is opposite.
        aggressor = "sell" if side == "buy" else "buy"
    return TradeEvent(
        "coinbase-exchange", product, trade_id, event_ns, received_ns,
        _price_ticks(row["price"], mintick), qty, aggressor,
    )


class CoinbaseTradeEvents:
    """Public Coinbase time-and-sales adapter. No credentials required."""

    def __init__(self, product: str, mintick: float, *, max_pages: int = 8):
        self.instrument = str(product)
        self.mintick = float(mintick)
        self.max_pages = max(1, min(int(max_pages), 50))
        self._last_id: Optional[int] = None
        self._last_event_ns: Optional[int] = None
        self._error = ""
        self._connected = False

    @property
    def available(self) -> bool:
        return True

    @property
    def reason(self) -> str:
        return self._error

    def start(self) -> None:
        self._connected = True

    def stop(self) -> None:
        self._connected = False

    def _page(self, after: Optional[str] = None):
        q = {"limit": 1000}
        if after:
            q["after"] = after
        url = "https://api.exchange.coinbase.com/products/" + urllib.parse.quote(self.instrument, safe="") + "/trades?" + urllib.parse.urlencode(q)
        req = urllib.request.Request(url, headers=_UA)
        with urllib.request.urlopen(req, timeout=8) as response:
            raw = response.read(4 * 1024 * 1024 + 1)
            if len(raw) > 4 * 1024 * 1024:
                raise ValueError("Coinbase trade response exceeds 4 MiB")
            received_ns = time.time_ns()
            rows = json.loads(raw.decode("utf-8"))
            if not isinstance(rows, list):
                raise ValueError("Coinbase trade response is not a list")
            return rows, response.headers.get("CB-AFTER") or response.headers.get("cb-after"), received_ns

    def _fetch(self, max_events: int, stop_id: Optional[int]) -> List[TradeEvent]:
        fetched = {}
        cursor = None
        for _ in range(self.max_pages):
            rows, next_cursor, received_ns = self._page(cursor)
            if not rows:
                break
            for row in rows:
                tid = row.get("trade_id")
                if type(tid) is int:
                    fetched.setdefault(tid, (row, received_ns))
            if stop_id is not None and fetched and min(fetched) <= stop_id:
                break
            if len(fetched) >= max_events:
                break
            if not next_cursor or next_cursor == cursor:
                break
            cursor = next_cursor
        events = []
        for tid in sorted(fetched):
            if stop_id is not None and tid <= stop_id:
                continue
            row, received = fetched[tid]
            events.append(_coinbase_event(self.instrument, row, received, self.mintick))
        if len(events) > max_events:
            events = events[-max_events:]
        return events

    def history(self, start_ns: int, end_ns: int, *, max_events: int = 100000) -> List[TradeEvent]:
        # REST pagination is event-count bounded. Filter exact event timestamps after retrieval.
        events = self._fetch(max_events, None)
        return [e for e in events if int(start_ns) <= e.event_ns < int(end_ns)]

    def drain(self, *, max_events: int = 50000) -> List[TradeEvent]:
        try:
            events = self._fetch(max_events, self._last_id)
            if events:
                self._last_id = events[-1].sequence
                self._last_event_ns = events[-1].event_ns
            self._connected = True
            self._error = ""
            return events
        except Exception as ex:
            self._error = f"{type(ex).__name__}: {ex}"
            self._connected = False
            raise

    def status(self) -> dict:
        return {
            "provider": "coinbase-exchange",
            "instrument": self.instrument,
            "continuous": False,
            "authentic_trade_events": True,
            "connected": self._connected,
            "last_event_ns": self._last_event_ns,
            "error": self._error or None,
        }


class DatabentoContinuousEvents:
    """Databento CME/CBOT/COMEX/NYMEX continuous trade adapter.

    Uses volume-ranked smart symbology ROOT.v.0. Sessions are deliberately
    renewed periodically because Databento documents that an already-open live
    continuous subscription is not remapped in-place when its mapping changes.
    """

    DATASET = "GLBX.MDP3"

    def __init__(self, root: str, mintick: float, *, reconnect_sec: Optional[int] = None,
                 db_module=None, queue_size: int = 250000):
        self.root = str(root).upper()
        self.instrument = f"{self.root}.v.0"
        self.mintick = float(mintick)
        self.reconnect_sec = max(30, int(reconnect_sec or os.environ.get("ICARUS_DATABENTO_RESOLVE_SEC", "300")))
        self._db_module = db_module
        self._queue: "queue.Queue[TradeEvent]" = queue.Queue(maxsize=max(1000, int(queue_size)))
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._client = None
        self._error = ""
        self._connected = False
        self._overflow = False
        self._last_key = None
        self._last_event_ns: Optional[int] = None

    def _db(self):
        if self._db_module is not None:
            return self._db_module
        try:
            import databento as db  # type: ignore
        except Exception as ex:
            raise RuntimeError("Databento SDK is not installed; install ICARUS with .[events]") from ex
        self._db_module = db
        return db

    @property
    def available(self) -> bool:
        if not os.environ.get("DATABENTO_API_KEY") and self._db_module is None:
            return False
        try:
            self._db()
            return True
        except Exception:
            return False

    @property
    def reason(self) -> str:
        if not os.environ.get("DATABENTO_API_KEY") and self._db_module is None:
            return "DATABENTO_API_KEY is required for continuous futures event data"
        return self._error

    def _record_to_event(self, rec) -> Optional[TradeEvent]:
        needed = ("ts_event", "ts_recv", "price", "size", "sequence")
        if not all(hasattr(rec, name) for name in needed):
            return None
        event_ns = int(rec.ts_event)
        received_ns = max(int(rec.ts_recv), event_ns)
        # DBN prices are fixed-point integers at 1e-9 currency units.
        price = Decimal(int(rec.price)) / Decimal(1_000_000_000)
        side = str(getattr(rec, "side", "")).upper()
        aggressor = "sell" if side in ("A", "ASK") else "buy" if side in ("B", "BID") else "unknown"
        return TradeEvent(
            "databento-GLBX.MDP3", self.instrument, int(rec.sequence),
            event_ns, received_ns, _price_ticks(price, self.mintick), float(rec.size), aggressor,
        )

    def _accept(self, event: TradeEvent) -> None:
        key = (event.sequence, event.event_ns, event.price_ticks, event.quantity)
        if key == self._last_key:
            return
        if self._overflow:
            return
        try:
            self._queue.put_nowait(event)
        except queue.Full:
            self._overflow = True
            self._error = "event queue overflow; stream halted rather than dropping trades"
            try:
                if self._client is not None:
                    self._client.terminate()
            except Exception:
                pass
            return
        self._last_key = key
        self._last_event_ns = event.event_ns

    def _callback(self, rec) -> None:
        event = self._record_to_event(rec)
        if event is not None:
            self._accept(event)

    def history(self, start_ns: int, end_ns: int, *, max_events: int = 250000) -> List[TradeEvent]:
        if not self.available:
            raise RuntimeError(self.reason)
        db = self._db()
        client = db.Historical(key=os.environ.get("DATABENTO_API_KEY"))
        data = client.timeseries.get_range(
            dataset=self.DATASET, schema="trades", stype_in="continuous",
            symbols=[self.instrument], start=_iso_ns(start_ns), end=_iso_ns(end_ns),
        )
        out: Deque[TradeEvent] = collections.deque(maxlen=max(1, int(max_events)))
        def collect(rec):
            event = self._record_to_event(rec)
            if event is not None:
                out.append(event)
        data.replay(callback=collect)
        return list(out)

    def _run(self) -> None:
        db = self._db()
        while not self._stop.is_set() and not self._overflow:
            client = None
            try:
                client = db.Live(key=os.environ.get("DATABENTO_API_KEY"))
                self._client = client
                kwargs = {
                    "dataset": self.DATASET,
                    "schema": "trades",
                    "stype_in": "continuous",
                    "symbols": [self.instrument],
                }
                if self._last_event_ns is not None:
                    kwargs["start"] = _iso_ns(self._last_event_ns + 1)
                client.subscribe(**kwargs)
                client.add_callback(self._callback)
                self._connected = True
                self._error = ""
                client.start()
                # Periodic reconnect automatically re-resolves ROOT.v.0 after rolls.
                client.block_for_close(timeout=self.reconnect_sec)
            except Exception as ex:
                self._connected = False
                self._error = f"{type(ex).__name__}: {ex}"
                if self._stop.wait(1.0):
                    break
            finally:
                self._connected = False
                if client is not None:
                    try:
                        client.stop()
                    except Exception:
                        try:
                            client.terminate()
                        except Exception:
                            pass
                self._client = None

    def start(self) -> None:
        if not self.available:
            raise RuntimeError(self.reason)
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name=f"databento-{self.root}")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        client = self._client
        if client is not None:
            try:
                client.stop()
            except Exception:
                try:
                    client.terminate()
                except Exception:
                    pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)

    def drain(self, *, max_events: int = 50000) -> List[TradeEvent]:
        if self._overflow:
            raise RuntimeError(self._error)
        out = []
        for _ in range(max(1, int(max_events))):
            try:
                out.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return out

    def status(self) -> dict:
        return {
            "provider": "databento",
            "dataset": self.DATASET,
            "instrument": self.instrument,
            "continuous": True,
            "roll_rule": "volume",
            "authentic_trade_events": True,
            "connected": self._connected,
            "last_event_ns": self._last_event_ns,
            "queue_depth": self._queue.qsize(),
            "error": self._error or None,
        }


def make_event_feed(spec, mintick: float, *, db_module=None):
    """Return an authentic event adapter for an AssetSpec, or None when unavailable."""
    if getattr(spec, "kind", None) == "futures":
        root = str(spec.ticker[:-2] if str(spec.ticker).endswith("=F") else spec.symbol)
        feed = DatabentoContinuousEvents(root, mintick, db_module=db_module)
        return feed if feed.available else None
    if getattr(spec, "feed", None) == "coinbase":
        return CoinbaseTradeEvents(spec.ticker, mintick)
    return None



def event_bar_to_bar(raw: dict, mintick: float) -> Bar:
    """Convert an authenticated event-aggregator bar to the engine's real OHLCV Bar."""
    for key in ("start_ns", "open_ticks", "high_ticks", "low_ticks", "close_ticks", "volume"):
        if key not in raw:
            raise ValueError(f"event bar missing {key}")
    q = float(mintick)
    return Bar(
        int(raw["start_ns"]) // 1_000_000_000,
        float(raw["open_ticks"]) * q,
        float(raw["high_ticks"]) * q,
        float(raw["low_ticks"]) * q,
        float(raw["close_ticks"]) * q,
        float(raw["volume"]),
    )
