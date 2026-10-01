"""Economic world-state federation for APEX Ω."""
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from .contracts import authority_flags, parse_utc

DOMAINS=("growth","inflation","rates","credit","labor","consumption","production","fx","commodities","liquidity","earnings","policy")


def _conf(v: Any) -> float:
    if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(float(v)):
        raise ValueError("confidence must be finite")
    x=float(v)
    if not 0<=x<=1: raise ValueError("confidence must be in [0, 1]")
    return x


def economic_world_state(evidence: Sequence[Mapping[str,Any]], *, as_of: str) -> dict[str,Any]:
    boundary=parse_utc(as_of,"as_of")
    groups: dict[str,list[dict[str,Any]]]={d:[] for d in DOMAINS}
    for row in evidence:
        if not isinstance(row,Mapping): continue
        val=row.get("value")
        if not isinstance(val,Mapping): continue
        domain=str(val.get("domain") or "").lower()
        if domain not in groups: continue
        try:
            if parse_utc(str(row.get("observed_at") or ""),"observed_at")>boundary: continue
            if parse_utc(str(row.get("received_at") or ""),"received_at")>boundary: continue
        except ValueError: continue
        state=str(val.get("state") or "").strip()
        if not state: continue
        groups[domain].append({
            "state":state,"confidence":_conf(row.get("confidence",0.0)),
            "market_response":val.get("market_response"),"evidence_id":row.get("evidence_id"),
            "kind":str(row.get("kind") or "inferred"),
        })
    domains={}
    for domain,rows in groups.items():
        if not rows:
            domains[domain]={"status":"UNAVAILABLE","state":None,"market_response":None,"hypotheses":[]}
            continue
        rows=sorted(rows,key=lambda x:(-x["confidence"],x["state"],str(x.get("evidence_id"))))
        distinct={x["state"] for x in rows}
        best=rows[0]
        domains[domain]={
            "status":"CONTESTED" if len(distinct)>1 else "SUPPORTED",
            "state":best["state"],"market_response":best.get("market_response"),"hypotheses":rows,
        }
    return {"schema_version":"icarus-apex-economic-world-v1","as_of":as_of,"domains":domains,**authority_flags()}
