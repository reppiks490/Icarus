"""Verified GitHub -> Adaptive Brain ingest for the five custom ICARUS agents.

Cloud automations cannot directly reach the operator's localhost engine. They persist
material results as immutable repository-native MCP events. This background sync
pulls those events into the local Adaptive Brain journal with Git-blob verification,
source allowlisting, idempotence, and no authority escalation.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Callable, Mapping
from urllib.request import Request, urlopen

from .brain import record_brain_event

REMOTE_REPOSITORY = "reppiks490/Icarus-engine"
REMOTE_REF = "main"
REMOTE_ROOT = "automation_intelligence/mcp_interface/events"
REMOTE_CONSUMER_CONTRACT = "automation_intelligence/mcp_interface/icarus_consumer_contract.json"
REMOTE_PRODUCER_CONTRACT = "automation_intelligence/mcp_interface/contract.json"
REMOTE_PEER_PACKET = "automation_intelligence/interrepo/latest.json"
_REMOTE_API = f"https://api.github.com/repos/{REMOTE_REPOSITORY}/contents/{REMOTE_ROOT}?ref={REMOTE_REF}"
_REMOTE_CONSUMER_CONTRACT_API = (
    f"https://api.github.com/repos/{REMOTE_REPOSITORY}/contents/{REMOTE_CONSUMER_CONTRACT}?ref={REMOTE_REF}"
)
_REMOTE_PRODUCER_CONTRACT_API = (
    f"https://api.github.com/repos/{REMOTE_REPOSITORY}/contents/{REMOTE_PRODUCER_CONTRACT}?ref={REMOTE_REF}"
)
_REMOTE_PEER_PACKET_API = (
    f"https://api.github.com/repos/{REMOTE_REPOSITORY}/contents/{REMOTE_PEER_PACKET}?ref={REMOTE_REF}"
)

SOURCE_TO_AGENT = {
    "OMEGA_AUTOMATION": "omega",
    "MACRO_AUTOMATION": "macro",
    "FLOW_AUTOMATION": "flow",
    "AION_AUTOMATION": "aion",
    "DAEDALUS_AUTOMATION": "daedalus",
}

_SUBSYSTEM_ALIASES = {
    "aegis": "aegis",
    "aion": "aion",
    "argus": "argus",
    "ascension": "ascension",
    "athena": "athena",
    "daedalus": "daedalus",
    "helios": "helios-prime",
    "helios_prime": "helios-prime",
    "infrastructure": "infrastructure",
    "janus": "janus",
    "nexus": "nexus",
    "oracle": "oracle",
    "prometheus": "prometheus",
    "supermesh_x": "supermesh-x",
    "supermesh-x": "supermesh-x",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


def _is_sha(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 40 and all(c in "0123456789abcdef" for c in value.lower())


def _remote_compare_api(source_commit: str) -> str:
    source = str(source_commit or "").strip().lower()
    if not _is_sha(source):
        raise ValueError("peer source commit must be an exact 40-character Git SHA")
    return f"https://api.github.com/repos/{REMOTE_REPOSITORY}/compare/{source}...{REMOTE_REF}"


def _remote_artifact_api(path: str, source_commit: str) -> str:
    source = str(source_commit or "").strip().lower()
    candidate = str(path or "").strip()
    if not _is_sha(source):
        raise ValueError("peer artifact source commit must be an exact 40-character Git SHA")
    if (
        not candidate.startswith("automation_intelligence/")
        or candidate.startswith("/")
        or ".." in candidate.split("/")
    ):
        raise ValueError("peer artifact path is outside the allowed automation_intelligence root")
    return (
        f"https://api.github.com/repos/{REMOTE_REPOSITORY}/contents/"
        f"{candidate}?ref={source}"
    )


def _state_path(base_dir: str | os.PathLike[str]) -> Path:
    return Path(base_dir) / "audit" / "brain_remote_sync.json"


def _default_state(interval_seconds: int) -> dict[str, Any]:
    return {
        "schema_version": "icarus-brain-remote-sync-v1",
        "enabled": True,
        "repository": REMOTE_REPOSITORY,
        "ref": REMOTE_REF,
        "root": REMOTE_ROOT,
        "interval_seconds": interval_seconds,
        "status": "not_started",
        "last_attempt_at": None,
        "last_success_at": None,
        "last_error": None,
        "ingested_total": 0,
        "ignored_total": 0,
        "rejected_total": 0,
        "last_ingested": [],
        "processed_blob_shas": [],
        "peer_packet_status": "not_started",
        "peer_packet_blob_sha": None,
        "peer_packet_id": None,
        "peer_source_commit": None,
        "peer_source_commit_verified": False,
        "peer_source_commit_relation": None,
        "peer_observed_at": None,
        "peer_packet_fresh": False,
        "peer_packet_age_seconds": None,
        "peer_lanes": [],
        "peer_substantive_lane_count": 0,
        "peer_durability_only_lane_count": 0,
        "peer_historical_artifacts": [],
        "peer_historical_context_count": 0,
        "peer_historical_collection_count": 0,
        "peer_historical_source_blob_verified_count": 0,
        "consumer_contract_blob_sha": None,
        "producer_contract_blob_sha": None,
        "truth_contract": {
            "federation_schema": None,
            "producer_contract_schema": None,
            "event_records": "RESEARCH_OBSERVABILITY_ONLY",
            "durability_receipts_are_substantive_evidence": False,
            "remote_status_is_production_decision": False,
            "raw_owner_data_transfer": False,
            "automatic_model_promotion": False,
            "production_decision_authorized": False,
            "automatic_execution_authority": False,
            "strict_event_contract": False,
            "legacy_exception_count": 0,
            "peer_packet_schema": None,
            "peer_packet_authority": "OBSERVE",
            "peer_historical_context_mode": None,
            "peer_historical_context_source_count": 0,
            "peer_historical_context_candidate_evidence": False,
            "peer_historical_context_execution_authorized": False,
            "peer_historical_source_blob_required": True,
            "peer_historical_artifact_id_sha256_required": True,
        },
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


def _read_state(base_dir: str | os.PathLike[str], interval_seconds: int) -> dict[str, Any]:
    path = _state_path(base_dir)
    state = _default_state(interval_seconds)
    if not path.is_file():
        return state
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        state["status"] = "degraded"
        state["last_error"] = "local sync state is unreadable; remote events will be safely replayed idempotently"
        return state
    if not isinstance(raw, dict) or raw.get("execution_authorized") is not False:
        state["status"] = "degraded"
        state["last_error"] = "local sync state failed authority validation"
        return state
    state.update(raw)
    state["interval_seconds"] = interval_seconds
    state["execution_authorized"] = False
    state["production_decision_authorized"] = False
    return state


def _write_state(base_dir: str | os.PathLike[str], state: Mapping[str, Any]) -> None:
    path = _state_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(state)
    payload["execution_authorized"] = False
    payload["production_decision_authorized"] = False
    raw = json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n"
    with NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, prefix=".brain-sync-", delete=False) as fh:
        tmp = Path(fh.name)
        fh.write(raw)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _compact_evidence(payload: Mapping[str, Any], path: str, blob_sha: str) -> list[str]:
    out = [
        f"remote_repository:{REMOTE_REPOSITORY}",
        f"remote_path:{path}",
        f"git_blob_sha:{blob_sha}",
        f"source:{payload.get('source', '')}",
        f"category:{payload.get('category', '')}",
    ]
    evidence = payload.get("evidence")
    if isinstance(evidence, Mapping):
        for key, value in list(evidence.items())[:16]:
            out.append(f"{key}:{str(value)[:620]}")
    elif isinstance(evidence, list):
        for value in evidence[:16]:
            out.append(str(value)[:680])
    elif isinstance(evidence, str) and evidence.strip():
        out.append(evidence[:680])
    return out[:32]


def _event_details(payload: Mapping[str, Any], path: str, blob_sha: str) -> dict[str, Any]:
    keep = (
        "category",
        "event_time_utc",
        "retrieval_time_utc",
        "at_utc",
        "status",
        "severity",
        "surface",
        "regime_implication",
        "next_decisive_check",
        "data_gaps",
        "conflicts",
        "paths",
        "persistence_authority",
    )
    details = {key: payload[key] for key in keep if key in payload}
    details.update(
        {
            "remote_repository": REMOTE_REPOSITORY,
            "remote_ref": REMOTE_REF,
            "remote_path": path,
            "remote_blob_sha": blob_sha,
        }
    )
    return details


def _summary(payload: Mapping[str, Any]) -> str:
    for key in ("net_new_delta", "summary", "finding", "detail"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:2200]
    return "Verified custom-agent repository event ingested; no summary field was supplied."


def _normalize_status(value: Any) -> str:
    status = str(value or "observed").strip().lower()
    aliases = {
        "implemented": "verified",
        "useful": "observed",
        "run_persisted": "active",
        "no_material_delta": "observed",
        "warning": "degraded",
        "error": "blocked",
    }
    status = aliases.get(status, status)
    allowed = {"observed", "active", "verified", "qualified", "rejected", "blocked", "degraded", "retired", "unverified"}
    return status if status in allowed else "observed"


def _normalize_federation_contract(
    consumer: Mapping[str, Any],
    producer: Mapping[str, Any],
    blobs: Mapping[str, str],
) -> dict[str, Any]:
    """Validate the producer/consumer handshake before any remote event is trusted."""
    if consumer.get("execution_authorized") is not False:
        raise ValueError("consumer contract must preserve execution_authorized=false")
    if consumer.get("production_decision_authorized") is not False:
        raise ValueError("consumer contract must preserve production_decision_authorized=false")
    if consumer.get("schema_version") != "icarus-engine-brain-federation-v1":
        raise ValueError("unsupported Icarus-engine Brain federation contract")
    if (
        consumer.get("producer_repository") != REMOTE_REPOSITORY
        or consumer.get("producer_ref") != REMOTE_REF
        or consumer.get("consumer_repository") != "reppiks490/Icarus"
    ):
        raise ValueError("Icarus-engine Brain federation identity mismatch")
    if consumer.get("event_root") != REMOTE_ROOT:
        raise ValueError("Icarus-engine Brain federation event root mismatch")
    if consumer.get("event_schema") != "icarus-mcp-event-v1":
        raise ValueError("Icarus-engine Brain federation event schema mismatch")
    if consumer.get("producer_contract") != REMOTE_PRODUCER_CONTRACT:
        raise ValueError("Icarus-engine Brain federation producer contract path mismatch")
    if consumer.get("producer_contract_schema") != "icarus-mcp-interface-contract-v1":
        raise ValueError("Icarus-engine Brain federation producer contract schema mismatch")

    sources = consumer.get("accepted_sources")
    if not isinstance(sources, list) or set(sources) != set(SOURCE_TO_AGENT):
        raise ValueError("Icarus-engine Brain federation source allowlist mismatch")
    categories = consumer.get("accepted_categories")
    expected_categories = {"REPAIR", "AUDIT", "EVOLUTION", "INTEGRATION"}
    if not isinstance(categories, list) or set(categories) != expected_categories:
        raise ValueError("Icarus-engine Brain federation category allowlist mismatch")

    semantics = consumer.get("semantics")
    if not isinstance(semantics, Mapping):
        raise ValueError("Icarus-engine Brain federation semantics are missing")
    if semantics.get("event_records") != "RESEARCH_OBSERVABILITY_ONLY":
        raise ValueError("Icarus-engine Brain federation changed event authority")
    for key in (
        "durability_receipts_are_substantive_evidence",
        "remote_status_is_production_decision",
        "raw_owner_data_transfer",
        "automatic_model_promotion",
        "production_decision_authorized",
        "automatic_execution_authority",
    ):
        if semantics.get(key) is not False:
            raise ValueError(f"Icarus-engine Brain federation attempts authority escalation: {key}")

    peer_packet = consumer.get("peer_packet")
    if not isinstance(peer_packet, Mapping):
        raise ValueError("Icarus-engine Brain federation peer packet contract is missing")
    if peer_packet.get("path") != REMOTE_PEER_PACKET:
        raise ValueError("Icarus-engine Brain federation peer packet path mismatch")
    if peer_packet.get("schema_version") != "icarus-peer-intelligence-packet-v1":
        raise ValueError("Icarus-engine Brain federation peer packet schema mismatch")
    if peer_packet.get("authority") != "OBSERVE":
        raise ValueError("Icarus-engine Brain federation peer packet authority must remain OBSERVE")
    if peer_packet.get("source_commit_required") is not True:
        raise ValueError("Icarus-engine Brain federation peer packet must require source commit")
    if peer_packet.get("git_blob_verification_required") is not True:
        raise ValueError("Icarus-engine Brain federation peer packet must require Git blob verification")
    if peer_packet.get("required_for_event_ingest") is not False:
        raise ValueError("peer packet must not become an authority gate for independent event ingest")
    peer_semantics = peer_packet.get("semantics")
    if not isinstance(peer_semantics, Mapping):
        raise ValueError("Icarus-engine Brain federation peer packet semantics are missing")
    for key in (
        "lane_state_is_foreign_evidence",
        "durability_only_is_not_substantive_research_evidence",
        "remote_sibling_state_is_never_inferred",
    ):
        if peer_semantics.get(key) is not True:
            raise ValueError(f"Icarus-engine Brain federation peer packet truth rule missing: {key}")
    for key in (
        "automatic_model_promotion",
        "production_decision_authorized",
        "automatic_execution_authority",
    ):
        if peer_semantics.get(key) is not False:
            raise ValueError(f"Icarus-engine Brain federation peer packet attempts authority escalation: {key}")
    if peer_semantics.get("stale_packet_is_current_state") is not False:
        raise ValueError("Icarus-engine Brain federation stale packet semantics must fail closed")
    if peer_packet.get("freshness_required") is not True:
        raise ValueError("Icarus-engine Brain federation peer packet freshness must be required")
    if peer_packet.get("max_age_seconds") != 1800:
        raise ValueError("Icarus-engine Brain federation peer packet max age mismatch")
    if peer_packet.get("max_future_skew_seconds") != 300:
        raise ValueError("Icarus-engine Brain federation peer packet future-skew bound mismatch")

    historical_context = consumer.get("historical_context")
    if not isinstance(historical_context, Mapping):
        raise ValueError("Icarus-engine Brain federation historical context contract is missing")
    if historical_context.get("mode") != "RESEARCH_CONTEXT_ONLY":
        raise ValueError("Icarus-engine historical context mode must remain RESEARCH_CONTEXT_ONLY")
    if historical_context.get("source_artifact_blob_required") is not True:
        raise ValueError("Icarus-engine historical context must require exact source artifact blobs")
    if historical_context.get("artifact_id_sha256_required") is not True:
        raise ValueError("Icarus-engine historical context must require SHA-256 artifact IDs")
    for key in (
        "direct_candidate_evidence",
        "automatic_candidate_creation",
        "automatic_model_promotion",
        "execution_authorized",
        "production_decision_authorized",
    ):
        if historical_context.get(key) is not False:
            raise ValueError(f"Icarus-engine historical context attempts authority escalation: {key}")
    historical_sources = historical_context.get("sources")
    if not isinstance(historical_sources, list) or not historical_sources:
        raise ValueError("Icarus-engine historical context sources are missing")
    historical_ids: set[str] = set()
    historical_paths: set[str] = set()
    for index, source in enumerate(historical_sources):
        if not isinstance(source, Mapping):
            raise ValueError(f"Icarus-engine historical context source {index} is not an object")
        source_id = str(source.get("id") or "").strip()
        path = str(source.get("path") or "").strip()
        if not source_id or source_id in historical_ids:
            raise ValueError("Icarus-engine historical context source IDs must be unique")
        if not path or path in historical_paths:
            raise ValueError("Icarus-engine historical context source paths must be unique")
        historical_ids.add(source_id)
        historical_paths.add(path)
        if source.get("research_context_eligible") is not True:
            raise ValueError(f"Icarus-engine historical source {source_id} must be research-context eligible")
        if source.get("candidate_evidence_eligible") is not False:
            raise ValueError(f"Icarus-engine historical source {source_id} cannot be candidate evidence")
        if source.get("execution_authorized") is not False:
            raise ValueError(f"Icarus-engine historical source {source_id} attempts execution authority")
        if source.get("evidence_status") not in {
            "HISTORICAL_RESEARCH_EVIDENCE",
            "HISTORICAL_COLLECTION_EVIDENCE",
        }:
            raise ValueError(f"Icarus-engine historical source {source_id} has unsupported evidence status")
        if type(source.get("collection_only")) is not bool:
            raise ValueError(f"Icarus-engine historical source {source_id} collection_only must be Boolean")

    historical_truth = historical_context.get("truth_contract")
    if not isinstance(historical_truth, Mapping):
        raise ValueError("Icarus-engine historical context truth contract is missing")
    for key in (
        "foreign_repository_state_is_context_not_native_truth",
        "historical_context_never_bypasses_foundry",
        "historical_context_never_bypasses_evaluator",
        "historical_context_never_grants_shadow_qualification",
        "historical_context_never_grants_execution_authority",
    ):
        if historical_truth.get(key) is not True:
            raise ValueError(f"Icarus-engine historical context truth invariant failed: {key}")

    event_validation = consumer.get("event_validation")
    if not isinstance(event_validation, Mapping):
        raise ValueError("Icarus-engine Brain federation event validation policy is missing")
    if event_validation.get("required_fields_source") != (
        "automation_intelligence/mcp_interface/contract.json#required_fields"
    ):
        raise ValueError("Icarus-engine Brain federation required-fields source mismatch")
    if event_validation.get("strict_v1_required_fields") is not True:
        raise ValueError("Icarus-engine Brain federation must strictly enforce v1 required fields")
    legacy_blobs = event_validation.get("legacy_relaxed_blob_shas")
    if not isinstance(legacy_blobs, list) or any(not _is_sha(value) for value in legacy_blobs):
        raise ValueError("Icarus-engine Brain federation legacy blob allowlist is invalid")
    if len(set(str(value).lower() for value in legacy_blobs)) != len(legacy_blobs):
        raise ValueError("Icarus-engine Brain federation legacy blob allowlist contains duplicates")
    legacy_rule = str(event_validation.get("legacy_rule") or "")
    if "No future blob inherits this exception" not in legacy_rule:
        raise ValueError("Icarus-engine Brain federation legacy exception rule is not fail-closed")

    if producer.get("schema_version") != "icarus-mcp-interface-contract-v1":
        raise ValueError("unsupported producer MCP interface contract")
    if producer.get("event_root") != REMOTE_ROOT:
        raise ValueError("producer MCP event root disagrees with federation contract")
    if producer.get("event_schema") != consumer.get("event_schema"):
        raise ValueError("producer MCP event schema disagrees with federation contract")
    producer_categories = producer.get("required_categories")
    if not isinstance(producer_categories, list) or set(producer_categories) != expected_categories:
        raise ValueError("producer MCP categories disagree with federation contract")
    required_fields = producer.get("required_fields")
    expected_required_fields = {
        "event_id", "at_utc", "category", "status", "severity", "summary",
        "surface", "source", "paths", "evidence", "execution_authorized",
    }
    if not isinstance(required_fields, list) or set(required_fields) != expected_required_fields:
        raise ValueError("producer MCP required event envelope disagrees with federation contract")
    if producer.get("trading_execution_authorized") is not False:
        raise ValueError("producer MCP contract attempts trading authority escalation")

    consumer_blob = str(blobs.get("consumer") or "").lower()
    producer_blob = str(blobs.get("producer") or "").lower()
    if not _is_sha(consumer_blob) or not _is_sha(producer_blob):
        raise ValueError("federation contract Git blob identity is invalid")

    return {
        "consumer_contract_blob_sha": consumer_blob,
        "producer_contract_blob_sha": producer_blob,
        "truth_contract": {
            "federation_schema": consumer.get("schema_version"),
            "producer_contract_schema": producer.get("schema_version"),
            "event_records": semantics.get("event_records"),
            "durability_receipts_are_substantive_evidence": False,
            "remote_status_is_production_decision": False,
            "raw_owner_data_transfer": False,
            "automatic_model_promotion": False,
            "production_decision_authorized": False,
            "automatic_execution_authority": False,
            "strict_event_contract": True,
            "legacy_exception_count": len(legacy_blobs),
            "peer_packet_schema": peer_packet.get("schema_version"),
            "peer_packet_authority": peer_packet.get("authority"),
            "peer_packet_freshness_required": True,
            "peer_packet_max_age_seconds": 1800,
            "peer_packet_max_future_skew_seconds": 300,
            "peer_historical_context_mode": historical_context.get("mode"),
            "peer_historical_context_source_count": len(historical_sources),
            "peer_historical_context_candidate_evidence": False,
            "peer_historical_context_execution_authorized": False,
        },
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


def _normalize_peer_packet(
    packet: Mapping[str, Any],
    *,
    blob_sha: str,
    historical_context_contract: Mapping[str, Any],
) -> dict[str, Any]:
    if packet.get("schema_version") != "icarus-peer-intelligence-packet-v1":
        raise ValueError("unsupported Icarus-engine peer packet schema")
    if packet.get("source_repository") != REMOTE_REPOSITORY:
        raise ValueError("Icarus-engine peer packet repository identity mismatch")
    source_commit = str(packet.get("source_commit") or "").lower()
    if not _is_sha(source_commit):
        raise ValueError("Icarus-engine peer packet source_commit is invalid")
    observed_at = packet.get("observed_at")
    if not isinstance(observed_at, str) or not observed_at.strip():
        raise ValueError("Icarus-engine peer packet observed_at is missing")
    try:
        parsed = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    except ValueError as ex:
        raise ValueError("Icarus-engine peer packet observed_at is invalid") from ex
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("Icarus-engine peer packet observed_at must be timezone-aware")

    for key in ("execution_authorized", "production_decision_authorized", "peer_write_authorized"):
        if packet.get(key) is not False:
            raise ValueError(f"Icarus-engine peer packet attempts authority escalation: {key}")

    source_contracts = packet.get("source_contracts")
    expected_contracts = {
        "control_plane": "automation_intelligence/restored_five_native/control_plane.json",
        "agent_fabric": "automation_intelligence/agent_fabric/manifest.json",
        "mcp_interface": "automation_intelligence/mcp_interface/contract.json",
    }
    if not isinstance(source_contracts, Mapping) or dict(source_contracts) != expected_contracts:
        raise ValueError("Icarus-engine peer packet source contracts mismatch")

    control_plane = packet.get("control_plane")
    if not isinstance(control_plane, Mapping):
        raise ValueError("Icarus-engine peer packet control plane is missing")
    if control_plane.get("schema_version") != "restored-five-native-control-v1":
        raise ValueError("Icarus-engine peer packet control-plane schema mismatch")
    if control_plane.get("control_plane_id") != "restored-five-native-liveness-v1":
        raise ValueError("Icarus-engine peer packet control-plane identity mismatch")
    if control_plane.get("timezone") != "America/Chicago":
        raise ValueError("Icarus-engine peer packet control-plane timezone mismatch")

    mcp_interface = packet.get("mcp_interface")
    if not isinstance(mcp_interface, Mapping):
        raise ValueError("Icarus-engine peer packet MCP interface is missing")
    if mcp_interface.get("schema_version") != "icarus-mcp-interface-contract-v1":
        raise ValueError("Icarus-engine peer packet MCP interface schema mismatch")
    if mcp_interface.get("event_root") != REMOTE_ROOT:
        raise ValueError("Icarus-engine peer packet MCP event root mismatch")
    if mcp_interface.get("trading_execution_authorized") is not False:
        raise ValueError("Icarus-engine peer packet MCP interface attempts trading authority")

    truth = packet.get("truth_contract")
    if not isinstance(truth, Mapping):
        raise ValueError("Icarus-engine peer packet truth contract is missing")
    for key in (
        "foreign_repository_state_is_evidence_not_native_truth",
        "durability_receipt_is_not_substantive_worker_evidence",
        "remote_sibling_state_is_never_inferred",
        "exact_source_commit_required",
        "execution_authority_never_transfers_between_repositories",
        "historical_context_never_bypasses_foundry_or_evaluator",
    ):
        if truth.get(key) is not True:
            raise ValueError(f"Icarus-engine peer packet truth invariant failed: {key}")

    claimed_id = str(packet.get("packet_id") or "").lower()
    if len(claimed_id) != 64 or any(ch not in "0123456789abcdef" for ch in claimed_id):
        raise ValueError("Icarus-engine peer packet_id is invalid")
    unsigned = dict(packet)
    unsigned.pop("packet_id", None)
    computed_id = hashlib.sha256(
        json.dumps(
            unsigned,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()
    if claimed_id != computed_id:
        raise ValueError("Icarus-engine peer packet_id mismatch")

    lanes_raw = packet.get("lanes")
    if not isinstance(lanes_raw, list):
        raise ValueError("Icarus-engine peer packet lanes must be an array")
    allowed_status = {
        "UNMEASURED",
        "REMOTE_PEER_UNREAD",
        "UNAVAILABLE",
        "DURABILITY_ONLY",
        "PERSISTED_WORKER_EVIDENCE",
        "PERSISTED_UNCLASSIFIED",
        "INCOMPLETE_OR_UNVERIFIED",
    }
    lanes: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw in enumerate(lanes_raw):
        if not isinstance(raw, Mapping):
            raise ValueError(f"Icarus-engine peer lane {index} is not an object")
        name = str(raw.get("name") or "").strip()
        if not name or name in seen:
            raise ValueError("Icarus-engine peer lane names must be non-empty and unique")
        seen.add(name)
        status = str(raw.get("evidence_status") or "").strip().upper()
        if status not in allowed_status:
            raise ValueError(f"Icarus-engine peer lane {name} has unsupported evidence status")
        worker_repository = str(raw.get("worker_repository") or "").strip()
        if not worker_repository:
            raise ValueError(f"Icarus-engine peer lane {name} worker repository is missing")
        if worker_repository != REMOTE_REPOSITORY and status != "REMOTE_PEER_UNREAD":
            raise ValueError(
                f"Icarus-engine peer lane {name} invents state for a foreign sibling repository"
            )
        if raw.get("execution_authorized") is not False:
            raise ValueError(f"Icarus-engine peer lane {name} attempts execution authority")
        substantive = raw.get("substantive_research_evidence")
        if type(substantive) is not bool:
            raise ValueError(f"Icarus-engine peer lane {name} substantive flag must be Boolean")
        if substantive and (
            status != "PERSISTED_WORKER_EVIDENCE"
            or raw.get("worker_execution_observed") is not True
        ):
            raise ValueError(
                f"Icarus-engine peer lane {name} claims substantive evidence without observed worker evidence"
            )
        if status in {"DURABILITY_ONLY", "REMOTE_PEER_UNREAD", "UNAVAILABLE"} and substantive:
            raise ValueError(
                f"Icarus-engine peer lane {name} conflates durability/unavailable state with substantive evidence"
            )
        lanes.append({
            "name": name,
            "title": raw.get("title"),
            "scheduler_id": raw.get("scheduler_id"),
            "run_id": raw.get("run_id"),
            "run_status": raw.get("run_status"),
            "worker_repository": worker_repository,
            "evidence_status": status,
            "worker_execution_observed": raw.get("worker_execution_observed"),
            "substantive_research_evidence": substantive,
            "execution_authorized": False,
        })

    source_rows = historical_context_contract.get("sources")
    if not isinstance(source_rows, list):
        raise ValueError("Icarus-engine peer historical context sources are unavailable")
    source_by_id = {
        str(source.get("id") or "").strip(): source
        for source in source_rows
        if isinstance(source, Mapping)
    }

    historical_raw = packet.get("historical_artifacts")
    if not isinstance(historical_raw, list):
        raise ValueError("Icarus-engine peer historical artifacts must be an array")
    historical_artifacts: list[dict[str, Any]] = []
    seen_artifact_ids: set[str] = set()
    seen_historical_lanes: set[str] = set()
    for index, raw in enumerate(historical_raw):
        if not isinstance(raw, Mapping):
            raise ValueError(f"Icarus-engine peer historical artifact {index} is not an object")
        lane = str(raw.get("lane") or "").strip()
        source = source_by_id.get(lane)
        if source is None:
            raise ValueError(f"Icarus-engine peer historical artifact lane is undeclared: {lane}")
        if lane in seen_historical_lanes:
            raise ValueError(f"Icarus-engine peer historical artifact lane is duplicated: {lane}")
        seen_historical_lanes.add(lane)

        if raw.get("artifact_kind") != "HISTORICAL_LATEST":
            raise ValueError(f"Icarus-engine peer historical artifact {lane} has unsupported kind")
        artifact_path = str(raw.get("path") or "")
        if artifact_path != str(source.get("path") or ""):
            raise ValueError(f"Icarus-engine peer historical artifact {lane} path mismatch")
        _remote_artifact_api(artifact_path, source_commit)
        source_artifact_blob_sha = str(raw.get("source_artifact_blob_sha") or "").lower()
        if not _is_sha(source_artifact_blob_sha):
            raise ValueError(
                f"Icarus-engine peer historical artifact {lane} source artifact blob is invalid"
            )
        if raw.get("evidence_status") != source.get("evidence_status"):
            raise ValueError(f"Icarus-engine peer historical artifact {lane} evidence status mismatch")
        if raw.get("research_context_eligible") is not True:
            raise ValueError(f"Icarus-engine peer historical artifact {lane} is not research-context eligible")
        if raw.get("candidate_evidence_eligible") is not False:
            raise ValueError(f"Icarus-engine peer historical artifact {lane} attempts candidate-evidence promotion")
        if raw.get("execution_authorized") is not False:
            raise ValueError(f"Icarus-engine peer historical artifact {lane} attempts execution authority")
        if raw.get("run_status") != "RUN_PERSISTED":
            raise ValueError(f"Icarus-engine peer historical artifact {lane} is not durably persisted")
        run_id = str(raw.get("run_id") or "").strip()
        if not run_id:
            raise ValueError(f"Icarus-engine peer historical artifact {lane} run_id is missing")

        artifact_id = str(raw.get("artifact_id") or "").lower()
        if len(artifact_id) != 64 or any(ch not in "0123456789abcdef" for ch in artifact_id):
            raise ValueError(f"Icarus-engine peer historical artifact {lane} artifact_id is invalid")
        if artifact_id in seen_artifact_ids:
            raise ValueError("Icarus-engine peer historical artifact IDs must be unique")
        seen_artifact_ids.add(artifact_id)
        unsigned_artifact = dict(raw)
        unsigned_artifact.pop("artifact_id", None)
        computed_artifact_id = hashlib.sha256(
            json.dumps(
                unsigned_artifact,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()
        if artifact_id != computed_artifact_id:
            raise ValueError(f"Icarus-engine peer historical artifact {lane} artifact_id mismatch")

        lineage = raw.get("lineage")
        if not isinstance(lineage, Mapping):
            raise ValueError(f"Icarus-engine peer historical artifact {lane} lineage is missing")
        history_blob_sha = str(lineage.get("history_blob_sha") or "").lower()
        if not _is_sha(history_blob_sha):
            raise ValueError(f"Icarus-engine peer historical artifact {lane} history blob is invalid")
        for key in ("base_main_sha", "final_main_sha", "ledger_blob_sha"):
            value = lineage.get(key)
            if value is not None and not _is_sha(str(value).lower()):
                raise ValueError(f"Icarus-engine peer historical artifact {lane} {key} is invalid")
        run_core_sha256 = lineage.get("run_core_sha256")
        collection_only = bool(source.get("collection_only"))
        if not collection_only:
            run_core = str(run_core_sha256 or "").lower()
            if len(run_core) != 64 or any(ch not in "0123456789abcdef" for ch in run_core):
                raise ValueError(
                    f"Icarus-engine peer historical artifact {lane} research run-core hash is invalid"
                )
        elif run_core_sha256 is not None:
            run_core = str(run_core_sha256).lower()
            if len(run_core) != 64 or any(ch not in "0123456789abcdef" for ch in run_core):
                raise ValueError(
                    f"Icarus-engine peer historical artifact {lane} collection run-core hash is invalid"
                )

        summary = raw.get("summary")
        if not isinstance(summary, Mapping):
            raise ValueError(f"Icarus-engine peer historical artifact {lane} summary is missing")
        historical_artifacts.append({
            "artifact_id": artifact_id,
            "lane": lane,
            "artifact_kind": "HISTORICAL_LATEST",
            "path": artifact_path,
            "source_artifact_blob_sha": source_artifact_blob_sha,
            "source_artifact_blob_verified": False,
            "run_id": run_id,
            "run_status": "RUN_PERSISTED",
            "evidence_status": str(raw.get("evidence_status")),
            "research_context_eligible": True,
            "candidate_evidence_eligible": False,
            "collection_only": collection_only,
            "summary": dict(summary),
            "lineage": {
                "base_main_sha": lineage.get("base_main_sha"),
                "final_main_sha": lineage.get("final_main_sha"),
                "run_core_sha256": lineage.get("run_core_sha256"),
                "history_blob_sha": history_blob_sha,
                "ledger_blob_sha": lineage.get("ledger_blob_sha"),
                "history_mode": lineage.get("history_mode"),
            },
            "execution_authorized": False,
        })

    peer_blob = str(blob_sha or "").lower()
    if not _is_sha(peer_blob):
        raise ValueError("Icarus-engine peer packet Git blob identity is invalid")
    return {
        "peer_packet_status": "green",
        "peer_packet_blob_sha": peer_blob,
        "peer_packet_id": claimed_id,
        "peer_source_commit": source_commit,
        "peer_observed_at": parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "peer_lanes": lanes,
        "peer_substantive_lane_count": sum(
            1 for lane in lanes if lane["substantive_research_evidence"]
        ),
        "peer_durability_only_lane_count": sum(
            1 for lane in lanes if lane["evidence_status"] == "DURABILITY_ONLY"
        ),
        "peer_historical_artifacts": historical_artifacts,
        "peer_historical_context_count": sum(
            1 for artifact in historical_artifacts if not artifact["collection_only"]
        ),
        "peer_historical_collection_count": sum(
            1 for artifact in historical_artifacts if artifact["collection_only"]
        ),
    }


class BrainRemoteSync:
    """Poll repository-native custom-agent events into the local brain journal."""

    def __init__(
        self,
        base_dir: str | os.PathLike[str],
        *,
        interval_seconds: int | None = None,
        fetch_json: Callable[[str], Any] | None = None,
        fetch_bytes: Callable[[str], bytes] | None = None,
        now_utc: Callable[[], datetime] | None = None,
    ):
        self.base_dir = Path(base_dir)
        token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or ""
        self.interval_seconds = int(interval_seconds or (60 if token else 300))
        self.interval_seconds = max(30, min(3600, self.interval_seconds))
        self._token = token
        self._fetch_json = fetch_json or self._default_fetch_json
        self._fetch_bytes = fetch_bytes or self._default_fetch_bytes
        self._now_utc = now_utc or (lambda: datetime.now(timezone.utc))
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def _request(self, url: str, accept: str) -> bytes:
        headers = {
            "Accept": accept,
            "User-Agent": "icarus-adaptive-brain-sync/1",
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        req = Request(url, headers=headers)
        with urlopen(req, timeout=15) as resp:
            return resp.read()

    def _default_fetch_json(self, url: str) -> Any:
        return json.loads(self._request(url, "application/vnd.github+json").decode("utf-8"))

    def _default_fetch_bytes(self, url: str) -> bytes:
        return self._request(url, "application/vnd.github.raw+json")

    def status(self) -> dict[str, Any]:
        state = _read_state(self.base_dir, self.interval_seconds)
        state.pop("processed_blob_shas", None)
        return state

    def _record_subsystems(
        self,
        payload: Mapping[str, Any],
        evidence: list[str],
        details: Mapping[str, Any],
    ) -> int:
        count = 0
        for key, subsystem_id in _SUBSYSTEM_ALIASES.items():
            value = payload.get(key)
            if not isinstance(value, Mapping):
                continue
            finding = value.get("finding") or value.get("summary") or value.get("detail")
            if not isinstance(finding, str) or not finding.strip():
                continue
            record_brain_event(
                self.base_dir,
                {
                    "kind": "subsystem",
                    "subject": subsystem_id,
                    "summary": finding.strip()[:2200],
                    "status": _normalize_status(value.get("status")),
                    "evidence": evidence,
                    "details": {
                        **dict(details),
                        "reported_subsystem": subsystem_id,
                        "remote_subsystem_status": value.get("status"),
                    },
                },
            )
            count += 1
        return count

    def sync_once(self) -> dict[str, Any]:
        with self._lock:
            state = _read_state(self.base_dir, self.interval_seconds)
            state["last_attempt_at"] = _utc_now()
            state["status"] = "syncing"
            state["last_error"] = None
            errors: list[str] = []
            ingested_paths: list[str] = []

            try:
                contract_docs: dict[str, Mapping[str, Any]] = {}
                contract_blobs: dict[str, str] = {}
                for label, api_url in (
                    ("consumer", _REMOTE_CONSUMER_CONTRACT_API),
                    ("producer", _REMOTE_PRODUCER_CONTRACT_API),
                ):
                    meta = self._fetch_json(api_url)
                    if not isinstance(meta, Mapping):
                        raise ValueError(f"{label} federation contract metadata is not an object")
                    blob_sha = str(meta.get("sha") or "").lower()
                    raw_url = str(meta.get("url") or "")
                    if not _is_sha(blob_sha) or not raw_url:
                        raise ValueError(f"{label} federation contract has invalid GitHub blob metadata")
                    raw = self._fetch_bytes(raw_url)
                    if _git_blob_sha(raw) != blob_sha:
                        raise ValueError(f"{label} federation contract Git blob SHA mismatch")
                    payload = json.loads(raw.decode("utf-8"))
                    if not isinstance(payload, Mapping):
                        raise ValueError(f"{label} federation contract payload is not an object")
                    contract_docs[label] = payload
                    contract_blobs[label] = blob_sha

                state.update(
                    _normalize_federation_contract(
                        contract_docs["consumer"],
                        contract_docs["producer"],
                        contract_blobs,
                    )
                )

                peer_error = None
                try:
                    peer_meta = self._fetch_json(_REMOTE_PEER_PACKET_API)
                    if not isinstance(peer_meta, Mapping):
                        raise ValueError("peer packet metadata is not an object")
                    peer_blob = str(peer_meta.get("sha") or "").lower()
                    peer_url = str(peer_meta.get("url") or "")
                    if not _is_sha(peer_blob) or not peer_url:
                        raise ValueError("peer packet has invalid GitHub blob metadata")
                    peer_raw = self._fetch_bytes(peer_url)
                    if _git_blob_sha(peer_raw) != peer_blob:
                        raise ValueError("peer packet Git blob SHA mismatch")
                    peer_payload = json.loads(peer_raw.decode("utf-8"))
                    if not isinstance(peer_payload, Mapping):
                        raise ValueError("peer packet payload is not an object")
                    normalized_peer = _normalize_peer_packet(
                        peer_payload,
                        blob_sha=peer_blob,
                        historical_context_contract=contract_docs["consumer"]["historical_context"],
                    )
                    source_commit = normalized_peer["peer_source_commit"]
                    compare = self._fetch_json(_remote_compare_api(source_commit))
                    if not isinstance(compare, Mapping):
                        raise ValueError("peer source-commit comparison is not an object")
                    relation = str(compare.get("status") or "").strip().lower()
                    if relation not in {"ahead", "identical"}:
                        raise ValueError(
                            "peer source commit is not an ancestor of Icarus-engine/main"
                        )
                    base_commit = compare.get("base_commit")
                    if not isinstance(base_commit, Mapping) or (
                        str(base_commit.get("sha") or "").lower() != source_commit
                    ):
                        raise ValueError("peer source-commit comparison base mismatch")
                    merge_base = compare.get("merge_base_commit")
                    if relation == "ahead" and (
                        not isinstance(merge_base, Mapping)
                        or str(merge_base.get("sha") or "").lower() != source_commit
                    ):
                        raise ValueError("peer source commit is not the mainline merge base")
                    normalized_peer["peer_source_commit_verified"] = True
                    normalized_peer["peer_source_commit_relation"] = relation.upper()

                    verified_historical = 0
                    for artifact in normalized_peer["peer_historical_artifacts"]:
                        artifact_api = _remote_artifact_api(
                            artifact["path"],
                            source_commit,
                        )
                        artifact_meta = self._fetch_json(artifact_api)
                        if not isinstance(artifact_meta, Mapping):
                            raise ValueError(
                                f"peer historical artifact metadata is not an object: {artifact['lane']}"
                            )
                        artifact_blob = str(artifact_meta.get("sha") or "").lower()
                        artifact_url = str(artifact_meta.get("url") or "")
                        if not _is_sha(artifact_blob) or not artifact_url:
                            raise ValueError(
                                f"peer historical artifact has invalid GitHub blob metadata: {artifact['lane']}"
                            )
                        if artifact_blob != artifact["source_artifact_blob_sha"]:
                            raise ValueError(
                                f"peer historical artifact source blob mismatch: {artifact['lane']}"
                            )
                        artifact_raw = self._fetch_bytes(artifact_url)
                        if _git_blob_sha(artifact_raw) != artifact_blob:
                            raise ValueError(
                                f"peer historical artifact Git blob SHA mismatch: {artifact['lane']}"
                            )
                        artifact_source = json.loads(artifact_raw.decode("utf-8"))
                        if not isinstance(artifact_source, Mapping):
                            raise ValueError(
                                f"peer historical artifact source is not an object: {artifact['lane']}"
                            )
                        if artifact_source.get("execution_authorized") is True:
                            raise ValueError(
                                f"peer historical artifact source attempts execution authority: {artifact['lane']}"
                            )
                        source_run_id = artifact_source.get("RUN_ID") or artifact_source.get("run_id")
                        source_run_status = (
                            artifact_source.get("RUN_STATUS") or artifact_source.get("status")
                        )
                        if str(source_run_id or "") != artifact["run_id"]:
                            raise ValueError(
                                f"peer historical artifact source run_id mismatch: {artifact['lane']}"
                            )
                        if str(source_run_status or "").upper() != artifact["run_status"]:
                            raise ValueError(
                                f"peer historical artifact source run status mismatch: {artifact['lane']}"
                            )
                        artifact["source_artifact_blob_verified"] = True
                        verified_historical += 1
                    normalized_peer["peer_historical_source_blob_verified_count"] = (
                        verified_historical
                    )

                    now = self._now_utc()
                    if not isinstance(now, datetime) or now.tzinfo is None or now.utcoffset() is None:
                        raise ValueError("peer packet freshness clock must be timezone-aware")
                    observed = datetime.fromisoformat(
                        normalized_peer["peer_observed_at"].replace("Z", "+00:00")
                    )
                    age_seconds = (
                        now.astimezone(timezone.utc) - observed.astimezone(timezone.utc)
                    ).total_seconds()
                    max_age = int(
                        (contract_docs["consumer"].get("peer_packet") or {}).get(
                            "max_age_seconds", -1
                        )
                    )
                    max_future_skew = int(
                        (contract_docs["consumer"].get("peer_packet") or {}).get(
                            "max_future_skew_seconds", -1
                        )
                    )
                    if age_seconds > max_age:
                        raise ValueError(
                            f"peer packet is stale: age {age_seconds:.3f}s exceeds {max_age}s"
                        )
                    if age_seconds < -max_future_skew:
                        raise ValueError(
                            "peer packet observed_at exceeds allowed future clock skew"
                        )
                    normalized_peer["peer_packet_fresh"] = True
                    normalized_peer["peer_packet_age_seconds"] = round(age_seconds, 3)
                    state.update(normalized_peer)
                except Exception as ex:
                    state.update({
                        "peer_packet_status": "degraded",
                        "peer_packet_blob_sha": None,
                        "peer_packet_id": None,
                        "peer_source_commit": None,
                        "peer_source_commit_verified": False,
                        "peer_source_commit_relation": None,
                        "peer_observed_at": None,
                        "peer_packet_fresh": False,
                        "peer_packet_age_seconds": None,
                        "peer_lanes": [],
                        "peer_substantive_lane_count": 0,
                        "peer_durability_only_lane_count": 0,
                        "peer_historical_artifacts": [],
                        "peer_historical_context_count": 0,
                        "peer_historical_collection_count": 0,
                        "peer_historical_source_blob_verified_count": 0,
                    })
                    peer_error = f"{type(ex).__name__}: {ex}"[:1000]

                listing = self._fetch_json(_REMOTE_API)
                if not isinstance(listing, list):
                    raise ValueError("GitHub event directory response is not a list")
            except Exception as ex:
                state["status"] = "degraded"
                state["last_error"] = f"{type(ex).__name__}: {ex}"[:1000]
                _write_state(self.base_dir, state)
                return self.status()

            processed = {
                str(x).lower()
                for x in state.get("processed_blob_shas", [])
                if _is_sha(x)
            }
            entries = []
            for item in listing[:1000]:
                if not isinstance(item, Mapping):
                    continue
                name = item.get("name")
                path = item.get("path")
                sha = str(item.get("sha") or "").lower()
                if (
                    item.get("type") == "file"
                    and isinstance(name, str)
                    and name.endswith(".json")
                    and isinstance(path, str)
                    and path.startswith(REMOTE_ROOT + "/")
                    and _is_sha(sha)
                ):
                    entries.append((name, path, sha, str(item.get("url") or "")))
            entries.sort(key=lambda x: x[0])

            for _name, path, blob_sha, url in entries:
                if blob_sha in processed:
                    continue
                if not url:
                    errors.append(f"{path}: missing GitHub contents URL")
                    continue
                try:
                    raw = self._fetch_bytes(url)
                    if _git_blob_sha(raw) != blob_sha:
                        raise ValueError("Git blob SHA mismatch")
                    payload = json.loads(raw.decode("utf-8"))
                    if not isinstance(payload, Mapping):
                        raise ValueError("event payload is not an object")
                    if payload.get("execution_authorized") is not False:
                        raise ValueError("event does not explicitly preserve execution_authorized=false")

                    source = str(payload.get("source") or "").strip().upper()
                    agent_id = SOURCE_TO_AGENT.get(source)
                    if agent_id is None:
                        state["ignored_total"] = int(state.get("ignored_total", 0)) + 1
                        processed.add(blob_sha)
                        continue

                    schema = payload.get("schema_version", payload.get("schema"))
                    if schema != "icarus-mcp-event-v1":
                        raise ValueError("unsupported custom-agent event schema")
                    category = str(payload.get("category") or "").strip().upper()
                    if category not in {"REPAIR", "AUDIT", "EVOLUTION", "INTEGRATION"}:
                        raise ValueError("unsupported custom-agent event category")

                    required_fields = contract_docs["producer"].get("required_fields") or []
                    missing_fields = [
                        field for field in required_fields
                        if field not in payload
                    ]
                    legacy_blobs = {
                        str(value).lower()
                        for value in (
                            (contract_docs["consumer"].get("event_validation") or {})
                            .get("legacy_relaxed_blob_shas", [])
                        )
                    }
                    legacy_exception = bool(missing_fields and blob_sha in legacy_blobs)
                    if missing_fields and not legacy_exception:
                        raise ValueError(
                            "custom-agent event missing required producer fields: "
                            + ", ".join(sorted(missing_fields))
                        )

                    evidence = _compact_evidence(payload, path, blob_sha)
                    evidence.extend([
                        f"consumer_contract_blob:{state.get('consumer_contract_blob_sha')}",
                        f"producer_contract_blob:{state.get('producer_contract_blob_sha')}",
                    ])
                    evidence = evidence[:32]
                    details = _event_details(payload, path, blob_sha)
                    details["federation_event_validation"] = (
                        "LEGACY_EXACT_BLOB_EXCEPTION"
                        if legacy_exception
                        else "STRICT_V1_REQUIRED_FIELDS"
                    )
                    details["federation_missing_required_fields"] = missing_fields
                    record_brain_event(
                        self.base_dir,
                        {
                            "kind": "agent",
                            "subject": agent_id,
                            "summary": _summary(payload),
                            "status": _normalize_status(payload.get("status")),
                            "evidence": evidence,
                            "details": details,
                        },
                    )
                    self._record_subsystems(payload, evidence, details)
                    processed.add(blob_sha)
                    state["ingested_total"] = int(state.get("ingested_total", 0)) + 1
                    ingested_paths.append(path)
                except Exception as ex:
                    errors.append(f"{path}: {type(ex).__name__}: {ex}")
                    state["rejected_total"] = int(state.get("rejected_total", 0)) + 1

            if peer_error:
                errors.append(f"peer packet: {peer_error}")
            state["processed_blob_shas"] = sorted(processed)[-5000:]
            state["last_ingested"] = ingested_paths[-20:]
            state["last_success_at"] = _utc_now()
            state["last_error"] = " | ".join(errors[-10:])[:3000] if errors else None
            state["status"] = "degraded" if errors else "green"
            _write_state(self.base_dir, state)
            return self.status()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                self.sync_once()
            except Exception:
                # The trader engine must never crash because the optional remote
                # intelligence plane is unavailable.
                pass
            self._stop.wait(self.interval_seconds)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="icarus-adaptive-brain-remote-sync",
            daemon=True,
        )
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive() and self._thread is not threading.current_thread():
            self._thread.join(timeout=2.0)
