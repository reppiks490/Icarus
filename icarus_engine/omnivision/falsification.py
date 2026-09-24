"""Point-in-time falsification primitives for OMNIVISION."""
from __future__ import annotations

import math
import statistics
from typing import Sequence


def _rows(rows: Sequence[tuple[int, int, float]], name: str) -> dict[int, tuple[int, float]]:
    out = {}
    for row in rows:
        if not isinstance(row, (tuple, list)) or len(row) != 3:
            raise ValueError(f"{name} rows must be (observed_at, available_at, value)")
        observed, available, value = row
        if type(observed) is not int or type(available) is not int:
            raise ValueError("timestamps must be integers")
        if available < observed:
            raise ValueError("availability cannot precede observation")
        if observed in out:
            raise ValueError("duplicate observation")
        if isinstance(value, bool) or type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("values must be finite numbers")
        out[observed] = (available, float(value))
    return out


def _correlation(pairs):
    if len(pairs) < 2:
        return None
    x = [a for a, _ in pairs]
    y = [b for _, b in pairs]
    mx, my = statistics.mean(x), statistics.mean(y)
    sx = sum((v - mx) ** 2 for v in x)
    sy = sum((v - my) ** 2 for v in y)
    if sx == 0 or sy == 0:
        return None
    cov = sum((a - mx) * (b - my) for a, b in pairs)
    return max(-1.0, min(1.0, cov / math.sqrt(sx * sy)))


def aligned_pairs(feature_rows: Sequence[tuple[int, int, float]],
                  outcome_rows: Sequence[tuple[int, int, float]],
                  *, decision_cutoff: int, lag_seconds: int) -> list[tuple[float, float]]:
    if type(decision_cutoff) is not int or decision_cutoff < 0:
        raise ValueError("decision_cutoff must be a non-negative integer")
    if type(lag_seconds) is not int or lag_seconds < 0:
        raise ValueError("lag_seconds must be a non-negative integer")
    features = _rows(feature_rows, "feature")
    outcomes = _rows(outcome_rows, "outcome")
    pairs = []
    for observed in sorted(features):
        feature_available, feature_value = features[observed]
        target = observed + lag_seconds
        outcome = outcomes.get(target)
        if outcome is None:
            continue
        outcome_available, outcome_value = outcome
        if feature_available <= decision_cutoff and outcome_available <= decision_cutoff:
            pairs.append((feature_value, outcome_value))
    return pairs


def placebo_shift_test(feature_rows: Sequence[tuple[int, int, float]],
                       outcome_rows: Sequence[tuple[int, int, float]],
                       *, decision_cutoff: int, lag_seconds: int,
                       placebo_shift_seconds: int, min_pairs: int = 20) -> dict:
    if type(placebo_shift_seconds) is not int:
        raise ValueError("placebo_shift_seconds must be an integer")
    placebo_lag = lag_seconds + placebo_shift_seconds
    if placebo_lag < 0:
        raise ValueError("placebo lag cannot be negative")
    if type(min_pairs) is not int or min_pairs < 2:
        raise ValueError("min_pairs must be an integer >= 2")

    real_pairs = aligned_pairs(
        feature_rows, outcome_rows,
        decision_cutoff=decision_cutoff, lag_seconds=lag_seconds,
    )
    placebo_pairs = aligned_pairs(
        feature_rows, outcome_rows,
        decision_cutoff=decision_cutoff, lag_seconds=placebo_lag,
    )
    real = _correlation(real_pairs)
    placebo = _correlation(placebo_pairs)
    enough = len(real_pairs) >= min_pairs and len(placebo_pairs) >= min_pairs
    if not enough or real is None or placebo is None:
        return {
            "status": "insufficient_data",
            "real_abs_correlation": None if real is None else abs(real),
            "placebo_abs_correlation": None if placebo is None else abs(placebo),
            "pairs": len(real_pairs),
            "placebo_pairs": len(placebo_pairs),
            "passed": False,
        }
    return {
        "status": "complete",
        "real_abs_correlation": abs(real),
        "placebo_abs_correlation": abs(placebo),
        "pairs": len(real_pairs),
        "placebo_pairs": len(placebo_pairs),
        "passed": abs(real) > abs(placebo),
    }


def walk_forward_correlation(feature_rows: Sequence[tuple[int, int, float]],
                             outcome_rows: Sequence[tuple[int, int, float]],
                             *, cutoffs: Sequence[int], lag_seconds: int,
                             min_pairs: int = 20) -> dict:
    if not isinstance(cutoffs, (tuple, list)) or not cutoffs:
        raise ValueError("cutoffs must be a non-empty sequence")
    if len(set(cutoffs)) != len(cutoffs) or any(type(c) is not int or c < 0 for c in cutoffs):
        raise ValueError("cutoffs must be unique non-negative integers")
    if type(min_pairs) is not int or min_pairs < 2:
        raise ValueError("min_pairs must be an integer >= 2")
    if type(lag_seconds) is not int or lag_seconds < 0:
        raise ValueError("lag_seconds must be a non-negative integer")

    folds = []
    qualified = []
    for cutoff in cutoffs:
        pairs = aligned_pairs(
            feature_rows, outcome_rows,
            decision_cutoff=cutoff, lag_seconds=lag_seconds,
        )
        corr = _correlation(pairs)
        status = "complete" if len(pairs) >= min_pairs and corr is not None else "insufficient_data"
        fold = {
            "cutoff": cutoff,
            "pairs": len(pairs),
            "correlation": corr,
            "status": status,
        }
        folds.append(fold)
        if status == "complete":
            qualified.append(corr)

    signs = {1 if value > 0 else -1 if value < 0 else 0 for value in qualified}
    stable_sign = len(qualified) >= 1 and 0 not in signs and len(signs) == 1
    return {
        "folds": folds,
        "folds_total": len(folds),
        "folds_qualified": len(qualified),
        "median_correlation": statistics.median(qualified) if qualified else None,
        "stable_sign": stable_sign,
        "passed": len(qualified) >= 3 and stable_sign,
    }
