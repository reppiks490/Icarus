from __future__ import annotations

import copy

import pytest

from icarus_engine.ascendancy.federated_seeds import build_federated_research_seeds


def _source(
    source_id="robustness_guardian",
    *,
    blob="b" * 40,
    evidence_status="HISTORICAL_RESEARCH_EVIDENCE",
    summary=None,
):
    if summary is None:
        summary = {
            "RUN_CORE.findings": [
                "Protected holdout lineage is incomplete.",
                "Replay determinism remains intact.",
            ],
            "RUN_CORE.NEXT": "Bind immutable dataset and holdout identities.",
        }
    return {
        "id": source_id,
        "path": f"automation_intelligence/{source_id}/latest.json",
        "remote_blob_sha": blob,
        "run_id": f"{source_id}-20261002T180000Z",
        "run_status": "RUN_PERSISTED",
        "evidence_status": evidence_status,
        "collection_only": source_id == "flow_microstructure",
        "research_context_eligible": True,
        "candidate_evidence_eligible": False,
        "foreign_evidence_only": True,
        "requires_foundry_and_evaluator": True,
        "summary": summary,
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


def _witness(
    source_id="robustness_guardian",
    *,
    blob="b" * 40,
    relation="SAME_AS_PACKET_SOURCE",
):
    return {
        "id": source_id,
        "artifact_id": "c" * 64,
        "path": f"automation_intelligence/{source_id}/latest.json",
        "source_artifact_blob_sha": blob,
        "source_artifact_blob_verified": True,
        "current_main_blob_sha": blob if relation == "SAME_AS_PACKET_SOURCE" else "d" * 40,
        "current_main_relation": relation,
        "run_id": f"{source_id}-20261002T180000Z",
        "run_status": "RUN_PERSISTED",
    }


def _state(*, source=None, witness=None, status="green"):
    source = source or _source()
    witness = witness or _witness(source["id"], blob=source["remote_blob_sha"])
    return {
        "status": status,
        "repository": "reppiks490/Icarus-engine",
        "ref": "main",
        "peer_packet_status": "green",
        "peer_packet_fresh": True,
        "peer_source_commit": "a" * 40,
        "peer_source_commit_verified": True,
        "peer_source_commit_relation": "AHEAD",
        "historical_context_status": "green",
        "historical_packet_witness_status": "green",
        "historical_candidate_evidence_count": 0,
        "historical_context_sources": [source],
        "historical_packet_witnesses": [witness],
        "truth_contract": {
            "historical_context_mode": "RESEARCH_CONTEXT_ONLY",
            "historical_context_never_bypasses_foundry": True,
            "historical_context_never_bypasses_evaluator": True,
            "historical_context_never_grants_shadow_qualification": True,
            "historical_context_never_grants_execution_authority": True,
            "historical_source_artifact_blob_required": True,
            "historical_artifact_id_sha256_required": True,
        },
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


def test_seed_is_deterministic_provenance_bound_and_never_a_candidate():
    state = _state()
    one = build_federated_research_seeds(state)
    two = build_federated_research_seeds(state)

    assert one == two
    assert one["status"] == "READY"
    assert one["ready_seed_count"] == 1
    assert one["blocked_source_count"] == 0

    seed = one["seeds"][0]
    assert len(seed["seed_id"]) == 64
    assert seed["source_repository"] == "reppiks490/Icarus-engine"
    assert seed["source_commit"] == "a" * 40
    assert seed["source_artifact_blob_sha"] == "b" * 40
    assert seed["source_artifact_id"] == "c" * 64
    assert seed["source_id"] == "robustness_guardian"
    assert seed["research_focus"] == "robustness_and_falsification"
    assert seed["status"] == "RESEARCH_SEED_ONLY"
    assert seed["candidate_id"] is None
    assert seed["candidate_evidence_eligible"] is False
    assert seed["automatic_candidate_creation"] is False
    assert seed["qualification_authorized"] is False
    assert seed["execution_authorized"] is False
    assert seed["production_decision_authorized"] is False

    admission = seed["admission_contract"]
    assert admission["candidate_foundry_required"] is True
    assert admission["evaluator_required"] is True
    assert admission["independent_evidence_required"] is True
    assert admission["source_context_is_candidate_evidence"] is False


def test_live_source_advancement_blocks_seed_until_packet_refresh():
    source = _source()
    witness = _witness(relation="LIVE_SOURCE_ADVANCED")
    out = build_federated_research_seeds(_state(source=source, witness=witness))

    assert out["status"] == "PARTIALLY_BLOCKED"
    assert out["ready_seed_count"] == 0
    assert out["blocked_source_count"] == 1
    blocked = out["blocked_sources"][0]
    assert blocked["source_id"] == "robustness_guardian"
    assert blocked["reason"] == "PROVENANCE_REFRESH_REQUIRED"
    assert blocked["current_main_relation"] == "LIVE_SOURCE_ADVANCED"
    assert blocked["candidate_evidence_eligible"] is False


def test_unverified_peer_commit_blocks_all_seed_generation():
    state = _state()
    state["peer_source_commit_verified"] = False
    out = build_federated_research_seeds(state)
    assert out["status"] == "BLOCKED_PROVENANCE"
    assert out["ready_seed_count"] == 0
    assert out["seeds"] == []
    assert out["execution_authorized"] is False


def test_degraded_federation_is_not_treated_as_zero_or_valid_research():
    out = build_federated_research_seeds(_state(status="degraded"))
    assert out["status"] == "BLOCKED_FEDERATION"
    assert out["ready_seed_count"] == 0
    assert out["unavailable_is_not_zero"] is True


def test_authority_or_candidate_evidence_escalation_is_rejected():
    state = _state()
    state["execution_authorized"] = True
    with pytest.raises(ValueError, match="authority"):
        build_federated_research_seeds(state)

    state = _state()
    state["historical_context_sources"][0]["candidate_evidence_eligible"] = True
    with pytest.raises(ValueError, match="candidate evidence"):
        build_federated_research_seeds(state)


def test_blob_or_witness_identity_mismatch_fails_closed():
    state = _state()
    state["historical_packet_witnesses"][0]["source_artifact_blob_sha"] = "e" * 40
    with pytest.raises(ValueError, match="blob"):
        build_federated_research_seeds(state)

    state = _state()
    state["historical_packet_witnesses"][0]["source_artifact_blob_verified"] = False
    with pytest.raises(ValueError, match="verified"):
        build_federated_research_seeds(state)


def test_all_declared_peer_research_domains_receive_typed_focuses():
    cases = [
        ("robustness_guardian", "HISTORICAL_RESEARCH_EVIDENCE", "robustness_and_falsification"),
        ("alpha_synthesis", "HISTORICAL_RESEARCH_EVIDENCE", "alpha_execution_economics"),
        ("apex_council", "HISTORICAL_RESEARCH_EVIDENCE", "cross_system_disagreement"),
        ("flow_microstructure", "HISTORICAL_COLLECTION_EVIDENCE", "market_evidence_and_data_gaps"),
    ]
    sources = []
    witnesses = []
    for index, (source_id, evidence, _) in enumerate(cases):
        blob = f"{index + 1:x}" * 40
        sources.append(_source(
            source_id,
            blob=blob,
            evidence_status=evidence,
            summary={"research": f"context-{source_id}"},
        ))
        witnesses.append(_witness(source_id, blob=blob))

    state = _state(source=sources[0], witness=witnesses[0])
    state["historical_context_sources"] = sources
    state["historical_packet_witnesses"] = witnesses
    out = build_federated_research_seeds(state)

    assert out["ready_seed_count"] == 4
    by_source = {row["source_id"]: row for row in out["seeds"]}
    for source_id, _, focus in cases:
        assert by_source[source_id]["research_focus"] == focus
        assert by_source[source_id]["research_prompt"]
        assert by_source[source_id]["source_summary_hash"]
