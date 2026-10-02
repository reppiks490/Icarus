from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def test_icarus_engine_is_revision_pinned_research_satellite():
    mesh = _load("integration/ICARUS_MESH.json")
    handoff = _load("integration/manifests/ICARUS_ENGINE_HANDOFF.json")
    node = next(item for item in mesh["nodes"] if item["id"] == "icarus-engine")

    assert node["repository"] == "reppiks490/Icarus-engine"
    assert node["status"] == "active"
    assert node["role"] == "active-research-satellite"
    assert node["authority_ceiling"] == "RESEARCH"
    assert node["cross_repository_execution_authorized"] is False
    assert node["producer_revision"] == handoff["producer_revision"]
    assert node["accepted_against_revision"] == handoff["target_revision"]
    assert handoff["target_repository"] == "reppiks490/Icarus"
    assert handoff["authority_granted"] == "RESEARCH"


def test_cross_repo_handoff_fails_closed_on_revision_drift_contract():
    handoff = _load("integration/manifests/ICARUS_ENGINE_HANDOFF.json")
    assert len(handoff["producer_revision"]) == 40
    assert len(handoff["target_revision"]) == 40
    assert any("revision drift" in item.lower() for item in handoff["limitations"])
    assert any("does not" in claim.lower() and "execution" in claim.lower() for claim in handoff["claims"])
