"""Machine-native semantic collaboration over the ICARUS Intelligence Fabric.

Phase 4A uses Phase 1 IntelligenceEvent records as the only canonical journal.
This module does not authorize execution or production decisions.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Sequence

from icarus_engine.intelligence_fabric import IntelligenceEvent, IntelligenceFabric

COLLABORATION_PROTOCOL = "icarus-collaboration-v1"
COLLABORATION_CHANNEL = "collaboration"
MAX_PRINCIPAL = 64
MAX_TARGET = 64
MAX_IDEMPOTENCY_KEY = 128
MAX_OPERATION_ID = 128
MAX_CHALLENGE_ID = 128
MAX_CAPABILITY = 64
MAX_REVIEWERS = 32
MAX_CAPABILITIES = 32
MAX_OBJECTIVE = 2000
MAX_COLLABORATION_PAYLOAD_BYTES = 30 * 1024

PRINCIPAL_KINDS = {"agent", "human", "system"}
TARGET_KINDS = {"principal", "group"}
WORK_KINDS = {
    "research",
    "evidence",
    "investigation",
    "model_review",
    "risk_review",
    "hypothesis_challenge",
    "cross_verification",
    "decision",
    "delegation",
    "synthesis",
}
TERMINAL_STATES = {"COMPLETED", "FAILED", "REJECTED", "CANCELLED", "EXPIRED"}


class CollaborationIntegrityError(ValueError):
    """Raised when a reserved work thread cannot be projected safely."""


@dataclass(frozen=True)
class WorkConflict:
    event_id: str
    sequence: int
    code: str
    operation_id: str | None = None


@dataclass(frozen=True)
class WorkSnapshot:
    protocol: str
    work_id: str
    work_kind: str
    requester_principal: str
    requester_kind: str
    target_kind: str
    target_id: str
    assignee: str | None
    parent_work_id: str | None
    parent_event_id: str | None
    state: str
    root_event_id: str
    head_event_id: str
    created_at: str
    updated_at: str
    deadline: str | None
    deadline_passed: bool
    priority: int
    objective: str
    constraints: Mapping[str, Any]
    required_capabilities: tuple[str, ...]
    reviewer_principals: tuple[str, ...]
    result_contract: Mapping[str, Any] | None
    latest_partial_result: Any | None
    final_result: Any | None
    evidence_ids: tuple[str, ...]
    open_challenge_ids: tuple[str, ...]
    resolved_challenge_ids: tuple[str, ...]
    escalated: bool
    applied_event_count: int
    conflicts: tuple[WorkConflict, ...]
    integrity_status: str
    execution_authorized: bool = False
    production_decision_authorized: bool = False


def _text(value: Any, name: str, limit: int) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    out = value.strip()
    if not out:
        raise ValueError(f"{name} is required")
    if len(out) > limit:
        raise ValueError(f"{name} exceeds {limit} characters")
    return out


def _optional_text(value: Any, name: str, limit: int) -> str | None:
    if value is None:
        return None
    return _text(value, name, limit)


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("value must be finite JSON") from exc


def _finite_json_mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{name} must be a mapping")
    material = dict(value)
    try:
        _canonical_json(material)
    except ValueError as exc:
        raise ValueError(f"{name} must be finite JSON") from exc
    return material


def _time_text(value: Any, name: str) -> str:
    text = _text(value, name, 80)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{name} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _bounded_items(
    values: Iterable[str] | None,
    name: str,
    *,
    item_limit: int,
    count_limit: int,
) -> tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{name} must be a collection")
    try:
        items = tuple(values)
    except TypeError as exc:
        raise ValueError(f"{name} must be a collection") from exc
    if len(items) > count_limit:
        raise ValueError(f"{name} exceeds {count_limit} items")
    return tuple(sorted({_text(item, f"{name} item", item_limit) for item in items}))


def _priority(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 5:
        raise ValueError("priority must be an integer in [0, 5]")
    return value


def _lower_enum(value: Any, name: str, allowed: set[str], limit: int = 64) -> str:
    out = _text(value, name, limit).lower()
    if out not in allowed:
        raise ValueError(f"unsupported {name}")
    return out


def _work_id(value: Any, name: str = "work_id") -> str:
    out = _text(value, name, 64).lower()
    if len(out) != 64 or any(ch not in "0123456789abcdef" for ch in out):
        raise ValueError(f"{name} must be 64 lowercase hexadecimal characters")
    return out


def _sha256_json(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def derive_work_id(requester_principal: str, idempotency_key: str) -> str:
    requester = _text(requester_principal, "requester_principal", MAX_PRINCIPAL)
    key = _text(idempotency_key, "idempotency_key", MAX_IDEMPOTENCY_KEY)
    return _sha256_json([COLLABORATION_PROTOCOL, requester, key])


def request_material_hash(material: Mapping[str, object]) -> str:
    normalized = _finite_json_mapping(material, "request material")
    return _sha256_json(normalized)


@dataclass(frozen=True)
class WorkRequest:
    requester_principal: str
    requester_kind: str
    target_kind: str
    target_id: str
    work_kind: str
    idempotency_key: str
    objective: str
    priority: int = 0
    constraints: Mapping[str, object] = field(default_factory=dict)
    required_capabilities: tuple[str, ...] = ()
    reviewer_principals: tuple[str, ...] = ()
    deadline: str | None = None
    result_contract: Mapping[str, object] | None = None
    parent_work_id: str | None = None
    parent_event_id: str | None = None

    def normalized(self) -> dict[str, object]:
        requester = _text(self.requester_principal, "requester_principal", MAX_PRINCIPAL)
        requester_kind = _lower_enum(self.requester_kind, "requester_kind", PRINCIPAL_KINDS)
        target_kind = _lower_enum(self.target_kind, "target_kind", TARGET_KINDS)
        target_id = _text(self.target_id, "target_id", MAX_TARGET)
        work_kind = _lower_enum(self.work_kind, "work_kind", WORK_KINDS)
        key = _text(self.idempotency_key, "idempotency_key", MAX_IDEMPOTENCY_KEY)
        objective = _text(self.objective, "objective", MAX_OBJECTIVE)
        constraints = _finite_json_mapping(self.constraints, "constraints")
        capabilities = _bounded_items(
            self.required_capabilities,
            "required_capabilities",
            item_limit=MAX_CAPABILITY,
            count_limit=MAX_CAPABILITIES,
        )
        reviewers = _bounded_items(
            self.reviewer_principals,
            "reviewer_principals",
            item_limit=MAX_PRINCIPAL,
            count_limit=MAX_REVIEWERS,
        )
        deadline = _time_text(self.deadline, "deadline") if self.deadline is not None else None
        result_contract = (
            _finite_json_mapping(self.result_contract, "result_contract")
            if self.result_contract is not None
            else None
        )
        parent_work_id = _work_id(self.parent_work_id, "parent_work_id") if self.parent_work_id is not None else None
        parent_event_id = _optional_text(self.parent_event_id, "parent_event_id", 240)
        if (parent_work_id is None) != (parent_event_id is None):
            raise ValueError("parent_work_id and parent_event_id must be supplied together")

        material: dict[str, object] = {
            "requester_principal": requester,
            "requester_kind": requester_kind,
            "target_kind": target_kind,
            "target_id": target_id,
            "work_kind": work_kind,
            "idempotency_key": key,
            "objective": objective,
            "priority": _priority(self.priority),
            "constraints": constraints,
            "required_capabilities": list(capabilities),
            "reviewer_principals": list(reviewers),
            "deadline": deadline,
            "result_contract": result_contract,
            "parent_work_id": parent_work_id,
            "parent_event_id": parent_event_id,
        }
        _canonical_json(material)
        return material

    def work_id(self) -> str:
        return derive_work_id(self.requester_principal, self.idempotency_key)


def _event_type_for_root(work_kind: str, actor_kind: str) -> str:
    if work_kind == "decision":
        return "decision_request"
    return {
        "agent": "agent_note",
        "human": "human_note",
        "system": "system",
    }[actor_kind]


def _payload_size(payload: Mapping[str, Any]) -> int:
    return len(_canonical_json(dict(payload)).encode("utf-8"))


def build_request_event(
    request: WorkRequest,
    *,
    observed_at: str,
    received_at: str,
    actor_kind: str,
    assets: Iterable[str] = (),
    evidence_ids: Iterable[str] = (),
    parent_causation_ids: Iterable[str] = (),
) -> IntelligenceEvent:
    if not isinstance(request, WorkRequest):
        raise ValueError("request must be WorkRequest")
    material = request.normalized()
    actor = _lower_enum(actor_kind, "actor_kind", PRINCIPAL_KINDS)
    if actor != material["requester_kind"]:
        raise ValueError("actor_kind must match requester_kind for a root request")

    work_id = request.work_id()
    digest = request_material_hash(material)
    payload: dict[str, Any] = {
        "protocol": COLLABORATION_PROTOCOL,
        "work_id": work_id,
        "transition": "requested",
        "actor_principal": material["requester_principal"],
        "actor_kind": actor,
        "operation_id": None,
        "expected_head_event_id": None,
        "request_material_hash": digest,
        "request": material,
    }
    size = _payload_size(payload)
    if size > MAX_COLLABORATION_PAYLOAD_BYTES:
        raise ValueError(
            f"collaboration payload exceeds 30 KiB ({MAX_COLLABORATION_PAYLOAD_BYTES} bytes)"
        )

    causes = set(_bounded_items(
        parent_causation_ids,
        "parent_causation_ids",
        item_limit=240,
        count_limit=64,
    ))
    parent_event_id = material.get("parent_event_id")
    if isinstance(parent_event_id, str):
        causes.add(parent_event_id)

    tags = {
        "collaboration:v1",
        f"work-kind:{material['work_kind']}",
        f"requester:{material['requester_principal']}",
        f"transition:requested",
    }
    if material["target_kind"] == "principal":
        tags.add(f"to:{material['target_id']}")
    else:
        tags.add(f"group:{material['target_id']}")
    parent_work_id = material.get("parent_work_id")
    if isinstance(parent_work_id, str):
        tags.add(f"parent:{parent_work_id}")

    objective = str(material["objective"])
    work_kind = str(material["work_kind"])
    priority = int(material["priority"])
    return IntelligenceEvent(
        event_type=_event_type_for_root(work_kind, actor),
        source=str(material["requester_principal"]),
        source_kind=actor,
        channel=COLLABORATION_CHANNEL,
        thread_key=f"work:{work_id}",
        title=f"Work request: {work_kind}",
        body=objective,
        observed_at=observed_at,
        received_at=received_at,
        severity=priority,
        urgency=0.0,
        confidence=None,
        assets=tuple(assets),
        correlation_id=work_id,
        causation_ids=tuple(sorted(causes)),
        evidence_ids=tuple(evidence_ids),
        tags=tuple(sorted(tags)),
        payload=payload,
    )


def _integrity(condition: bool, message: str) -> None:
    if not condition:
        raise CollaborationIntegrityError(message)


def _event_identity(event: Mapping[str, Any]) -> tuple[int, str]:
    sequence = event.get("sequence")
    event_id = event.get("event_id")
    _integrity(isinstance(sequence, int) and not isinstance(sequence, bool) and sequence >= 1, "invalid sequence")
    _integrity(isinstance(event_id, str) and bool(event_id.strip()), "invalid event_id")
    return int(sequence), str(event_id)


def _validate_envelope(event: Mapping[str, Any], work_id: str | None = None) -> tuple[dict[str, Any], int, str]:
    _integrity(isinstance(event, Mapping), "event must be a mapping")
    sequence, event_id = _event_identity(event)
    _integrity(event.get("execution_authorized") is False, "execution authority violation")
    _integrity(event.get("production_decision_authorized") is False, "production decision authority violation")
    _integrity(event.get("channel") == COLLABORATION_CHANNEL, "foreign event in collaboration thread")
    payload = event.get("payload")
    _integrity(isinstance(payload, Mapping), "collaboration payload must be a mapping")
    payload = dict(payload)
    _integrity(payload.get("protocol") == COLLABORATION_PROTOCOL, "unsupported collaboration protocol")
    event_work_id = payload.get("work_id")
    _integrity(isinstance(event_work_id, str), "missing work_id")
    try:
        normalized_work_id = _work_id(event_work_id)
    except ValueError as exc:
        raise CollaborationIntegrityError(str(exc)) from exc
    if work_id is not None:
        _integrity(normalized_work_id == work_id, "work_id mismatch")
    _integrity(event.get("thread_key") == f"work:{normalized_work_id}", "thread/work mismatch")
    _integrity(event.get("correlation_id") == normalized_work_id, "correlation/work mismatch")
    actor = payload.get("actor_principal")
    actor_kind = payload.get("actor_kind")
    _integrity(isinstance(actor, str) and bool(actor.strip()), "invalid actor_principal")
    _integrity(actor_kind in PRINCIPAL_KINDS, "invalid actor_kind")
    _integrity(event.get("source") == actor, "source/actor mismatch")
    _integrity(event.get("source_kind") == actor_kind, "source_kind/actor_kind mismatch")
    try:
        _canonical_json(payload)
    except ValueError as exc:
        raise CollaborationIntegrityError("collaboration payload must be finite JSON") from exc
    return payload, sequence, event_id


def _conflict(event: Mapping[str, Any], code: str, operation_id: str | None = None) -> WorkConflict:
    sequence, event_id = _event_identity(event)
    return WorkConflict(event_id=event_id, sequence=sequence, code=code, operation_id=operation_id)


def _actor_can_apply(
    transition: str,
    actor: str,
    actor_kind: str,
    *,
    requester: str,
    target_kind: str,
    target_id: str,
    assignee: str | None,
    reviewers: set[str],
    state: str,
) -> bool:
    if transition == "expired":
        return actor_kind == "system"
    if transition == "cancelled":
        return actor == requester
    if transition in {"accepted", "rejected"}:
        if state != "OPEN":
            return False
        if target_kind == "principal":
            return actor == target_id
        return transition == "accepted"
    if actor == requester and transition in {"evidence_added", "challenge", "escalated"}:
        return True
    if actor in reviewers and transition in {"evidence_added", "challenge", "escalated"}:
        return True
    if assignee is not None and actor == assignee and transition in {
        "started",
        "evidence_added",
        "partial_result",
        "challenge_response",
        "escalated",
        "completed",
        "failed",
    }:
        return True
    return False


def _transition_state(state: str, transition: str, *, target_kind: str) -> str | None:
    if state in TERMINAL_STATES:
        return None
    if transition == "accepted" and state == "OPEN":
        return "ACCEPTED"
    if transition == "rejected" and state == "OPEN" and target_kind == "principal":
        return "REJECTED"
    if transition == "started" and state in {"ACCEPTED", "PARTIAL"}:
        return "IN_PROGRESS"
    if transition == "partial_result" and state in {"ACCEPTED", "IN_PROGRESS", "PARTIAL"}:
        return "PARTIAL"
    if transition == "completed" and state in {"ACCEPTED", "IN_PROGRESS", "PARTIAL"}:
        return "COMPLETED"
    if transition == "failed" and state in {"ACCEPTED", "IN_PROGRESS", "PARTIAL"}:
        return "FAILED"
    if transition == "cancelled":
        return "CANCELLED"
    if transition == "expired":
        return "EXPIRED"
    if transition in {"evidence_added", "challenge", "challenge_response", "escalated"}:
        return state
    return None


def project_work(
    events: Sequence[Mapping[str, object]],
    *,
    as_of: str | None = None,
) -> WorkSnapshot:
    if not events:
        raise ValueError("unknown work: empty history")

    ordered = sorted(events, key=lambda item: int(item.get("sequence", 0)))
    root_payload, root_sequence, root_event_id = _validate_envelope(ordered[0])
    _integrity(root_payload.get("transition") == "requested", "first collaboration event must be requested")
    work_id = str(root_payload["work_id"])
    request = root_payload.get("request")
    _integrity(isinstance(request, Mapping), "root request material missing")
    request = dict(request)
    try:
        expected_work_id = derive_work_id(str(request.get("requester_principal", "")), str(request.get("idempotency_key", "")))
        normalized_request = WorkRequest(
            requester_principal=request.get("requester_principal"),
            requester_kind=request.get("requester_kind"),
            target_kind=request.get("target_kind"),
            target_id=request.get("target_id"),
            work_kind=request.get("work_kind"),
            idempotency_key=request.get("idempotency_key"),
            objective=request.get("objective"),
            priority=request.get("priority", 0),
            constraints=request.get("constraints", {}),
            required_capabilities=tuple(request.get("required_capabilities", ()) or ()),
            reviewer_principals=tuple(request.get("reviewer_principals", ()) or ()),
            deadline=request.get("deadline"),
            result_contract=request.get("result_contract"),
            parent_work_id=request.get("parent_work_id"),
            parent_event_id=request.get("parent_event_id"),
        ).normalized()
    except (TypeError, ValueError) as exc:
        raise CollaborationIntegrityError(f"invalid root request material: {exc}") from exc
    _integrity(expected_work_id == work_id, "derived work_id mismatch")
    _integrity(root_payload.get("request_material_hash") == request_material_hash(normalized_request), "request material hash mismatch")

    requester = str(normalized_request["requester_principal"])
    requester_kind = str(normalized_request["requester_kind"])
    target_kind = str(normalized_request["target_kind"])
    target_id = str(normalized_request["target_id"])
    reviewers = set(normalized_request["reviewer_principals"])
    state = "OPEN"
    assignee: str | None = None
    head_event_id = root_event_id
    updated_at = str(ordered[0].get("received_at"))
    applied_count = 1
    conflicts: list[WorkConflict] = []
    evidence = set(str(item) for item in (ordered[0].get("evidence_ids") or ()))
    open_challenges: set[str] = set()
    resolved_challenges: set[str] = set()
    latest_partial_result: Any | None = None
    final_result: Any | None = None
    escalated = False
    deadline = normalized_request.get("deadline")

    last_sequence = root_sequence
    for event in ordered[1:]:
        payload, sequence, event_id = _validate_envelope(event, work_id)
        _integrity(sequence > last_sequence, "events must have unique ascending sequence")
        last_sequence = sequence
        transition = payload.get("transition")
        _integrity(isinstance(transition, str) and transition != "requested", "invalid non-root transition")
        actor = str(payload["actor_principal"])
        actor_kind = str(payload["actor_kind"])
        operation_id_raw = payload.get("operation_id")
        expected_head_raw = payload.get("expected_head_event_id")
        try:
            operation_id = _text(operation_id_raw, "operation_id", MAX_OPERATION_ID)
            expected_head = _text(expected_head_raw, "expected_head_event_id", 240)
        except ValueError as exc:
            raise CollaborationIntegrityError(str(exc)) from exc

        if expected_head != head_event_id:
            conflicts.append(_conflict(event, "stale_head", operation_id))
            continue
        causes = event.get("causation_ids") or ()
        if isinstance(causes, (str, bytes)) or expected_head not in set(causes):
            conflicts.append(_conflict(event, "missing_required_cause", operation_id))
            continue
        if state in TERMINAL_STATES:
            conflicts.append(_conflict(event, "illegal_transition", operation_id))
            continue
        if not _actor_can_apply(
            transition,
            actor,
            actor_kind,
            requester=requester,
            target_kind=target_kind,
            target_id=target_id,
            assignee=assignee,
            reviewers=reviewers,
            state=state,
        ):
            if transition == "rejected" and target_kind == "group" and state == "OPEN":
                code = "illegal_transition"
            else:
                code = "actor_not_permitted"
            conflicts.append(_conflict(event, code, operation_id))
            continue

        next_state = _transition_state(state, transition, target_kind=target_kind)
        if next_state is None:
            conflicts.append(_conflict(event, "illegal_transition", operation_id))
            continue

        if transition == "expired":
            if deadline is None:
                conflicts.append(_conflict(event, "deadline_violation", operation_id))
                continue
            event_time = _time_text(event.get("received_at"), "received_at")
            if event_time < str(deadline):
                conflicts.append(_conflict(event, "deadline_violation", operation_id))
                continue

        if transition == "accepted":
            assignee = actor
        event_evidence = event.get("evidence_ids") or ()
        if isinstance(event_evidence, (str, bytes)):
            raise CollaborationIntegrityError("evidence_ids must be a collection")
        evidence.update(str(item) for item in event_evidence)
        data = payload.get("data")
        if not isinstance(data, Mapping):
            raise CollaborationIntegrityError("transition data must be a mapping")
        if transition == "partial_result":
            latest_partial_result = data.get("result")
        elif transition == "completed":
            final_result = data.get("result")
        elif transition == "challenge":
            challenge_id = data.get("challenge_id")
            if isinstance(challenge_id, str) and challenge_id.strip():
                open_challenges.add(challenge_id.strip())
        elif transition == "challenge_response":
            challenge_id = data.get("challenge_id")
            if isinstance(challenge_id, str) and challenge_id in open_challenges:
                open_challenges.remove(challenge_id)
                resolved_challenges.add(challenge_id)
        elif transition == "escalated":
            escalated = True

        state = next_state
        head_event_id = event_id
        updated_at = str(event.get("received_at"))
        applied_count += 1

    deadline_passed = False
    if as_of is not None and deadline is not None:
        deadline_passed = _time_text(as_of, "as_of") >= str(deadline)

    return WorkSnapshot(
        protocol=COLLABORATION_PROTOCOL,
        work_id=work_id,
        work_kind=str(normalized_request["work_kind"]),
        requester_principal=requester,
        requester_kind=requester_kind,
        target_kind=target_kind,
        target_id=target_id,
        assignee=assignee,
        parent_work_id=normalized_request.get("parent_work_id"),
        parent_event_id=normalized_request.get("parent_event_id"),
        state=state,
        root_event_id=root_event_id,
        head_event_id=head_event_id,
        created_at=str(ordered[0].get("received_at")),
        updated_at=updated_at,
        deadline=str(deadline) if deadline is not None else None,
        deadline_passed=deadline_passed,
        priority=int(normalized_request["priority"]),
        objective=str(normalized_request["objective"]),
        constraints=dict(normalized_request["constraints"]),
        required_capabilities=tuple(normalized_request["required_capabilities"]),
        reviewer_principals=tuple(normalized_request["reviewer_principals"]),
        result_contract=(
            dict(normalized_request["result_contract"])
            if isinstance(normalized_request.get("result_contract"), Mapping)
            else None
        ),
        latest_partial_result=latest_partial_result,
        final_result=final_result,
        evidence_ids=tuple(sorted(evidence)),
        open_challenge_ids=tuple(sorted(open_challenges)),
        resolved_challenge_ids=tuple(sorted(resolved_challenges)),
        escalated=escalated,
        applied_event_count=applied_count,
        conflicts=tuple(conflicts),
        integrity_status="ok",
        execution_authorized=False,
        production_decision_authorized=False,
    )
