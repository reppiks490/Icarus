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
    assert out["architecture"]["subsystem_count"] >= 12
    assert out["authority"]["production_decision_authorized"] is False
    assert out["authority"]["execution_authorized"] is False
    assert out["truth_contract"]["success_rate"] is None
    assert out["truth_contract"]["omnipotence_claim"] is False
    assert out["remote_sync"]["status"] == "not_configured"


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
