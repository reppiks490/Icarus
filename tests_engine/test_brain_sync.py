from __future__ import annotations

import json
import pytest
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
    _remote_contents_api,
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
            "source_contract_blob_witnesses_required": True,
            "source_contract_blob_witness_keys": [
                "control_plane",
                "agent_fabric",
                "mcp_interface",
            ],
            "lane_source_witnesses_required": True,
            "lane_source_witness_fields": [
                "heartbeat_path",
                "heartbeat_blob_sha",
                "finalization_path",
                "finalization_blob_sha",
            ],
            "semantics": {
                "lane_state_is_foreign_evidence": True,
                "durability_only_is_not_substantive_research_evidence": True,
                "remote_sibling_state_is_never_inferred": True,
                "automatic_model_promotion": False,
                "production_decision_authorized": False,
                "automatic_execution_authority": False,
                "stale_packet_is_current_state": False,
                "lane_state_source_blobs_are_revision_bound": True,
                "source_contract_blobs_are_revision_bound": True,
            },
            "freshness_required": True,
            "max_age_seconds": 1800,
            "max_future_skew_seconds": 300,
        },
        "canonical_acceptance": {
            "repository": "reppiks490/Icarus",
            "ref": "main",
            "path": "automation_intelligence/federation/icarus_engine_acceptance.json",
            "schema_version": "icarus-engine-federation-acceptance-v1",
            "authority": "RESEARCH",
            "required_for_export": False,
            "lag_semantics": (
                "Acknowledgement may refer to the previously published peer packet; "
                "it never upgrades the current packet's authority."
            ),
            "semantics": {
                "acceptance_is_foreign_evidence_not_native_truth": True,
                "prior_packet_acknowledgement_is_not_current_packet_qualification": True,
                "automatic_model_promotion": False,
                "production_decision_authorized": False,
                "automatic_execution_authority": False,
            },
            "execution_authorized": False,
            "production_decision_authorized": False,
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


def _historical_context_contract():
    return {
        "mode": "RESEARCH_CONTEXT_ONLY",
        "source_artifact_blob_required": True,
        "artifact_id_sha256_required": True,
        "packet_projection_verification_required": True,
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
                "summary_fields": [
                    "RUN_CORE.findings",
                    "RUN_CORE.built_changes",
                    "RUN_CORE.unresolved_risks",
                    "RUN_CORE.NEXT",
                    "RUN_CORE.test_state",
                    "RUN_CORE.base_main_sha",
                    "RUN_CORE.final_main_sha",
                    "RUN_CORE_SHA256",
                    "history_blob_sha",
                ],
                "execution_authorized": False,
            },
            {
                "id": "alpha_synthesis",
                "path": "automation_intelligence/agent_fabric/alpha_synthesis/latest.json",
                "evidence_status": "HISTORICAL_RESEARCH_EVIDENCE",
                "research_context_eligible": True,
                "candidate_evidence_eligible": False,
                "collection_only": False,
                "summary_fields": [
                    "RUN_CORE.evidence_dataset_identity",
                    "RUN_CORE.findings",
                    "RUN_CORE.built_changes",
                    "RUN_CORE.unresolved_risks",
                    "RUN_CORE.NEXT",
                    "RUN_CORE_SHA256",
                    "history_blob_sha",
                    "ledger_blob_sha",
                ],
                "execution_authorized": False,
            },
            {
                "id": "apex_council",
                "path": "automation_intelligence/agent_fabric/apex_council/latest.json",
                "evidence_status": "HISTORICAL_RESEARCH_EVIDENCE",
                "research_context_eligible": True,
                "candidate_evidence_eligible": False,
                "collection_only": False,
                "summary_fields": [
                    "RUN_CORE.specialist_states_consumed",
                    "RUN_CORE.evidence_contract",
                    "RUN_CORE.decision_contract",
                    "RUN_CORE.disagreements_collisions",
                    "RUN_CORE.built_changes",
                    "RUN_CORE.NEXT",
                    "RUN_CORE.base_main_sha",
                    "RUN_CORE.final_main_sha",
                    "RUN_CORE_SHA256",
                    "history_blob_sha",
                    "ledger_blob_sha",
                ],
                "execution_authorized": False,
            },
            {
                "id": "flow_microstructure",
                "path": "automation_intelligence/flow/latest.json",
                "evidence_status": "HISTORICAL_COLLECTION_EVIDENCE",
                "research_context_eligible": True,
                "candidate_evidence_eligible": False,
                "collection_only": True,
                "summary_fields": [
                    "NET_NEW_DELTA",
                    "observations",
                    "PROVIDER_CONFLICTS",
                    "DATA_GAPS",
                    "source_provenance",
                    "quality_notes",
                    "history_blob_sha",
                ],
                "execution_authorized": False,
            },
        ],
        "truth_contract": {
            "foreign_repository_state_is_context_not_native_truth": True,
            "historical_context_never_bypasses_foundry": True,
            "historical_context_never_bypasses_evaluator": True,
            "historical_context_never_grants_shadow_qualification": True,
            "historical_context_never_grants_execution_authority": True,
            "historical_packet_projection_is_source_derived": True,
        },
    }


def _historical_docs():
    return {
        "robustness_guardian": {
            "schema_version": "agent-fabric-persistence-v3",
            "agent": "robustness_guardian",
            "RUN_ID": "robustness-guardian-20260929T180500Z",
            "RUN_STATUS": "RUN_PERSISTED",
            "RUN_CORE": {
                "execution_authorized": False,
                "base_main_sha": "1" * 40,
                "final_main_sha": "2" * 40,
                "findings": [
                    "Protected holdout lineage is incomplete.",
                    "Replay determinism remains intact.",
                ],
                "built_changes": ["No behavioral code change."],
                "unresolved_risks": ["Dataset identity still needs exact binding."],
                "NEXT": "Bind immutable dataset and holdout identities.",
                "test_state": {"status": "green"},
            },
            "RUN_CORE_SHA256": "3" * 64,
            "history_blob_sha": "4" * 40,
            "execution_authorized": False,
            "private_raw_payload": {"must_not_cross": True},
        },
        "alpha_synthesis": {
            "schema_version": "agent-fabric-persistence-v3",
            "agent": "alpha_synthesis",
            "RUN_ID": "alpha-synthesis-20260929T181500Z",
            "RUN_STATUS": "RUN_PERSISTED",
            "RUN_CORE": {
                "execution_authorized": False,
                "evidence_dataset_identity": {"dataset": "fixture"},
                "findings": ["Execution economics remain binding."],
                "built_changes": ["No production mutation."],
                "unresolved_risks": ["Cost model drift."],
                "NEXT": "Revalidate under new cost strata.",
            },
            "RUN_CORE_SHA256": "5" * 64,
            "history_blob_sha": "6" * 40,
            "ledger_blob_sha": "7" * 40,
            "execution_authorized": False,
        },
        "apex_council": {
            "schema_version": "agent-fabric-persistence-v3",
            "agent": "apex_council",
            "RUN_ID": "apex-council-20260929T182500Z",
            "RUN_STATUS": "RUN_PERSISTED",
            "RUN_CORE": {
                "execution_authorized": False,
                "specialist_states_consumed": ["flow", "aion", "daedalus"],
                "evidence_contract": {"mode": "research"},
                "decision_contract": {"authority": "none"},
                "disagreements_collisions": ["Flow and macro disagree on regime timing."],
                "built_changes": ["Preserved disagreement."],
                "NEXT": "Resolve with causal-time evidence.",
                "base_main_sha": "8" * 40,
                "final_main_sha": "9" * 40,
            },
            "RUN_CORE_SHA256": "a" * 64,
            "history_blob_sha": "b" * 40,
            "ledger_blob_sha": "c" * 40,
            "execution_authorized": False,
        },
        "flow_microstructure": {
            "engine": "flow",
            "schema_version": "microstructure-collection-v4",
            "RUN_ID": "flow-20260929T173500Z",
            "RUN_STATUS": "RUN_PERSISTED",
            "COLLECTION_ONLY": True,
            "execution_authorized": False,
            "NET_NEW_DELTA": {"btc": "fresh funding evidence"},
            "observations": {"BTC": {"funding_percent": 0.003}},
            "PROVIDER_CONFLICTS": [],
            "DATA_GAPS": ["No direct NQ depth."],
            "source_provenance": [{"source": "venue"}],
            "quality_notes": ["fixture"],
            "history_blob_sha": "d" * 40,
        },
    }


def _producer_contract():
    return {
        "schema_version": "icarus-mcp-interface-contract-v1",
        "event_root": "automation_intelligence/mcp_interface/events",
        "event_schema": "icarus-mcp-event-v1",
        "ui_api": "/api/mcp/control",
        "ui_tab": "MCP / Automation",
        "source_of_truth": "LOCAL_REPOSITORY_SNAPSHOT",
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


def _historical_packet_projection_fixture(document):
    core = document.get("RUN_CORE")
    if not isinstance(core, dict):
        core = {}
    findings = core.get("findings") if isinstance(core.get("findings"), list) else []
    built_changes = (
        core.get("built_changes") if isinstance(core.get("built_changes"), list) else []
    )
    next_step = core.get("NEXT") if isinstance(core.get("NEXT"), str) else None
    observations = document.get("observations")
    if not isinstance(observations, dict):
        observations = {}
    data_gaps = document.get("DATA_GAPS")
    if not isinstance(data_gaps, list):
        data_gaps = []
    source_provenance = document.get("source_provenance")
    if not isinstance(source_provenance, list):
        source_provenance = []
    net_new_delta = document.get("NET_NEW_DELTA")
    if not isinstance(net_new_delta, dict):
        net_new_delta = {}
    persisted = str(document.get("RUN_STATUS") or document.get("status") or "").upper() == "RUN_PERSISTED"
    if persisted and (findings or built_changes or next_step):
        evidence_status = "HISTORICAL_RESEARCH_EVIDENCE"
        context_eligible = True
    elif persisted and (
        document.get("COLLECTION_ONLY") is True
        or observations
        or source_provenance
        or net_new_delta
    ):
        evidence_status = "HISTORICAL_COLLECTION_EVIDENCE"
        context_eligible = True
    elif persisted:
        evidence_status = "HISTORICAL_STATE_ONLY"
        context_eligible = False
    else:
        evidence_status = "HISTORICAL_UNVERIFIED"
        context_eligible = False
    return {
        "summary": {
            "findings": [str(x) for x in findings],
            "built_changes": [str(x) for x in built_changes],
            "next": next_step,
            "observation_keys": sorted(str(x) for x in observations.keys()),
            "data_gaps": [str(x) for x in data_gaps],
            "source_provenance_count": len(source_provenance),
            "net_new_delta_keys": sorted(str(x) for x in net_new_delta.keys()),
        },
        "lineage": {
            "base_main_sha": core.get("base_main_sha"),
            "final_main_sha": core.get("final_main_sha"),
            "run_core_sha256": document.get("RUN_CORE_SHA256"),
            "history_blob_sha": document.get("history_blob_sha"),
            "ledger_blob_sha": document.get("ledger_blob_sha"),
            "history_mode": document.get("history_mode"),
        },
        "evidence_status": evidence_status,
        "research_context_eligible": context_eligible,
    }


def _rehash_historical_artifact(artifact):
    unsigned = dict(artifact)
    unsigned.pop("artifact_id", None)
    artifact["artifact_id"] = __import__("hashlib").sha256(
        json.dumps(
            unsigned,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode()
    ).hexdigest()


def _historical_packet_artifacts(documents=None):
    documents = documents or _historical_docs()
    contract = _historical_context_contract()
    sources = {row["id"]: row for row in contract["sources"]}
    artifacts = []
    for source_id in sorted(sources):
        source = sources[source_id]
        document = documents[source_id]
        raw = (json.dumps(document, sort_keys=True) + "\n").encode()
        run_id = document.get("RUN_ID") or document.get("run_id")
        run_status = document.get("RUN_STATUS") or document.get("status")
        projection = _historical_packet_projection_fixture(document)
        artifact = {
            "lane": source_id,
            "artifact_kind": "HISTORICAL_LATEST",
            "path": source["path"],
            "source_artifact_blob_sha": _git_blob_sha(raw),
            "run_id": run_id,
            "run_status": run_status,
            "evidence_status": source["evidence_status"],
            "research_context_eligible": True,
            "candidate_evidence_eligible": False,
            "summary": projection["summary"],
            "lineage": projection["lineage"],
            "execution_authorized": False,
        }
        _rehash_historical_artifact(artifact)
        artifacts.append(artifact)
    return artifacts


def _lane_source_docs():
    return {
        "automation_intelligence/agent_fabric/robustness_guardian/heartbeat.json": {
            "RUN_ID": "robustness-guardian-20261002T200500Z",
            "RUN_STATUS": "RUN_PERSISTED",
            "finalization_commit_sha": "d" * 40,
            "execution_authorized": False,
        },
        "automation_intelligence/agent_fabric/robustness_guardian/finalization_state.json": {
            "RUN_ID": "robustness-guardian-20261002T200500Z",
            "RUN_STATUS": "RUN_PERSISTED",
            "completion_semantics": "DURABILITY_RECEIPT_ONLY",
            "receipt_origin": "github_watchdog_stabilization_fallback",
            "worker_execution_observed": False,
            "execution_authorized": False,
        },
        "automation_intelligence/flow/heartbeat.json": {
            "RUN_ID": "flow-20261002T203500Z",
            "RUN_STATUS": "RUN_PERSISTED",
            "finalization_commit_sha": "e" * 40,
            "execution_authorized": False,
        },
        "automation_intelligence/flow/finalization_state.json": {
            "RUN_ID": "flow-20261002T203500Z",
            "RUN_STATUS": "RUN_PERSISTED",
            "completion_semantics": "WORKER_EVIDENCE",
            "worker_execution_observed": True,
            "execution_authorized": False,
        },
    }


def _fixture_blob(document):
    raw = (json.dumps(document, sort_keys=True) + "\n").encode()
    return _git_blob_sha(raw)


def _source_contract_docs():
    return {
        "control_plane": {
            "schema_version": "restored-five-native-control-v1",
            "control_plane_id": "restored-five-native-liveness-v1",
            "repository": "reppiks490/Icarus-engine",
            "timezone": "America/Chicago",
            "grace_minutes": 8,
            "catchup_horizon_minutes": 180,
            "execution_authorized": False,
            "lanes": [
                {
                    "name": "robustness_guardian",
                    "title": "Robustness Guardian Evolution",
                    "minute": 5,
                    "scheduler_id": "rg-1",
                    "worker_root": "automation_intelligence/agent_fabric/robustness_guardian",
                    "run_prefix": "robustness-guardian",
                },
                {
                    "name": "advanced_csv",
                    "title": "Advanced CSV Data Collector",
                    "minute": 15,
                    "scheduler_id": "csv-1",
                    "worker_repository": "reppiks490/icarus-csv-evidence-lab",
                    "worker_root": "automation_intelligence/advanced_csv",
                    "run_prefix": "advanced-csv",
                },
                {
                    "name": "flow_microstructure",
                    "title": "Microstructure Sensor Grid",
                    "minute": 35,
                    "scheduler_id": "flow-1",
                    "worker_root": "automation_intelligence/flow",
                    "run_prefix": "flow",
                },
            ],
        },
        "agent_fabric": {
            "schema_version": "agent-fabric-scheduler-bindings-v1",
            "repository": "reppiks490/Icarus-engine",
            "branch": "main",
            "execution_authorized": False,
            "lanes": {
                "robustness_guardian": {
                    "runtime_status_source": (
                        "automation_intelligence/agent_fabric/"
                        "robustness_guardian/heartbeat.json"
                    ),
                    "finalization_state": (
                        "automation_intelligence/agent_fabric/"
                        "robustness_guardian/finalization_state.json"
                    ),
                }
            },
        },
        "mcp_interface": _producer_contract(),
    }


def _source_contract_blobs(documents=None):
    documents = documents or _source_contract_docs()
    return {
        key: _fixture_blob(documents[key])
        for key in ("control_plane", "agent_fabric", "mcp_interface")
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
        "source_contract_blobs": _source_contract_blobs(),
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
                "heartbeat_path": "automation_intelligence/agent_fabric/robustness_guardian/heartbeat.json",
                "heartbeat_blob_sha": _fixture_blob(
                    _lane_source_docs()[
                        "automation_intelligence/agent_fabric/robustness_guardian/heartbeat.json"
                    ]
                ),
                "finalization_path": "automation_intelligence/agent_fabric/robustness_guardian/finalization_state.json",
                "finalization_blob_sha": _fixture_blob(
                    _lane_source_docs()[
                        "automation_intelligence/agent_fabric/robustness_guardian/finalization_state.json"
                    ]
                ),
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
                "heartbeat_path": "automation_intelligence/flow/heartbeat.json",
                "heartbeat_blob_sha": _fixture_blob(
                    _lane_source_docs()["automation_intelligence/flow/heartbeat.json"]
                ),
                "finalization_path": "automation_intelligence/flow/finalization_state.json",
                "finalization_blob_sha": _fixture_blob(
                    _lane_source_docs()["automation_intelligence/flow/finalization_state.json"]
                ),
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
                "heartbeat_path": None,
                "heartbeat_blob_sha": None,
                "finalization_path": None,
                "finalization_blob_sha": None,
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
        "historical_artifacts": _historical_packet_artifacts(),
        "mcp_interface": {
            "schema_version": "icarus-mcp-interface-contract-v1",
            "event_root": "automation_intelligence/mcp_interface/events",
            "ui_api": "/api/mcp/control",
            "ui_tab": "MCP / Automation",
            "source_of_truth": "LOCAL_REPOSITORY_SNAPSHOT",
            "trading_execution_authorized": False,
        },
        "canonical_acceptance": {
            "status": "UNAVAILABLE",
            "schema_version": "icarus-engine-federation-acceptance-v1",
            "accepted_by_repository": "reppiks490/Icarus",
            "producer_repository": "reppiks490/Icarus-engine",
            "authority": "RESEARCH",
            "required_for_export": False,
            "execution_authorized": False,
            "production_decision_authorized": False,
            "automatic_model_promotion": False,
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


def _verified_roundtrip_ack(**overrides):
    payload = {
        "status": "VERIFIED_PRIOR_PACKET",
        "schema_version": "icarus-engine-federation-acceptance-v1",
        "accepted_by_repository": "reppiks490/Icarus",
        "producer_repository": "reppiks490/Icarus-engine",
        "accepted_by_icarus_commit": "1" * 40,
        "accepted_peer_packet_id": "2" * 64,
        "accepted_peer_packet_blob_sha": "3" * 40,
        "accepted_peer_source_commit": "4" * 40,
        "peer_source_commit_relation": "AHEAD",
        "peer_source_contract_witness_count": 3,
        "peer_lane_count": 3,
        "peer_lane_witness_verified_count": 2,
        "peer_lane_contract_binding_verified_count": 3,
        "authority": "RESEARCH",
        "required_for_export": False,
        "execution_authorized": False,
        "production_decision_authorized": False,
        "automatic_model_promotion": False,
    }
    payload.update(overrides)
    return payload


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
    historical_docs=None,
    packet_historical_docs=None,
    lane_source_docs=None,
    source_contract_docs=None,
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
    historical_docs = historical_docs or {}
    packet_historical_docs = packet_historical_docs or _historical_docs()
    lane_source_docs = lane_source_docs or _lane_source_docs()
    source_contract_docs = source_contract_docs or _source_contract_docs()
    if allow_legacy_event:
        consumer_doc = json.loads(json.dumps(consumer_doc))
        consumer_doc["event_validation"]["legacy_relaxed_blob_shas"] = [event_sha]
    producer_doc = _producer_contract()
    peer_doc = peer or _peer_packet(
        historical_artifacts=_historical_packet_artifacts(packet_historical_docs),
        source_contract_blobs=_source_contract_blobs(source_contract_docs),
    )
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

    historical_meta = {}
    historical_raw = {}
    for source_id, document in historical_docs.items():
        raw = (json.dumps(document, sort_keys=True) + "\n").encode()
        url = f"https://api.github.test/historical/{source_id}"
        historical_path = next(
            row["path"]
            for row in consumer_doc.get("historical_context", {}).get("sources", [])
            if row["id"] == source_id
        )
        api = (
            "https://api.github.com/repos/reppiks490/Icarus-engine/contents/"
            f"{historical_path}?ref=main"
        )
        historical_raw[url] = raw
        historical_meta[api] = {
            "type": "file",
            "sha": _git_blob_sha(raw),
            "url": url,
        }

    packet_historical_meta = {}
    packet_historical_raw = {}
    for source_id, document in packet_historical_docs.items():
        raw = (json.dumps(document, sort_keys=True) + "\n").encode()
        url = f"https://api.github.test/packet-historical/{source_id}"
        historical_path = next(
            row["path"]
            for row in _historical_context_contract()["sources"]
            if row["id"] == source_id
        )
        api = _remote_contents_api(
            historical_path,
            ref=peer_doc["source_commit"],
        )
        packet_historical_raw[url] = raw
        packet_historical_meta[api] = {
            "type": "file",
            "sha": _git_blob_sha(raw),
            "url": url,
        }

    lane_source_meta = {}
    lane_source_raw = {}
    for lane_path, document in lane_source_docs.items():
        raw = (json.dumps(document, sort_keys=True) + "\n").encode()
        url = "https://api.github.test/lane-source/" + lane_path.replace("/", "_")
        api = _remote_contents_api(lane_path, ref=peer_doc["source_commit"])
        lane_source_raw[url] = raw
        lane_source_meta[api] = {
            "type": "file",
            "sha": _git_blob_sha(raw),
            "url": url,
        }

    source_contract_meta = {}
    source_contract_raw = {}
    source_contract_paths = {
        "control_plane": "automation_intelligence/restored_five_native/control_plane.json",
        "agent_fabric": "automation_intelligence/agent_fabric/manifest.json",
        "mcp_interface": "automation_intelligence/mcp_interface/contract.json",
    }
    for contract_id, document in source_contract_docs.items():
        raw = (json.dumps(document, sort_keys=True) + "\n").encode()
        url = f"https://api.github.test/source-contract/{contract_id}"
        api = _remote_contents_api(
            source_contract_paths[contract_id],
            ref=peer_doc["source_commit"],
        )
        source_contract_raw[url] = raw
        source_contract_meta[api] = {
            "type": "file",
            "sha": _git_blob_sha(raw),
            "url": url,
        }

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
        if requested in historical_meta:
            return historical_meta[requested]
        if requested in packet_historical_meta:
            return packet_historical_meta[requested]
        if requested in lane_source_meta:
            return lane_source_meta[requested]
        if requested in source_contract_meta:
            return source_contract_meta[requested]
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
        if requested in historical_raw:
            return historical_raw[requested]
        if requested in packet_historical_raw:
            return packet_historical_raw[requested]
        if requested in lane_source_raw:
            return lane_source_raw[requested]
        if requested in source_contract_raw:
            return source_contract_raw[requested]
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
    assert status["peer_lane_witness_verified_count"] == 2
    assert status["peer_lane_witness_unavailable_count"] == 0
    assert status["peer_source_contract_witness_status"] == "green"
    assert status["peer_source_contract_witness_count"] == 3
    assert status["peer_roundtrip_ack_status"] == "UNAVAILABLE"
    assert status["peer_roundtrip_ack"]["authority"] == "RESEARCH"
    assert status["peer_roundtrip_ack"]["execution_authorized"] is False
    assert status["truth_contract"]["canonical_acceptance_schema"] == "icarus-engine-federation-acceptance-v1"
    assert status["truth_contract"]["canonical_acceptance_required_for_export"] is False
    assert status["peer_lane_contract_binding_verified_count"] == 3
    contract_bound = {row["name"]: row for row in status["peer_lanes"]}
    assert contract_bound["robustness_guardian"]["contract_binding_status"] == "CONTRACT_BOUND_LOCAL"
    assert contract_bound["flow_microstructure"]["contract_binding_status"] == "CONTRACT_BOUND_LOCAL"
    assert contract_bound["advanced_csv"]["contract_binding_status"] == "CONTRACT_BOUND_REMOTE_SIBLING"
    assert all(row["contract_binding_verified"] is True for row in contract_bound.values())
    assert all(
        row["verified"] is True
        for row in status["peer_source_contract_witnesses"]
    )
    assert (
        status["truth_contract"]["peer_source_contract_blob_witnesses_required"]
        is True
    )
    assert status["truth_contract"]["peer_lane_source_witnesses_required"] is True
    assert len(status["peer_lanes"]) == 3
    local_lanes = [
        row for row in status["peer_lanes"]
        if row["worker_repository"] == "reppiks490/Icarus-engine"
    ]
    assert all(row["source_witness_verified"] is True for row in local_lanes)
    assert all(
        row["source_witness_status"] == "VERIFIED_AT_PACKET_SOURCE"
        for row in local_lanes
    )
    remote_lane = next(
        row for row in status["peer_lanes"] if row["name"] == "advanced_csv"
    )
    assert remote_lane["source_witness_status"] == "REMOTE_PEER_UNREAD"
    assert status["historical_packet_witness_status"] == "green"
    assert status["historical_packet_witness_count"] == 4
    assert all(
        row["source_artifact_blob_verified"] is True
        and row["candidate_evidence_eligible"] is False
        and row["execution_authorized"] is False
        for row in status["historical_packet_witnesses"]
    )
    assert status["truth_contract"]["historical_source_artifact_blob_required"] is False
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


def test_remote_sync_ingests_declared_historical_context_without_candidate_authority(tmp_path):
    consumer = _consumer_contract(historical_context=_historical_context_contract())
    fixture = _fixture(
        _remote_event(),
        consumer=consumer,
        historical_docs=_historical_docs(),
    )
    sync = BrainRemoteSync(
        tmp_path,
        interval_seconds=60,
        fetch_json=fixture["fetch_json"],
        fetch_bytes=fixture["fetch_bytes"],
        now_utc=fixture["now_utc"],
    )
    status = sync.sync_once()

    assert status["status"] == "green", status.get("last_error")
    assert status["historical_context_status"] == "green"
    assert status["historical_context_source_count"] == 4
    assert status["historical_context_ingested_total"] == 4
    assert status["historical_candidate_evidence_count"] == 0
    assert status["truth_contract"]["historical_context_mode"] == "RESEARCH_CONTEXT_ONLY"
    assert status["truth_contract"]["historical_context_never_bypasses_foundry"] is True
    assert status["truth_contract"]["historical_context_never_bypasses_evaluator"] is True
    assert status["truth_contract"]["historical_context_never_grants_shadow_qualification"] is True
    assert status["truth_contract"]["historical_source_artifact_blob_required"] is True
    assert status["truth_contract"]["historical_artifact_id_sha256_required"] is True
    assert (
        status["truth_contract"]["historical_packet_projection_verification_required"]
        is True
    )
    assert status["truth_contract"]["historical_packet_projection_is_source_derived"] is True
    assert status["historical_packet_witness_status"] == "green"
    assert status["historical_packet_witness_count"] == 4
    assert status["historical_packet_projection_verified_count"] == 4
    assert all(
        row["projection_verified"] is True
        for row in status["historical_packet_witnesses"]
    )
    assert status["historical_packet_same_as_live_count"] == 4
    assert status["historical_packet_live_advanced_count"] == 0

    rows = {row["id"]: row for row in status["historical_context_sources"]}
    assert set(rows) == {
        "robustness_guardian", "alpha_synthesis", "apex_council", "flow_microstructure"
    }
    assert all(row["candidate_evidence_eligible"] is False for row in rows.values())
    assert all(row["foreign_evidence_only"] is True for row in rows.values())
    assert all(row["requires_foundry_and_evaluator"] is True for row in rows.values())
    assert rows["flow_microstructure"]["evidence_status"] == "HISTORICAL_COLLECTION_EVIDENCE"
    assert rows["robustness_guardian"]["summary"]["RUN_CORE.findings"] == [
        "Protected holdout lineage is incomplete.",
        "Replay determinism remains intact.",
    ]
    assert "private_raw_payload" not in json.dumps(rows["robustness_guardian"])

    snap = brain_snapshot(tmp_path, remote_sync=status)
    assert snap["remote_sync"]["historical_context_status"] == "green"
    assert snap["remote_sync"]["historical_candidate_evidence_count"] == 0

    # Historical context is durable Brain evidence, but not a candidate.
    events = snap["events"]
    historical_events = [
        row for row in events
        if (row.get("details") or {}).get("foreign_historical_context") is True
    ]
    assert len(historical_events) == 4
    assert all((row.get("details") or {}).get("candidate_evidence_eligible") is False for row in historical_events)
    assert snap["candidates"] == []

    again = sync.sync_once()
    assert again["historical_context_ingested_total"] == 4
    snap2 = brain_snapshot(tmp_path, remote_sync=again)
    historical_events2 = [
        row for row in snap2["events"]
        if (row.get("details") or {}).get("foreign_historical_context") is True
    ]
    assert len(historical_events2) == 4


def test_remote_sync_rejects_historical_context_authority_escalation(tmp_path):
    historical = _historical_context_contract()
    historical["direct_candidate_evidence"] = True
    consumer = _consumer_contract(historical_context=historical)
    fixture = _fixture(_remote_event(), consumer=consumer)
    sync = BrainRemoteSync(
        tmp_path,
        interval_seconds=60,
        fetch_json=fixture["fetch_json"],
        fetch_bytes=fixture["fetch_bytes"],
    )
    status = sync.sync_once()
    assert status["status"] == "degraded"
    assert "historical context attempts authority escalation" in status["last_error"]
    assert status["ingested_total"] == 0


def test_remote_sync_rejects_historical_source_not_in_bounded_allowlist(tmp_path):
    historical = _historical_context_contract()
    historical["sources"][0]["summary_fields"].append("private_raw_payload")
    consumer = _consumer_contract(historical_context=historical)
    fixture = _fixture(_remote_event(), consumer=consumer)
    sync = BrainRemoteSync(
        tmp_path,
        interval_seconds=60,
        fetch_json=fixture["fetch_json"],
        fetch_bytes=fixture["fetch_bytes"],
    )
    status = sync.sync_once()
    assert status["status"] == "degraded"
    assert "historical context field allowlist mismatch" in status["last_error"]


def test_remote_sync_degrades_if_declared_historical_blob_is_substituted(tmp_path):
    consumer = _consumer_contract(historical_context=_historical_context_contract())
    docs = _historical_docs()
    fixture = _fixture(_remote_event(), consumer=consumer, historical_docs=docs)

    original_fetch_json = fixture["fetch_json"]
    def fetch_json(url):
        meta = original_fetch_json(url)
        if "robustness_guardian/latest.json" in url and isinstance(meta, dict):
            meta = dict(meta)
            meta["sha"] = "f" * 40
        return meta

    sync = BrainRemoteSync(
        tmp_path,
        interval_seconds=60,
        fetch_json=fetch_json,
        fetch_bytes=fixture["fetch_bytes"],
    )
    status = sync.sync_once()
    assert status["status"] == "degraded"
    assert status["historical_context_status"] == "degraded"
    assert "historical context Git blob SHA mismatch" in status["last_error"]

def test_remote_sync_rejects_packet_historical_artifact_id_substitution(tmp_path):
    packet = _peer_packet()
    packet["historical_artifacts"][0]["artifact_id"] = "0" * 64
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
    assert status["historical_packet_witness_status"] == "degraded"
    assert status["ingested_total"] == 1
    assert "historical artifact ID mismatch" in status["last_error"]


def test_remote_sync_rejects_packet_historical_source_blob_substitution(tmp_path):
    packet = _peer_packet()
    artifact = packet["historical_artifacts"][0]
    artifact["source_artifact_blob_sha"] = "0" * 40
    _rehash_historical_artifact(artifact)
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
    assert status["historical_packet_witness_status"] == "degraded"
    assert status["historical_packet_witness_count"] == 0
    assert status["ingested_total"] == 1
    assert "historical packet witness source blob mismatch" in status["last_error"]


def test_remote_sync_allows_live_historical_source_to_advance_after_packet_source(tmp_path):
    consumer = _consumer_contract(historical_context=_historical_context_contract())
    packet_docs = _historical_docs()
    live_docs = json.loads(json.dumps(packet_docs))
    live_docs["robustness_guardian"]["RUN_CORE"]["findings"].append(
        "new current-main observation after packet export"
    )
    fixture = _fixture(
        _remote_event(),
        consumer=consumer,
        historical_docs=live_docs,
        packet_historical_docs=packet_docs,
    )
    sync = BrainRemoteSync(
        tmp_path,
        interval_seconds=60,
        fetch_json=fixture["fetch_json"],
        fetch_bytes=fixture["fetch_bytes"],
        now_utc=fixture["now_utc"],
    )
    status = sync.sync_once()
    assert status["status"] == "green", status.get("last_error")
    assert status["historical_context_status"] == "green"
    assert status["historical_packet_witness_status"] == "green"
    assert status["historical_packet_live_advanced_count"] == 1
    assert status["historical_packet_same_as_live_count"] == 3
    witness = next(
        row for row in status["historical_packet_witnesses"]
        if row["id"] == "robustness_guardian"
    )
    assert witness["current_main_relation"] == "LIVE_SOURCE_ADVANCED"
    assert witness["source_artifact_blob_verified"] is True
    assert witness["current_main_blob_sha"] != witness["source_artifact_blob_sha"]


def test_remote_sync_rejects_historical_contract_without_blob_and_artifact_id_requirements(tmp_path):
    historical = _historical_context_contract()
    historical["source_artifact_blob_required"] = False
    consumer = _consumer_contract(historical_context=historical)
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
    assert "must require exact source artifact blobs" in status["last_error"]

def test_remote_sync_rejects_peer_lane_source_blob_substitution(tmp_path):
    packet = _peer_packet()
    packet["lanes"][0]["heartbeat_blob_sha"] = "0" * 40
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
    assert status["ingested_total"] == 1
    assert status["peer_lane_witness_verified_count"] == 0
    assert "peer lane source blob mismatch" in status["last_error"]


def test_remote_sync_rejects_peer_lane_state_that_disagrees_with_source_blobs(tmp_path):
    packet = _peer_packet()
    packet["lanes"][1]["run_id"] = "forged-flow-run"
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
    assert status["ingested_total"] == 1
    assert "peer lane source state mismatch: flow_microstructure:run_id" in status["last_error"]


def test_remote_sync_requires_lane_source_witness_contract(tmp_path):
    consumer = _consumer_contract()
    peer_contract = dict(consumer["peer_packet"])
    peer_contract["lane_source_witnesses_required"] = False
    consumer["peer_packet"] = peer_contract
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
    assert "peer lane source witnesses must be required" in status["last_error"]

def test_remote_sync_rejects_peer_source_contract_blob_substitution(tmp_path):
    packet = _peer_packet()
    packet["source_contract_blobs"]["agent_fabric"] = "0" * 40
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
    assert status["ingested_total"] == 1
    assert status["peer_source_contract_witness_status"] == "degraded"
    assert "peer source contract blob mismatch: agent_fabric" in status["last_error"]


def test_remote_sync_requires_source_contract_blob_witness_contract(tmp_path):
    consumer = _consumer_contract()
    peer_contract = dict(consumer["peer_packet"])
    peer_contract["source_contract_blob_witnesses_required"] = False
    consumer["peer_packet"] = peer_contract
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
    assert "source contract blob witnesses must be required" in status["last_error"]

def test_remote_sync_rejects_peer_lane_control_plane_attribution_substitution(tmp_path):
    packet = _peer_packet()
    packet["lanes"][1]["scheduler_id"] = "forged-scheduler"
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
    assert status["ingested_total"] == 1
    assert "peer lane control-plane binding mismatch: flow_microstructure:scheduler_id" in status["last_error"]


def test_remote_sync_rejects_peer_lane_agent_fabric_path_substitution(tmp_path):
    packet = _peer_packet()
    robustness = next(
        row for row in packet["lanes"] if row["name"] == "robustness_guardian"
    )
    robustness["heartbeat_path"] = "automation_intelligence/flow/heartbeat.json"
    robustness["heartbeat_blob_sha"] = _fixture_blob(
        _lane_source_docs()["automation_intelligence/flow/heartbeat.json"]
    )
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
    assert status["ingested_total"] == 1
    assert (
        "peer lane agent-fabric binding mismatch: robustness_guardian:heartbeat_path"
        in status["last_error"]
    )


def test_remote_sync_rejects_peer_control_plane_projection_drift(tmp_path):
    packet = _peer_packet()
    packet["control_plane"]["grace_minutes"] = 9
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
    assert status["ingested_total"] == 1
    assert "peer control-plane projection mismatch: grace_minutes" in status["last_error"]


def test_remote_sync_rejects_peer_mcp_projection_drift(tmp_path):
    packet = _peer_packet()
    packet["mcp_interface"]["ui_tab"] = "forged-tab"
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
    assert status["ingested_total"] == 1
    assert "peer MCP projection mismatch: ui_tab" in status["last_error"]

def test_remote_sync_rejects_packet_historical_summary_projection_substitution(tmp_path):
    packet = _peer_packet()
    artifact = packet["historical_artifacts"][0]
    artifact["summary"]["findings"].append("forged packet-only finding")
    _rehash_historical_artifact(artifact)
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
    assert status["ingested_total"] == 1
    assert status["historical_packet_projection_verified_count"] == 0
    assert "historical packet witness summary projection mismatch" in status["last_error"]


def test_remote_sync_rejects_packet_historical_lineage_projection_substitution(tmp_path):
    packet = _peer_packet()
    artifact = packet["historical_artifacts"][0]
    artifact["lineage"]["history_blob_sha"] = "f" * 40
    _rehash_historical_artifact(artifact)
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
    assert status["ingested_total"] == 1
    assert "historical packet witness lineage projection mismatch" in status["last_error"]


def test_remote_sync_rejects_packet_historical_evidence_projection_not_supported_by_source(tmp_path):
    packet_docs = _historical_docs()
    guardian = packet_docs["robustness_guardian"]
    guardian["RUN_CORE"]["findings"] = []
    guardian["RUN_CORE"]["built_changes"] = []
    guardian["RUN_CORE"]["NEXT"] = None
    packet = _peer_packet(
        historical_artifacts=_historical_packet_artifacts(packet_docs)
    )
    fixture = _fixture(
        _remote_event(),
        peer=packet,
        packet_historical_docs=packet_docs,
    )
    sync = BrainRemoteSync(
        tmp_path,
        interval_seconds=60,
        fetch_json=fixture["fetch_json"],
        fetch_bytes=fixture["fetch_bytes"],
        now_utc=fixture["now_utc"],
    )
    status = sync.sync_once()
    assert status["status"] == "degraded"
    assert status["ingested_total"] == 1
    assert "historical packet witness evidence projection mismatch" in status["last_error"]


@pytest.mark.parametrize("source_id,section,key,value", [
    ("robustness_guardian", "RUN_CORE", "execution_authorized", True),
    ("robustness_guardian", None, "trading_execution_authorized", True),
    ("robustness_guardian", "RUN_CORE", "trading_execution_authorized", True),
    ("flow_microstructure", None, "COLLECTION_ONLY", False),
])
def test_packet_source_projection_rejects_invalid_semantics(
    tmp_path, source_id, section, key, value,
):
    docs = _historical_docs()
    target = docs[source_id][section] if section else docs[source_id]
    target[key] = value
    packet = _peer_packet(historical_artifacts=_historical_packet_artifacts(docs))
    fixture = _fixture(_remote_event(), peer=packet, packet_historical_docs=docs)
    sync = BrainRemoteSync(tmp_path, interval_seconds=60,
                           fetch_json=fixture["fetch_json"],
                           fetch_bytes=fixture["fetch_bytes"],
                           now_utc=fixture["now_utc"])
    status = sync.sync_once()
    assert status["status"] == "degraded"
    assert status["historical_packet_projection_verified_count"] == 0
    assert status["peer_packet_status"] == "degraded"
    assert status["ingested_total"] == 1
    assert status["execution_authorized"] is False


def test_remote_sync_requires_historical_packet_projection_contract(tmp_path):
    historical = _historical_context_contract()
    historical["packet_projection_verification_required"] = False
    consumer = _consumer_contract(historical_context=historical)
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
    assert "must require packet projection verification" in status["last_error"]


def test_remote_sync_validates_verified_prior_packet_acknowledgement(tmp_path):
    packet = _peer_packet(canonical_acceptance=_verified_roundtrip_ack())
    fixture = _fixture(_remote_event(), peer=packet)
    sync = BrainRemoteSync(
        tmp_path,
        interval_seconds=60,
        fetch_json=fixture["fetch_json"],
        fetch_bytes=fixture["fetch_bytes"],
        now_utc=fixture["now_utc"],
    )
    status = sync.sync_once()
    assert status["status"] == "green"
    assert status["peer_roundtrip_ack_status"] == "VERIFIED_PRIOR_PACKET"
    ack = status["peer_roundtrip_ack"]
    assert ack["accepted_by_repository"] == "reppiks490/Icarus"
    assert ack["accepted_peer_packet_id"] == "2" * 64
    assert ack["accepted_peer_source_commit"] == "4" * 40
    assert ack["peer_source_contract_witness_count"] == 3
    assert ack["peer_lane_contract_binding_verified_count"] == 3
    assert ack["execution_authorized"] is False
    assert status["execution_authorized"] is False
    assert status["production_decision_authorized"] is False


def test_remote_sync_rejects_roundtrip_ack_authority_escalation(tmp_path):
    packet = _peer_packet(
        canonical_acceptance=_verified_roundtrip_ack(execution_authorized=True)
    )
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
    assert status["ingested_total"] == 1
    assert status["peer_roundtrip_ack_status"] == "degraded"
    assert "canonical acceptance attempts authority escalation" in status["last_error"]


def test_remote_sync_requires_canonical_acceptance_contract_semantics(tmp_path):
    consumer = _consumer_contract()
    acceptance = dict(consumer["canonical_acceptance"])
    semantics = dict(acceptance["semantics"])
    semantics["automatic_execution_authority"] = True
    acceptance["semantics"] = semantics
    consumer["canonical_acceptance"] = acceptance
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
    assert "canonical acceptance attempts authority escalation" in status["last_error"]
