# CL (Claude, Anthropic) — 2026-10-04 — icarus_futures.engine: execution coordinator (risk before venue, recovery, flatten)
"""Flow for every intent: duplicate suppression -> risk governor -> journal -> venue.
Restart rebuilds the book from the journal and never resubmits; any order that was live
at the crash blocks new risk until reconcile() has compared the book with the venue's
authoritative open orders and positions. Modes are explicit identities: SIM and PAPER
run against SimVenue; SHADOW records decisions without a venue; LIVE requires a venue
of kind LIVE AND a separate production-governance record that authorizes it (none
exists, so LIVE construction fails closed)."""
from __future__ import annotations

import json
import inspect
import math
import os
from dataclasses import asdict
from datetime import datetime, timezone

from . import EXECUTION_AUTHORIZED
from .journal import Journal
from .orders import LIVE_STATES, TERMINAL, Intent, OrderBook, S
from .risk import PortfolioState, RiskGovernor

MODES = ("SIM", "PAPER", "SHADOW", "LIVE")


class ExecutionEngine:
    def __init__(self, venue, governor: RiskGovernor, journal: Journal, mode: str = "SIM",
                 governance_path: str = "config/production_governance.json"):
        if mode not in MODES:
            raise ValueError(mode)
        self.live_authorized = False
        if mode == "LIVE":
            gov = {}
            if os.path.exists(governance_path):
                with open(governance_path, encoding="utf-8") as f:
                    gov = json.load(f)
            if venue is None or getattr(venue, "kind", "") != "LIVE" or gov.get("production_authorized") is not True:
                raise PermissionError("LIVE mode requires a LIVE venue and a production-governance authorization")
            self.live_authorized = True
        if mode in ("SIM", "PAPER") and (venue is None or venue.kind not in ("SIM", "PAPER")):
            raise ValueError(f"{mode} mode needs a SIM/PAPER venue")
        self.mode, self.venue, self.gov, self.journal = mode, venue, governor, journal
        self.book = OrderBook()
        self.state = PortfolioState()
        self.vetoes = []
        self.needs_reconcile = False
        self._by_client = {}
        self._recover()

    # ---------- recovery ----------
    def _recover(self):
        recs = self.journal.replay() if os.path.exists(self.journal.path) else []
        for r in recs:
            k, p = r["kind"], r["payload"]
            if k == "intent":
                o, _ = self.book.add(Intent(**p["intent"]))
                if not p["decision"]["allowed"]:
                    o.state = S.REJECTED
            elif k == "sent":
                self.book.on_sent(p["order_id"])
            elif k == "timeout":
                self.book.on_timeout(p["order_id"])
            elif k == "venue_event":
                self._apply(p, journal=False)
            elif k == "reconciled":
                for oid, broker_id in p.get("resolved", {}).items():
                    self.book.on_ack(oid, broker_id)
                for oid in p.get("not_at_venue", []):
                    self.book.orders[oid].state = S.REJECTED
        self.needs_reconcile = any(o.state in LIVE_STATES or o.state == S.AMBIGUOUS for o in self.book.orders.values())

    # ---------- state ----------
    def portfolio(self) -> PortfolioState:
        self.state.positions = dict(self.book.positions)
        self.state.ambiguous_orders = len(self.book.ambiguous()) + (1 if self.needs_reconcile else 0)
        return self.state

    # ---------- intents ----------
    def submit(self, intent: Intent, now: datetime = None) -> dict:
        now = now or datetime.now(timezone.utc)
        o, created = self.book.add(intent)
        if not created:
            return dict(status="DUPLICATE_SUPPRESSED", order_id=o.id, state=o.state.value)
        d = self.gov.evaluate(intent, self.portfolio(), now)
        self.journal.append("intent", dict(intent=asdict(intent), decision=asdict(d), at=now.isoformat()))
        if not d.allowed:
            o.state = S.REJECTED
            o.reject = dict(code="RISK_VETO", reasons=d.codes)
            self.vetoes = (self.vetoes + [dict(at=now.isoformat(), order_id=o.id, codes=d.codes)])[-50:]
            return dict(status="VETOED", order_id=o.id, codes=d.codes, reasons=d.reasons)
        if self.mode == "SHADOW":
            return dict(status="SHADOW_RECORDED", order_id=o.id)
        self.book.on_sent(o.id)
        self.journal.append("sent", dict(order_id=o.id))
        try:
            r = self.venue.submit(o.id, intent.symbol, intent.side, intent.qty, intent.kind, intent.price)
        except (ConnectionError, TimeoutError):
            self.book.on_timeout(o.id)
            self.journal.append("timeout", dict(order_id=o.id))
            return dict(status="AMBIGUOUS", order_id=o.id)
        if r.get("status") == "timeout":
            self.book.on_timeout(o.id)
            self.journal.append("timeout", dict(order_id=o.id))
            return dict(status="AMBIGUOUS", order_id=o.id)
        self.pump()
        return dict(status=self.book.orders[o.id].state.value, order_id=o.id)

    def cancel(self, order_id: str) -> bool:
        o = self.book.orders[order_id]
        if not o.broker_id or not self.book.on_cancel_requested(order_id):
            return False
        cancel = self.venue.cancel
        try:
            parameters = inspect.signature(cancel).parameters.values()
            supports_client_id = any(
                parameter.name == "client_id" or parameter.kind is inspect.Parameter.VAR_KEYWORD
                for parameter in parameters
            )
        except (TypeError, ValueError):
            supports_client_id = False
        if supports_client_id:
            cancel(o.broker_id, client_id=o.id)
        else:
            # Keep adapters written to the original one-argument protocol usable;
            # the broker ID remains the scoped target for those implementations.
            cancel(o.broker_id)
        self.pump()
        return True

    # ---------- venue events ----------
    def pump(self) -> int:
        evs = self.venue.poll() if self.venue else []
        for ev in evs:
            self._apply(ev)
        return len(evs)

    def _apply(self, ev: dict, journal: bool = True):
        oid = ev.get("client_id")
        if oid not in self.book.orders:
            self.book.alarms.append(f"venue event for unknown order {oid}")
            return
        if journal:
            self.journal.append("venue_event", ev)
        t = ev["type"]
        if t == "ack":
            self.book.on_ack(oid, ev["broker_id"])
        elif t == "fill":
            if ev.get("broker_id") and not self.book.orders[oid].broker_id:
                self.book.on_ack(oid, ev["broker_id"])
            self.book.on_fill(oid, ev["fill_id"], int(ev["qty"]), float(ev["price"]))
        elif t == "cancel_ack":
            self.book.on_cancel_ack(oid)
        elif t == "replace_ack":
            self.book.on_replace_ack(oid, float(ev["price"]))
        elif t == "reject":
            self.book.on_reject(oid, ev.get("code", "UNKNOWN"))
        elif t == "expire":
            self.book.on_expire(oid)

    # ---------- reconciliation ----------
    def reconcile(self) -> dict:
        """Authoritative venue truth vs the engine book. Mismatches block new risk."""
        self.pump()
        readback_order = getattr(self.venue, "reconcile_order", None)
        readback_resolved = {}
        if callable(readback_order):
            for order in list(self.book.orders.values()):
                if order.state == S.AMBIGUOUS or (order.state in LIVE_STATES and not order.broker_id):
                    result = readback_order(order.id, order.intent.symbol, order.intent.side,
                                            order.intent.qty, order.intent.kind, order.intent.price)
                    if result.get("status") == "ack" and result.get("broker_id") is not None:
                        readback_resolved[order.id] = str(result["broker_id"])
            # A readback can validate the broker identity and release callbacks
            # that arrived before that identity was trusted. Apply those events
            # before comparing positions or deciding whether ambiguity remains.
            self.pump()
        venue_open = {}
        duplicate_refs = set()
        invalid_snapshot = False
        try:
            open_order_rows = self.venue.open_orders()
        except (OSError, TimeoutError, ValueError, TypeError):
            self.needs_reconcile = True
            rep = dict(resolved={}, not_at_venue=[], mismatched_orders={},
                       incomplete_open_order_snapshot=True,
                       open_order_readback_error="UNAVAILABLE_OR_INVALID",
                       position_mismatch={}, ambiguous=[o.id for o in self.book.ambiguous()])
            self.journal.append("reconciled", rep)
            return rep
        for row in open_order_rows:
            if not isinstance(row, dict):
                invalid_snapshot = True
                continue
            client_id = row.get("client_id")
            if not isinstance(client_id, str) or not client_id:
                invalid_snapshot = True
                continue
            if client_id in venue_open:
                duplicate_refs.add(client_id)
            else:
                venue_open[client_id] = row
        venue_pos = self.venue.positions()
        resolved, not_at_venue, mismatched = dict(readback_resolved), [], {}
        for o in list(self.book.orders.values()):
            if o.state == S.AMBIGUOUS or (o.state in LIVE_STATES and not o.broker_id):
                if o.id in venue_open:
                    venue_order = venue_open[o.id]
                    mismatch = self._reconcile_order_mismatch(o, venue_order)
                    if o.id in duplicate_refs:
                        mismatch.append("duplicate_client_reference")
                    if mismatch:
                        mismatched[o.id] = mismatch
                        continue
                    broker_id = venue_order.get("broker_id")
                    if not broker_id:
                        mismatched[o.id] = ["missing_broker_id"]
                        continue
                    accept_reconciled = getattr(self.venue, "accept_reconciled_order", None)
                    if callable(accept_reconciled):
                        accept_reconciled(o.id, str(broker_id))
                    resolved[o.id] = broker_id
                    self.book.on_ack(o.id, broker_id)
                elif invalid_snapshot:
                    mismatched[o.id] = ["incomplete_open_order_snapshot"]
                elif o.filled == 0 and venue_pos.get(o.intent.symbol, 0) == self.book.positions.get(o.intent.symbol, 0):
                    not_at_venue.append(o.id)
                    o.state = S.REJECTED
                    o.reject = dict(code="NOT_AT_VENUE_AFTER_TIMEOUT")
        book_pos = {k: v for k, v in self.book.positions.items() if v}
        mismatch = {k: dict(engine=book_pos.get(k, 0), venue=venue_pos.get(k, 0))
                    for k in set(book_pos) | set(venue_pos) if book_pos.get(k, 0) != venue_pos.get(k, 0)}
        self.state.broker_mismatch = bool(mismatch)
        self.needs_reconcile = bool(self.book.ambiguous()) or bool(mismatched) or invalid_snapshot
        rep = dict(resolved=resolved, not_at_venue=not_at_venue, mismatched_orders=mismatched,
                   incomplete_open_order_snapshot=invalid_snapshot, position_mismatch=mismatch,
                   ambiguous=[o.id for o in self.book.ambiguous()])
        self.journal.append("reconciled", rep)
        return rep

    @staticmethod
    def _reconcile_order_mismatch(order, venue_order: dict) -> list[str]:
        """Require complete normalized terms before matching an open order to an intent."""
        intent = order.intent
        required = ("symbol", "side", "quantity", "kind", "price", "remaining", "broker_id")
        if any(key not in venue_order for key in required):
            return ["incomplete_order_identity"]
        mismatches = []
        if venue_order["symbol"] != intent.symbol:
            mismatches.append("symbol")
        if str(venue_order["side"]).upper() != intent.side.upper():
            mismatches.append("side")
        if type(venue_order["quantity"]) is not int or venue_order["quantity"] != intent.qty:
            mismatches.append("quantity")
        if str(venue_order["kind"]).upper() != intent.kind.upper():
            mismatches.append("kind")
        if venue_order["remaining"] != order.remaining:
            mismatches.append("remaining")
        expected_price, actual_price = intent.price, venue_order["price"]
        if expected_price is None or actual_price is None:
            if expected_price is not actual_price:
                mismatches.append("price")
        else:
            try:
                if not math.isclose(float(expected_price), float(actual_price), rel_tol=0.0, abs_tol=1e-9):
                    mismatches.append("price")
            except (TypeError, ValueError, OverflowError):
                mismatches.append("price")
        return mismatches

    # ---------- controls ----------
    def pause(self, on: bool = True) -> None:
        self.state.paused = on
        self.journal.append("pause", dict(on=on))

    def flatten_all(self, now: datetime = None) -> list:
        """Cancel working orders, then market out of every position with reduce-only intents."""
        now = now or datetime.now(timezone.utc)
        for o in list(self.book.orders.values()):
            if o.state in (S.WORKING, S.PARTIALLY_FILLED) and o.broker_id:
                self.cancel(o.id)
        out = []
        for sym, q in list(self.book.positions.items()):
            if q:
                it = Intent("FLATTEN", sym, "SELL" if q > 0 else "BUY", abs(q), "MARKET",
                            signal_ts=now.isoformat(), reduce_only=True, tag="flatten")
                out.append(self.submit(it, now))
        return out

    def snapshot(self) -> dict:
        st = self.portfolio()
        by = {}
        for o in self.book.orders.values():
            by[o.state.value] = by.get(o.state.value, 0) + 1
        blocked = st.broker_mismatch or st.ambiguous_orders or st.paused
        return dict(schema="icarus_futures.snapshot/1", mode=self.mode,
                    venue=getattr(self.venue, "name", None), venue_kind=getattr(self.venue, "kind", None),
                    health="BLOCKED" if blocked else ("DEGRADED" if self.book.alarms else "GREEN"),
                    ui_state={"SIM": "PAPER", "PAPER": "PAPER", "SHADOW": "SHADOW", "LIVE": "LIVE"}[self.mode],
                    orders=by, positions={k: v for k, v in st.positions.items() if v},
                    alarms=self.book.alarms[-20:], last_vetoes=self.vetoes[-10:],
                    broker_mismatch=st.broker_mismatch, needs_reconcile=self.needs_reconcile, paused=st.paused,
                    execution_authorized=bool(EXECUTION_AUTHORIZED or self.live_authorized))
