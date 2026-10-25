"""Read bounded, committed discovery-catalog receipts without opening the DB."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
import re
from typing import Any


_CATALOGS = (
    ("api-mega-list", "cporter202/API-mega-list"),
    ("scraping-apis-for-devs", "cporter202/scraping-apis-for-devs"),
    ("ai-agent-tools", "cporter202/ai-agent-tools"),
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_SUMMARY_FIELDS = (
    "raw_count", "imported_entries", "unique_candidates", "duplicate_groups",
    "rejected", "review_required", "parse_failures",
)
_MAX_RECEIPT_BYTES = 64 * 1024


def _nonnegative_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value >= 0 else None


def _catalog_row(root: Path, catalog_id: str, upstream_repo: str) -> dict[str, object]:
    path = root / "automation_intelligence" / "catalog_registry_v1" / "latest" / f"{catalog_id}.json"
    try:
        if path.is_symlink():
            raise ValueError("UNSAFE_RECEIPT_PATH")
        resolved = path.resolve(strict=True)
        if root not in resolved.parents or not resolved.is_file():
            raise ValueError("UNSAFE_RECEIPT_PATH")
        if resolved.stat().st_size > _MAX_RECEIPT_BYTES:
            raise ValueError("RECEIPT_TOO_LARGE")
        payload = json.loads(resolved.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("INVALID_RECEIPT")
        summary = payload.get("import_summary")
        if not isinstance(summary, dict):
            raise ValueError("INVALID_RECEIPT")
        commit = payload.get("upstream_commit")
        digest = payload.get("content_sha256")
        retrieved_at = payload.get("retrieved_at")
        parsed_time = datetime.fromisoformat(retrieved_at.replace("Z", "+00:00")) if isinstance(retrieved_at, str) else None
        if (payload.get("catalog_id") != catalog_id or payload.get("upstream_repo") != upstream_repo
                or payload.get("status") != "SUCCESS" or payload.get("execution_authorized") is not False
                or payload.get("production_decision_authorized") is not False
                or not isinstance(commit, str) or not _COMMIT.fullmatch(commit)
                or not isinstance(digest, str) or not _SHA256.fullmatch(digest)
                or parsed_time is None or parsed_time.tzinfo is None or not retrieved_at.endswith("Z")):
            raise ValueError("INVALID_RECEIPT")
        counts = {field: _nonnegative_int(summary.get(field)) for field in _SUMMARY_FIELDS}
        if any(value is None for value in counts.values()):
            raise ValueError("INVALID_RECEIPT")
        return {
            "catalog_id": catalog_id,
            "upstream_repo": upstream_repo,
            "status": "SUCCESS",
            "upstream_commit": commit,
            "upstream_path": payload.get("upstream_path") if isinstance(payload.get("upstream_path"), str) else None,
            "retrieved_at": retrieved_at,
            "content_sha256": digest,
            "summary": counts,
            "execution_authorized": False,
            "production_decision_authorized": False,
        }
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError):
        return {
            "catalog_id": catalog_id,
            "upstream_repo": upstream_repo,
            "status": "UNAVAILABLE",
            "reason": "INVALID_OR_MISSING_COMMITTED_RECEIPT",
            "execution_authorized": False,
            "production_decision_authorized": False,
        }


def snapshot(repository_root: Path) -> dict[str, object]:
    """Return only allowlisted receipt summaries; never initialize the private registry."""
    root = repository_root.resolve()
    catalogs = [_catalog_row(root, catalog_id, upstream_repo) for catalog_id, upstream_repo in _CATALOGS]
    available = sum(row["status"] == "SUCCESS" for row in catalogs)
    status = "AVAILABLE" if available == len(_CATALOGS) else "PARTIAL" if available else "UNAVAILABLE"
    return {
        "status": status,
        "scope": "PINNED_PUBLIC_CATALOG_METADATA_ONLY",
        "catalogs": catalogs,
        "catalogs_available": available,
        "catalogs_expected": len(_CATALOGS),
        "source_probes_performed": False,
        "market_data_provided": False,
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


__all__ = ["snapshot"]
