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
        return _attach_evolution(out, base_dir)
    try:
        out = normalize_repository_audit(json.loads(path.read_text(encoding="utf-8")))
        out["storage"] = {"source": "runtime", "path": str(path)}
        return _attach_evolution(out, base_dir)
    except Exception as ex:  # fail visibly; never report a corrupt runtime audit as green
        out = deepcopy(DEFAULT_REPOSITORY_AUDIT)
        out["status"] = "unknown"
        out["storage"] = {"source": "bundled-default", "path": str(path), "error": f"{type(ex).__name__}: {ex}"}
        out["note"] = "Runtime repository audit is unreadable; showing bundled snapshot only."
        return _attach_evolution(out, base_dir)


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


# Important MCP repairs/audits/evolutions are a separate durable stream so routine
# repository-audit refreshes cannot erase them.
EVOLUTION_FILENAME = "system_evolution.json"
_EVOLUTION_KINDS = {"repair", "audit", "evolution", "integration", "validation"}
_EVOLUTION_STATUS = {"planned", "in_progress", "blocked", "verified", "merged", "superseded"}
_EVOLUTION_SEVERITY = {"info", "notice", "warning", "critical"}

DEFAULT_SYSTEM_EVOLUTION: Dict[str, Any] = {
    "schema_version": 1,
    "source": "github-mcp",
    "recorded_at": "2026-10-01T02:20:00Z",
    "mirror_required": True,
    "execution_authorized": False,
    "production_authorized": False,
    "items": [
        {
            "id": "aion-parallax-causal-atlas-20260930",
            "subsystem": "AION / PARALLAX",
            "kind": "evolution",
            "status": "in_progress",
            "severity": "notice",
            "important": True,
            "summary": "PARALLAX now binds provenance-preserving fingerprints to causal AION frames, rejects future evidence, balances analog distance by source, and supports source ablation.",
            "detail": "Research-only. Verified outcomes remain separately gated and no execution authority is created.",
            "source_repo": "reppiks490/divine-providence",
            "source_branch": "sol/ml-subsystems-evolution-isolated-20260930",
            "source_commit": "ef1a197bee8424676c8e9c22ea7875e07c6fa4be",
            "validation_state": "tests_added",
            "interface_surface": "System",
        },
        {
            "id": "athena-causal-learning-repair-20260930",
            "subsystem": "ATHENA",
            "kind": "repair",
            "status": "in_progress",
            "severity": "warning",
            "important": True,
            "summary": "Restored ATHENA's stricter ingestion-time journal and fail-closed outcome-gated competence memory after detecting a weaker branch overwrite.",
            "detail": "Sequence gaps, blocked source-quality flags, production-plane learning, missing OOD evidence, future outcomes, and premature recording fail closed.",
            "source_repo": "reppiks490/divine-providence",
            "source_branch": "sol/ml-subsystems-evolution-isolated-20260930",
            "source_commit": "0245d4661b9051c5a79fcc84cca8fb2830d60956",
            "validation_state": "tests_added",
            "interface_surface": "System",
        },
        {
            "id": "argus-evidence-journal-20260930",
            "subsystem": "ARGUS",
            "kind": "evolution",
            "status": "in_progress",
            "severity": "notice",
            "important": True,
            "summary": "ARGUS has receipt-time microstructure journaling, deterministic depth replay, gap/recovery semantics, and explicit capability-based evidence-tier bridging.",
            "detail": "Candle proxies cannot become L2 by numeric tier coincidence; execution authorization remains false.",
            "source_repo": "reppiks490/divine-providence",
            "source_branch": "sol/ml-subsystems-evolution-isolated-20260930",
            "source_commit": "24381966a344ac7d48391ffecf4021b7e6da5d10",
            "validation_state": "linux_windows_green",
            "interface_surface": "System",
        },
        {
            "id": "intelligence-fabric-20260930",
            "subsystem": "NEXUS → AION/PARALLAX → ARGUS/ATHENA",
            "kind": "integration",
            "status": "blocked",
            "severity": "warning",
            "important": True,
            "summary": "A causal cross-system validation path was added; current CI exposed AION diagnostic mismatch plus pre-existing NEXUS sibling-contract drift failures that are being repaired before merge.",
            "detail": "The integration is not treated as verified while exact-head CI is red.",
            "source_repo": "reppiks490/divine-providence",
            "source_branch": "sol/ml-subsystems-evolution-isolated-20260930",
            "source_commit": "8576431cd109a889eca8cedd205dd2f033e57c3b",
            "validation_state": "ci_blocked",
            "interface_surface": "System",
        },
    ],
}


def evolution_path(base_dir: str | os.PathLike[str]) -> Path:
    return Path(base_dir) / EVOLUTION_FILENAME


def _normalize_evolution_item(row: Any, index: int) -> Dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError("each evolution item must be an object")
    ident = _text(row.get("id"), 120) or f"item-{index}"
    kind = _text(row.get("kind"), 24).lower()
    status = _text(row.get("status"), 24).lower()
    severity = _text(row.get("severity"), 24).lower()
    if kind not in _EVOLUTION_KINDS:
        raise ValueError(f"{ident}: invalid evolution kind")
    if status not in _EVOLUTION_STATUS:
        raise ValueError(f"{ident}: invalid evolution status")
    if severity not in _EVOLUTION_SEVERITY:
        raise ValueError(f"{ident}: invalid evolution severity")
    surface = _text(row.get("interface_surface"), 80)
    important = bool(row.get("important", True))
    return {
        "id": ident,
        "subsystem": _text(row.get("subsystem"), 160) or "UNKNOWN",
        "kind": kind,
        "status": status,
        "severity": severity,
        "important": important,
        "summary": _text(row.get("summary"), 1400),
        "detail": _text(row.get("detail"), 3000),
        "source_repo": _text(row.get("source_repo"), 200),
        "source_branch": _text(row.get("source_branch"), 240),
        "source_commit": _text(row.get("source_commit"), 80),
        "validation_state": _text(row.get("validation_state"), 80) or "unknown",
        "interface_surface": surface,
        "surface_status": "mirrored" if surface == "System" else ("required" if important else "not_required"),
        "execution_authorized": False,
        "production_authorized": False,
    }


def normalize_system_evolution(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("system evolution must be an object")
    raw_items = value.get("items") or []
    if not isinstance(raw_items, list):
        raise ValueError("system evolution items must be an array")
    items: list[Dict[str, Any]] = []
    ids: set[str] = set()
    for index, raw in enumerate(raw_items[:250]):
        item = _normalize_evolution_item(raw, index)
        if item["id"] in ids:
            raise ValueError(f"duplicate evolution item id: {item['id']}")
        ids.add(item["id"])
        items.append(item)
    mirror_ok = all((not x["important"]) or x["surface_status"] == "mirrored" for x in items)
    blocked = sum(1 for x in items if x["status"] == "blocked")
    in_progress = sum(1 for x in items if x["status"] == "in_progress")
    verified = sum(1 for x in items if x["status"] in {"verified", "merged"})
    return {
        "schema_version": 1,
        "source": _text(value.get("source", "mcp"), 80) or "mcp",
        "recorded_at": _text(value.get("recorded_at"), 64) or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "mirror_required": True,
        "mirror_ok": mirror_ok,
        "execution_authorized": False,
        "production_authorized": False,
        "summary": {
            "total": len(items),
            "important": sum(1 for x in items if x["important"]),
            "verified_or_merged": verified,
            "in_progress": in_progress,
            "blocked": blocked,
            "needs_attention": blocked + sum(1 for x in items if x["surface_status"] != "mirrored"),
        },
        "items": items,
    }


def load_system_evolution(base_dir: str | os.PathLike[str]) -> Dict[str, Any]:
    path = evolution_path(base_dir)
    if not path.exists():
        out = normalize_system_evolution(DEFAULT_SYSTEM_EVOLUTION)
        out["storage"] = {"source": "bundled-default", "path": str(path)}
        return out
    try:
        out = normalize_system_evolution(json.loads(path.read_text(encoding="utf-8")))
        out["storage"] = {"source": "runtime", "path": str(path)}
        return out
    except Exception as ex:
        out = normalize_system_evolution(DEFAULT_SYSTEM_EVOLUTION)
        out["mirror_ok"] = False
        out["storage"] = {"source": "bundled-default", "path": str(path), "error": f"{type(ex).__name__}: {ex}"}
        return out


def save_system_evolution(base_dir: str | os.PathLike[str], value: Any) -> Dict[str, Any]:
    evolution = normalize_system_evolution(value)
    path = evolution_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_name = None
    try:
        with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", suffix=".tmp", delete=False) as fh:
            tmp_name = fh.name
            json.dump(evolution, fh, indent=2, sort_keys=True, allow_nan=False)
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
    out = deepcopy(evolution)
    out["storage"] = {"source": "runtime", "path": str(path)}
    return out


def _attach_evolution(audit: Dict[str, Any], base_dir: str | os.PathLike[str]) -> Dict[str, Any]:
    audit["evolution"] = load_system_evolution(base_dir)
    # Repo CI can be green while an important subsystem evolution is still blocked.
    # Surface both states instead of hiding one inside an overall green badge.
    audit["system_attention"] = bool(
        audit["evolution"]["summary"]["needs_attention"]
        or audit["evolution"]["summary"]["in_progress"]
    )
    return audit
