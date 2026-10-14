"""Phase 4C presence, capability matching, incident rooms, and escalation.

Presence is an expiring authenticated lease. Incident content is immutable
Phase 1 history; this module owns no durable room or message database.
"""
from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from .intelligence_collaboration import (
    IntelligenceCollaboration,
    TransitionRequest,
    WorkRequest,
    _text,
)
from .intelligence_fabric import IntelligenceEvent, IntelligenceFabric

INCIDENT_PROTOCOL = "icarus-incident-room-v1"
MAX_ROOM_MEMBERS = 64
MAX_ROOM_TEXT = 4000


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


@dataclass(frozen=True)
class PresenceLease:
    principal_id: str
    principal_kind: str
    capabilities: tuple[str, ...]
    status: str
    last_seen_monotonic: float
    expires_monotonic: float


class CapabilityPresenceRegistry:
    """Process-local TTL registry; every write requires a caller-bound identity."""

    def __init__(self, *, max_principals: int = 512, max_ttl_seconds: int = 300):
        if isinstance(max_principals, bool) or not isinstance(max_principals, int) or not 1 <= max_principals <= 10000:
            raise ValueError("max_principals must be in [1, 10000]")
        if isinstance(max_ttl_seconds, bool) or not isinstance(max_ttl_seconds, int) or not 10 <= max_ttl_seconds <= 3600:
            raise ValueError("max_ttl_seconds must be in [10, 3600]")
        self._max = max_principals
        self._max_ttl = max_ttl_seconds
        self._leases: dict[str, PresenceLease] = {}
        self._lock = threading.RLock()

    @staticmethod
    def _capabilities(values: Iterable[str]) -> tuple[str, ...]:
        if isinstance(values, (str, bytes)):
            raise ValueError("capabilities must be a collection")
        items = tuple(values)
        if len(items) > 32:
            raise ValueError("capabilities exceeds 32 items")
        return tuple(sorted({_text(item, "capability", 64).lower() for item in items}))

    def advertise(
        self,
        *,
        principal_id: str,
        principal_kind: str,
        capabilities: Iterable[str],
        ttl_seconds: int = 60,
        status: str = "available",
        now_monotonic: float | None = None,
    ) -> PresenceLease:
        principal = _text(principal_id, "principal_id", 64)
        if principal_kind not in {"agent", "human", "system"}:
            raise ValueError("principal_kind is invalid")
        if status not in {"available", "busy", "away"}:
            raise ValueError("status is invalid")
        if isinstance(ttl_seconds, bool) or not isinstance(ttl_seconds, int) or not 10 <= ttl_seconds <= self._max_ttl:
            raise ValueError("ttl_seconds is outside the configured bound")
        now = time.monotonic() if now_monotonic is None else float(now_monotonic)
        if not now >= 0 or not now < float("inf"):
            raise ValueError("now_monotonic is invalid")
        normalized = self._capabilities(capabilities)
        with self._lock:
            self._purge(now)
            if principal not in self._leases and len(self._leases) >= self._max:
                raise ValueError("presence registry is full")
            lease = PresenceLease(principal, principal_kind, normalized, status, now, now + ttl_seconds)
            self._leases[principal] = lease
            return lease

    def withdraw(self, principal_id: str) -> bool:
        principal = _text(principal_id, "principal_id", 64)
        with self._lock:
            return self._leases.pop(principal, None) is not None

    def _purge(self, now: float) -> None:
        for principal in [p for p, lease in self._leases.items() if lease.expires_monotonic <= now]:
            self._leases.pop(principal, None)

    def list(self, *, now_monotonic: float | None = None) -> tuple[PresenceLease, ...]:
        now = time.monotonic() if now_monotonic is None else float(now_monotonic)
        with self._lock:
            self._purge(now)
            return tuple(sorted(self._leases.values(), key=lambda lease: lease.principal_id))

    def match(self, required_capabilities: Iterable[str], *, now_monotonic: float | None = None) -> tuple[PresenceLease, ...]:
        required = set(self._capabilities(required_capabilities))
        return tuple(
            lease for lease in self.list(now_monotonic=now_monotonic)
            if lease.status == "available" and required.issubset(lease.capabilities)
        )


def route_escalation(
    collaboration: IntelligenceCollaboration,
    presence: CapabilityPresenceRegistry,
    *,
    work_id: str,
    actor_principal: str,
    actor_kind: str,
    operation_id: str,
    target_principal: str,
    objective: str | None = None,
    observed_at: str | None = None,
) -> dict[str, object]:
    """Record escalation and create an explicitly selected capability-matched child."""
    snapshot = collaboration.snapshot(work_id)
    operation = _text(operation_id, "operation_id", 128)
    target_id = _text(target_principal, "target_principal", 64)
    if snapshot.assignee != actor_principal:
        raise ValueError("only the assigned principal may route delegated escalation work")
    if snapshot.escalated:
        retry = None
        for event in collaboration.history(work_id):
            payload = event.get("payload")
            if not isinstance(payload, Mapping) or payload.get("transition") != "escalated":
                continue
            if payload.get("operation_id") == operation:
                retry = event
                break
        retry_data = retry.get("payload", {}).get("data") if retry is not None else None
        if (retry is None or retry.get("event_id") != snapshot.head_event_id
                or not isinstance(retry_data, Mapping) or retry_data.get("target_principal") != target_id):
            raise ValueError("work already has an escalation route")
    matched = {lease.principal_id: lease for lease in presence.match(snapshot.required_capabilities)}
    target = matched.get(target_id)
    if target is None:
        raise ValueError("selected principal is not currently capability eligible")
    if target.principal_id == actor_principal:
        raise ValueError("an escalation route must select another principal")
    stamp = observed_at or _now()
    transition = TransitionRequest(
        work_id=work_id,
        transition="escalated",
        actor_principal=actor_principal,
        actor_kind=actor_kind,
        operation_id=operation,
        expected_head_event_id=snapshot.head_event_id,
        data={"target_principal": target.principal_id, "capabilities": list(target.capabilities)},
    )
    result = collaboration.append_transition(transition, observed_at=stamp, received_at=_now())
    if not result.get("applied") and result.get("conflict_code") != "duplicate_operation":
        raise ValueError("escalation transition conflicted; no child work was created")
    updated = collaboration.snapshot(work_id)
    child_key = "route:" + hashlib.sha256(_canonical([work_id, operation, target.principal_id]).encode("utf-8")).hexdigest()
    child = WorkRequest(
        requester_principal=actor_principal,
        requester_kind=actor_kind,
        target_kind="principal",
        target_id=target.principal_id,
        work_kind="investigation",
        idempotency_key=child_key,
        objective=(objective or f"Escalation support for {work_id}: {snapshot.objective}")[:2000],
        priority=snapshot.priority,
        constraints={"escalation_for": work_id, "required_capabilities": list(snapshot.required_capabilities)},
        required_capabilities=snapshot.required_capabilities,
        reviewer_principals=snapshot.reviewer_principals,
        parent_work_id=work_id,
        parent_event_id=updated.head_event_id,
    )
    child_result = collaboration.create_work(child, observed_at=_now(), received_at=_now())
    child_result["work_id"] = child.work_id()
    return {
        "escalation": result,
        "child": child_result,
        "selected_principal": target.principal_id,
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


def incident_room_id(work_id: str) -> str:
    value = _text(work_id, "work_id", 64)
    return hashlib.sha256(_canonical([INCIDENT_PROTOCOL, value]).encode("utf-8")).hexdigest()


def _room_event(
    *,
    room_id: str,
    work_id: str,
    actor_principal: str,
    actor_kind: str,
    action: str,
    title: str,
    body: str,
    observed_at: str,
    members: Iterable[str],
    causation_ids: Iterable[str] = (),
) -> IntelligenceEvent:
    room = _text(room_id, "room_id", 64)
    parent = _text(work_id, "work_id", 64)
    actor = _text(actor_principal, "actor_principal", 64)
    if actor_kind not in {"human", "agent", "system"}:
        raise ValueError("actor_kind is invalid")
    if action not in {"opened", "message", "closed"}:
        raise ValueError("room action is invalid")
    member_set = sorted({_text(item, "member", 64) for item in members} | {actor})
    if len(member_set) > MAX_ROOM_MEMBERS:
        raise ValueError("room has too many members")
    safe_body = _text(body, "body", MAX_ROOM_TEXT)
    stamp = _text(observed_at, "observed_at", 80)
    try:
        parsed = datetime.fromisoformat(stamp[:-1] + "+00:00" if stamp.endswith("Z") else stamp)
    except ValueError as exc:
        raise ValueError("observed_at must be ISO-8601") from exc
    if parsed.tzinfo is None:
        raise ValueError("observed_at must include timezone")
    payload = {
        "protocol": INCIDENT_PROTOCOL,
        "room_id": room,
        "work_id": parent,
        "action": action,
        "actor_principal": actor,
        "actor_kind": actor_kind,
        "members": member_set,
        "body_sha256": hashlib.sha256(safe_body.encode("utf-8")).hexdigest(),
        "execution_authorized": False,
        "production_decision_authorized": False,
    }
    # Keep the room payload well below the Phase 1 envelope limit.
    if len(_canonical(payload).encode("utf-8")) > 8 * 1024:
        raise ValueError("room metadata is too large")
    causes = {_text(item, "causation_id", 240) for item in causation_ids}
    return IntelligenceEvent(
        event_type={"human": "human_note", "agent": "agent_note", "system": "system"}[actor_kind],
        source=actor,
        source_kind=actor_kind,
        channel="incident",
        thread_key=f"incident:{room}",
        title=_text(title, "title", 160),
        body=safe_body,
        observed_at=parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        received_at=_now(),
        severity=3,
        urgency=0.0,
        confidence=None,
        correlation_id=parent,
        causation_ids=tuple(sorted(causes)),
        tags=("incident-room:v1", f"incident-action:{action}", f"work:{parent}"),
        payload=payload,
    )


class IncidentRoomService:
    """Journal-backed room operations with authorization from projected membership."""

    def __init__(self, fabric: IntelligenceFabric, collaboration: IntelligenceCollaboration):
        self._fabric = fabric
        self._collaboration = collaboration

    def _history(self, room_id: str) -> list[dict[str, object]]:
        indexed = self._fabric.query(channel="incident", thread_key=f"incident:{room_id}", limit=1000)
        if len(indexed) < 1000:
            return sorted(indexed, key=lambda row: int(row.get("sequence", 0)))
        # The public query API is capped. At saturation, reconstruct from the
        # journal so the caller never projects a silently truncated room.
        output: list[dict[str, object]] = []
        after = 0
        while True:
            page = self._fabric.replay(after_sequence=after, limit=1000)
            if not page:
                break
            for event in page:
                if event.get("channel") == "incident" and event.get("thread_key") == f"incident:{room_id}":
                    output.append(event)
            after = int(page[-1]["sequence"])
        return sorted(output, key=lambda row: int(row.get("sequence", 0)))

    @staticmethod
    def _validate(history: list[dict[str, object]], room_id: str, work_id: str, *, allow_closed: bool = False) -> set[str]:
        if not history:
            raise ValueError("incident room is unavailable")
        members: set[str] = set()
        opened = False
        closed = False
        previous_event_id: str | None = None
        previous_sequence = 0
        for event in sorted(history, key=lambda row: int(row.get("sequence", 0))):
            payload = event.get("payload")
            if not isinstance(payload, Mapping) or payload.get("protocol") != INCIDENT_PROTOCOL:
                raise ValueError("incident history is invalid")
            if payload.get("room_id") != room_id or payload.get("work_id") != work_id:
                raise ValueError("incident identity mismatch")
            if event.get("channel") != "incident" or event.get("thread_key") != f"incident:{room_id}":
                raise ValueError("incident envelope mismatch")
            sequence = event.get("sequence")
            event_id = event.get("event_id")
            if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence <= previous_sequence or not isinstance(event_id, str):
                raise ValueError("incident sequence is invalid")
            previous_sequence = sequence
            if event.get("correlation_id") != work_id:
                raise ValueError("incident correlation binding mismatch")
            if payload.get("execution_authorized") is not False or payload.get("production_decision_authorized") is not False:
                raise ValueError("incident authority invariant violated")
            event_body = event.get("body")
            if not isinstance(event_body, str) or payload.get("body_sha256") != hashlib.sha256(event_body.encode("utf-8")).hexdigest():
                raise ValueError("incident body binding mismatch")
            actor = payload.get("actor_principal")
            kind = payload.get("actor_kind")
            if event.get("source") != actor or event.get("source_kind") != kind:
                raise ValueError("incident actor binding mismatch")
            raw_members = payload.get("members")
            if not isinstance(raw_members, list) or any(not isinstance(item, str) for item in raw_members):
                raise ValueError("incident member projection is invalid")
            event_members = set(raw_members)
            if len(event_members) > MAX_ROOM_MEMBERS or actor not in event_members:
                raise ValueError("incident member projection is invalid")
            if not opened:
                members = event_members
            elif event_members != members:
                raise ValueError("incident membership changed without a membership event")
            action = payload.get("action")
            if action not in {"opened", "message", "closed"} or closed:
                raise ValueError("incident action sequence is invalid")
            causes_raw = event.get("causation_ids")
            if not isinstance(causes_raw, list) or any(not isinstance(item, str) for item in causes_raw):
                raise ValueError("incident causation is invalid")
            if previous_event_id is not None and previous_event_id not in causes_raw:
                raise ValueError("incident event does not cause from the prior room event")
            if previous_event_id is None and not causes_raw:
                raise ValueError("incident root must reference its work head")
            if action == "message":
                try:
                    _text(payload.get("operation_id"), "operation_id", 128)
                except ValueError as exc:
                    raise ValueError("incident message operation identity is invalid") from exc
            if not opened and action != "opened":
                raise ValueError("incident must begin with opened event")
            if action == "opened":
                opened = True
            if action == "closed":
                closed = True
            previous_event_id = event_id
        if not opened:
            raise ValueError("incident is not open")
        if closed and not allow_closed:
            raise ValueError("incident is closed")
        return members

    def open(self, *, work_id: str, actor_principal: str, actor_kind: str, members: Iterable[str], observed_at: str | None = None) -> dict[str, object]:
        snapshot = self._collaboration.snapshot(work_id)
        actor = _text(actor_principal, "actor_principal", 64)
        if actor not in {snapshot.requester_principal, snapshot.assignee} and actor not in snapshot.reviewer_principals:
            raise ValueError("actor cannot open an incident for this work")
        room_id = incident_room_id(work_id)
        existing = self._history(room_id)
        if existing:
            self._validate(existing, room_id, work_id)
            return {"room_id": room_id, "event_id": existing[0]["event_id"], "idempotent": True,
                    "execution_authorized": False, "production_decision_authorized": False}
        event = _room_event(room_id=room_id, work_id=work_id, actor_principal=actor, actor_kind=actor_kind,
                            action="opened", title="Incident room opened", body=f"Incident response for work {work_id}",
                            observed_at=observed_at or _now(), members=members, causation_ids=(snapshot.head_event_id,))
        result = self._fabric.publish(event)
        return {"room_id": room_id, "event_id": result["event_id"], "sequence": result["sequence"], "idempotent": bool(result.get("idempotent")),
                "execution_authorized": False, "production_decision_authorized": False}

    def post(self, *, work_id: str, actor_principal: str, actor_kind: str, body: str, operation_id: str, observed_at: str | None = None) -> dict[str, object]:
        room_id = incident_room_id(work_id)
        history = self._history(room_id)
        members = self._validate(history, room_id, work_id)
        actor = _text(actor_principal, "actor_principal", 64)
        if actor not in members:
            raise ValueError("actor is not an incident member")
        operation = _text(operation_id, "operation_id", 128)
        body_hash = hashlib.sha256(_text(body, "body", MAX_ROOM_TEXT).encode("utf-8")).hexdigest()
        for existing in history:
            payload = existing.get("payload")
            if isinstance(payload, Mapping) and payload.get("operation_id") == operation:
                if payload.get("actor_principal") == actor and payload.get("body_sha256") == body_hash:
                    return {"event_id": existing.get("event_id"), "sequence": existing.get("sequence"), "idempotent": True,
                            "execution_authorized": False, "production_decision_authorized": False}
                raise ValueError("incident operation_id has conflicting material")
        last_event = max(history, key=lambda row: int(row.get("sequence", 0)))
        event = _room_event(room_id=room_id, work_id=work_id, actor_principal=actor, actor_kind=actor_kind,
                            action="message", title="Incident update", body=body, observed_at=observed_at or _now(),
                            members=members, causation_ids=(str(last_event["event_id"]),))
        payload = dict(event.payload or {})
        payload["operation_id"] = operation
        event = replace(event, payload=payload)
        return self._fabric.publish(event)

    def close(self, *, work_id: str, actor_principal: str, actor_kind: str, observed_at: str | None = None) -> dict[str, object]:
        room_id = incident_room_id(work_id)
        history = self._history(room_id)
        members = self._validate(history, room_id, work_id, allow_closed=True)
        actor = _text(actor_principal, "actor_principal", 64)
        if actor not in members:
            raise ValueError("actor is not an incident member")
        ordered = sorted(history, key=lambda row: int(row.get("sequence", 0)))
        if ordered[-1].get("payload", {}).get("action") == "closed":
            return {"event_id": ordered[-1]["event_id"], "idempotent": True,
                    "execution_authorized": False, "production_decision_authorized": False}
        event = _room_event(room_id=room_id, work_id=work_id, actor_principal=actor, actor_kind=actor_kind,
                            action="closed", title="Incident room closed", body="Incident response closed",
                            observed_at=observed_at or _now(), members=members,
                            causation_ids=(str(ordered[-1]["event_id"]),))
        return self._fabric.publish(event)

    def read(self, *, work_id: str, actor_principal: str) -> dict[str, object]:
        room_id = incident_room_id(work_id)
        history = self._history(room_id)
        members = self._validate(history, room_id, work_id)
        actor = _text(actor_principal, "actor_principal", 64)
        if actor not in members:
            raise ValueError("actor is not an incident member")
        return {"room_id": room_id, "work_id": work_id, "events": history,
                "execution_authorized": False, "production_decision_authorized": False}
