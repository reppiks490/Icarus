"""ASCENDANCY federated research-seed adapter.

Turns provenance-verified Icarus-engine historical research context into
deterministic *research seeds*.  A seed is an invitation to formulate and test
a hypothesis; it is not a candidate, not evidence of edge, and cannot bypass
Candidate Foundry, the Evaluator Cascade, qualification, or execution controls.

Only historical context whose current-main artifact is exactly the artifact
witnessed by the provenance-bound peer packet can produce a ready seed.  If the
live peer artifact has advanced, the source is blocked until a fresh packet
binds the new revision.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "icarus-ascendancy-federated-research-seeds-v1"
SEED_SCHEMA_VERSION = "icarus-ascendancy-federated-research-seed-v1"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA64 = re.compile(r"^[0-9a-f]{64}$")

_FOCUS = {
    "robustness_guardian": "robustness_and_falsification",
    "alpha_synthesis": "alpha_execution_economics",
    "apex_council": "cross_system_disagreement",
    "flow_microstructure": "market_evidence_and_data_gaps",
}
_EVIDENCE = {
    "HISTORICAL_RESEARCH_EVIDENCE",
    "HISTORICAL_COLLECTION_EVIDENCE",
}


def _canonical(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as ex:
        raise ValueError("federated seed values must be finite JSON") from ex


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _sha(value: Any, name: str, size: int) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a {size}-character hash")
    out = value.strip().lower()
    pattern = _SHA40 if size == 40 else _SHA64
    if not pattern.fullmatch(out):
        raise ValueError(f"{name} must be a {size}-character hash")
    return out


def _research_only(value: Mapping[str, Any], label: str) -> None:
    for key in (
        "execution_authorized",
        "production_decision_authorized",
        "qualification_authorized",
    ):
        if value.get(key) is True:
            raise ValueError(f"{label} authority escalation is forbidden")


def _base(status: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "status": status,
        "source_repository": "reppiks490/Icarus-engine",
        "source_ref": "main",
        "ready_seed_count": 0,
        "blocked_source_count": 0,
        "seeds": [],
        "blocked_sources": [],
        "unavailable_is_not_zero": True,
        "truth_contract": {
            "research_seed_is_not_candidate": True,
            "research_seed_is_not_candidate_evidence": True,
            "automatic_candidate_creation": False,
            "candidate_foundry_required": True,
            "evaluator_required": True,
            "independent_evidence_required": True,
            "provenance_refresh_required_after_live_source_advance": True,
            "qualification_authorized": False,
            "execution_authorized": False,
            "production_decision_authorized": False,
        },
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


def _prompt(source_id: str, focus: str, summary: Mapping[str, Any]) -> str:
    excerpt = _canonical(summary)
    if len(excerpt) > 1800:
        excerpt = excerpt[:1800] + "…"
    return (
        f"Formulate a falsifiable research question in the {focus} domain from "
        f"the bounded foreign context emitted by {source_id}. Treat the context "
        f"as a hypothesis-generating constraint, not as candidate evidence. "
        f"Require independent evidence, protected evaluation, and an explicit "
        f"invalidation condition before any Foundry admission. Context={excerpt}"
    )


def build_federated_research_seeds(remote_sync: Mapping[str, Any]) -> dict[str, Any]:
    """Build deterministic research seeds from canonical BrainRemoteSync state."""
    if not isinstance(remote_sync, Mapping):
        raise ValueError("remote_sync must be an object")
    _research_only(remote_sync, "remote federation")

    if str(remote_sync.get("status") or "").lower() != "green":
        return _base("BLOCKED_FEDERATION")
    if str(remote_sync.get("historical_context_status") or "").lower() != "green":
        return _base("BLOCKED_FEDERATION")
    if str(remote_sync.get("historical_packet_witness_status") or "").lower() != "green":
        return _base("BLOCKED_PROVENANCE")
    if remote_sync.get("peer_source_commit_verified") is not True:
        return _base("BLOCKED_PROVENANCE")
    if int(remote_sync.get("historical_candidate_evidence_count") or 0) != 0:
        raise ValueError("foreign historical context cannot become candidate evidence")

    truth = remote_sync.get("truth_contract")
    if not isinstance(truth, Mapping):
        raise ValueError("remote federation truth_contract is required")
    required_truth = (
        "historical_context_never_bypasses_foundry",
        "historical_context_never_bypasses_evaluator",
        "historical_context_never_grants_shadow_qualification",
        "historical_context_never_grants_execution_authority",
        "historical_source_artifact_blob_required",
        "historical_artifact_id_sha256_required",
    )
    for key in required_truth:
        if truth.get(key) is not True:
            raise ValueError(f"remote federation truth contract must affirm {key}")

    source_commit = _sha(remote_sync.get("peer_source_commit"), "peer_source_commit", 40)
    source_repository = str(remote_sync.get("repository") or "reppiks490/Icarus-engine").strip()
    if source_repository != "reppiks490/Icarus-engine":
        raise ValueError("unexpected federated source repository")

    raw_sources = remote_sync.get("historical_context_sources")
    raw_witnesses = remote_sync.get("historical_packet_witnesses")
    if not isinstance(raw_sources, Sequence) or isinstance(raw_sources, (str, bytes)):
        raise ValueError("historical_context_sources must be a list")
    if not isinstance(raw_witnesses, Sequence) or isinstance(raw_witnesses, (str, bytes)):
        raise ValueError("historical_packet_witnesses must be a list")

    witnesses: dict[str, Mapping[str, Any]] = {}
    for witness in raw_witnesses:
        if not isinstance(witness, Mapping):
            raise ValueError("historical packet witness must be an object")
        source_id = str(witness.get("id") or "").strip()
        if not source_id or source_id in witnesses:
            raise ValueError("historical packet witness identity is missing or duplicated")
        if witness.get("source_artifact_blob_verified") is not True:
            raise ValueError(f"historical packet witness is not verified: {source_id}")
        witnesses[source_id] = witness

    out = _base("READY")
    out["source_commit"] = source_commit
    ready: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    seen_sources: set[str] = set()

    for raw in raw_sources:
        if not isinstance(raw, Mapping):
            raise ValueError("historical context source must be an object")
        _research_only(raw, "historical context source")
        source_id = str(raw.get("id") or "").strip()
        if not source_id or source_id in seen_sources:
            raise ValueError("historical context source identity is missing or duplicated")
        seen_sources.add(source_id)

        if raw.get("candidate_evidence_eligible") is not False:
            raise ValueError(f"historical context attempts candidate evidence: {source_id}")
        if raw.get("research_context_eligible") is not True:
            blocked.append({
                "source_id": source_id,
                "reason": "RESEARCH_CONTEXT_NOT_ELIGIBLE",
                "candidate_evidence_eligible": False,
            })
            continue
        if raw.get("foreign_evidence_only") is not True:
            raise ValueError(f"historical context must remain foreign evidence: {source_id}")
        if raw.get("requires_foundry_and_evaluator") is not True:
            raise ValueError(f"historical context must require Foundry and Evaluator: {source_id}")

        evidence_status = str(raw.get("evidence_status") or "").upper()
        if evidence_status not in _EVIDENCE:
            blocked.append({
                "source_id": source_id,
                "reason": "UNSUPPORTED_EVIDENCE_STATUS",
                "evidence_status": evidence_status or None,
                "candidate_evidence_eligible": False,
            })
            continue

        witness = witnesses.get(source_id)
        if witness is None:
            blocked.append({
                "source_id": source_id,
                "reason": "MISSING_PACKET_WITNESS",
                "candidate_evidence_eligible": False,
            })
            continue

        source_blob = _sha(raw.get("remote_blob_sha"), "remote_blob_sha", 40)
        witnessed_blob = _sha(
            witness.get("source_artifact_blob_sha"),
            "source_artifact_blob_sha",
            40,
        )
        if source_blob != witnessed_blob:
            relation = str(witness.get("current_main_relation") or "").upper()
            if relation != "LIVE_SOURCE_ADVANCED":
                raise ValueError(f"historical source blob does not match packet witness: {source_id}")

        relation = str(witness.get("current_main_relation") or "").upper()
        current_blob_raw = witness.get("current_main_blob_sha")
        current_blob = (
            _sha(current_blob_raw, "current_main_blob_sha", 40)
            if current_blob_raw not in (None, "")
            else None
        )

        if relation == "LIVE_SOURCE_ADVANCED":
            blocked.append({
                "source_id": source_id,
                "reason": "PROVENANCE_REFRESH_REQUIRED",
                "current_main_relation": relation,
                "packet_source_commit": source_commit,
                "witnessed_blob_sha": witnessed_blob,
                "current_main_blob_sha": current_blob,
                "candidate_evidence_eligible": False,
            })
            continue
        if relation != "SAME_AS_PACKET_SOURCE":
            blocked.append({
                "source_id": source_id,
                "reason": "PROVENANCE_RELATION_UNRESOLVED",
                "current_main_relation": relation or None,
                "candidate_evidence_eligible": False,
            })
            continue
        if current_blob != source_blob or source_blob != witnessed_blob:
            raise ValueError(f"historical source blob identity mismatch: {source_id}")

        artifact_id = _sha(witness.get("artifact_id"), "artifact_id", 64)
        summary = raw.get("summary")
        if not isinstance(summary, Mapping) or not summary:
            blocked.append({
                "source_id": source_id,
                "reason": "INSUFFICIENT_CONTEXT",
                "candidate_evidence_eligible": False,
            })
            continue
        summary_dict = dict(summary)
        summary_hash = _hash(summary_dict)
        focus = _FOCUS.get(source_id, "federated_research_context")

        semantic: dict[str, Any] = {
            "schema_version": SEED_SCHEMA_VERSION,
            "source_repository": source_repository,
            "source_ref": "main",
            "source_commit": source_commit,
            "source_id": source_id,
            "source_path": str(raw.get("path") or ""),
            "source_artifact_blob_sha": source_blob,
            "source_artifact_id": artifact_id,
            "source_run_id": raw.get("run_id"),
            "source_run_status": raw.get("run_status"),
            "source_evidence_status": evidence_status,
            "source_summary_hash": summary_hash,
            "source_summary": summary_dict,
            "research_focus": focus,
            "research_prompt": _prompt(source_id, focus, summary_dict),
            "status": "RESEARCH_SEED_ONLY",
            "candidate_id": None,
            "candidate_evidence_eligible": False,
            "automatic_candidate_creation": False,
            "admission_contract": {
                "candidate_foundry_required": True,
                "evaluator_required": True,
                "independent_evidence_required": True,
                "source_context_is_candidate_evidence": False,
            },
            "qualification_authorized": False,
            "execution_authorized": False,
            "production_decision_authorized": False,
        }
        semantic["seed_id"] = _hash(semantic)
        ready.append(semantic)

    ready.sort(key=lambda row: (row["source_id"], row["seed_id"]))
    blocked.sort(key=lambda row: (row["source_id"], row["reason"]))
    out["seeds"] = ready
    out["blocked_sources"] = blocked
    out["ready_seed_count"] = len(ready)
    out["blocked_source_count"] = len(blocked)
    if blocked:
        out["status"] = "PARTIALLY_BLOCKED"
    elif not ready:
        out["status"] = "NO_CONTEXT"
    return out
