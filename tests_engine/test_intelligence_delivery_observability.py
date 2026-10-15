from __future__ import annotations

import sqlite3

from icarus_engine.intelligence_delivery import IntelligenceDeliveryPlane, SubscriptionSpec
from icarus_engine.intelligence_fabric import IntelligenceEvent, IntelligenceFabric

T0 = "2026-10-13T03:00:00Z"
T1 = "2026-10-13T03:00:10Z"


def _event(index: int, asset: str = "NQ") -> IntelligenceEvent:
    return IntelligenceEvent(
        event_type="risk",
        source="fve",
        source_kind="system",
        channel="risk",
        thread_key=f"risk:{asset.lower()}",
        title=f"event {index}",
        body="body",
        observed_at=T0,
        received_at=T0 if index == 1 else T1,
        severity=3,
        urgency=0.7,
        assets=(asset,),
        tags=("urgent",),
    )


def _setup():
    connection = sqlite3.connect(":memory:")
    fabric = IntelligenceFabric(connection)
    first = fabric.publish(_event(1, "NQ"))
    second = fabric.publish(_event(2, "NQ"))
    third = fabric.publish(_event(3, "GC"))
    tokens = iter([f"lease-{i}" for i in range(1, 20)])
    plane = IntelligenceDeliveryPlane(connection, token_factory=lambda: next(tokens))
    plane.register_consumer("risk-monitor", as_of=T0)
    plane.create_subscription(
        SubscriptionSpec(
            subscription_id="live-risk",
            revision=1,
            mode="broadcast",
            consumer_id="risk-monitor",
            channel="risk",
            event_types=("risk",),
            assets=("NQ",),
            source="fve",
            max_attempts=3,
        ),
        as_of=T0,
    )
    return connection, fabric, plane, (first, second, third)


def test_replay_subscription_copies_material_contract_and_uses_new_inclusive_start_sequence() -> None:
    _, _, plane, events = _setup()
    created = plane.create_replay_subscription(
        "live-risk", 1, "replay-risk", 2, as_of="2026-10-13T03:01:00Z"
    )
    assert created["subscription_id"] == "replay-risk"
    assert created["revision"] == 1
    claimed = plane.claim("replay-risk", 1, "risk-monitor", as_of="2026-10-13T03:01:01Z", limit=10)
    assert [row["journal_sequence"] for row in claimed] == [2]
    assert claimed[0]["event_id"] == events[1]["event_id"]


def test_replay_does_not_mutate_live_subscription_or_phase1_events() -> None:
    connection, _, plane, events = _setup()
    before_events = connection.execute(
        "SELECT sequence, event_id, envelope_json FROM fabric_events ORDER BY sequence"
    ).fetchall()
    before_live = connection.execute(
        "SELECT material_json, material_hash, enabled FROM fabric_subscriptions WHERE subscription_id='live-risk' AND revision=1"
    ).fetchone()

    plane.create_replay_subscription("live-risk", 1, "replay-risk", 1, as_of="2026-10-13T03:01:00Z")

    after_events = connection.execute(
        "SELECT sequence, event_id, envelope_json FROM fabric_events ORDER BY sequence"
    ).fetchall()
    after_live = connection.execute(
        "SELECT material_json, material_hash, enabled FROM fabric_subscriptions WHERE subscription_id='live-risk' AND revision=1"
    ).fetchone()
    assert [tuple(row) for row in before_events] == [tuple(row) for row in after_events]
    assert tuple(before_live) == tuple(after_live)
    assert [row["event_id"] for row in events] == [row[1] for row in after_events]


def test_metrics_report_backlog_active_expired_retry_deadletter_and_tail() -> None:
    _, _, plane, _ = _setup()
    claimed = plane.claim("live-risk", 1, "risk-monitor", as_of="2026-10-13T03:01:00Z", lease_seconds=30, limit=1)[0]
    metrics = plane.metrics("live-risk", 1, as_of="2026-10-13T03:01:10Z")

    assert metrics["matching_event_count"] == 2
    assert metrics["pending_count"] == 1
    assert metrics["active_leases"] == 1
    assert metrics["expired_leases"] == 0
    assert metrics["tail_sequence"] == 3
    assert metrics["has_matching_events"] is True
    assert metrics["oldest_pending_sequence"] == 2
    assert metrics["execution_authorized"] is False

    plane.recover_expired(as_of="2026-10-13T03:01:30Z")
    later = plane.metrics("live-risk", 1, as_of="2026-10-13T03:01:31Z")
    assert later["retry_count"] >= 1
    assert later["active_leases"] == 0
    assert later["pending_count"] == 2
    assert claimed["attempt"] == 1


def test_filtered_subscription_with_no_matches_has_explicit_empty_zero_lag_state() -> None:
    _, _, plane, _ = _setup()
    plane.create_subscription(
        SubscriptionSpec(
            subscription_id="empty",
            revision=1,
            mode="broadcast",
            consumer_id="risk-monitor",
            channel="risk",
            assets=("ES",),
        ),
        as_of=T0,
    )
    metrics = plane.metrics("empty", 1, as_of="2026-10-13T03:02:00Z")
    assert metrics["matching_event_count"] == 0
    assert metrics["pending_count"] == 0
    assert metrics["sequence_lag"] == 0
    assert metrics["has_matching_events"] is False
    assert metrics["oldest_pending_sequence"] is None


def test_receipts_are_append_only_and_filterable() -> None:
    _, _, plane, _ = _setup()
    delivery = plane.claim("live-risk", 1, "risk-monitor", as_of="2026-10-13T03:01:00Z")[0]
    plane.ack(delivery["delivery_id"], "risk-monitor", delivery["lease_token"], as_of="2026-10-13T03:01:01Z")
    delivery_receipts = plane.receipts(delivery_id=delivery["delivery_id"], limit=20)
    subscription_receipts = plane.receipts(subscription_id="live-risk", limit=20)
    assert [r["transition"] for r in delivery_receipts] == ["PENDING", "LEASED", "ACKED"]
    assert [r["receipt_sequence"] for r in delivery_receipts] == sorted(r["receipt_sequence"] for r in delivery_receipts)
    assert len(subscription_receipts) >= len(delivery_receipts)
