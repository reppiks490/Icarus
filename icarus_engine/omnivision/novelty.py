"""Bounded redundancy screening for OMNIVISION research features."""
from __future__ import annotations

import math
import statistics
from typing import Mapping, Sequence


def _series(rows: Sequence[tuple[int, float]], name: str) -> dict[int, float]:
    points = {}
    for row in rows:
        if not isinstance(row, (tuple, list)) or len(row) != 2:
            raise ValueError(f"{name} rows must be (timestamp, value)")
        ts, value = row
        if type(ts) is not int:
            raise ValueError("timestamp must be an integer")
        if ts in points:
            raise ValueError("duplicate timestamp")
        if isinstance(value, bool) or type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError("series values must be finite numbers")
        points[ts] = float(value)
    return points


def _pearson(x, y):
    if len(x) != len(y) or len(x) < 2:
        return None
    mx, my = statistics.mean(x), statistics.mean(y)
    sx = sum((v - mx) ** 2 for v in x)
    sy = sum((v - my) ** 2 for v in y)
    if sx == 0 or sy == 0:
        return None
    cov = sum((a - mx) * (b - my) for a, b in zip(x, y))
    value = cov / math.sqrt(sx * sy)
    return max(-1.0, min(1.0, value))


def screen_novelty(candidate: Sequence[tuple[int, float]],
                   existing: Mapping[str, Sequence[tuple[int, float]]],
                   *, max_abs_correlation: float = 0.95, min_pairs: int = 20) -> dict:
    if (isinstance(max_abs_correlation, bool)
            or type(max_abs_correlation) not in (int, float)
            or not math.isfinite(max_abs_correlation)
            or not 0 < max_abs_correlation <= 1):
        raise ValueError("max_abs_correlation must be in (0,1]")
    if type(min_pairs) is not int or min_pairs < 2:
        raise ValueError("min_pairs must be an integer >= 2")
    if not isinstance(existing, Mapping):
        raise ValueError("existing must be a mapping")

    candidate_points = _series(candidate, "candidate")
    best = None
    best_pairs = 0
    comparable = False

    for feature in sorted(existing):
        if type(feature) is not str or not feature:
            raise ValueError("feature names must be non-empty strings")
        points = _series(existing[feature], feature)
        shared = sorted(candidate_points.keys() & points.keys())
        best_pairs = max(best_pairs, len(shared))
        if len(shared) < min_pairs:
            continue
        left = [candidate_points[t] for t in shared]
        right = [points[t] for t in shared]
        comparable = True
        if left == right:
            corr = 1.0
        else:
            corr = _pearson(left, right)
        if corr is None:
            continue
        item = (abs(corr), feature, len(shared))
        if best is None or item[0] > best[0] or (item[0] == best[0] and item[1] < best[1]):
            best = item

    if best is None:
        return {
            "status": "insufficient_data",
            "max_abs_correlation": None,
            "closest_feature": None,
            "pairs": best_pairs,
            "reason": "no aligned non-constant comparison" if comparable else "insufficient aligned observations",
        }

    magnitude, feature, pairs = best
    redundant = magnitude >= float(max_abs_correlation)
    return {
        "status": "redundant" if redundant else "novel",
        "max_abs_correlation": magnitude,
        "closest_feature": feature,
        "pairs": pairs,
        "reason": "absolute correlation exceeds redundancy threshold" if redundant
                  else "no existing feature exceeds redundancy threshold",
    }
