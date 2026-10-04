# CL (Claude, Anthropic) — 2026-10-04 — icarus_futures.orders: deterministic intents and the futures order state machine
"""Order lifecycle with explicit, tested race handling.

States: PENDING_SUBMIT -> SUBMITTED -> WORKING -> PARTIALLY_FILLED -> FILLED, with
PENDING_CANCEL / PENDING_REPLACE side states and terminal FILLED, CANCELLED, REJECTED,
EXPIRED. AMBIGUOUS means the engine cannot know the venue's truth (timeout without
ack, impossible fill, lost connection mid-submit); it blocks new risk until
reconciliation with the venue resolves it. Rules that matter:

* the client intent id is a deterministic hash of the intent, so a retried or duplicated
  request maps to the same order and is never sent twice;
* fills are keyed by fill id: a duplicate fill report is ignored;
* a fill that arrives while a cancel or replace is pending is applied; a late cancel ack
  for a filled order is ignored; overfills are impossible and make the order AMBIGUOUS;
* an OCO sibling is cancelled when the other leg fills."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Optional


class S(str, Enum):
    PENDING_SUBMIT = "PENDING_SUBMIT"
    SUBMITTED = "SUBMITTED"
    WORKING = "WORKING"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    PENDING_CANCEL = "PENDING_CANCEL"
    PENDING_REPLACE = "PENDING_REPLACE"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    AMBIGUOUS = "AMBIGUOUS"


TERMINAL = {S.FILLED, S.CANCELLED, S.REJECTED, S.EXPIRED}
LIVE_STATES = {S.SUBMITTED, S.WORKING, S.PARTIALLY_FILLED, S.PENDING_CANCEL, S.PENDING_REPLACE}

REJECT_TAXONOMY = {
    "INSUFFICIENT_MARGIN": False, "PRICE_OUT_OF_BAND": False, "MARKET_CLOSED": False,
    "INVALID_ORDER": False, "POSITION_LIMIT": False, "RATE_LIMIT": True, "VENUE_BUSY": True, "UNKNOWN": False,
}


def classify_reject(code: str) -> dict:
    c = code if code in REJECT_TAXONOMY else "UNKNOWN"
    return dict(code=c, retryable=REJECT_TAXONOMY[c], raw=code)


@dataclass(frozen=True)
class Intent:
    strategy: str
    symbol: str          # dated contract code (resolved from a continuous identity)
    side: str            # BUY | SELL
    qty: int
    kind: str            # MARKET | LIMIT | STOP
    price: Optional[float] = None
    signal_ts: str = ""  # decision timestamp (UTC ISO) — part of the identity
    reduce_only: bool = False
    oco_group: Optional[str] = None
    tag: str = ""

    @property
    def intent_id(self) -> str:
        blob = json.dumps(asdict(self), sort_keys=True)
        return "ci-" + hashlib.sha256(blob.encode()).hexdigest()[:20]

    @property
    def signed_qty(self) -> int:
        return self.qty if self.side == "BUY" else -self.qty


@dataclass
class Order:
    intent: Intent
    state: S = S.PENDING_SUBMIT
    broker_id: Optional[str] = None
    filled: int = 0
    avg_price: Optional[float] = None
    working_price: Optional[float] = None
    fill_ids: set = field(default_factory=set)
    reject: Optional[dict] = None
    history: list = field(default_factory=list)

    @property
    def id(self) -> str:
        return self.intent.intent_id

    @property
    def remaining(self) -> int:
        return self.intent.qty - self.filled

    def _to(self, new: S, why: str) -> None:
        self.history.append((self.state.value, new.value, why))
        self.state = new


class OrderBook:
    """All orders keyed by deterministic intent id, plus signed positions per contract."""

    def __init__(self):
        self.orders: dict[str, Order] = {}
        self.positions: dict[str, int] = {}
        self.alarms: list[str] = []

    # ---- intents ----
    def add(self, intent: Intent) -> tuple[Order, bool]:
        """Returns (order, created). A duplicate intent returns the existing order, created=False."""
        oid = intent.intent_id
        if oid in self.orders:
            return self.orders[oid], False
        o = Order(intent, working_price=intent.price)
        self.orders[oid] = o
        return o, True

    def by_broker(self, broker_id: str) -> Optional[Order]:
        return next((o for o in self.orders.values() if o.broker_id == broker_id), None)

    def live(self):
        return [o for o in self.orders.values() if o.state in LIVE_STATES or o.state == S.PENDING_SUBMIT]

    def ambiguous(self):
        return [o for o in self.orders.values() if o.state == S.AMBIGUOUS]

    # ---- venue events ----
    def on_sent(self, oid: str) -> None:
        o = self.orders[oid]
        if o.state == S.PENDING_SUBMIT:
            o._to(S.SUBMITTED, "sent")

    def on_ack(self, oid: str, broker_id: str) -> None:
        o = self.orders[oid]
        if o.broker_id and o.broker_id != broker_id:
            o._to(S.AMBIGUOUS, f"second broker id {broker_id} for {o.broker_id}")
            self.alarms.append(f"{oid}: conflicting broker ids")
            return
        o.broker_id = broker_id
        if o.state in (S.PENDING_SUBMIT, S.SUBMITTED, S.AMBIGUOUS):
            o._to(S.WORKING, "ack")

    def on_timeout(self, oid: str) -> None:
        o = self.orders[oid]
        if o.state in (S.PENDING_SUBMIT, S.SUBMITTED):
            o._to(S.AMBIGUOUS, "submit timeout without ack")

    def on_fill(self, oid: str, fill_id: str, qty: int, price: float) -> None:
        o = self.orders[oid]
        if fill_id in o.fill_ids:
            return  # duplicate report
        if qty <= 0 or qty > o.remaining:
            o._to(S.AMBIGUOUS, f"impossible fill {qty} with {o.remaining} remaining")
            self.alarms.append(f"{oid}: impossible fill {fill_id}")
            return
        o.fill_ids.add(fill_id)
        o.avg_price = price if not o.filled else (o.avg_price * o.filled + price * qty) / (o.filled + qty)
        o.filled += qty
        sym = o.intent.symbol
        self.positions[sym] = self.positions.get(sym, 0) + (qty if o.intent.side == "BUY" else -qty)
        if o.remaining == 0:
            o._to(S.FILLED, f"fill {fill_id}")
            self._oco_cancel(o)
        elif o.state not in (S.PENDING_CANCEL, S.PENDING_REPLACE):
            o._to(S.PARTIALLY_FILLED, f"fill {fill_id}")

    def on_cancel_requested(self, oid: str) -> bool:
        o = self.orders[oid]
        if o.state in TERMINAL or o.state == S.AMBIGUOUS:
            return False
        o._to(S.PENDING_CANCEL, "cancel requested")
        return True

    def on_cancel_ack(self, oid: str) -> None:
        o = self.orders[oid]
        if o.state in TERMINAL:
            return  # e.g. filled while the cancel was in flight
        o._to(S.CANCELLED, "cancel ack")

    def on_replace_requested(self, oid: str) -> bool:
        o = self.orders[oid]
        if o.state not in (S.WORKING, S.PARTIALLY_FILLED):
            return False
        o._to(S.PENDING_REPLACE, "replace requested")
        return True

    def on_replace_ack(self, oid: str, new_price: float) -> None:
        o = self.orders[oid]
        if o.state in TERMINAL:
            return
        o.working_price = new_price
        o._to(S.PARTIALLY_FILLED if o.filled else S.WORKING, "replace ack")

    def on_reject(self, oid: str, code: str) -> None:
        o = self.orders[oid]
        if o.state in TERMINAL:
            return
        o.reject = classify_reject(code)
        o._to(S.REJECTED, f"reject {o.reject['code']}")

    def on_expire(self, oid: str) -> None:
        o = self.orders[oid]
        if o.state not in TERMINAL:
            o._to(S.EXPIRED, "expired")

    def _oco_cancel(self, filled: Order) -> None:
        g = filled.intent.oco_group
        if not g:
            return
        for o in self.orders.values():
            if o is not filled and o.intent.oco_group == g and o.state not in TERMINAL:
                if o.filled:
                    self.alarms.append(f"OCO group {g}: both legs filled")
                    o._to(S.AMBIGUOUS, "OCO sibling also filled")
                else:
                    self.on_cancel_requested(o.id)
