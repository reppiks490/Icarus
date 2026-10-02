from __future__ import annotations

import copy

import pytest

from icarus_engine.ascendancy.federated_intake import (
    FederatedResearchIntake,
    derive_federated_proposals,
)


def _snapshot():
    return {
        "schema_version": "icarus-brain-remote-sync-v1",
        "repository": "reppiks490/Icarus-engine",
        "ref": "main",
        "status": "green",
        "peer_packet_status": "green",
        "peer_packet_id": "1" * 64,
        "peer_source_commit": "a" * 40,
        "peer_source_commit_verified": True,
        "peer_source_commit_relation": "HEAD_OR_ANCESTOR",
        "peer_packet_fresh": True,
        "peer_packet_age_seconds": 90.0,
        "historical_context_status": "green",
        "historical_context_source_count": 4,
        "historical_candidate_evidence_count": 0,
        "historical_context_sources": [
            {
                "id": "robustness_guardian",
                "path": "automation_intelligence/agent_fabric/robustness_guardian/latest.json",
                "remote_blob_sha": "b" * 40,
                "run_id": "robustness-guardian-1",
                "run_status": "RUN_PERSISTED",
                "evidence_status": "HISTORICAL_RESEARCH_EVIDENCE",
                "collection_only": False,
                "research_context_eligible": True,
                "candidate_evidence_eligible": False,
                "foreign_evidence_only": True,
                "requires_foundry_and_evaluator": True,
                "summary": {
                    "RUN_CORE.findings": [
                        "Protected holdout lineage is incomplete.",
                        "Replay determinism remains intact.",
                    ],
                    "RUN_CORE.unresolved_risks": [
                        "Dataset identity can drift across historical replays."
                    ],
                    "RUN_CORE.NEXT": "Bind immutable dataset and holdout identities.",
                },
                "subject": "Robustness Guardian",
                "execution_authorized": False,
                "production_decision_authorized": False,
            },
            {
                "id": "alpha_synthesis",
                "path": "automation_intelligence/agent_fabric/alpha_synthesis/latest.json",
                "remote_blob_sha": "c" * 40,
                "run_id": "alpha-1",
                "run_status": "RUN_PERSISTED",
                "evidence_status": "HISTORICAL_RESEARCH_EVIDENCE",
                "collection_only": False,
                "research_context_eligible": True,
                "candidate_evidence_eligible": False,
                "foreign_evidence_only": True,
                "requires_foundry_and_evaluator": True,
                "summary": {
                    "RUN_CORE.findings": [
                        "Execution economics vary materially by latency bucket."
                    ],
                    "RUN_CORE.NEXT": "Re-estimate cost sensitivity by regime.",
                },
                "subject": "Alpha Synthesis",
                "execution_authorized": False,
                "production_decision_authorized": False,
            },
            {
                "id": "apex_council",
                "path": "automation_intelligence/agent_fabric/apex_council/latest.json",
                "remote_blob_sha": "d" * 40,
                "run_id": "apex-1",
                "run_status": "RUN_PERSISTED",
                "evidence_status": "HISTORICAL_RESEARCH_EVIDENCE",
                "collection_only": False,
                "research_context_eligible": True,
                "candidate_evidence_eligible": False,
                "foreign_evidence_only": True,
                "requires_foundry_and_evaluator": True,
                "summary": {
                    "RUN_CORE.disagreements_collisions": [
                        "Flow and macro disagree on the persistence horizon."
                    ],
                    "RUN_CORE.NEXT": "Test disagreement resolution by regime.",
                },
                "subject": "Apex Council",
                "execution_authorized": False,
                "production_decision_authorized": False,
            },
            {
                "id": "flow_microstructure",
                "path": "automation_intelligence/flow/latest.json",
                "remote_blob_sha": "e" * 40,
                "run_id": "flow-1",
                "run_status": "RUN_PERSISTED",
                "evidence_status": "HISTORICAL_COLLECTION_EVIDENCE",
                "collection_only": True,
                "research_context_eligible": True,
                "candidate_evidence_eligible": False,
                "foreign_evidence_only": True,
                "requires_foundry_and_evaluator": True,
                "summary": {
                    "DATA_GAPS": ["No direct NQ depth in this run."],
                    "observations": {"BTC": {"funding_percent": 0.003}},
                    "NET_NEW_DELTA": {"btc": "fresh funding evidence"},
                    "source_provenance": [{"source": "venue"}],
                },
                "subject": "Flow Microstructure",
                "execution_authorized": False,
                "production_decision_authorized": False,
            },
        ],
        "truth_contract": {
            "federation_schema": "icarus-engine-brain-federation-v1",
            "historical_context_mode": "RESEARCH_CONTEXT_ONLY",
            "historical_context_never_bypasses_foundry": True,
            "historical_context_never_bypasses_evaluator": True,
            "historical_context_never_grants_shadow_qualification": True,
            "historical_context_never_grants_execution_authority": True,
            "durability_receipts_are_substantive_evidence": False,
            "automatic_model_promotion": False,
            "automatic_execution_authority": False,
            "production_decision_authorized": False,
        },
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


def test_federated_intake_derives_deterministic_bounded_research_prompts():
    one = derive_federated_proposals(_snapshot())
    two = derive_federated_proposals(_snapshot())
    assert one == two
    assert len(one) >= 5
    assert len({row["proposal_id"] for row in one}) == len(one)

    kinds = {row["proposal_kind"] for row in one}
    assert "FINDING_REPLICATION" in kinds
    assert "ROBUSTNESS_INVESTIGATION" in kinds
    assert "DISAGREEMENT_INVESTIGATION" in kinds
    assert "DATA_GAP_INVESTIGATION" in kinds
    assert "OBSERVATION_REPLICATION" in kinds

    for row in one:
        assert row["source_repository"] == "reppiks490/Icarus-engine"
        assert row["source_commit"] == "a" * 40
        assert len(row["source_blob_sha"]) == 40
        assert row["admission_state"] == "RESEARCH_PROMPT_ONLY"
        assert row["research_context_eligible"] is True
        assert row["candidate_evidence_eligible"] is False
        assert row["automatic_candidate_creation"] is False
        assert row["automatic_model_promotion"] is False
        assert row["requires_foundry_and_evaluator"] is True
        assert row["execution_authorized"] is False
        assert row["production_decision_authorized"] is False


def test_intake_rejects_unverified_stale_or_degraded_peer_state():
    for key, value in (
        ("peer_source_commit_verified", False),
        ("peer_packet_fresh", False),
        ("peer_packet_status", "degraded"),
        ("historical_context_status", "degraded"),
    ):
        state = _snapshot()
        state[key] = value
        with pytest.raises(ValueError):
            derive_federated_proposals(state)


def test_intake_rejects_any_historical_candidate_evidence_or_authority_escalation():
    state = _snapshot()
    state["historical_candidate_evidence_count"] = 1
    with pytest.raises(ValueError, match="candidate evidence"):
        derive_federated_proposals(state)

    state = _snapshot()
    state["historical_context_sources"][0]["candidate_evidence_eligible"] = True
    with pytest.raises(ValueError, match="candidate_evidence_eligible"):
        derive_federated_proposals(state)

    state = _snapshot()
    state["historical_context_sources"][0]["execution_authorized"] = True
    with pytest.raises(ValueError, match="authority"):
        derive_federated_proposals(state)


def test_intake_requires_exact_foreign_blob_and_packet_source_revision():
    state = _snapshot()
    state["peer_source_commit"] = "short"
    with pytest.raises(ValueError, match="source commit"):
        derive_federated_proposals(state)

    state = _snapshot()
    state["historical_context_sources"][0]["remote_blob_sha"] = "bad"
    with pytest.raises(ValueError, match="blob"):
        derive_federated_proposals(state)


def test_collection_evidence_cannot_be_rewritten_as_market_truth():
    rows = derive_federated_proposals(_snapshot())
    flow = [row for row in rows if row["source_id"] == "flow_microstructure"]
    assert flow
    assert all(row["source_evidence_status"] == "HISTORICAL_COLLECTION_EVIDENCE" for row in flow)
    assert all(row["claim_status"] == "FOREIGN_CONTEXT_UNVERIFIED_LOCALLY" for row in flow)
    assert all(row["candidate_evidence_eligible"] is False for row in flow)


def test_intake_ledger_is_wal_idempotent_and_append_only(tmp_path):
    lab = FederatedResearchIntake(tmp_path)
    first = lab.ingest(_snapshot())
    second = lab.ingest(_snapshot())

    assert lab.journal_mode == "wal"
    assert first["new_proposal_count"] == len(first["proposals"])
    assert second["new_proposal_count"] == 0
    snap = lab.snapshot()
    assert snap["proposal_count"] == len(first["proposals"])
    assert snap["source_repository_count"] == 1
    assert snap["candidate_evidence_count"] == 0
    assert snap["automatic_candidate_creation"] is False
    assert snap["execution_authorized"] is False
    assert snap["production_decision_authorized"] is False


def test_changed_peer_revision_preserves_prior_prompts_and_creates_new_lineage(tmp_path):
    lab = FederatedResearchIntake(tmp_path)
    first = lab.ingest(_snapshot())

    newer = copy.deepcopy(_snapshot())
    newer["peer_source_commit"] = "f" * 40
    newer["peer_packet_id"] = "2" * 64
    newer["historical_context_sources"][0]["remote_blob_sha"] = "9" * 40
    newer["historical_context_sources"][0]["summary"]["RUN_CORE.findings"] = [
        "Protected holdout lineage is now bound but regime labels drift."
    ]
    second = lab.ingest(newer)

    snap = lab.snapshot()
    assert second["new_proposal_count"] > 0
    assert snap["proposal_count"] > len(first["proposals"])
    assert {"a" * 40, "f" * 40}.issubset(set(snap["source_commits"]))
