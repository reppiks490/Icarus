"""Repository/MCP system-intelligence state shared by the engine API, dashboard, and MCP server.

The read endpoint is deliberately local-file-only: opening trader health must never
trigger GitHub/provider network I/O. Verified agents can publish repository audits,
loop durability receipts, and important repair/audit/evolution events through the
authenticated admin API (or MCP wrappers). This surface is diagnostic only and
never grants execution authority.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Dict
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

AUDIT_FILENAME = "repository_audit.json"
_ALLOWED_STATUS = {"green", "warn", "red", "unknown"}
_ALLOWED_EVENT_KIND = {"repair", "audit", "evolution", "integration", "finding"}
_ALLOWED_EVENT_SEVERITY = {"info", "success", "warn", "error"}
_AUDIT_LOCK = threading.Lock()

LOOP_FEED_SPECS = (
    {
        "id": "robustness-guardian",
        "title": "Robustness Guardian Evolution",
        "scheduler_id": "6abaf924e0248191b8a11bd1d32bf0b7",
        "schedule": ":05 hourly",
        "repository": "reppiks490/Icarus-engine",
        "root": "automation_intelligence/agent_fabric/robustness_guardian",
    },
    {
        "id": "advanced-csv",
        "title": "Advanced CSV Data Collector",
        "scheduler_id": "6abaef9d5c28819190d98a5af7f308b8",
        "schedule": ":15 hourly",
        "repository": "reppiks490/icarus-csv-evidence-lab",
        "root": "automation_intelligence/advanced_csv",
    },
    {
        "id": "alpha-synthesis",
        "title": "Alpha Synthesis Evolution",
        "scheduler_id": "6abaf8d75cf48191bc7ce06bc0006f1c",
        "schedule": ":25 hourly",
        "repository": "reppiks490/Icarus-engine",
        "root": "automation_intelligence/agent_fabric/alpha_synthesis",
    },
    {
        "id": "flow",
        "title": "Microstructure Sensor Grid",
        "scheduler_id": "6abaef8effb48191aa5c959455451681",
        "schedule": ":35 hourly",
        "repository": "reppiks490/Icarus-engine",
        "root": "automation_intelligence/flow",
    },
    {
        "id": "apex-council",
        "title": "Apex Council Evolution",
        "scheduler_id": "6ababd570fac81918777c8f809cf67c9",
        "schedule": ":45 hourly",
        "repository": "reppiks490/Icarus-engine",
        "root": "automation_intelligence/agent_fabric/apex_council",
    },
)

_SIGNAL_KEY_RE = re.compile(
    r"^(run_id|run_status|result|next|findings?|risks?|warnings?|errors?|built.*|verified.*|merged.*|"
    r"tests?.*|metrics?.*|artifacts?.*|blockers?.*|conflicts?.*|.*conflicts?.*|gaps?.*|.*gaps?.*|"
    r"coverage.*|baseline.*|net_new_delta|passes_completed|backlog_depth|oldest_unsent_run|"
    r"replayed_run_ids|duplicate_run_ids_skipped|new_.+|candidates?.*|components?.*|corpus.*|"
    r"evidence.*|.*evidence.*|data_quality.*|quality_notes?|persistence.*|.*findings?.*)$",
    re.IGNORECASE,
)
_SIGNAL_CONTAINER_KEYS = {
    "run_core",
    "authoritative_checkpoint",
    "authoritative_reconciliation",
    "observations",
    "source_provenance",
    "provenance_source_identities",
    "candidate_branches",
    "specialist_states_consumed",
    "test_state",
    "tests_workflows",
    "pr_state",
    "pr_commit_evidence",
    "decision_contract",
    "evidence_contract",
    "internal_topology",
    "disagreements_collisions",
    "unresolved_risks",
}

DEFAULT_REPOSITORY_AUDIT: Dict[str, Any] = {
    "schema_version": 2,
    "repository": "reppiks490/Icarus",
    "source": "github-mcp",
    "status": "green",
    "recorded_at": "2026-10-01T02:25:55Z",
    "main": {
        "sha": "ad010c6b3329ce25f3d6628e17d3da937dbae068",
        "workflow_run": 36805649545,
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
            "id": "audit:system-intelligence-main:ad010c6b",
            "kind": "audit",
            "severity": "success",
            "title": "System Intelligence integration verified on main",
            "detail": "Post-merge Linux and Windows CI both passed on the exact main merge SHA.",
            "recorded_at": "2026-10-01T02:25:55Z",
            "repository": "reppiks490/Icarus",
            "ref": "ad010c6b3329ce25f3d6628e17d3da937dbae068",
        },
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
    "loop_sync": {
        "enabled": True,
        "status": "bundled",
        "interval_seconds": 300,
        "source": "github-verified-loop-sync",
        "last_attempt_at": "",
        "last_success_at": "",
        "errors": [],
    },
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


def git_blob_sha(raw: bytes) -> str:
    """Return the Git object SHA-1 for raw file bytes."""
    header = b"blob " + str(len(raw)).encode("ascii") + b"\0"
    return hashlib.sha1(header + raw).hexdigest()


def _run_recorded_at(run_id: str) -> str:
    match = re.search(r"(\d{8}T\d{6}Z)", str(run_id or ""))
    if not match:
        return ""
    try:
        dt = datetime.strptime(match.group(1), "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")
    except ValueError:
        return ""


def _compact_value(value: Any, depth: int = 0) -> Any:
    """Bound diagnostic payloads so loop chatter can never bloat the trader state file."""
    if depth > 3:
        return None
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:1000]
    if isinstance(value, list):
        return [_compact_value(x, depth + 1) for x in value[:25]]
    if isinstance(value, dict):
        out: Dict[str, Any] = {}
        for key, item in list(value.items())[:40]:
            out[str(key)[:120]] = _compact_value(item, depth + 1)
        return out
    return str(value)[:1000]


def _signal_subset(value: Any, depth: int = 0) -> Dict[str, Any]:
    if not isinstance(value, dict) or depth > 3:
        return {}
    out: Dict[str, Any] = {}
    for key, item in value.items():
        name = str(key)
        lower = name.lower()
        if lower in _SIGNAL_CONTAINER_KEYS:
            out[name[:120]] = _compact_value(item)
            continue
        if _SIGNAL_KEY_RE.match(name):
            out[name[:120]] = _compact_value(item)
            continue
        if isinstance(item, dict):
            nested = _signal_subset(item, depth + 1)
            if nested:
                out[name[:120]] = nested
    return out


def _extract_signals(finalization: Dict[str, Any], latest: Any = None, state: Any = None) -> Dict[str, Any]:
    final_signals: Dict[str, Any] = {
        "work_status": _text(finalization.get("work_status"), 120),
        "completion_semantics": _text(finalization.get("completion_semantics"), 120),
        "payload": _compact_value(finalization.get("payload") or {}),
    }
    out: Dict[str, Any] = {"finalization": final_signals}
    latest_subset = _signal_subset(latest)
    state_subset = _signal_subset(state)
    if latest_subset:
        out["latest"] = latest_subset
    if state_subset:
        out["state"] = state_subset
    return out


def _parse_json_bytes(raw: bytes, label: str) -> Dict[str, Any]:
    try:
        value = json.loads(raw.decode("utf-8"))
    except Exception as ex:
        raise ValueError(f"{label} is not valid UTF-8 JSON: {ex}") from ex
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _default_fetch_bytes(repository: str, ref: str, path: str) -> bytes:
    """Fetch one GitHub text file. Public repos use raw GitHub; private repos may use a token."""
    token = os.environ.get("ICARUS_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN")
    timeout_raw = os.environ.get("ICARUS_LOOP_SYNC_HTTP_TIMEOUT_SECONDS", "8")
    try:
        timeout = max(1.0, min(30.0, float(timeout_raw)))
    except ValueError:
        timeout = 8.0
    safe_path = quote(path, safe="/")
    safe_ref = quote(ref, safe="")
    headers = {"User-Agent": "icarus-system-intelligence/1"}
    if token:
        url = f"https://api.github.com/repos/{repository}/contents/{safe_path}?ref={safe_ref}"
        headers["Accept"] = "application/vnd.github.raw+json"
        headers["Authorization"] = f"Bearer {token}"
    else:
        url = f"https://raw.githubusercontent.com/{repository}/{safe_ref}/{safe_path}"
    req = Request(url, headers=headers, method="GET")
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read((1 << 20) + 1)
    except HTTPError as ex:
        if ex.code == 404:
            raise FileNotFoundError(f"{repository}@{ref}:{path}") from ex
        raise RuntimeError(f"GitHub HTTP {ex.code} for {repository}@{ref}:{path}") from ex
    except URLError as ex:
        raise RuntimeError(f"GitHub fetch failed for {repository}@{ref}:{path}: {ex.reason}") from ex
    if len(raw) > (1 << 20):
        raise ValueError(f"GitHub file too large for loop intelligence: {repository}@{ref}:{path}")
    return raw


def collect_loop_snapshot(spec: Dict[str, Any], fetch_bytes=None):
    """Fetch and cryptographically cross-check one loop's current durable receipt."""
    fetch = fetch_bytes or _default_fetch_bytes
    repository = str(spec["repository"])
    root = str(spec["root"]).rstrip("/")
    final_path = f"{root}/finalization_state.json"
    heartbeat_path = f"{root}/heartbeat.json"

    final_raw = fetch(repository, "main", final_path)
    heartbeat_raw = fetch(repository, "main", heartbeat_path)
    finalization = _parse_json_bytes(final_raw, f"{spec['id']} finalization")
    heartbeat = _parse_json_bytes(heartbeat_raw, f"{spec['id']} heartbeat")

    commit_sha = _text(heartbeat.get("finalization_commit_sha"), 64)
    expected_blob = _text(heartbeat.get("finalization_state_blob_sha"), 64)
    current_blob = git_blob_sha(final_raw)
    committed_raw = fetch(repository, commit_sha, final_path) if commit_sha else b""
    committed_blob = git_blob_sha(committed_raw) if committed_raw else ""

    final_run = _text(finalization.get("RUN_ID"), 200)
    heartbeat_run = _text(heartbeat.get("RUN_ID"), 200)
    verification = {
        "run_id_matches": bool(final_run) and final_run == heartbeat_run,
        "run_status_matches": finalization.get("RUN_STATUS") == "RUN_PERSISTED" and heartbeat.get("RUN_STATUS") == "RUN_PERSISTED",
        "scheduler_matches": _text(heartbeat.get("scheduler_id"), 160) == _text(spec.get("scheduler_id"), 160),
        "execution_authorized_false": finalization.get("execution_authorized") is False and heartbeat.get("execution_authorized") is False,
        "current_blob_matches": bool(expected_blob) and current_blob == expected_blob,
        "commit_blob_matches": bool(expected_blob) and committed_blob == expected_blob,
        "current_equals_committed": bool(current_blob) and current_blob == committed_blob,
    }
    verified = all(verification.values())

    latest = None
    state = None
    for filename, target in (("latest.json", "latest"), ("state.json", "state")):
        try:
            obj = _parse_json_bytes(fetch(repository, "main", f"{root}/{filename}"), f"{spec['id']} {filename}")
        except FileNotFoundError:
            obj = None
        except Exception:
            obj = None
        if target == "latest":
            latest = obj
        else:
            state = obj

    failed = [key for key, ok in verification.items() if not ok]
    status = "RUN_PERSISTED" if verified else "RECEIPT_MISMATCH"
    detail = (
        "Automatic GitHub receipt verification passed: finalization, heartbeat, current blob, and exact commit binding agree."
        if verified else
        "Automatic GitHub receipt verification failed: " + ", ".join(failed)
    )
    row = {
        "id": spec["id"],
        "title": spec.get("title") or spec["id"],
        "scheduler_id": spec.get("scheduler_id", ""),
        "schedule": spec.get("schedule", ""),
        "status": status,
        "run_id": final_run or heartbeat_run,
        "recorded_at": _run_recorded_at(final_run or heartbeat_run),
        "repository": repository,
        "finalization_commit_sha": commit_sha,
        "finalization_state_blob_sha": current_blob,
        "detail": detail,
        "verification": verification,
        "signals": _extract_signals(finalization, latest, state),
    }
    event = {
        "id": f"loop:{spec['id']}:{row['run_id'] or 'unknown'}",
        "kind": "audit",
        "severity": "success" if verified else "error",
        "title": f"{row['title']} {'verified' if verified else 'receipt mismatch'}",
        "detail": detail,
        "recorded_at": row["recorded_at"] or _utc_now(),
        "repository": repository,
        "ref": commit_sha,
    }
    return row, event


def _normalize_loop(row: Any) -> Dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError("each loop must be an object")
    loop_id = _text(row.get("id"), 120)
    if not loop_id:
        raise ValueError("loop id is required")
    verification = row.get("verification") if isinstance(row.get("verification"), dict) else {}
    signals = row.get("signals") if isinstance(row.get("signals"), dict) else {}
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
        "verification": _compact_value(verification),
        "signals": _compact_value(signals),
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

    raw_loop_sync = value.get("loop_sync") or {}
    if not isinstance(raw_loop_sync, dict):
        raise ValueError("loop_sync must be an object")
    raw_sync_errors = raw_loop_sync.get("errors") or []
    if not isinstance(raw_sync_errors, list):
        raise ValueError("loop_sync.errors must be an array")

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
        "loop_sync": {
            "enabled": bool(raw_loop_sync.get("enabled", True)),
            "status": _text(raw_loop_sync.get("status", "unknown"), 32).lower() or "unknown",
            "interval_seconds": max(0, _nonnegative_int(raw_loop_sync.get("interval_seconds", 0), "loop_sync.interval_seconds")),
            "source": _text(raw_loop_sync.get("source", "github-verified-loop-sync"), 120) or "github-verified-loop-sync",
            "last_attempt_at": _text(raw_loop_sync.get("last_attempt_at"), 64),
            "last_success_at": _text(raw_loop_sync.get("last_success_at"), 64),
            "errors": [_text(x, 500) for x in raw_sync_errors[:32]],
        },
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



class LoopIntelligenceSync:
    """Background read-only GitHub synchronizer for the five ICARUS automation lanes."""

    def __init__(self, base_dir, specs=None, fetch_bytes=None, interval_seconds=None, enabled=None):
        self.base_dir = Path(base_dir)
        self.specs = list(specs or LOOP_FEED_SPECS)
        self.fetch_bytes = fetch_bytes or _default_fetch_bytes
        raw_interval = interval_seconds if interval_seconds is not None else os.environ.get("ICARUS_LOOP_SYNC_INTERVAL_SECONDS", "300")
        try:
            self.interval_seconds = max(60, int(raw_interval))
        except (TypeError, ValueError):
            self.interval_seconds = 300
        if enabled is None:
            flag = str(os.environ.get("ICARUS_LOOP_SYNC", "1")).strip().lower()
            enabled = flag not in {"0", "false", "off", "no"}
        self.enabled = bool(enabled)
        self._stop = threading.Event()
        self._thread = None

    def start(self) -> None:
        if not self.enabled or (self._thread and self._thread.is_alive()):
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="icarus-loop-intelligence-sync", daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=2.0)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.sync_once()
            except Exception:
                # The trading engine must never fail because observability synchronization failed.
                pass
            if self._stop.wait(self.interval_seconds):
                break

    def sync_once(self) -> Dict[str, Any]:
        attempt_at = _utc_now()
        initial = load_repository_audit(self.base_dir)
        initial_by_id = {row.get("id"): row for row in initial.get("loops", []) if isinstance(row, dict)}
        rows = []
        new_events = []
        errors = []

        for spec in self.specs:
            try:
                row, event = collect_loop_snapshot(spec, fetch_bytes=self.fetch_bytes)
            except Exception as ex:
                prev = deepcopy(initial_by_id.get(spec.get("id")) or {})
                row = {
                    "id": spec.get("id", ""),
                    "title": spec.get("title") or spec.get("id", ""),
                    "scheduler_id": spec.get("scheduler_id", ""),
                    "schedule": spec.get("schedule", ""),
                    "status": "SYNC_ERROR",
                    "run_id": prev.get("run_id", ""),
                    "recorded_at": prev.get("recorded_at", ""),
                    "repository": spec.get("repository", ""),
                    "finalization_commit_sha": prev.get("finalization_commit_sha", ""),
                    "finalization_state_blob_sha": prev.get("finalization_state_blob_sha", ""),
                    "detail": f"Automatic loop sync failed: {type(ex).__name__}: {ex}",
                    "verification": {"sync_error": True},
                    "signals": prev.get("signals", {}),
                }
                event = {
                    "id": f"loop-sync-error:{spec.get('id','unknown')}",
                    "kind": "finding",
                    "severity": "error",
                    "title": f"{row['title']} automatic sync failed",
                    "detail": row["detail"],
                    "recorded_at": attempt_at,
                    "repository": spec.get("repository", ""),
                    "ref": "",
                }
                errors.append(f"{spec.get('id','unknown')}: {type(ex).__name__}: {ex}")
            rows.append(row)
            new_events.append(event)

        statuses = {row.get("status") for row in rows}
        sync_status = "green" if statuses == {"RUN_PERSISTED"} else ("red" if "RECEIPT_MISMATCH" in statuses else "warn")

        with _AUDIT_LOCK:
            current = load_repository_audit(self.base_dir)
            current.pop("storage", None)
            managed_ids = {str(spec.get("id")) for spec in self.specs}
            unmanaged = [row for row in current.get("loops", []) if row.get("id") not in managed_ids]
            current["loops"] = rows + unmanaged

            events = list(current.get("events", []))
            for event in new_events:
                events = [event] + [old for old in events if old.get("id") != event.get("id")]
            current["events"] = events[:200]

            prior_sync = current.get("loop_sync") if isinstance(current.get("loop_sync"), dict) else {}
            current["loop_sync"] = {
                "enabled": self.enabled,
                "status": sync_status,
                "interval_seconds": self.interval_seconds,
                "source": "github-verified-loop-sync",
                "last_attempt_at": attempt_at,
                "last_success_at": attempt_at if sync_status == "green" else prior_sync.get("last_success_at", ""),
                "errors": errors,
            }
            current["recorded_at"] = attempt_at
            return save_repository_audit(self.base_dir, current)
