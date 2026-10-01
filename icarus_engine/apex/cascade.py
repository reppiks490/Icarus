"""Cascade topology and reflexive-loop diagnostics for APEX Ω."""
from __future__ import annotations
import math
from typing import Any, Mapping
from .contracts import authority_flags

_SUPPORTED={"temporally_supported","mechanistically_supported","intervention_supported"}


def build_cascade_graph(*, forces: Mapping[str,Any], causal_graph: Mapping[str,Any], participant_state: Mapping[str,Any], liquidity_state: Mapping[str,Any], as_of: str) -> dict[str,Any]:
    active_force=any(isinstance(c,Mapping) and c.get("status")=="ACTIVE" and c.get("contributions") for c in forces.get("cells",[]) or [])
    edges=[]
    for raw in causal_graph.get("edges",[]) or []:
        if not isinstance(raw,Mapping): continue
        horizon=raw.get("horizon_seconds",0)
        delay=raw.get("estimated_delay_seconds",0)
        if isinstance(horizon,bool) or not isinstance(horizon,(int,float)) or horizon < 0: horizon=0
        if isinstance(delay,bool) or not isinstance(delay,(int,float)) or not math.isfinite(float(delay)): delay=0
        delay=max(0.0,min(float(delay),float(horizon)))
        status=str(raw.get("status") or "unknown")
        edges.append({
            "edge_id":raw.get("edge_id"),"source":raw.get("source"),"target":raw.get("target"),
            "horizon_seconds":int(horizon),"estimated_delay_seconds":delay,"status":status,
            "confidence":float(raw.get("confidence",0.0)),"active":bool(active_force and status in _SUPPORTED),
            "falsifiers":list(raw.get("falsifiers",[]) or []),"event_clustering_is_causal_proof":False,
        })
    edges.sort(key=lambda e:(not e["active"],-e["confidence"],str(e["source"]),str(e["target"])))
    return {"schema_version":"icarus-apex-cascade-v1","as_of":as_of,"edges":edges,"participant_context":participant_state,"liquidity_context":liquidity_state,**authority_flags()}


def cascade_paths(graph: Mapping[str,Any], *, max_depth: int=8) -> list[dict[str,Any]]:
    if max_depth<1: raise ValueError("max_depth must be positive")
    adj: dict[str,list[Mapping[str,Any]]]={}
    for e in graph.get("edges",[]) or []:
        if isinstance(e,Mapping) and e.get("active"):
            adj.setdefault(str(e.get("source")),[]).append(e)
    nodes=set(adj)
    for vals in adj.values():
        vals.sort(key=lambda e:(-float(e.get("confidence",0.0)),str(e.get("target"))))
        nodes.update(str(e.get("target")) for e in vals)
    roots=set(adj)-{str(e.get("target")) for vals in adj.values() for e in vals}
    if not roots: roots=set(adj)
    paths=[]
    def dfs(node: str, path: list[str], score: float):
        if len(path)-1>max_depth: return
        nexts=[e for e in adj.get(node,[]) if str(e.get("target")) not in path]
        if not nexts:
            if len(path)>1: paths.append({"nodes":path,"confidence":score})
            return
        for e in nexts:
            dfs(str(e["target"]),path+[str(e["target"])],score*float(e.get("confidence",0.0)))
    for r in sorted(roots): dfs(r,[r],1.0)
    paths.sort(key=lambda x:(-x["confidence"],x["nodes"]))
    return paths


def _canonical_cycle(nodes: list[str]) -> tuple[str,...]:
    rots=[tuple(nodes[i:]+nodes[:i]) for i in range(len(nodes))]
    return min(rots)


def reflexive_loops(graph: Mapping[str,Any], *, max_cycle: int=6) -> list[dict[str,Any]]:
    adj: dict[str,list[Mapping[str,Any]]]={}
    for e in graph.get("edges",[]) or []:
        if isinstance(e,Mapping) and e.get("active",True): adj.setdefault(str(e.get("source")),[]).append(e)
    found: dict[tuple[str,...],list[Mapping[str,Any]]]={}
    def dfs(start: str,node: str,path: list[str],edges: list[Mapping[str,Any]]):
        if len(path)>max_cycle: return
        for e in adj.get(node,[]):
            nxt=str(e.get("target"))
            if nxt==start and len(path)>=2:
                key=_canonical_cycle(path)
                found.setdefault(key,edges+[e]); continue
            if nxt in path: continue
            dfs(start,nxt,path+[nxt],edges+[e])
    for start in sorted(adj): dfs(start,start,[start],[])
    out=[]
    for key,edges in found.items():
        factors=[]
        for e in edges:
            conf=max(0.0,min(1.0,float(e.get("confidence",0.0))))
            if e.get("status")=="contradicted": conf*=0.25
            factors.append(conf)
        gain=1.0
        for f in factors: gain*=f
        gain=gain ** (1/max(1,len(factors)))
        damping=max(0.0,1.0-gain)
        out.append({"nodes":list(key),"gain":gain,"damping":damping,"edge_count":len(edges)})
    out.sort(key=lambda x:(-x["gain"],x["nodes"]))
    return out
