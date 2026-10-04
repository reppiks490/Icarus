# CL (Claude, Anthropic) — 2026-10-04 — icarus_futures.venue: venue adapter protocol and a deterministic simulated venue
"""A venue adapter is whatever talks to a real broker/exchange gateway. None ships here
until the owner chooses a futures broker. SimVenue is a deterministic paper/sim venue
with fault injection used for paper trading and for the chaos tests: lost acks,
duplicate fills, rejects, partial fills, fills racing cancels, and disconnects."""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Optional, Protocol


class VenueAdapter(Protocol):
    name: str
    kind: str  # "SIM" | "PAPER" | "LIVE"

    def submit(self, order_id: str, symbol: str, side: str, qty: int, kind: str, price: Optional[float]) -> dict: ...
    def cancel(self, broker_id: str) -> dict: ...
    def replace(self, broker_id: str, new_price: float) -> dict: ...
    def open_orders(self) -> list: ...
    def positions(self) -> dict: ...
    def poll(self) -> list: ...


@dataclass
class _SimOrder:
    broker_id: str
    client_id: str
    symbol: str
    side: str
    qty: int
    kind: str
    price: Optional[float]
    filled: int = 0
    active: bool = True


@dataclass
class SimVenue:
    """Deterministic venue. ``faults`` maps a fault name to how many times it fires:
    drop_ack, duplicate_fill, reject:<CODE>, partial_fill, disconnect."""
    name: str = "sim"
    kind: str = "SIM"
    slippage_ticks: int = 1
    tick: float = 0.25
    faults: dict = field(default_factory=dict)
    last: dict = field(default_factory=dict)       # symbol -> last price
    _orders: dict = field(default_factory=dict)
    _pos: dict = field(default_factory=dict)
    _events: list = field(default_factory=list)
    _ids: itertools.count = field(default_factory=lambda: itertools.count(1))
    _fills: itertools.count = field(default_factory=lambda: itertools.count(1))
    connected: bool = True

    def _fault(self, name: str) -> bool:
        n = self.faults.get(name, 0)
        if n:
            self.faults[name] = n - 1
            return True
        return False

    def _check(self):
        if not self.connected or self._fault("disconnect"):
            self.connected = False
            raise ConnectionError("venue disconnected")

    def submit(self, order_id, symbol, side, qty, kind, price):
        self._check()
        for code in [k.split(":", 1)[1] for k in list(self.faults) if k.startswith("reject:")]:
            if self._fault(f"reject:{code}"):
                self._events.append(dict(type="reject", client_id=order_id, code=code))
                return dict(status="rejected", code=code)
        bid = f"S{next(self._ids)}"
        self._orders[bid] = _SimOrder(bid, order_id, symbol, side, qty, kind, price)
        if self._fault("drop_ack"):
            return dict(status="timeout")      # accepted at the venue, ack lost on the wire
        self._events.append(dict(type="ack", client_id=order_id, broker_id=bid))
        return dict(status="ack", broker_id=bid)

    def cancel(self, broker_id):
        self._check()
        o = self._orders.get(broker_id)
        if o and o.active:
            o.active = False
            self._events.append(dict(type="cancel_ack", client_id=o.client_id, broker_id=broker_id))
        return dict(status="ok")

    def replace(self, broker_id, new_price):
        self._check()
        o = self._orders.get(broker_id)
        if o and o.active:
            o.price = new_price
            self._events.append(dict(type="replace_ack", client_id=o.client_id, price=new_price))
        return dict(status="ok")

    def mark(self, symbol: str, price: float) -> None:
        """Move the market; working orders that the price reaches fill (market orders fill now)."""
        self.last[symbol] = price
        for o in list(self._orders.values()):
            if not o.active or o.symbol != symbol:
                continue
            hit = (o.kind == "MARKET" or
                   (o.kind == "LIMIT" and ((o.side == "BUY" and price <= o.price) or (o.side == "SELL" and price >= o.price))) or
                   (o.kind == "STOP" and ((o.side == "BUY" and price >= o.price) or (o.side == "SELL" and price <= o.price))))
            if not hit:
                continue
            slip = self.slippage_ticks * self.tick * (1 if o.side == "BUY" else -1)
            px = price + slip if o.kind in ("MARKET", "STOP") else o.price
            qty = o.qty - o.filled
            if self._fault("partial_fill") and qty > 1:
                qty //= 2
            fid = f"F{next(self._fills)}"
            o.filled += qty
            self._pos[symbol] = self._pos.get(symbol, 0) + (qty if o.side == "BUY" else -qty)
            ev = dict(type="fill", client_id=o.client_id, broker_id=o.broker_id, fill_id=fid, qty=qty, price=px)
            self._events.append(ev)
            if self._fault("duplicate_fill"):
                self._events.append(dict(ev))
            if o.filled >= o.qty:
                o.active = False

    def open_orders(self):
        return [dict(broker_id=o.broker_id, client_id=o.client_id, symbol=o.symbol, side=o.side,
                     remaining=o.qty - o.filled, price=o.price) for o in self._orders.values() if o.active]

    def positions(self):
        return {k: v for k, v in self._pos.items() if v}

    def poll(self):
        ev, self._events = self._events, []
        return ev
