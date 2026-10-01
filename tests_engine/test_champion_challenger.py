from __future__ import annotations

import pytest

from icarus_engine.champion_challenger import select_shadow_champion, wilson_interval


def row(candidate, successes, settled=40, brier=0.15, **overrides):
    base = {
        "candidate_id": candidate,
        "asset": "NQ",
        "regime": "TREND",
        "success_definition": "positive net outcome after configured costs",
        "horizon_seconds": 300,
        "settled": settled,
        "successes": successes,
        "success_rate": successes / settled,
        "brier_score": brier,
        "closed_regime_sample": True,
        "outcome_coverage": 1.0,
    }
    base.update(overrides)
    return base


def test_wilson_interval_is_bounded_and_contains_observed_rate():
    low, high = wilson_interval(30, 40)
    assert 0.0 <= low <= 0.75 <= high <= 1.0


def test_best_lower_bound_wins_shadow_tournament():
    out = select_shadow_champion([
        row("a", 30, brier=0.18),
        row("b", 34, brier=0.12),
    ])
    assert out["status"] == "SHADOW_CHAMPION_SELECTED"
    assert out["shadow_champion"] == "b"
    assert out["selection_mode"] == "EMPIRICAL_SHADOW_ONLY"
    assert out["execution_authorized"] is False
    assert out["production_decision_authorized"] is False


def test_hysteresis_retains_incumbent_until_lower_bound_clears_margin():
    rows = [
        row("incumbent", 32, settled=40, brier=0.12),
        row("challenger", 33, settled=40, brier=0.11),
    ]
    out = select_shadow_champion(
        rows,
        incumbent_id="incumbent",
        min_lower_bound_improvement=0.05,
    )
    assert out["shadow_champion"] == "incumbent"
    assert out["decision"] == "INCUMBENT_RETAINED_BY_HYSTERESIS"


def test_mixed_scopes_fail_closed():
    out = select_shadow_champion([
        row("a", 35),
        row("b", 35, horizon_seconds=600),
    ])
    assert out["status"] == "MIXED_SCOPE_BLOCKED"
    assert out["shadow_champion"] is None


def test_incomplete_or_small_samples_are_rejected():
    out = select_shadow_champion([
        row("small", 19, settled=20),
        row("incomplete", 35, outcome_coverage=0.9),
    ])
    assert out["status"] == "NO_ELIGIBLE_CANDIDATES"
    assert len(out["rejected"]) == 2


def test_bad_success_counts_fail_closed():
    out = select_shadow_champion([
        row("bad", 45, settled=40),
    ])
    assert out["status"] == "NO_ELIGIBLE_CANDIDATES"
    assert "successes outside [0, settled]" in out["rejected"][0]["blockers"]


def test_configuration_validation():
    with pytest.raises(ValueError):
        select_shadow_champion([], min_settled=5)
    with pytest.raises(ValueError):
        select_shadow_champion([], min_lower_bound_improvement=-0.01)
