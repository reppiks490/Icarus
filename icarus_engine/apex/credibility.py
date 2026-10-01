"""Research credibility scoring for APEX Ω."""
from __future__ import annotations
import math
from typing import Any


def _unit(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be numeric")
    x = float(value)
    if not math.isfinite(x) or not 0 <= x <= 1:
        raise ValueError(f"{field} must be in [0, 1]")
    return x


def credibility_score(*, calibration: float | None, data_quality: float, independence: float, reality_gap: float | None) -> dict[str, Any]:
    quality = _unit(data_quality, "data_quality")
    indep = _unit(independence, "independence")
    if calibration is None:
        return {
            "status": "UNMEASURED", "score": None, "calibration": None,
            "data_quality": quality, "independence": indep,
            "reality_gap": None if reality_gap is None else _unit(reality_gap, "reality_gap"),
        }
    cal = _unit(calibration, "calibration")
    gap = 0.0 if reality_gap is None else _unit(reality_gap, "reality_gap")
    score = max(0.0, min(1.0, cal * quality * indep * (1.0 - gap)))
    return {"status": "MEASURED", "score": score, "calibration": cal, "data_quality": quality, "independence": indep, "reality_gap": gap}


def effective_model_diversity(models: list[dict[str, Any]]) -> dict[str, Any]:
    signatures: set[tuple[Any, ...]] = set()
    for model in models:
        if not isinstance(model, dict):
            raise ValueError("models must contain objects")
        data = tuple(sorted(str(x) for x in model.get("data_families", []) or []))
        features = tuple(sorted(str(x) for x in model.get("features", []) or []))
        architecture = str(model.get("architecture") or "")
        residual = str(model.get("residual_signature") or "")
        signatures.add((data, features, architecture, residual))
    nominal = len(models)
    effective = len(signatures)
    return {
        "nominal_model_count": nominal,
        "effective_model_count": effective,
        "monoculture_ratio": 0.0 if nominal == 0 else 1.0 - (effective / nominal),
    }
