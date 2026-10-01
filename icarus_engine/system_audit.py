"""Repository/MCP audit state shared by the engine API, dashboard, and MCP server.

The status endpoint is deliberately local-file-only: reading trader health must never
trigger GitHub/provider network I/O. A verified agent can update the snapshot through
the authenticated /admin/system/audit endpoint (or the MCP wrapper).
"""
from __future__ import annotations

import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Dict

AUDIT_FILENAME = "repository_audit.json"
_ALLOWED_STATUS = {"green", "warn", "red", "unknown"}

DEFAULT_REPOSITORY_AUDIT: Dict[str, Any] = {
    "schema_version": 1,
    "repository": "reppiks490/Icarus",
    "source": "github-mcp",
    "status": "green",
    "recorded_at": "2026-10-01T02:01:54Z",
    "main": {
        "sha": "427c4a1f60c91f72cd6d16d6218b25105e12e93a",
        "workflow_run": 36802107082,
        "linux": "success",
        "windows": "success",
    },
    "summary": {
        "branches_audited": 62,
        "current_head_failures": 0,
        "pending": 0,
        "unresolved": 0,
    },
    "checks": [
        {"name": "main / engine", "status": "success", "detail": "Linux engine job succeeded on exact main head"},
        {"name": "main / engine-windows", "status": "success", "detail": "Windows engine job succeeded on exact main head"},
        {"name": "codex/exotic-research-loop", "status": "success", "detail": "Exact head 64d3e322e033 passed tests"},
        {"name": "codex/ml-d9d4db8", "status": "success", "detail": "Exact head f897686b7c0d passed tests"},
        {"name": "chatgpt/real-subminute-tick-adapter", "status": "success", "detail": "Exact head 8a21fd6e848e passed tests"},
    ],
    "issue": {"number": 62, "url": "https://github.com/reppiks490/Icarus/issues/62"},
    "note": "Current-head audit snapshot. Historical superseded red runs are not counted as current defects.",
}


def repository_audit_path(base_dir: str | os.PathLike[str]) -> Path:
    return Path(base_dir) / AUDIT_FILENAME


def _text(value: Any, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _nonnegative_int(value: Any, name: str) -> int:
    try:
        out = int(value)
    except (TypeError, ValueError) as ex:
        raise ValueError(f"{name} must be an integer") from ex
    if out < 0:
        raise ValueError(f"{name} must be non-negative")
    return out


def normalize_repository_audit(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("audit must be an object")
    status = _text(value.get("status", "unknown"), 16).lower() or "unknown"
    if status not in _ALLOWED_STATUS:
        raise ValueError("audit status must be green, warn, red, or unknown")

    main_in = value.get("main") or {}
    summary_in = value.get("summary") or {}
    issue_in = value.get("issue") or {}
    if not isinstance(main_in, dict) or not isinstance(summary_in, dict) or not isinstance(issue_in, dict):
        raise ValueError("main, summary, and issue must be objects")

    checks = []
    raw_checks = value.get("checks") or []
    if not isinstance(raw_checks, list):
        raise ValueError("checks must be an array")
    for row in raw_checks[:100]:
        if not isinstance(row, dict):
            raise ValueError("each check must be an object")
        checks.append({
            "name": _text(row.get("name"), 120),
            "status": _text(row.get("status", "unknown"), 32).lower() or "unknown",
            "detail": _text(row.get("detail"), 500),
        })

    recorded_at = _text(value.get("recorded_at"), 64)
    if not recorded_at:
        recorded_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    out: Dict[str, Any] = {
        "schema_version": 1,
        "repository": _text(value.get("repository", "reppiks490/Icarus"), 160) or "reppiks490/Icarus",
        "source": _text(value.get("source", "mcp"), 64) or "mcp",
        "status": status,
        "recorded_at": recorded_at,
        "main": {
            "sha": _text(main_in.get("sha"), 64),
            "workflow_run": _nonnegative_int(main_in.get("workflow_run", 0), "main.workflow_run"),
            "linux": _text(main_in.get("linux", "unknown"), 32).lower() or "unknown",
            "windows": _text(main_in.get("windows", "unknown"), 32).lower() or "unknown",
        },
        "summary": {
            "branches_audited": _nonnegative_int(summary_in.get("branches_audited", 0), "summary.branches_audited"),
            "current_head_failures": _nonnegative_int(summary_in.get("current_head_failures", 0), "summary.current_head_failures"),
            "pending": _nonnegative_int(summary_in.get("pending", 0), "summary.pending"),
            "unresolved": _nonnegative_int(summary_in.get("unresolved", 0), "summary.unresolved"),
        },
        "checks": checks,
        "issue": {
            "number": _nonnegative_int(issue_in.get("number", 0), "issue.number"),
            "url": _text(issue_in.get("url"), 500),
        },
        "note": _text(value.get("note"), 1000),
    }
    return out


def load_repository_audit(base_dir: str | os.PathLike[str]) -> Dict[str, Any]:
    path = repository_audit_path(base_dir)
    if not path.exists():
        out = deepcopy(DEFAULT_REPOSITORY_AUDIT)
        out["storage"] = {"source": "bundled-default", "path": str(path)}
        return out
    try:
        out = normalize_repository_audit(json.loads(path.read_text(encoding="utf-8")))
        out["storage"] = {"source": "runtime", "path": str(path)}
        return out
    except Exception as ex:  # fail visibly; never report a corrupt runtime audit as green
        out = deepcopy(DEFAULT_REPOSITORY_AUDIT)
        out["status"] = "unknown"
        out["storage"] = {"source": "bundled-default", "path": str(path), "error": f"{type(ex).__name__}: {ex}"}
        out["note"] = "Runtime repository audit is unreadable; showing bundled snapshot only."
        return out


def save_repository_audit(base_dir: str | os.PathLike[str], value: Any) -> Dict[str, Any]:
    audit = normalize_repository_audit(value)
    path = repository_audit_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_name = None
    try:
        with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as fh:
            tmp_name = fh.name
            json.dump(audit, fh, indent=2, sort_keys=True, allow_nan=False)
            fh.write("\n")
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
        tmp_name = None
    finally:
        if tmp_name:
            try:
                os.unlink(tmp_name)
            except FileNotFoundError:
                pass
    out = deepcopy(audit)
    out["storage"] = {"source": "runtime", "path": str(path)}
    return out
