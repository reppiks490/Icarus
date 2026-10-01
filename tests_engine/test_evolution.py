from __future__ import annotations

import json
from pathlib import Path

import pytest

from icarus_engine.evolution import report


def test_system_evolution_ledger_is_valid_and_read_only():
    data = report()
    assert data["schema"] == "icarus.system-evolution.v1"
    assert data["interface_contract"]["important_mcp_changes_must_surface"] is True
    assert data["entry_count"] == len(data["entries"])
    assert data["entry_count"] >= 1
    assert len(data["ledger_sha256"]) == 64
    assert data["execution_authorized"] is False
    assert all(row["execution_authorized"] is False for row in data["entries"])
    assert len({row["id"] for row in data["entries"]}) == data["entry_count"]


def test_system_evolution_rejects_execution_authority(tmp_path: Path):
    source = Path(__file__).resolve().parents[1] / "icarus_engine" / "system_evolution.json"
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["entries"][0]["execution_authorized"] = True
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="cannot authorize execution"):
        report(path)
