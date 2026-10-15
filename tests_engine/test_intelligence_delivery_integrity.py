from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from icarus_engine.intelligence_delivery import IntelligenceDeliveryPlane, SubscriptionSpec
from icarus_engine.intelligence_fabric import IntelligenceEvent, IntelligenceFabric

T0 = "2026-10-13T04:00:00Z"


def _event() -> IntelligenceEvent:
    return IntelligenceEvent(
        event_type="risk",
        source="fve",
        source_kind="system",
        channel="risk",
        thread_key="risk:nq",
        title="integrity event",
        body="integrity body",
        observed_at=T0,
        received_at=T0,
        severity=3,
        urgency=0.8,
        assets=("NQ",),
        tags=("urgent",),
    )


def _broadcast_spec() -> SubscriptionSpec:
    return SubscriptionSpec(
        subscription_id="integrity-sub",
        revision=1,
        mode="broadcast",
        consumer_id="worker-a",
        channel="risk",
        assets=("NQ",),
        source="fve",
    )


def test_file_backed_reopen_preserves_subscriptions_deliveries_receipts_and_ack_state(tmp_path) -> None:
    db = tmp_path / "fabric.db"
    connection = sqlite3.connect(db)
    fabric = IntelligenceFabric(connection)
    fabric.publish(_event())
    connection.close()

    with IntelligenceDeliveryPlane(str(db), token_factory=lambda: "lease-one") as plane:
        plane.register_consumer("worker-a", as_of=T0)
        plane.create_subscription(_broadcast_spec(), as_of=T0)
        delivery = plane.claim("integrity-sub", 1, "worker-a", as_of="2026-10-13T04:00:01Z")[0]
        plane.ack(delivery["delivery_id"], "worker-a", delivery["lease_token"], as_of="2026-10-13T04:00:02Z")

    with IntelligenceDeliveryPlane(str(db), token_factory=lambda: "lease-two") as reopened:
        recreated = reopened.create_subscription(_broadcast_spec(), as_of="2026-10-13T04:01:00Z")
        assert recreated["idempotent"] is True
        assert reopened.claim("integrity-sub", 1, "worker-a", as_of="2026-10-13T04:01:01Z") == []
        receipts = reopened.receipts(subscription_id="integrity-sub", limit=20)
        assert [r["transition"] for r in receipts][-3:] == ["PENDING", "LEASED", "ACKED"]
        assert reopened.metrics("integrity-sub", 1, as_of="2026-10-13T04:01:02Z")["acked_count"] == 1


def test_tampered_phase1_envelope_or_authority_flags_fail_closed_before_delivery() -> None:
    connection = sqlite3.connect(":memory:")
    fabric = IntelligenceFabric(connection)
    published = fabric.publish(_event())
    plane = IntelligenceDeliveryPlane(connection, token_factory=lambda: "lease-one")
    plane.register_consumer("worker-a", as_of=T0)
    plane.create_subscription(_broadcast_spec(), as_of=T0)

    envelope = connection.execute(
        "SELECT envelope_json FROM fabric_events WHERE event_id=?", (published["event_id"],)
    ).fetchone()[0]
    tampered = envelope.replace('"execution_authorized":false', '"execution_authorized":true')
    connection.execute(
        "UPDATE fabric_events SET envelope_json=? WHERE event_id=?", (tampered, published["event_id"])
    )
    connection.commit()

    with pytest.raises(ValueError, match="integrity|authority"):
        plane.claim("integrity-sub", 1, "worker-a", as_of="2026-10-13T04:00:01Z")
    assert connection.execute("SELECT COUNT(*) FROM fabric_deliveries").fetchone()[0] == 0


def test_claim_race_across_independent_sqlite_connections_yields_one_competing_lease(tmp_path) -> None:
    db = tmp_path / "race.db"
    connection = sqlite3.connect(db)
    fabric = IntelligenceFabric(connection)
    fabric.publish(_event())
    connection.close()

    with IntelligenceDeliveryPlane(str(db)) as setup:
        setup.register_consumer("worker-a", as_of=T0)
        setup.register_consumer("worker-b", as_of=T0)
        setup.set_group_membership("worker-a", "researchers", True, as_of=T0)
        setup.set_group_membership("worker-b", "researchers", True, as_of=T0)
        setup.create_subscription(
            SubscriptionSpec(
                subscription_id="race-sub", revision=1, mode="competing", consumer_group="researchers",
                channel="risk", assets=("NQ",), source="fve",
            ),
            as_of=T0,
        )

    barrier = Barrier(2)
    def worker(consumer_id: str, token: str):
        with IntelligenceDeliveryPlane(str(db), token_factory=lambda: token) as plane:
            barrier.wait()
            return plane.claim("race-sub", 1, consumer_id, as_of="2026-10-13T04:00:01Z")

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda args: worker(*args), [("worker-a", "token-a"), ("worker-b", "token-b")]))
    assert sorted(len(result) for result in results) == [0, 1]
    leased = sqlite3.connect(db).execute(
        "SELECT COUNT(*) FROM fabric_deliveries WHERE status='LEASED'"
    ).fetchone()[0]
    assert leased == 1


def test_failed_transition_rolls_back_projection_and_receipt_together() -> None:
    connection = sqlite3.connect(":memory:")
    fabric = IntelligenceFabric(connection)
    fabric.publish(_event())
    plane = IntelligenceDeliveryPlane(connection, token_factory=lambda: "lease-one")
    plane.register_consumer("worker-a", as_of=T0)
    plane.create_subscription(_broadcast_spec(), as_of=T0)
    delivery = plane.claim("integrity-sub", 1, "worker-a", as_of="2026-10-13T04:00:01Z")[0]
    connection.execute(
        """CREATE TRIGGER block_acked_receipt BEFORE INSERT ON fabric_delivery_receipts
           WHEN NEW.transition='ACKED' BEGIN SELECT RAISE(ABORT, 'blocked receipt'); END"""
    )
    connection.commit()

    with pytest.raises(sqlite3.IntegrityError):
        plane.ack(delivery["delivery_id"], "worker-a", delivery["lease_token"], as_of="2026-10-13T04:00:02Z")
    state = connection.execute(
        "SELECT status, lease_token FROM fabric_deliveries WHERE delivery_id=?", (delivery["delivery_id"],)
    ).fetchone()
    assert tuple(state) == ("LEASED", "lease-one")
    assert connection.execute(
        "SELECT COUNT(*) FROM fabric_delivery_receipts WHERE transition='ACKED'"
    ).fetchone()[0] == 0


def test_every_public_result_keeps_execution_authority_false() -> None:
    connection = sqlite3.connect(":memory:")
    fabric = IntelligenceFabric(connection)
    fabric.publish(_event())
    plane = IntelligenceDeliveryPlane(connection, token_factory=lambda: "lease-one")
    results = []
    results.append(plane.register_consumer("worker-a", as_of=T0))
    results.append(plane.create_subscription(_broadcast_spec(), as_of=T0))
    results.extend(plane.claim("integrity-sub", 1, "worker-a", as_of="2026-10-13T04:00:01Z"))
    results.append(plane.metrics("integrity-sub", 1, as_of="2026-10-13T04:00:02Z"))
    results.extend(plane.receipts(subscription_id="integrity-sub", limit=20))
    replay = plane.create_replay_subscription("integrity-sub", 1, "integrity-replay", 1, as_of="2026-10-13T04:00:03Z")
    results.append(replay)
    assert results
    assert all(result["execution_authorized"] is False for result in results)
    assert all(result["production_decision_authorized"] is False for result in results)
