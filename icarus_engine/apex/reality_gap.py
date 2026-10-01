"""Calibration-aware reality-gap monitor for APEX Ω."""
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from .contracts import authority_flags


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be numeric")
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"{field} must be finite")
    return out


def reality_gap(*, predictions: Sequence[float], observations: Sequence[float], calibration_contract: Mapping[str, Any]) -> dict[str, Any]:
    if len(predictions) != len(observations):
        raise ValueError("predictions and observations must have equal length")
    if not predictions:
        return {"schema_version":"icarus-apex-reality-gap-v1","state":"UNMEASURED","gap":None,"sample_count":0,**authority_flags()}
    scale = _finite(calibration_contract.get("scale", 1.0), "scale")
    if scale <= 0:
        raise ValueError("scale must be positive")
    errors=[abs(_finite(p,"prediction")-_finite(o,"observation"))/scale for p,o in zip(predictions,observations)]
    mean_error=sum(errors)/len(errors); gap=max(0.0,min(1.0,mean_error))
    if gap>=0.9: state="INVALID"
    elif gap>=0.6: state="DEGRADED"
    elif gap>=0.3: state="DRIFTING"
    else: state="NORMAL"
    return {"schema_version":"icarus-apex-reality-gap-v1","state":state,"gap":gap,"mean_scaled_error":mean_error,"sample_count":len(errors),**authority_flags()}
