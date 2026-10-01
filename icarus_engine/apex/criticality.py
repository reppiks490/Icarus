"""Conservative multi-diagnostic market criticality classifier."""
from __future__ import annotations
import math
from typing import Any, Mapping
from .contracts import authority_flags


def _maybe(mapping: Mapping[str,Any], key: str) -> float | None:
    v=mapping.get(key)
    if isinstance(v,bool) or not isinstance(v,(int,float)): return None
    x=float(v)
    if not math.isfinite(x): return None
    return max(0.0,min(1.0,x))


def criticality_state(*, liquidity: Mapping[str,Any], reflexivity: Mapping[str,Any], volatility_evidence: Mapping[str,Any], participant_concentration: Mapping[str,Any], cross_asset_evidence: Mapping[str,Any]) -> dict[str,Any]:
    vals=[_maybe(liquidity,"fragility"),_maybe(reflexivity,"gain"),_maybe(volatility_evidence,"expansion"),_maybe(participant_concentration,"concentration"),_maybe(cross_asset_evidence,"synchronization")]
    observed=[x for x in vals if x is not None]
    resilience=_maybe(liquidity,"resilience") or 0.0
    damping=_maybe(reflexivity,"damping") or 0.0
    if not observed:
        state="UNKNOWN"; score=None
    else:
        raw=sum(observed)/len(observed)
        score=max(0.0,min(1.0,raw - 0.25*resilience - 0.25*damping))
        high=sum(1 for x in observed if x>=0.7)
        if high>=4 and score>=0.65: state="CRITICAL"
        elif high>=3 and score>=0.55: state="METASTABLE"
        elif score>=0.45: state="COMPRESSED"
        else: state="STABLE"
    return {"schema_version":"icarus-apex-criticality-v1","state":state,"score":score,"diagnostics_observed":len(observed),"resilience":resilience,"damping":damping,**authority_flags()}
