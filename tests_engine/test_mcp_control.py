import json
from pathlib import Path

import pytest

from icarus_engine.mcp_control import MCPControlPlane


def _write(root: Path, rel: str, value: dict) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_mcp_projector_surfaces_important_repository_events(tmp_path: Path):
    _write(tmp_path, "automation_intelligence/mcp_interface/contract.json", {
        "schema_version": "icarus-mcp-interface-contract-v1",
        "purpose": "surface important MCP work",
        "event_root": "automation_intelligence/mcp_interface/events",
        "required_categories": ["REPAIR", "AUDIT", "EVOLUTION", "INTEGRATION"],
        "required_fields": ["event_id"],
    })
    _write(tmp_path, "automation_intelligence/mcp_interface/events/20261001T010000Z-repair.json", {
        "event_id": "repair-1",
        "at_utc": "2026-10-01T01:00:00Z",
        "category": "REPAIR",
        "status": "VERIFIED",
        "severity": "IMPORTANT",
        "summary": "fixed causal replay gate",
        "surface": "nexus",
        "source": "MCP",
        "repository": "reppiks490/divine-providence",
        "branch": "main",
        "commit": "a" * 40,
        "paths": ["systems/nexus/src/nexus/replay.py"],
        "evidence": ["tests green"],
        "execution_authorized": False,
        "production_decision_authorized": False,
    })
    _write(tmp_path, "automation_intelligence/mcp_interface/events/20261001T020000Z-noise.json", {
        "event_id": "noise",
        "at_utc": "2026-10-01T02:00:00Z",
        "category": "INFO",
        "status": "OK",
        "summary": "not material",
    })

    status = MCPControlPlane(tmp_path).status()
    assert status["schema_version"] == "icarus-mcp-operator-evidence-v1"
    assert status["authority"]["read_only"] is True
    assert status["authority"]["execution_authorized"] is False
    assert status["summary"]["important_events"] == 1
    assert status["summary"]["category_counts"] == {"REPAIR": 1}
    assert status["events"][0]["event_id"] == "repair-1"
    assert status["events"][0]["commit"] == "a" * 40
    assert status["events"][0]["event_path"].endswith("20261001T010000Z-repair.json")


def test_mcp_projector_orders_newest_first_and_bounds_limit(tmp_path: Path):
    for idx in range(3):
        _write(tmp_path, f"automation_intelligence/mcp_interface/events/{idx}.json", {
            "event_id": str(idx),
            "at_utc": f"2026-10-01T00:00:0{idx}Z",
            "category": "AUDIT",
            "status": "VERIFIED",
            "summary": str(idx),
        })
    events = MCPControlPlane(tmp_path).events(limit=2)
    assert [row["event_id"] for row in events] == ["2", "1"]


def test_mcp_projector_ignores_corrupt_json_and_missing_root(tmp_path: Path):
    broken = tmp_path / "automation_intelligence/mcp_interface/events/broken.json"
    broken.parent.mkdir(parents=True)
    broken.write_text("{not json", encoding="utf-8")
    status = MCPControlPlane(tmp_path).status()
    assert status["events"] == []
    assert status["summary"]["important_events"] == 0


def test_mcp_path_cannot_escape_base_directory(tmp_path: Path):
    plane = MCPControlPlane(tmp_path)
    with pytest.raises(ValueError, match="escapes"):
        plane._path("../outside.json")
