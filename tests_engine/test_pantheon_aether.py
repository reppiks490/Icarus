from __future__ import annotations

from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest

from icarus_engine.pantheon import AetherSwarm, PantheonKernel, subsystem_context
from icarus_engine.pantheon.bridge import oracle_context
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
        "nullspace", "godel", "ananke", "nemesis", "ex_nihilo", "mint", "archon", "socrates"
    }
    assert analysis["faculties"]["nullspace"]["routing_state"] == "absorbed"
    assert analysis["faculties"]["godel"]["identifiability"] < 0.01
    assert analysis["faculties"]["ananke"]["least_cost_direction"] == "up"
    assert analysis["faculties"]["nemesis"]["survival_score"] > 0.70
    assert analysis["faculties"]["ex_nihilo"]["new_phenomenon_candidate"] is True
    assert analysis["faculties"]["mint"]["best_candidate"]["name"] == "nq_es_relative_value"
    assert analysis["faculties"]["archon"]["contradiction"] > 0.80
    assert analysis["faculties"]["archon"]["consensus_forced"] is False
    assert analysis["authority"]["execution_authorized"] is False
    assert analysis["authority"]["production_decision_authorized"] is False
    assert all(not lease["execution_authorized"] for lease in analysis["faculties"]["archon"]["leases"])


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
    assert '/pantheon-ui.js' in dashboard
    assert 'data-v="pantheon">PANTHEON / AETHER</span>' in dashboard
    assert "wirePantheon()" in dashboard
    assert "/api/pantheon" in ui
    assert "NO CAPITAL AUTHORITY" in ui
    assert "SHADOW ONLY" in ui
    assert 'p.path == "/api/pantheon"' in server
    assert 'p.path == "/admin/pantheon/observe"' in server
    assert 'p.path == "/admin/pantheon/claim"' in server


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


def test_oracle_context_is_compact_and_research_only():
    out = oracle_context({
        "schema_version": "icarus-possibility-v1",
        "asset": "NQ",
        "generated_at": "2026-10-01T06:02:00Z",
        "oracle": {"latent_pressure": -0.7, "latent_pressure_score": -70.0, "evidence_coverage": 0.9, "components": {"large": "not copied"}},
        "possibility": {"future_entropy": 22.0, "future_space_collapse": 78.0, "clusters": [1, 2, 3]},
        "edge_state": {"state": "SHORT_BIAS", "confidence": 0.6},
        "phase_transition": {"direction": "DOWN"},
        "forced_consensus": {"active": True, "direction": "DOWN"},
        "causal_leadership": {"status": "observed", "leaders": [{"asset": "ES"}]},
    })
    assert out["asset"] == "NQ"
    assert out["latent_pressure"] == -0.7
    assert out["edge_state"] == "SHORT_BIAS"
    assert out["future_space_collapse"] == 78.0
    assert "components" not in out
    assert "clusters" not in out
    assert out["authority"]["execution_authorized"] is False
    assert out["authority"]["production_decision_authorized"] is False


def test_subsystem_context_adds_oracle_without_overwriting_caller_owned_data():
    out = subsystem_context(
        {"counts": {}, "regret": {}, "mutation_signals": [], "paired_ablation_attribution": []},
        {"stages": {}, "candidates": [], "required_gates": []},
        oracle_snapshot={
            "asset": "NQ",
            "oracle": {"latent_pressure": 0.4, "latent_pressure_score": 40.0, "evidence_coverage": 0.8},
            "possibility": {"future_entropy": 30.0, "future_space_collapse": 70.0},
            "edge_state": {"state": "NO_EDGE", "confidence": 0.2},
            "phase_transition": {"direction": "UP"},
            "forced_consensus": {"active": False, "direction": None},
            "causal_leadership": {"status": "observed"},
        },
        existing={"custom": {"preserved": True}},
    )
    assert out["custom"]["preserved"] is True
    assert out["oracle"]["latent_pressure"] == 0.4
    assert out["oracle"]["future_space_collapse"] == 70.0
    assert out["oracle"]["authority"]["execution_authorized"] is False


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
        oracle_snapshot={
            "asset": "NQ",
            "oracle": {"latent_pressure": 0.25, "latent_pressure_score": 25.0, "evidence_coverage": 0.7},
            "possibility": {},
            "edge_state": {"state": "NO_EDGE"},
            "phase_transition": {},
            "forced_consensus": {},
            "causal_leadership": {},
        },
        existing={
            "oracle": {"latent_pressure": 999},
            "parallax": {"counts": {"decisions": 999}},
            "dreamstate": {"stages": {"validated": 999}},
            "custom": {"preserved": True},
        },
    )
    assert out["oracle"]["latent_pressure"] == 0.25
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


def test_failed_native_oracle_adapter_cannot_fall_back_to_spoofed_context():
    out = subsystem_context(
        {"counts": {}, "regret": {}, "mutation_signals": [], "paired_ablation_attribution": []},
        {"stages": {}, "candidates": [], "required_gates": []},
        oracle_snapshot=None,
        existing={"oracle": {"latent_pressure": 999}, "custom": {"preserved": True}},
    )
    assert out["oracle"]["status"] == "unavailable"
    assert out["oracle"]["latent_pressure"] is None
    assert out["custom"]["preserved"] is True
    assert out["oracle"]["authority"]["execution_authorized"] is False


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
