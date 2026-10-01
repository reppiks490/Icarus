"""Export/data integrity plane mirrored into the ICARUS trading interface.

The plane is diagnostic only. It cannot modify strategy inputs, broker state, orders,
positions, sizing, or execution authority.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

SCHEMA_VERSION = "icarus-interface-integrity-v2"
MANIFEST_SCHEMA = "icarus-interface-ledger-v2"
_EVENT_LOCK = threading.Lock()
_HEX40 = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)

_ALLOWED_EVENT_KEYS = {
    "kind",
    "area",
    "summary",
    "status",
    "severity",
    "source_repo",
    "source_branch",
    "source_commit",
    "verification",
    "interface_effect",
    "evidence",
    "details",
}
_ALLOWED_KINDS = {
    "repair",
    "audit",
    "evolution",
    "hardening",
    "provenance",
    "data_quality",
    "verification",
    "integration",
    "intake",
    "warning",
}
_ALLOWED_STATUS = {
    "verified",
    "repaired",
    "merged",
    "integrated_branch",
    "branch_only",
    "active",
    "pending",
    "blocked",
    "failed",
    "waived",
    "observed",
    "reconciled_with_note",
}
_ALLOWED_SEVERITY = {"info", "important", "warning", "high", "critical"}


def _manifest_path() -> Path:
    return Path(__file__).resolve().parents[1] / "integration" / "ICARUS_INTERFACE_LEDGER.json"


def _journal_path(base_dir: str | os.PathLike[str]) -> Path:
    return Path(base_dir) / "audit" / "interface_events.jsonl"


def _text(value: Any, name: str, limit: int, *, required: bool = False) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    value = value.strip()
    if required and not value:
        raise ValueError(f"{name} is required")
    if len(value) > limit:
        raise ValueError(f"{name} exceeds {limit} characters")
    return value


def _json_value(value: Any, name: str, limit: int) -> Any:
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as ex:
        raise ValueError(f"{name} must be finite JSON") from ex
    if len(raw.encode("utf-8")) > limit:
        raise ValueError(f"{name} exceeds {limit} bytes")
    return value


def _semantic_event(body: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(body, Mapping):
        raise ValueError("event must be an object")
    extra = set(body) - _ALLOWED_EVENT_KEYS
    if extra:
        raise ValueError("unknown integrity fields: " + ", ".join(sorted(extra)))

    kind = _text(body.get("kind"), "kind", 32, required=True).lower()
    status = _text(body.get("status", "observed"), "status", 32, required=True).lower()
    severity = _text(body.get("severity", "important"), "severity", 16, required=True).lower()
    if kind not in _ALLOWED_KINDS:
        raise ValueError("unsupported integrity kind")
    if status not in _ALLOWED_STATUS:
        raise ValueError("unsupported integrity status")
    if severity not in _ALLOWED_SEVERITY:
        raise ValueError("unsupported integrity severity")

    source_repo = _text(body.get("source_repo"), "source_repo", 160, required=True)
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", source_repo):
        raise ValueError("source_repo must be owner/repository")
    source_commit = _text(body.get("source_commit"), "source_commit", 40, required=True).lower()
    if not _HEX40.fullmatch(source_commit):
        raise ValueError("source_commit must be an exact 40-character Git SHA")

    evidence = body.get("evidence", [])
    if isinstance(evidence, str):
        evidence = [evidence]
    if not isinstance(evidence, list) or len(evidence) > 24:
        raise ValueError("evidence must be a list with at most 24 items")
    evidence = [_text(item, "evidence item", 600, required=True) for item in evidence]

    details = body.get("details", {})
    if not isinstance(details, dict):
        raise ValueError("details must be an object")
    details = _json_value(details, "details", 12288)

    return {
        "kind": kind,
        "area": _text(body.get("area"), "area", 120, required=True),
        "summary": _text(body.get("summary"), "summary", 1800, required=True),
        "status": status,
        "severity": severity,
        "source_repo": source_repo,
        "source_branch": _text(body.get("source_branch"), "source_branch", 180, required=True),
        "source_commit": source_commit,
        "verification": _text(body.get("verification"), "verification", 1800, required=True),
        "interface_effect": _text(body.get("interface_effect"), "interface_effect", 1200, required=True),
        "evidence": evidence,
        "details": details,
        "execution_authorized": False,
    }


def _event_id(semantic: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        dict(semantic),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _new_event(body: Mapping[str, Any], *, recorded_at: str | None = None, source: str = "mcp") -> dict[str, Any]:
    semantic = _semantic_event(body)
    event = dict(semantic)
    event["id"] = _event_id(semantic)
    event["recorded_at"] = recorded_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    event["source"] = _text(source, "source", 32, required=True)
    return event


def _stored_event(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError("stored event must be an object")
    if row.get("execution_authorized") is not False:
        raise ValueError("stored event cannot authorize execution")
    body = {key: row.get(key) for key in _ALLOWED_EVENT_KEYS if key in row}
    event = _new_event(
        body,
        recorded_at=_text(row.get("recorded_at"), "recorded_at", 80, required=True),
        source=_text(row.get("source", "mcp"), "source", 32, required=True),
    )
    supplied = _text(row.get("id"), "id", 64, required=True)
    if supplied != event["id"]:
        raise ValueError("stored event id does not match semantic payload")
    return event


def record_integrity_event(base_dir: str | os.PathLike[str], body: Mapping[str, Any]) -> dict[str, Any]:
    """Idempotently append one fully-provenanced MCP event to the dashboard ledger."""
    event = _new_event(body)
    path = _journal_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)

    with _EVENT_LOCK:
        if path.is_file():
            try:
                for line in path.read_text(encoding="utf-8").splitlines():
                    try:
                        prior = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(prior, dict) and prior.get("id") == event["id"]:
                        return {
                            "ok": True,
                            "idempotent": True,
                            "event": _stored_event(prior),
                            "execution_authorized": False,
                            "note": "integrity event already recorded; trading authority unchanged",
                        }
            except OSError:
                pass

        line = json.dumps(event, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())

    return {
        "ok": True,
        "idempotent": False,
        "event": event,
        "execution_authorized": False,
        "note": "integrity event recorded; trading authority unchanged",
    }


def _validate_manifest(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("manifest root must be an object")
    if data.get("schema_version") != MANIFEST_SCHEMA:
        raise ValueError("unsupported integrity manifest schema")
    if data.get("execution_authorized") is not False:
        raise ValueError("manifest must keep execution_authorized=false")

    policy = data.get("policy")
    if not isinstance(policy, dict) or policy.get("mcp_mirror_required") is not True:
        raise ValueError("MCP mirror policy is missing or disabled")

    for key in ("export_intake",):
        if not isinstance(data.get(key), dict):
            raise ValueError(f"{key} must be an object")
    for key in ("checklist", "repairs", "events"):
        if not isinstance(data.get(key), list):
            raise ValueError(f"{key} must be a list")

    normalized_events = []
    for raw in data["events"]:
        if not isinstance(raw, dict):
            raise ValueError("baseline event must be an object")
        recorded_at = _text(raw.get("recorded_at"), "recorded_at", 80, required=True)
        source = _text(raw.get("source", "mcp"), "source", 32, required=True)
        body = {key: raw.get(key) for key in _ALLOWED_EVENT_KEYS if key in raw}
        normalized_events.append(_new_event(body, recorded_at=recorded_at, source=source))
    out = dict(data)
    out["events"] = normalized_events
    return out


def _read_manifest(path: Path) -> tuple[dict[str, Any], str | None]:
    try:
        return _validate_manifest(json.loads(path.read_text(encoding="utf-8"))), None
    except Exception as ex:
        return {}, f"{type(ex).__name__}: {ex}"


def _read_runtime_events(path: Path, limit: int) -> tuple[list[dict[str, Any]], int]:
    if not path.is_file():
        return [], 0
    rows: list[dict[str, Any]] = []
    errors = 0
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return [], 1
    for line in lines[-max(limit * 4, limit):]:
        try:
            rows.append(_stored_event(json.loads(line)))
        except Exception:
            errors += 1
    return rows[-limit:], errors


def integrity_snapshot(
    base_dir: str | os.PathLike[str],
    *,
    limit: int = 200,
    manifest_path: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    """Return checked-in export integrity plus append-only MCP change receipts."""
    limit = max(1, min(1000, int(limit)))
    manifest, manifest_error = _read_manifest(Path(manifest_path) if manifest_path else _manifest_path())
    runtime, journal_errors = _read_runtime_events(_journal_path(base_dir), limit)
    events = list(manifest.get("events", [])) + runtime
    events.sort(key=lambda row: (str(row.get("recorded_at", "")), str(row.get("id", ""))))
    return {
        "schema_version": SCHEMA_VERSION,
        "execution_authorized": False,
        "policy": manifest.get("policy", {}),
        "audit_cutoff": manifest.get("audit_cutoff", {}),
        "export_intake": manifest.get("export_intake", {}),
        "checklist": manifest.get("checklist", []),
        "repairs": manifest.get("repairs", []),
        "events": events[-limit:],
        "runtime_event_count": len(runtime),
        "journal_errors": journal_errors,
        "manifest_error": manifest_error,
    }
