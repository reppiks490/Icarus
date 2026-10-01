"""Repository-native MCP evidence projector for the ICARUS operator plane.

This module is intentionally read-only. It lets the running dashboard surface
important MCP repair/audit/evolution/integration receipts already present in
the synchronized ICARUS checkout. It performs no network I/O and never mutates
trading state.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable
import json


IMPORTANT_CATEGORIES = {"REPAIR", "AUDIT", "EVOLUTION", "INTEGRATION"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class MCPControlPlane:
    ROOT = Path("automation_intelligence/mcp_interface")

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
    def _load_json(path: Path) -> Dict[str, Any] | None:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None

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

    def events(self, limit: int = 200) -> list[Dict[str, Any]]:
        limit = max(1, min(500, int(limit)))
        root = self._path(self.ROOT / "events")
        rows: list[Dict[str, Any]] = []
        for path in self._json_files(root):
            event = self._load_json(path)
            if not event:
                continue
            category = str(event.get("category") or "").strip().upper()
            if category not in IMPORTANT_CATEGORIES:
                continue
            rows.append({
                "event_id": event.get("event_id"),
                "at_utc": event.get("at_utc"),
                "category": category,
                "status": event.get("status"),
                "severity": event.get("severity"),
                "summary": event.get("summary"),
                "surface": event.get("surface"),
                "source": event.get("source"),
                "repository": event.get("repository") or "reppiks490/Icarus",
                "branch": event.get("branch"),
                "commit": event.get("commit"),
                "paths": event.get("paths") if isinstance(event.get("paths"), list) else [],
                "evidence": event.get("evidence") if isinstance(event.get("evidence"), list) else [],
                "execution_authorized": bool(event.get("execution_authorized", False)),
                "production_decision_authorized": bool(event.get("production_decision_authorized", False)),
                "event_path": self._rel(path),
            })
        rows.sort(
            key=lambda row: (
                str(row.get("at_utc") or ""),
                str(row.get("event_id") or ""),
            ),
            reverse=True,
        )
        return rows[:limit]

    def status(self, event_limit: int = 200) -> Dict[str, Any]:
        root = self._path(self.ROOT)
        contract_path = root / "contract.json"
        contract = self._load_json(contract_path) or {}
        events = self.events(event_limit)
        counts: Dict[str, int] = {}
        statuses: Dict[str, int] = {}
        for event in events:
            category = str(event.get("category") or "UNKNOWN")
            status = str(event.get("status") or "UNKNOWN").upper()
            counts[category] = counts.get(category, 0) + 1
            statuses[status] = statuses.get(status, 0) + 1
        return {
            "schema_version": "icarus-mcp-operator-evidence-v1",
            "generated_at": _utc_now(),
            "present": root.is_dir(),
            "source": "LOCAL_REPOSITORY_SNAPSHOT",
            "source_note": "Remote MCP changes appear after the local ICARUS checkout is synchronized.",
            "authority": {
                "read_only": True,
                "execution_authorized": False,
                "production_decision_authorized": False,
            },
            "contract": {
                "present": bool(contract),
                "schema_version": contract.get("schema_version"),
                "purpose": contract.get("purpose"),
                "event_root": contract.get("event_root"),
                "required_categories": contract.get("required_categories"),
                "required_fields": contract.get("required_fields"),
                "path": self._rel(contract_path),
            },
            "summary": {
                "important_events": len(events),
                "category_counts": dict(sorted(counts.items())),
                "status_counts": dict(sorted(statuses.items())),
            },
            "events": events,
        }
