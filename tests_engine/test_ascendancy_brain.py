from __future__ import annotations

from icarus_engine.brain import SUBSYSTEMS, brain_snapshot


def test_ascendancy_rebased_organs_are_registered_without_duplicate_peer_bridge(tmp_path):
    rows = {row["id"]: row for row in SUBSYSTEMS}
    expected = {
        "capability-orchestrator": "omega",
        "ascendancy-foundry": "omega",
        "ascendancy-unknowns": "omega",
        "ascendancy-mechanisms": "daedalus",
        "ascendancy-invention": "aion",
        "ascendancy-contribution": "daedalus",
        "ascendancy-evaluator": "daedalus",
    }
    for subsystem_id, owner in expected.items():
        assert rows[subsystem_id]["owner"] == owner
    assert "ascendancy-peer-bridge" not in rows

    snapshot = brain_snapshot(tmp_path)
    surfaced = {row["id"]: row for row in snapshot["architecture"]["subsystems"]}
    for subsystem_id in expected:
        assert surfaced[subsystem_id]["status"] == "REGISTERED"
    assert snapshot["authority"]["execution_authorized"] is False
    assert snapshot["authority"]["production_decision_authorized"] is False
