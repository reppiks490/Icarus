from __future__ import annotations

import math

import pytest

from icarus_engine.intelligence_fabric import (
    IntelligenceEvent,
    IntelligenceFabric,
    attention_score,
    event_from_intelligence_claim,
)


def _event(**overrides):
    body = dict(
        event_type="anomaly",
        source="fve",
        source_kind="native",
        channel="market",
        thread_key="NQ:liquidity-regime",
        title="NQ liquidity regime anomaly",
        body="Cross-source deterioration detected.",
        observed_at="2026-10-12T20:00:00-05:00",
        received_at="2026-10-13T01:00:01Z",
        severity=3,
        urgency=0.7,
        confidence=0.61,
        assets=("NQ", "MNQ"),
        correlation_id="corr-1",
        causation_ids=("event-parent",),
        evidence_ids=("receipt-1",),
        tags=("microstructure", "liquidity"),
        payload={"metric": 3.2},
    )
    body.update(overrides)
    return IntelligenceEvent(**body)


def test_event_normalizes_authority_and_timestamps():
    normalized = _event().normalized()
    assert normalized["schema_version"] == "icarus-intelligence-fabric-v1"
    assert normalized["observed_at"] == "2026-10-13T01:00:00Z"
    assert normalized["received_at"] == "2026-10-13T01:00:01Z"
    assert normalized["execution_authorized"] is False
    assert normalized["production_decision_authorized"] is False
    assert normalized["assets"] == ["MNQ", "NQ"]
    assert normalized["tags"] == ["liquidity", "microstructure"]


@pytest.mark.parametrize(
    "overrides, match",
    [
        ({"observed_at": "2026-10-13T01:00:00"}, "timezone"),
        ({"received_at": "2026-10-13T00:59:59Z"}, "precede"),
        ({"event_type": "trade"}, "event_type"),
        ({"source_kind": "broker"}, "source_kind"),
        ({"severity": True}, "severity"),
        ({"severity": 6}, "severity"),
        ({"urgency": float("nan")}, "urgency"),
        ({"urgency": 1.1}, "urgency"),
        ({"confidence": float("inf")}, "confidence"),
        ({"confidence": -0.1}, "confidence"),
        ({"payload": {"bad": float("nan")}}, "payload"),
    ],
)
def test_event_validation_fails_closed(overrides, match):
    with pytest.raises(ValueError, match=match):
        _event(**overrides).normalized()


def test_event_bounds_payload_and_repeated_fields():
    with pytest.raises(ValueError, match="32768"):
        _event(payload={"blob": "x" * 33000}).normalized()
    with pytest.raises(ValueError, match="64"):
        _event(assets=tuple(f"A{i}" for i in range(65))).normalized()
    with pytest.raises(ValueError, match="64"):
        _event(tags=tuple(f"t{i}" for i in range(65))).normalized()
    with pytest.raises(ValueError, match="64"):
        _event(evidence_ids=tuple(f"e{i}" for i in range(65))).normalized()
    with pytest.raises(ValueError, match="64"):
        _event(causation_ids=tuple(f"c{i}" for i in range(65))).normalized()


def test_event_identity_is_deterministic_and_attention_ignores_confidence():
    left = _event(confidence=0.1)
    right = _event(confidence=0.9)
    assert _event().event_id() == _event().event_id()
    assert left.event_id() != right.event_id()
    assert attention_score(left) == attention_score(right)
    assert attention_score(left) == pytest.approx(63.0)


def test_publish_is_append_only_idempotent_and_replayable():
    fabric = IntelligenceFabric(":memory:")
    try:
        event = _event()
        first = fabric.publish(event)
        second = fabric.publish(event)
        rows = fabric.replay()

        assert first["sequence"] == 1
        assert first["idempotent"] is False
        assert second["sequence"] == 1
        assert second["idempotent"] is True
        assert len(rows) == 1
        assert rows[0]["event_id"] == event.event_id()
        assert rows[0]["execution_authorized"] is False
        assert rows[0]["production_decision_authorized"] is False
    finally:
        fabric.close()


def test_file_backed_reopen_preserves_sequence_and_idempotency(tmp_path):
    db = tmp_path / "fabric.sqlite3"
    event = _event()
    with IntelligenceFabric(str(db)) as first:
        receipt = first.publish(event)
        assert receipt["sequence"] == 1
    with IntelligenceFabric(str(db)) as second:
        rows = second.replay()
        duplicate = second.publish(event)
        assert [row["sequence"] for row in rows] == [1]
        assert duplicate["sequence"] == 1
        assert duplicate["idempotent"] is True


def test_replay_query_and_thread_use_indexed_semantics():
    with IntelligenceFabric(":memory:") as fabric:
        a = fabric.publish(_event(thread_key="thread-a", tags=("one",), assets=("NQ",), severity=1))
        b = fabric.publish(_event(
            event_type="risk",
            source="risk-engine",
            channel="risk",
            thread_key="thread-b",
            tags=("two",),
            assets=("GC",),
            severity=5,
            urgency=1.0,
            observed_at="2026-10-13T01:00:02Z",
            received_at="2026-10-13T01:00:03Z",
        ))
        c = fabric.publish(_event(
            event_type="human_note",
            source="owner",
            source_kind="human",
            channel="market",
            thread_key="thread-a",
            tags=("two",),
            assets=("NQ", "ES"),
            severity=2,
            observed_at="2026-10-13T01:00:04Z",
            received_at="2026-10-13T01:00:05Z",
        ))

        assert [row["sequence"] for row in fabric.replay(after_sequence=a["sequence"])] == [b["sequence"], c["sequence"]]
        assert [row["sequence"] for row in fabric.thread("thread-a")] == [a["sequence"], c["sequence"]]
        assert [row["sequence"] for row in fabric.query(channel="risk")] == [b["sequence"]]
        assert [row["sequence"] for row in fabric.query(assets=("GC",))] == [b["sequence"]]
        assert [row["sequence"] for row in fabric.query(tags=("two",), channel="market")] == [c["sequence"]]
        assert [row["sequence"] for row in fabric.query(event_types=("risk",), min_severity=4)] == [b["sequence"]]
        assert [row["sequence"] for row in fabric.query(source="owner")] == [c["sequence"]]
        assert [row["sequence"] for row in fabric.query(after="2026-10-13T01:00:03Z")] == [c["sequence"]]
        assert [row["sequence"] for row in fabric.query(before="2026-10-13T01:00:03Z")] == [a["sequence"], b["sequence"]]
        assert fabric.get(b["event_id"])["sequence"] == b["sequence"]


def test_inbox_ranks_attention_and_expiration_does_not_delete_history():
    with IntelligenceFabric(":memory:") as fabric:
        expired = fabric.publish(_event(
            event_type="risk",
            severity=5,
            urgency=1.0,
            expires_at="2026-10-13T01:05:00Z",
        ))
        active = fabric.publish(_event(
            event_type="alert",
            severity=4,
            urgency=0.8,
            title="Active alert",
            observed_at="2026-10-13T01:05:01Z",
            received_at="2026-10-13T01:05:02Z",
            expires_at="2026-10-13T02:00:00Z",
        ))
        low = fabric.publish(_event(
            event_type="research",
            severity=1,
            urgency=0.1,
            title="Research note",
            observed_at="2026-10-13T01:05:03Z",
            received_at="2026-10-13T01:05:04Z",
        ))
        inbox = fabric.inbox(as_of="2026-10-13T01:10:00Z")
        assert [row["sequence"] for row in inbox] == [active["sequence"], low["sequence"]]
        assert expired["sequence"] in [row["sequence"] for row in fabric.replay()]


def test_limits_fail_closed():
    with IntelligenceFabric(":memory:") as fabric:
        for bad in (True, 0, -1, 1001):
            with pytest.raises(ValueError, match="limit"):
                fabric.replay(limit=bad)
            with pytest.raises(ValueError, match="limit"):
                fabric.query(limit=bad)


def _claim(**overrides):
    claim = {
        "schema_version": "icarus-unified-intelligence-v1",
        "source": "chronofold",
        "source_kind": "native",
        "semantic_key": "NQ:time_price_phase",
        "stance": 0.7,
        "confidence": 0.82,
        "evidence_class": "derived",
        "observed_at": "2026-10-13T01:00:00Z",
        "received_at": "2026-10-13T01:00:01Z",
        "regime": "RTH",
        "horizon_seconds": 300,
        "lineage": ["bar:123", "feature:abc"],
        "falsifiers": ["future outcome disagrees"],
        "details": {"asset": "NQ", "model": "chronofold-v1"},
        "execution_authorized": True,
        "production_decision_authorized": True,
    }
    claim.update(overrides)
    return claim


def test_unified_intelligence_bridge_preserves_claim_without_granting_authority():
    event = event_from_intelligence_claim(_claim(), claim_id="claim-1")
    normalized = event.normalized()
    assert normalized["event_type"] == "claim"
    assert normalized["channel"] == "intelligence"
    assert normalized["source"] == "chronofold"
    assert normalized["source_kind"] == "native"
    assert normalized["observed_at"] == "2026-10-13T01:00:00Z"
    assert normalized["received_at"] == "2026-10-13T01:00:01Z"
    assert normalized["confidence"] == 0.82
    assert normalized["assets"] == ["NQ"]
    assert normalized["execution_authorized"] is False
    assert normalized["production_decision_authorized"] is False
    assert normalized["thread_key"].startswith("ui:")
    assert "claim-1" in normalized["evidence_ids"]
    assert "bar:123" in normalized["evidence_ids"]
    payload = normalized["payload"]
    assert payload["semantic_key"] == "NQ:time_price_phase"
    assert payload["stance"] == 0.7
    assert payload["regime"] == "RTH"
    assert payload["horizon_seconds"] == 300
    assert payload["unified_intelligence_claim"]["execution_authorized"] is True
    assert payload["bridge"] == "unified-intelligence-v1"
    low_conf = event_from_intelligence_claim(_claim(confidence=0.1))
    high_conf = event_from_intelligence_claim(_claim(confidence=0.99))
    assert attention_score(low_conf) == attention_score(high_conf)


def test_unified_intelligence_bridge_is_deterministic_and_fails_closed():
    first = event_from_intelligence_claim(_claim())
    second = event_from_intelligence_claim(_claim())
    assert first.thread_key == second.thread_key
    assert first.event_id() == second.event_id()
    broken = _claim()
    del broken["semantic_key"]
    with pytest.raises(ValueError, match="semantic_key"):
        event_from_intelligence_claim(broken)
    with pytest.raises(ValueError, match="stance"):
        event_from_intelligence_claim(_claim(stance=math.nan))
