"""Read-only MCP/system evolution feed for the ICARUS operator interface.

Important repairs, audits, and subsystem evolutions are mirrored into
integration/SYSTEM_INTELLIGENCE.json and rendered in the dashboard. This module
never authorizes or changes trading behavior.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping


SCHEMA = "icarus.system-intelligence.v1"
_ALLOWED_STATUS = {"planned", "in_progress", "blocked", "verified", "merged", "superseded"}
_ALLOWED_KIND = {"repair", "audit", "evolution", "integration", "validation"}
_ALLOWED_SEVERITY = {"info", "notice", "warning", "critical"}


def _safe_str(value: Any, *, limit: int = 2000) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:limit]


def _manifest_path(base_dir: str | Path) -> Path:
    return Path(base_dir) / "integration" / "SYSTEM_INTELLIGENCE.json"


def _empty(detail: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "generated_at": None,
        "mirror_required": True,
        "mirror_ok": False,
        "execution_authorized": False,
        "production_authorized": False,
        "items": [],
        "warnings": [detail],
    }


def _normalize_item(raw: Mapping[str, Any], index: int) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    ident = _safe_str(raw.get("id"), limit=120) or f"item-{index}"
    subsystem = _safe_str(raw.get("subsystem"), limit=120) or "UNKNOWN"
    kind = _safe_str(raw.get("kind"), limit=40)
    if kind not in _ALLOWED_KIND:
        warnings.append(f"{ident}: invalid kind")
        kind = "audit"
    status = _safe_str(raw.get("status"), limit=40)
    if status not in _ALLOWED_STATUS:
        warnings.append(f"{ident}: invalid status")
        status = "blocked"
    severity = _safe_str(raw.get("severity"), limit=40)
    if severity not in _ALLOWED_SEVERITY:
        severity = "warning"
        warnings.append(f"{ident}: invalid severity")

    important = bool(raw.get("important", True))
    surface = _safe_str(raw.get("interface_surface"), limit=120)
    surface_status = "mirrored" if surface else ("required" if important else "not_required")
    if important and not surface:
        warnings.append(f"{ident}: important MCP change is not mirrored into the ICARUS interface")

    validation = raw.get("validation") if isinstance(raw.get("validation"), Mapping) else {}
    checks = validation.get("checks") if isinstance(validation.get("checks"), list) else []
    clean_checks = []
    for check in checks[:50]:
        if isinstance(check, Mapping):
            clean_checks.append({
                "name": _safe_str(check.get("name"), limit=160),
                "status": _safe_str(check.get("status"), limit=40) or "unknown",
                "detail": _safe_str(check.get("detail"), limit=800),
            })

    item = {
        "id": ident,
        "subsystem": subsystem,
        "kind": kind,
        "status": status,
        "severity": severity,
        "important": important,
        "summary": _safe_str(raw.get("summary"), limit=1200),
        "detail": _safe_str(raw.get("detail"), limit=4000),
        "source_repo": _safe_str(raw.get("source_repo"), limit=240),
        "source_branch": _safe_str(raw.get("source_branch"), limit=240),
        "source_commit": _safe_str(raw.get("source_commit"), limit=80),
        "updated_at": _safe_str(raw.get("updated_at"), limit=80),
        "interface_surface": surface,
        "surface_status": surface_status,
        "validation": {
            "state": _safe_str(validation.get("state"), limit=80) or "unknown",
            "checks": clean_checks,
        },
        "execution_authorized": False,
        "production_authorized": False,
    }
    return item, warnings


def load(base_dir: str | Path) -> dict[str, Any]:
    path = _manifest_path(base_dir)
    if not path.is_file():
        return _empty(f"system-intelligence manifest missing: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return _empty(f"system-intelligence manifest unreadable: {type(exc).__name__}: {exc}")

    if not isinstance(raw, Mapping):
        return _empty("system-intelligence manifest must be an object")

    warnings: list[str] = []
    if raw.get("schema") != SCHEMA:
        warnings.append(f"unsupported schema: {raw.get('schema')!r}")

    source_items = raw.get("items")
    if not isinstance(source_items, list):
        source_items = []
        warnings.append("manifest items must be a list")

    items = []
    ids = set()
    for index, source in enumerate(source_items):
        if not isinstance(source, Mapping):
            warnings.append(f"item-{index}: item must be an object")
            continue
        item, item_warnings = _normalize_item(source, index)
        if item["id"] in ids:
            warnings.append(f"{item['id']}: duplicate item id")
            continue
        ids.add(item["id"])
        items.append(item)
        warnings.extend(item_warnings)

    mirror_ok = all((not item["important"]) or item["surface_status"] == "mirrored" for item in items)
    return {
        "schema": SCHEMA,
        "generated_at": _safe_str(raw.get("generated_at"), limit=80) or None,
        "mirror_required": True,
        "mirror_ok": mirror_ok,
        "execution_authorized": False,
        "production_authorized": False,
        "policy": {
            "important_mcp_changes_must_surface_in_interface": True,
            "surface": "Intelligence",
            "read_only": True,
        },
        "items": items,
        "warnings": warnings,
    }


def report(base_dir: str | Path, *, runtime: Mapping[str, Any] | None = None) -> dict[str, Any]:
    result = load(base_dir)
    items = result["items"]
    status_counts: dict[str, int] = {}
    for item in items:
        status_counts[item["status"]] = status_counts.get(item["status"], 0) + 1
    result["summary"] = {
        "total": len(items),
        "important": sum(1 for item in items if item["important"]),
        "verified_or_merged": sum(1 for item in items if item["status"] in {"verified", "merged"}),
        "needs_attention": sum(1 for item in items if item["status"] in {"blocked", "in_progress"} or item["surface_status"] != "mirrored"),
        "status_counts": status_counts,
    }
    runtime = runtime if isinstance(runtime, Mapping) else {}
    result["runtime"] = {
        "reported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "feed_mode": _safe_str(runtime.get("feed_mode"), limit=80),
        "running_assets": [str(x)[:40] for x in runtime.get("running_assets", [])] if isinstance(runtime.get("running_assets"), list) else [],
        "all_warm": bool(runtime.get("all_warm", False)),
    }
    return result
