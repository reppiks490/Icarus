"""Read-only ICARUS system-evolution ledger exposed to the trading interface."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA = "icarus.system-evolution.v1"
_LEDGER = Path(__file__).with_name("system_evolution.json")
_REQUIRED_ENTRY_FIELDS = (
    "id",
    "recorded_date",
    "subsystem",
    "kind",
    "status",
    "severity",
    "title",
    "summary",
    "source_repo",
    "source_branch",
    "source_commit",
    "verification",
    "interface_effect",
    "execution_authorized",
)


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _validate(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("schema") != SCHEMA:
        raise ValueError("invalid system-evolution schema")
    contract = payload.get("interface_contract")
    if not isinstance(contract, dict) or contract.get("important_mcp_changes_must_surface") is not True:
        raise ValueError("system-evolution interface contract is missing or disabled")
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise ValueError("system-evolution entries must be a list")

    seen: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"system-evolution entry {index} must be an object")
        missing = [field for field in _REQUIRED_ENTRY_FIELDS if field not in entry]
        if missing:
            raise ValueError(f"system-evolution entry {index} missing {', '.join(missing)}")
        entry_id = entry["id"]
        if not isinstance(entry_id, str) or not entry_id.strip():
            raise ValueError(f"system-evolution entry {index} has invalid id")
        if entry_id in seen:
            raise ValueError(f"duplicate system-evolution id {entry_id}")
        seen.add(entry_id)
        if entry["execution_authorized"] is not False:
            raise ValueError(f"system-evolution entry {entry_id} cannot authorize execution")
        commit = entry["source_commit"]
        if not isinstance(commit, str) or len(commit) != 40:
            raise ValueError(f"system-evolution entry {entry_id} has invalid commit")
        try:
            int(commit, 16)
        except ValueError as exc:
            raise ValueError(f"system-evolution entry {entry_id} has invalid commit") from exc
        for field in (
            "recorded_date",
            "subsystem",
            "kind",
            "status",
            "severity",
            "title",
            "summary",
            "source_repo",
            "source_branch",
            "verification",
            "interface_effect",
        ):
            if not isinstance(entry[field], str) or not entry[field].strip():
                raise ValueError(f"system-evolution entry {entry_id} has invalid {field}")
    return payload


def report(path: str | Path | None = None) -> dict[str, Any]:
    ledger_path = Path(path) if path is not None else _LEDGER
    payload = _validate(json.loads(ledger_path.read_text(encoding="utf-8")))
    entries = list(payload["entries"])
    counts: dict[str, int] = {}
    subsystem_counts: dict[str, int] = {}
    for entry in entries:
        counts[entry["status"]] = counts.get(entry["status"], 0) + 1
        subsystem_counts[entry["subsystem"]] = subsystem_counts.get(entry["subsystem"], 0) + 1
    return {
        "schema": payload["schema"],
        "interface_contract": payload["interface_contract"],
        "entries": entries,
        "entry_count": len(entries),
        "status_counts": dict(sorted(counts.items())),
        "subsystem_counts": dict(sorted(subsystem_counts.items())),
        "ledger_sha256": hashlib.sha256(_canonical(payload)).hexdigest(),
        "latest_recorded_date": max((x["recorded_date"] for x in entries), default=None),
        "execution_authorized": False,
    }
