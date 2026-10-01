"""Fail-isolated read-only sibling adapters for APEX Ω."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Mapping

from .contracts import authority_flags


def safe_snapshot(name: str, producer: Callable[[], Mapping[str,Any]]) -> dict[str,Any]:
    base={"subsystem":str(name),**authority_flags()}
    try:
        snap=producer()
        if not isinstance(snap,Mapping): raise ValueError("snapshot must be an object")
        copied=deepcopy(dict(snap))
        if copied.get("execution_authorized") is True or copied.get("production_decision_authorized") is True:
            raise ValueError("snapshot attempted authority escalation")
        return {**base,"status":"AVAILABLE","snapshot":copied,"error":None}
    except Exception as ex:
        return {**base,"status":"DEGRADED","snapshot":None,"error":f"{type(ex).__name__}: {ex}"[:800]}


def sibling_evidence(*, possibility=None, chronofold=None, pantheon=None, parallax=None, dreamstate=None, sibyl=None) -> list[dict[str,Any]]:
    supplied={"psi":possibility,"chronofold":chronofold,"pantheon":pantheon,"parallax":parallax,"dreamstate":dreamstate,"sibyl":sibyl}
    out=[]
    for name,source in supplied.items():
        if source is None:
            out.append({"subsystem":name,"status":"UNAVAILABLE","snapshot":None,"error":None,**authority_flags()}); continue
        if callable(source): producer=source
        elif hasattr(source,"snapshot") and callable(source.snapshot): producer=source.snapshot
        else: producer=lambda source=source: source
        out.append(safe_snapshot(name,producer))
    return out
