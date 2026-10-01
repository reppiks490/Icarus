"""Self-model and capability dependency graph for APEX Ω."""
from __future__ import annotations
from copy import deepcopy
from typing import Any, Mapping, Sequence
from .contracts import authority_flags

class CapabilityGraph:
    def __init__(self)->None: self._deps:dict[str,tuple[str,...]]={}
    def register(self, capability:str, prerequisites:Sequence[str])->None:
        cap=str(capability or "").strip()
        if not cap: raise ValueError("capability is required")
        deps=tuple(str(x or "").strip() for x in prerequisites)
        if any(not x for x in deps): raise ValueError("prerequisites must be non-empty")
        candidate=dict(self._deps); candidate[cap]=deps
        def visit(node:str,active:set[str],done:set[str])->None:
            if node in active: raise ValueError("capability cycle detected")
            if node in done: return
            active.add(node)
            for dep in candidate.get(node,()):
                if dep in candidate: visit(dep,active,done)
            active.remove(node); done.add(node)
        done:set[str]=set()
        for node in candidate: visit(node,set(),done)
        self._deps=candidate
    def status(self, available:Mapping[str,bool])->dict[str,dict[str,Any]]:
        memo:dict[str,bool]={}
        def resolve(cap:str)->bool:
            if cap in memo: return memo[cap]
            if cap not in self._deps:
                value=available.get(cap,False); memo[cap]=bool(value) if type(value) is bool else False; return memo[cap]
            prereqs=self._deps[cap]; own=available.get(cap,True)
            if type(own) is not bool: own=False
            memo[cap]=own and all(resolve(dep) for dep in prereqs); return memo[cap]
        out={}
        for cap in sorted(set(self._deps)|set(available)):
            deps=list(self._deps.get(cap,()))
            out[cap]={"available":resolve(cap),"prerequisites":deps,"missing_prerequisites":[dep for dep in deps if not resolve(dep)]}
        return out

def self_model_snapshot(*,source_commit:str,capabilities:Mapping[str,Any],model_health:Mapping[str,Any],compute:Mapping[str,Any],latency:Mapping[str,Any])->dict[str,Any]:
    revision=str(source_commit or "").strip().lower()
    if len(revision)!=40 or any(ch not in "0123456789abcdef" for ch in revision): raise ValueError("source_commit must be an exact 40-character Git SHA")
    latency_out=deepcopy(dict(latency)) or {"status":"UNMEASURED"}
    return {"schema_version":"icarus-apex-self-model-v1","source_commit":revision,"capabilities":deepcopy(dict(capabilities)),"model_health":deepcopy(dict(model_health)),"compute":deepcopy(dict(compute)),"latency":latency_out,**authority_flags()}
