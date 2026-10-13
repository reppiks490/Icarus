from __future__ import annotations

import sqlite3

import pytest

from icarus_engine.intelligence_delivery import IntelligenceDeliveryPlane, SubscriptionSpec


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
