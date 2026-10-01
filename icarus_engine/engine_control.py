"""Authenticated, auditable application-level control plane for ICARUS.

The control plane intentionally does not expose arbitrary shell, filesystem, or
secret access. "Full control" here means full registered control of the running
ICARUS application and its attached subsystems. Every mutation is named,
typed, authenticated by the HTTP layer, confirmable when destructive, and
mirrored into System Intelligence.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Mapping

from .system_audit import append_system_event, load_repository_audit


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _compact(value: Any, depth: int = 0) -> Any:
    if depth > 4:
        return None
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:2000]
    if isinstance(value, Mapping):
        return {
            str(k)[:120]: _compact(v, depth + 1)
            for k, v in list(value.items())[:80]
        }
    if isinstance(value, (list, tuple)):
        return [_compact(v, depth + 1) for v in list(value)[:100]]
    return str(value)[:1000]


@dataclass(frozen=True)
class ControlAction:
    action_id: str
    title: str
    group: str
    description: str
    handler: Callable[[Dict[str, Any]], Any]
    danger: bool = False
    confirmation: str | None = None
    target: str = "none"

    def __post_init__(self) -> None:
        for name, value in (
            ("action_id", self.action_id),
            ("title", self.title),
            ("group", self.group),
            ("description", self.description),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required")
        if self.target not in {"none", "asset", "job"}:
            raise ValueError("target must be none, asset, or job")
        if self.danger and not self.confirmation:
            raise ValueError("dangerous actions require an exact confirmation phrase")

    def public(self) -> Dict[str, Any]:
        return {
            "id": self.action_id,
            "title": self.title,
            "group": self.group,
            "description": self.description,
            "danger": self.danger,
            "confirmation": self.confirmation,
            "target": self.target,
        }


class EngineControlPlane:
    """Registered ICARUS application controls with durable audit receipts."""

    def __init__(
        self,
        base_dir,
        *,
        snapshotters: Mapping[str, Callable[[], Any]],
        actions: Mapping[str, ControlAction],
    ):
        self.base_dir = base_dir
        self.snapshotters = dict(snapshotters)
        self.actions = dict(actions)
        if set(self.actions) != {a.action_id for a in self.actions.values()}:
            raise ValueError("action registry keys must equal ControlAction.action_id")

    def _snapshot_one(self, name: str, fn: Callable[[], Any]) -> Dict[str, Any]:
        try:
            return {"status": "ok", "data": _compact(fn())}
        except Exception as ex:
            return {
                "status": "error",
                "error": f"{type(ex).__name__}: {ex}"[:1000],
            }

    def status(self) -> Dict[str, Any]:
        subsystems = {
            name: self._snapshot_one(name, fn)
            for name, fn in sorted(self.snapshotters.items())
        }
        audit = load_repository_audit(self.base_dir)
        important = []
        for row in audit.get("events", [])[:80]:
            if not isinstance(row, dict):
                continue
            important.append({
                "id": row.get("id"),
                "kind": row.get("kind"),
                "severity": row.get("severity"),
                "title": row.get("title"),
                "detail": row.get("detail"),
                "recorded_at": row.get("recorded_at"),
                "repository": row.get("repository"),
                "ref": row.get("ref"),
            })
        return {
            "schema_version": "icarus-engine-control-v1",
            "generated_at": _utc_now(),
            "authority": {
                "admin_auth_required": True,
                "application_control": True,
                "arbitrary_shell": False,
                "arbitrary_filesystem": False,
                "secret_export": False,
                "broker_arming": False,
                "scope": "running ICARUS application and registered subsystems",
            },
            "summary": {
                "registered_actions": len(self.actions),
                "subsystems": len(subsystems),
                "subsystem_errors": sum(1 for x in subsystems.values() if x["status"] != "ok"),
                "important_events": len(important),
            },
            "actions": [self.actions[k].public() for k in sorted(self.actions)],
            "subsystems": subsystems,
            "important_events": important,
        }

    def run(self, body: Mapping[str, Any]) -> Dict[str, Any]:
        if not isinstance(body, Mapping):
            raise ValueError("control request must be an object")
        allowed = {"action", "target", "confirm", "reason", "args"}
        extra = set(body) - allowed
        if extra:
            raise ValueError(f"unknown control fields: {sorted(extra)}")
        action_id = str(body.get("action") or "").strip()
        action = self.actions.get(action_id)
        if action is None:
            raise ValueError(f"unknown engine-control action: {action_id or '(empty)'}")

        raw_target = str(body.get("target") or "").strip()
        target = raw_target.upper() if action.target == "asset" else raw_target
        if action.target != "none" and not target:
            raise ValueError(f"{action_id} requires target={action.target}")
        if action.target == "none" and target:
            raise ValueError(f"{action_id} does not accept a target")

        if action.confirmation is not None:
            supplied = str(body.get("confirm") or "")
            if supplied != action.confirmation:
                raise ValueError(
                    f"{action_id} requires exact confirmation: {action.confirmation}"
                )

        args = body.get("args") or {}
        if not isinstance(args, dict):
            raise ValueError("args must be an object")
        payload = {
            "target": target or None,
            "reason": str(body.get("reason") or "operator-control")[:160],
            "args": args,
        }

        started = _utc_now()
        try:
            result = action.handler(payload)
        except Exception as ex:
            append_system_event(self.base_dir, {
                "id": f"engine-control:{action_id}:{started}",
                "kind": "finding",
                "severity": "error",
                "title": f"Engine Control failed: {action.title}",
                "detail": f"{type(ex).__name__}: {ex}"[:2200],
                "recorded_at": started,
                "repository": "reppiks490/Icarus",
                "ref": action_id,
            })
            raise

        finished = _utc_now()
        event = append_system_event(self.base_dir, {
            "id": f"engine-control:{action_id}:{finished}",
            "kind": "integration",
            "severity": "success",
            "title": f"Engine Control: {action.title}",
            "detail": (
                f"action={action_id}"
                + (f" target={target}" if target else "")
                + f" reason={payload['reason']}"
            )[:2200],
            "recorded_at": finished,
            "repository": "reppiks490/Icarus",
            "ref": action_id,
        })
        return {
            "ok": True,
            "action": action.public(),
            "target": target or None,
            "started_at": started,
            "finished_at": finished,
            "result": _compact(result),
            "audit_recorded": True,
            "audit_status": event.get("status", "unknown"),
        }
