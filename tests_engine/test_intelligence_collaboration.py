from __future__ import annotations

import hashlib
import json

import pytest

from icarus_engine.intelligence_collaboration import (
    COLLABORATION_CHANNEL,
    COLLABORATION_PROTOCOL,
    IntelligenceCollaboration,
    WorkRequest,
    build_request_event,
    derive_work_id,
    request_material_hash,
)
from icarus_engine.intelligence_fabric import IntelligenceFabric


def _request(**overrides):
    values = dict(
        requester_principal="research-agent",
        requester_kind="agent",
        target_kind="principal",
        target_id="macro-agent",
        work_kind="research",
        idempotency_key="nq-regime-001",
        objective="Investigate NQ rate sensitivity with traceable evidence.",
        priority=3,
        constraints={"asset": "NQ", "window": "RTH"},
        required_capabilities=("macro", "rates", "macro"),
        reviewer_principals=("risk-agent", "risk-agent", "history-agent"),
        deadline="2026-10-14T02:30:00-05:00",
        result_contract={
            "result_kind": "json",
            "required_fields": ["conclusion", "evidence"],
            "schema_id": "icarus.research.result",
            "schema_version": "1",
        },
    )
    values.update(overrides)
    return WorkRequest(**values)


def _expected_work_id(requester: str, key: str) -> str:
    raw = json.dumps(
        [COLLABORATION_PROTOCOL, requester, key],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def test_derive_work_id_matches_exact_protocol_requester_key_digest():
    expected = _expected_work_id("research-agent", "nq-regime-001")
    assert derive_work_id(" research-agent ", " nq-regime-001 ") == expected
    assert len(expected) == 64
    assert expected == expected.lower()


def test_request_normalization_deduplicates_and_sorts_unordered_collections():
    normalized = _request().normalized()
    assert normalized["required_capabilities"] == ["macro", "rates"]
    assert normalized["reviewer_principals"] == ["history-agent", "risk-agent"]
    assert normalized["deadline"] == "2026-10-14T07:30:00Z"
    assert normalized["priority"] == 3
    assert normalized["constraints"] == {"asset": "NQ", "window": "RTH"}


@pytest.mark.parametrize(
    "overrides, match",
    [
        ({"requester_principal": "x" * 65}, "requester_principal"),
        ({"target_id": "x" * 65}, "target_id"),
        ({"idempotency_key": "x" * 129}, "idempotency_key"),
        ({"objective": "x" * 2001}, "objective"),
        ({"priority": True}, "priority"),
        ({"priority": 6}, "priority"),
        ({"constraints": {"bad": float("nan")}}, "constraints"),
        ({"result_contract": {"bad": float("inf")}}, "result_contract"),
    ],
)
def test_request_limits_reject_oversized_identifiers_objective_and_nonfinite_json(overrides, match):
    with pytest.raises(ValueError, match=match):
        _request(**overrides).normalized()


@pytest.mark.parametrize(
    "overrides, match",
    [
        ({"work_kind": "trade"}, "work_kind"),
        ({"target_kind": "capability"}, "target_kind"),
        ({"requester_kind": "broker"}, "requester_kind"),
    ],
)
def test_request_rejects_unknown_work_kind_target_kind_or_principal_kind(overrides, match):
    with pytest.raises(ValueError, match=match):
        _request(**overrides).normalized()


def test_request_material_hash_changes_for_semantic_material_but_not_mapping_order():
    left = _request(constraints={"b": 2, "a": 1}).normalized()
    right = _request(constraints={"a": 1, "b": 2}).normalized()
    changed = _request(constraints={"a": 1, "b": 3}).normalized()

    assert request_material_hash(left) == request_material_hash(right)
    assert request_material_hash(left) != request_material_hash(changed)


def test_build_request_event_uses_reserved_channel_thread_and_correlation():
    request = _request()
    event = build_request_event(
        request,
        observed_at="2026-10-14T00:00:00Z",
        received_at="2026-10-14T00:00:01Z",
        actor_kind="agent",
    )
    normalized = event.normalized()
    work_id = request.work_id()

    assert normalized["channel"] == COLLABORATION_CHANNEL == "collaboration"
    assert normalized["thread_key"] == f"work:{work_id}"
    assert normalized["correlation_id"] == work_id
    assert normalized["source"] == "research-agent"
    assert normalized["source_kind"] == "agent"


def test_request_event_payload_contains_protocol_work_id_transition_and_material_hash():
    request = _request()
    normalized = build_request_event(
        request,
        observed_at="2026-10-14T00:00:00Z",
        received_at="2026-10-14T00:00:01Z",
        actor_kind="agent",
    ).normalized()
    payload = normalized["payload"]

    assert payload["protocol"] == COLLABORATION_PROTOCOL
    assert payload["work_id"] == request.work_id()
    assert payload["transition"] == "requested"
    assert payload["actor_principal"] == "research-agent"
    assert payload["actor_kind"] == "agent"
    assert payload["operation_id"] is None
    assert payload["expected_head_event_id"] is None
    assert payload["request_material_hash"] == request_material_hash(request.normalized())
    assert payload["request"]["objective"] == request.objective


def test_decision_root_maps_to_decision_request_event_type():
    event = build_request_event(
        _request(work_kind="decision"),
        observed_at="2026-10-14T00:00:00Z",
        received_at="2026-10-14T00:00:01Z",
        actor_kind="agent",
    )
    assert event.normalized()["event_type"] == "decision_request"


@pytest.mark.parametrize(
    "requester_kind, actor_kind, expected_event_type",
    [
        ("agent", "agent", "agent_note"),
        ("human", "human", "human_note"),
        ("system", "system", "system"),
    ],
)
def test_nondecision_root_event_type_follows_actor_kind(requester_kind, actor_kind, expected_event_type):
    event = build_request_event(
        _request(requester_kind=requester_kind),
        observed_at="2026-10-14T00:00:00Z",
        received_at="2026-10-14T00:00:01Z",
        actor_kind=actor_kind,
    )
    assert event.normalized()["event_type"] == expected_event_type


def test_root_preserves_assets_evidence_and_parent_causation():
    event = build_request_event(
        _request(parent_work_id="a" * 64, parent_event_id="parent-head"),
        observed_at="2026-10-14T00:00:00Z",
        received_at="2026-10-14T00:00:01Z",
        actor_kind="agent",
        assets=("NQ", "MNQ"),
        evidence_ids=("evidence-2", "evidence-1"),
        parent_causation_ids=("parent-head", "parent-proof"),
    )
    normalized = event.normalized()

    assert normalized["assets"] == ["MNQ", "NQ"]
    assert normalized["evidence_ids"] == ["evidence-1", "evidence-2"]
    assert normalized["causation_ids"] == ["parent-head", "parent-proof"]
    assert "evidence_ids" not in normalized["payload"]
    assert "causation_ids" not in normalized["payload"]


def test_root_payload_is_rejected_above_30_kib():
    request = _request(constraints={"blob": "x" * 31_000})
    with pytest.raises(ValueError, match="30 KiB|30720|payload"):
        build_request_event(
            request,
            observed_at="2026-10-14T00:00:00Z",
            received_at="2026-10-14T00:00:01Z",
            actor_kind="agent",
        )


def test_root_authority_flags_are_false_after_normalization():
    normalized = build_request_event(
        _request(),
        observed_at="2026-10-14T00:00:00Z",
        received_at="2026-10-14T00:00:01Z",
        actor_kind="agent",
    ).normalized()

    assert normalized["execution_authorized"] is False
    assert normalized["production_decision_authorized"] is False


def test_create_work_publishes_through_fabric_and_reprojects_result():
    fabric = IntelligenceFabric()
    collaboration = IntelligenceCollaboration(fabric)
    request = _request(idempotency_key="service-create-001")

    result = collaboration.create_work(
        request,
        observed_at="2026-10-14T00:00:00Z",
        received_at="2026-10-14T00:00:01Z",
        assets=("NQ",),
        evidence_ids=("seed-1",),
    )

    assert result["applied"] is True
    assert result["state"] == "OPEN"
    assert result["head_event_id"] == result["event_id"]
    assert result["sequence"] == 1
    assert result["execution_authorized"] is False
    assert result["production_decision_authorized"] is False
    assert collaboration.snapshot(request.work_id()).root_event_id == result["event_id"]
    assert len(collaboration.history(request.work_id())) == 1


def test_identical_root_retry_reports_duplicate_without_new_semantic_state():
    fabric = IntelligenceFabric()
    collaboration = IntelligenceCollaboration(fabric)
    request = _request(idempotency_key="service-retry-001")
    first = collaboration.create_work(
        request,
        observed_at="2026-10-14T00:00:00Z",
        received_at="2026-10-14T00:00:01Z",
    )
    retry = collaboration.create_work(
        request,
        observed_at="2026-10-14T00:00:00Z",
        received_at="2026-10-14T00:00:01Z",
    )

    assert first["applied"] is True
    assert retry["applied"] is False
    assert retry["conflict_code"] == "duplicate_root"
    assert retry["original_event_id"] == first["event_id"]
    assert retry["event_id"] == first["event_id"]
    assert retry["sequence"] == first["sequence"]
    assert len(collaboration.history(request.work_id())) == 1
    assert collaboration.snapshot(request.work_id()).applied_event_count == 1


def test_conflicting_request_material_is_reported_not_silently_rewritten():
    fabric = IntelligenceFabric()
    collaboration = IntelligenceCollaboration(fabric)
    first_request = _request(idempotency_key="service-conflict-001", objective="Original objective")
    conflicting_request = _request(idempotency_key="service-conflict-001", objective="Conflicting objective")

    first = collaboration.create_work(
        first_request,
        observed_at="2026-10-14T00:00:00Z",
        received_at="2026-10-14T00:00:01Z",
    )
    conflicting = collaboration.create_work(
        conflicting_request,
        observed_at="2026-10-14T00:00:02Z",
        received_at="2026-10-14T00:00:03Z",
    )

    assert first["applied"] is True
    assert conflicting["applied"] is False
    assert conflicting["conflict_code"] == "conflicting_root"
    assert conflicting["event_id"] != first["event_id"]
    assert len(collaboration.history(first_request.work_id())) == 2
    snapshot = collaboration.snapshot(first_request.work_id())
    assert snapshot.objective == "Original objective"
    assert snapshot.head_event_id == first["event_id"]
    assert snapshot.applied_event_count == 1


def test_publication_success_does_not_imply_semantic_application():
    fabric = IntelligenceFabric()
    collaboration = IntelligenceCollaboration(fabric)
    original = _request(idempotency_key="service-append-vs-apply", objective="Canonical objective")
    conflict = _request(idempotency_key="service-append-vs-apply", objective="Stored but not applied")

    first = collaboration.create_work(
        original,
        observed_at="2026-10-14T00:00:00Z",
        received_at="2026-10-14T00:00:01Z",
    )
    second = collaboration.create_work(
        conflict,
        observed_at="2026-10-14T00:00:02Z",
        received_at="2026-10-14T00:00:03Z",
    )

    assert second["sequence"] > first["sequence"]
    assert second["event_id"] in {item["event_id"] for item in collaboration.history(original.work_id())}
    assert second["applied"] is False
    assert second["conflict_code"] == "conflicting_root"
    assert collaboration.snapshot(original.work_id()).head_event_id == first["event_id"]
