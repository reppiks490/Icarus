"""In-memory shadow broker — fills market orders instantly at a price you feed it.

Used for EXECUTION_MODE=shadow (dry-run: everything journaled, nothing sent to
Alpaca) and for the unit tests. Stop/limit orders rest until `tick(price)` crosses them.
Bracket exits use OCO semantics: the first exit fill cancels its sibling.
"""
from __future__ import annotations

import itertools
import time
from typing import Any, Dict, List, Optional

from . import Broker, BrokerOrder, Clock


class ShadowBroker:
    name = "shadow"

    def __init__(self, prices: Optional[Dict[str, float]] = None, market_open: bool = True):
        self.prices: Dict[str, float] = dict(prices or {})
        self._pos: Dict[str, float] = {}
        self._basis: Dict[str, float] = {}     # signed cost basis (qty * avg price) per symbol
        self._orders: Dict[str, BrokerOrder] = {}
        self._oco_siblings: Dict[str, set[str]] = {}
        self._ids = itertools.count(1)
        self.market_open = market_open
        self.fills: List[Dict[str, Any]] = []
        self.cash = 100000.0

    # ── test / dry-run controls ──
    def set_price(self, symbol: str, price: float) -> None:
        self.prices[symbol] = price
        self.tick(symbol)

    def tick(self, symbol: str) -> None:
        """Fill triggered market parents and stop/limit children at the current price."""
        p = self.prices.get(symbol)
        if p is None:
            return
        orders = list(self._orders.values())
        # Fill unpriced bracket parents before their held children. For an
        # already-open OCO group, choose a stop before a limit if one tick
        # crosses multiple conditions; this is conservative and deterministic.
        orders.sort(key=lambda o: (
            0 if o.kind == "bracket" and o.status in ("new", "accepted") else
            1 if o.kind == "stop" else 2
        ))
        for o in orders:
            if o.symbol != symbol or o.status not in ("new", "accepted"):
                continue
            if o.kind == "bracket":
                self._fill(o, p)
                for leg in o.legs:
                    if leg.status == "held":
                        leg.status = "accepted"
                continue
            stop_hit = (o.kind == "stop" and o.stop_price is not None and
                        ((o.side == "sell" and p <= o.stop_price) or (o.side == "buy" and p >= o.stop_price)))
            limit_hit = (o.kind == "limit" and o.limit_price is not None and
                         ((o.side == "buy" and p <= o.limit_price) or (o.side == "sell" and p >= o.limit_price)))
            if stop_hit or limit_hit:
                self._fill(o, p if stop_hit else o.limit_price)

    def _cancel_oco_siblings(self, order_id: str) -> None:
        for sibling_id in self._oco_siblings.get(order_id, set()):
            sibling = self._orders.get(sibling_id)
            if sibling and sibling.status in ("new", "accepted"):
                sibling.status = "canceled"
        self._oco_siblings.pop(order_id, None)
        for sibling_id in list(self._oco_siblings):
            self._oco_siblings[sibling_id].discard(order_id)
            if not self._oco_siblings[sibling_id]:
                self._oco_siblings.pop(sibling_id, None)

    def _fill(self, o: BrokerOrder, price: float) -> None:
        if o.status not in ("new", "accepted"):
            return
        o.status = "filled"
        o.filled_qty = o.qty
        o.fill_price = price
        signed = o.qty if o.side == "buy" else -o.qty
        prev = self._pos.get(o.symbol, 0.0)
        new = prev + signed
        # average-entry bookkeeping: adding to a position averages in; reducing keeps the average; flipping restarts it
        if prev == 0 or (prev > 0) != (new > 0):
            self._basis[o.symbol] = new * price
        elif abs(new) > abs(prev):
            self._basis[o.symbol] = self._basis.get(o.symbol, 0.0) + signed * price
        else:
            avg = self._basis.get(o.symbol, 0.0) / prev if prev else price
            self._basis[o.symbol] = new * avg
        self._pos[o.symbol] = new
        self.cash -= signed * price
        self.fills.append({"id": o.id, "symbol": o.symbol, "side": o.side, "qty": o.qty, "price": price, "ts": time.time()})
        if abs(self._pos[o.symbol]) < 1e-9:
            self._pos.pop(o.symbol, None)
            self._basis.pop(o.symbol, None)
        self._cancel_oco_siblings(o.id)

    # ── Broker protocol ──
    def account(self) -> Dict[str, Any]:
        equity = self.cash + sum(q * self.prices.get(s, 0.0) for s, q in self._pos.items())
        return {"equity": equity, "cash": self.cash, "buying_power": self.cash * 2, "status": "SHADOW"}

    def clock(self) -> Clock:
        return Clock(is_open=self.market_open)

    def latest_price(self, symbol: str) -> Optional[float]:
        return self.prices.get(symbol)

    def position(self, symbol: str) -> float:
        return self._pos.get(symbol, 0.0)

    def positions(self) -> List[Dict[str, Any]]:
        out = []
        for s, q in self._pos.items():
            px = self.prices.get(s, 0.0)
            avg = (self._basis.get(s, 0.0) / q) if q else None
            out.append({"symbol": s, "qty": q, "avg_entry_price": avg, "market_value": q * px,
                        "unrealized_pl": (q * (px - avg)) if avg else None, "current_price": px})
        return out

    def open_orders(self, symbol: Optional[str] = None) -> List[BrokerOrder]:
        return [o for o in self._orders.values() if o.status in ("new", "accepted") and (symbol is None or o.symbol == symbol)]

    def cancel_orders(self, symbol: Optional[str] = None) -> int:
        n = 0
        for o in self.open_orders(symbol):
            o.status = "canceled"; n += 1
        return n

    def cancel_order(self, order_id: str) -> bool:
        o = self._orders.get(order_id)
        if o and o.status in ("new", "accepted"):
            o.status = "canceled"; return True
        return False

    def _new(self, symbol: str, side: str, qty: float, kind: str, **kw: Any) -> BrokerOrder:
        o = BrokerOrder(id=f"sh-{next(self._ids)}", symbol=symbol, side=side, qty=float(qty), kind=kind, status="accepted", **kw)
        self._orders[o.id] = o
        return o

    def submit_market(self, symbol: str, side: str, qty: float, *, extended: bool = False) -> BrokerOrder:
        o = self._new(symbol, side, qty, "market")
        p = self.prices.get(symbol)
        if p is not None:
            self._fill(o, p)
        return o

    def submit_stop(self, symbol: str, side: str, qty: float, stop_price: float) -> BrokerOrder:
        o = self._new(symbol, side, qty, "stop", stop_price=stop_price)
        self.tick(symbol)
        return o

    def submit_bracket(self, symbol: str, side: str, qty: float, take_profit: float, stop_loss: float) -> BrokerOrder:
        o = self._new(symbol, side, qty, "bracket")
        p = self.prices.get(symbol)
        exit_side = "sell" if side == "buy" else "buy"
        tp = self._new(symbol, exit_side, qty, "limit", limit_price=take_profit)
        sl = self._new(symbol, exit_side, qty, "stop", stop_price=stop_loss)
        o.legs = [tp, sl]
        self._oco_siblings[tp.id] = {sl.id}
        self._oco_siblings[sl.id] = {tp.id}
        if p is not None:
            self._fill(o, p)
            self.tick(symbol)
        else:
            tp.status = sl.status = "held"
        return o

    def replace_stop(self, order_id: str, stop_price: float) -> BrokerOrder:
        o = self._orders[order_id]
        o.stop_price = stop_price
        self.tick(o.symbol)
        return o

    def close_position(self, symbol: str) -> Optional[BrokerOrder]:
        q = self._pos.get(symbol, 0.0)
        if abs(q) < 1e-9:
            return None
        self.cancel_orders(symbol)
        return self.submit_market(symbol, "sell" if q > 0 else "buy", abs(q))

    def wait_filled(self, order_id: str, timeout: float = 10.0) -> BrokerOrder:
        return self._orders[order_id]

    def recent_fills(self, limit: int = 50) -> List[Dict[str, Any]]:
        return self.fills[-limit:]
