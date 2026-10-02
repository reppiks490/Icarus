from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from icarus_engine.brain import brain_snapshot
from icarus_engine.brain_sync import (
    BrainRemoteSync,
    REMOTE_ROOT,
    _REMOTE_CONSUMER_CONTRACT_API,
    _REMOTE_PRODUCER_CONTRACT_API,
    _REMOTE_PEER_PACKET_API,
    _git_blob_sha,
    _remote_compare_api,
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
                "stale_packet_is_current_state": False,
            },
            "freshness_required": True,
            "max_age_seconds": 1800,
            "max_future_skew_seconds": 300,
        },
        "historical_context": {
            "mode": "RESEARCH_CONTEXT_ONLY",
            "direct_candidate_evidence": False,
            "automatic_candidate_creation": False,
            "automatic_model_promotion": False,
            "execution_authorized": False,
            "production_decision_authorized": False,
            "sources": [
                {
                    "id": "robustness_guardian",
                    "path": "automation_intelligence/agent_fabric/robustness_guardian/latest.json",
                    "evidence_status": "HISTORICAL_RESEARCH_EVIDENCE",
                    "research_context_eligible": True,
                    "candidate_evidence_eligible": False,
                    "collection_only": False,
                    "summary_fields": ["RUN_CORE.findings"],
                    "execution_authorized": False,
                },
                {
                    "id": "alpha_synthesis",
                    "path": "automation_intelligence/agent_fabric/alpha_synthesis/latest.json",
                    "evidence_status": "HISTORICAL_RESEARCH_EVIDENCE",
                    "research_context_eligible": True,
                    "candidate_evidence_eligible": False,
                    "collection_only": False,
                    "summary_fields": ["RUN_CORE.findings"],
                    "execution_authorized": False,
                },
                {
                    "id": "apex_council",
                    "path": "automation_intelligence/agent_fabric/apex_council/latest.json",
                    "evidence_status": "HISTORICAL_RESEARCH_EVIDENCE",
                    "research_context_eligible": True,
                    "candidate_evidence_eligible": False,
                    "collection_only": False,
                    "summary_fields": ["RUN_CORE.findings"],
                    "execution_authorized": False,
                },
                {
                    "id": "flow_microstructure",
                    "path": "automation_intelligence/flow/latest.json",
                    "evidence_status": "HISTORICAL_COLLECTION_EVIDENCE",
                    "research_context_eligible": True,
                    "candidate_evidence_eligible": False,
                    "collection_only": True,
                    "summary_fields": ["NET_NEW_DELTA", "observations"],
                    "execution_authorized": False,
                },
            ],
            "truth_contract": {
                "foreign_repository_state_is_context_not_native_truth": True,
                "historical_context_never_bypasses_foundry": True,
                "historical_context_never_bypasses_evaluator": True,
                "historical_context_never_grants_shadow_qualification": True,
                "historical_context_never_grants_execution_authority": True,
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


def _historical_artifact(
    lane,
    *,
    path,
    evidence_status,
    collection_only=False,
    candidate_evidence_eligible=False,
    execution_authorized=False,
):
    artifact = {
        "lane": lane,
        "artifact_kind": "HISTORICAL_LATEST",
        "path": path,
        "run_id": f"{lane}-20260929T180500Z",
        "run_status": "RUN_PERSISTED",
        "evidence_status": evidence_status,
        "research_context_eligible": True,
        "candidate_evidence_eligible": candidate_evidence_eligible,
        "summary": {
            "built_changes": [],
            "data_gaps": ["fixture gap"] if collection_only else [],
            "findings": ["bounded historical context"],
            "next": "revalidate through foundry/evaluator",
            "net_new_delta_keys": ["btc"] if collection_only else [],
            "observation_keys": ["BTC_FIXTURE"] if collection_only else [],
            "source_provenance_count": 1 if collection_only else 0,
        },
        "lineage": {
            "base_main_sha": None if collection_only else "1" * 40,
            "final_main_sha": None if collection_only else "2" * 40,
            "run_core_sha256": None if collection_only else "3" * 64,
            "history_blob_sha": "4" * 40,
            "ledger_blob_sha": None,
            "history_mode": "primary_immutable" if collection_only else "primary_immutable_file",
        },
        "execution_authorized": execution_authorized,
    }
    artifact["artifact_id"] = __import__("hashlib").sha256(
        json.dumps(artifact, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    return artifact


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
        "historical_artifacts": [
            _historical_artifact(
                "robustness_guardian",
                path="automation_intelligence/agent_fabric/robustness_guardian/latest.json",
                evidence_status="HISTORICAL_RESEARCH_EVIDENCE",
            ),
            _historical_artifact(
                "flow_microstructure",
                path="automation_intelligence/flow/latest.json",
                evidence_status="HISTORICAL_COLLECTION_EVIDENCE",
                collection_only=True,
            ),
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
            "historical_context_never_bypasses_foundry_or_evaluator": True,
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
    peer_compare_status="ahead",
    peer_now_offset_seconds=60,
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
    peer_observed = datetime.fromisoformat(
        str(peer_doc["observed_at"]).replace("Z", "+00:00")
    )
    peer_now = peer_observed + timedelta(seconds=peer_now_offset_seconds)
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
        if requested == _remote_compare_api(peer_doc["source_commit"]):
            status = str(peer_compare_status).lower()
            response = {
                "status": status,
                "base_commit": {"sha": peer_doc["source_commit"]},
                "merge_base_commit": {"sha": peer_doc["source_commit"]},
            }
            if status == "diverged":
                response["merge_base_commit"] = {"sha": "a" * 40}
            return response
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
        "now_utc": lambda: peer_now,
    }


def test_remote_sync_ingests_custom_agent_and_owned_subsystem_events(tmp_path):
    fixture = _fixture(_remote_event())

    sync = BrainRemoteSync(
        tmp_path,
        interval_seconds=60,
        fetch_json=fixture["fetch_json"],
        fetch_bytes=fixture["fetch_bytes"],
        now_utc=fixture["now_utc"],
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
    assert status["peer_source_commit_verified"] is True
    assert status["peer_source_commit_relation"] == "AHEAD"
    assert status["peer_packet_fresh"] is True
    assert status["peer_packet_age_seconds"] == 60.0
    assert status["truth_contract"]["peer_packet_freshness_required"] is True
    assert status["truth_contract"]["peer_packet_max_age_seconds"] == 1800
    assert status["truth_contract"]["peer_packet_max_future_skew_seconds"] == 300
    assert status["peer_substantive_lane_count"] == 1
    assert status["peer_durability_only_lane_count"] == 1
    assert len(status["peer_lanes"]) == 3
    assert status["truth_contract"]["peer_historical_context_mode"] == "RESEARCH_CONTEXT_ONLY"
    assert status["truth_contract"]["peer_historical_context_source_count"] == 4
    assert status["truth_contract"]["peer_historical_context_candidate_evidence"] is False
    assert status["peer_historical_context_count"] == 1
    assert status["peer_historical_collection_count"] == 1
    assert len(status["peer_historical_artifacts"]) == 2
    assert all(
        artifact["candidate_evidence_eligible"] is False
        and artifact["execution_authorized"] is False
        for artifact in status["peer_historical_artifacts"]
    )
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
        now_utc=fixture["now_utc"],
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
        now_utc=fixture["now_utc"],
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
        now_utc=fixture["now_utc"],
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
        now_utc=fixture["now_utc"],
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
        now_utc=fixture["now_utc"],
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
        now_utc=fixture["now_utc"],
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
        now_utc=fixture["now_utc"],
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
        now_utc=fixture["now_utc"],
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
        now_utc=fixture["now_utc"],
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
        now_utc=fixture["now_utc"],
    )
    status = sync.sync_once()
    assert status["status"] == "degraded"
    assert status["peer_packet_status"] == "degraded"
    assert status["peer_substantive_lane_count"] == 0
    assert "claims substantive evidence without observed worker evidence" in status["last_error"]

def _rehash_peer_packet(packet):
    unsigned = dict(packet)
    unsigned.pop("packet_id", None)
    packet["packet_id"] = __import__("hashlib").sha256(
        json.dumps(unsigned, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    return packet


def test_remote_sync_rejects_peer_packet_source_contract_substitution(tmp_path):
    packet = _peer_packet()
    packet["source_contracts"]["control_plane"] = "automation_intelligence/fake-control.json"
    _rehash_peer_packet(packet)
    fixture = _fixture(_remote_event(), peer=packet)
    sync = BrainRemoteSync(
        tmp_path,
        interval_seconds=60,
        fetch_json=fixture["fetch_json"],
        fetch_bytes=fixture["fetch_bytes"],
        now_utc=fixture["now_utc"],
    )
    status = sync.sync_once()
    assert status["status"] == "degraded"
    assert status["peer_packet_status"] == "degraded"
    assert status["peer_lanes"] == []
    assert "source contracts mismatch" in status["last_error"]


def test_remote_sync_rejects_invented_foreign_sibling_lane_state(tmp_path):
    packet = _peer_packet()
    csv_lane = next(row for row in packet["lanes"] if row["name"] == "advanced_csv")
    csv_lane["evidence_status"] = "PERSISTED_WORKER_EVIDENCE"
    csv_lane["worker_execution_observed"] = True
    csv_lane["substantive_research_evidence"] = True
    _rehash_peer_packet(packet)
    fixture = _fixture(_remote_event(), peer=packet)
    sync = BrainRemoteSync(
        tmp_path,
        interval_seconds=60,
        fetch_json=fixture["fetch_json"],
        fetch_bytes=fixture["fetch_bytes"],
        now_utc=fixture["now_utc"],
    )
    status = sync.sync_once()
    assert status["status"] == "degraded"
    assert status["peer_packet_status"] == "degraded"
    assert status["peer_lanes"] == []
    assert "invents state for a foreign sibling repository" in status["last_error"]

def test_remote_sync_rejects_peer_packet_whose_source_commit_is_not_on_main(tmp_path):
    fixture = _fixture(_remote_event(), peer_compare_status="diverged")
    sync = BrainRemoteSync(
        tmp_path,
        interval_seconds=60,
        fetch_json=fixture["fetch_json"],
        fetch_bytes=fixture["fetch_bytes"],
        now_utc=fixture["now_utc"],
    )
    status = sync.sync_once()
    assert status["status"] == "degraded"
    assert status["peer_packet_status"] == "degraded"
    assert status["peer_source_commit"] is None
    assert status["peer_source_commit_verified"] is False
    assert status["peer_source_commit_relation"] is None
    assert status["ingested_total"] == 1
    assert "not an ancestor of Icarus-engine/main" in status["last_error"]

def test_remote_sync_rejects_stale_peer_packet_but_keeps_event_ingest_independent(tmp_path):
    fixture = _fixture(_remote_event(), peer_now_offset_seconds=1801)
    sync = BrainRemoteSync(
        tmp_path,
        interval_seconds=60,
        fetch_json=fixture["fetch_json"],
        fetch_bytes=fixture["fetch_bytes"],
        now_utc=fixture["now_utc"],
    )
    status = sync.sync_once()
    assert status["status"] == "degraded"
    assert status["peer_packet_status"] == "degraded"
    assert status["peer_packet_fresh"] is False
    assert status["peer_packet_age_seconds"] is None
    assert status["ingested_total"] == 1
    assert "peer packet is stale" in status["last_error"]


def test_remote_sync_rejects_peer_packet_beyond_future_clock_skew(tmp_path):
    fixture = _fixture(_remote_event(), peer_now_offset_seconds=-301)
    sync = BrainRemoteSync(
        tmp_path,
        interval_seconds=60,
        fetch_json=fixture["fetch_json"],
        fetch_bytes=fixture["fetch_bytes"],
        now_utc=fixture["now_utc"],
    )
    status = sync.sync_once()
    assert status["status"] == "degraded"
    assert status["peer_packet_status"] == "degraded"
    assert status["peer_packet_fresh"] is False
    assert status["ingested_total"] == 1
    assert "future clock skew" in status["last_error"]


def test_remote_sync_rejects_peer_freshness_contract_drift_before_event_ingest(tmp_path):
    consumer = _consumer_contract()
    consumer["peer_packet"] = json.loads(json.dumps(consumer["peer_packet"]))
    consumer["peer_packet"]["max_age_seconds"] = 999999
    fixture = _fixture(_remote_event(), consumer=consumer)
    sync = BrainRemoteSync(
        tmp_path,
        interval_seconds=60,
        fetch_json=fixture["fetch_json"],
        fetch_bytes=fixture["fetch_bytes"],
        now_utc=fixture["now_utc"],
    )
    status = sync.sync_once()
    assert status["status"] == "degraded"
    assert status["ingested_total"] == 0
    assert "peer packet max age mismatch" in status["last_error"]

def _rehash_peer_packet(packet):
    unsigned = dict(packet)
    unsigned.pop("packet_id", None)
    packet["packet_id"] = __import__("hashlib").sha256(
        json.dumps(unsigned, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    return packet


def test_remote_sync_rejects_historical_context_candidate_evidence_promotion(tmp_path):
    packet = _peer_packet()
    packet["historical_artifacts"][0] = _historical_artifact(
        "robustness_guardian",
        path="automation_intelligence/agent_fabric/robustness_guardian/latest.json",
        evidence_status="HISTORICAL_RESEARCH_EVIDENCE",
        candidate_evidence_eligible=True,
    )
    _rehash_peer_packet(packet)
    fixture = _fixture(_remote_event(), peer=packet)
    sync = BrainRemoteSync(
        tmp_path,
        interval_seconds=60,
        fetch_json=fixture["fetch_json"],
        fetch_bytes=fixture["fetch_bytes"],
        now_utc=fixture["peer_now_utc"],
    )
    status = sync.sync_once()
    assert status["status"] == "degraded"
    assert status["peer_historical_artifacts"] == []
    assert status["ingested_total"] == 1
    assert "attempts candidate-evidence promotion" in status["last_error"]


def test_remote_sync_rejects_undeclared_historical_artifact_path(tmp_path):
    packet = _peer_packet()
    packet["historical_artifacts"][0] = _historical_artifact(
        "robustness_guardian",
        path="automation_intelligence/agent_fabric/robustness_guardian/other.json",
        evidence_status="HISTORICAL_RESEARCH_EVIDENCE",
    )
    _rehash_peer_packet(packet)
    fixture = _fixture(_remote_event(), peer=packet)
    sync = BrainRemoteSync(
        tmp_path,
        interval_seconds=60,
        fetch_json=fixture["fetch_json"],
        fetch_bytes=fixture["fetch_bytes"],
        now_utc=fixture["peer_now_utc"],
    )
    status = sync.sync_once()
    assert status["status"] == "degraded"
    assert status["peer_historical_artifacts"] == []
    assert status["ingested_total"] == 1
    assert "path mismatch" in status["last_error"]


def test_remote_sync_rejects_historical_artifact_hash_substitution(tmp_path):
    packet = _peer_packet()
    packet["historical_artifacts"][0]["summary"]["findings"] = ["tampered after artifact hash"]
    _rehash_peer_packet(packet)
    fixture = _fixture(_remote_event(), peer=packet)
    sync = BrainRemoteSync(
        tmp_path,
        interval_seconds=60,
        fetch_json=fixture["fetch_json"],
        fetch_bytes=fixture["fetch_bytes"],
        now_utc=fixture["peer_now_utc"],
    )
    status = sync.sync_once()
    assert status["status"] == "degraded"
    assert status["peer_historical_artifacts"] == []
    assert "artifact_id mismatch" in status["last_error"]


def test_remote_sync_rejects_historical_contract_authority_escalation(tmp_path):
    consumer = _consumer_contract()
    consumer["historical_context"]["automatic_candidate_creation"] = True
    fixture = _fixture(_remote_event(), consumer=consumer)
    sync = BrainRemoteSync(
        tmp_path,
        interval_seconds=60,
        fetch_json=fixture["fetch_json"],
        fetch_bytes=fixture["fetch_bytes"],
        now_utc=fixture["peer_now_utc"],
    )
    status = sync.sync_once()
    assert status["status"] == "degraded"
    assert status["ingested_total"] == 0
    assert "historical context attempts authority escalation" in status["last_error"]
