from __future__ import annotations

from icarus_engine.brain import AGENTS, SUBSYSTEMS, brain_snapshot, candidate_gate, record_brain_event


def _candidate(**overrides):
    body = {
        "kind": "candidate",
        "subject": "nq-trend-v1",
        "summary": "regime specialist candidate",
        "status": "qualified",
        "candidate_id": "nq-trend-v1",
        "stage": "qualified_shadow",
        "regimes": ["STRONG"],
        "metrics": {"validation_score": 0.81},
        "validation": {
            "causal_time": True,
            "provenance": True,
            "oos": True,
            "protected_holdout": True,
            "multiple_testing": True,
            "costs_slippage_latency": True,
            "ablation": True,
            "calibration": True,
            "ood_drift": True,
            "deterministic_replay": True,
            "independent_verification": True,
        },
        "source_repo": "reppiks490/Icarus",
        "source_commit": "a" * 40,
        "evidence": ["test evidence"],
    }
    body.update(overrides)
    return body


def test_brain_registers_five_custom_agents_and_twelve_plus_subsystems(tmp_path):
    out = brain_snapshot(tmp_path)
    assert len(AGENTS) == 5
    assert len(SUBSYSTEMS) >= 12
    assert out["architecture"]["agent_count"] == 5
    assert {"parallax", "provenance", "ml", "data"} <= {x["id"] for x in out["architecture"]["subsystems"]}
    assert out["architecture"]["subsystem_count"] >= 12
    assert out["authority"]["production_decision_authorized"] is False
    assert out["authority"]["execution_authorized"] is False
    assert out["truth_contract"]["success_rate"] is None
    assert out["truth_contract"]["omnipotence_claim"] is False
    assert out["remote_sync"]["status"] == "not_configured"
    assert out["research_sync"]["status"] == "not_configured"
    assert out["performance_proof"]["metrics"]["success_rate"] is None
    assert out["latency_telemetry"]["hot_path"] is None
    assert out["evidence_tournaments"] == []
    assert out["evidence_graph"]["metrics"]["node_count"] == 0
    assert out["evidence_graph"]["execution_authorized"] is False
    assert out["source_reliability"]["observation_count"] == 0
    assert out["source_reliability"]["execution_authorized"] is False


def test_brain_surfaces_zero_cost_incubator_without_promotion_authority(tmp_path):
    research = {
        "adaptation": {
            "assets": {
                "NQ": {
                    "last_proposal": "p" * 64,
                    "review_mode": "study_only",
                    "status": "candidate_proposed",
                    "regime_context": {
                        "label": "STRONG TREND",
                        "regime_score": 0.81,
                        "observed_market_ts": 660,
                    },
                }
            }
        },
        "ledger": {
            "proposals": [
                {
                    "proposal_id": "p" * 64,
                    "state": "proposed",
                    "candidate": {
                        "asset": "NQ",
                        "inputs": {"use_cycle": False},
                        "decision_at": "2026-10-01T05:00:00Z",
                        "expires_at": "2026-10-01T06:00:00Z",
                    },
                    "reviews": [],
                },
                {
                    "proposal_id": "a" * 64,
                    "state": "approved",
                    "candidate": {
                        "asset": "GC",
                        "inputs": {"conf_min_votes": 5},
                        "decision_at": "2026-10-01T05:00:00Z",
                        "expires_at": "2026-10-01T06:00:00Z",
                    },
                    "reviews": [{"provider": "openai"}, {"provider": "anthropic"}],
                },
            ]
        }
    }
    out = brain_snapshot(tmp_path, research_status=research)
    assert out["incubator"]["available"] is True
    assert out["incubator"]["proposal_count"] == 2
    assert out["incubator"]["review_required"] == 1
    assert out["incubator"]["approved"] == 1
    nq = next(row for row in out["incubator"]["proposals"] if row["asset"] == "NQ")
    assert nq["review_mode"] == "study_only"
    assert nq["scheduler_status"] == "candidate_proposed"
    assert nq["regime_context"]["label"] == "STRONG TREND"
    assert nq["regime_context"]["regime_score"] == 0.81
    assert out["incubator"]["execution_authorized"] is False
    assert out["incubator"]["production_decision_authorized"] is False
    assert out["learning"]["incubator_proposals"] == 2
    assert out["learning"]["incubator_review_required"] == 1


def test_candidate_gate_is_fail_closed_until_every_validation_gate_passes(tmp_path):
    body = _candidate()
    rec = record_brain_event(tmp_path, body)
    assert rec["execution_authorized"] is False
    snap = brain_snapshot(
        tmp_path,
        market_status={
            "assets": [
                {"symbol": "NQ", "warm": True, "paused": False, "state": {"rate_regime_str": "STRONG", "rate_regime": 0.84}}
            ]
        },
    )
    assert snap["candidates"][0]["eligible_for_regime_swap"] is True
    assert snap["regime_routes"][0]["selected_candidate"] == "nq-trend-v1"
    assert snap["regime_routes"][0]["selection_mode"] == "SHADOW_ONLY"

    bad = dict(snap["candidates"][0])
    bad["validation"] = dict(bad["validation"])
    bad["validation"]["protected_holdout"] = False
    eligible, blockers = candidate_gate(bad)
    assert eligible is False
    assert "protected_holdout gate not verified" in blockers


def test_brain_event_is_idempotent_and_never_mints_execution_authority(tmp_path):
    first = record_brain_event(tmp_path, _candidate())
    second = record_brain_event(tmp_path, _candidate())
    assert first["idempotent"] is False
    assert second["idempotent"] is True
    assert second["event"]["execution_authorized"] is False
    assert second["event"]["production_decision_authorized"] is False


def test_candidate_requires_exact_git_provenance(tmp_path):
    body = _candidate(source_commit="short")
    try:
        record_brain_event(tmp_path, body)
    except ValueError as ex:
        assert "40-character Git SHA" in str(ex)
    else:
        raise AssertionError("candidate without exact source revision must fail")


def test_brain_surfaces_closed_sample_proof_and_tournament(tmp_path):
    proof = {
        "metrics": {"success_rate": 1.0, "outcome_coverage": 1.0, "brier_score": 0.04, "expected_calibration_error": 0.02, "matured_forecasts": 30, "settled_forecasts": 30},
        "closed_sample": {"complete": True, "historical_100_percent_established": True, "future_guarantee": False},
        "replay": {"determinism_rate": 1.0, "historical_100_percent_established": True},
        "candidate_statistics": [{
            "candidate_id": "nq-trend-v1", "asset": "NQ", "regime": "STRONG",
            "success_definition": "positive net outcome after configured costs", "horizon_seconds": 300,
            "matured": 30, "settled": 30, "successes": 30, "outcome_coverage": 1.0,
            "success_rate": 1.0, "brier_score": 0.04, "closed_regime_sample": True,
        }],
        "execution_authorized": False, "production_decision_authorized": False,
    }
    latency = {"hot_path": {"stage": "shadow_decision_total", "p99_ms": 12.5, "budget_status": "PASS_P99"}, "stages": [], "targets_are_measured_not_assumed": True, "execution_authorized": False, "production_decision_authorized": False}
    out = brain_snapshot(tmp_path, proof_status=proof, latency_status=latency)
    assert out["truth_contract"]["success_rate"] == 1.0
    assert out["truth_contract"]["success_rate_status"] == "ESTABLISHED_100_PERCENT_CLOSED_SAMPLE"
    assert out["truth_contract"]["future_guarantee"] is False
    assert out["latency_telemetry"]["hot_path"]["p99_ms"] == 12.5
    assert out["evidence_tournaments"][0]["shadow_champion"] == "nq-trend-v1"


def test_brain_registers_apex_omega_research_subsystem(tmp_path):
    out = brain_snapshot(tmp_path)
    rows = {x["id"]: x for x in SUBSYSTEMS}
    assert "apex-omega" in rows
    assert rows["apex-omega"]["owner"] == "omega"
    assert "world-state" in rows["apex-omega"]["job"].lower()
    assert "epistemic" in rows["apex-omega"]["job"].lower()
    assert out["authority"]["production_decision_authorized"] is False
    assert out["authority"]["execution_authorized"] is False


def test_brain_registers_pantheon_echo_research_subsystem(tmp_path):
    out = brain_snapshot(tmp_path)
    rows = {x["id"]: x for x in SUBSYSTEMS}
    assert "echo" in rows
    assert rows["echo"]["title"] == "ECHO Ω"
    assert rows["echo"]["owner"] == "pantheon"
    assert "evidence-ancestry" in rows["echo"]["job"].lower()
    assert "without trading authority" in rows["echo"]["job"].lower()
    surfaced = {x["id"]: x for x in out["architecture"]["subsystems"]}
    assert surfaced["echo"]["title"] == "ECHO Ω"
    assert surfaced["echo"]["status"] == "REGISTERED"
    assert out["authority"]["production_decision_authorized"] is False
    assert out["authority"]["execution_authorized"] is False


def test_brain_registers_continuous_learning_fabric(tmp_path):
    out = brain_snapshot(tmp_path)
    rows = {x["id"]: x for x in SUBSYSTEMS}
    assert "learning-fabric" in rows
    assert rows["learning-fabric"]["owner"] == "aion"
    assert "outcome" in rows["learning-fabric"]["job"].lower()
    assert "calibration" in rows["learning-fabric"]["job"].lower()
    assert "historical replay" in rows["learning-fabric"]["job"].lower()
    assert out["authority"]["execution_authorized"] is False
    assert out["authority"]["production_decision_authorized"] is False


def test_brain_registers_pantheon_lethe_research_subsystem(tmp_path):
    out = brain_snapshot(tmp_path)
    rows = {x["id"]: x for x in SUBSYSTEMS}
    assert "lethe" in rows
    assert rows["lethe"]["title"] == "LETHE Ω"
    assert rows["lethe"]["owner"] == "pantheon"
    assert "memory" in rows["lethe"]["job"].lower()
    assert "resurrection" in rows["lethe"]["job"].lower()
    surfaced = {x["id"]: x for x in out["architecture"]["subsystems"]}
    assert surfaced["lethe"]["status"] == "REGISTERED"
    assert out["authority"]["execution_authorized"] is False
    assert out["authority"]["production_decision_authorized"] is False


def test_brain_registers_ascendancy_capability_orchestrator(tmp_path):
    out = brain_snapshot(tmp_path)
    rows = {x["id"]: x for x in SUBSYSTEMS}
    assert "capability-orchestrator" in rows
    assert rows["capability-orchestrator"]["owner"] == "omega"
    assert "capability" in rows["capability-orchestrator"]["job"].lower()
    assert "evidence" in rows["capability-orchestrator"]["job"].lower()
    surfaced = {x["id"]: x for x in out["architecture"]["subsystems"]}
    assert surfaced["capability-orchestrator"]["status"] == "REGISTERED"
    assert out["authority"]["execution_authorized"] is False
    assert out["authority"]["production_decision_authorized"] is False


def test_brain_registers_ascendancy_candidate_foundry(tmp_path):
    out = brain_snapshot(tmp_path)
    rows = {x["id"]: x for x in SUBSYSTEMS}
    assert "ascendancy-foundry" in rows
    assert rows["ascendancy-foundry"]["owner"] == "omega"
    assert "candidate" in rows["ascendancy-foundry"]["job"].lower()
    assert "falsif" in rows["ascendancy-foundry"]["job"].lower()
    surfaced = {x["id"]: x for x in out["architecture"]["subsystems"]}
    assert surfaced["ascendancy-foundry"]["status"] == "REGISTERED"
    assert out["authority"]["execution_authorized"] is False
    assert out["authority"]["production_decision_authorized"] is False
