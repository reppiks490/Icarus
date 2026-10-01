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
import json
import math
import re
import threading

from .system_audit import append_system_event, load_repository_audit


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _compact(value: Any, depth: int = 0) -> Any:
    if depth > 4:
        return None
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
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
    args_example: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("action_id", self.action_id),
            ("title", self.title),
            ("group", self.group),
            ("description", self.description),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} is required")
            if value != value.strip():
                raise ValueError(f"{name} must be trimmed")
        if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,119}", self.action_id):
            raise ValueError("action_id must be a canonical lowercase identifier")
        if not callable(self.handler):
            raise TypeError("handler must be callable")
        if self.target not in {"none", "asset", "job", "candidate", "proposal", "source"}:
            raise ValueError("unsupported target type")
        if self.danger and not self.confirmation:
            raise ValueError("dangerous actions require an exact confirmation phrase")
        if self.args_example is not None:
            if not isinstance(self.args_example, Mapping):
                raise TypeError("args_example must be a mapping or None")
            try:
                json.dumps(self.args_example, sort_keys=True, separators=(",", ":"), allow_nan=False)
            except (TypeError, ValueError) as ex:
                raise ValueError("args_example must be finite JSON data") from ex

    def public(self) -> Dict[str, Any]:
        return {
            "id": self.action_id,
            "title": self.title,
            "group": self.group,
            "description": self.description,
            "danger": self.danger,
            "confirmation": self.confirmation,
            "target": self.target,
            "args_example": _compact(dict(self.args_example)) if self.args_example is not None else None,
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
        self._lock = threading.RLock()

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
        groups: Dict[str, int] = {}
        for action in self.actions.values():
            groups[action.group] = groups.get(action.group, 0) + 1
        return {
            "schema_version": "icarus-engine-control-v2",
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
                "action_groups": dict(sorted(groups.items())),
            },
            "actions": [self.actions[k].public() for k in sorted(self.actions)],
            "subsystems": subsystems,
            "important_events": important,
        }

    def run(self, body: Mapping[str, Any]) -> Dict[str, Any]:
        if not isinstance(body, Mapping):
            raise ValueError("control request must be an object")
        try:
            json.dumps(body, sort_keys=True, separators=(",", ":"), allow_nan=False)
        except (TypeError, ValueError) as ex:
            raise ValueError("control request must be finite JSON data") from ex
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

        args = body.get("args", {})
        if args is None:
            args = {}
        if not isinstance(args, dict):
            raise ValueError("args must be an object")
        payload = {
            "target": target or None,
            "reason": str(body.get("reason") or "operator-control")[:160],
            "args": args,
        }

        started = _utc_now()
        event_id = f"engine-control:{action_id}:{started}"
        intent = {
            "id": event_id,
            "kind": "integration",
            "severity": "info",
            "title": f"Engine Control requested: {action.title}",
            "detail": (
                f"action={action_id}"
                + (f" target={target}" if target else "")
                + f" reason={payload['reason']} status=REQUESTED"
            )[:2200],
            "recorded_at": started,
            "repository": "reppiks490/Icarus",
            "ref": action_id,
        }

        with self._lock:
            # Mutation is forbidden if the durable intent receipt cannot be written.
            append_system_event(self.base_dir, intent)
            try:
                result = action.handler(payload)
            except Exception as ex:
                failed = dict(intent)
                failed.update({
                    "severity": "error",
                    "title": f"Engine Control failed: {action.title}",
                    "detail": (
                        f"action={action_id}"
                        + (f" target={target}" if target else "")
                        + f" error={type(ex).__name__}: {ex}"
                    )[:2200],
                    "recorded_at": _utc_now(),
                })
                try:
                    append_system_event(self.base_dir, failed)
                except Exception:
                    # The pre-mutation intent remains durable even if finalization
                    # cannot update it; do not hide the real command exception.
                    pass
                raise

            finished = _utc_now()
            completed = dict(intent)
            completed.update({
                "severity": "success",
                "title": f"Engine Control: {action.title}",
                "detail": (
                    f"action={action_id}"
                    + (f" target={target}" if target else "")
                    + f" reason={payload['reason']} status=SUCCEEDED"
                )[:2200],
                "recorded_at": finished,
            })
            audit_recorded = True
            audit_error = None
            try:
                append_system_event(self.base_dir, completed)
            except Exception as ex:
                # State already changed; the durable REQUESTED intent is retained.
                audit_recorded = False
                audit_error = f"{type(ex).__name__}: {ex}"[:1000]
        return {
            "ok": True,
            "note": f"{action.title} completed",
            "action": action.public(),
            "target": target or None,
            "started_at": started,
            "finished_at": finished,
            "result": _compact(result),
            "audit_recorded": audit_recorded,
            "audit_error": audit_error,
        }
