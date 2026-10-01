"""Typed multi-horizon causal-claim graph for APEX Ω."""
from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Mapping

from .contracts import authority_flags, parse_utc

CAUSAL_STATUSES = frozenset({
    "correlated", "temporally_supported", "mechanistically_supported",
    "intervention_supported", "contradicted", "unknown",
})


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _unit(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be numeric")
    x=float(value)
    if not math.isfinite(x) or not 0 <= x <= 1:
        raise ValueError(f"{field} must be in [0, 1]")
    return x


def _strings(value: Any, field: str) -> list[str]:
    if value is None: return []
    if not isinstance(value, list): raise ValueError(f"{field} must be a list")
    return [_text(x, f"{field} item") for x in value]


def causal_edge(body: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(body, Mapping): raise ValueError("causal edge must be an object")
    status=_text(body.get("status"),"status").lower()
    if status not in CAUSAL_STATUSES: raise ValueError("unsupported causal status")
    source_precedes=body.get("source_precedes_target")
    if type(source_precedes) is not bool: raise ValueError("source_precedes_target must be boolean")
    obs=_unit(body.get("observational_support",0.0),"observational_support")
    mech=_unit(body.get("mechanistic_support",0.0),"mechanistic_support")
    inter=_unit(body.get("intervention_support",0.0),"intervention_support")
    if status in {"temporally_supported","mechanistically_supported","intervention_supported"} and not source_precedes:
        raise ValueError("temporal support requires source to precede target")
    if status in {"mechanistically_supported","intervention_supported"} and mech <= 0:
        raise ValueError("mechanistic support is required")
    if status == "intervention_supported" and inter <= 0:
        raise ValueError("intervention support is required")
    horizon=body.get("horizon_seconds")
    if isinstance(horizon,bool) or not isinstance(horizon,int) or horizon<=0: raise ValueError("horizon_seconds must be positive integer")
    observed_at=_text(body.get("observed_at"),"observed_at")
    received_at=_text(body.get("received_at"),"received_at")
    o=parse_utc(observed_at,"observed_at"); r=parse_utc(received_at,"received_at")
    if r < o: raise ValueError("received_at cannot precede observed_at")
    semantic={
        "schema_version":"icarus-apex-causal-edge-v1",
        "source":_text(body.get("source"),"source"),"target":_text(body.get("target"),"target"),
        "horizon_seconds":horizon,"observed_at":observed_at,"received_at":received_at,
        "source_precedes_target":source_precedes,"mechanism":_text(body.get("mechanism"),"mechanism"),
        "observational_support":obs,"mechanistic_support":mech,"intervention_support":inter,
        "confounders":_strings(body.get("confounders",[]),"confounders"),
        "contradictions":_strings(body.get("contradictions",[]),"contradictions"),
        "falsifiers":_strings(body.get("falsifiers",[]),"falsifiers"),
        "status":status,"confidence":_unit(body.get("confidence",0.0),"confidence"),
        **authority_flags(),
    }
    raw=json.dumps(semantic,sort_keys=True,separators=(",",":"),allow_nan=False).encode()
    semantic["edge_id"]=hashlib.sha256(raw).hexdigest()
    return semantic


class CausalGraph:
    def __init__(self) -> None:
        self._edges: dict[str,dict[str,Any]]={}

    def add_edge(self, edge: Mapping[str, Any]) -> dict[str, Any]:
        row=dict(edge)
        eid=_text(row.get("edge_id"),"edge_id")
        prior=self._edges.get(eid)
        if prior is not None and prior != row: raise ValueError("causal edge identity collision")
        self._edges[eid]=row
        return row

    def edges_as_of(self, as_of: str, *, horizon_seconds: int | None = None) -> list[dict[str, Any]]:
        boundary=parse_utc(as_of,"as_of")
        rows=[]
        for e in self._edges.values():
            if parse_utc(e["observed_at"],"observed_at") > boundary or parse_utc(e["received_at"],"received_at") > boundary:
                continue
            if horizon_seconds is not None and e["horizon_seconds"] != horizon_seconds: continue
            rows.append(dict(e))
        rows.sort(key=lambda x:(x["horizon_seconds"],x["source"],x["target"],x["edge_id"]))
        return rows

    def pathways(self, source: str, target: str, *, max_depth: int = 6) -> list[list[str]]:
        if max_depth < 1: raise ValueError("max_depth must be positive")
        adjacency: dict[str,list[str]]={}
        for e in self._edges.values():
            if e.get("status") in {"contradicted","unknown"}: continue
            adjacency.setdefault(e["source"],[]).append(e["target"])
        for v in adjacency.values(): v.sort()
        out=[]
        def dfs(node: str, path: list[str]):
            if len(path)-1 > max_depth: return
            if node == target:
                out.append(path[:]); return
            if len(path)-1 == max_depth: return
            for nxt in adjacency.get(node,[]):
                if nxt in path: continue
                dfs(nxt,path+[nxt])
        dfs(source,[source])
        return out

    def snapshot(self) -> dict[str,Any]:
        return {"edges":[dict(e) for e in sorted(self._edges.values(),key=lambda x:x["edge_id"])], **authority_flags()}
