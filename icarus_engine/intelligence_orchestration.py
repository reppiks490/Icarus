"""Phase 4D bounded work decomposition and evidence-preserving review councils."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from .intelligence_collaboration import (
    IntelligenceCollaboration,
    TransitionRequest,
    WorkRequest,
    WorkSnapshot,
    _text,
)

MAX_CHILD_WORK = 16
MAX_COUNCIL_CLAIM = 2000


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


@dataclass(frozen=True)
class DecompositionTask:
    target_principal: str
    work_kind: str
    objective: str
    required_capabilities: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()

    def normalized(self) -> dict[str, object]:
        target = _text(self.target_principal, "target_principal", 64)
        objective = _text(self.objective, "objective", 2000)
        kind = _text(self.work_kind, "work_kind", 64).lower()
        if isinstance(self.required_capabilities, (str, bytes)) or isinstance(self.evidence_ids, (str, bytes)):
            raise ValueError("capabilities and evidence_ids must be collections")
        capabilities = tuple(sorted({_text(item, "capability", 64).lower() for item in self.required_capabilities}))
        evidence = tuple(sorted({_text(item, "evidence_id", 240) for item in self.evidence_ids}))
        if len(capabilities) > 32 or len(evidence) > 64:
            raise ValueError("decomposition task exceeds collection bounds")
        return {"target_principal": target, "work_kind": kind, "objective": objective,
                "required_capabilities": list(capabilities), "evidence_ids": list(evidence)}


def decompose_work(
    collaboration: IntelligenceCollaboration,
    *,
    parent_work_id: str,
    actor_principal: str,
    actor_kind: str,
    decomposition_id: str | None = None,
    tasks: Sequence[DecompositionTask] | None = None,
    observed_at: str,
) -> dict[str, object]:
    """Create explicit, idempotent child work under the current parent head."""
    parent = collaboration.snapshot(parent_work_id)
    if parent.assignee != actor_principal or parent.state not in {"ACCEPTED", "IN_PROGRESS", "PARTIAL"}:
        raise ValueError("only the active assignee may decompose nonterminal work")
    if tasks is None:
        contract = parent.constraints.get("decomposition_plan")
        if not isinstance(contract, Mapping) or set(contract) - {"plan_id", "tasks"} or not isinstance(contract.get("tasks"), list):
            raise ValueError("work has no bounded decomposition_plan contract")
        raw_tasks = contract["tasks"]
        if any(not isinstance(item, Mapping) or set(item) - {"target_principal", "work_kind", "objective", "required_capabilities", "evidence_ids"} for item in raw_tasks):
            raise ValueError("decomposition_plan contains an invalid task")
        tasks = [DecompositionTask(**item) for item in raw_tasks]
        if decomposition_id is None:
            decomposition_id = str(contract.get("plan_id") or hashlib.sha256(_canonical(contract).encode("utf-8")).hexdigest())
    if decomposition_id is None:
        raise ValueError("decomposition_id is required when tasks are supplied")
    if not isinstance(tasks, Sequence) or isinstance(tasks, (str, bytes)) or not 1 <= len(tasks) <= MAX_CHILD_WORK:
        raise ValueError("tasks must contain 1..16 decomposition entries")
    plan_id = _text(decomposition_id, "decomposition_id", 128)
    normalized = [task.normalized() if isinstance(task, DecompositionTask) else None for task in tasks]
    if any(item is None for item in normalized):
        raise ValueError("every decomposition entry must be a DecompositionTask")
    if len({_canonical(item) for item in normalized}) != len(normalized):
        raise ValueError("duplicate decomposition task")
    # Keep child idempotency stable even if a retry happens after another
    # parent transition; Phase 4A will record changed parent linkage as a root
    # conflict instead of creating a second child with the same plan index.
    base = hashlib.sha256(_canonical([parent.work_id, plan_id]).encode("utf-8")).hexdigest()
    children = []
    for index, material in enumerate(normalized):
        assert material is not None
        request = WorkRequest(
            requester_principal=actor_principal,
            requester_kind=actor_kind,
            target_kind="principal",
            target_id=str(material["target_principal"]),
            work_kind=str(material["work_kind"]),
            idempotency_key=f"decomp:{base}:{index}",
            objective=str(material["objective"]),
            priority=parent.priority,
            constraints={"decomposition_id": plan_id, "decomposition_index": index},
            required_capabilities=tuple(str(x) for x in material["required_capabilities"]),
            reviewer_principals=parent.reviewer_principals,
            parent_work_id=parent.work_id,
            parent_event_id=parent.head_event_id,
        )
        child = collaboration.create_work(
            request,
            observed_at=observed_at,
            received_at=observed_at,
            evidence_ids=tuple(str(x) for x in material["evidence_ids"]),
        )
        child["work_id"] = request.work_id()
        children.append(child)
    return {"parent_work_id": parent.work_id, "parent_head_event_id": parent.head_event_id,
            "decomposition_id": plan_id, "children": children,
            "execution_authorized": False, "production_decision_authorized": False}


def cast_council_review(
    collaboration: IntelligenceCollaboration,
    *,
    work_id: str,
    actor_principal: str,
    actor_kind: str,
    council_id: str,
    vote: str,
    claim: str,
    operation_id: str,
    evidence_ids: Iterable[str] = (),
    observed_at: str,
) -> dict[str, object]:
    """Record an eligible review as a normal immutable Phase 4A evidence event."""
    snapshot = collaboration.snapshot(work_id)
    actor = _text(actor_principal, "actor_principal", 64)
    if actor not in snapshot.reviewer_principals:
        raise ValueError("only a declared reviewer may vote in this council")
    normalized_vote = _text(vote, "vote", 32).lower()
    if normalized_vote not in {"support", "challenge", "abstain"}:
        raise ValueError("vote must be support, challenge, or abstain")
    body = _text(claim, "claim", MAX_COUNCIL_CLAIM)
    transition = TransitionRequest(
        work_id=work_id,
        transition="evidence_added",
        actor_principal=actor,
        actor_kind=actor_kind,
        operation_id=_text(operation_id, "operation_id", 128),
        expected_head_event_id=snapshot.head_event_id,
        data={"council": {"council_id": _text(council_id, "council_id", 128), "vote": normalized_vote, "claim": body}},
        evidence_ids=tuple(evidence_ids),
    )
    return collaboration.append_transition(transition, observed_at=observed_at, received_at=observed_at)


def council_projection(snapshot: WorkSnapshot, history: Sequence[Mapping[str, object]], *, council_id: str) -> dict[str, object]:
    """Project council votes while preserving every eligible dissenting claim."""
    target_id = _text(council_id, "council_id", 128)
    expected = set(snapshot.reviewer_principals)
    rejected_event_ids = {conflict.event_id for conflict in snapshot.conflicts}
    votes: dict[str, dict[str, object]] = {}
    conflicts = []
    for event in sorted(history, key=lambda row: int(row.get("sequence", 0))):
        if str(event.get("event_id")) in rejected_event_ids:
            continue
        payload = event.get("payload")
        if not isinstance(payload, Mapping) or payload.get("transition") != "evidence_added":
            continue
        data = payload.get("data")
        council = data.get("council") if isinstance(data, Mapping) else None
        if not isinstance(council, Mapping) or council.get("council_id") != target_id:
            continue
        actor = payload.get("actor_principal")
        vote = council.get("vote")
        claim = council.get("claim")
        if actor not in expected or vote not in {"support", "challenge", "abstain"} or not isinstance(claim, str) or not claim.strip():
            conflicts.append(str(event.get("event_id", "unknown")))
            continue
        if actor in votes:
            conflicts.append(str(event.get("event_id", "unknown")))
            continue
        votes[str(actor)] = {"vote": vote, "claim": claim.strip(), "event_id": event.get("event_id"),
                             "sequence": event.get("sequence"), "evidence_ids": list(event.get("evidence_ids") or ())}
    support = sum(item["vote"] == "support" for item in votes.values())
    challenge = sum(item["vote"] == "challenge" for item in votes.values())
    abstain = sum(item["vote"] == "abstain" for item in votes.values())
    quorum = bool(expected) and len(votes) >= (len(expected) // 2 + 1)
    return {
        "council_id": target_id,
        "declared_reviewers": sorted(expected),
        "received_reviewers": sorted(votes),
        "missing_reviewers": sorted(expected - set(votes)),
        "votes": votes,
        "support_count": support,
        "challenge_count": challenge,
        "abstain_count": abstain,
        "quorum_met": quorum,
        "outcome": ("contested" if support and challenge else "support" if support else "challenge" if challenge else "undetermined") if quorum else "pending",
        "conflicting_vote_event_ids": conflicts,
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


def synthesize_work(
    collaboration: IntelligenceCollaboration,
    *,
    work_id: str,
    actor_principal: str,
    actor_kind: str,
    operation_id: str,
    child_work_ids: Sequence[str],
    summary: str,
    observed_at: str,
    complete: bool = False,
) -> dict[str, object]:
    """Record an evidence-linked partial result or completion over child outputs."""
    parent = collaboration.snapshot(work_id)
    if parent.assignee != actor_principal:
        raise ValueError("only the assignee may synthesize this work")
    if not isinstance(child_work_ids, Sequence) or isinstance(child_work_ids, (str, bytes)) or not 1 <= len(child_work_ids) <= MAX_CHILD_WORK:
        raise ValueError("child_work_ids must contain 1..16 items")
    normalized_child_ids = [_text(child_id, "child_work_id", 64) for child_id in child_work_ids]
    if len(set(normalized_child_ids)) != len(normalized_child_ids):
        raise ValueError("child_work_ids must be unique")
    refs = []
    child_event_ids = []
    for child_id in normalized_child_ids:
        child = collaboration.snapshot(child_id)
        if child.parent_work_id != parent.work_id:
            raise ValueError("synthesis may reference only direct child work")
        if child.final_result is None and child.latest_partial_result is None:
            raise ValueError("each child must have a partial or final result")
        if complete and child.state != "COMPLETED":
            raise ValueError("completion requires every child work item to be completed")
        refs.append({"work_id": child.work_id, "state": child.state, "head_event_id": child.head_event_id,
                     "result": child.final_result if child.final_result is not None else child.latest_partial_result})
        child_event_ids.append(child.head_event_id)
    result = {"summary": _text(summary, "summary", MAX_COUNCIL_CLAIM), "child_results": refs,
              "event_refs": sorted(set(child_event_ids))}
    data: dict[str, object] = {"result": result}
    transition_name = "completed" if complete else "partial_result"
    if complete:
        data["unresolved_challenge_ids"] = list(parent.open_challenge_ids)
    transition = TransitionRequest(
        work_id=parent.work_id,
        transition=transition_name,
        actor_principal=actor_principal,
        actor_kind=actor_kind,
        operation_id=operation_id,
        expected_head_event_id=parent.head_event_id,
        data=data,
        evidence_ids=tuple(sorted(set(child_event_ids))),
        additional_causation_ids=tuple(sorted(set(child_event_ids))),
    )
    emitted = collaboration.append_transition(transition, observed_at=observed_at, received_at=observed_at)
    return {"result": emitted, "work": collaboration.snapshot(work_id),
            "execution_authorized": False, "production_decision_authorized": False}
