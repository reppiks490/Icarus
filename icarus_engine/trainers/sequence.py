from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from icarus_engine.spec import FEATURE_KEYS

_SCHEMA = "icarus.trainer.sequence/1"
_MIN_SCALE = 1e-12


def _finite(value: Any, field: str) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if not math.isfinite(out):
        raise ValueError(f"{field} must be finite")
    return out


def _feature_vector(row: Mapping[str, Any]) -> dict[str, float]:
    features = row.get("x")
    if not isinstance(features, Mapping):
        raise ValueError("row.x must be a mapping")
    return {key: _finite(features.get(key), f"x.{key}") for key in FEATURE_KEYS}


def fit_standardizer(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Fit feature centering/scaling strictly from the supplied rows.

    Callers are responsible for passing only training rows. Constant features
    are assigned scale=1.0 so inference remains finite and deterministic.
    """
    if not rows:
        raise ValueError("standardizer needs training rows")
    vectors = [_feature_vector(row) for row in rows]
    n = len(vectors)
    mean: dict[str, float] = {}
    scale: dict[str, float] = {}
    for key in FEATURE_KEYS:
        mu = math.fsum(vec[key] for vec in vectors) / n
        variance = math.fsum((vec[key] - mu) ** 2 for vec in vectors) / n
        sigma = math.sqrt(max(variance, 0.0))
        mean[key] = mu
        scale[key] = sigma if sigma > _MIN_SCALE else 1.0
    return {
        "schema": _SCHEMA,
        "features": list(FEATURE_KEYS),
        "fitted_rows": n,
        "mean": mean,
        "scale": scale,
    }


def standardize_sequence(
    steps: Sequence[Mapping[str, Any]],
    standardizer: Mapping[str, Any],
) -> list[dict[str, float]]:
    features = standardizer.get("features")
    if list(features or ()) != list(FEATURE_KEYS):
        raise ValueError("standardizer feature contract mismatch")
    means = standardizer.get("mean")
    scales = standardizer.get("scale")
    if not isinstance(means, Mapping) or not isinstance(scales, Mapping):
        raise ValueError("invalid standardizer")
    out: list[dict[str, float]] = []
    for step in steps:
        vec = {key: _finite(step.get(key), f"x.{key}") for key in FEATURE_KEYS}
        normalized: dict[str, float] = {}
        for key in FEATURE_KEYS:
            mu = _finite(means.get(key), f"mean.{key}")
            sigma = _finite(scales.get(key), f"scale.{key}")
            if sigma <= 0.0:
                raise ValueError(f"scale.{key} must be positive")
            normalized[key] = (vec[key] - mu) / sigma
        out.append(normalized)
    return out


def causal_sequence_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    start: int,
    stop: int,
    sequence_length: int,
) -> list[dict[str, Any]]:
    """Create causal windows whose final step is the decision row.

    A sequence ending at row i contains only rows [i-L+1, ..., i]. The label
    belongs to row i and may reference its already-declared future label_ts,
    but no feature row after i is ever included.
    """
    if isinstance(sequence_length, bool) or int(sequence_length) != sequence_length or sequence_length < 2:
        raise ValueError("sequence_length must be an integer >= 2")
    sequence_length = int(sequence_length)
    if start < 0 or stop < start or stop > len(rows):
        raise ValueError("invalid sequence bounds")

    timestamps = [_finite(row.get("ts"), "ts") for row in rows]
    for left, right in zip(timestamps, timestamps[1:]):
        if right <= left:
            raise ValueError("sequence rows must have strictly increasing timestamps")

    out: list[dict[str, Any]] = []
    for end in range(start, stop):
        begin = end - sequence_length + 1
        if begin < 0:
            continue
        decision = rows[end]
        decision_ts = timestamps[end]
        label_ts = _finite(decision.get("label_ts"), "label_ts")
        if label_ts <= decision_ts:
            raise ValueError("label_ts must be after decision ts")
        y = int(decision.get("y") or 0)
        if y not in (-1, 1):
            raise ValueError("sequence labels must be -1 or 1")

        steps: list[dict[str, float]] = []
        for idx in range(begin, end + 1):
            if timestamps[idx] > decision_ts:
                raise ValueError("future feature row entered causal sequence")
            steps.append(_feature_vector(rows[idx]))

        out.append(
            {
                "start_index": begin,
                "end_index": end,
                "ts": decision_ts,
                "label_ts": label_ts,
                "y": y,
                "steps": steps,
            }
        )
    return out
