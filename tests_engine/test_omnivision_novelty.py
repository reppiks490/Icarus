import pytest

from icarus_engine.omnivision.novelty import screen_novelty


def test_exact_duplicate_is_redundant():
    series = [(i, float(i)) for i in range(30)]
    out = screen_novelty(series, {"existing": series})
    assert out["status"] == "redundant"
    assert out["closest_feature"] == "existing"
    assert out["pairs"] == 30
    assert out["max_abs_correlation"] == 1.0


def test_distinct_orthogonal_pattern_can_pass():
    candidate = [(i, float(i % 2)) for i in range(40)]
    existing = [(i, float((i // 2) % 2)) for i in range(40)]
    out = screen_novelty(candidate, {"existing": existing}, max_abs_correlation=0.95)
    assert out["status"] == "novel"
    assert out["max_abs_correlation"] < 0.95


def test_alignment_never_fills_missing_rows():
    candidate = [(i, float(i)) for i in range(30)]
    existing = [(100 + i, float(i)) for i in range(30)]
    out = screen_novelty(candidate, {"x": existing})
    assert out["status"] == "insufficient_data"
    assert out["pairs"] == 0


def test_high_negative_correlation_is_redundant():
    candidate = [(i, float(i)) for i in range(30)]
    existing = [(i, float(-i)) for i in range(30)]
    out = screen_novelty(candidate, {"inverse": existing}, max_abs_correlation=0.9)
    assert out["status"] == "redundant"
    assert out["closest_feature"] == "inverse"
    assert out["max_abs_correlation"] == pytest.approx(1.0)


def test_duplicate_timestamps_rejected():
    with pytest.raises(ValueError, match="duplicate timestamp"):
        screen_novelty([(1, 1.0), (1, 2.0)], {"x": [(1, 1.0), (2, 2.0)]}, min_pairs=2)


def test_constant_nonduplicate_comparison_is_insufficient():
    candidate = [(i, 1.0) for i in range(30)]
    existing = [(i, 2.0) for i in range(30)]
    out = screen_novelty(candidate, {"constant": existing})
    assert out["status"] == "insufficient_data"
    assert out["pairs"] == 30


@pytest.mark.parametrize("threshold", [0, -0.1, 1.1, True])
def test_invalid_threshold_rejected(threshold):
    with pytest.raises(ValueError):
        screen_novelty([(i, float(i)) for i in range(30)], {}, max_abs_correlation=threshold)
