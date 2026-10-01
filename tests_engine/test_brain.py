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
    assert out["qualification_receipts"]["candidate_revision_count"] == 0
    assert out["qualification_receipts"]["qualification_ready_count"] == 0


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


def test_qualification_receipts_are_visible_but_do_not_bypass_durable_stage_transition(tmp_path):
    validated = _candidate(
        status="verified",
        stage="validated",
        validation={
            "causal_time": None,
            "provenance": None,
            "oos": None,
            "protected_holdout": None,
            "multiple_testing": None,
            "costs_slippage_latency": None,
            "ablation": None,
            "calibration": None,
            "ood_drift": None,
            "deterministic_replay": None,
            "independent_verification": None,
        },
    )
    record_brain_event(tmp_path, validated)
    qualification = {
        "required_gates": list(validated["validation"]),
        "candidate_revision_count": 1,
        "qualification_ready_count": 1,
        "candidates": [{
            "candidate_id": "nq-trend-v1",
            "candidate_source_repo": "reppiks490/Icarus",
            "candidate_source_commit": "a" * 40,
            "candidate_source_revision": "reppiks490/Icarus@" + "a" * 40,
            "receipt_count": 11,
            "qualification_ready": True,
            "recommended_stage": "qualified_shadow",
            "blockers": [],
            "validation": {gate: True for gate in validated["validation"]},
            "execution_authorized": False,
            "production_decision_authorized": False,
        }],
        "execution_authorized": False,
        "production_decision_authorized": False,
    }
    out = brain_snapshot(
        tmp_path,
        qualification_receipts=qualification,
        market_status={
            "assets": [{"symbol": "NQ", "warm": True, "paused": False, "state": {"rate_regime_str": "STRONG"}}]
        },
    )
    candidate = out["candidates"][0]
    assert candidate["qualification_receipts"]["qualification_ready"] is True
    assert candidate["qualification_receipts"]["receipt_count"] == 11
    assert candidate["stage"] == "validated"
    assert candidate["eligible_for_regime_swap"] is False
    assert out["regime_routes"][0]["selected_candidate"] is None
    assert out["learning"]["qualification_ready_revisions"] == 1
