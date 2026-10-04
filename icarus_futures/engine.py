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
        self.venue.cancel(o.broker_id)
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
        venue_open = {o["client_id"]: o for o in self.venue.open_orders()}
        venue_pos = self.venue.positions()
        resolved, not_at_venue = {}, []
        for o in list(self.book.orders.values()):
            if o.state == S.AMBIGUOUS or (o.state in LIVE_STATES and not o.broker_id):
                if o.id in venue_open:
                    resolved[o.id] = venue_open[o.id]["broker_id"]
                    self.book.on_ack(o.id, venue_open[o.id]["broker_id"])
                elif o.filled == 0 and venue_pos.get(o.intent.symbol, 0) == self.book.positions.get(o.intent.symbol, 0):
                    not_at_venue.append(o.id)
                    o.state = S.REJECTED
                    o.reject = dict(code="NOT_AT_VENUE_AFTER_TIMEOUT")
        book_pos = {k: v for k, v in self.book.positions.items() if v}
        mismatch = {k: dict(engine=book_pos.get(k, 0), venue=venue_pos.get(k, 0))
                    for k in set(book_pos) | set(venue_pos) if book_pos.get(k, 0) != venue_pos.get(k, 0)}
        self.state.broker_mismatch = bool(mismatch)
        self.needs_reconcile = bool(self.book.ambiguous())
        rep = dict(resolved=resolved, not_at_venue=not_at_venue, position_mismatch=mismatch,
                   ambiguous=[o.id for o in self.book.ambiguous()])
        self.journal.append("reconciled", rep)
        return rep

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
