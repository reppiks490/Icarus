"""Bounded recursive expectations for APEX Ω."""
from __future__ import annotations
import math
from typing import Any, Mapping, Sequence
from .contracts import authority_flags


def _unit(x: Any) -> float:
    if isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(float(x)) or not 0<=float(x)<=1:
        raise ValueError("confidence must be in [0, 1]")
    return float(x)


def expectation_graph(evidence: Sequence[Mapping[str,Any]], *, max_depth: int=3, depth_penalty: float=0.65) -> dict[str,Any]:
    if isinstance(max_depth,bool) or not isinstance(max_depth,int) or max_depth<1: raise ValueError("max_depth must be positive")
    penalty=_unit(depth_penalty)
    edges=[]
    for row in evidence:
        if not isinstance(row,Mapping): continue
        ids=row.get("evidence_ids")
        if not isinstance(ids,list) or not ids: continue
        believer=str(row.get("believer") or "").strip(); about=str(row.get("about") or "").strip(); belief=str(row.get("belief") or "").strip()
        if not believer or not about or not belief: continue
        edges.append({"believer":believer,"about":about,"belief":belief,"confidence":_unit(row.get("confidence",0.0)),"evidence_ids":[str(x) for x in ids]})
    edges.sort(key=lambda x:(x["believer"],x["about"],x["belief"]))
    return {"schema_version":"icarus-apex-expectations-v1","max_depth":max_depth,"depth_penalty":penalty,"edges":edges,**authority_flags()}


def expectation_paths(graph: Mapping[str,Any], *, participant: str) -> list[dict[str,Any]]:
    max_depth=int(graph.get("max_depth",3)); penalty=float(graph.get("depth_penalty",0.65))
    adj: dict[str,list[Mapping[str,Any]]]={}
    for e in graph.get("edges",[]) or []: adj.setdefault(e["believer"],[]).append(e)
    for vals in adj.values(): vals.sort(key=lambda e:(e["about"],e["belief"]))
    out=[]
    def walk(node: str, depth: int, confidence: float, seen: set[str]):
        if depth >= max_depth: return
        for e in adj.get(node,[]):
            nxt=e["about"]
            if nxt in seen: continue
            d=depth+1
            conf=min(confidence,float(e["confidence"])) * (penalty ** (d-1))
            out.append({"from":node,"to":nxt,"belief":e["belief"],"depth":d,"confidence":conf,"evidence_ids":e["evidence_ids"]})
            walk(nxt,d,min(confidence,float(e["confidence"])),seen|{nxt})
    walk(participant,0,1.0,{participant})
    out.sort(key=lambda x:(x["depth"],-x["confidence"],x["from"],x["to"]))
    return out
