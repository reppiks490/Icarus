"""Bounded architecture proposal evaluation for APEX Ω."""
from __future__ import annotations
import math
from typing import Any, Mapping
from .contracts import authority_flags

def _nonneg(value:Any,field:str)->float|None:
    if value is None:return None
    if isinstance(value,bool) or not isinstance(value,(int,float)):raise ValueError(f"{field} must be numeric")
    out=float(value)
    if not math.isfinite(out) or out<0:raise ValueError(f"{field} must be finite and non-negative")
    return out

def evaluate_architecture_proposal(body:Mapping[str,Any])->dict[str,Any]:
    if not isinstance(body,Mapping):raise ValueError("proposal must be an object")
    proposal_id=str(body.get("proposal_id") or "").strip()
    if not proposal_id:raise ValueError("proposal_id is required")
    reasons=[]
    if str(body.get("requested_authority") or "").strip()!="research_only":reasons.append("authority")
    if body.get("reversible") is not True:reasons.append("reversibility")
    gain=_nonneg(body.get("independent_information_gain"),"independent_information_gain")
    reliability=_nonneg(body.get("reliability_gain"),"reliability_gain")
    costs=[_nonneg(body.get(name),name) for name in ("compute_cost","dependency_cost","failure_surface_cost")]
    if gain is None or reliability is None or any(x is None for x in costs):
        decision="WITHHOLD" if not reasons else "REJECT";value=None
    else:
        total=sum(float(x) for x in costs if x is not None)
        value=(gain*reliability)/max(total,1e-9)
        if value<0.01:reasons.append("complexity")
        decision="REJECT" if reasons else "ACCEPT_FOR_SANDBOX"
    return {"schema_version":"icarus-apex-evolution-v1","proposal_id":proposal_id,"decision":decision,"reasons":reasons,"complexity_adjusted_value":value,"next_stage":None if decision!="ACCEPT_FOR_SANDBOX" else "sandbox",**authority_flags()}
