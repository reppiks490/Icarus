from __future__ import annotations

import copy
import hashlib
import json

import pytest

from icarus_engine.ascendancy.peer_bridge import PeerRepositoryBridge, normalize_peer_packet


def _hash(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _packet(**overrides):
    body = {
        "schema_version": "icarus-peer-intelligence-packet-v1",
        "source_repository": "reppiks490/Icarus-engine",
        "source_commit": "a" * 40,
        "observed_at": "2026-10-02T15:40:00Z",
        "source_contracts": {
            "control_plane": "automation_intelligence/restored_five_native/control_plane.json",
            "agent_fabric": "automation_intelligence/agent_fabric/manifest.json",
            "mcp_interface": "automation_intelligence/mcp_interface/contract.json",
        },
        "control_plane": {
            "schema_version": "restored-five-native-control-v1",
            "control_plane_id": "restored-five-native-liveness-v1",
            "timezone": "America/Chicago",
            "grace_minutes": 8,
            "catchup_horizon_minutes": 180,
        },
        "lanes": [
            {
                "name": "robustness_guardian",
                "title": "Robustness Guardian Evolution",
                "minute": 5,
                "scheduler_id": "rg-1",
                "run_prefix": "robustness-guardian",
                "worker_repository": "reppiks490/Icarus-engine",
                "worker_root": "automation_intelligence/agent_fabric/robustness_guardian",
                "run_id": "robustness-guardian-20261002T150500Z",
                "run_status": "RUN_PERSISTED",
                "finalization_commit_sha": "d" * 40,
                "completion_semantics": "DURABILITY_RECEIPT_ONLY",
                "worker_execution_observed": False,
                "evidence_status": "DURABILITY_ONLY",
                "substantive_research_evidence": False,
                "execution_authorized": False,
            },
            {
                "name": "flow_microstructure",
                "title": "Microstructure Sensor Grid",
                "minute": 35,
                "scheduler_id": "flow-1",
                "run_prefix": "flow",
                "worker_repository": "reppiks490/Icarus-engine",
                "worker_root": "automation_intelligence/flow",
                "run_id": "flow-20261002T153500Z",
                "run_status": "RUN_PERSISTED",
                "finalization_commit_sha": "e" * 40,
                "completion_semantics": "WORKER_RESULT",
                "worker_execution_observed": True,
                "evidence_status": "PERSISTED_WORKER_EVIDENCE",
                "substantive_research_evidence": True,
                "execution_authorized": False,
            },
        ],
        "mcp_interface": {
            "schema_version": "icarus-mcp-interface-contract-v1",
            "event_root": "automation_intelligence/mcp_interface/events",
            "ui_api": "/api/mcp/control",
            "ui_tab": "MCP / Automation",
            "source_of_truth": "LOCAL_REPOSITORY_SNAPSHOT",
            "trading_execution_authorized": False,
        },
        "truth_contract": {
            "foreign_repository_state_is_evidence_not_native_truth": True,
            "durability_receipt_is_not_substantive_worker_evidence": True,
            "remote_sibling_state_is_never_inferred": True,
            "exact_source_commit_required": True,
            "execution_authority_never_transfers_between_repositories": True,
        },
        "execution_authorized": False,
        "production_decision_authorized": False,
        "peer_write_authorized": False,
    }
    body.update(overrides)
    body["packet_id"] = _hash({k: v for k, v in body.items() if k != "packet_id"})
    return body


def test_peer_packet_normalization_preserves_foreign_evidence_boundary():
    row = normalize_peer_packet(_packet())
    assert row["source_repository"] == "reppiks490/Icarus-engine"
    assert row["execution_authorized"] is False
    assert row["production_decision_authorized"] is False
    assert row["peer_write_authorized"] is False
    durability = next(x for x in row["lanes"] if x["name"] == "robustness_guardian")
    assert durability["candidate_evidence_eligible"] is False
    substantive = next(x for x in row["lanes"] if x["name"] == "flow_microstructure")
    assert substantive["candidate_evidence_eligible"] is True


def test_peer_packet_rejects_hash_tampering_and_authority_escalation():
    tampered = _packet()
    tampered["lanes"][0]["run_id"] = "changed-after-signing"
    with pytest.raises(ValueError, match="packet_id"):
        normalize_peer_packet(tampered)

    escalated = _packet()
    escalated["execution_authorized"] = True
    escalated["packet_id"] = _hash({k: v for k, v in escalated.items() if k != "packet_id"})
    with pytest.raises(ValueError, match="authority"):
        normalize_peer_packet(escalated)


def test_peer_packet_rejects_self_source_and_unknown_evidence_status():
    with pytest.raises(ValueError, match="self-source"):
        normalize_peer_packet(_packet(source_repository="reppiks490/Icarus"))

    bad = _packet()
    bad["lanes"][0]["evidence_status"] = "MAGIC_ALPHA"
    bad["packet_id"] = _hash({k: v for k, v in bad.items() if k != "packet_id"})
    with pytest.raises(ValueError, match="evidence_status"):
        normalize_peer_packet(bad)


def test_peer_bridge_is_wal_append_only_and_idempotent(tmp_path):
    bridge = PeerRepositoryBridge(tmp_path)
    packet = _packet()
    one = bridge.ingest(packet)
    two = bridge.ingest(packet)

    assert bridge.journal_mode == "wal"
    assert one["idempotent"] is False
    assert two["idempotent"] is True
    snap = bridge.snapshot()
    assert snap["packet_count"] == 1
    assert snap["source_count"] == 1
    assert snap["latest_by_source"][0]["packet_id"] == packet["packet_id"]
    assert snap["execution_authorized"] is False
    assert snap["production_decision_authorized"] is False


def test_peer_bridge_preserves_historical_packets_instead_of_overwriting(tmp_path):
    bridge = PeerRepositoryBridge(tmp_path)
    first = _packet()
    bridge.ingest(first)

    second = copy.deepcopy(first)
    second["source_commit"] = "b" * 40
    second["observed_at"] = "2026-10-02T16:40:00Z"
    second["lanes"][1]["run_id"] = "flow-20261002T163500Z"
    second["packet_id"] = _hash({k: v for k, v in second.items() if k != "packet_id"})
    bridge.ingest(second)

    snap = bridge.snapshot()
    assert snap["packet_count"] == 2
    assert snap["latest_by_source"][0]["packet_id"] == second["packet_id"]
    assert {x["packet_id"] for x in snap["packets"]} == {first["packet_id"], second["packet_id"]}


def test_bridge_surfaces_substantive_and_durability_lanes_separately(tmp_path):
    bridge = PeerRepositoryBridge(tmp_path)
    bridge.ingest(_packet())
    snap = bridge.snapshot()
    source = snap["latest_by_source"][0]

    assert source["substantive_lane_count"] == 1
    assert source["durability_only_lane_count"] == 1
    assert source["candidate_evidence_eligible_lanes"] == ["flow_microstructure"]
    assert source["durability_only_lanes"] == ["robustness_guardian"]
    assert snap["truth_contract"]["durability_only_never_enters_candidate_evidence"] is True
