"""Phase 20: fail-closed OFFLINE order-lifecycle reconciliation harness.

No broker imports, sockets, credentials, account access or external side
effects. All "orders" are typed messages in a local sequence supplied by an
operator, never transmitted. It models message ordering and permissions,
not exchange matching, real fills, account equity or order profitability.
"""
from __future__ import annotations

import re
from typing import Any, Mapping
from .contracts import canonical_bytes, identity, utc

_AUTHORITY = {"research_only": True, "execution_authorized": False,
              "production_decision_authorized": False, "auto_promote": False}
_SCHEMA = "icarus-omnigenesis-offline-order-router-v1"
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")
_ASSET = re.compile(r"^[A-Z0-9._-]{1,24}$")
_FIELDS = {
    "SUBMIT": {"order_id", "side", "quantity", "limit_ticks"},
    "ACK": {"order_id"},
    "FILL": {"order_id", "execution_id", "quantity", "price_ticks"},
    "CANCEL": {"order_id"},
    "CANCEL_ACK": {"order_id"},
    "REJECT": {"order_id"},
    "HALT": {"reason"},
    "RECONCILE": {"position_contracts"},
}
_COMMON = {"event_id", "sequence", "received_at", "action"}
_WORKING = {"PENDING_ACK", "OPEN", "CANCEL_PENDING"}


def _int(v: Any, name: str, lo: int, hi: int) -> int:
    if type(v) is not int or not lo <= v <= hi:
        raise ValueError(f"invalid {name}")
    return v


def _ident(v: Any, name: str) -> str:
    if not isinstance(v, str) or not _ID.fullmatch(v):
        raise ValueError(f"invalid {name}")
    return v


def _working(order: dict) -> bool:
    return order["remaining"] > 0 and order["status"] in _WORKING


def replay_offline_order_router(spec: Mapping[str, Any]) -> dict:
    """Replay strict typed messages with a local, idempotent state machine.

    Event-ID deduplication applies to identical bytes *within this replay*;
    it is not persistent across processes or evidence of exactly-once
    exchange orders. Unique events require increasing sequence and clocks.
    """
    if not isinstance(spec, Mapping) or set(spec) != {
            "schema_version", "mode", "asset", "max_position_contracts",
            "max_single_order_contracts", "max_active_orders", "events"}:
        raise ValueError("invalid offline router schema")
    if spec["schema_version"] != _SCHEMA or spec["mode"] != "OFFLINE_SANDBOX":
        raise ValueError("offline sandbox is the only router mode")
    asset = spec["asset"]
    if not isinstance(asset, str) or not _ASSET.fullmatch(asset):
        raise ValueError("invalid asset")
    max_position = _int(spec["max_position_contracts"], "max position", 1, 100)
    max_single = _int(spec["max_single_order_contracts"], "max single order", 1, 50)
    max_active = _int(spec["max_active_orders"], "max active orders", 1, 100)
    raw = spec["events"]
    if not isinstance(raw, list) or not 1 <= len(raw) <= 2000:
        raise ValueError("invalid event count")
    if len(canonical_bytes(spec)) > 1_500_000:
        raise ValueError("offline event bytes exceed cap")
    order_map: dict[str, dict] = {}
    seen: dict[str, bytes] = {}
    seen_exec: set[str] = set()
    audit = []
    duplicate_deliveries = 0
    position = 0
    prior_received = None
    previous_seq = 0
    last_receipt = "0" * 64
    halted = False
    halt_reason = None
    reconciliation_failed = False
    accepted_submits = 0
    fill_events = 0
    canceled_orders = 0
    total_filled_contracts = 0

    for event in raw:
        if not isinstance(event, Mapping):
            raise ValueError("event must be a typed object")
        action = event.get("action")
        if not isinstance(action, str) or action not in _FIELDS:
            raise ValueError("unapproved offline router action")
        if set(event) != _COMMON | _FIELDS[action]:
            raise ValueError("unexpected offline event fields")
        eid = _ident(event["event_id"], "event ID")
        encoded = canonical_bytes(event)
        if eid in seen:
            if seen[eid] != encoded:
                raise ValueError("conflicting duplicate event ID")
            duplicate_deliveries += 1
            continue
        seq = _int(event["sequence"], "sequence", 1, 10_000_000)
        received = utc(event["received_at"])
        if seq <= previous_seq or (prior_received is not None and received <= prior_received):
            raise ValueError("non-increasing event sequence or receive time")
        previous_seq, prior_received = seq, received
        # Unique event IDs are accepted only after all safety checks succeed.
        oid = event.get("order_id")
        if oid is not None:
            oid = _ident(oid, "order ID")
        if action == "SUBMIT":
            if halted:
                raise ValueError("submit forbidden after safety halt")
            if oid in order_map:
                raise ValueError("duplicate client order ID")
            side = event["side"]
            if side not in ("BUY", "SELL"):
                raise ValueError("invalid order side")
            qty = _int(event["quantity"], "order quantity", 1, max_single)
            price = _int(event["limit_ticks"], "limit ticks", 1, 1_000_000_000)
            working = [o for o in order_map.values() if _working(o)]
            if len(working) >= max_active:
                raise ValueError("active order budget exhausted")
            # Worst-case fill of ALL outstanding same-side orders: opposing
            # intentions cannot net one another until the exchange confirms.
            pending_buys = sum(o["remaining"] for o in working if o["side"] == "BUY")
            pending_sells = sum(o["remaining"] for o in working if o["side"] == "SELL")
            if side == "BUY":
                pending_buys += qty
            else:
                pending_sells += qty
            if position + pending_buys > max_position or position - pending_sells < -max_position:
                raise ValueError("worst-case outstanding exposure exceeds position limit")
            order_map[oid] = {"side": side, "quantity": qty, "remaining": qty,
                              "limit_ticks": price, "status": "PENDING_ACK",
                              "ack_seen": False, "filled_contracts": 0}
            accepted_submits += 1
        elif action == "HALT":
            why = event["reason"]
            if not isinstance(why, str) or not 1 <= len(why) <= 96:
                raise ValueError("invalid safety halt reason")
            halted = True
            halt_reason = halt_reason or why
        elif action == "RECONCILE":
            snapshot = _int(event["position_contracts"], "reported position",
                            -100_000, 100_000)
            if snapshot != position:
                halted, reconciliation_failed = True, True
                halt_reason = halt_reason or "RECONCILIATION_MISMATCH"
        else:
            order = order_map.get(oid)
            if order is None:
                raise ValueError("event references unknown client order")
            status = order["status"]
            if action == "ACK":
                # An asynchronous fill/cancel request may race ahead of ACK;
                # a late ACK never resurrects a completed order.
                if order["ack_seen"] or status == "REJECTED":
                    raise ValueError("duplicate or invalid order ACK")
                order["ack_seen"] = True
                if status == "PENDING_ACK":
                    order["status"] = "OPEN"
            elif action == "FILL":
                if status not in _WORKING:
                    raise ValueError("fill after terminal order state")
                exec_id = _ident(event["execution_id"], "execution ID")
                if exec_id in seen_exec:
                    raise ValueError("duplicate execution ID")
                qty = _int(event["quantity"], "fill quantity", 1, max_single)
                _int(event["price_ticks"], "fill price ticks", 1, 1_000_000_000)
                if qty > order["remaining"]:
                    raise ValueError("execution overfills original order")
                new_pos = position + qty * (1 if order["side"] == "BUY" else -1)
                if abs(new_pos) > max_position:
                    raise ValueError("fill violates absolute position limit")
                position = new_pos
                order["remaining"] -= qty
                order["filled_contracts"] += qty
                if order["remaining"] == 0:
                    order["status"] = "FILLED"
                seen_exec.add(exec_id)
                fill_events += 1
                total_filled_contracts += qty
            elif action == "CANCEL":
                if status not in ("OPEN", "PENDING_ACK"):
                    raise ValueError("cannot cancel terminal or pending-cancel order")
                order["status"] = "CANCEL_PENDING"
            elif action == "CANCEL_ACK":
                if status != "CANCEL_PENDING":
                    raise ValueError("cancel confirmation requires pending cancellation")
                order["status"] = "CANCELED"
                canceled_orders += 1
            elif action == "REJECT":
                if status != "PENDING_ACK" or order["filled_contracts"]:
                    raise ValueError("cannot reject acknowledged or filled order")
                order["status"] = "REJECTED"
        seen[eid] = encoded
        node = {"sequence": seq, "event_id": eid, "action": action,
                "order_id": oid, "position_contracts": position,
                "halted": halted, "previous_receipt": last_receipt,
                "research_only": True, "execution_authorized": False}
        node["receipt_id"] = identity(node)
        last_receipt = node["receipt_id"]
        audit.append(node)

    open_ids = sorted(oid for oid, order in order_map.items() if _working(order))
    report = {
        "schema_version": _SCHEMA,
        "mode": "OFFLINE_SANDBOX", "asset": asset,
        "evidence_kind": "SIMULATED_ORDER_LIFECYCLE",
        "authority": dict(_AUTHORITY),
        "source_authenticity_verified": False, "actual_exchange_reconciled": False,
        "profitability_verified": False, "broker_order_count": 0,
        "message_count": len(audit), "duplicate_delivery_count": duplicate_deliveries,
        "accepted_mock_submits": accepted_submits,
        "acknowledged_execution_events": fill_events,
        "mock_filled_contracts": total_filled_contracts,
        "canceled_mock_orders": canceled_orders,
        "position_contracts": position,
        "halted": halted, "halt_reason": halt_reason,
        "reconciliation_failed": reconciliation_failed,
        "outstanding_order_ids": open_ids,
        "must_cancel_and_reconcile_externally": halted and bool(open_ids),
        "orders": {oid: {"status": o["status"], "side": o["side"],
                          "remaining": o["remaining"],
                          "filled_contracts": o["filled_contracts"],
                          "ack_seen": o["ack_seen"]} for oid, o in sorted(order_map.items())},
        "audit_receipts": audit,
        "audit_final_receipt": last_receipt,
        "idempotency_scope": "THIS_REPLAY_ONLY",
        "broker_adapters_available": False,
    }
    report["receipt_id"] = identity(report)
    return report
