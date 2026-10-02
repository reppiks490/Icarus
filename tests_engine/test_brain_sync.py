from __future__ import annotations

import json

from icarus_engine.brain import brain_snapshot
from icarus_engine.brain_sync import (
    BrainRemoteSync,
    REMOTE_ROOT,
    _REMOTE_CONSUMER_CONTRACT_API,
    _REMOTE_PRODUCER_CONTRACT_API,
    _REMOTE_PEER_PACKET_API,
    _git_blob_sha,
)


def _remote_event(**overrides):
    payload = {
        "schema": "icarus-mcp-event-v1",
        "event_id": "flow-test",
        "at_utc": "2026-10-01T04:23:01Z",
        "category": "AUDIT",
        "status": "OBSERVED",
        "severity": "INFO",
        "summary": "Authenticated flow delta.",
        "surface": "Adaptive Brain federation fixture",
        "source": "FLOW_AUTOMATION",
        "paths": ["automation_intelligence/mcp_interface/events/flow-test.json"],
        "execution_authorized": False,
        "retrieval_time_utc": "2026-10-01T04:23:01Z",
        "net_new_delta": "Authenticated flow delta.",
        "evidence": {"btc": "measured spot evidence"},
        "argus": {"status": "USEFUL", "finding": "True depth snapshot preserved as snapshot-only evidence."},
        "nexus": {"status": "USEFUL", "finding": "Representations and data gaps remain separated."},
        "data_gaps": ["direct NQ unavailable"],
        "conflicts": [],
    }
    payload.update(overrides)
    return payload


def _consumer_contract(**overrides):
    payload = {
        "schema_version": "icarus-engine-brain-federation-v1",
        "producer_repository": "reppiks490/Icarus-engine",
        "producer_ref": "main",
        "consumer_repository": "reppiks490/Icarus",
        "consumer_surface": "Adaptive Brain remote sync",
        "producer_contract": "automation_intelligence/mcp_interface/contract.json",
        "producer_contract_schema": "icarus-mcp-interface-contract-v1",
        "event_root": "automation_intelligence/mcp_interface/events",
        "event_schema": "icarus-mcp-event-v1",
        "accepted_sources": [
            "OMEGA_AUTOMATION",
            "MACRO_AUTOMATION",
            "FLOW_AUTOMATION",
            "AION_AUTOMATION",
            "DAEDALUS_AUTOMATION",
        ],
        "accepted_categories": ["REPAIR", "AUDIT", "EVOLUTION", "INTEGRATION"],
        "semantics": {
            "event_records": "RESEARCH_OBSERVABILITY_ONLY",
            "durability_receipts_are_substantive_evidence": False,
            "remote_status_is_production_decision": False,
            "raw_owner_data_transfer": False,
            "automatic_model_promotion": False,
            "production_decision_authorized": False,
            "automatic_execution_authority": False,
        },
        "peer_packet": {
            "path": "automation_intelligence/interrepo/latest.json",
            "schema_version": "icarus-peer-intelligence-packet-v1",
            "authority": "OBSERVE",
            "source_commit_required": True,
            "git_blob_verification_required": True,
            "required_for_event_ingest": False,
            "semantics": {
                "lane_state_is_foreign_evidence": True,
                "durability_only_is_not_substantive_research_evidence": True,
                "remote_sibling_state_is_never_inferred": True,
                "automatic_model_promotion": False,
                "production_decision_authorized": False,
                "automatic_execution_authority": False,
            },
        },
        "event_validation": {
            "required_fields_source": "automation_intelligence/mcp_interface/contract.json#required_fields",
            "strict_v1_required_fields": True,
            "legacy_relaxed_blob_shas": [],
            "legacy_rule": (
                "Only these exact immutable Git blobs may omit producer-required envelope fields. "
                "No future blob inherits this exception."
            ),
        },
        "execution_authorized": False,
        "production_decision_authorized": False,
    }
    payload.update(overrides)
    return payload


def _producer_contract():
    return {
        "schema_version": "icarus-mcp-interface-contract-v1",
        "event_root": "automation_intelligence/mcp_interface/events",
        "event_schema": "icarus-mcp-event-v1",
        "required_categories": ["REPAIR", "AUDIT", "EVOLUTION", "INTEGRATION"],
        "required_fields": [
            "event_id",
            "at_utc",
            "category",
            "status",
            "severity",
            "summary",
            "surface",
            "source",
            "paths",
            "evidence",
            "execution_authorized",
        ],
        "trading_execution_authorized": False,
    }


def _peer_packet(**overrides):
    packet = {
        "schema_version": "icarus-peer-intelligence-packet-v1",
        "source_repository": "reppiks490/Icarus-engine",
        "source_commit": "c" * 40,
        "observed_at": "2026-10-02T20:43:00Z",
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
                "run_id": "robustness-guardian-20261002T200500Z",
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
                "run_id": "flow-20261002T203500Z",
                "run_status": "RUN_PERSISTED",
                "finalization_commit_sha": "e" * 40,
                "completion_semantics": "WORKER_EVIDENCE",
                "worker_execution_observed": True,
                "evidence_status": "PERSISTED_WORKER_EVIDENCE",
                "substantive_research_evidence": True,
                "execution_authorized": False,
            },
            {
                "name": "advanced_csv",
                "title": "Advanced CSV Data Collector",
                "minute": 15,
                "scheduler_id": "csv-1",
                "run_prefix": "advanced-csv",
                "worker_repository": "reppiks490/icarus-csv-evidence-lab",
                "worker_root": "automation_intelligence/advanced_csv",
                "run_id": None,
                "run_status": None,
                "finalization_commit_sha": None,
                "completion_semantics": None,
                "worker_execution_observed": None,
                "evidence_status": "REMOTE_PEER_UNREAD",
                "substantive_research_evidence": False,
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
    packet.update(overrides)
    unsigned = dict(packet)
    unsigned.pop("packet_id", None)
    packet["packet_id"] = __import__("hashlib").sha256(
        json.dumps(unsigned, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    return packet


def _fixture(
    payload,
    *,
    consumer=None,
    corrupt_event_blob=False,
    corrupt_consumer_blob=False,
    corrupt_peer_blob=False,
    peer=None,
    allow_legacy_event=False,
):
    event_raw = (json.dumps(payload, sort_keys=True) + "\n").encode()
    event_sha = _git_blob_sha(event_raw)
    path = f"{REMOTE_ROOT}/flow-test.json"
    event_url = "https://api.github.test/flow-test"
    listing = [{
        "name": "flow-test.json",
        "path": path,
        "sha": "a" * 40 if corrupt_event_blob else event_sha,
        "url": event_url,
        "type": "file",
    }]

    consumer_doc = consumer or _consumer_contract()
    if allow_legacy_event:
        consumer_doc = json.loads(json.dumps(consumer_doc))
        consumer_doc["event_validation"]["legacy_relaxed_blob_shas"] = [event_sha]
    producer_doc = _producer_contract()
    peer_doc = peer or _peer_packet()
    consumer_raw = (json.dumps(consumer_doc, sort_keys=True) + "\n").encode()
    producer_raw = (json.dumps(producer_doc, sort_keys=True) + "\n").encode()
    peer_raw = (json.dumps(peer_doc, sort_keys=True) + "\n").encode()
    consumer_sha = _git_blob_sha(consumer_raw)
    producer_sha = _git_blob_sha(producer_raw)
    peer_sha = _git_blob_sha(peer_raw)
    consumer_url = "https://api.github.test/consumer-contract"
    producer_url = "https://api.github.test/producer-contract"
    peer_url = "https://api.github.test/peer-packet"

    def fetch_json(requested):
        if requested == _REMOTE_CONSUMER_CONTRACT_API:
            return {
                "type": "file",
                "sha": "b" * 40 if corrupt_consumer_blob else consumer_sha,
                "url": consumer_url,
            }
        if requested == _REMOTE_PRODUCER_CONTRACT_API:
            return {"type": "file", "sha": producer_sha, "url": producer_url}
        if requested == _REMOTE_PEER_PACKET_API:
            return {
                "type": "file",
                "sha": "f" * 40 if corrupt_peer_blob else peer_sha,
                "url": peer_url,
            }
        return listing

    def fetch_bytes(requested):
        if requested == event_url:
            return event_raw
        if requested == consumer_url:
            return consumer_raw
        if requested == producer_url:
            return producer_raw
        if requested == peer_url:
            return peer_raw
        return b""

    return {
        "event_raw": event_raw,
        "event_sha": event_sha,
        "path": path,
        "event_url": event_url,
        "listing": listing,
        "consumer_sha": consumer_sha,
        "producer_sha": producer_sha,
        "peer_sha": peer_sha,
        "fetch_json": fetch_json,
        "fetch_bytes": fetch_bytes,
    }


def test_remote_sync_ingests_custom_agent_and_owned_subsystem_events(tmp_path):
    fixture = _fixture(_remote_event())

    sync = BrainRemoteSync(
        tmp_path,
        interval_seconds=60,
        fetch_json=fixture["fetch_json"],
        fetch_bytes=fixture["fetch_bytes"],
    )
    status = sync.sync_once()
    assert status["status"] == "green"
    assert status["ingested_total"] == 1
    assert status["last_ingested"] == [fixture["path"]]
    assert status["consumer_contract_blob_sha"] == fixture["consumer_sha"]
    assert status["producer_contract_blob_sha"] == fixture["producer_sha"]
    assert status["truth_contract"]["federation_schema"] == "icarus-engine-brain-federation-v1"
    assert status["truth_contract"]["event_records"] == "RESEARCH_OBSERVABILITY_ONLY"
    assert status["truth_contract"]["automatic_execution_authority"] is False
    assert status["truth_contract"]["peer_packet_schema"] == "icarus-peer-intelligence-packet-v1"
    assert status["peer_packet_status"] == "green"
    assert status["peer_packet_blob_sha"] == fixture["peer_sha"]
    assert status["peer_source_commit"] == "c" * 40
    assert status["peer_substantive_lane_count"] == 1
    assert status["peer_durability_only_lane_count"] == 1
    assert len(status["peer_lanes"]) == 3
    assert status["execution_authorized"] is False

    snap = brain_snapshot(tmp_path, remote_sync=status)
    agents = {x["id"]: x for x in snap["architecture"]["agents"]}
    subsystems = {x["id"]: x for x in snap["architecture"]["subsystems"]}
    assert agents["flow"]["detail"] == "Authenticated flow delta."
    assert subsystems["argus"]["detail"].startswith("True depth snapshot")
    assert subsystems["nexus"]["detail"].startswith("Representations and data gaps")
    assert snap["remote_sync"]["status"] == "green"

    again = sync.sync_once()
    assert again["ingested_total"] == 1
    assert len(brain_snapshot(tmp_path)["events"]) == 3


def test_remote_sync_rejects_authority_escalation(tmp_path):
    fixture = _fixture(_remote_event(execution_authorized=True))
    sync = BrainRemoteSync(
        tmp_path,
        interval_seconds=60,
        fetch_json=fixture["fetch_json"],
        fetch_bytes=fixture["fetch_bytes"],
    )
    status = sync.sync_once()
    assert status["status"] == "degraded"
    assert status["rejected_total"] == 1
    assert "execution_authorized=false" in status["last_error"]
    assert brain_snapshot(tmp_path)["events"] == []


def test_remote_sync_detects_event_blob_substitution(tmp_path):
    fixture = _fixture(_remote_event(), corrupt_event_blob=True)
    sync = BrainRemoteSync(
        tmp_path,
        interval_seconds=60,
        fetch_json=fixture["fetch_json"],
        fetch_bytes=fixture["fetch_bytes"],
    )
    status = sync.sync_once()
    assert status["status"] == "degraded"
    assert status["rejected_total"] == 1
    assert "Git blob SHA mismatch" in status["last_error"]
    assert brain_snapshot(tmp_path)["events"] == []


def test_remote_sync_rejects_invalid_custom_agent_schema(tmp_path):
    fixture = _fixture(_remote_event(schema="wrong-schema"))
    sync = BrainRemoteSync(
        tmp_path,
        interval_seconds=60,
        fetch_json=fixture["fetch_json"],
        fetch_bytes=fixture["fetch_bytes"],
    )
    status = sync.sync_once()
    assert status["status"] == "degraded"
    assert status["rejected_total"] == 1
    assert "unsupported custom-agent event schema" in status["last_error"]
    assert brain_snapshot(tmp_path)["events"] == []


def test_remote_sync_fails_closed_when_consumer_contract_escalates_authority(tmp_path):
    consumer = _consumer_contract(
        semantics={
            **_consumer_contract()["semantics"],
            "automatic_execution_authority": True,
        }
    )
    fixture = _fixture(_remote_event(), consumer=consumer)
    sync = BrainRemoteSync(
        tmp_path,
        interval_seconds=60,
        fetch_json=fixture["fetch_json"],
        fetch_bytes=fixture["fetch_bytes"],
    )
    status = sync.sync_once()
    assert status["status"] == "degraded"
    assert status["ingested_total"] == 0
    assert "attempts authority escalation" in status["last_error"]
    assert brain_snapshot(tmp_path)["events"] == []


def test_remote_sync_fails_closed_on_consumer_contract_blob_substitution(tmp_path):
    fixture = _fixture(_remote_event(), corrupt_consumer_blob=True)
    sync = BrainRemoteSync(
        tmp_path,
        interval_seconds=60,
        fetch_json=fixture["fetch_json"],
        fetch_bytes=fixture["fetch_bytes"],
    )
    status = sync.sync_once()
    assert status["status"] == "degraded"
    assert status["ingested_total"] == 0
    assert "consumer federation contract Git blob SHA mismatch" in status["last_error"]
    assert brain_snapshot(tmp_path)["events"] == []

def test_remote_sync_rejects_new_event_missing_required_producer_envelope(tmp_path):
    payload = _remote_event()
    del payload["severity"]
    fixture = _fixture(payload)
    sync = BrainRemoteSync(
        tmp_path,
        interval_seconds=60,
        fetch_json=fixture["fetch_json"],
        fetch_bytes=fixture["fetch_bytes"],
    )
    status = sync.sync_once()
    assert status["status"] == "degraded"
    assert status["rejected_total"] == 1
    assert "missing required producer fields: severity" in status["last_error"]
    assert brain_snapshot(tmp_path)["events"] == []


def test_remote_sync_allows_only_exact_legacy_blob_exception(tmp_path):
    payload = _remote_event()
    for field in ("event_id", "at_utc", "status", "severity", "summary", "surface", "paths"):
        del payload[field]
    fixture = _fixture(payload, allow_legacy_event=True)
    sync = BrainRemoteSync(
        tmp_path,
        interval_seconds=60,
        fetch_json=fixture["fetch_json"],
        fetch_bytes=fixture["fetch_bytes"],
    )
    status = sync.sync_once()
    assert status["status"] == "green"
    assert status["ingested_total"] == 1
    assert status["truth_contract"]["strict_event_contract"] is True
    assert status["truth_contract"]["legacy_exception_count"] == 1
    events = brain_snapshot(tmp_path)["events"]
    assert any(
        event.get("details", {}).get("federation_event_validation")
        == "LEGACY_EXACT_BLOB_EXCEPTION"
        for event in events
    )

def test_remote_sync_rejects_peer_packet_blob_substitution_without_blocking_event_validation(tmp_path):
    fixture = _fixture(_remote_event(), corrupt_peer_blob=True)
    sync = BrainRemoteSync(
        tmp_path,
        interval_seconds=60,
        fetch_json=fixture["fetch_json"],
        fetch_bytes=fixture["fetch_bytes"],
    )
    status = sync.sync_once()
    assert status["status"] == "degraded"
    assert status["peer_packet_status"] == "degraded"
    assert status["peer_lanes"] == []
    assert status["ingested_total"] == 1
    assert "peer packet Git blob SHA mismatch" in status["last_error"]


def test_remote_sync_rejects_peer_packet_authority_escalation(tmp_path):
    packet = _peer_packet(execution_authorized=True)
    fixture = _fixture(_remote_event(), peer=packet)
    sync = BrainRemoteSync(
        tmp_path,
        interval_seconds=60,
        fetch_json=fixture["fetch_json"],
        fetch_bytes=fixture["fetch_bytes"],
    )
    status = sync.sync_once()
    assert status["status"] == "degraded"
    assert status["peer_packet_status"] == "degraded"
    assert status["peer_lanes"] == []
    assert status["ingested_total"] == 1
    assert "peer packet attempts authority escalation" in status["last_error"]


def test_remote_sync_rejects_peer_lane_that_conflates_durability_with_substantive_evidence(tmp_path):
    packet = _peer_packet()
    packet["lanes"][0]["substantive_research_evidence"] = True
    unsigned = dict(packet)
    unsigned.pop("packet_id", None)
    packet["packet_id"] = __import__("hashlib").sha256(
        json.dumps(unsigned, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    fixture = _fixture(_remote_event(), peer=packet)
    sync = BrainRemoteSync(
        tmp_path,
        interval_seconds=60,
        fetch_json=fixture["fetch_json"],
        fetch_bytes=fixture["fetch_bytes"],
    )
    status = sync.sync_once()
    assert status["status"] == "degraded"
    assert status["peer_packet_status"] == "degraded"
    assert status["peer_substantive_lane_count"] == 0
    assert "claims substantive evidence without observed worker evidence" in status["last_error"]
