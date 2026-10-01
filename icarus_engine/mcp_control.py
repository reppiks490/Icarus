"""Repository-native MCP evidence projector for the ICARUS operator plane.

This is a read-only local projection of the same immutable event feed consumed
by EvolutionRemoteSync. Both paths use the same fail-closed schema validator and
canonical event field names.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping
import json

from .evolution_sync import (
    REMOTE_ROOT,
    SCHEMA_VERSION,
    git_blob_sha,
    normalize_interface_event,
)


IMPORTANT_CATEGORIES = {"REPAIR", "AUDIT", "EVOLUTION", "INTEGRATION", "FINDING"}
CONTRACT_SCHEMA = "icarus-mcp-interface-contract-v1"
_REQUIRED_EVENT_FIELDS = {
    "schema_version",
    "event_id",
    "category",
    "severity",
    "status",
    "subsystems",
    "recorded_at",
    "title",
    "summary",
    "source_repository",
    "source_ref",
    "source_commit",
    "evidence",
    "execution_authorized",
    "production_decision_authorized",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class MCPControlPlane:
    ROOT = Path("automation_intelligence/mcp_interface")
    EVENT_ROOT = Path(REMOTE_ROOT)
    CONTRACT = ROOT / "contract.json"

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
        if not isinstance(payload, Mapping):
            raise ValueError("event payload must be an object")
        relative = self._rel(path)
        if not relative:
            raise ValueError("event path is outside ICARUS base directory")
        event = normalize_interface_event(
            payload,
            source_path=relative,
            blob_sha=git_blob_sha(raw),
        )
        # Preserve the canonical interface schema all the way to the dashboard.
        return {
            "event_id": event["event_id"],
            "category": event["category"],
            "severity": event["severity"],
            "status": event["status"],
            "subsystems": list(event["subsystems"]),
            "recorded_at": event["recorded_at"],
            "title": event["title"],
            "summary": event["summary"],
            "source_repository": event["source_repository"],
            "source_ref": event["source_ref"],
            "source_commit": event["source_commit"],
            "evidence": list(event["evidence"]),
            "execution_authorized": False,
            "production_decision_authorized": False,
            "event_path": relative,
            "local_blob_sha": event["remote_blob_sha"],
        }

    def _contract(self) -> tuple[Dict[str, Any] | None, str | None]:
        path = self._path(self.CONTRACT)
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None, "machine-readable MCP contract is missing"
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            return None, f"machine-readable MCP contract is unreadable: {type(exc).__name__}: {exc}"
        if not isinstance(raw, Mapping):
            return None, "machine-readable MCP contract is not an object"
        if raw.get("schema_version") != CONTRACT_SCHEMA:
            return None, "unsupported MCP interface contract schema"
        if raw.get("event_schema_version") != SCHEMA_VERSION:
            return None, "MCP contract event schema does not match EvolutionRemoteSync"
        if raw.get("event_root") != REMOTE_ROOT:
            return None, "MCP contract event_root does not match EvolutionRemoteSync"
        if raw.get("execution_authorized") is not False:
            return None, "MCP contract execution_authorized must be false"
        if raw.get("production_decision_authorized") is not False:
            return None, "MCP contract production_decision_authorized must be false"
        categories = raw.get("required_categories")
        if not isinstance(categories, list) or set(categories) != IMPORTANT_CATEGORIES:
            return None, "MCP contract required_categories do not match the operator projector"
        fields = raw.get("required_fields")
        if not isinstance(fields, list) or not _REQUIRED_EVENT_FIELDS.issubset(set(fields)):
            return None, "MCP contract required_fields are incomplete"
        return dict(raw), None

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
                str(row.get("recorded_at") or ""),
                str(row.get("event_id") or ""),
            ),
            reverse=True,
        )
        rejected.sort(key=lambda row: row["event_path"])
        return rows, rejected

    def events(self, limit: int = 200) -> list[Dict[str, Any]]:
        if type(limit) is not int or limit < 1:
            raise ValueError("limit must be a positive integer")
        limit = min(500, limit)
        rows, _ = self._scan()
        return rows[:limit]

    def status(self, event_limit: int = 200) -> Dict[str, Any]:
        if type(event_limit) is not int or event_limit < 1:
            raise ValueError("event_limit must be a positive integer")
        limit = min(500, event_limit)
        root = self._path(self.ROOT)
        contract_path = self._path(self.CONTRACT)
        contract, contract_error = self._contract()
        events, rejected = self._scan()
        events = events[:limit]
        counts: Dict[str, int] = {}
        statuses: Dict[str, int] = {}
        for event in events:
            category = str(event.get("category") or "UNKNOWN")
            status = str(event.get("status") or "UNKNOWN").upper()
            counts[category] = counts.get(category, 0) + 1
            statuses[status] = statuses.get(status, 0) + 1
        degraded = bool(rejected or contract_error)
        return {
            "schema_version": "icarus-mcp-operator-evidence-v3",
            "generated_at": _utc_now(),
            "status": "degraded" if degraded else "green",
            "present": root.is_dir(),
            "source": "LOCAL_REPOSITORY_SNAPSHOT",
            "source_note": (
                "Local receipts use the same canonical fail-closed validator as "
                "EvolutionRemoteSync. Remote MCP changes appear after the local "
                "ICARUS checkout is synchronized."
            ),
            "authority": {
                "read_only": True,
                "execution_authorized": False,
                "production_decision_authorized": False,
            },
            "contract": {
                "present": contract is not None,
                "schema_version": contract.get("schema_version") if contract else None,
                "event_schema_version": contract.get("event_schema_version") if contract else None,
                "event_root": contract.get("event_root") if contract else REMOTE_ROOT,
                "required_categories": sorted(IMPORTANT_CATEGORIES),
                "path": self._rel(contract_path),
                "validator": "evolution_sync.normalize_interface_event",
                "error": contract_error,
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
