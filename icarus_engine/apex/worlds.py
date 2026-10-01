"""Structured weighted counterfactual world population for APEX Ω."""
from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from typing import Any, Mapping, Sequence

from .contracts import authority_flags


def _finite_nonneg(v: Any, field: str) -> float:
    if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(float(v)) or float(v)<0:
        raise ValueError(f"{field} must be finite and non-negative")
    return float(v)


def _hash_state(state: Mapping[str,Any], assumptions: Sequence[Any]) -> str:
    raw=json.dumps({"state":state,"assumptions":list(assumptions)},sort_keys=True,separators=(",",":"),allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


class WorldPopulation:
    def __init__(self, *, max_worlds: int=256):
        if isinstance(max_worlds,bool) or not isinstance(max_worlds,int) or max_worlds<1: raise ValueError("max_worlds must be positive")
        self.max_worlds=max_worlds; self._worlds: dict[str,dict[str,Any]]={}; self._status="EMPTY"

    def seed(self, worlds: Sequence[Mapping[str,Any]]) -> None:
        if len(worlds)>self.max_worlds: raise ValueError("world population exceeds max_worlds")
        staged=[]; total=0.0
        for raw in worlds:
            if not isinstance(raw,Mapping): raise ValueError("world must be an object")
            if raw.get("execution_authorized") is True or raw.get("production_decision_authorized") is True: raise ValueError("world cannot authorize")
            wid=str(raw.get("world_id") or "").strip()
            if not wid: raise ValueError("world_id required")
            weight=_finite_nonneg(raw.get("weight",0.0),"weight"); total+=weight
            staged.append({"world_id":wid,"state":deepcopy(dict(raw.get("state") or {})),"assumptions":deepcopy(list(raw.get("assumptions") or [])),"weight":weight,**authority_flags()})
        if staged and total<=0: raise ValueError("seed weights must have positive mass")
        for x in staged: x["weight"]=x["weight"]/total if total else 0.0
        self._worlds={x["world_id"]:x for x in staged}; self._status="ACTIVE" if staged else "EMPTY"

    def update(self, observation: Mapping[str,Any]) -> dict[str,Any]:
        likes=observation.get("likelihoods",{}) if isinstance(observation,Mapping) else {}
        if not isinstance(likes,Mapping): raise ValueError("likelihoods must be an object")
        weighted=[]; total=0.0
        for wid,w in self._worlds.items():
            like=_finite_nonneg(likes.get(wid,1.0),"likelihood")
            val=w["weight"]*like; weighted.append((wid,val)); total+=val
        if self._worlds and total<=0:
            for w in self._worlds.values(): w["weight"]=0.0
            self._status="UNRESOLVED"
        elif total>0:
            for wid,val in weighted: self._worlds[wid]["weight"]=val/total
            self._status="ACTIVE"
        return self.snapshot()

    def split(self, world_id: str, branches: Sequence[Mapping[str,Any]]) -> list[str]:
        parent=self._worlds.get(world_id)
        if parent is None: raise KeyError(world_id)
        if len(self._worlds)-1+len(branches)>self.max_worlds: raise ValueError("split exceeds max_worlds")
        shares=[_finite_nonneg(b.get("weight_share",0.0),"weight_share") for b in branches]
        total=sum(shares)
        if total<=0: raise ValueError("branches require positive weight_share")
        del self._worlds[world_id]
        ids=[]
        for i,(b,share) in enumerate(zip(branches,shares)):
            state=deepcopy(dict(b.get("state") or parent["state"])); assumptions=deepcopy(list(parent["assumptions"]))+deepcopy(list(b.get("assumptions") or []))
            semantic={"state":state,"assumptions":assumptions,"parent":world_id,"ordinal":i}
            wid=hashlib.sha256(json.dumps(semantic,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()[:24]
            self._worlds[wid]={"world_id":wid,"state":state,"assumptions":assumptions,"weight":parent["weight"]*(share/total),**authority_flags()}; ids.append(wid)
        return ids

    def merge_equivalent(self) -> int:
        groups: dict[str,list[str]]={}
        for wid,w in self._worlds.items(): groups.setdefault(_hash_state(w["state"],w["assumptions"]),[]).append(wid)
        merged=0
        for ids in groups.values():
            if len(ids)<2: continue
            keep=sorted(ids)[0]; total=sum(self._worlds[i]["weight"] for i in ids)
            self._worlds[keep]["weight"]=total
            for i in ids:
                if i!=keep: del self._worlds[i]; merged+=1
        return merged

    def snapshot(self) -> dict[str,Any]:
        return {"schema_version":"icarus-apex-world-population-v1","status":self._status,"worlds":[deepcopy(self._worlds[k]) for k in sorted(self._worlds)],**authority_flags()}
