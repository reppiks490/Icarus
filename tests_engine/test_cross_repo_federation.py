from __future__ import annotations

import json
from pathlib import Path

from icarus_engine import brain_sync, evidence_lab_sync, evolution_sync


ROOT = Path(__file__).resolve().parents[1]


def _mesh():
    return json.loads((ROOT / "integration" / "ICARUS_MESH.json").read_text(encoding="utf-8"))


def _node(node_id: str):
    return next(row for row in _mesh()["nodes"] if row["id"] == node_id)


def test_icarus_engine_mesh_binding_matches_live_brain_federation_contract():
    node = _node("icarus-engine")

    assert node["repository"] == brain_sync.REMOTE_REPOSITORY
    assert node["status"] == "active"
    assert node["role"] == "active-research-satellite"
    assert node["authority_ceiling"] == "RESEARCH"
    assert node["consumer_contract"] == brain_sync.REMOTE_CONSUMER_CONTRACT
    assert node["producer_contract"] == brain_sync.REMOTE_PRODUCER_CONTRACT
    assert node["consumer_surface"] == "Adaptive Brain remote sync"
    assert node["cross_repository_execution_authorized"] is False


def test_divine_providence_mesh_binding_matches_evolution_receipt_ingress():
    node = _node("divine-providence")

    assert node["repository"] == "reppiks490/divine-providence"
    assert node["status"] == "active"
    assert node["role"] == "active-research-satellite"
    assert node["authority_ceiling"] == "RESEARCH"
    assert node["ingress_mode"] == "immutable-receipt-mirror"
    assert node["ingress_repository"] == evolution_sync.REMOTE_REPOSITORY
    assert node["ingress_path"] == evolution_sync.REMOTE_ROOT
    assert node["receipt_schema"] == evolution_sync.SCHEMA_VERSION
    assert node["consumer_surface"] == (
        "MCP Evolution and Adaptive Brain observability"
    )
    assert node["cross_repository_execution_authorized"] is False


def test_csv_evidence_lab_mesh_binding_matches_live_receipt_federation():
    node = _node("icarus-csv-evidence-lab")

    assert node["repository"] == evidence_lab_sync.REMOTE_REPOSITORY
    assert node["status"] == "active"
    assert node["role"] == "active-research-satellite"
    assert node["authority_ceiling"] == "OBSERVE"
    assert node["consumer_contract"] == (
        evidence_lab_sync.REMOTE_ROOT + "/icarus_consumer_contract.json"
    )
    assert node["consumer_surface"] == "CSV Evidence Lab remote sync"
    assert node["substantive_evidence_authority"] == "evidence_state.EVIDENCE_STATUS"
    assert node["cross_repository_execution_authorized"] is False


def test_all_active_external_mesh_nodes_are_non_executing():
    mesh = _mesh()
    active_external = [
        row for row in mesh["nodes"]
        if row["id"] != "icarus-main" and row.get("status") == "active"
    ]

    assert {row["id"] for row in active_external} >= {
        "icarus-engine",
        "divine-providence",
        "icarus-csv-evidence-lab",
    }
    assert all(
        row.get("authority_ceiling") in {"OBSERVE", "RESEARCH"}
        for row in active_external
    )
    assert all(
        row.get("cross_repository_execution_authorized") is False
        for row in active_external
    )
