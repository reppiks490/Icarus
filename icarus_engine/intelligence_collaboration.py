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
from icarus_engine.intelligence_time import instant

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
RESULT_KINDS = {"json", "event_refs", "evidence_bundle", "decision", "text_plus_refs"}
TRANSITIONS = {
    "requested",
    "accepted",
    "started",
    "partial_result",
    "evidence_added",
    "challenge",
    "challenge_response",
    "escalated",
    "completed",
    "failed",
    "rejected",
    "cancelled",
    "expired",
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
    return None if value is None else _text(value, name, limit)


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
    return _sha256_json(_finite_json_mapping(material, "request material"))


def _normalize_result_contract(value: Mapping[str, object] | None) -> dict[str, object] | None:
    if value is None:
        return None
    contract = _finite_json_mapping(value, "result_contract")
    result_kind = _lower_enum(contract.get("result_kind"), "result_contract.result_kind", RESULT_KINDS)
    required_fields = _bounded_items(
        contract.get("required_fields", ()),
        "result_contract.required_fields",
        item_limit=64,
        count_limit=32,
    )
    schema_id = _optional_text(contract.get("schema_id"), "result_contract.schema_id", 160)
    schema_version = _optional_text(contract.get("schema_version"), "result_contract.schema_version", 80)
    return {
        "result_kind": result_kind,
        "required_fields": list(required_fields),
        "schema_id": schema_id,
        "schema_version": schema_version,
    }


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
        result_contract = _normalize_result_contract(self.result_contract)
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


def _normalize_request_mapping(value: Any) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise ValueError("request must be a mapping")
    return WorkRequest(
        requester_principal=value.get("requester_principal"),
        requester_kind=value.get("requester_kind"),
        target_kind=value.get("target_kind"),
        target_id=value.get("target_id"),
        work_kind=value.get("work_kind"),
        idempotency_key=value.get("idempotency_key"),
        objective=value.get("objective"),
        priority=value.get("priority", 0),
        constraints=value.get("constraints", {}),
        required_capabilities=tuple(value.get("required_capabilities", ()) or ()),
        reviewer_principals=tuple(value.get("reviewer_principals", ()) or ()),
        deadline=value.get("deadline"),
        result_contract=value.get("result_contract"),
        parent_work_id=value.get("parent_work_id"),
        parent_event_id=value.get("parent_event_id"),
    ).normalized()


def _event_type_for_root(work_kind: str, actor_kind: str) -> str:
    if work_kind == "decision":
        return "decision_request"
    return {"agent": "agent_note", "human": "human_note", "system": "system"}[actor_kind]


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
    observed = _time_text(observed_at, "observed_at")
    received = _time_text(received_at, "received_at")
    if instant(received) < instant(observed):
        raise ValueError("received_at cannot precede observed_at")
    deadline = material.get("deadline")
    if isinstance(deadline, str) and instant(deadline) < max(instant(observed), instant(received)):
        raise ValueError("deadline cannot precede root time")
    actor = _lower_enum(actor_kind, "actor_kind", PRINCIPAL_KINDS)
    if actor != material["requester_kind"]:
        raise ValueError("actor_kind must match requester_kind for a root request")
    work_id = request.work_id()
    payload: dict[str, Any] = {
        "protocol": COLLABORATION_PROTOCOL,
        "work_id": work_id,
        "transition": "requested",
        "actor_principal": material["requester_principal"],
        "actor_kind": actor,
        "operation_id": None,
        "expected_head_event_id": None,
        "request_material_hash": request_material_hash(material),
        "request": material,
    }
    if _payload_size(payload) > MAX_COLLABORATION_PAYLOAD_BYTES:
        raise ValueError(f"collaboration payload exceeds 30 KiB ({MAX_COLLABORATION_PAYLOAD_BYTES} bytes)")
    causes = set(
        _bounded_items(
            parent_causation_ids,
            "parent_causation_ids",
            item_limit=240,
            count_limit=64,
        )
    )
    parent_event_id = material.get("parent_event_id")
    if isinstance(parent_event_id, str):
        causes.add(parent_event_id)
    tags = {
        "collaboration:v1",
        f"work-kind:{material['work_kind']}",
        f"requester:{material['requester_principal']}",
        "transition:requested",
    }
    tags.add(
        f"to:{material['target_id']}"
        if material["target_kind"] == "principal"
        else f"group:{material['target_id']}"
    )
    parent_work_id = material.get("parent_work_id")
    if isinstance(parent_work_id, str):
        tags.add(f"parent:{parent_work_id}")
    work_kind = str(material["work_kind"])
    return IntelligenceEvent(
        event_type=_event_type_for_root(work_kind, actor),
        source=str(material["requester_principal"]),
        source_kind=actor,
        channel=COLLABORATION_CHANNEL,
        thread_key=f"work:{work_id}",
        title=f"Work request: {work_kind}",
        body=str(material["objective"]),
        observed_at=observed,
        received_at=received,
        severity=int(material["priority"]),
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


def _validate_envelope(
    event: Mapping[str, Any], work_id: str | None = None
) -> tuple[dict[str, Any], int, str]:
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


def _operation_digest(event: Mapping[str, Any], payload: Mapping[str, Any]) -> str:
    def _sorted_collection(name: str) -> list[str]:
        raw = event.get(name) or ()
        if isinstance(raw, (str, bytes)):
            raise CollaborationIntegrityError(f"{name} must be a collection")
        try:
            return sorted(str(item) for item in raw)
        except TypeError as exc:
            raise CollaborationIntegrityError(f"{name} must be a collection") from exc

    material = {
        "transition": payload.get("transition"),
        "actor_principal": payload.get("actor_principal"),
        "actor_kind": payload.get("actor_kind"),
        "expected_head_event_id": payload.get("expected_head_event_id"),
        "data": payload.get("data", {}),
        "event_type": event.get("event_type"),
        "assets": _sorted_collection("assets"),
        "evidence_ids": _sorted_collection("evidence_ids"),
        "causation_ids": _sorted_collection("causation_ids"),
    }
    try:
        return _sha256_json(material)
    except ValueError as exc:
        raise CollaborationIntegrityError("operation material must be finite JSON") from exc


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
    return assignee is not None and actor == assignee and transition in {
        "started",
        "evidence_added",
        "partial_result",
        "challenge_response",
        "escalated",
        "completed",
        "failed",
    }


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


def _result_contract_matches(
    contract: Mapping[str, Any] | None,
    *,
    work_kind: str,
    transition: str,
    event_type: Any,
    result: Any,
    event_evidence_ids: Sequence[str],
) -> bool:
    if transition not in {"partial_result", "completed"}:
        return True
    expected_type = "decision_response" if work_kind == "decision" and transition == "completed" else "research"
    if event_type != expected_type:
        return False
    if contract is None:
        return True
    if not isinstance(result, Mapping):
        return False
    kind = contract.get("result_kind")
    required = contract.get("required_fields") or ()
    if isinstance(required, (str, bytes)):
        return False
    if any(field not in result for field in required):
        return False
    if kind == "event_refs":
        refs = result.get("event_refs")
        return isinstance(refs, (list, tuple)) and bool(refs)
    if kind == "evidence_bundle":
        return bool(event_evidence_ids)
    if kind == "text_plus_refs":
        text = result.get("text")
        refs = result.get("event_refs")
        has_refs = isinstance(refs, (list, tuple)) and bool(refs)
        return isinstance(text, str) and bool(text.strip()) and (has_refs or bool(event_evidence_ids))
    return kind in {"json", "decision"}


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
    try:
        normalized_request = _normalize_request_mapping(root_payload.get("request"))
    except (TypeError, ValueError) as exc:
        raise CollaborationIntegrityError(f"invalid root request material: {exc}") from exc
    _integrity(root_payload.get("actor_principal") == normalized_request["requester_principal"],
               "root actor/requester principal mismatch")
    _integrity(root_payload.get("actor_kind") == normalized_request["requester_kind"],
               "root actor/requester kind mismatch")
    expected_work_id = derive_work_id(
        str(normalized_request["requester_principal"]),
        str(normalized_request["idempotency_key"]),
    )
    _integrity(expected_work_id == work_id, "derived work_id mismatch")
    root_material_hash = request_material_hash(normalized_request)
    _integrity(root_payload.get("request_material_hash") == root_material_hash, "request material hash mismatch")
    root_received = _time_text(ordered[0].get("received_at"), "received_at")
    deadline = normalized_request.get("deadline")
    _integrity(deadline is None or instant(str(deadline)) >= instant(root_received), "deadline precedes root time")

    requester = str(normalized_request["requester_principal"])
    requester_kind = str(normalized_request["requester_kind"])
    target_kind = str(normalized_request["target_kind"])
    target_id = str(normalized_request["target_id"])
    work_kind = str(normalized_request["work_kind"])
    reviewers = set(normalized_request["reviewer_principals"])
    result_contract = normalized_request.get("result_contract")
    state = "OPEN"
    assignee: str | None = None
    head_event_id = root_event_id
    updated_at = root_received
    applied_count = 1
    conflicts: list[WorkConflict] = []
    operation_registry: dict[str, tuple[str, str]] = {}
    evidence = set(str(item) for item in (ordered[0].get("evidence_ids") or ()))
    open_challenges: dict[str, str] = {}
    resolved_challenges: set[str] = set()
    latest_partial_result: Any | None = None
    final_result: Any | None = None
    escalated = False

    last_sequence = root_sequence
    for event in ordered[1:]:
        payload, sequence, event_id = _validate_envelope(event, work_id)
        _integrity(sequence > last_sequence, "events must have unique ascending sequence")
        last_sequence = sequence
        transition = payload.get("transition")
        _integrity(isinstance(transition, str) and transition in TRANSITIONS, "invalid transition")

        if transition == "requested":
            try:
                later_request = _normalize_request_mapping(payload.get("request"))
            except (TypeError, ValueError) as exc:
                raise CollaborationIntegrityError(f"invalid root request material: {exc}") from exc
            _integrity(payload.get("actor_principal") == later_request["requester_principal"],
                       "root actor/requester principal mismatch")
            _integrity(payload.get("actor_kind") == later_request["requester_kind"],
                       "root actor/requester kind mismatch")
            later_hash = request_material_hash(later_request)
            _integrity(payload.get("request_material_hash") == later_hash, "request material hash mismatch")
            later_work_id = derive_work_id(
                str(later_request["requester_principal"]),
                str(later_request["idempotency_key"]),
            )
            _integrity(later_work_id == work_id, "derived work_id mismatch")
            conflicts.append(_conflict(event, "duplicate_root" if later_hash == root_material_hash else "conflicting_root"))
            continue

        actor = str(payload["actor_principal"])
        actor_kind = str(payload["actor_kind"])
        try:
            operation_id = _text(payload.get("operation_id"), "operation_id", MAX_OPERATION_ID)
            expected_head = _text(payload.get("expected_head_event_id"), "expected_head_event_id", 240)
        except ValueError as exc:
            raise CollaborationIntegrityError(str(exc)) from exc

        digest = _operation_digest(event, payload)
        prior = operation_registry.get(operation_id)
        if prior is not None:
            prior_digest, _prior_event_id = prior
            conflicts.append(
                _conflict(
                    event,
                    "duplicate_operation" if prior_digest == digest else "conflicting_operation",
                    operation_id,
                )
            )
            continue
        if expected_head != head_event_id:
            conflicts.append(_conflict(event, "stale_head", operation_id))
            continue
        causes_raw = event.get("causation_ids") or ()
        if isinstance(causes_raw, (str, bytes)):
            conflicts.append(_conflict(event, "missing_required_cause", operation_id))
            continue
        causes = set(str(item) for item in causes_raw)
        if expected_head not in causes:
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
            code = "illegal_transition" if transition == "rejected" and target_kind == "group" and state == "OPEN" else "actor_not_permitted"
            conflicts.append(_conflict(event, code, operation_id))
            continue
        next_state = _transition_state(state, transition, target_kind=target_kind)
        if next_state is None:
            conflicts.append(_conflict(event, "illegal_transition", operation_id))
            continue
        data = payload.get("data")
        if not isinstance(data, Mapping):
            raise CollaborationIntegrityError("transition data must be a mapping")

        if transition == "expired":
            if deadline is None:
                conflicts.append(_conflict(event, "deadline_violation", operation_id))
                continue
            event_time = _time_text(event.get("received_at"), "received_at")
            if instant(event_time) < instant(str(deadline)):
                conflicts.append(_conflict(event, "deadline_violation", operation_id))
                continue

        event_evidence_raw = event.get("evidence_ids") or ()
        if isinstance(event_evidence_raw, (str, bytes)):
            raise CollaborationIntegrityError("evidence_ids must be a collection")
        event_evidence = tuple(str(item) for item in event_evidence_raw)

        if transition == "challenge":
            try:
                challenge_id = _text(data.get("challenge_id"), "challenge_id", MAX_CHALLENGE_ID)
            except ValueError:
                conflicts.append(_conflict(event, "challenge_mismatch", operation_id))
                continue
            if challenge_id in open_challenges or challenge_id in resolved_challenges:
                conflicts.append(_conflict(event, "challenge_mismatch", operation_id))
                continue
        elif transition == "challenge_response":
            try:
                challenge_id = _text(data.get("challenge_id"), "challenge_id", MAX_CHALLENGE_ID)
            except ValueError:
                conflicts.append(_conflict(event, "challenge_mismatch", operation_id))
                continue
            challenge_event_id = open_challenges.get(challenge_id)
            if challenge_event_id is None or challenge_event_id not in causes:
                conflicts.append(_conflict(event, "challenge_mismatch", operation_id))
                continue
        elif transition == "completed":
            unresolved_raw = data.get("unresolved_challenge_ids", ())
            try:
                unresolved = _bounded_items(
                    unresolved_raw,
                    "unresolved_challenge_ids",
                    item_limit=MAX_CHALLENGE_ID,
                    count_limit=64,
                )
            except ValueError:
                conflicts.append(_conflict(event, "challenge_mismatch", operation_id))
                continue
            if set(unresolved) != set(open_challenges):
                conflicts.append(_conflict(event, "challenge_mismatch", operation_id))
                continue

        if transition in {"partial_result", "completed"} and not _result_contract_matches(
            result_contract if isinstance(result_contract, Mapping) else None,
            work_kind=work_kind,
            transition=transition,
            event_type=event.get("event_type"),
            result=data.get("result"),
            event_evidence_ids=event_evidence,
        ):
            conflicts.append(_conflict(event, "result_contract_mismatch", operation_id))
            continue

        operation_registry[operation_id] = (digest, event_id)
        if transition == "accepted":
            assignee = actor
        evidence.update(event_evidence)
        if transition == "partial_result":
            latest_partial_result = data.get("result")
        elif transition == "completed":
            final_result = data.get("result")
        elif transition == "challenge":
            challenge_id = _text(data.get("challenge_id"), "challenge_id", MAX_CHALLENGE_ID)
            open_challenges[challenge_id] = event_id
        elif transition == "challenge_response":
            challenge_id = _text(data.get("challenge_id"), "challenge_id", MAX_CHALLENGE_ID)
            open_challenges.pop(challenge_id, None)
            resolved_challenges.add(challenge_id)
        elif transition == "escalated":
            escalated = True

        state = next_state
        head_event_id = event_id
        updated_at = str(event.get("received_at"))
        applied_count += 1

    deadline_passed = bool(
        as_of is not None and deadline is not None and instant(_time_text(as_of, "as_of")) >= instant(str(deadline))
    )
    return WorkSnapshot(
        protocol=COLLABORATION_PROTOCOL,
        work_id=work_id,
        work_kind=work_kind,
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
        created_at=root_received,
        updated_at=updated_at,
        deadline=str(deadline) if deadline is not None else None,
        deadline_passed=deadline_passed,
        priority=int(normalized_request["priority"]),
        objective=str(normalized_request["objective"]),
        constraints=dict(normalized_request["constraints"]),
        required_capabilities=tuple(normalized_request["required_capabilities"]),
        reviewer_principals=tuple(normalized_request["reviewer_principals"]),
        result_contract=(dict(result_contract) if isinstance(result_contract, Mapping) else None),
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


def load_complete_work_history(fabric: IntelligenceFabric, work_id: str) -> list[dict[str, object]]:
    """Load a collaboration thread without ever treating a capped page as complete."""
    normalized_work_id = _work_id(work_id)
    thread_key = f"work:{normalized_work_id}"
    fast = list(fabric.thread(thread_key, limit=1000))
    if len(fast) < 1000:
        return sorted(fast, key=lambda item: int(item.get("sequence", 0)))

    history: list[dict[str, object]] = []
    after_sequence = 0
    while True:
        page = list(fabric.replay(after_sequence=after_sequence, limit=1000))
        if not page:
            break
        last = after_sequence
        for record in page:
            sequence = record.get("sequence")
            if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence <= last:
                raise CollaborationIntegrityError("global replay returned invalid sequence order")
            last = sequence
            if record.get("thread_key") == thread_key:
                history.append(dict(record))
        after_sequence = last
        if len(page) < 1000:
            break
    return history


def project_work_from_fabric(
    fabric: IntelligenceFabric,
    work_id: str,
    *,
    as_of: str | None = None,
) -> WorkSnapshot:
    """Project only after complete work history has been retrieved successfully."""
    return project_work(load_complete_work_history(fabric, work_id), as_of=as_of)


def _publication_result(
    published: Mapping[str, object],
    snapshot: WorkSnapshot,
    *,
    idempotent_root: bool = False,
) -> dict[str, object]:
    event_id = str(published["event_id"])
    conflict = next((item for item in snapshot.conflicts if item.event_id == event_id), None)
    if idempotent_root:
        applied = False
        conflict_code = "duplicate_root"
        original_event_id = snapshot.root_event_id
    else:
        applied = conflict is None and snapshot.head_event_id == event_id
        conflict_code = None if conflict is None else conflict.code
        original_event_id = None
    result: dict[str, object] = {
        "event_id": event_id,
        "sequence": int(published["sequence"]),
        "applied": applied,
        "head_event_id": snapshot.head_event_id,
        "state": snapshot.state,
        "execution_authorized": False,
        "production_decision_authorized": False,
    }
    if conflict_code is not None:
        result["conflict_code"] = conflict_code
    if original_event_id is not None:
        result["original_event_id"] = original_event_id
    return result


class IntelligenceCollaboration:
    """Thin publication facade over the canonical Phase 1 fabric and pure projector."""

    def __init__(self, fabric: IntelligenceFabric):
        self._fabric = fabric

    def history(self, work_id: str) -> list[dict[str, object]]:
        return load_complete_work_history(self._fabric, work_id)

    def snapshot(self, work_id: str, *, as_of: str | None = None) -> WorkSnapshot:
        return project_work_from_fabric(self._fabric, work_id, as_of=as_of)

    def create_work(
        self,
        request: WorkRequest,
        *,
        observed_at: str,
        received_at: str,
        assets: Iterable[str] = (),
        evidence_ids: Iterable[str] = (),
    ) -> dict[str, object]:
        event = build_request_event(
            request,
            observed_at=observed_at,
            received_at=received_at,
            actor_kind=request.requester_kind,
            assets=assets,
            evidence_ids=evidence_ids,
        )
        published = self._fabric.publish(event)
        snapshot = self.snapshot(request.work_id())
        return _publication_result(
            published,
            snapshot,
            idempotent_root=bool(published.get("idempotent")),
        )


@dataclass(frozen=True)
class TransitionRequest:
    work_id: str
    transition: str
    actor_principal: str
    actor_kind: str
    operation_id: str
    expected_head_event_id: str
    data: Mapping[str, object] = field(default_factory=dict)
    evidence_ids: tuple[str, ...] = ()
    assets: tuple[str, ...] = ()
    additional_causation_ids: tuple[str, ...] = ()

    def normalized(self) -> dict[str, object]:
        work_id = _work_id(self.work_id)
        transition = _lower_enum(self.transition, "transition", TRANSITIONS - {"requested"})
        actor = _text(self.actor_principal, "actor_principal", MAX_PRINCIPAL)
        actor_kind = _lower_enum(self.actor_kind, "actor_kind", PRINCIPAL_KINDS)
        operation_id = _text(self.operation_id, "operation_id", MAX_OPERATION_ID)
        expected_head = _text(self.expected_head_event_id, "expected_head_event_id", 240)
        data = _finite_json_mapping(self.data, "data")
        evidence_ids = _bounded_items(
            self.evidence_ids,
            "evidence_ids",
            item_limit=240,
            count_limit=64,
        )
        assets = _bounded_items(self.assets, "assets", item_limit=80, count_limit=64)
        additional_causes = _bounded_items(
            self.additional_causation_ids,
            "additional_causation_ids",
            item_limit=240,
            count_limit=64,
        )
        return {
            "work_id": work_id,
            "transition": transition,
            "actor_principal": actor,
            "actor_kind": actor_kind,
            "operation_id": operation_id,
            "expected_head_event_id": expected_head,
            "data": data,
            "evidence_ids": list(evidence_ids),
            "assets": list(assets),
            "additional_causation_ids": list(additional_causes),
        }


def _event_type_for_transition(work_kind: str, transition: str, actor_kind: str) -> str:
    if transition == "completed" and work_kind == "decision":
        return "decision_response"
    if transition in {"partial_result", "completed"}:
        return "research"
    return {"agent": "agent_note", "human": "human_note", "system": "system"}[actor_kind]


def build_transition_event(
    snapshot: WorkSnapshot,
    transition: TransitionRequest,
    *,
    observed_at: str,
    received_at: str,
) -> IntelligenceEvent:
    if not isinstance(snapshot, WorkSnapshot):
        raise ValueError("snapshot must be WorkSnapshot")
    if not isinstance(transition, TransitionRequest):
        raise ValueError("transition must be TransitionRequest")
    material = transition.normalized()
    if material["work_id"] != snapshot.work_id:
        raise ValueError("transition work_id must match snapshot work_id")
    observed = _time_text(observed_at, "observed_at")
    received = _time_text(received_at, "received_at")
    if instant(received) < instant(observed):
        raise ValueError("received_at cannot precede observed_at")
    payload: dict[str, object] = {
        "protocol": COLLABORATION_PROTOCOL,
        "work_id": material["work_id"],
        "transition": material["transition"],
        "actor_principal": material["actor_principal"],
        "actor_kind": material["actor_kind"],
        "operation_id": material["operation_id"],
        "expected_head_event_id": material["expected_head_event_id"],
        "data": material["data"],
    }
    if _payload_size(payload) > MAX_COLLABORATION_PAYLOAD_BYTES:
        raise ValueError(f"collaboration payload exceeds 30 KiB ({MAX_COLLABORATION_PAYLOAD_BYTES} bytes)")
    causes = set(str(item) for item in material["additional_causation_ids"])
    causes.add(str(material["expected_head_event_id"]))
    tags = {
        "collaboration:v1",
        f"work-kind:{snapshot.work_kind}",
        f"transition:{material['transition']}",
        f"actor:{material['actor_principal']}",
    }
    event_type = _event_type_for_transition(
        snapshot.work_kind,
        str(material["transition"]),
        str(material["actor_kind"]),
    )
    return IntelligenceEvent(
        event_type=event_type,
        source=str(material["actor_principal"]),
        source_kind=str(material["actor_kind"]),
        channel=COLLABORATION_CHANNEL,
        thread_key=f"work:{snapshot.work_id}",
        title=f"Work {material['transition']}: {snapshot.work_kind}",
        body=str(material["transition"]),
        observed_at=observed,
        received_at=received,
        severity=snapshot.priority,
        urgency=0.0,
        confidence=None,
        assets=tuple(str(item) for item in material["assets"]),
        correlation_id=snapshot.work_id,
        causation_ids=tuple(sorted(causes)),
        evidence_ids=tuple(str(item) for item in material["evidence_ids"]),
        tags=tuple(sorted(tags)),
        payload=payload,
    )


def _original_operation_event_id(
    history: Sequence[Mapping[str, object]],
    operation_id: str,
    *,
    exclude_event_id: str | None = None,
) -> str | None:
    rejected_ids = {conflict.event_id for conflict in project_work(history).conflicts}
    for record in history:
        if record.get("event_id") in rejected_ids:
            continue
        payload = record.get("payload")
        if not isinstance(payload, Mapping):
            continue
        if payload.get("operation_id") != operation_id:
            continue
        event_id = record.get("event_id")
        if not isinstance(event_id, str):
            continue
        if exclude_event_id is not None and event_id == exclude_event_id:
            continue
        return event_id
    return None


_BaseIntelligenceCollaboration = IntelligenceCollaboration


class IntelligenceCollaboration(_BaseIntelligenceCollaboration):
    """Publication facade with semantic transition appends."""

    def append_transition(
        self,
        transition: TransitionRequest,
        *,
        observed_at: str,
        received_at: str,
    ) -> dict[str, object]:
        normalized = transition.normalized()
        work_id = str(normalized["work_id"])
        history_before = self.history(work_id)
        snapshot_before = project_work(history_before)
        original_event_id = _original_operation_event_id(
            history_before,
            str(normalized["operation_id"]),
        )
        event = build_transition_event(
            snapshot_before,
            transition,
            observed_at=observed_at,
            received_at=received_at,
        )
        published = self._fabric.publish(event)
        snapshot_after = self.snapshot(work_id)
        event_id = str(published["event_id"])

        if (bool(published.get("idempotent")) and original_event_id is not None
                and not any(conflict.event_id == event_id for conflict in snapshot_after.conflicts)):
            return {
                "event_id": event_id,
                "sequence": int(published["sequence"]),
                "applied": False,
                "conflict_code": "duplicate_operation",
                "original_event_id": original_event_id,
                "head_event_id": snapshot_after.head_event_id,
                "state": snapshot_after.state,
                "execution_authorized": False,
                "production_decision_authorized": False,
            }

        result = _publication_result(published, snapshot_after)
        if result.get("conflict_code") == "duplicate_operation":
            original = original_event_id or _original_operation_event_id(
                self.history(work_id),
                str(normalized["operation_id"]),
                exclude_event_id=event_id,
            )
            if original is not None:
                result["original_event_id"] = original
        return result


_TransitionIntelligenceCollaboration = IntelligenceCollaboration


class IntelligenceCollaboration(_TransitionIntelligenceCollaboration):
    """Collaboration facade with validated parent/child delegation discovery."""

    def _validate_parent_for_child(self, request: WorkRequest) -> WorkSnapshot | None:
        material = request.normalized()
        parent_work_id = material.get("parent_work_id")
        parent_event_id = material.get("parent_event_id")
        if parent_work_id is None:
            return None

        parent = self.snapshot(str(parent_work_id))
        if parent.integrity_status != "ok" or parent.conflicts:
            raise ValueError("parent work must be clean and conflict-free before delegation")
        if parent.state not in {"ACCEPTED", "IN_PROGRESS", "PARTIAL"} or parent.assignee is None:
            raise ValueError("parent work must be in an assignable nonterminal state")
        if material.get("requester_principal") != parent.assignee:
            raise ValueError("child requester must equal parent assignee")
        if parent_event_id != parent.head_event_id:
            raise ValueError("parent_event_id must equal parent current head")
        return parent

    def create_work(
        self,
        request: WorkRequest,
        *,
        observed_at: str,
        received_at: str,
        assets: Iterable[str] = (),
        evidence_ids: Iterable[str] = (),
    ) -> dict[str, object]:
        existing = self.history(request.work_id())
        if existing:
            # Existing roots own their identity even after parent progress. Replay
            # first to fail closed on corrupt history; publication handles an
            # identical retry versus conflicting material without changing state.
            project_work(existing)
        else:
            self._validate_parent_for_child(request)
        return super().create_work(
            request,
            observed_at=observed_at,
            received_at=received_at,
            assets=assets,
            evidence_ids=evidence_ids,
        )

    def children(self, parent_work_id: str, *, limit: int = 100) -> list[dict[str, object]]:
        parent_id = _work_id(parent_work_id, "parent_work_id")
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
            raise ValueError("limit must be an integer in [1, 100]")
        candidates = self._fabric.query(
            channel=COLLABORATION_CHANNEL,
            tags=(f"parent:{parent_id}",),
            limit=limit,
        )
        children: list[dict[str, object]] = []
        for record in candidates:
            try:
                payload, _sequence, _event_id = _validate_envelope(record)
            except CollaborationIntegrityError:
                continue
            if payload.get("transition") != "requested":
                continue
            request = payload.get("request")
            if not isinstance(request, Mapping) or request.get("parent_work_id") != parent_id:
                continue
            children.append(dict(record))
        return children
