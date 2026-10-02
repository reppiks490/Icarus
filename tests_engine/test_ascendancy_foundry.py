from __future__ import annotations

import pytest

from icarus_engine.ascendancy.foundry import CandidateFoundry, normalize_candidate


def _candidate(**overrides):
    body = {
        "origin": "generated_math",
        "source_repo": "reppiks490/Icarus",
        "source_commit": "c" * 40,
        "title": "Information-time phase compression",
        "hypothesis": "A state-dependent information clock improves reversal-state separation.",
        "mechanism": {
            "type": "representation_mutation",
            "inputs": ["price", "information_time", "volatility_time"],
            "transform": "phase_compression",
            "outputs": ["compressed_phase"],
        },
        "expected_advantage": {
            "target": "incremental_information",
            "direction": "increase",
            "scope": "NQ:RTH",
        },
        "required_observations": [
            {"name": "price", "evidence_class": "observed"},
            {"name": "information_time", "evidence_class": "derived"},
        ],
        "falsifiers": [
            "protected OOS incremental information is nonpositive",
            "effect disappears under regime-stratified replay",
        ],
        "parent_candidate_ids": [],
        "parent_genome_ids": [],
        "evaluation_contract": {
            "objectives": [
                {"name": "incremental_information", "direction": "max"},
                {"name": "instability", "direction": "min"},
            ],
            "descriptor_keys": ["regime", "complexity_band"],
            "protected_holdout_required": True,
        },
        "resource_budget": {
            "max_evaluations": 64,
            "max_wall_seconds": 1800,
            "max_cost_units": 25.0,
        },
        "metadata": {
            "research_question": "Does information-time geometry add state separation beyond current ICARUS?",
        },
    }
    body.update(overrides)
    return body


def test_candidate_normalization_is_deterministic_and_research_only():
    one = normalize_candidate(_candidate())
    two = normalize_candidate(_candidate())
    assert one["candidate_id"] == two["candidate_id"]
    assert len(one["candidate_id"]) == 64
    assert one["stage"] == "PROPOSED"
    assert one["execution_authorized"] is False
    assert one["production_decision_authorized"] is False
    assert one["broker_authority"] is False


def test_candidate_requires_falsifiers_and_exact_git_provenance():
    with pytest.raises(ValueError, match="falsifier"):
        normalize_candidate(_candidate(falsifiers=[]))
    with pytest.raises(ValueError, match="40-character Git SHA"):
        normalize_candidate(_candidate(source_commit="short"))


def test_candidate_observations_require_explicit_evidence_classes():
    bad = _candidate()
    bad["required_observations"][0] = {"name": "price"}
    with pytest.raises(ValueError, match="evidence_class"):
        normalize_candidate(bad)

    unavailable = _candidate()
    unavailable["required_observations"].append(
        {"name": "private_order_flow", "evidence_class": "unavailable"}
    )
    row = normalize_candidate(unavailable)
    unavailable_row = next(x for x in row["required_observations"] if x["name"] == "private_order_flow")
    assert unavailable_row["usable_for_confirmation"] is False


def test_foundry_is_wal_idempotent_and_preserves_rejections(tmp_path):
    foundry = CandidateFoundry(tmp_path)
    candidate = normalize_candidate(_candidate())
    first = foundry.register(candidate)
    second = foundry.register(candidate)

    assert foundry.journal_mode == "wal"
    assert first["idempotent"] is False
    assert second["idempotent"] is True
    assert foundry.snapshot()["candidate_count"] == 1

    rejected = foundry.reject(candidate["candidate_id"], "failed mechanism plausibility review")
    assert rejected["stage"] == "REJECTED"
    snap = foundry.snapshot()
    assert snap["candidates"][0]["stage"] == "REJECTED"
    assert snap["lifecycle_events"][-1]["reason"] == "failed mechanism plausibility review"
    assert snap["execution_authorized"] is False
    assert snap["production_decision_authorized"] is False


def test_foundry_preserves_parent_candidate_lineage(tmp_path):
    foundry = CandidateFoundry(tmp_path)
    parent = normalize_candidate(_candidate(title="parent"))
    foundry.register(parent)

    child_body = _candidate(
        title="child",
        hypothesis="A descendant interaction hypothesis.",
        parent_candidate_ids=[parent["candidate_id"]],
    )
    child = normalize_candidate(child_body)
    foundry.register(child)

    snap = foundry.snapshot()
    assert snap["lineage"] == [{
        "parent_candidate_id": parent["candidate_id"],
        "child_candidate_id": child["candidate_id"],
    }]


def test_identical_semantics_under_different_origin_are_distinct_candidates():
    one = normalize_candidate(_candidate(origin="generated_math"))
    two = normalize_candidate(_candidate(origin="foreign_lens"))
    assert one["candidate_id"] != two["candidate_id"]


def test_candidate_requires_bounded_resource_budget_and_holdout():
    bad_budget = _candidate()
    bad_budget["resource_budget"]["max_evaluations"] = 0
    with pytest.raises(ValueError, match="max_evaluations"):
        normalize_candidate(bad_budget)

    bad_contract = _candidate()
    bad_contract["evaluation_contract"]["protected_holdout_required"] = False
    with pytest.raises(ValueError, match="protected holdout"):
        normalize_candidate(bad_contract)


def test_candidate_rejects_authority_escalation(tmp_path):
    body = _candidate()
    body["execution_authorized"] = True
    with pytest.raises(ValueError, match="authority"):
        normalize_candidate(body)

    foundry = CandidateFoundry(tmp_path)
    candidate = normalize_candidate(_candidate())
    foundry.register(candidate)
    with pytest.raises(ValueError, match="terminal"):
        foundry.advance(candidate["candidate_id"], "QUALIFIED_SHADOW", "skip directly to qualified")


def test_candidate_advancement_is_monotonic_and_reasoned(tmp_path):
    foundry = CandidateFoundry(tmp_path)
    candidate = normalize_candidate(_candidate())
    foundry.register(candidate)

    incubating = foundry.advance(candidate["candidate_id"], "INCUBATING", "mechanism review passed")
    assert incubating["stage"] == "INCUBATING"
    testing = foundry.advance(candidate["candidate_id"], "TESTING", "evaluation runtime constructed")
    assert testing["stage"] == "TESTING"

    with pytest.raises(ValueError, match="backward"):
        foundry.advance(candidate["candidate_id"], "INCUBATING", "regress stage")

    with pytest.raises(ValueError, match="reason"):
        foundry.advance(candidate["candidate_id"], "VALIDATED_RESEARCH", "")
