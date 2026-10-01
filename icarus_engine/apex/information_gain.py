"""Active information-value and research-compute ranking for APEX Ω."""
from __future__ import annotations
import math
from copy import deepcopy
from typing import Any, Mapping, Sequence
from .contracts import authority_flags
def _unit(value:Any,field:str,default:float=0.0)->float:
    if value is None:return default
    if isinstance(value,bool) or not isinstance(value,(int,float)):raise ValueError(f"{field} must be numeric")
    out=float(value)
    if not math.isfinite(out) or out<0:raise ValueError(f"{field} must be finite and non-negative")
    return out
def rank_observations(candidates:Sequence[Mapping[str,Any]],*,uncertainty_state:Mapping[str,Any],acquisition_costs:Mapping[str,float],availability:Mapping[str,bool])->list[dict[str,Any]]:
    ranked=[]
    for row in candidates:
        cid=str(row.get("id") or "").strip()
        if not cid:raise ValueError("candidate id is required")
        is_available=availability.get(cid,False) is True; redundancy=min(1.0,_unit(row.get("redundancy",0.0),"redundancy")); reduction=_unit(row.get("uncertainty_reduction",0.0),"uncertainty_reduction"); improvement=_unit(row.get("decision_improvement",0.0),"decision_improvement"); cost=_unit(acquisition_costs.get(cid,0.0),"acquisition_cost")
        score=None if not is_available else max(0.0,((reduction+improvement)/2.0)*(1.0-redundancy)-cost)
        ranked.append({"id":cid,"status":"AVAILABLE" if is_available else "UNAVAILABLE","score":score,"redundancy":redundancy})
    ranked.sort(key=lambda x:(x["status"]!="AVAILABLE",-(x["score"] if x["score"] is not None else -1.0),x["id"]));return ranked
def rank_experiments(hypotheses:Sequence[Any],experiments:Sequence[Mapping[str,Any]])->list[dict[str,Any]]:
    n=max(1,len(hypotheses));out=[]
    for exp in experiments:
        eid=str(exp.get("id") or "").strip();discrimination=_unit(exp.get("discrimination",0.0),"discrimination");cost=_unit(exp.get("cost",0.0),"cost");score=max(0.0,discrimination*min(1.0,n/2.0)-cost);out.append({"id":eid,"score":score,"discrimination":discrimination,"cost":cost})
    out.sort(key=lambda x:(-x["score"],x["id"]));return out
def rank_compute_jobs(jobs:Sequence[Mapping[str,Any]],*,opportunity:Mapping[str,float],uncertainty_reduction:Mapping[str,float],impact:Mapping[str,float],urgency:Mapping[str,float],compute_cost:Mapping[str,float])->list[dict[str,Any]]:
    out=[]
    for job in jobs:
        jid=str(job.get("id") or "").strip()
        if not jid:raise ValueError("job id is required")
        opp=_unit(opportunity.get(jid,0.0),"opportunity");unc=_unit(uncertainty_reduction.get(jid,0.0),"uncertainty_reduction");imp=_unit(impact.get(jid,0.0),"impact");urg=_unit(urgency.get(jid,0.0),"urgency");cost=_unit(compute_cost.get(jid,0.0),"compute_cost");score=(opp*unc*imp*urg)/max(cost,1e-9);out.append({"id":jid,"score":score,"compute_cost":cost})
    out.sort(key=lambda x:(-x["score"],x["id"]));return out
def scientific_governor_snapshot(*,unresolved_hypotheses:Sequence[Mapping[str,Any]],anomalies:Sequence[Mapping[str,Any]],experiments:Sequence[Mapping[str,Any]],compute_jobs:Sequence[Mapping[str,Any]])->dict[str,Any]:
    return {"schema_version":"icarus-apex-scientific-governor-v1","unresolved_hypotheses":deepcopy(list(unresolved_hypotheses)),"anomalies":deepcopy(list(anomalies)),"experiments":deepcopy(list(experiments)),"compute_jobs":deepcopy(list(compute_jobs)),**authority_flags()}
