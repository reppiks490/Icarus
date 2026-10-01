from __future__ import annotations

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from icarus_engine.pantheon import AetherSwarm, PantheonKernel, subsystem_context
from icarus_engine.pantheon.bridge import oracle_context, psi_context
from icarus_engine.pantheon.contracts import iso_aware


def _payload(**overrides):
    payload = {
        "observed_at": "2026-10-01T06:00:00Z",
        "asset": "NQ",
        "horizon_ms": 15000,
        "source_commit": "a" * 40,
        "evidence": ["fixture:synthetic-shadow"],
        "signals": {
            "expected_response": -1.0,
            "observed_response": -0.10,
            "absorber_strength": 0.80,
            "relationship_validity": 0.95,
            "world_scores": {"accumulation": 0.51, "distribution": 0.49},
            "diagnostic_values": {"nq_qqq_basis": 0.91, "queue_replenishment": 0.82},
            "transition_cost_up": 0.25,
            "transition_cost_down": 2.20,
            "perturbation_margin": 0.82,
            "data_sensitivity": 0.10,
            "execution_sensitivity": 0.15,
            "thesis_fragility": 0.18,
            "novelty": 0.90,
            "representation_error": 0.88,
            "cross_regime_invariance": 0.70,
            "data_quality": 0.95,
            "risk": 0.20,
            "engine_scores": {"oracle": 0.91, "nullspace": -0.84, "ananke": 0.77},
            "engine_reliability": {"oracle": 0.80, "nullspace": 0.85, "ananke": 0.75},
            "candidate_expressions": [
                {
                    "name": "nq_es_relative_value",
                    "expected_gross": 600.0,
                    "costs": 80.0,
                    "risk_capital": 5000.0,
                    "duration_seconds": 90.0,
                    "capacity_remaining": 0.90,
                },
                {
                    "name": "outright_nq",
                    "expected_gross": 410.0,
                    "costs": 70.0,
                    "risk_capital": 7000.0,
                    "duration_seconds": 300.0,
                    "capacity_remaining": 0.80,
                },
            ],
        },
        "subsystem_outputs": {
            "oracle": {"source": "external/native", "pressure": 0.91},
            "parallax": {"source": "native", "decision_id": "fixture"},
        },
    }
    payload.update(overrides)
    return payload


def test_pantheon_runs_independent_faculties_and_never_grants_execution(tmp_path):
    kernel = PantheonKernel(tmp_path)
    obs = kernel.record_observation(_payload())
    analysis = obs["analysis"]
    assert set(analysis["faculties"]) == {
        "nullspace", "godel", "ananke", "nemesis", "ex_nihilo", "mint", "echo", "veritas", "archon", "socrates"
    }
    assert analysis["faculties"]["nullspace"]["routing_state"] == "absorbed"
    assert analysis["faculties"]["nullspace"]["debt_state"] == "absorbed"
    assert analysis["faculties"]["nullspace"]["repayment_pressure"] >= 0
    assert analysis["faculties"]["godel"]["identifiability"] < 0.01
    assert analysis["faculties"]["godel"]["epistemic_blindspot"] is True
    assert analysis["faculties"]["godel"]["effective_world_count"] > 1.9
    assert analysis["faculties"]["ananke"]["least_cost_direction"] == "up"
    assert analysis["faculties"]["ananke"]["reachable_space_collapse"] > 0
    assert analysis["faculties"]["nemesis"]["survival_score"] > 0.70
    assert analysis["faculties"]["nemesis"]["edge_half_life_source"] == "unmeasured"
    assert analysis["faculties"]["nemesis"]["dreamstate_curriculum"]
    assert analysis["faculties"]["ex_nihilo"]["new_phenomenon_candidate"] is True
    assert analysis["faculties"]["mint"]["best_candidate"]["name"] == "nq_es_relative_value"
    assert analysis["faculties"]["mint"]["best_candidate"]["stress_expected_net"] > 0
    assert analysis["faculties"]["mint"]["best_candidate"]["alpha_metabolism"]["stress_net_conversion"] > 0
    assert analysis["faculties"]["mint"]["profit_surface"]["robust_positive_count"] >= 1
    assert analysis["faculties"]["mint"]["profit_chain"]
    assert analysis["faculties"]["socrates"]["question_queue"]
    assert analysis["faculties"]["socrates"]["hypothesis_queue"]
    assert analysis["faculties"]["archon"]["contradiction"] > 0.80
    assert 0 <= analysis["faculties"]["archon"]["attention_concentration"] <= 1
    assert analysis["faculties"]["archon"]["consensus_forced"] is False
    assert analysis["authority"]["execution_authorized"] is False
    assert analysis["authority"]["production_decision_authorized"] is False
    assert all(not lease["execution_authorized"] for lease in analysis["faculties"]["archon"]["leases"])


def test_echo_detects_consensus_illusion_and_archon_discounts_shared_evidence(tmp_path):
    payload = _payload(observation_id="pan-echo-illusion")
    payload["signals"] = dict(payload["signals"])
    payload["signals"]["engine_scores"] = {"oracle": 0.90, "athena": 0.86, "argus": 0.82}
    payload["signals"]["engine_reliability"] = {"oracle": 0.90, "athena": 0.88, "argus": 0.84}
    payload["signals"]["engine_evidence_lineage"] = {
        "oracle": ["databento:nq:mbp10", "qqq:1m"],
        "athena": ["databento:nq:mbp10", "qqq:1m"],
        "argus": ["databento:nq:mbp10", "qqq:1m"],
    }
    kernel = PantheonKernel(tmp_path, swarm=AetherSwarm(threshold=0.0, max_agents=8))
    obs = kernel.record_observation(payload)
    echo_state = obs["analysis"]["faculties"]["echo"]
    archon_state = obs["analysis"]["faculties"]["archon"]
    swarm = obs["analysis"]["aether"]

    assert echo_state["status"] == "active"
    assert echo_state["raw_directional_agreement"] == pytest.approx(1.0)
    assert echo_state["mean_lineage_overlap"] == pytest.approx(1.0)
    assert echo_state["effective_independence_factor"] == pytest.approx(1.0 / 3.0)
    assert echo_state["echo_risk"] == pytest.approx(2.0 / 3.0)
    assert echo_state["consensus_illusion_candidate"] is True
    assert echo_state["effective_independent_support"] == pytest.approx(1.0 / 3.0)
    assert len(echo_state["duplicated_ancestry_pairs"]) == 3
    assert all(value == pytest.approx(1.0 / 3.0) for value in echo_state["engine_independence"].values())
    assert archon_state["evidence_independence_discounted"] is True
    assert archon_state["consensus_illusion_candidate"] is True
    assert all(row["evidence_independence"] == pytest.approx(1.0 / 3.0) for row in archon_state["engine_states"])
    assert swarm["field"]["echo_risk"] == pytest.approx(2.0 / 3.0)
    assert "redundancy_hunter" in {agent["role"] for agent in swarm["agents"]}
    assert swarm["authority"]["execution_authorized"] is False


def test_echo_preserves_genuinely_independent_confirmation(tmp_path):
    payload = _payload(observation_id="pan-echo-independent")
    payload["signals"] = dict(payload["signals"])
    payload["signals"]["engine_scores"] = {"oracle": 0.90, "athena": 0.86, "argus": 0.82}
    payload["signals"]["engine_reliability"] = {"oracle": 0.90, "athena": 0.88, "argus": 0.84}
    payload["signals"]["engine_evidence_lineage"] = {
        "oracle": ["orderbook:nq"],
        "athena": ["options:dealer-gamma"],
        "argus": ["macro:rates"],
    }
    obs = PantheonKernel(tmp_path).record_observation(payload)
    echo_state = obs["analysis"]["faculties"]["echo"]
    archon_state = obs["analysis"]["faculties"]["archon"]

    assert echo_state["raw_directional_agreement"] == pytest.approx(1.0)
    assert echo_state["mean_lineage_overlap"] == pytest.approx(0.0)
    assert echo_state["effective_independence_factor"] == pytest.approx(1.0)
    assert echo_state["echo_risk"] == pytest.approx(0.0)
    assert echo_state["effective_independent_support"] == pytest.approx(1.0)
    assert echo_state["consensus_illusion_candidate"] is False
    assert echo_state["duplicated_ancestry_pairs"] == []
    assert all(value == pytest.approx(1.0) for value in echo_state["engine_independence"].values())
    assert all(row["evidence_independence"] == pytest.approx(1.0) for row in archon_state["engine_states"])


def test_echo_without_any_lineage_fails_closed_and_archon_grants_no_attention(tmp_path):
    payload = _payload(observation_id="pan-echo-no-lineage")
    payload["signals"] = dict(payload["signals"])
    payload["signals"].pop("engine_evidence_lineage", None)
    payload["signals"]["engine_scores"] = {"oracle": 0.90, "athena": 0.86, "argus": 0.82}
    payload["signals"]["engine_reliability"] = {"oracle": 0.90, "athena": 0.88, "argus": 0.84}

    obs = PantheonKernel(tmp_path).record_observation(payload)
    echo_state = obs["analysis"]["faculties"]["echo"]
    archon_state = obs["analysis"]["faculties"]["archon"]

    assert echo_state["status"] == "abstain"
    assert echo_state["lineage_verified"] is False
    assert echo_state["unresolved_lineage_fraction"] == pytest.approx(1.0)
    assert echo_state["effective_independence_factor"] == pytest.approx(0.0)
    assert echo_state["effective_independent_support"] == pytest.approx(0.0)
    assert set(echo_state["engine_independence"]) == {"oracle", "athena", "argus"}
    assert all(value == 0.0 for value in echo_state["engine_independence"].values())
    assert archon_state["evidence_independence_discounted"] is True
    assert all(row["evidence_independence"] == 0.0 for row in archon_state["engine_states"])
    assert all(row["attention_weight"] == 0.0 for row in archon_state["engine_states"])
    assert archon_state["leases"] == []
    assert archon_state["authority"]["execution_authorized"] is False


def test_echo_treats_missing_lineage_as_unproven_independence(tmp_path):
    payload = _payload(observation_id="pan-echo-missing-lineage")
    payload["signals"] = dict(payload["signals"])
    payload["signals"]["engine_scores"] = {"oracle": 0.90, "athena": 0.86, "argus": 0.82}
    payload["signals"]["engine_reliability"] = {"oracle": 0.90, "athena": 0.88, "argus": 0.84}
    payload["signals"]["engine_evidence_lineage"] = {
        "oracle": ["orderbook:nq"],
        "athena": ["options:dealer-gamma"],
    }
    obs = PantheonKernel(tmp_path).record_observation(payload)
    echo_state = obs["analysis"]["faculties"]["echo"]
    assert echo_state["unresolved_lineage_fraction"] > 0
    assert echo_state["engine_independence"]["argus"] == 0.0
    assert echo_state["effective_independence_factor"] < 1.0
    assert echo_state["echo_risk"] > 0.0


def test_echo_fails_closed_on_malformed_lineage(tmp_path):
    payload = _payload(observation_id="pan-echo-invalid")
    payload["signals"] = dict(payload["signals"])
    payload["signals"]["engine_evidence_lineage"] = {"oracle": {"not": "a-list"}}
    with pytest.raises(ValueError, match="engine_evidence_lineage.oracle"):
        PantheonKernel(tmp_path).record_observation(payload)


def _veritas_payload(observation_id: str = "pan-veritas") -> dict:
    payload = _payload(observation_id=observation_id)
    payload["signals"] = dict(payload["signals"])
    payload["signals"]["mechanism_certificate"] = {
        "mechanism_id": "dealer-hedging-followthrough",
        "thesis": "dealer hedging drives the directional move and should leave the declared path signatures",
        "direction": "long",
        "confidence": 0.8,
        "fidelity_threshold": 0.70,
        "min_reconciliation_confidence": 0.65,
        "expected_signatures": [
            {"key": "basis_expands", "operator": "truthy", "weight": 0.4},
            {"key": "queue_replenishment", "operator": "gte", "threshold": 0.6, "weight": 0.35},
            {"key": "cross_asset_lead", "operator": "positive", "weight": 0.25},
        ],
        "invalidators": ["basis compresses while price rises", "queue replenishment disappears"],
        "invalidating_signatures": [
            {"key": "basis_compression", "operator": "truthy", "weight": 1.0},
        ],
    }
    return payload


def _veritas_source_payload(
    observation_id: str,
    observed_at: str,
    realized_direction: str = "long",
    **signatures,
) -> dict:
    payload = _payload(observation_id=observation_id, observed_at=observed_at)
    payload["signals"] = dict(payload["signals"])
    payload["signals"]["veritas_realized_direction"] = realized_direction
    payload["signals"].update(signatures)
    return payload


def test_veritas_freezes_falsifiable_mechanism_certificate(tmp_path):
    kernel = PantheonKernel(tmp_path)
    obs = kernel.record_observation(_veritas_payload())
    state = obs["analysis"]["faculties"]["veritas"]
    assert state["status"] == "active"
    assert state["certificate_id"].startswith("ver-")
    assert state["mechanism_id"] == "dealer-hedging-followthrough"
    assert state["reconciliation_state"] == "pending"
    assert state["reinforcement_eligible"] is False
    assert len(state["expected_signatures"]) == 3
    assert obs["veritas_reconciliation"]["status"] == "pending"
    assert obs["analysis"]["authority"]["execution_authorized"] is False


def test_veritas_distinguishes_right_reasons_from_lucky_direction(tmp_path):
    kernel = PantheonKernel(tmp_path)
    obs = kernel.record_observation(_veritas_payload("pan-veritas-right"))
    source = kernel.record_observation(_veritas_source_payload(
        "pan-veritas-right-source",
        "2026-10-01T06:00:20Z",
        basis_expands=True,
        queue_replenishment=0.8,
        cross_asset_lead=0.2,
    ))
    right = kernel.record_veritas_reconciliation({
        "observation_id": obs["observation_id"],
        "source_observation_id": source["observation_id"],
        "observed_at": source["observed_at"],
        "confidence": 0.9,
        "evidence": ["fixture:all-predicted-signatures-observed"],
    })
    score = right["reconciliation"]["score"]
    assert score["classification"] == "right_for_right_reasons"
    assert score["mechanism_fidelity"] == pytest.approx(1.0)
    assert score["reinforcement_eligible"] is True
    assert score["lucky_outcome_quarantine"] is False
    assert score["learning_credit"] == pytest.approx(0.9)

    obs2 = kernel.record_observation(_veritas_payload("pan-veritas-lucky"))
    source2 = kernel.record_observation(_veritas_source_payload(
        "pan-veritas-lucky-source",
        "2026-10-01T06:00:20Z",
        basis_expands=False,
        queue_replenishment=0.1,
        cross_asset_lead=-0.3,
    ))
    lucky = kernel.record_veritas_reconciliation({
        "observation_id": obs2["observation_id"],
        "source_observation_id": source2["observation_id"],
        "observed_at": source2["observed_at"],
        "realized_direction": "long",
        "confidence": 0.9,
        "evidence": ["fixture:direction-right-path-wrong"],
    })
    lucky_score = lucky["reconciliation"]["score"]
    assert lucky_score["classification"] == "right_for_wrong_reasons"
    assert lucky_score["mechanism_fidelity"] == pytest.approx(0.0)
    assert lucky_score["reinforcement_eligible"] is False
    assert lucky_score["lucky_outcome_quarantine"] is True
    assert lucky_score["learning_credit"] == pytest.approx(0.0)


def test_veritas_mechanism_can_match_even_when_endpoint_fails(tmp_path):
    kernel = PantheonKernel(tmp_path)
    obs = kernel.record_observation(_veritas_payload("pan-veritas-endpoint-fail"))
    source = kernel.record_observation(_veritas_source_payload(
        "pan-veritas-endpoint-fail-source",
        "2026-10-01T06:00:20Z",
        realized_direction="short",
        basis_expands=True,
        queue_replenishment=0.7,
        cross_asset_lead=0.1,
    ))
    state = kernel.record_veritas_reconciliation({
        "observation_id": obs["observation_id"],
        "source_observation_id": source["observation_id"],
        "observed_at": source["observed_at"],
        "confidence": 0.8,
        "evidence": ["fixture:path-matched-endpoint-failed"],
    })
    score = state["reconciliation"]["score"]
    assert score["classification"] == "mechanism_without_endpoint"
    assert score["mechanism_fidelity"] == pytest.approx(1.0)
    assert score["reinforcement_eligible"] is False
    assert score["learning_credit"] == pytest.approx(0.0)


def test_veritas_low_confidence_right_reasons_are_not_reinforced(tmp_path):
    kernel = PantheonKernel(tmp_path)
    obs = kernel.record_observation(_veritas_payload("pan-veritas-low-confidence"))
    source = kernel.record_observation(_veritas_source_payload(
        "pan-veritas-low-confidence-source",
        "2026-10-01T06:00:20Z",
        basis_expands=True,
        queue_replenishment=0.8,
        cross_asset_lead=0.2,
    ))
    state = kernel.record_veritas_reconciliation({
        "observation_id": obs["observation_id"],
        "source_observation_id": source["observation_id"],
        "observed_at": source["observed_at"],
        "confidence": 0.20,
        "evidence": ["fixture:low-confidence-right-path"],
    })
    score = state["reconciliation"]["score"]
    assert score["classification"] == "right_for_right_reasons"
    assert score["mechanism_fidelity"] == pytest.approx(1.0)
    assert score["confidence_gate_passed"] is False
    assert score["reinforcement_eligible"] is False
    assert score["learning_credit"] == pytest.approx(0.0)


def test_veritas_refuses_trivial_reconciliation_confidence_gate(tmp_path):
    payload = _veritas_payload("pan-veritas-low-confidence-gate")
    payload["signals"]["mechanism_certificate"]["min_reconciliation_confidence"] = 0.1
    with pytest.raises(ValueError, match="min_reconciliation_confidence must be at least 0.50"):
        PantheonKernel(tmp_path).record_observation(payload)


def test_veritas_machine_invalidator_overrides_signature_fidelity(tmp_path):
    kernel = PantheonKernel(tmp_path)
    obs = kernel.record_observation(_veritas_payload("pan-veritas-invalidator"))
    source = kernel.record_observation(_veritas_source_payload(
        "pan-veritas-invalidator-source",
        "2026-10-01T06:00:20Z",
        basis_expands=True,
        queue_replenishment=0.8,
        cross_asset_lead=0.2,
        basis_compression=True,
    ))
    state = kernel.record_veritas_reconciliation({
        "observation_id": obs["observation_id"],
        "source_observation_id": source["observation_id"],
        "observed_at": source["observed_at"],
        "confidence": 0.9,
        "evidence": ["fixture:invalidator-triggered"],
    })
    score = state["reconciliation"]["score"]
    assert score["mechanism_fidelity"] == pytest.approx(1.0)
    assert score["invalidator_triggered"] is True
    assert score["triggered_invalidators"] == ["basis_compression"]
    assert score["mechanism_match"] is False
    assert score["classification"] == "right_for_wrong_reasons"
    assert score["reinforcement_eligible"] is False
    assert score["lucky_outcome_quarantine"] is True


def test_veritas_reconciliation_is_maturity_bound_idempotent_and_immutable(tmp_path):
    kernel = PantheonKernel(tmp_path)
    obs = kernel.record_observation(_veritas_payload("pan-veritas-immutable"))
    source = kernel.record_observation(_veritas_source_payload(
        "pan-veritas-immutable-source",
        "2026-10-01T06:00:20Z",
        basis_expands=True,
        queue_replenishment=0.7,
        cross_asset_lead=0.1,
    ))
    body = {
        "observation_id": obs["observation_id"],
        "source_observation_id": source["observation_id"],
        "observed_at": source["observed_at"],
        "realized_direction": "long",
        "confidence": 0.75,
        "evidence": ["fixture:immutable"],
    }
    first = kernel.record_veritas_reconciliation(body)
    again = kernel.record_veritas_reconciliation(body)
    assert again == first

    kernel.record_observation(_veritas_payload("pan-veritas-early"))
    early_source = kernel.record_observation(_veritas_source_payload(
        "pan-veritas-early-source",
        "2026-10-01T06:00:05Z",
        basis_expands=True,
        queue_replenishment=0.7,
        cross_asset_lead=0.1,
    ))
    too_early = dict(
        body,
        observation_id="pan-veritas-early",
        source_observation_id=early_source["observation_id"],
        observed_at=early_source["observed_at"],
    )
    with pytest.raises(ValueError, match="maturity"):
        kernel.record_veritas_reconciliation(too_early)

    changed = dict(body, confidence=0.6)
    with pytest.raises(ValueError, match="immutable"):
        kernel.record_veritas_reconciliation(changed)


def test_veritas_reconciliation_is_bound_to_immutable_source_observation(tmp_path):
    kernel = PantheonKernel(tmp_path)
    obs = kernel.record_observation(_veritas_payload("pan-veritas-source-bound"))
    source = kernel.record_observation(_veritas_source_payload(
        "pan-veritas-source-bound-later",
        "2026-10-01T06:00:20Z",
        basis_expands=True,
        queue_replenishment=0.8,
        cross_asset_lead=0.2,
    ))
    with pytest.raises(ValueError, match="must match source observation time"):
        kernel.record_veritas_reconciliation({
            "observation_id": obs["observation_id"],
            "source_observation_id": source["observation_id"],
            "observed_at": "2026-10-01T06:00:21Z",
            "confidence": 0.8,
            "evidence": ["fixture:mismatched-time"],
        })

    other = _veritas_source_payload(
        "pan-veritas-source-other-asset",
        "2026-10-01T06:00:20Z",
        basis_expands=True,
        queue_replenishment=0.8,
        cross_asset_lead=0.2,
    )
    other["asset"] = "ES"
    other_obs = kernel.record_observation(other)
    with pytest.raises(ValueError, match="asset must match"):
        kernel.record_veritas_reconciliation({
            "observation_id": obs["observation_id"],
            "source_observation_id": other_obs["observation_id"],
            "observed_at": other_obs["observed_at"],
            "realized_direction": "long",
            "confidence": 0.8,
            "evidence": ["fixture:wrong-asset"],
        })


def test_veritas_source_must_immutably_declare_realized_direction(tmp_path):
    kernel = PantheonKernel(tmp_path)
    obs = kernel.record_observation(_veritas_payload("pan-veritas-source-direction"))
    source = _payload(
        observation_id="pan-veritas-source-direction-later",
        observed_at="2026-10-01T06:00:20Z",
    )
    source["signals"] = dict(source["signals"])
    source["signals"].update({
        "basis_expands": True,
        "queue_replenishment": 0.8,
        "cross_asset_lead": 0.2,
    })
    source_obs = kernel.record_observation(source)
    with pytest.raises(ValueError, match="veritas_realized_direction"):
        kernel.record_veritas_reconciliation({
            "observation_id": obs["observation_id"],
            "source_observation_id": source_obs["observation_id"],
            "observed_at": source_obs["observed_at"],
            "confidence": 0.8,
            "evidence": ["fixture:missing-endpoint"],
        })


def test_veritas_refuses_trivial_fidelity_threshold(tmp_path):
    payload = _veritas_payload("pan-veritas-low-threshold")
    payload["signals"]["mechanism_certificate"]["fidelity_threshold"] = 0.1
    with pytest.raises(ValueError, match="at least 0.50"):
        PantheonKernel(tmp_path).record_observation(payload)


def _monetization_claim(observation: dict) -> dict:
    return next(claim for claim in observation["claims"] if claim["kind"] == "monetization_candidate")


def test_veritas_quarantines_lucky_positive_monetization_fitness(tmp_path):
    kernel = PantheonKernel(tmp_path)
    origin = kernel.record_observation(_veritas_payload("pan-veritas-fitness-lucky"))
    claim = _monetization_claim(origin)
    source = kernel.record_observation(_veritas_source_payload(
        "pan-veritas-fitness-lucky-source",
        "2026-10-01T06:00:20Z",
        basis_expands=False,
        queue_replenishment=0.1,
        cross_asset_lead=-0.2,
    ))

    with pytest.raises(ValueError, match="requires VERITAS reconciliation"):
        kernel.record_claim_outcome({
            "claim_id": claim["claim_id"],
            "observed_at": source["observed_at"],
            "utility": 0.8,
            "confidence": 0.9,
            "_source_observation_id": source["observation_id"],
            "evidence": ["fixture:profitable-before-veritas"],
        })

    kernel.record_veritas_reconciliation({
        "observation_id": origin["observation_id"],
        "source_observation_id": source["observation_id"],
        "observed_at": source["observed_at"],
        "confidence": 0.9,
        "evidence": ["fixture:lucky-path-failed"],
    })
    outcome = kernel.record_claim_outcome({
        "claim_id": claim["claim_id"],
        "observed_at": source["observed_at"],
        "utility": 0.8,
        "confidence": 0.9,
        "_source_observation_id": source["observation_id"],
        "evidence": ["fixture:profitable-after-veritas"],
    })
    assert outcome["utility"] == pytest.approx(0.8)
    assert outcome["fitness_utility"] == pytest.approx(0.0)
    assert outcome["veritas_gate"] == "positive_outcome_quarantined"
    assert outcome["fitness_credit"] == pytest.approx(0.0)


def test_veritas_allows_positive_monetization_fitness_only_for_right_reasons(tmp_path):
    kernel = PantheonKernel(tmp_path)
    origin = kernel.record_observation(_veritas_payload("pan-veritas-fitness-right"))
    claim = _monetization_claim(origin)
    source = kernel.record_observation(_veritas_source_payload(
        "pan-veritas-fitness-right-source",
        "2026-10-01T06:00:20Z",
        basis_expands=True,
        queue_replenishment=0.8,
        cross_asset_lead=0.2,
    ))
    kernel.record_veritas_reconciliation({
        "observation_id": origin["observation_id"],
        "source_observation_id": source["observation_id"],
        "observed_at": source["observed_at"],
        "confidence": 0.9,
        "evidence": ["fixture:right-reasons"],
    })
    outcome = kernel.record_claim_outcome({
        "claim_id": claim["claim_id"],
        "observed_at": source["observed_at"],
        "utility": 0.8,
        "confidence": 0.9,
        "_source_observation_id": source["observation_id"],
        "evidence": ["fixture:profitable-right-reasons"],
    })
    assert outcome["fitness_utility"] == pytest.approx(0.8)
    assert outcome["veritas_gate"] == "right_for_right_reasons"
    assert outcome["fitness_credit"] == pytest.approx(0.8)


def test_veritas_positive_fitness_requires_same_reconciliation_source(tmp_path):
    kernel = PantheonKernel(tmp_path)
    origin = kernel.record_observation(_veritas_payload("pan-veritas-fitness-source"))
    claim = _monetization_claim(origin)
    source = kernel.record_observation(_veritas_source_payload(
        "pan-veritas-fitness-source-good",
        "2026-10-01T06:00:20Z",
        basis_expands=True,
        queue_replenishment=0.8,
        cross_asset_lead=0.2,
    ))
    other = kernel.record_observation(_veritas_source_payload(
        "pan-veritas-fitness-source-other",
        "2026-10-01T06:00:21Z",
        basis_expands=True,
        queue_replenishment=0.8,
        cross_asset_lead=0.2,
    ))
    kernel.record_veritas_reconciliation({
        "observation_id": origin["observation_id"],
        "source_observation_id": source["observation_id"],
        "observed_at": source["observed_at"],
        "confidence": 0.9,
        "evidence": ["fixture:right-reasons-source"],
    })
    with pytest.raises(ValueError, match="source must match reconciliation source"):
        kernel.record_claim_outcome({
            "claim_id": claim["claim_id"],
            "observed_at": other["observed_at"],
            "utility": 0.8,
            "confidence": 0.9,
            "_source_observation_id": other["observation_id"],
            "evidence": ["fixture:wrong-positive-source"],
        })


def test_veritas_never_hides_negative_monetization_fitness(tmp_path):
    kernel = PantheonKernel(tmp_path)
    origin = kernel.record_observation(_veritas_payload("pan-veritas-fitness-loss"))
    claim = _monetization_claim(origin)
    outcome = kernel.record_claim_outcome({
        "claim_id": claim["claim_id"],
        "observed_at": "2026-10-01T06:00:20Z",
        "utility": -0.6,
        "confidence": 0.9,
        "evidence": ["fixture:loss-counts-without-veritas"],
    })
    assert outcome["fitness_utility"] == pytest.approx(-0.6)
    assert outcome["veritas_gate"] == "negative_outcome_counts"
    assert outcome["fitness_credit"] == pytest.approx(-0.6)


def test_claim_outcome_persists_source_observation_provenance(tmp_path):
    kernel = PantheonKernel(tmp_path)
    origin = kernel.record_observation(_veritas_payload("pan-veritas-source-provenance"))
    claim = _monetization_claim(origin)
    source = kernel.record_observation(_veritas_source_payload(
        "pan-veritas-source-provenance-later",
        "2026-10-01T06:00:20Z",
        basis_expands=True,
        queue_replenishment=0.8,
        cross_asset_lead=0.2,
    ))
    kernel.record_veritas_reconciliation({
        "observation_id": origin["observation_id"],
        "source_observation_id": source["observation_id"],
        "observed_at": source["observed_at"],
        "confidence": 0.9,
        "evidence": ["fixture:source-provenance"],
    })
    outcome = kernel.record_claim_outcome({
        "claim_id": claim["claim_id"],
        "observed_at": source["observed_at"],
        "utility": 0.5,
        "confidence": 0.9,
        "_source_observation_id": source["observation_id"],
        "evidence": ["fixture:source-provenance-outcome"],
    })
    assert outcome["source_observation_id"] == source["observation_id"]

    with kernel._connect() as con:
        row = con.execute(
            "SELECT source_observation_id FROM claim_outcomes WHERE outcome_id=?",
            (outcome["outcome_id"],),
        ).fetchone()
    assert row["source_observation_id"] == source["observation_id"]


def test_veritas_certificate_fails_closed_on_malformed_signatures(tmp_path):
    payload = _veritas_payload("pan-veritas-invalid")
    payload["signals"]["mechanism_certificate"]["expected_signatures"] = [
        {"key": "x", "operator": "gte", "weight": 1.0},
    ]
    with pytest.raises(ValueError, match="threshold is required"):
        PantheonKernel(tmp_path).record_observation(payload)


def test_aether_spawns_bounded_ephemeral_agents_with_zero_capital_authority(tmp_path):
    kernel = PantheonKernel(tmp_path, swarm=AetherSwarm(threshold=0.25, max_agents=7))
    obs = kernel.record_observation(_payload())
    swarm = obs["analysis"]["aether"]
    assert swarm["status"] == "active"
    assert 4 <= len(swarm["agents"]) <= 7
    assert all(agent["ephemeral"] is True for agent in swarm["agents"])
    assert all(agent["capital_authority"] == "NONE" for agent in swarm["agents"])
    assert all(agent["execution_authorized"] is False for agent in swarm["agents"])
    assert {"falsifier", "alternative_cause", "provenance_guard", "risk_guard"} <= {a["role"] for a in swarm["agents"]}
    assert all(agent["independence_round"] == "blind_first_pass" for agent in swarm["agents"])
    assert all(agent["peer_context_authorized"] is False for agent in swarm["agents"])
    assert swarm["diversity_contract"]["peer_conclusions_hidden_until_commitment"] is True
    assert swarm["diversity_contract"]["forced_consensus"] is False
    assert swarm["truth_contract"]["risk_kernel_bypass"] is False


def test_aether_stays_quiet_when_field_energy_and_data_quality_are_low(tmp_path):
    payload = _payload()
    payload["signals"] = {
        "data_quality": 0.10,
        "risk": 0.90,
        "world_scores": {"a": 1.0, "b": 0.0},
        "transition_cost_up": 1.0,
        "transition_cost_down": 1.0,
    }
    kernel = PantheonKernel(tmp_path)
    obs = kernel.record_observation(payload)
    assert obs["analysis"]["aether"]["status"] == "quiet"
    assert obs["analysis"]["aether"]["agents"] == []


def test_observation_identity_is_immutable_and_idempotent(tmp_path):
    kernel = PantheonKernel(tmp_path)
    payload = _payload(observation_id="pan-fixed")
    first = kernel.record_observation(payload)
    second = kernel.record_observation(payload)
    assert second["observation_id"] == first["observation_id"]
    changed = _payload(observation_id="pan-fixed")
    changed["signals"] = dict(changed["signals"])
    changed["signals"]["risk"] = 0.99
    with pytest.raises(ValueError, match="immutable identity"):
        kernel.record_observation(changed)


def test_pantheon_fails_closed_on_bad_time_commit_or_shape(tmp_path):
    kernel = PantheonKernel(tmp_path)
    bad = _payload(observed_at="2026-10-01T06:00:00")
    with pytest.raises(ValueError, match="timezone"):
        kernel.record_observation(bad)
    bad = _payload(source_commit="abc")
    with pytest.raises(ValueError, match="40-character"):
        kernel.record_observation(bad)
    bad = _payload()
    bad["signals"] = []
    with pytest.raises(ValueError, match="signals must be an object"):
        kernel.record_observation(bad)


def test_snapshot_preserves_existing_engine_ownership(tmp_path):
    kernel = PantheonKernel(tmp_path)
    state = kernel.snapshot()
    assert state["engine_catalog"]["ORACLE"]["ownership"].startswith("preserved")
    assert state["engine_catalog"]["PARALLAX"]["ownership"] == "preserved"
    assert state["engine_catalog"]["DREAMSTATE"]["ownership"] == "preserved"
    assert state["authority"]["execution_authorized"] is False
    assert state["truth_contract"]["no_direct_agent_trading"] is True
    assert state["counts"]["sentinel_cells"] == 0


def test_pantheon_is_visible_in_trader_interface():
    repo = Path(__file__).resolve().parents[1]
    dashboard = (repo / "icarus_engine" / "dashboard.html").read_text(encoding="utf-8")
    ui = (repo / "icarus_engine" / "pantheon-ui.js").read_text(encoding="utf-8")
    server = (repo / "icarus_engine" / "server.py").read_text(encoding="utf-8")
    brain = (repo / "icarus_engine" / "brain.py").read_text(encoding="utf-8")
    assert '/pantheon-ui.js' in dashboard
    assert 'data-v="pantheon">PANTHEON / AETHER</span>' in dashboard
    assert "wirePantheon()" in dashboard
    assert "/api/pantheon" in ui
    assert "NO CAPITAL AUTHORITY" in ui
    assert "SHADOW ONLY" in ui
    assert "AETHER alpha food web" in ui
    assert "Cognitive genesis" in ui
    assert "Echo risk" in ui
    assert "VERITAS right-for-right-reasons audit" in ui
    assert "APEX lineage" in ui
    assert "SIBYL structural evidence bridge" in ui
    assert 'p.path == "/api/pantheon"' in server
    assert 'p.path == "/admin/pantheon/observe"' in server
    assert 'p.path == "/admin/pantheon/claim"' in server
    assert 'p.path == "/admin/pantheon/veritas"' in server
    assert '"pantheon": pantheon.snapshot' in server
    assert "resolve_engine_evidence_lineage" in server
    assert '"apex_lineage"' in server
    for subsystem in ("PANTHEON", "NEMESIS Ω", "GÖDEL Ω", "SOCRATES", "ANANKĒ", "EX NIHILO", "MINT Ω", "NULLSPACE Ω", "ECHO Ω", "VERITAS Ω", "ARCHON Ω", "AETHER Ω"):
        assert subsystem in brain


def test_sentinel_cells_accumulate_without_becoming_trade_authority(tmp_path):
    kernel = PantheonKernel(tmp_path, swarm=AetherSwarm(threshold=0.25))
    first = kernel.record_observation(_payload(observation_id="pan-cell-1"))
    second_payload = _payload(observation_id="pan-cell-2", observed_at="2026-10-01T06:00:01Z")
    second = kernel.record_observation(second_payload)
    state = kernel.snapshot()
    assert first["asset"] == second["asset"] == "NQ"
    assert state["counts"]["sentinel_cells"] == 1
    assert state["sentinel_cells"][0]["observation_count"] == 2
    assert state["sentinel_cells"][0]["asset"] == "NQ"
    assert state["sentinel_cells"][0]["horizon_ms"] == 15000
    assert state["authority"]["execution_authorized"] is False


def test_existing_research_subsystems_are_compacted_without_authority():
    out = subsystem_context(
        {
            "schema_version": "px",
            "counts": {"decisions": 4},
            "regret": {"n": 3, "mean_delta": 0.2},
            "mutation_signals": [{"branch_label": "delay_1"}] * 30,
            "paired_ablation_attribution": [{"subsystem": "athena"}],
        },
        {
            "schema_version": "ds",
            "stages": {"proposed": 2},
            "required_gates": ["oos", "costs"],
            "candidates": [
                {"candidate_id": "c1", "family_id": "f1", "stage": "proposed", "asset": "NQ", "regime": "trend", "secret": "not copied"}
            ],
        },
        existing={"oracle": {"latent_pressure": 0.5}},
    )
    assert out["oracle"]["latent_pressure"] == 0.5
    assert out["parallax"]["counts"]["decisions"] == 4
    assert len(out["parallax"]["mutation_signals"]) == 12
    assert out["dreamstate"]["candidates"][0]["candidate_id"] == "c1"
    assert "secret" not in out["dreamstate"]["candidates"][0]
    assert out["parallax"]["authority"]["execution_authorized"] is False
    assert out["dreamstate"]["authority"]["production_decision_authorized"] is False


def test_psi_context_is_compact_and_research_only():
    snapshot = {
        "schema_version": "icarus-possibility-v1",
        "asset": "NQ",
        "generated_at": "2026-10-01T06:02:00Z",
        "latent_pressure_engine": {"latent_pressure": -0.7, "latent_pressure_score": -70.0, "evidence_coverage": 0.9, "components": {"large": "not copied"}},
        "possibility": {"future_entropy": 22.0, "future_space_collapse": 78.0, "clusters": [1, 2, 3]},
        "edge_state": {"state": "SHORT_BIAS", "confidence": 0.6},
        "phase_transition": {"direction": "DOWN"},
        "forced_consensus": {"active": True, "direction": "DOWN"},
        "causal_leadership": {"status": "observed", "leaders": [{"asset": "ES"}]},
    }
    out = psi_context(snapshot)
    legacy = oracle_context(snapshot)
    assert out["subsystem"] == "psi"
    assert legacy == out
    assert out["asset"] == "NQ"
    assert out["latent_pressure"] == -0.7
    assert out["edge_state"] == "SHORT_BIAS"
    assert out["future_space_collapse"] == 78.0
    assert "components" not in out
    assert "clusters" not in out
    assert out["authority"]["execution_authorized"] is False
    assert out["authority"]["production_decision_authorized"] is False


def test_subsystem_context_adds_psi_while_preserving_caller_oracle():
    out = subsystem_context(
        {"counts": {}, "regret": {}, "mutation_signals": [], "paired_ablation_attribution": []},
        {"stages": {}, "candidates": [], "required_gates": []},
        psi_snapshot={
            "asset": "NQ",
            "latent_pressure_engine": {"latent_pressure": 0.4, "latent_pressure_score": 40.0, "evidence_coverage": 0.8},
            "possibility": {"future_entropy": 30.0, "future_space_collapse": 70.0},
            "edge_state": {"state": "NO_EDGE", "confidence": 0.2},
            "phase_transition": {"direction": "UP"},
            "forced_consensus": {"active": False, "direction": None},
            "causal_leadership": {"status": "observed"},
        },
        existing={"oracle": {"identity": "external-oracle"}, "custom": {"preserved": True}},
    )
    assert out["custom"]["preserved"] is True
    assert out["oracle"] == {"identity": "external-oracle"}
    assert out["psi"]["subsystem"] == "psi"
    assert out["psi"]["latent_pressure"] == 0.4
    assert out["psi"]["future_space_collapse"] == 70.0
    assert out["psi"]["authority"]["execution_authorized"] is False


def test_aether_enforces_minimum_independent_population(tmp_path):
    kernel = PantheonKernel(tmp_path, swarm=AetherSwarm(threshold=0.0, max_agents=1))
    obs = kernel.record_observation(_payload(observation_id="pan-min-pop"))
    swarm = obs["analysis"]["aether"]
    assert swarm["status"] == "active"
    assert len(swarm["agents"]) >= 4
    assert {"falsifier", "alternative_cause", "provenance_guard", "risk_guard"} <= {a["role"] for a in swarm["agents"]}


def test_native_subsystem_names_cannot_be_spoofed_by_caller_context():
    out = subsystem_context(
        {"counts": {"decisions": 7}, "regret": {}, "mutation_signals": [], "paired_ablation_attribution": []},
        {"stages": {"proposed": 1}, "candidates": [], "required_gates": []},
        psi_snapshot={
            "asset": "NQ",
            "latent_pressure_engine": {"latent_pressure": 0.25, "latent_pressure_score": 25.0, "evidence_coverage": 0.7},
            "possibility": {},
            "edge_state": {"state": "NO_EDGE"},
            "phase_transition": {},
            "forced_consensus": {},
            "causal_leadership": {},
        },
        existing={
            "oracle": {"identity": "external-oracle"},
            "psi": {"latent_pressure": 999},
            "parallax": {"counts": {"decisions": 999}},
            "dreamstate": {"stages": {"validated": 999}},
            "custom": {"preserved": True},
        },
    )
    assert out["oracle"] == {"identity": "external-oracle"}
    assert out["psi"]["latent_pressure"] == 0.25
    assert out["parallax"]["counts"]["decisions"] == 7
    assert out["dreamstate"]["stages"]["proposed"] == 1
    assert out["custom"]["preserved"] is True


def test_ambient_subsystem_context_does_not_break_idempotent_retries(tmp_path):
    kernel = PantheonKernel(tmp_path)
    first_payload = _payload(observation_id="pan-ambient-idempotent")
    first_payload["subsystem_outputs"] = {"oracle": {"snapshot": 1}}
    first = kernel.record_observation(first_payload)

    retry_payload = _payload(observation_id="pan-ambient-idempotent")
    retry_payload["subsystem_outputs"] = {"oracle": {"snapshot": 2}, "parallax": {"snapshot": 3}}
    retry = kernel.record_observation(retry_payload)

    assert retry["observation_id"] == first["observation_id"]
    assert retry["analysis"]["external_subsystems"] == {"oracle": {"snapshot": 1}}
    assert retry["analysis"]["truth_contract"]["ambient_subsystem_context_excluded_from_immutable_identity"] is True


def test_failed_native_psi_adapter_cannot_fall_back_to_spoofed_context():
    out = subsystem_context(
        {"counts": {}, "regret": {}, "mutation_signals": [], "paired_ablation_attribution": []},
        {"stages": {}, "candidates": [], "required_gates": []},
        psi_snapshot=None,
        existing={
            "oracle": {"identity": "external-oracle"},
            "psi": {"latent_pressure": 999},
            "custom": {"preserved": True},
        },
    )
    assert out["oracle"] == {"identity": "external-oracle"}
    assert out["psi"]["status"] == "unavailable"
    assert out["psi"]["latent_pressure"] is None
    assert out["custom"]["preserved"] is True
    assert out["psi"]["authority"]["execution_authorized"] is False


def test_concurrent_duplicate_observation_is_idempotent(tmp_path):
    kernel = PantheonKernel(tmp_path)
    payload = _payload(observation_id="pan-concurrent-idempotent")

    def record(_):
        return kernel.record_observation(payload)["observation_id"]

    with ThreadPoolExecutor(max_workers=8) as pool:
        ids = list(pool.map(record, range(24)))

    assert set(ids) == {"pan-concurrent-idempotent"}
    state = kernel.snapshot()
    assert state["counts"]["observations"] == 1
    assert state["counts"]["sentinel_cells"] == 1
    assert state["sentinel_cells"][0]["observation_count"] == 1


def test_pantheon_time_is_canonical_utc_and_future_closed(tmp_path):
    assert iso_aware("2026-10-01T01:00:00-05:00") == "2026-10-01T06:00:00Z"
    kernel = PantheonKernel(tmp_path)
    equivalent = _payload(observation_id="pan-time-canonical", observed_at="2026-10-01T01:00:00-05:00")
    out = kernel.record_observation(equivalent)
    assert out["observed_at"] == "2026-10-01T06:00:00Z"

    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    with pytest.raises(ValueError, match="future"):
        kernel.record_observation(_payload(observation_id="pan-future", observed_at=future))


def test_aether_claim_protocol_preserves_independence_and_disagreement(tmp_path):
    kernel = PantheonKernel(tmp_path, swarm=AetherSwarm(threshold=0.0, max_agents=4))
    observation = kernel.record_observation(_payload(observation_id="pan-claims"))
    mandatory = {"falsifier", "alternative_cause", "provenance_guard", "risk_guard"}
    agents = {row["role"]: row for row in observation["analysis"]["aether"]["agents"] if row["role"] in mandatory}
    assert set(agents) == mandatory

    directions = {
        "falsifier": "short",
        "alternative_cause": "long",
        "provenance_guard": "flat",
        "risk_guard": "short",
    }
    state = observation
    for role, agent in agents.items():
        state = kernel.record_agent_claim({
            "observation_id": observation["observation_id"],
            "agent_id": agent["agent_id"],
            "peer_context_used": False,
            "claim": {
                "thesis": f"{role} independent thesis",
                "direction": directions[role],
                "confidence": 0.6,
                "falsifier": f"evidence that would falsify {role}",
                "evidence": [f"partition:{agent['information_partition']}"],
            },
        })

    assert state["deliberation"]["ready_for_deliberation"] is True
    assert state["deliberation"]["blind_first_pass_complete"] is True
    assert state["deliberation"]["consensus_forced"] is False
    assert state["deliberation"]["submitted_claims"] == 4
    assert state["deliberation"]["disagreement_index"] > 0
    assert state["deliberation"]["execution_authorized"] is False
    assert state["deliberation"]["production_decision_authorized"] is False
    assert kernel.snapshot()["counts"]["agent_claims"] == 4


def test_aether_first_pass_claim_is_idempotent_but_immutable(tmp_path):
    kernel = PantheonKernel(tmp_path, swarm=AetherSwarm(threshold=0.0))
    observation = kernel.record_observation(_payload(observation_id="pan-claim-immutable"))
    agent = observation["analysis"]["aether"]["agents"][0]
    payload = {
        "observation_id": observation["observation_id"],
        "agent_id": agent["agent_id"],
        "peer_context_used": False,
        "claim": {
            "thesis": "first independent claim",
            "direction": "unknown",
            "confidence": 0.5,
            "falsifier": "counterexample",
            "evidence": ["fixture"],
        },
    }
    first = kernel.record_agent_claim(payload)
    again = kernel.record_agent_claim(payload)
    assert again["agent_claims"] == first["agent_claims"]

    changed = dict(payload)
    changed["claim"] = dict(payload["claim"], thesis="mutated after seeing peers")
    with pytest.raises(ValueError, match="immutable"):
        kernel.record_agent_claim(changed)

    with pytest.raises(ValueError, match="peer context"):
        kernel.record_agent_claim(dict(payload, agent_id=observation["analysis"]["aether"]["agents"][1]["agent_id"], peer_context_used=True))

    with pytest.raises(ValueError, match="not an active"):
        kernel.record_agent_claim(dict(payload, agent_id="aeth-not-real"))

def test_pantheon_exports_only_identified_structural_constraint_evidence_to_sibyl(tmp_path):
    kernel = PantheonKernel(tmp_path)
    payload = _payload(observation_id="pan-sibyl-identified")
    payload["signals"] = dict(payload["signals"])
    payload["signals"]["world_scores"] = {"up_constraint": 0.98, "down_constraint": 0.02}
    payload["signals"]["transition_cost_up"] = 0.10
    payload["signals"]["transition_cost_down"] = 2.80
    obs = kernel.record_observation(payload)
    exported = obs["analysis"]["exports"]["sibyl_evidence"]
    assert len(exported) == 1
    row = exported[0]
    assert row["source"] == "pantheon-ananke"
    assert row["domain"] == "structural_constraints"
    assert row["direction"] > 0
    assert row["confidence"] > 0.10
    assert row["source_commit"] == "a" * 40
    assert row["payload"]["authority"]["execution_authorized"] is False

    ambiguous = kernel.record_observation(
        _payload(observation_id="pan-sibyl-ambiguous", observed_at="2026-10-01T06:00:01Z")
    )
    assert ambiguous["analysis"]["exports"]["sibyl_evidence"] == []


def test_pantheon_extended_constraints_ablation_and_causal_debt_states(tmp_path):
    kernel = PantheonKernel(tmp_path)
    payload = _payload(observation_id="pan-extended")
    payload["signals"] = dict(payload["signals"])
    payload["signals"].update({
        "expected_response": 1.0,
        "observed_response": 0.30,
        "absorber_strength": 0.0,
        "diversion_score": 0.0,
        "lag_score": 0.0,
        "debt_change_rate": 0.80,
        "world_reachability": {
            "macro_up": {"up": 0.80, "down": 0.20},
            "flow_up": {"up": 0.65, "down": 0.30},
        },
        "subsystem_survival": {
            "oracle": 0.90,
            "argus": 0.35,
            "athena": 0.70,
        },
    })
    obs = kernel.record_observation(payload)
    faculties = obs["analysis"]["faculties"]
    assert faculties["nullspace"]["debt_state"] == "cliff"
    cross = faculties["ananke"]["cross_world_reachability"]
    assert cross["intersection"]["up"] == pytest.approx(0.65)
    assert cross["intersection"]["down"] == pytest.approx(0.20)
    ablation = faculties["nemesis"]["subsystem_ablation_survival"]
    assert ablation[0]["subsystem"] == "argus"
    assert any(row["target"] == "ablate:argus" for row in faculties["nemesis"]["dreamstate_curriculum"])


def test_nemesis_derives_edge_half_life_when_decay_is_supplied(tmp_path):
    kernel = PantheonKernel(tmp_path)
    payload = _payload(observation_id="pan-half-life")
    payload["signals"] = dict(payload["signals"])
    payload["signals"]["edge_decay_rate_per_second"] = 0.01
    obs = kernel.record_observation(payload)
    nemesis = obs["analysis"]["faculties"]["nemesis"]
    assert nemesis["edge_half_life_source"] == "derived_from_decay_rate"
    assert nemesis["edge_half_life_seconds"] == pytest.approx(69.314718, rel=1e-5)


def test_sentinel_cells_preserve_latest_observed_state_under_late_ingestion(tmp_path):
    kernel = PantheonKernel(tmp_path, swarm=AetherSwarm(threshold=0.25))
    kernel.record_observation(_payload(observation_id="pan-newer", observed_at="2026-10-01T06:00:02Z"))
    kernel.record_observation(_payload(observation_id="pan-older", observed_at="2026-10-01T06:00:01Z"))
    cell = kernel.snapshot()["sentinel_cells"][0]
    assert cell["observation_count"] == 2
    assert cell["last_observation_id"] == "pan-newer"
    assert cell["last_observed_at"] == "2026-10-01T06:00:02Z"


def _feedback_payload(observation_id: str, observed_at: str, claim_id: str, utility: float):
    return {
        "observation_id": observation_id,
        "observed_at": observed_at,
        "asset": "NQ",
        "horizon_ms": 15000,
        "source_commit": "a" * 40,
        "signals": {
            "data_quality": 0.50,
            "risk": 0.10,
            "world_scores": {"identified": 1.0, "other": 0.0},
            "transition_cost_up": 1.0,
            "transition_cost_down": 1.0,
        },
        "evidence": [f"feedback:{observation_id}"],
        "claim_outcomes": [
            {
                "claim_id": claim_id,
                "observed_at": observed_at,
                "utility": utility,
                "confidence": 0.90,
                "evidence": [f"observed-outcome:{observation_id}"],
            }
        ],
    }


def test_aether_ecology_requires_observed_fitness_for_speciation_and_genesis(tmp_path):
    kernel = PantheonKernel(tmp_path)
    first = kernel.record_observation(_payload(observation_id="pan-origin"))
    ontology_claim = next(c for c in first["claims"] if c["kind"] == "ontology_candidate")

    for i in range(1, 4):
        result = kernel.record_observation(
            _feedback_payload(
                f"pan-positive-{i}",
                f"2026-10-01T06:00:{19 + i:02d}Z",
                ontology_claim["claim_id"],
                0.80,
            )
        )
        assert result["ecology_outcomes"][0]["authority"]["execution_authorized"] is False

    ecology = kernel.snapshot()["ecology"]
    parent = next(x for x in ecology["species"] if x["origin_claim_id"] == ontology_claim["claim_id"] and x["generation"] == 0)
    children = [x for x in ecology["species"] if x["parent_species_id"] == parent["species_id"]]
    assert parent["stage"] == "surviving_shadow"
    assert parent["fitness_credit"] == pytest.approx(0.80)
    assert parent["evidence_count"] == 3
    assert len(children) == 1
    assert children[0]["generation"] == 1
    assert children[0]["origin_claim_id"].startswith("mut-")
    assert ecology["alpha_food_web"]
    assert any(x["species_id"] == parent["species_id"] for x in ecology["cognitive_genesis_candidates"])
    assert ecology["authority"]["execution_authorized"] is False
    assert ecology["contracts"]["cognitive_genesis_never_auto_creates_production_code"] is True


def test_aether_offspring_has_independent_claim_identity_and_can_be_scored(tmp_path):
    kernel = PantheonKernel(tmp_path)
    first = kernel.record_observation(_payload(observation_id="pan-parent"))
    claim = next(c for c in first["claims"] if c["kind"] == "monetization_candidate")
    for i in range(1, 4):
        kernel.record_observation(
            _feedback_payload(f"pan-parent-fit-{i}", f"2026-10-01T06:02:0{i}Z", claim["claim_id"], 0.90)
        )
    ecology = kernel.snapshot()["ecology"]
    child = next(x for x in ecology["species"] if x["parent_species_id"] is not None)
    birth_observation = kernel.observation("pan-parent-fit-3")
    assert any(c["claim_id"] == child["origin_claim_id"] for c in birth_observation["claims"])
    with pytest.raises(ValueError, match="claim maturity"):
        kernel.record_claim_outcome({
            "claim_id": child["origin_claim_id"],
            "observed_at": "2026-10-01T06:02:10Z",
            "utility": 0.40,
            "confidence": 0.80,
            "evidence": ["premature-child-outcome"],
        })
    scored = kernel.record_claim_outcome({
        "claim_id": child["origin_claim_id"],
        "observed_at": "2026-10-01T06:03:00Z",
        "utility": 0.40,
        "confidence": 0.80,
        "evidence": ["child-shadow-outcome"],
    })
    assert scored["claim_id"] == child["origin_claim_id"]
    assert scored["evidence_count"] == 1


def test_aether_ecology_retires_repeated_negative_species(tmp_path):
    kernel = PantheonKernel(tmp_path)
    first = kernel.record_observation(_payload(observation_id="pan-neg-origin"))
    edge_claim = next(c for c in first["claims"] if c["kind"] == "monetization_candidate")
    for i in range(1, 4):
        kernel.record_observation(
            _feedback_payload(f"pan-negative-{i}", f"2026-10-01T06:01:0{i}Z", edge_claim["claim_id"], -0.75)
        )
    ecology = kernel.snapshot()["ecology"]
    parent = next(x for x in ecology["species"] if x["origin_claim_id"] == edge_claim["claim_id"] and x["generation"] == 0)
    assert parent["stage"] == "retired"
    assert parent["fitness_credit"] == pytest.approx(-0.75)
    assert any(x["species_id"] == parent["species_id"] for x in ecology["extinct_species"])


def test_claim_outcome_is_causal_and_immutable_per_claim_time(tmp_path):
    kernel = PantheonKernel(tmp_path)
    first = kernel.record_observation(_payload(observation_id="pan-time-origin"))
    claim = first["claims"][0]
    with pytest.raises(ValueError, match="cannot precede"):
        kernel.record_claim_outcome({
            "claim_id": claim["claim_id"],
            "observed_at": "2026-10-01T05:59:59Z",
            "utility": 0.5,
            "confidence": 1.0,
            "evidence": ["invalid-retroactive-outcome"],
        })
    with pytest.raises(ValueError, match="claim maturity"):
        kernel.record_claim_outcome({
            "claim_id": claim["claim_id"],
            "observed_at": "2026-10-01T06:00:05Z",
            "utility": 0.5,
            "confidence": 1.0,
            "evidence": ["invalid-before-horizon-maturity"],
        })

    payload = {
        "claim_id": claim["claim_id"],
        "observed_at": "2026-10-01T06:04:00Z",
        "utility": 0.5,
        "confidence": 1.0,
        "evidence": ["first-score"],
    }
    first_score = kernel.record_claim_outcome(payload)
    again = kernel.record_claim_outcome(payload)
    assert again["outcome_id"] == first_score["outcome_id"]
    with pytest.raises(ValueError, match="immutable"):
        kernel.record_claim_outcome({**payload, "utility": -0.5})



def test_aether_claim_requires_confidence_evidence_and_role_falsifier(tmp_path):
    kernel = PantheonKernel(tmp_path, swarm=AetherSwarm(threshold=0.0, max_agents=4))
    observation = kernel.record_observation(_payload(observation_id="pan-claim-required-fields"))
    agent = next(row for row in observation["analysis"]["aether"]["agents"] if row["role"] == "falsifier")
    base = {
        "observation_id": observation["observation_id"],
        "agent_id": agent["agent_id"],
        "peer_context_used": False,
    }

    with pytest.raises(ValueError, match="confidence is required"):
        kernel.record_agent_claim({
            **base,
            "claim": {"thesis": "x", "direction": "unknown", "falsifier": "y", "evidence": ["z"]},
        })

    with pytest.raises(ValueError, match="1-24"):
        kernel.record_agent_claim({
            **base,
            "claim": {"thesis": "x", "direction": "unknown", "confidence": 0.5, "falsifier": "y", "evidence": []},
        })

    with pytest.raises(ValueError, match="falsifier is required"):
        kernel.record_agent_claim({
            **base,
            "claim": {"thesis": "x", "direction": "unknown", "confidence": 0.5, "falsifier": "", "evidence": ["z"]},
        })


def test_blind_claim_bodies_are_hidden_until_mandatory_round_completes(tmp_path):
    kernel = PantheonKernel(tmp_path, swarm=AetherSwarm(threshold=0.0, max_agents=8))
    observation = kernel.record_observation(_payload(observation_id="pan-blind-visibility"))
    agents = {row["role"]: row for row in observation["analysis"]["aether"]["agents"]}

    first = kernel.record_agent_claim({
        "observation_id": observation["observation_id"],
        "agent_id": agents["falsifier"]["agent_id"],
        "peer_context_used": False,
        "claim": {
            "thesis": "must remain hidden",
            "direction": "short",
            "confidence": 0.7,
            "falsifier": "counterexample",
            "evidence": ["partition:adversarial"],
        },
    })
    assert first["deliberation"]["ready_for_deliberation"] is False
    assert first["deliberation"]["claim_bodies_visible"] is False
    assert first["agent_claims"][0]["claim"] is None

    for role, direction in (("alternative_cause", "long"), ("provenance_guard", "flat"), ("risk_guard", "short")):
        state = kernel.record_agent_claim({
            "observation_id": observation["observation_id"],
            "agent_id": agents[role]["agent_id"],
            "peer_context_used": False,
            "claim": {
                "thesis": f"{role} thesis",
                "direction": direction,
                "confidence": 0.6,
                "falsifier": "counterexample",
                "evidence": [f"partition:{agents[role]['information_partition']}"],
            },
        })

    assert state["deliberation"]["mandatory_roles_complete"] is True
    assert state["deliberation"]["ready_for_deliberation"] is False
    assert state["deliberation"]["claim_bodies_visible"] is False
    assert all(row["claim"] is None for row in state["agent_claims"])

    submitted = {row["agent_id"] for row in state["agent_claims"]}
    for agent in observation["analysis"]["aether"]["agents"]:
        if agent["agent_id"] in submitted:
            continue
        state = kernel.record_agent_claim({
            "observation_id": observation["observation_id"],
            "agent_id": agent["agent_id"],
            "peer_context_used": False,
            "claim": {
                "thesis": f"{agent['role']} optional thesis",
                "direction": "unknown",
                "confidence": 0.5,
                "falsifier": "counterexample",
                "evidence": [f"partition:{agent['information_partition']}"],
            },
        })

    assert state["deliberation"]["ready_for_deliberation"] is True
    assert state["deliberation"]["blind_first_pass_complete"] is True
    assert state["deliberation"]["claim_bodies_visible"] is True
    assert any((row["claim"] or {}).get("thesis") == "must remain hidden" for row in state["agent_claims"])


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("risk", 1.1, "between 0 and 1"),
        ("data_quality", -0.1, "between 0 and 1"),
    ],
)
def test_normalized_faculty_inputs_fail_closed_instead_of_clamping(tmp_path, field, value, match):
    payload = _payload(observation_id=f"pan-invalid-{field}")
    payload["signals"] = dict(payload["signals"])
    payload["signals"][field] = value
    with pytest.raises(ValueError, match=match):
        PantheonKernel(tmp_path).record_observation(payload)


def test_structural_and_monetization_inputs_reject_invalid_economics(tmp_path):
    bad_transition = _payload(observation_id="pan-bad-transition")
    bad_transition["signals"] = dict(bad_transition["signals"], transition_cost_up=-0.1)
    with pytest.raises(ValueError, match="transition costs"):
        PantheonKernel(tmp_path / "a").record_observation(bad_transition)

    bad_world = _payload(observation_id="pan-bad-world")
    bad_world["signals"] = dict(bad_world["signals"], world_scores={"a": 1.0, "b": -0.1})
    with pytest.raises(ValueError, match="non-negative"):
        PantheonKernel(tmp_path / "b").record_observation(bad_world)

    bad_risk = _payload(observation_id="pan-bad-risk-capital")
    bad_risk["signals"] = dict(bad_risk["signals"])
    bad_risk["signals"]["candidate_expressions"] = [{
        "name": "invalid",
        "expected_gross": 10.0,
        "costs": 1.0,
        "risk_capital": -100.0,
        "duration_seconds": 10.0,
        "capacity_remaining": 0.5,
    }]
    with pytest.raises(ValueError, match="risk_capital must be positive"):
        PantheonKernel(tmp_path / "c").record_observation(bad_risk)


def test_claim_outcome_quality_fields_fail_closed(tmp_path):
    kernel = PantheonKernel(tmp_path)
    first = kernel.record_observation(_payload(observation_id="pan-outcome-quality"))
    claim = first["claims"][0]
    base = {
        "claim_id": claim["claim_id"],
        "observed_at": "2026-10-01T06:10:00Z",
        "utility": 0.5,
        "confidence": 0.8,
        "evidence": ["observed:fixture"],
    }

    with pytest.raises(ValueError, match="between -1 and 1"):
        kernel.record_claim_outcome({**base, "utility": 1.2})
    without_confidence = dict(base)
    without_confidence.pop("confidence")
    with pytest.raises(ValueError, match="confidence is required"):
        kernel.record_claim_outcome(without_confidence)
    with pytest.raises(ValueError, match="1-64"):
        kernel.record_claim_outcome({**base, "evidence": []})


def test_extended_faculty_timing_and_stress_inputs_fail_closed(tmp_path):
    kernel = PantheonKernel(tmp_path)

    neg_decay = _payload(observation_id="pan-neg-decay")
    neg_decay["signals"] = dict(neg_decay["signals"], edge_decay_rate_per_second=-0.01)
    with pytest.raises(ValueError, match="edge_decay_rate_per_second must be non-negative"):
        kernel.record_observation(neg_decay)

    neg_half_life = _payload(observation_id="pan-neg-half-life")
    neg_half_life["signals"] = dict(neg_half_life["signals"], edge_half_life_seconds=-1.0)
    with pytest.raises(ValueError, match="edge_half_life_seconds must be non-negative"):
        kernel.record_observation(neg_half_life)

    bad_stress = _payload(observation_id="pan-bad-stress")
    bad_stress["signals"] = dict(bad_stress["signals"])
    bad_stress["signals"]["candidate_expressions"] = [{
        "name": "bad_stress",
        "expected_gross": 10.0,
        "costs": 1.0,
        "risk_capital": 100.0,
        "duration_seconds": 10.0,
        "capacity_remaining": 0.5,
        "cost_stress_multiplier": 0.9,
    }]
    with pytest.raises(ValueError, match="cost_stress_multiplier must be at least 1"):
        kernel.record_observation(bad_stress)

    bad_ttl = _payload(observation_id="pan-bad-ttl")
    bad_ttl["signals"] = dict(bad_ttl["signals"], lease_ttl_seconds=30.5)
    with pytest.raises(ValueError, match="lease_ttl_seconds must be an integer"):
        kernel.record_observation(bad_ttl)

def test_pantheon_psi_adapter_preserves_oracle_identity():
    snapshot = {
        "schema_version": "icarus-possibility-v1",
        "asset": "NQ",
        "generated_at": "2026-10-01T06:00:00Z",
        "latent_pressure_engine": {
            "latent_pressure": 0.42,
            "latent_pressure_score": 42.0,
            "evidence_coverage": 0.75,
        },
        "possibility": {"future_entropy": 31.0, "future_space_collapse": 69.0},
        "edge_state": {"state": "LONG_BIAS", "confidence": 0.61},
        "phase_transition": {"direction": "UP"},
        "forced_consensus": {"active": True, "direction": "UP"},
        "causal_leadership": {"status": "observed"},
    }
    existing = {"oracle": {"status": "external-oracle", "identity": "oracle"}}
    out = subsystem_context({}, {}, psi_snapshot=snapshot, existing=existing)
    assert out["oracle"] == existing["oracle"]
    assert out["psi"]["subsystem"] == "psi"
    assert out["psi"]["latent_pressure"] == pytest.approx(0.42)
    assert out["psi"]["evidence_coverage"] == pytest.approx(0.75)
    assert "distinct from ORACLE" in out["psi"]["source_semantics"]


def test_pantheon_numeric_contracts_reject_out_of_range_values():
    from icarus_engine.pantheon.contracts import unit, signed_unit
    with pytest.raises(ValueError, match="between 0 and 1"):
        unit(1.1, "confidence")
    with pytest.raises(ValueError, match="between -1 and 1"):
        signed_unit(-1.1, "direction")

def test_ecology_upgrade_backfills_legacy_claims_and_sentinel_clock(tmp_path):
    kernel = PantheonKernel(tmp_path)
    observation = kernel.record_observation(_payload(observation_id="pan-legacy-upgrade"))
    durable_claim = next(c for c in observation["claims"] if c["kind"] == "ontology_candidate")
    expected_time = observation["observed_at"]
    with kernel._connect() as con:
        con.execute("DELETE FROM species")
        con.execute("UPDATE sentinel_cells SET last_observed_at=''")
    upgraded = PantheonKernel(tmp_path)
    state = upgraded.snapshot()
    assert any(row["origin_claim_id"] == durable_claim["claim_id"] for row in state["ecology"]["species"])
    assert state["sentinel_cells"][0]["last_observed_at"] == expected_time


def test_zero_confidence_outcomes_do_not_satisfy_fitness_evidence_thresholds(tmp_path):
    kernel = PantheonKernel(tmp_path)
    first = kernel.record_observation(_payload(observation_id="pan-zero-confidence-origin"))
    claim = next(c for c in first["claims"] if c["kind"] == "ontology_candidate")
    last = None
    for i in range(3):
        last = kernel.record_claim_outcome({
            "claim_id": claim["claim_id"],
            "observed_at": f"2026-10-01T06:04:0{i}Z",
            "utility": 1.0,
            "confidence": 0.0,
            "evidence": [f"observed-but-zero-confidence:{i}"],
        })
    assert last["fitness_credit"] == 0.0
    assert last["evidence_count"] == 0
    assert last["outcome_count"] == 3
    assert last["species_stage"] == "hypothesis"
    assert last["offspring_species_id"] is None
    ecology = kernel.snapshot()["ecology"]
    species = next(x for x in ecology["species"] if x["origin_claim_id"] == claim["claim_id"])
    assert species["fitness_credit"] == 0.0
    assert species["evidence_count"] == 0
    assert species["stage"] == "hypothesis"


def test_attached_claim_outcome_is_bound_to_feedback_asset_and_timestamp(tmp_path):
    kernel = PantheonKernel(tmp_path)
    first = kernel.record_observation(_payload(observation_id="pan-feedback-origin"))
    claim = next(c for c in first["claims"] if c["kind"] == "ontology_candidate")
    bad_asset = _feedback_payload("pan-feedback-wrong-asset", "2026-10-01T06:01:00Z", claim["claim_id"], 0.5)
    bad_asset["asset"] = "ES"
    with pytest.raises(ValueError, match="source asset"):
        kernel.record_observation(bad_asset)
    mismatched = _feedback_payload("pan-feedback-wrong-time", "2026-10-01T06:02:00Z", claim["claim_id"], 0.5)
    mismatched["claim_outcomes"][0]["observed_at"] = "2026-10-01T06:02:01Z"
    with pytest.raises(ValueError, match="source observation time"):
        kernel.record_observation(mismatched)

