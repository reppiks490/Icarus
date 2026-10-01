"""Repository/MCP system-intelligence state shared by the engine API, dashboard, and MCP server.

The read endpoint is deliberately local-file-only: opening trader health must never
trigger GitHub/provider network I/O. Verified agents can publish repository audits,
loop durability receipts, and important repair/audit/evolution events through the
authenticated admin API (or MCP wrappers). This surface is diagnostic only and
never grants execution authority.
"""
from __future__ import annotations

import json
import os
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Dict

AUDIT_FILENAME = "repository_audit.json"
_ALLOWED_STATUS = {"green", "warn", "red", "unknown"}
_ALLOWED_EVENT_KIND = {"repair", "audit", "evolution", "integration", "finding"}
_ALLOWED_EVENT_SEVERITY = {"info", "success", "warn", "error"}
_AUDIT_LOCK = threading.Lock()

DEFAULT_REPOSITORY_AUDIT: Dict[str, Any] = {
    "schema_version": 2,
    "repository": "reppiks490/Icarus",
    "source": "github-mcp",
    "status": "green",
    "recorded_at": "2026-10-01T02:24:49Z",
    "main": {
        "sha": "3bedc5a3a122caa063a7a473bf4585c9b74febd2",
        "workflow_run": 36804732200,
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
    "loops": [
        {
            "id": "robustness-guardian",
            "title": "Robustness Guardian Evolution",
            "scheduler_id": "6abaf924e0248191b8a11bd1d32bf0b7",
            "schedule": ":05 hourly",
            "status": "RUN_PERSISTED",
            "run_id": "robustness-guardian-20261001T020500Z",
            "recorded_at": "2026-10-01T02:20:21Z",
            "repository": "reppiks490/Icarus-engine",
            "finalization_commit_sha": "db87576f36988577a153db99f692be73cfb64167",
            "finalization_state_blob_sha": "02fab3bce986b5dbbcbf5e5d1ec6915c160cfa4c",
            "detail": "Stale receipt repaired; matching finalization and heartbeat binding reread and verified.",
        },
        {
            "id": "advanced-csv",
            "title": "Advanced CSV Data Collector",
            "scheduler_id": "6abaef9d5c28819190d98a5af7f308b8",
            "schedule": ":15 hourly",
            "status": "RUN_PERSISTED",
            "run_id": "advanced-csv-20261001T021500Z",
            "recorded_at": "2026-10-01T02:24:49Z",
            "repository": "reppiks490/icarus-csv-evidence-lab",
            "finalization_commit_sha": "64cf1ac4268cc0494ed27caa487ed5e18aef8ad5",
            "finalization_state_blob_sha": "5ce94ccd12b0b6417ce62d86eaa3193c05a21252",
            "detail": "Stale 02:15Z slot repaired; matching finalization and heartbeat binding reread and verified.",
        },
        {
            "id": "alpha-synthesis",
            "title": "Alpha Synthesis Evolution",
            "scheduler_id": "6abaf8d75cf48191bc7ce06bc0006f1c",
            "schedule": ":25 hourly",
            "status": "RUN_PERSISTED",
            "run_id": "alpha-synthesis-20261001T012500Z",
            "recorded_at": "2026-10-01T02:20:26Z",
            "repository": "reppiks490/Icarus-engine",
            "finalization_commit_sha": "0004a4af3d579c5b6f6ccabec102a8010e36677f",
            "finalization_state_blob_sha": "6e5255c94c284a4af0fed88656e92689ee89f615",
            "detail": "Stale receipt repaired; matching finalization and heartbeat binding reread and verified.",
        },
        {
            "id": "flow",
            "title": "Microstructure Sensor Grid",
            "scheduler_id": "6abaef8effb48191aa5c959455451681",
            "schedule": ":35 hourly",
            "status": "RUN_PERSISTED",
            "run_id": "flow-20261001T013500Z",
            "repository": "reppiks490/Icarus-engine",
            "finalization_commit_sha": "cac7d9daad70edd45539d29ac5529ae71339b311",
            "finalization_state_blob_sha": "de8655ce63e18428c3675b82ec16e8bd162d3908",
            "detail": "Matching finalization and heartbeat receipt verified.",
        },
        {
            "id": "apex-council",
            "title": "Apex Council Evolution",
            "scheduler_id": "6ababd570fac81918777c8f809cf67c9",
            "schedule": ":45 hourly",
            "status": "RUN_PERSISTED",
            "run_id": "apex-council-20261001T014500Z",
            "recorded_at": "2026-10-01T02:20:31Z",
            "repository": "reppiks490/Icarus-engine",
            "finalization_commit_sha": "273558d55a6befc1b441838e16b278fcd4a2ccfb",
            "finalization_state_blob_sha": "5cffa87ce7d75a78003c3f4a1a06dfed8145d2d2",
            "detail": "Stale receipt repaired; matching finalization and heartbeat binding reread and verified.",
        },
    ],
    "events": [
        {
            "id": "repair:advanced-csv:0215",
            "kind": "repair",
            "severity": "success",
            "title": "Advanced CSV durability receipt repaired",
            "detail": "Restored the 02:15Z RUN_PERSISTED finalization/heartbeat pair and verified exact commit/blob binding.",
            "recorded_at": "2026-10-01T02:24:49Z",
            "repository": "reppiks490/icarus-csv-evidence-lab",
            "ref": "6f9dbb613d2b987175f72d6ee556224418f0467e",
        },
        {
            "id": "repair:apex-council:0145",
            "kind": "repair",
            "severity": "success",
            "title": "Apex Council durability receipt repaired",
            "detail": "Restored the 01:45Z RUN_PERSISTED finalization/heartbeat pair and verified exact commit/blob binding.",
            "recorded_at": "2026-10-01T02:20:31Z",
            "repository": "reppiks490/Icarus-engine",
            "ref": "288ddcc0449dd7c339ff13bad8ede49267acf952",
        },
        {
            "id": "repair:alpha-synthesis:0125",
            "kind": "repair",
            "severity": "success",
            "title": "Alpha Synthesis durability receipt repaired",
            "detail": "Restored the 01:25Z RUN_PERSISTED finalization/heartbeat pair and verified exact commit/blob binding.",
            "recorded_at": "2026-10-01T02:20:26Z",
            "repository": "reppiks490/Icarus-engine",
            "ref": "aa232e14243db01e9df51e716c28714ebcfdd4e5",
        },
        {
            "id": "repair:robustness-guardian:0205",
            "kind": "repair",
            "severity": "success",
            "title": "Robustness Guardian durability receipt repaired",
            "detail": "Restored the 02:05Z RUN_PERSISTED finalization/heartbeat pair and verified exact commit/blob binding.",
            "recorded_at": "2026-10-01T02:20:21Z",
            "repository": "reppiks490/Icarus-engine",
            "ref": "5749cb0dd141f7d813ef00d8bfe8d07ee543a862",
        },
        {
            "id": "integration:3bedc5a3",
            "kind": "integration",
            "severity": "success",
            "title": "Repository MCP audit dashboard merged",
            "detail": "Verified repository/CI audit is now exposed in the ICARUS trader UI and local MCP surface.",
            "recorded_at": "2026-10-01T02:12:26Z",
            "repository": "reppiks490/Icarus",
            "ref": "3bedc5a3a122caa063a7a473bf4585c9b74febd2",
        }
    ],
    "issue": {"number": 62, "url": "https://github.com/reppiks490/Icarus/issues/62"},
    "note": "Current-head repository audit plus MCP-visible system intelligence. Historical superseded red runs are not counted as current defects.",
    "execution_authorized": False,
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


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalize_loop(row: Any) -> Dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError("each loop must be an object")
    loop_id = _text(row.get("id"), 120)
    if not loop_id:
        raise ValueError("loop id is required")
    return {
        "id": loop_id,
        "title": _text(row.get("title") or loop_id, 160),
        "scheduler_id": _text(row.get("scheduler_id"), 160),
        "schedule": _text(row.get("schedule"), 120),
        "status": _text(row.get("status", "UNKNOWN"), 64).upper() or "UNKNOWN",
        "run_id": _text(row.get("run_id"), 200),
        "recorded_at": _text(row.get("recorded_at"), 64),
        "repository": _text(row.get("repository"), 200),
        "finalization_commit_sha": _text(row.get("finalization_commit_sha"), 64),
        "finalization_state_blob_sha": _text(row.get("finalization_state_blob_sha"), 64),
        "detail": _text(row.get("detail"), 1000),
    }


def _normalize_event(row: Any) -> Dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError("each event must be an object")
    kind = _text(row.get("kind", "finding"), 32).lower() or "finding"
    severity = _text(row.get("severity", "info"), 32).lower() or "info"
    if kind not in _ALLOWED_EVENT_KIND:
        raise ValueError("event kind must be repair, audit, evolution, integration, or finding")
    if severity not in _ALLOWED_EVENT_SEVERITY:
        raise ValueError("event severity must be info, success, warn, or error")
    title = _text(row.get("title"), 200)
    if not title:
        raise ValueError("event title is required")
    recorded_at = _text(row.get("recorded_at"), 64) or _utc_now()
    event_id = _text(row.get("id"), 200) or _text(f"{kind}:{recorded_at}:{title}", 200)
    return {
        "id": event_id,
        "kind": kind,
        "severity": severity,
        "title": title,
        "detail": _text(row.get("detail"), 2000),
        "recorded_at": recorded_at,
        "repository": _text(row.get("repository"), 200),
        "ref": _text(row.get("ref"), 500),
    }


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

    raw_loops = value.get("loops") or []
    if not isinstance(raw_loops, list):
        raise ValueError("loops must be an array")
    loops = [_normalize_loop(row) for row in raw_loops[:32]]

    raw_events = value.get("events") or []
    if not isinstance(raw_events, list):
        raise ValueError("events must be an array")
    events = [_normalize_event(row) for row in raw_events[:200]]

    recorded_at = _text(value.get("recorded_at"), 64) or _utc_now()

    out: Dict[str, Any] = {
        "schema_version": 2,
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
        "loops": loops,
        "events": events,
        "issue": {
            "number": _nonnegative_int(issue_in.get("number", 0), "issue.number"),
            "url": _text(issue_in.get("url"), 500),
        },
        "note": _text(value.get("note"), 1000),
        "execution_authorized": False,
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
    except Exception as ex:
        out = deepcopy(DEFAULT_REPOSITORY_AUDIT)
        out["status"] = "unknown"
        out["storage"] = {"source": "bundled-default", "path": str(path), "error": f"{type(ex).__name__}: {ex}"}
        out["note"] = "Runtime system-intelligence audit is unreadable; showing bundled snapshot only."
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


def append_system_event(base_dir: str | os.PathLike[str], event: Any) -> Dict[str, Any]:
    """Atomically append/replace one diagnostic MCP event without touching trading state."""
    normalized = _normalize_event(event)
    with _AUDIT_LOCK:
        current = load_repository_audit(base_dir)
        current.pop("storage", None)
        prior = [row for row in current.get("events", []) if row.get("id") != normalized["id"]]
        current["events"] = [normalized, *prior][:200]
        current["recorded_at"] = normalized["recorded_at"]
        return save_repository_audit(base_dir, current)


def upsert_loop_status(base_dir: str | os.PathLike[str], loop: Any) -> Dict[str, Any]:
    """Atomically publish one loop receipt/status row, keyed by loop id."""
    normalized = _normalize_loop(loop)
    if not normalized["recorded_at"]:
        normalized["recorded_at"] = _utc_now()
    with _AUDIT_LOCK:
        current = load_repository_audit(base_dir)
        current.pop("storage", None)
        prior = [row for row in current.get("loops", []) if row.get("id") != normalized["id"]]
        current["loops"] = [normalized, *prior][:32]
        current["recorded_at"] = normalized["recorded_at"]
        return save_repository_audit(base_dir, current)
