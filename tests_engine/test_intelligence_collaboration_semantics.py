from __future__ import annotations

from copy import deepcopy

import pytest

from icarus_engine.intelligence_collaboration import (
    WorkRequest,
    build_request_event,
    project_work,
)


def _root(
    *,
    work_kind: str = "research",
    result_contract=None,
    deadline: str | None = "2026-10-14T06:00:00Z",
    observed_at: str = "2026-10-14T05:00:00Z",
    received_at: str = "2026-10-14T05:00:01Z",
):
    request = WorkRequest(
        requester_principal="requester-agent",
        requester_kind="agent",
        target_kind="principal",
        target_id="worker-agent",
        work_kind=work_kind,
        idempotency_key=f"{work_kind}-001",
        objective="Investigate and return a traceable result.",
        priority=4,
        constraints={"asset": "NQ"},
        reviewer_principals=("reviewer-agent",),
        deadline=deadline,
        result_contract=result_contract,
    )
    event = build_request_event(
        request,
        observed_at=observed_at,
        received_at=received_at,
        actor_kind="agent",
        evidence_ids=("seed",),
    ).normalized()
    return {"sequence": 1, "event_id": "root", "attention_score": 48.0, **event}


def _transition(
    root,
    *,
    sequence: int,
    event_id: str,
    transition: str,
    actor: str,
    expected_head: str,
    data=None,
    evidence=(),
    causes=None,
    event_type: str = "agent_note",
    actor_kind: str = "agent",
    received_at: str | None = None,
):
    work_id = root["payload"]["work_id"]
    return {
        "sequence": sequence,
        "event_id": event_id,
        "attention_score": 0.0,
        "schema_version": root["schema_version"],
        "event_type": event_type,
        "source": actor,
        "source_kind": actor_kind,
        "channel": "collaboration",
        "thread_key": f"work:{work_id}",
        "title": transition,
        "body": transition,
        "observed_at": received_at or f"2026-10-14T05:{sequence:02d}:00Z",
        "received_at": received_at or f"2026-10-14T05:{sequence:02d}:01Z",
        "severity": 0,
        "urgency": 0.0,
        "confidence": None,
        "expires_at": None,
        "assets": [],
        "correlation_id": work_id,
        "causation_ids": list(causes if causes is not None else (expected_head,)),
        "evidence_ids": list(evidence),
        "tags": ["collaboration:v1", f"transition:{transition}"],
        "payload": {
            "protocol": "icarus-collaboration-v1",
            "work_id": work_id,
            "transition": transition,
            "actor_principal": actor,
            "actor_kind": actor_kind,
            "operation_id": f"op-{event_id}",
            "expected_head_event_id": expected_head,
            "data": dict(data or {}),
        },
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


def _accepted(root):
    return _transition(
        root,
        sequence=2,
        event_id="accept",
        transition="accepted",
        actor="worker-agent",
        expected_head="root",
    )


def test_unique_challenge_opens_and_response_closes_exact_challenge():
    root = _root()
    accepted = _accepted(root)
    challenge = _transition(
        root,
        sequence=3,
        event_id="challenge-1",
        transition="challenge",
        actor="requester-agent",
        expected_head="accept",
        data={"challenge_id": "c1", "claim": "Prove the causal direction."},
    )
    response = _transition(
        root,
        sequence=4,
        event_id="response-1",
        transition="challenge_response",
        actor="worker-agent",
        expected_head="challenge-1",
        causes=("challenge-1",),
        data={"challenge_id": "c1", "response": "Evidence supports the direction."},
    )
    snapshot = project_work([root, accepted, challenge, response])
    assert snapshot.open_challenge_ids == ()
    assert snapshot.resolved_challenge_ids == ("c1",)
    assert snapshot.head_event_id == "response-1"


def test_duplicate_challenge_id_does_not_apply():
    root = _root()
    accepted = _accepted(root)
    first = _transition(root, sequence=3, event_id="c1a", transition="challenge", actor="requester-agent", expected_head="accept", data={"challenge_id": "same", "claim": "first"})
    second = _transition(root, sequence=4, event_id="c1b", transition="challenge", actor="requester-agent", expected_head="c1a", data={"challenge_id": "same", "claim": "second"})
    snapshot = project_work([root, accepted, first, second])
    assert snapshot.head_event_id == "c1a"
    assert snapshot.open_challenge_ids == ("same",)
    assert snapshot.conflicts[-1].code == "challenge_mismatch"


def test_challenge_response_requires_current_head_and_original_challenge_causes():
    root = _root()
    accepted = _accepted(root)
    challenge = _transition(root, sequence=3, event_id="challenge", transition="challenge", actor="requester-agent", expected_head="accept", data={"challenge_id": "c1", "claim": "show evidence"})
    evidence = _transition(root, sequence=4, event_id="evidence", transition="evidence_added", actor="worker-agent", expected_head="challenge", evidence=("ev-1",))
    response = _transition(
        root,
        sequence=5,
        event_id="response",
        transition="challenge_response",
        actor="worker-agent",
        expected_head="evidence",
        causes=("evidence",),
        data={"challenge_id": "c1", "response": "answered"},
    )
    snapshot = project_work([root, accepted, challenge, evidence, response])
    assert snapshot.head_event_id == "evidence"
    assert snapshot.open_challenge_ids == ("c1",)
    assert snapshot.conflicts[-1].code == "challenge_mismatch"


def test_unknown_or_already_closed_challenge_response_does_not_apply():
    root = _root()
    accepted = _accepted(root)
    unknown = _transition(root, sequence=3, event_id="unknown", transition="challenge_response", actor="worker-agent", expected_head="accept", data={"challenge_id": "missing", "response": "x"})
    snapshot = project_work([root, accepted, unknown])
    assert snapshot.head_event_id == "accept"
    assert snapshot.conflicts[-1].code == "challenge_mismatch"

    challenge = _transition(root, sequence=3, event_id="challenge", transition="challenge", actor="requester-agent", expected_head="accept", data={"challenge_id": "c1", "claim": "x"})
    response = _transition(root, sequence=4, event_id="response", transition="challenge_response", actor="worker-agent", expected_head="challenge", causes=("challenge",), data={"challenge_id": "c1", "response": "done"})
    second = _transition(root, sequence=5, event_id="response-again", transition="challenge_response", actor="worker-agent", expected_head="response", causes=("response", "challenge"), data={"challenge_id": "c1", "response": "again"})
    snapshot = project_work([root, accepted, challenge, response, second])
    assert snapshot.head_event_id == "response"
    assert snapshot.conflicts[-1].code == "challenge_mismatch"


def test_completion_with_open_challenges_requires_exact_unresolved_set():
    root = _root(result_contract={"result_kind": "json", "required_fields": ["conclusion"]})
    accepted = _accepted(root)
    challenge = _transition(root, sequence=3, event_id="challenge", transition="challenge", actor="requester-agent", expected_head="accept", data={"challenge_id": "c1", "claim": "x"})
    completed = _transition(root, sequence=4, event_id="complete", transition="completed", actor="worker-agent", expected_head="challenge", event_type="research", data={"result": {"conclusion": "supported"}, "unresolved_challenge_ids": []})
    snapshot = project_work([root, accepted, challenge, completed])
    assert snapshot.state == "ACCEPTED"
    assert snapshot.head_event_id == "challenge"
    assert snapshot.conflicts[-1].code == "challenge_mismatch"


def test_completion_can_preserve_explicit_unresolved_disagreement():
    root = _root(result_contract={"result_kind": "json", "required_fields": ["conclusion"]})
    accepted = _accepted(root)
    challenge = _transition(root, sequence=3, event_id="challenge", transition="challenge", actor="requester-agent", expected_head="accept", data={"challenge_id": "c1", "claim": "x"})
    completed = _transition(root, sequence=4, event_id="complete", transition="completed", actor="worker-agent", expected_head="challenge", event_type="research", data={"result": {"conclusion": "supported with disagreement"}, "unresolved_challenge_ids": ["c1"]})
    snapshot = project_work([root, accepted, challenge, completed])
    assert snapshot.state == "COMPLETED"
    assert snapshot.open_challenge_ids == ("c1",)
    assert snapshot.final_result == {"conclusion": "supported with disagreement"}


def test_evidence_accumulates_only_from_applied_events():
    root = _root()
    accepted = _accepted(root)
    applied = _transition(root, sequence=3, event_id="ev-applied", transition="evidence_added", actor="worker-agent", expected_head="accept", evidence=("good",))
    stale = _transition(root, sequence=4, event_id="ev-stale", transition="evidence_added", actor="worker-agent", expected_head="accept", evidence=("bad",))
    snapshot = project_work([root, accepted, applied, stale])
    assert "seed" in snapshot.evidence_ids
    assert "good" in snapshot.evidence_ids
    assert "bad" not in snapshot.evidence_ids


def test_stale_conflicted_event_does_not_add_evidence_or_result():
    root = _root(result_contract={"result_kind": "json", "required_fields": ["conclusion"]})
    accepted = _accepted(root)
    partial = _transition(root, sequence=3, event_id="partial", transition="partial_result", actor="worker-agent", expected_head="accept", event_type="research", evidence=("good",), data={"result": {"conclusion": "first"}})
    stale = _transition(root, sequence=4, event_id="stale", transition="partial_result", actor="worker-agent", expected_head="accept", event_type="research", evidence=("bad",), data={"result": {"conclusion": "stale"}})
    snapshot = project_work([root, accepted, partial, stale])
    assert snapshot.latest_partial_result == {"conclusion": "first"}
    assert "bad" not in snapshot.evidence_ids


def test_json_result_contract_requires_declared_fields():
    root = _root(result_contract={"result_kind": "json", "required_fields": ["conclusion", "score"]})
    accepted = _accepted(root)
    completed = _transition(root, sequence=3, event_id="complete", transition="completed", actor="worker-agent", expected_head="accept", event_type="research", data={"result": {"conclusion": "supported"}, "unresolved_challenge_ids": []})
    snapshot = project_work([root, accepted, completed])
    assert snapshot.state == "ACCEPTED"
    assert snapshot.final_result is None
    assert snapshot.conflicts[-1].code == "result_contract_mismatch"


def test_event_refs_and_evidence_bundle_contracts_require_references():
    event_root = _root(result_contract={"result_kind": "event_refs"})
    accepted = _accepted(event_root)
    completed = _transition(event_root, sequence=3, event_id="complete", transition="completed", actor="worker-agent", expected_head="accept", event_type="research", data={"result": {"event_refs": []}, "unresolved_challenge_ids": []})
    snapshot = project_work([event_root, accepted, completed])
    assert snapshot.conflicts[-1].code == "result_contract_mismatch"

    evidence_root = _root(result_contract={"result_kind": "evidence_bundle"})
    accepted2 = _accepted(evidence_root)
    completed2 = _transition(evidence_root, sequence=3, event_id="complete-2", transition="completed", actor="worker-agent", expected_head="accept", event_type="research", data={"result": {}, "unresolved_challenge_ids": []})
    snapshot2 = project_work([evidence_root, accepted2, completed2])
    assert snapshot2.conflicts[-1].code == "result_contract_mismatch"


def test_decision_completion_requires_decision_response_event_type():
    root = _root(work_kind="decision", result_contract={"result_kind": "decision", "required_fields": ["decision"]})
    accepted = _accepted(root)
    wrong = _transition(root, sequence=3, event_id="wrong", transition="completed", actor="worker-agent", expected_head="accept", event_type="research", data={"result": {"decision": "hold"}, "unresolved_challenge_ids": []})
    snapshot = project_work([root, accepted, wrong])
    assert snapshot.state == "ACCEPTED"
    assert snapshot.conflicts[-1].code == "result_contract_mismatch"

    correct = deepcopy(wrong)
    correct["event_id"] = "correct"
    correct["event_type"] = "decision_response"
    correct["payload"] = dict(correct["payload"], operation_id="op-correct")
    snapshot = project_work([root, accepted, correct])
    assert snapshot.state == "COMPLETED"


def test_nondecision_partial_and_completed_results_require_research_event_type():
    root = _root(result_contract={"result_kind": "json", "required_fields": ["conclusion"]})
    accepted = _accepted(root)
    wrong = _transition(root, sequence=3, event_id="wrong", transition="partial_result", actor="worker-agent", expected_head="accept", event_type="agent_note", data={"result": {"conclusion": "x"}})
    snapshot = project_work([root, accepted, wrong])
    assert snapshot.state == "ACCEPTED"
    assert snapshot.conflicts[-1].code == "result_contract_mismatch"

    partial = deepcopy(wrong)
    partial["event_id"] = "partial"
    partial["event_type"] = "research"
    partial["payload"] = dict(partial["payload"], operation_id="op-partial")
    snapshot = project_work([root, accepted, partial])
    assert snapshot.state == "PARTIAL"


def test_deadline_normalizes_to_utc():
    root = _root(deadline="2026-10-14T01:00:00-05:00")
    snapshot = project_work([root])
    assert snapshot.deadline == "2026-10-14T06:00:00Z"


def test_deadline_before_root_time_is_invalid():
    with pytest.raises(ValueError, match="deadline"):
        _root(deadline="2026-10-14T04:59:59Z")


def test_crossing_deadline_only_sets_derived_deadline_passed():
    root = _root(deadline="2026-10-14T05:10:00Z")
    before = project_work([root], as_of="2026-10-14T05:09:59Z")
    after = project_work([root], as_of="2026-10-14T05:10:01Z")
    assert before.state == after.state == "OPEN"
    assert before.deadline_passed is False
    assert after.deadline_passed is True
    assert before.head_event_id == after.head_event_id == "root"


def test_predeadline_expired_event_is_deadline_violation():
    root = _root(deadline="2026-10-14T05:10:00Z")
    expired = _transition(root, sequence=2, event_id="early", transition="expired", actor="clock-system", actor_kind="system", expected_head="root", received_at="2026-10-14T05:09:00Z")
    snapshot = project_work([root, expired])
    assert snapshot.state == "OPEN"
    assert snapshot.conflicts[-1].code == "deadline_violation"


def test_postdeadline_system_expiry_applies():
    root = _root(deadline="2026-10-14T05:10:00Z")
    expired = _transition(root, sequence=2, event_id="late", transition="expired", actor="clock-system", actor_kind="system", expected_head="root", received_at="2026-10-14T05:10:01Z")
    snapshot = project_work([root, expired])
    assert snapshot.state == "EXPIRED"
    assert snapshot.head_event_id == "late"
