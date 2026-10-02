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

_HISTORICAL_CONTEXT_EXPECTED = {
    "robustness_guardian": {
        "path": "automation_intelligence/agent_fabric/robustness_guardian/latest.json",
        "evidence_status": "HISTORICAL_RESEARCH_EVIDENCE",
        "collection_only": False,
        "subject": "aegis",
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
    },
    "alpha_synthesis": {
        "path": "automation_intelligence/agent_fabric/alpha_synthesis/latest.json",
        "evidence_status": "HISTORICAL_RESEARCH_EVIDENCE",
        "collection_only": False,
        "subject": "aion",
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
    },
    "apex_council": {
        "path": "automation_intelligence/agent_fabric/apex_council/latest.json",
        "evidence_status": "HISTORICAL_RESEARCH_EVIDENCE",
        "collection_only": False,
        "subject": "apex-omega",
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
    },
    "flow_microstructure": {
        "path": "automation_intelligence/flow/latest.json",
        "evidence_status": "HISTORICAL_COLLECTION_EVIDENCE",
        "collection_only": True,
        "subject": "data",
        "summary_fields": [
            "NET_NEW_DELTA",
            "observations",
            "PROVIDER_CONFLICTS",
            "DATA_GAPS",
            "source_provenance",
            "quality_notes",
            "history_blob_sha",
        ],
    },
}

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


def _remote_contents_api(path: str) -> str:
    remote_path = str(path or "").strip().lstrip("/")
    if not remote_path or ".." in remote_path.split("/"):
        raise ValueError("historical context path is invalid")
    return (
        f"https://api.github.com/repos/{REMOTE_REPOSITORY}/contents/"
        f"{remote_path}?ref={REMOTE_REF}"
    )


def _remote_compare_api(source_commit: str) -> str:
    source = str(source_commit or "").strip().lower()
    if not _is_sha(source):
        raise ValueError("peer source commit must be an exact 40-character Git SHA")
    return f"https://api.github.com/repos/{REMOTE_REPOSITORY}/compare/{source}...{REMOTE_REF}"


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
        "historical_context_status": "not_started",
        "historical_context_source_count": 0,
        "historical_context_ingested_total": 0,
        "historical_context_sources": [],
        "historical_candidate_evidence_count": 0,
        "processed_historical_blob_shas": [],
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
            "historical_context_mode": "UNDECLARED",
            "historical_context_never_bypasses_foundry": True,
            "historical_context_never_bypasses_evaluator": True,
            "historical_context_never_grants_shadow_qualification": True,
            "historical_context_never_grants_execution_authority": True,
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


def _normalize_historical_context_contract(
    consumer: Mapping[str, Any],
) -> list[dict[str, Any]]:
    raw = consumer.get("historical_context")
    if raw is None:
        return []
    if not isinstance(raw, Mapping):
        raise ValueError("Icarus-engine historical context contract must be an object")
    if raw.get("mode") != "RESEARCH_CONTEXT_ONLY":
        raise ValueError("Icarus-engine historical context mode must remain research-only")
    for key in (
        "direct_candidate_evidence",
        "automatic_candidate_creation",
        "automatic_model_promotion",
        "execution_authorized",
        "production_decision_authorized",
    ):
        if raw.get(key) is not False:
            raise ValueError(
                f"Icarus-engine historical context attempts authority escalation: {key}"
            )

    truth = raw.get("truth_contract")
    if not isinstance(truth, Mapping):
        raise ValueError("Icarus-engine historical context truth contract is missing")
    for key in (
        "foreign_repository_state_is_context_not_native_truth",
        "historical_context_never_bypasses_foundry",
        "historical_context_never_bypasses_evaluator",
        "historical_context_never_grants_shadow_qualification",
        "historical_context_never_grants_execution_authority",
    ):
        if truth.get(key) is not True:
            raise ValueError(
                f"Icarus-engine historical context truth invariant failed: {key}"
            )

    sources = raw.get("sources")
    if not isinstance(sources, list):
        raise ValueError("Icarus-engine historical context sources must be an array")
    if len(sources) != len(_HISTORICAL_CONTEXT_EXPECTED):
        raise ValueError("Icarus-engine historical context source set mismatch")

    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for source in sources:
        if not isinstance(source, Mapping):
            raise ValueError("Icarus-engine historical context source must be an object")
        source_id = str(source.get("id") or "").strip()
        if source_id in seen or source_id not in _HISTORICAL_CONTEXT_EXPECTED:
            raise ValueError("Icarus-engine historical context source identity mismatch")
        seen.add(source_id)
        expected = _HISTORICAL_CONTEXT_EXPECTED[source_id]
        if source.get("path") != expected["path"]:
            raise ValueError(
                f"Icarus-engine historical context path mismatch: {source_id}"
            )
        if source.get("evidence_status") != expected["evidence_status"]:
            raise ValueError(
                f"Icarus-engine historical context evidence status mismatch: {source_id}"
            )
        if source.get("research_context_eligible") is not True:
            raise ValueError(
                f"Icarus-engine historical context must remain research-context eligible: {source_id}"
            )
        if source.get("candidate_evidence_eligible") is not False:
            raise ValueError(
                f"Icarus-engine historical context cannot become candidate evidence: {source_id}"
            )
        if source.get("collection_only") is not expected["collection_only"]:
            raise ValueError(
                f"Icarus-engine historical context collection semantics mismatch: {source_id}"
            )
        if source.get("execution_authorized") is not False:
            raise ValueError(
                f"Icarus-engine historical context attempts execution authority: {source_id}"
            )
        fields = source.get("summary_fields")
        if not isinstance(fields, list) or fields != expected["summary_fields"]:
            raise ValueError(
                f"Icarus-engine historical context field allowlist mismatch: {source_id}"
            )
        normalized.append({
            "id": source_id,
            "path": expected["path"],
            "evidence_status": expected["evidence_status"],
            "collection_only": expected["collection_only"],
            "subject": expected["subject"],
            "summary_fields": list(expected["summary_fields"]),
            "research_context_eligible": True,
            "candidate_evidence_eligible": False,
            "execution_authorized": False,
        })
    return sorted(normalized, key=lambda row: row["id"])


def _get_dotted(payload: Mapping[str, Any], path: str) -> Any:
    current: Any = payload
    for part in str(path).split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def _normalize_historical_document(
    source: Mapping[str, Any],
    payload: Mapping[str, Any],
    *,
    blob_sha: str,
) -> dict[str, Any]:
    if payload.get("execution_authorized") is not False:
        raise ValueError(
            f"historical context {source['id']} must preserve execution_authorized=false"
        )
    run_core = payload.get("RUN_CORE")
    if isinstance(run_core, Mapping) and run_core.get("execution_authorized") not in (None, False):
        raise ValueError(
            f"historical context {source['id']} RUN_CORE attempts execution authority"
        )
    if source.get("collection_only") is True and payload.get("COLLECTION_ONLY") is not True:
        raise ValueError(
            f"historical context {source['id']} must preserve collection-only semantics"
        )
    sha = str(blob_sha or "").lower()
    if not _is_sha(sha):
        raise ValueError("historical context Git blob identity is invalid")

    summary: dict[str, Any] = {}
    for field in source.get("summary_fields") or []:
        value = _get_dotted(payload, field)
        if value is not None:
            summary[str(field)] = value
    try:
        encoded = json.dumps(
            summary,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as ex:
        raise ValueError(
            f"historical context {source['id']} summary is not finite JSON"
        ) from ex
    if len(encoded.encode("utf-8")) > 65536:
        raise ValueError(
            f"historical context {source['id']} summary exceeds bounded payload size"
        )

    return {
        "id": source["id"],
        "path": source["path"],
        "remote_blob_sha": sha,
        "run_id": payload.get("RUN_ID") or payload.get("run_id"),
        "run_status": payload.get("RUN_STATUS") or payload.get("status"),
        "evidence_status": source["evidence_status"],
        "collection_only": source["collection_only"],
        "research_context_eligible": True,
        "candidate_evidence_eligible": False,
        "foreign_evidence_only": True,
        "requires_foundry_and_evaluator": True,
        "summary": summary,
        "subject": source["subject"],
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


def _historical_event_summary(row: Mapping[str, Any]) -> str:
    summary = row.get("summary")
    if not isinstance(summary, Mapping):
        return f"{row.get('id', 'peer')} historical research context observed."
    priority = (
        "RUN_CORE.findings",
        "RUN_CORE.disagreements_collisions",
        "NET_NEW_DELTA",
        "RUN_CORE.NEXT",
        "DATA_GAPS",
    )
    for key in priority:
        value = summary.get(key)
        if value in (None, "", [], {}):
            continue
        if isinstance(value, str):
            text = value
        else:
            text = json.dumps(value, sort_keys=True, allow_nan=False)
        return f"{row.get('id')}: {text}"[:2200]
    return f"{row.get('id', 'peer')} historical research context observed."[:2200]


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

    historical_sources = _normalize_historical_context_contract(consumer)

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
        },
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


def _normalize_peer_packet(
    packet: Mapping[str, Any],
    *,
    blob_sha: str,
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
        state.pop("processed_historical_blob_shas", None)
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

    def _sync_historical_context(
        self,
        state: dict[str, Any],
        consumer_contract: Mapping[str, Any],
    ) -> list[str]:
        sources = _normalize_historical_context_contract(consumer_contract)
        if not sources:
            state["historical_context_status"] = "not_declared"
            state["historical_context_source_count"] = 0
            state["historical_context_sources"] = []
            state["historical_candidate_evidence_count"] = 0
            return []

        processed = {
            str(x).lower()
            for x in state.get("processed_historical_blob_shas", [])
            if _is_sha(x)
        }
        errors: list[str] = []
        rows: list[dict[str, Any]] = []
        for source in sources:
            try:
                meta = self._fetch_json(_remote_contents_api(source["path"]))
                if not isinstance(meta, Mapping) or meta.get("type") != "file":
                    raise ValueError("historical context GitHub metadata is not a file")
                blob_sha = str(meta.get("sha") or "").lower()
                raw_url = str(meta.get("url") or "")
                if not _is_sha(blob_sha) or not raw_url:
                    raise ValueError("historical context has invalid GitHub blob metadata")
                raw = self._fetch_bytes(raw_url)
                if _git_blob_sha(raw) != blob_sha:
                    raise ValueError("historical context Git blob SHA mismatch")
                payload = json.loads(raw.decode("utf-8"))
                if not isinstance(payload, Mapping):
                    raise ValueError("historical context payload is not an object")
                row = _normalize_historical_document(
                    source,
                    payload,
                    blob_sha=blob_sha,
                )
                rows.append(row)

                if blob_sha not in processed:
                    evidence = [
                        f"remote_repository:{REMOTE_REPOSITORY}",
                        f"remote_ref:{REMOTE_REF}",
                        f"remote_path:{source['path']}",
                        f"git_blob_sha:{blob_sha}",
                        f"evidence_status:{source['evidence_status']}",
                        f"consumer_contract_blob:{state.get('consumer_contract_blob_sha')}",
                        f"producer_contract_blob:{state.get('producer_contract_blob_sha')}",
                    ]
                    record_brain_event(
                        self.base_dir,
                        {
                            "kind": "subsystem",
                            "subject": source["subject"],
                            "summary": _historical_event_summary(row),
                            "status": "observed",
                            "evidence": evidence,
                            "details": {
                                "foreign_historical_context": True,
                                "historical_context_source": source["id"],
                                "historical_context_path": source["path"],
                                "historical_context_blob_sha": blob_sha,
                                "evidence_status": source["evidence_status"],
                                "collection_only": source["collection_only"],
                                "research_context_eligible": True,
                                "candidate_evidence_eligible": False,
                                "requires_foundry_and_evaluator": True,
                                "foreign_evidence_only": True,
                                "summary": row["summary"],
                                "execution_authorized": False,
                                "production_decision_authorized": False,
                            },
                        },
                    )
                    processed.add(blob_sha)
                    state["historical_context_ingested_total"] = int(
                        state.get("historical_context_ingested_total", 0)
                    ) + 1
            except Exception as ex:
                errors.append(
                    f"historical context {source.get('id')}: "
                    f"{type(ex).__name__}: {ex}"
                )

        rows.sort(key=lambda row: row["id"])
        state["processed_historical_blob_shas"] = sorted(processed)[-1000:]
        state["historical_context_sources"] = rows
        state["historical_context_source_count"] = len(rows)
        state["historical_candidate_evidence_count"] = sum(
            1 for row in rows if row.get("candidate_evidence_eligible") is True
        )
        state["historical_context_status"] = (
            "green" if len(rows) == len(sources) and not errors else "degraded"
        )
        return errors

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

                historical_errors = self._sync_historical_context(
                    state,
                    contract_docs["consumer"],
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
                    normalized_peer = _normalize_peer_packet(peer_payload, blob_sha=peer_blob)
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

            errors.extend(historical_errors)
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
