import json
from pathlib import Path

import pytest

from icarus_engine.mcp_control import MCPControlPlane


def _write(root: Path, rel: str, value: dict) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _event(**overrides):
    base = {
        "schema_version": "icarus-interface-event-v1",
        "event_id": "repair-1",
        "category": "REPAIR",
        "severity": "success",
        "status": "verified",
        "subsystems": ["nexus", "psi"],
        "recorded_at": "2026-10-01T01:00:00Z",
        "title": "Causal replay repaired",
        "summary": "Fixed the causal replay gate and verified the regression.",
        "source_repository": "reppiks490/divine-providence",
        "source_ref": "main",
        "source_commit": "a" * 40,
        "evidence": ["tests green"],
        "execution_authorized": False,
        "production_decision_authorized": False,
    }
    base.update(overrides)
    return base


def test_mcp_projector_surfaces_only_valid_important_repository_events(tmp_path: Path):
    readme = tmp_path / "automation_intelligence/mcp_interface/README.md"
    readme.parent.mkdir(parents=True, exist_ok=True)
    readme.write_text("# MCP feed\n", encoding="utf-8")
    _write(
        tmp_path,
        "automation_intelligence/mcp_interface/events/20261001T010000Z-repair.json",
        _event(),
    )

    status = MCPControlPlane(tmp_path).status()
    assert status["schema_version"] == "icarus-mcp-operator-evidence-v2"
    assert status["status"] == "green"
    assert status["authority"]["read_only"] is True
    assert status["authority"]["execution_authorized"] is False
    assert status["summary"]["important_events"] == 1
    assert status["summary"]["rejected_events"] == 0
    assert status["summary"]["category_counts"] == {"REPAIR": 1}
    assert status["contract"]["present"] is True
    assert status["contract"]["validator"] == "evolution_sync.normalize_interface_event"
    event = status["events"][0]
    assert event["event_id"] == "repair-1"
    assert event["commit"] == "a" * 40
    assert event["subsystems"] == ["nexus", "psi"]
    assert event["execution_authorized"] is False
    assert event["event_path"].endswith("20261001T010000Z-repair.json")
    assert len(event["blob_sha"]) == 40


def test_mcp_projector_orders_newest_first_and_bounds_limit(tmp_path: Path):
    for idx in range(3):
        _write(
            tmp_path,
            f"automation_intelligence/mcp_interface/events/{idx}.json",
            _event(
                event_id=str(idx),
                recorded_at=f"2026-10-01T00:00:0{idx}Z",
                category="AUDIT",
            ),
        )
    events = MCPControlPlane(tmp_path).events(limit=2)
    assert [row["event_id"] for row in events] == ["2", "1"]


@pytest.mark.parametrize(
    "payload",
    [
        _event(execution_authorized="false"),
        _event(production_decision_authorized=True),
        _event(source_commit="short"),
        _event(recorded_at="2026-10-01T01:00:00"),
        _event(subsystems=["unknown-subsystem"]),
    ],
)
def test_mcp_projector_quarantines_invalid_receipts(tmp_path: Path, payload):
    _write(
        tmp_path,
        "automation_intelligence/mcp_interface/events/bad.json",
        payload,
    )
    status = MCPControlPlane(tmp_path).status()
    assert status["status"] == "degraded"
    assert status["events"] == []
    assert status["summary"]["rejected_events"] == 1
    assert "bad.json" in status["rejected"][0]["event_path"]


def test_mcp_projector_ignores_corrupt_json_as_rejected_health(tmp_path: Path):
    broken = tmp_path / "automation_intelligence/mcp_interface/events/broken.json"
    broken.parent.mkdir(parents=True)
    broken.write_text("{not json", encoding="utf-8")
    status = MCPControlPlane(tmp_path).status()
    assert status["events"] == []
    assert status["status"] == "degraded"
    assert status["summary"]["rejected_events"] == 1


def test_mcp_path_cannot_escape_base_directory(tmp_path: Path):
    plane = MCPControlPlane(tmp_path)
    with pytest.raises(ValueError, match="escapes"):
        plane._path("../outside.json")
