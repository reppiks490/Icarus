from __future__ import annotations

import sqlite3

from icarus_engine.intelligence_collaboration import IntelligenceCollaboration, WorkRequest
from icarus_engine.intelligence_delivery import IntelligenceDeliveryPlane, SubscriptionSpec
from icarus_engine.intelligence_fabric import IntelligenceFabric


def test_delivery_ack_has_no_collaboration_acceptance_side_effect():
    connection = sqlite3.connect(":memory:")
    fabric = IntelligenceFabric(connection)
    tokens = iter(["lease-collaboration-1", "lease-collaboration-2"])
    delivery = IntelligenceDeliveryPlane(connection, token_factory=lambda: next(tokens))
    collaboration = IntelligenceCollaboration(fabric)

    request = WorkRequest(
        requester_principal="requester-agent",
        requester_kind="agent",
        target_kind="principal",
        target_id="worker-agent",
        work_kind="research",
        idempotency_key="ack-separation-001",
        objective="Prove transport acknowledgement cannot accept semantic work.",
        priority=2,
    )
    created = collaboration.create_work(
        request,
        observed_at="2026-10-14T00:00:00Z",
        received_at="2026-10-14T00:00:01Z",
    )
    before = collaboration.snapshot(request.work_id())
    assert before.state == "OPEN"
    assert before.assignee is None
    assert before.applied_event_count == 1

    delivery.register_consumer("worker-agent", as_of="2026-10-14T00:00:02Z")
    delivery.create_subscription(
        SubscriptionSpec(
            subscription_id="sub-collaboration-worker",
            revision=1,
            mode="broadcast",
            consumer_id="worker-agent",
            start_sequence=created["sequence"],
            channel="collaboration",
            max_attempts=3,
            retry_delay_seconds=0,
        ),
        as_of="2026-10-14T00:00:02Z",
    )
    claimed = delivery.claim(
        "sub-collaboration-worker",
        1,
        "worker-agent",
        as_of="2026-10-14T00:00:03Z",
        limit=1,
    )
    assert len(claimed) == 1
    assert claimed[0]["event_id"] == created["event_id"]

    acknowledged = delivery.ack(
        claimed[0]["delivery_id"],
        "worker-agent",
        claimed[0]["lease_token"],
        as_of="2026-10-14T00:00:04Z",
    )
    assert acknowledged["state"] == "ACKED"
    assert acknowledged["execution_authorized"] is False
    assert acknowledged["production_decision_authorized"] is False

    after = collaboration.snapshot(request.work_id())
    assert after.state == "OPEN"
    assert after.assignee is None
    assert after.head_event_id == created["event_id"]
    assert after.applied_event_count == 1
    assert after.conflicts == ()
    assert after.execution_authorized is False
    assert after.production_decision_authorized is False

    collaboration_events = fabric.thread(f"work:{request.work_id()}", limit=100)
    assert len(collaboration_events) == 1
    assert collaboration_events[0]["event_id"] == created["event_id"]
