from __future__ import annotations

from copy import deepcopy

import pytest

from icarus_engine.intelligence_collaboration import (
    CollaborationIntegrityError,
    WorkRequest,
    build_request_event,
    project_work,
)


def _root(
    *,
    target_kind: str = "principal",
    target_id: str = "worker-agent",
    requester: str = "requester-agent",
    requester_kind: str = "agent",
    reviewers: tuple[str, ...] = ("reviewer-agent",),
    deadline: str | None = "2026-10-14T06:00:00Z",
    sequence: int = 1,
    event_id: str = "root-event",
):
    request = WorkRequest(
        requester_principal=requester,
        requester_kind=requester_kind,
        target_kind=target_kind,
        target_id=target_id,
        work_kind="research",
        idempotency_key="work-001",
        objective="Investigate the anomaly and preserve evidence.",
        priority=4,
        constraints={"asset": "NQ"},
        required_capabilities=("research",),
        reviewer_principals=reviewers,
        deadline=deadline,
        result_contract={"result_kind": "json", "required_fields": ["conclusion"]},
    )
    event = build_request_event(
        request,
        observed_at="2026-10-14T05:00:00Z",
        received_at="2026-10-14T05:00:01Z",
        actor_kind=requester_kind,
        assets=("NQ",),
        evidence_ids=("seed-evidence",),
    ).normalized()
    return {"sequence": sequence, "event_id": event_id, "attention_score": 48.0, **event}


def _transition(
    root,
    *,
    sequence: int,
    event_id: str,
    transition: str,
    actor: str,
    actor_kind: str = "agent",
    expected_head: str | None = None,
    causes: tuple[str, ...] | None = None,
    evidence: tuple[str, ...] = (),
    data: dict | None = None,
    event_type: str = "agent_note",
):
    work_id = root["payload"]["work_id"]
    head = expected_head or root["event_id"]
    cause_ids = tuple(causes) if causes is not None else (head,)
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
        "observed_at": f"2026-10-14T05:{sequence:02d}:00Z",
        "received_at": f"2026-10-14T05:{sequence:02d}:01Z",
        "severity": 0,
        "urgency": 0.0,
        "confidence": None,
        "expires_at": None,
        "assets": [],
        "correlation_id": work_id,
        "causation_ids": list(cause_ids),
        "evidence_ids": list(evidence),
        "tags": ["collaboration:v1", f"transition:{transition}"],
        "payload": {
            "protocol": "icarus-collaboration-v1",
            "work_id": work_id,
            "transition": transition,
            "actor_principal": actor,
            "actor_kind": actor_kind,
            "operation_id": f"op-{event_id}",
            "expected_head_event_id": head,
            "data": dict(data or {}),
        },
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


def test_project_root_produces_open_snapshot():
    root = _root()
    snapshot = project_work([root])

    assert snapshot.protocol == "icarus-collaboration-v1"
    assert snapshot.work_id == root["payload"]["work_id"]
    assert snapshot.state == "OPEN"
    assert snapshot.requester_principal == "requester-agent"
    assert snapshot.target_kind == "principal"
    assert snapshot.target_id == "worker-agent"
    assert snapshot.assignee is None
    assert snapshot.root_event_id == "root-event"
    assert snapshot.head_event_id == "root-event"
    assert snapshot.applied_event_count == 1
    assert snapshot.evidence_ids == ("seed-evidence",)
    assert snapshot.execution_authorized is False
    assert snapshot.production_decision_authorized is False


def test_principal_target_acceptance_establishes_assignee():
    root = _root()
    accepted = _transition(root, sequence=2, event_id="accept-1", transition="accepted", actor="worker-agent")
    snapshot = project_work([root, accepted])

    assert snapshot.state == "ACCEPTED"
    assert snapshot.assignee == "worker-agent"
    assert snapshot.head_event_id == "accept-1"
    assert snapshot.applied_event_count == 2


def test_principal_target_rejection_is_terminal():
    root = _root()
    rejected = _transition(root, sequence=2, event_id="reject-1", transition="rejected", actor="worker-agent")
    snapshot = project_work([root, rejected])

    assert snapshot.state == "REJECTED"
    assert snapshot.head_event_id == "reject-1"


def test_group_target_first_acceptance_establishes_assignee():
    root = _root(target_kind="group", target_id="researchers")
    accepted = _transition(root, sequence=2, event_id="accept-g", transition="accepted", actor="agent-b")
    snapshot = project_work([root, accepted])

    assert snapshot.state == "ACCEPTED"
    assert snapshot.assignee == "agent-b"


def test_group_member_rejection_is_not_supported():
    root = _root(target_kind="group", target_id="researchers")
    rejected = _transition(root, sequence=2, event_id="reject-g", transition="rejected", actor="agent-b")
    snapshot = project_work([root, rejected])

    assert snapshot.state == "OPEN"
    assert snapshot.head_event_id == "root-event"
    assert snapshot.applied_event_count == 1
    assert snapshot.conflicts[-1].code == "illegal_transition"


def test_accepted_started_partial_started_completion_lifecycle():
    root = _root()
    accepted = _transition(root, sequence=2, event_id="accept", transition="accepted", actor="worker-agent")
    started = _transition(root, sequence=3, event_id="start-1", transition="started", actor="worker-agent", expected_head="accept")
    partial = _transition(
        root,
        sequence=4,
        event_id="partial",
        transition="partial_result",
        actor="worker-agent",
        expected_head="start-1",
        data={"result": {"progress": 0.5}},
    )
    restarted = _transition(root, sequence=5, event_id="start-2", transition="started", actor="worker-agent", expected_head="partial")
    completed = _transition(
        root,
        sequence=6,
        event_id="complete",
        transition="completed",
        actor="worker-agent",
        expected_head="start-2",
        data={"result": {"conclusion": "supported"}, "unresolved_challenge_ids": []},
        event_type="research",
    )
    snapshot = project_work([root, accepted, started, partial, restarted, completed])

    assert snapshot.state == "COMPLETED"
    assert snapshot.head_event_id == "complete"
    assert snapshot.applied_event_count == 6


def test_terminal_state_cannot_be_resurrected():
    root = _root()
    rejected = _transition(root, sequence=2, event_id="reject", transition="rejected", actor="worker-agent")
    late_accept = _transition(root, sequence=3, event_id="late", transition="accepted", actor="worker-agent", expected_head="reject")
    snapshot = project_work([root, rejected, late_accept])

    assert snapshot.state == "REJECTED"
    assert snapshot.head_event_id == "reject"
    assert snapshot.conflicts[-1].code == "illegal_transition"


def test_requester_may_evidence_challenge_escalate_cancel():
    root = _root()
    evidence = _transition(root, sequence=2, event_id="evidence", transition="evidence_added", actor="requester-agent", evidence=("ev-2",))
    challenge = _transition(
        root,
        sequence=3,
        event_id="challenge",
        transition="challenge",
        actor="requester-agent",
        expected_head="evidence",
        data={"challenge_id": "c1", "claim": "Show the causal link."},
    )
    escalated = _transition(root, sequence=4, event_id="escalate", transition="escalated", actor="requester-agent", expected_head="challenge")
    cancelled = _transition(root, sequence=5, event_id="cancel", transition="cancelled", actor="requester-agent", expected_head="escalate")
    snapshot = project_work([root, evidence, challenge, escalated, cancelled])

    assert snapshot.state == "CANCELLED"
    assert snapshot.head_event_id == "cancel"
    assert "ev-2" in snapshot.evidence_ids
    assert snapshot.escalated is True


def test_assignee_only_started_partial_complete_fail():
    root = _root()
    accepted = _transition(root, sequence=2, event_id="accept", transition="accepted", actor="worker-agent")
    bad_start = _transition(root, sequence=3, event_id="bad-start", transition="started", actor="requester-agent", expected_head="accept")
    good_start = _transition(root, sequence=4, event_id="good-start", transition="started", actor="worker-agent", expected_head="accept")
    snapshot = project_work([root, accepted, bad_start, good_start])

    assert snapshot.state == "IN_PROGRESS"
    assert snapshot.head_event_id == "good-start"
    assert snapshot.conflicts[0].code == "actor_not_permitted"


def test_declared_reviewer_may_evidence_challenge_escalate_only():
    root = _root()
    evidence = _transition(root, sequence=2, event_id="rev-ev", transition="evidence_added", actor="reviewer-agent", evidence=("review-evidence",))
    illegal_accept = _transition(root, sequence=3, event_id="rev-accept", transition="accepted", actor="reviewer-agent", expected_head="rev-ev")
    snapshot = project_work([root, evidence, illegal_accept])

    assert snapshot.state == "OPEN"
    assert snapshot.head_event_id == "rev-ev"
    assert "review-evidence" in snapshot.evidence_ids
    assert snapshot.conflicts[-1].code == "actor_not_permitted"


def test_nonroot_requires_expected_current_head_and_cause():
    root = _root()
    missing_cause = _transition(
        root,
        sequence=2,
        event_id="no-cause",
        transition="accepted",
        actor="worker-agent",
        causes=(),
    )
    snapshot = project_work([root, missing_cause])
    assert snapshot.state == "OPEN"
    assert snapshot.conflicts[-1].code == "missing_required_cause"

    wrong_head = _transition(
        root,
        sequence=2,
        event_id="wrong-head",
        transition="accepted",
        actor="worker-agent",
        expected_head="not-current",
        causes=("not-current",),
    )
    snapshot = project_work([root, wrong_head])
    assert snapshot.state == "OPEN"
    assert snapshot.conflicts[-1].code == "stale_head"


def test_system_expiry_requires_deadline_and_system_actor():
    root = _root(deadline="2026-10-14T05:10:00Z")
    premature = _transition(
        root,
        sequence=2,
        event_id="premature",
        transition="expired",
        actor="clock-system",
        actor_kind="system",
    )
    premature["observed_at"] = "2026-10-14T05:05:00Z"
    premature["received_at"] = "2026-10-14T05:05:01Z"
    snapshot = project_work([root, premature])
    assert snapshot.state == "OPEN"
    assert snapshot.conflicts[-1].code == "deadline_violation"

    late = deepcopy(premature)
    late["sequence"] = 3
    late["event_id"] = "expired"
    late["observed_at"] = "2026-10-14T05:11:00Z"
    late["received_at"] = "2026-10-14T05:11:01Z"
    late["payload"] = dict(late["payload"], operation_id="op-expired")
    snapshot = project_work([root, late])
    assert snapshot.state == "EXPIRED"


def test_actor_permission_is_semantic_only_not_authentication_claim():
    root = _root(target_kind="group", target_id="researchers")
    accepted = _transition(root, sequence=2, event_id="accept", transition="accepted", actor="declared-agent")
    snapshot = project_work([root, accepted])

    assert snapshot.assignee == "declared-agent"
    assert snapshot.integrity_status == "ok"
    assert snapshot.execution_authorized is False


def test_empty_history_is_unknown_work():
    with pytest.raises(ValueError, match="unknown work|empty"):
        project_work([])


def test_malformed_root_authority_violation_fails_closed():
    root = _root()
    root["execution_authorized"] = True
    with pytest.raises(CollaborationIntegrityError):
        project_work([root])
