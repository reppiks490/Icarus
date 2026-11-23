"""Phase 20 local-only mock order-router adversarial tests."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import pytest

from icarus_engine.omnigenesis.contracts import identity
from icarus_engine.omnigenesis.offline_order_router import replay_offline_order_router


def event(n, action, **payload):
    return {"event_id": f"evt_{n}", "sequence": n,
            "received_at": (datetime(2026, 1, 1, tzinfo=timezone.utc)
                            + timedelta(milliseconds=n)).isoformat(),
            "action": action, **payload}


def submit(n, oid, side, qty):
    return event(n, "SUBMIT", order_id=oid, side=side,
                 quantity=qty, limit_ticks=10000)


def config(events):
    return {"schema_version": "icarus-omnigenesis-offline-order-router-v1",
            "mode": "OFFLINE_SANDBOX", "asset": "NQ",
            "max_position_contracts": 5,
            "max_single_order_contracts": 5, "max_active_orders": 6,
            "events": events}


def test_partial_fill_cancel_race_and_late_ack_are_expressly_modelled():
    original = config([
        submit(1, "o1", "BUY", 5),
        event(2, "FILL", order_id="o1", execution_id="x1",
              quantity=2, price_ticks=10000),  # can precede ACK
        event(3, "ACK", order_id="o1"),
        event(4, "CANCEL", order_id="o1"),
        event(5, "FILL", order_id="o1", execution_id="x2",
              quantity=1, price_ticks=10001),  # can race cancel
        event(6, "CANCEL_ACK", order_id="o1"),
        event(7, "RECONCILE", position_contracts=3),
    ])
    x = replay_offline_order_router(original)
    assert x == replay_offline_order_router(original)
    assert x["receipt_id"] == identity({k: v for k, v in x.items()
                                        if k != "receipt_id"})
    assert x["broker_order_count"] == 0
    assert x["mode"] == "OFFLINE_SANDBOX"
    assert x["evidence_kind"] == "SIMULATED_ORDER_LIFECYCLE"
    assert x["actual_exchange_reconciled"] is False
    assert x["source_authenticity_verified"] is False
    assert x["profitability_verified"] is False
    assert x["authority"]["execution_authorized"] is False
    assert x["accepted_mock_submits"] == 1
    assert x["mock_filled_contracts"] == 3
    assert x["acknowledged_execution_events"] == 2
    assert x["canceled_mock_orders"] == 1
    assert x["position_contracts"] == 3
    assert x["orders"]["o1"]["status"] == "CANCELED"
    assert x["orders"]["o1"]["remaining"] == 2
    assert x["orders"]["o1"]["ack_seen"] is True
    assert x["outstanding_order_ids"] == []
    assert x["halted"] is False
    assert x["audit_final_receipt"] == x["audit_receipts"][-1]["receipt_id"]


def test_duplicate_delivery_same_bytes_is_idempotent_in_this_replay_only():
    submit_1 = submit(1, "o1", "BUY", 2)
    fill = event(2, "FILL", order_id="o1", execution_id="x1",
                 quantity=2, price_ticks=10000)
    spec = config([submit_1, fill, deepcopy(submit_1), deepcopy(fill)])
    r = replay_offline_order_router(spec)
    assert r["message_count"] == 2
    assert r["duplicate_delivery_count"] == 2
    assert r["mock_filled_contracts"] == 2
    assert r["position_contracts"] == 2
    assert r["orders"]["o1"]["status"] == "FILLED"
    assert r["idempotency_scope"] == "THIS_REPLAY_ONLY"


def test_duplicate_event_id_conflict_refused_before_state_mutation():
    a = submit(1, "o1", "BUY", 2)
    b = deepcopy(a)
    b["quantity"] = 3
    with pytest.raises(ValueError, match="conflicting duplicate event"):
        replay_offline_order_router(config([a, b]))


def test_late_ack_after_full_fill_does_not_resurrect_order():
    events = [submit(1, "o1", "SELL", 3),
              event(2, "FILL", order_id="o1", execution_id="x1",
                    quantity=3, price_ticks=10000),
              event(3, "ACK", order_id="o1")]
    r = replay_offline_order_router(config(events))
    assert r["orders"]["o1"]["status"] == "FILLED"
    assert r["orders"]["o1"]["ack_seen"] is True
    assert r["position_contracts"] == -3
    assert r["outstanding_order_ids"] == []


def test_kill_switch_blocks_new_orders_and_requires_external_cancel():
    s = config([submit(1, "o1", "BUY", 2),
                event(2, "ACK", order_id="o1"),
                event(3, "HALT", reason="MANUAL_RISK_HALT")])
    r = replay_offline_order_router(s)
    assert r["halted"] is True
    assert r["halt_reason"] == "MANUAL_RISK_HALT"
    assert r["outstanding_order_ids"] == ["o1"]
    assert r["must_cancel_and_reconcile_externally"] is True
    assert r["broker_adapters_available"] is False
    s["events"].append(submit(4, "o2", "SELL", 1))
    with pytest.raises(ValueError, match="submit forbidden"):
        replay_offline_order_router(s)


def test_halt_allows_subsequent_late_fills_but_no_new_exposure_requests():
    s = config([submit(1, "o1", "BUY", 2),
                event(2, "ACK", order_id="o1"),
                event(3, "HALT", reason="SYSTEM_ALARM"),
                event(4, "FILL", order_id="o1", execution_id="x1",
                      quantity=1, price_ticks=10000),
                event(5, "CANCEL", order_id="o1"),
                event(6, "CANCEL_ACK", order_id="o1")])
    r = replay_offline_order_router(s)
    assert r["position_contracts"] == 1
    assert r["halted"] is True
    assert r["outstanding_order_ids"] == []
    assert r["must_cancel_and_reconcile_externally"] is False


def test_mismatched_position_snapshot_halts_and_discloses_disagreement():
    s = config([submit(1, "o1", "BUY", 1),
                event(2, "ACK", order_id="o1"),
                event(3, "FILL", order_id="o1", execution_id="f1",
                      quantity=1, price_ticks=10004),
                event(4, "RECONCILE", position_contracts=0)])
    r = replay_offline_order_router(s)
    assert r["position_contracts"] == 1
    assert r["reconciliation_failed"] is True
    assert r["halted"] is True
    assert r["halt_reason"] == "RECONCILIATION_MISMATCH"
    assert r["actual_exchange_reconciled"] is False


def test_worst_case_in_flight_exposure_checks_both_sides_independently():
    events = [submit(1, "o1", "BUY", 5), submit(2, "o2", "SELL", 5)]
    assert replay_offline_order_router(config(events))["accepted_mock_submits"] == 2
    with pytest.raises(ValueError, match="worst-case outstanding exposure"):
        replay_offline_order_router(config(events + [submit(3, "o3", "BUY", 1)]))
    with pytest.raises(ValueError, match="worst-case outstanding exposure"):
        replay_offline_order_router(config(events + [submit(3, "o3", "SELL", 1)]))


def test_limit_of_active_orders_enforced_even_when_each_position_safe():
    spec = config([submit(1, "o1", "BUY", 1), submit(2, "o2", "SELL", 1)])
    spec["max_active_orders"] = 1
    with pytest.raises(ValueError, match="active order budget"):
        replay_offline_order_router(spec)


@pytest.mark.parametrize("invalid,pattern", [
    (lambda events: events[0].update(sequence=True), "sequence"),
    (lambda events: events[0].update(side="HEDGE"), "side"),
    (lambda events: events[0].update(quantity=0), "order quantity"),
    (lambda events: events[0].update(limit_ticks=-1), "limit ticks"),
    (lambda events: events[0].update(broker_api_key="NO"), "unexpected offline"),
    (lambda events: events[0].update(action="EXECUTE_REAL_BROKER"), "unapproved"),
])
def test_invalid_order_and_broker_injection_rejected(invalid, pattern):
    events = [submit(1, "o1", "BUY", 1)]
    invalid(events)
    with pytest.raises(ValueError, match=pattern):
        replay_offline_order_router(config(events))


def test_unordered_unique_receive_clocks_and_sequence_refused():
    spec = config([submit(1, "o1", "BUY", 1),
                   submit(2, "o2", "SELL", 1)])
    spec["events"][1]["received_at"] = spec["events"][0]["received_at"]
    with pytest.raises(ValueError, match="non-increasing event sequence or receive"):
        replay_offline_order_router(spec)
    spec = config([submit(1, "o1", "BUY", 1),
                   submit(2, "o2", "SELL", 1)])
    spec["events"][1]["sequence"] = 1
    with pytest.raises(ValueError, match="non-increasing"):
        replay_offline_order_router(spec)


def test_overfill_duplicate_execution_id_and_fill_after_cancel_ack_refused():
    initial = [submit(1, "o1", "BUY", 2),
               event(2, "ACK", order_id="o1"),
               event(3, "FILL", order_id="o1", execution_id="x1",
                     quantity=1, price_ticks=10000)]
    with pytest.raises(ValueError, match="overfills"):
        replay_offline_order_router(config(initial + [
            event(4, "FILL", order_id="o1", execution_id="x2",
                  quantity=2, price_ticks=10001)]))
    with pytest.raises(ValueError, match="duplicate execution ID"):
        replay_offline_order_router(config(initial + [
            event(4, "FILL", order_id="o1", execution_id="x1",
                  quantity=1, price_ticks=10001)]))
    settled = initial + [
        event(4, "CANCEL", order_id="o1"),
        event(5, "CANCEL_ACK", order_id="o1"),
        event(6, "FILL", order_id="o1", execution_id="x2",
              quantity=1, price_ticks=10001)]
    with pytest.raises(ValueError, match="fill after terminal"):
        replay_offline_order_router(config(settled))


def test_unknown_order_ack_and_unapproved_resume_refused():
    with pytest.raises(ValueError, match="unknown client"):
        replay_offline_order_router(config([
            event(1, "ACK", order_id="missing")]))
    with pytest.raises(ValueError, match="unapproved"):
        replay_offline_order_router(config([
            event(1, "RESUME", order_id="anything")]))


def test_duplicate_client_order_id_forbidden_even_with_new_event_id():
    with pytest.raises(ValueError, match="duplicate client order"):
        replay_offline_order_router(config([
            submit(1, "o1", "BUY", 1),
            submit(2, "o1", "BUY", 1)]))


def test_mode_cannot_be_live_or_paper_broker_and_strict_root():
    s = config([submit(1, "o1", "BUY", 1)])
    s["mode"] = "LIVE"
    with pytest.raises(ValueError, match="only router mode"):
        replay_offline_order_router(s)
    s = config([submit(1, "o1", "BUY", 1)])
    s["credentials"] = {"key": "forbidden"}
    with pytest.raises(ValueError, match="router schema"):
        replay_offline_order_router(s)
