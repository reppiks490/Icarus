from __future__ import annotations

from pathlib import Path

import pytest

from icarus_engine.dreamstate import DreamstateLab, REQUIRED_GATES
from icarus_engine.parallax import ParallaxStore
from icarus_engine.brain import brain_snapshot


def _record_pair(store: ParallaxStore, i: int, *, delay_utility: float = 1.0):
    decision = store.record_decision(
        {
            "asset": "NQ",
            "action": "long",
            "observed_at": f"2026-10-01T05:{i:02d}:00Z",
            "regime": "trend-high-vol",
            "source_commit": "a" * 40,
            "context": {"bar": i, "vix_accel": 0.2},
            "subsystem_votes": {"athena": 0.8, "argus": 0.55},
        }
    )
    store.record_outcome(
        {
            "decision_id": decision["decision_id"],
            "label": "actual",
            "utility": 0.0,
            "metrics": {"r_multiple": 0.0},
            "evidence": [f"replay:{i}:actual"],
        }
    )
    store.record_outcome(
        {
            "decision_id": decision["decision_id"],
            "label": "delay_1",
            "utility": delay_utility,
            "metrics": {"r_multiple": delay_utility},
            "evidence": [f"replay:{i}:delay1"],
        }
    )
    return store.decision(decision["decision_id"])


def test_parallax_creates_shadow_twins_and_never_scores_unobserved(tmp_path):
    store = ParallaxStore(tmp_path)
    decision = store.record_decision(
        {
            "asset": "NQ",
            "action": "long",
            "observed_at": "2026-10-01T05:00:00Z",
            "regime": "trend",
            "source_commit": "a" * 40,
            "context": {"price": 25000.0},
            "subsystem_votes": {"athena": 0.7, "argus": 0.4},
        }
    )
    labels = {branch["label"] for branch in decision["branches"]}
    assert {"actual", "skip", "opposite", "delay_1", "stop_1.25", "size_0.50", "without_athena"} <= labels
    assert decision["analysis"]["regret"] is None
    assert decision["execution_authorized"] is False
    assert decision["production_decision_authorized"] is False

    updated = store.record_outcome(
        {
            "decision_id": decision["decision_id"],
            "label": "actual",
            "utility": 0.25,
            "metrics": {"pnl": 125.0},
            "evidence": ["paper-replay:actual"],
        }
    )
    assert updated["analysis"]["actual_utility"] == 0.25
    assert updated["analysis"]["regret"] == 0.0
    assert updated["analysis"]["observed_branch_count"] == 1


def test_parallax_outcomes_are_immutable(tmp_path):
    store = ParallaxStore(tmp_path)
    decision = _record_pair(store, 0)
    same = store.record_outcome(
        {
            "decision_id": decision["decision_id"],
            "label": "delay_1",
            "utility": 1.0,
            "metrics": {"r_multiple": 1.0},
            "evidence": ["different-evidence-is-not-a-rescore"],
        }
    )
    assert same["analysis"]["best_observed_branch"] == "delay_1"

    with pytest.raises(ValueError, match="immutable"):
        store.record_outcome(
            {
                "decision_id": decision["decision_id"],
                "label": "delay_1",
                "utility": 2.0,
                "metrics": {"r_multiple": 2.0},
            }
        )


def test_parallax_requires_repeated_positive_lower_bound_before_signal(tmp_path):
    store = ParallaxStore(tmp_path)
    for i in range(4):
        _record_pair(store, i)
    assert not [s for s in store.mutation_signals(min_samples=5) if s["branch_label"] == "delay_1"]

    _record_pair(store, 4)
    signals = [s for s in store.mutation_signals(min_samples=5) if s["branch_label"] == "delay_1"]
    assert len(signals) == 1
    assert signals[0]["kind"] == "delay"
    assert signals[0]["n"] == 5
    assert signals[0]["ci95_low"] > 0


def test_dreamstate_generates_hypothesis_but_caps_authority_at_qualified_shadow(tmp_path):
    store = ParallaxStore(tmp_path)
    for i in range(5):
        _record_pair(store, i)

    lab = DreamstateLab(tmp_path, parallax=store)
    state = lab.refresh(min_samples=5)
    candidates = [c for c in state["candidates"] if c["mutation"]["op"] == "set_execution_delay_bars"]
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["stage"] == "proposed"
    assert all(value is None for value in candidate["validation"].values())
    assert state["authority"]["maximum_stage"] == "qualified_shadow"
    assert state["authority"]["automatic_production_promotion"] is False
    assert state["authority"]["execution_authorized"] is False
    brain = brain_snapshot(tmp_path)
    mirrored = next(c for c in brain["candidates"] if c["candidate_id"] == candidate["candidate_id"])
    assert mirrored["stage"] == "discovered"
    assert mirrored["details"]["origin"] == "DREAMSTATE"
    assert mirrored["eligible_for_regime_swap"] is False

    qualified = lab.evaluate(
        candidate["candidate_id"],
        {
            "validation": {gate: True for gate in REQUIRED_GATES},
            "evidence": ["independent protected evaluation fixture"],
        },
    )
    assert qualified["stage"] == "qualified_shadow"
    assert qualified["execution_authorized"] is False
    assert qualified["production_decision_authorized"] is False
    brain = brain_snapshot(tmp_path)
    mirrored = next(c for c in brain["candidates"] if c["candidate_id"] == candidate["candidate_id"])
    assert mirrored["stage"] == "qualified_shadow"
    assert mirrored["eligible_for_regime_swap"] is True


def test_dreamstate_keeps_one_active_trial_per_family_as_evidence_grows(tmp_path):
    store = ParallaxStore(tmp_path)
    for i in range(5):
        _record_pair(store, i)
    lab = DreamstateLab(tmp_path, parallax=store)
    first = lab.refresh(min_samples=5)
    active = [c for c in first["candidates"] if c["mutation"]["op"] == "set_execution_delay_bars"]
    assert len(active) == 1
    first_id = active[0]["candidate_id"]

    _record_pair(store, 5)
    second = lab.refresh(min_samples=5)
    same_family = [c for c in second["candidates"] if c["family_id"] == active[0]["family_id"]]
    assert len(same_family) == 1
    assert same_family[0]["candidate_id"] == first_id
    assert second["refresh"]["skipped_active_family"] >= 1
    assert second["family_trial_budget"] == 12


def test_dreamstate_failed_gate_is_terminal_for_candidate_revision(tmp_path):
    store = ParallaxStore(tmp_path)
    for i in range(5):
        _record_pair(store, i)
    lab = DreamstateLab(tmp_path, parallax=store)
    candidate = lab.refresh(min_samples=5)["candidates"][0]

    rejected = lab.evaluate(
        candidate["candidate_id"],
        {"validation": {"protected_holdout": False}, "evidence": ["holdout failure"]},
    )
    assert rejected["stage"] == "rejected"
    with pytest.raises(ValueError, match="terminal"):
        lab.evaluate(candidate["candidate_id"], {"validation": {"protected_holdout": True}})


def test_parallax_dreamstate_are_visible_in_trader_interface():
    repo = Path(__file__).resolve().parents[1]
    dashboard = (repo / "icarus_engine" / "dashboard.html").read_text(encoding="utf-8")
    ui = (repo / "icarus_engine" / "parallax-ui.js").read_text(encoding="utf-8")
    server = (repo / "icarus_engine" / "server.py").read_text(encoding="utf-8")

    assert '/parallax-ui.js' in dashboard
    assert 'data-v="parallax">PARALLAX / DREAMSTATE</span>' in dashboard
    assert "wireParallax()" in dashboard
    assert "/api/parallax" in ui
    assert "/api/dreamstate" in ui
    assert "SHADOW ONLY" in ui
    assert 'p.path == "/api/parallax"' in server
    assert 'p.path == "/api/dreamstate"' in server
    assert 'p.path == "/admin/parallax/decision"' in server
    assert 'p.path == "/admin/parallax/outcome"' in server
    assert 'p.path == "/admin/dreamstate/refresh"' in server
    assert 'p.path == "/admin/dreamstate/evaluate"' in server
