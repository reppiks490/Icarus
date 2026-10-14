from __future__ import annotations

import sqlite3

import pytest

from icarus_engine.intelligence_delivery import IntelligenceDeliveryPlane, SubscriptionSpec
from icarus_engine.intelligence_fabric import IntelligenceEvent, IntelligenceFabric


T0 = "2026-10-13T01:45:00Z"
T1 = "2026-10-13T01:46:00Z"


def _broadcast_spec(**overrides):
    values = {
        "subscription_id": "sub-risk",
        "revision": 1,
        "mode": "broadcast",
        "consumer_id": "risk-monitor",
        "start_sequence": 1,
        "channel": "risk",
        "event_types": ("risk",),
        "assets": ("NQ",),
        "tags": ("urgent",),
        "source": "fve",
        "min_severity": 2,
        "max_attempts": 3,
        "retry_delay_seconds": 5,
    }
    values.update(overrides)
    return SubscriptionSpec(**values)


def _risk_event(index: int, received_at: str) -> IntelligenceEvent:
    return IntelligenceEvent(
        event_type="risk",
        source="fve",
        source_kind="system",
        channel="risk",
        thread_key="risk:nq",
        title=f"NQ risk event {index}",
        body=f"risk body {index}",
        observed_at=T0,
        received_at=received_at,
        severity=3,
        urgency=0.8,
        assets=("NQ",),
        tags=("urgent",),
        payload={"index": index},
    )


def _shared_fabric():
    connection = sqlite3.connect(":memory:")
    fabric = IntelligenceFabric(connection)
    tokens = iter([f"lease-{index}" for index in range(1, 50)])
    plane = IntelligenceDeliveryPlane(connection, token_factory=lambda: next(tokens))
    return connection, fabric, plane


def test_subscription_revision_is_canonical_idempotent_and_conflict_fails_closed() -> None:
    connection = sqlite3.connect(":memory:")
    plane = IntelligenceDeliveryPlane(connection)

    first = plane.create_subscription(_broadcast_spec(), as_of=T0)
    second = plane.create_subscription(_broadcast_spec(tags=("urgent", "urgent")), as_of=T1)

    assert first["idempotent"] is False
    assert second["idempotent"] is True
    assert first["material_hash"] == second["material_hash"]
    assert first["execution_authorized"] is False
    assert first["production_decision_authorized"] is False

    with pytest.raises(ValueError, match="conflict"):
        plane.create_subscription(_broadcast_spec(channel="alerts"), as_of=T1)


def test_subscription_mode_target_and_retry_policy_validation() -> None:
    connection = sqlite3.connect(":memory:")
    plane = IntelligenceDeliveryPlane(connection)

    invalid_specs = [
        _broadcast_spec(consumer_id=None),
        _broadcast_spec(consumer_group="workers"),
        _broadcast_spec(mode="competing", consumer_id="risk-monitor", consumer_group=None),
        _broadcast_spec(start_sequence=0),
        _broadcast_spec(max_attempts=0),
        _broadcast_spec(retry_delay_seconds=-1),
    ]
    for spec in invalid_specs:
        with pytest.raises(ValueError):
            plane.create_subscription(spec, as_of=T0)

    with pytest.raises(ValueError, match="timezone"):
        plane.register_consumer("risk-monitor", as_of="2026-10-13T01:45:00")


def test_consumer_registration_and_group_membership_are_receipt_audited() -> None:
    connection = sqlite3.connect(":memory:")
    plane = IntelligenceDeliveryPlane(connection)

    registration = plane.register_consumer("worker-a", as_of=T0)
    enabled = plane.set_group_membership("worker-a", "researchers", True, as_of=T0)
    disabled = plane.set_group_membership("worker-a", "researchers", False, as_of=T1)
    receipts = plane.receipts(limit=20)

    assert registration["consumer_id"] == "worker-a"
    assert enabled["enabled"] is True
    assert disabled["enabled"] is False
    assert [row["transition"] for row in receipts] == [
        "CONSUMER_REGISTERED",
        "GROUP_MEMBERSHIP_ENABLED",
        "GROUP_MEMBERSHIP_DISABLED",
    ]
    assert all(row["execution_authorized"] is False for row in receipts)
    assert all(row["production_decision_authorized"] is False for row in receipts)


def test_subscription_enable_disable_is_receipt_audited_without_rewriting_material_spec() -> None:
    connection = sqlite3.connect(":memory:")
    plane = IntelligenceDeliveryPlane(connection)

    created = plane.create_subscription(_broadcast_spec(), as_of=T0)
    disabled = plane.set_subscription_enabled("sub-risk", 1, False, as_of=T1)
    enabled = plane.set_subscription_enabled("sub-risk", 1, True, as_of="2026-10-13T01:47:00Z")
    recreated = plane.create_subscription(_broadcast_spec(), as_of="2026-10-13T01:48:00Z")
    receipts = plane.receipts(subscription_id="sub-risk", limit=20)

    assert created["material_hash"] == disabled["material_hash"] == enabled["material_hash"]
    assert recreated["idempotent"] is True
    assert [row["transition"] for row in receipts] == [
        "SUBSCRIPTION_CREATED",
        "SUBSCRIPTION_DISABLED",
        "SUBSCRIPTION_ENABLED",
    ]


def test_broadcast_subscriptions_independently_claim_same_phase1_event() -> None:
    _, fabric, plane = _shared_fabric()
    published = fabric.publish(_risk_event(1, T0))
    plane.register_consumer("risk-monitor", as_of=T0)
    plane.register_consumer("audit-monitor", as_of=T0)
    plane.create_subscription(_broadcast_spec(), as_of=T0)
    plane.create_subscription(
        _broadcast_spec(subscription_id="sub-audit", consumer_id="audit-monitor"), as_of=T0
    )

    risk = plane.claim("sub-risk", 1, "risk-monitor", as_of=T1)
    audit = plane.claim("sub-audit", 1, "audit-monitor", as_of=T1)

    assert len(risk) == len(audit) == 1
    assert risk[0]["event_id"] == audit[0]["event_id"] == published["event_id"]
    assert risk[0]["journal_sequence"] == audit[0]["journal_sequence"] == published["sequence"]
    assert risk[0]["state"] == audit[0]["state"] == "LEASED"
    assert risk[0]["attempt"] == audit[0]["attempt"] == 1
    assert risk[0]["lease_token"]
    assert audit[0]["lease_token"]
    assert risk[0]["execution_authorized"] is False
    assert risk[0]["production_decision_authorized"] is False


def test_ack_is_terminal_only_for_its_subscription_target() -> None:
    _, fabric, plane = _shared_fabric()
    published = fabric.publish(_risk_event(1, T0))
    plane.register_consumer("risk-monitor", as_of=T0)
    plane.register_consumer("audit-monitor", as_of=T0)
    plane.create_subscription(_broadcast_spec(), as_of=T0)
    plane.create_subscription(
        _broadcast_spec(subscription_id="sub-audit", consumer_id="audit-monitor"), as_of=T0
    )

    risk = plane.claim("sub-risk", 1, "risk-monitor", as_of=T1)[0]
    acknowledged = plane.ack(
        risk["delivery_id"], "risk-monitor", risk["lease_token"], as_of="2026-10-13T01:46:10Z"
    )
    audit = plane.claim("sub-audit", 1, "audit-monitor", as_of="2026-10-13T01:46:11Z")

    assert acknowledged["state"] == "ACKED"
    assert plane.claim("sub-risk", 1, "risk-monitor", as_of="2026-10-13T01:46:12Z") == []
    assert len(audit) == 1
    assert audit[0]["event_id"] == published["event_id"]


def test_claim_order_is_phase1_sequence_and_start_sequence_is_inclusive() -> None:
    _, fabric, plane = _shared_fabric()
    first = fabric.publish(_risk_event(1, T0))
    second = fabric.publish(_risk_event(2, T1))
    plane.register_consumer("risk-monitor", as_of=T1)
    plane.create_subscription(_broadcast_spec(start_sequence=2), as_of=T1)

    claimed = plane.claim(
        "sub-risk", 1, "risk-monitor", as_of="2026-10-13T01:47:00Z", limit=5
    )

    assert first["sequence"] == 1
    assert second["sequence"] == 2
    assert [row["journal_sequence"] for row in claimed] == [2]
    assert [row["event_id"] for row in claimed] == [second["event_id"]]


def test_disabled_subscription_cannot_claim() -> None:
    _, fabric, plane = _shared_fabric()
    fabric.publish(_risk_event(1, T0))
    plane.register_consumer("risk-monitor", as_of=T0)
    plane.create_subscription(_broadcast_spec(), as_of=T0)
    plane.set_subscription_enabled("sub-risk", 1, False, as_of=T1)

    assert plane.claim("sub-risk", 1, "risk-monitor", as_of="2026-10-13T01:47:00Z") == []
