from __future__ import annotations

import copy

import pytest

from icarus_engine.ascendancy.governor import EvolutionGovernor, build_governor_plan


def _state():
    a = "a" * 64
    b = "b" * 64
    c = "c" * 64
    d = "d" * 64
    return {
        "foundry": {
            "candidates": [
                {
                    "candidate_id": a,
                    "stage": "TESTING",
                    "origin": "generated_math",
                    "mechanism": {"type": "typed_composition"},
                    "metadata": {"blueprint_id": "bp-used"},
                },
                {
                    "candidate_id": b,
                    "stage": "TESTING",
                    "origin": "generated_math",
                    "mechanism": {"type": "typed_composition"},
                    "metadata": {},
                },
                {
                    "candidate_id": c,
                    "stage": "INCUBATING",
                    "origin": "foreign_lens",
                    "mechanism": {"type": "time_price_geometry"},
                    "metadata": {},
                },
                {
                    "candidate_id": d,
                    "stage": "VALIDATED_RESEARCH",
                    "origin": "native_residual",
                    "mechanism": {"type": "residual_interaction"},
                    "metadata": {},
                },
            ]
        },
        "evaluator": {
            "candidates": [
                {
                    "candidate_id": a,
                    "state": "EVALUATING",
                    "next_stage": "LOW_FIDELITY_REPLAY",
                    "resource_remaining": {"cost_units": 12.0, "evaluations": 20, "wall_seconds": 600},
                },
                {
                    "candidate_id": b,
                    "state": "EVALUATING",
                    "next_stage": "ABLATION",
                    "resource_remaining": {"cost_units": 12.0, "evaluations": 20, "wall_seconds": 600},
                },
                {
                    "candidate_id": d,
                    "state": "READY_FOR_PROTECTED_QUALIFICATION",
                    "next_stage": None,
                    "resource_remaining": {"cost_units": 3.0, "evaluations": 4, "wall_seconds": 120},
                },
            ],
            "holdout_exposures": [],
        },
        "unknowns": {
            "phenomena": [
                {
                    "phenomenon_signature": "u" * 64,
                    "status": "REPLICATED",
                    "candidate_ids": [],
                    "independent_episode_count": 4,
                    "mean_residual_magnitude": 0.8,
                    "failed_explanations": ["volatility scaling only"],
                }
            ]
        },
        "inventions": {
            "blueprints": [
                {
                    "blueprint_id": "bp-used",
                    "status": "UNTESTED_HYPOTHESIS",
                    "estimated_cost_units": 1.0,
                },
                {
                    "blueprint_id": "bp-new",
                    "status": "UNTESTED_HYPOTHESIS",
                    "estimated_cost_units": 1.5,
                },
            ]
        },
        "frontier": {
            "contracts": [
                {
                    "evaluation_contract_hash": "f" * 64,
                    "pareto_genome_ids": ["1" * 64, "2" * 64],
                    "niches": [
                        {
                            "niche_id": "n1",
                            "elite_genome_ids": ["1" * 64],
                            "candidate_count": 4,
                        }
                    ],
                }
            ],
            "stepping_stones": [
                {
                    "genome_id": "3" * 64,
                    "state": "RETIRED",
                    "active_frontier_descendant_ids": ["1" * 64],
                    "informative_even_if_dominated": True,
                }
            ],
        },
        "federation": {
            "status": "green",
            "historical_context_status": "green",
            "historical_candidate_evidence_count": 0,
            "historical_context_sources": [
                {
                    "id": "robustness_guardian",
                    "research_context_eligible": True,
                    "candidate_evidence_eligible": False,
                    "evidence_status": "HISTORICAL_RESEARCH_EVIDENCE",
                    "blob_sha": "9" * 40,
                }
            ],
        },
    }


def _policy(**overrides):
    body = {
        "max_actions_per_cycle": 6,
        "max_estimated_cost_units": 8.0,
        "exploration_fraction": 0.34,
        "max_actions_per_niche": 1,
        "allow_protected_holdout_request": True,
        "allow_federated_context_mining": True,
    }
    body.update(overrides)
    return body


def test_governor_is_deterministic_research_only_and_budget_bounded():
    one = build_governor_plan(_state(), _policy())
    two = build_governor_plan(_state(), _policy())

    assert one["plan_id"] == two["plan_id"]
    assert one["actions"] == two["actions"]
    assert len(one["actions"]) <= 6
    assert one["estimated_cost_units"] <= 8.0
    assert one["execution_authorized"] is False
    assert one["production_decision_authorized"] is False
    assert one["can_mint_evaluator_receipts"] is False
    assert one["can_mint_qualification"] is False
    assert all(x["priority_basis"] == "scheduler_heuristic_not_edge_score" for x in one["actions"])


def test_governor_preserves_diversity_and_reserves_exploration_slots():
    plan = build_governor_plan(
        _state(),
        _policy(max_actions_per_cycle=4, max_estimated_cost_units=10.0, exploration_fraction=0.5),
    )
    assert plan["selected_exploration_actions"] >= 2
    evaluation_actions = [
        x for x in plan["actions"] if x["kind"] == "RUN_EVALUATOR_STAGE"
    ]
    generated_niches = [x["niche_key"] for x in evaluation_actions]
    assert generated_niches.count("generated_math:typed_composition") <= 1
    assert plan["truth_contract"]["diversity_preserved_before_second_pass"] is True


def test_governor_never_fabricates_receipts_or_protected_holdout_identity():
    state = _state()
    state["evaluator"]["candidates"][0]["next_stage"] = "PROTECTED_HOLDOUT"
    plan = build_governor_plan(state, _policy(max_actions_per_cycle=3))
    action = next(x for x in plan["actions"] if x["subject_id"] == "a" * 64)

    assert action["kind"] == "REQUEST_PROTECTED_HOLDOUT"
    assert action["requires_named_holdout"] is True
    assert "holdout_id" not in action
    assert action["requires_external_evidence"] is True
    assert "outcome" not in action
    assert plan["truth_contract"]["governor_never_fabricates_evaluation_outcomes"] is True


def test_governor_routes_unknowns_inventions_and_federated_context_as_research_only():
    plan = build_governor_plan(_state(), _policy(max_actions_per_cycle=10, max_estimated_cost_units=20))
    kinds = {x["kind"] for x in plan["actions"]}

    assert "GENERATE_UNKNOWN_HYPOTHESES" in kinds
    assert "PROMOTE_BLUEPRINT_TO_FOUNDRY" in kinds
    assert "MINE_FEDERATED_CONTEXT" in kinds

    fed = next(x for x in plan["actions"] if x["kind"] == "MINE_FEDERATED_CONTEXT")
    assert fed["candidate_evidence_eligible"] is False
    assert fed["requires_foundry_and_evaluator"] is True
    assert fed["execution_authorized"] is False


def test_ready_candidate_is_only_routed_to_independent_qualification():
    plan = build_governor_plan(_state(), _policy(max_actions_per_cycle=10, max_estimated_cost_units=20))
    row = next(x for x in plan["actions"] if x["subject_id"] == "d" * 64)

    assert row["kind"] == "SUBMIT_FOR_INDEPENDENT_QUALIFICATION"
    assert row["governor_can_qualify"] is False
    assert row["requires_external_authority"] == "protected_candidate_qualification"


def test_unregistered_incubating_candidate_is_enrolled_not_evaluated():
    plan = build_governor_plan(_state(), _policy(max_actions_per_cycle=10, max_estimated_cost_units=20))
    row = next(x for x in plan["actions"] if x["subject_id"] == "c" * 64)
    assert row["kind"] == "REGISTER_WITH_EVALUATOR"
    assert row["requires_external_evidence"] is False


def test_governor_persistence_is_wal_idempotent_and_append_only(tmp_path):
    gov = EvolutionGovernor(tmp_path)
    state = _state()
    first = gov.plan(state, _policy())
    second = gov.plan(state, _policy())

    assert gov.journal_mode == "wal"
    assert first["idempotent"] is False
    assert second["idempotent"] is True
    assert first["plan"]["plan_id"] == second["plan"]["plan_id"]

    changed = copy.deepcopy(state)
    changed["unknowns"]["phenomena"][0]["independent_episode_count"] = 5
    third = gov.plan(changed, _policy())
    assert third["idempotent"] is False
    snap = gov.snapshot()
    assert snap["cycle_count"] == 2
    assert snap["latest_plan_id"] == third["plan"]["plan_id"]
    assert snap["execution_authorized"] is False
    assert snap["production_decision_authorized"] is False


def test_governor_rejects_policy_that_would_make_it_an_authority():
    with pytest.raises(ValueError, match="authority"):
        build_governor_plan(_state(), {**_policy(), "execution_authorized": True})
    with pytest.raises(ValueError, match="qualification"):
        build_governor_plan(_state(), {**_policy(), "can_mint_qualification": True})
