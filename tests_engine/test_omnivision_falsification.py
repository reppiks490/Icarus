import pytest

from icarus_engine.omnivision.falsification import (
    aligned_pairs,
    placebo_shift_test,
    walk_forward_correlation,
)


def test_alignment_rejects_future_available_feature():
    features = [(10, 50, 1.0), (20, 20, 2.0)]
    outcomes = [(30, 30, 3.0), (40, 40, 4.0)]
    pairs = aligned_pairs(features, outcomes, decision_cutoff=40, lag_seconds=20)
    assert pairs == [(2.0, 4.0)]


def test_alignment_rejects_future_available_outcome():
    features = [(10, 10, 1.0), (20, 20, 2.0)]
    outcomes = [(30, 50, 3.0), (40, 40, 4.0)]
    assert aligned_pairs(features, outcomes, decision_cutoff=40, lag_seconds=20) == [(2.0, 4.0)]


def test_duplicate_observation_revision_is_rejected():
    with pytest.raises(ValueError, match="duplicate observation"):
        aligned_pairs(
            [(10, 10, 1.0), (10, 11, 2.0)],
            [(20, 20, 3.0)],
            decision_cutoff=30,
            lag_seconds=10,
        )


def test_placebo_that_matches_real_signal_fails_falsification():
    features = [(i, i, float(i)) for i in range(1, 80)]
    outcomes = [(i + 1, i + 1, float(i)) for i in range(1, 80)]
    out = placebo_shift_test(
        features,
        outcomes,
        decision_cutoff=80,
        lag_seconds=1,
        placebo_shift_seconds=0,
        min_pairs=20,
    )
    assert out["status"] == "complete"
    assert out["passed"] is False
    assert out["real_abs_correlation"] == pytest.approx(1.0)
    assert out["placebo_abs_correlation"] == pytest.approx(1.0)


def test_placebo_weaker_than_real_signal_can_pass():
    features = [(i, i, float(i % 7)) for i in range(1, 100)]
    outcomes = [(i + 1, i + 1, float(i % 7)) for i in range(1, 100)]
    out = placebo_shift_test(
        features,
        outcomes,
        decision_cutoff=100,
        lag_seconds=1,
        placebo_shift_seconds=5,
        min_pairs=20,
    )
    assert out["status"] == "complete"
    assert out["real_abs_correlation"] > out["placebo_abs_correlation"]
    assert out["passed"] is True


def test_constant_series_is_explicitly_insufficient():
    features = [(i, i, 1.0) for i in range(1, 50)]
    outcomes = [(i + 1, i + 1, 2.0) for i in range(1, 50)]
    out = placebo_shift_test(
        features,
        outcomes,
        decision_cutoff=50,
        lag_seconds=1,
        placebo_shift_seconds=2,
        min_pairs=20,
    )
    assert out["status"] == "insufficient_data"
    assert out["passed"] is False


def test_walk_forward_uses_each_fold_cutoff_and_requires_stable_sign():
    features = [(i, i, float(i)) for i in range(1, 101)]
    outcomes = [(i + 1, i + 1, float(i)) for i in range(1, 101)]
    out = walk_forward_correlation(
        features,
        outcomes,
        cutoffs=(40, 70, 100),
        lag_seconds=1,
        min_pairs=20,
    )
    assert out["folds_total"] == 3
    assert out["folds_qualified"] == 3
    assert out["stable_sign"] is True
    assert out["passed"] is True
    assert all(fold["pairs"] < 100 for fold in out["folds"])


def test_walk_forward_future_receipt_cannot_enter_earlier_fold():
    features = [(i, i, float(i)) for i in range(1, 70)]
    features.append((70, 100, 70.0))
    outcomes = [(i + 1, i + 1, float(i)) for i in range(1, 71)]
    out = walk_forward_correlation(
        features,
        outcomes,
        cutoffs=(40, 70, 100),
        lag_seconds=1,
        min_pairs=20,
    )
    assert out["folds"][1]["pairs"] == 69


@pytest.mark.parametrize("lag", [-1, True])
def test_invalid_lag_rejected(lag):
    with pytest.raises(ValueError):
        aligned_pairs([], [], decision_cutoff=10, lag_seconds=lag)
