from __future__ import annotations

import sqlite3

import pytest

from icarus_engine.intelligence_delivery import IntelligenceDeliveryPlane, SubscriptionSpec
from icarus_engine.intelligence_fabric import IntelligenceEvent, IntelligenceFabric

T0 = "2026-10-13T02:00:00Z"


def _event() -> IntelligenceEvent:
    return IntelligenceEvent(
        event_type="risk",
        source="fve",
        source_kind="system",
        channel="risk",
        thread_key="risk:nq",
        title="retry event",
        body="retry body",
        observed_at=T0,
        received_at=T0,
        severity=3,
        urgency=0.8,
        assets=("NQ",),
        tags=("urgent",),
    )


def _setup(*, max_attempts: int = 3, retry_delay_seconds: int = 5):
    connection = sqlite3.connect(":memory:")
    fabric = IntelligenceFabric(connection)
    fabric.publish(_event())
    tokens = iter([f"lease-{i}" for i in range(1, 20)])
    plane = IntelligenceDeliveryPlane(connection, token_factory=lambda: next(tokens))
    plane.register_consumer("worker-a", as_of=T0)
    plane.create_subscription(
        SubscriptionSpec(
            subscription_id="retry-sub",
            revision=1,
            mode="broadcast",
            consumer_id="worker-a",
            channel="risk",
            event_types=("risk",),
            assets=("NQ",),
            source="fve",
            max_attempts=max_attempts,
            retry_delay_seconds=retry_delay_seconds,
        ),
        as_of=T0,
    )
    return plane


def test_nack_retries_after_fixed_delay_when_attempts_remain() -> None:
    plane = _setup()
    first = plane.claim("retry-sub", 1, "worker-a", as_of="2026-10-13T02:00:01Z")[0]
    result = plane.nack(
        first["delivery_id"], "worker-a", first["lease_token"],
        as_of="2026-10-13T02:00:02Z", reason={"error": "temporary"},
    )
    assert result["state"] == "PENDING"
    assert result["attempt"] == 1
    assert result["retry_eligible_at"] == "2026-10-13T02:00:07Z"
    assert plane.claim("retry-sub", 1, "worker-a", as_of="2026-10-13T02:00:06Z") == []
    second = plane.claim("retry-sub", 1, "worker-a", as_of="2026-10-13T02:00:07Z")[0]
    assert second["attempt"] == 2


def test_expired_lease_recovers_and_can_be_redelivered() -> None:
    plane = _setup(retry_delay_seconds=0)
    first = plane.claim("retry-sub", 1, "worker-a", as_of="2026-10-13T02:00:01Z", lease_seconds=10)[0]
    recovered = plane.recover_expired(as_of="2026-10-13T02:00:11Z")
    assert recovered[0]["delivery_id"] == first["delivery_id"]
    assert recovered[0]["state"] == "PENDING"
    second = plane.claim("retry-sub", 1, "worker-a", as_of="2026-10-13T02:00:11Z")[0]
    assert second["attempt"] == 2
    assert second["lease_token"] != first["lease_token"]


def test_mixed_nack_and_expiry_reaches_max_attempts_then_dead_letters() -> None:
    plane = _setup(max_attempts=3, retry_delay_seconds=0)
    one = plane.claim("retry-sub", 1, "worker-a", as_of="2026-10-13T02:00:01Z", lease_seconds=5)[0]
    plane.nack(one["delivery_id"], "worker-a", one["lease_token"], as_of="2026-10-13T02:00:02Z")
    two = plane.claim("retry-sub", 1, "worker-a", as_of="2026-10-13T02:00:03Z", lease_seconds=5)[0]
    plane.recover_expired(as_of="2026-10-13T02:00:08Z")
    three = plane.claim("retry-sub", 1, "worker-a", as_of="2026-10-13T02:00:09Z", lease_seconds=5)[0]
    final = plane.nack(three["delivery_id"], "worker-a", three["lease_token"], as_of="2026-10-13T02:00:10Z")

    assert two["attempt"] == 2
    assert three["attempt"] == 3
    assert final["state"] == "DEAD_LETTERED"
    dead = plane.dead_letters(subscription_id="retry-sub")
    assert len(dead) == 1
    assert dead[0]["attempt"] == 3
    assert plane.claim("retry-sub", 1, "worker-a", as_of="2026-10-13T02:01:00Z") == []


def test_dead_letter_requeue_is_explicit_and_preserves_attempt_history() -> None:
    plane = _setup(max_attempts=1, retry_delay_seconds=0)
    first = plane.claim("retry-sub", 1, "worker-a", as_of="2026-10-13T02:00:01Z")[0]
    dead = plane.nack(first["delivery_id"], "worker-a", first["lease_token"], as_of="2026-10-13T02:00:02Z")
    assert dead["state"] == "DEAD_LETTERED"

    requeued = plane.requeue_dead_lettered(
        first["delivery_id"], as_of="2026-10-13T02:00:03Z", reason={"operator": "manual retry"}
    )
    assert requeued["state"] == "PENDING"
    assert requeued["attempt"] == 1
    second = plane.claim("retry-sub", 1, "worker-a", as_of="2026-10-13T02:00:04Z")[0]
    assert second["attempt"] == 2
    again_dead = plane.nack(second["delivery_id"], "worker-a", second["lease_token"], as_of="2026-10-13T02:00:05Z")
    assert again_dead["state"] == "DEAD_LETTERED"
    transitions = [row["transition"] for row in plane.receipts(delivery_id=first["delivery_id"], limit=30)]
    assert "REQUEUED" in transitions
    assert transitions.count("LEASED") == 2


def test_nack_reason_is_bounded_finite_json() -> None:
    plane = _setup()
    delivery = plane.claim("retry-sub", 1, "worker-a", as_of="2026-10-13T02:00:01Z")[0]
    with pytest.raises(ValueError, match="finite JSON"):
        plane.nack(
            delivery["delivery_id"], "worker-a", delivery["lease_token"],
            as_of="2026-10-13T02:00:02Z", reason={"value": float("nan")},
        )
    with pytest.raises(ValueError, match="exceeds"):
        plane.nack(
            delivery["delivery_id"], "worker-a", delivery["lease_token"],
            as_of="2026-10-13T02:00:02Z", reason={"value": "x" * 40000},
        )
    still_leased = plane.receipts(delivery_id=delivery["delivery_id"], limit=20)
    assert [r["transition"] for r in still_leased][-1] == "LEASED"
