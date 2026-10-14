from __future__ import annotations

import sqlite3

import pytest

from icarus_engine.intelligence_delivery import IntelligenceDeliveryPlane, SubscriptionSpec
from icarus_engine.intelligence_fabric import IntelligenceEvent, IntelligenceFabric

T0 = "2026-10-13T01:45:00Z"
T1 = "2026-10-13T01:46:00Z"


def _event() -> IntelligenceEvent:
    return IntelligenceEvent(
        event_type="risk",
        source="fve",
        source_kind="system",
        channel="risk",
        thread_key="risk:nq",
        title="NQ competing event",
        body="competing delivery",
        observed_at=T0,
        received_at=T0,
        severity=3,
        urgency=0.7,
        assets=("NQ",),
        tags=("urgent",),
    )


def _competing_spec() -> SubscriptionSpec:
    return SubscriptionSpec(
        subscription_id="sub-workers",
        revision=1,
        mode="competing",
        consumer_group="researchers",
        channel="risk",
        event_types=("risk",),
        assets=("NQ",),
        source="fve",
        min_severity=2,
        max_attempts=3,
    )


def _setup():
    connection = sqlite3.connect(":memory:")
    fabric = IntelligenceFabric(connection)
    fabric.publish(_event())
    tokens = iter(["lease-a", "lease-b", "lease-c", "lease-d"])
    plane = IntelligenceDeliveryPlane(connection, token_factory=lambda: next(tokens))
    plane.register_consumer("worker-a", as_of=T0)
    plane.register_consumer("worker-b", as_of=T0)
    plane.create_subscription(_competing_spec(), as_of=T0)
    return plane


def test_competing_group_allows_only_registered_member_to_claim() -> None:
    plane = _setup()
    plane.set_group_membership("worker-a", "researchers", True, as_of=T0)

    with pytest.raises(ValueError, match="membership"):
        plane.claim("sub-workers", 1, "worker-b", as_of=T1)

    claimed = plane.claim("sub-workers", 1, "worker-a", as_of=T1)
    assert len(claimed) == 1
    assert claimed[0]["lease_owner"] == "worker-a"
    assert claimed[0]["target_kind"] == "group"
    assert claimed[0]["target_id"] == "researchers"


def test_competing_group_has_only_one_active_lease_for_event() -> None:
    plane = _setup()
    plane.set_group_membership("worker-a", "researchers", True, as_of=T0)
    plane.set_group_membership("worker-b", "researchers", True, as_of=T0)

    first = plane.claim("sub-workers", 1, "worker-a", as_of=T1)
    second = plane.claim("sub-workers", 1, "worker-b", as_of="2026-10-13T01:46:01Z")

    assert len(first) == 1
    assert second == []


def test_wrong_consumer_or_wrong_token_cannot_ack() -> None:
    plane = _setup()
    plane.set_group_membership("worker-a", "researchers", True, as_of=T0)
    plane.set_group_membership("worker-b", "researchers", True, as_of=T0)
    delivery = plane.claim("sub-workers", 1, "worker-a", as_of=T1)[0]

    with pytest.raises(ValueError, match="own lease"):
        plane.ack(delivery["delivery_id"], "worker-b", delivery["lease_token"], as_of="2026-10-13T01:46:05Z")
    with pytest.raises(ValueError, match="token"):
        plane.ack(delivery["delivery_id"], "worker-a", "wrong-token", as_of="2026-10-13T01:46:05Z")


def test_ack_at_or_after_lease_expiry_fails_even_before_recovery() -> None:
    plane = _setup()
    plane.set_group_membership("worker-a", "researchers", True, as_of=T0)
    delivery = plane.claim("sub-workers", 1, "worker-a", as_of=T1, lease_seconds=30)[0]

    with pytest.raises(ValueError, match="expired"):
        plane.ack(
            delivery["delivery_id"],
            "worker-a",
            delivery["lease_token"],
            as_of="2026-10-13T01:46:30Z",
        )
