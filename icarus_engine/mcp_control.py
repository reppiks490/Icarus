"""Repository-native MCP evidence projector for the ICARUS operator plane.

This is a read-only local projection of the same immutable event feed consumed
by EvolutionRemoteSync. Both paths use the same fail-closed schema validator.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable
import json

from .evolution_sync import (
    REMOTE_ROOT,
    SCHEMA_VERSION,
    git_blob_sha,
    normalize_interface_event,
)


IMPORTANT_CATEGORIES = {"REPAIR", "AUDIT", "EVOLUTION", "INTEGRATION", "FINDING"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class MCPControlPlane:
    ROOT = Path("automation_intelligence/mcp_interface")
    EVENT_ROOT = Path(REMOTE_ROOT)

    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir).resolve()

    def _path(self, relative: str | Path) -> Path:
        candidate = (self.base_dir / relative).resolve()
        try:
            candidate.relative_to(self.base_dir)
        except ValueError as exc:
            raise ValueError("MCP path escapes ICARUS base directory") from exc
        return candidate

    @staticmethod
    def _json_files(root: Path) -> Iterable[Path]:
        if not root.is_dir():
            return ()
        return (p for p in root.rglob("*.json") if p.is_file())

    def _rel(self, path: Path) -> str | None:
        try:
            return path.resolve().relative_to(self.base_dir).as_posix()
        except ValueError:
            return None

    def _validated_event(self, path: Path) -> Dict[str, Any]:
        raw = path.read_bytes()
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("event JSON is unreadable") from exc
        if not isinstance(payload, dict):
            raise ValueError("event payload must be an object")
        relative = self._rel(path)
        if not relative:
            raise ValueError("event path is outside ICARUS base directory")
        event = normalize_interface_event(
            payload,
            source_path=relative,
            blob_sha=git_blob_sha(raw),
        )
        return {
            "event_id": event["event_id"],
            "at_utc": event["recorded_at"],
            "category": event["category"],
            "status": event["status"],
            "severity": event["severity"],
            "title": event["title"],
            "summary": event["summary"],
            "surface": ", ".join(event["subsystems"]),
            "subsystems": list(event["subsystems"]),
            "source": "MCP",
            "repository": event["source_repository"],
            "branch": event["source_ref"],
            "commit": event["source_commit"],
            "paths": [],
            "evidence": list(event["evidence"]),
            "execution_authorized": False,
            "production_decision_authorized": False,
            "event_path": relative,
            "blob_sha": event["remote_blob_sha"],
        }

    def _scan(self) -> tuple[list[Dict[str, Any]], list[Dict[str, str]]]:
        root = self._path(self.EVENT_ROOT)
        rows: list[Dict[str, Any]] = []
        rejected: list[Dict[str, str]] = []
        for path in self._json_files(root):
            try:
                event = self._validated_event(path)
            except (OSError, ValueError, TypeError) as exc:
                rejected.append({
                    "event_path": self._rel(path) or str(path),
                    "error": f"{type(exc).__name__}: {exc}"[:1000],
                })
                continue
            if event["category"] in IMPORTANT_CATEGORIES:
                rows.append(event)
        rows.sort(
            key=lambda row: (
                str(row.get("at_utc") or ""),
                str(row.get("event_id") or ""),
            ),
            reverse=True,
        )
        rejected.sort(key=lambda row: row["event_path"])
        return rows, rejected

    def events(self, limit: int = 200) -> list[Dict[str, Any]]:
        limit = max(1, min(500, int(limit)))
        rows, _ = self._scan()
        return rows[:limit]

    def status(self, event_limit: int = 200) -> Dict[str, Any]:
        limit = max(1, min(500, int(event_limit)))
        root = self._path(self.ROOT)
        readme = root / "README.md"
        events, rejected = self._scan()
        events = events[:limit]
        counts: Dict[str, int] = {}
        statuses: Dict[str, int] = {}
        for event in events:
            category = str(event.get("category") or "UNKNOWN")
            status = str(event.get("status") or "UNKNOWN").upper()
            counts[category] = counts.get(category, 0) + 1
            statuses[status] = statuses.get(status, 0) + 1
        return {
            "schema_version": "icarus-mcp-operator-evidence-v2",
            "generated_at": _utc_now(),
            "status": "degraded" if rejected else "green",
            "present": root.is_dir(),
            "source": "LOCAL_REPOSITORY_SNAPSHOT",
            "source_note": (
                "Local receipts are schema-validated with the same fail-closed "
                "validator as EvolutionRemoteSync. Remote MCP changes appear after "
                "the local ICARUS checkout is synchronized."
            ),
            "authority": {
                "read_only": True,
                "execution_authorized": False,
                "production_decision_authorized": False,
            },
            "contract": {
                "present": readme.is_file(),
                "schema_version": SCHEMA_VERSION,
                "event_root": REMOTE_ROOT,
                "required_categories": sorted(IMPORTANT_CATEGORIES),
                "path": self._rel(readme),
                "validator": "evolution_sync.normalize_interface_event",
            },
            "summary": {
                "important_events": len(events),
                "rejected_events": len(rejected),
                "category_counts": dict(sorted(counts.items())),
                "status_counts": dict(sorted(statuses.items())),
            },
            "events": events,
            "rejected": rejected[:50],
        }
