"""Machine-native semantic collaboration over the ICARUS Intelligence Fabric.

Phase 4A uses Phase 1 IntelligenceEvent records as the only canonical journal.
This module does not authorize execution or production decisions.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

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
