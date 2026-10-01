"""Synthetic conscience: independent audit judges, not consciousness."""
from __future__ import annotations
from typing import Any, Mapping
from .contracts import authority_flags
_SEVERITY={"PASS":0,"UNMEASURED":1,"WARN":2,"OBJECT":3,"VETO":4}
def _judge(state:str,detail:str)->dict[str,str]: return {"state":state,"detail":detail}
def conscience_verdict(*,belief_packet:Mapping[str,Any],risk_context:Mapping[str,Any],capability_state:Mapping[str,Any],authority_context:Mapping[str,Any])->dict[str,Any]:
    evidence_kind=str(belief_packet.get("evidence_kind") or "").lower(); representation=str(belief_packet.get("claim_representation") or evidence_kind or "unknown").lower()
    truth=_judge("VETO","non-observed evidence represented as observed") if evidence_kind in {"inferred","reconstructed","derived"} and representation=="observed" else _judge("PASS","truth labels preserved")
    confidence=belief_packet.get("nominal_confidence"); uncertainty=_judge("PASS","uncertainty bounded") if isinstance(confidence,(int,float)) and not isinstance(confidence,bool) else _judge("UNMEASURED","confidence unavailable")
    tail=risk_context.get("tail_loss"); max_tail=risk_context.get("max_tail_loss")
    risk=_judge("VETO","tail loss exceeds declared maximum") if isinstance(tail,(int,float)) and not isinstance(tail,bool) and isinstance(max_tail,(int,float)) and not isinstance(max_tail,bool) and float(tail)>float(max_tail) else _judge("PASS","no declared risk limit breached")
    consistency=_judge("OBJECT","; ".join(str(x) for x in capability_state.get("contradictions",[]) or []) or "internal contradiction") if capability_state.get("consistent") is False else _judge("PASS","no declared internal contradiction")
    evidence_ids=belief_packet.get("evidence_ids"); provenance=_judge("PASS","provenance present") if isinstance(evidence_ids,list) and bool(evidence_ids) else _judge("OBJECT","missing evidence provenance")
    prod=authority_context.get("production_decision_authorized"); exe=authority_context.get("execution_authorized")
    if prod is True or exe is True: authority=_judge("VETO","authority escalation requested")
    elif prod is False and exe is False: authority=_judge("PASS","research_only")
    else: authority=_judge("UNMEASURED","authority context incomplete")
    judges={"Truth":truth,"Uncertainty":uncertainty,"Risk":risk,"Consistency":consistency,"Provenance":provenance,"Authority":authority}
    overall=max(judges.values(),key=lambda x:_SEVERITY[x["state"]])["state"]
    return {"schema_version":"icarus-apex-conscience-v1","judges":judges,"overall":overall,**authority_flags()}
