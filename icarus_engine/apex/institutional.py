"""Institutional-mechanics evidence classifier for APEX Ω."""
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from .contracts import authority_flags, parse_utc

MECHANISMS = (
    "margin",
    "expiry",
    "settlement",
    "rebalance",
    "etf_creation_redemption",
    "vol_control",
    "cta_threshold",
    "dealer_gamma",
    "collateral",
    "basis_convergence",
)


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be numeric")
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"{field} must be finite")
    return out


def institutional_mechanics(evidence: Sequence[Mapping[str, Any]], *, asset: str, as_of: str, horizon_seconds: int) -> dict[str, Any]:
    asset = str(asset or "").strip().upper()
    boundary = parse_utc(as_of, "as_of").timestamp()
    selected: dict[str, list[Mapping[str, Any]]] = {m: [] for m in MECHANISMS}
    for e in evidence:
        if not isinstance(e, Mapping):
            continue
        v = e.get("value")
        if not isinstance(v, Mapping):
            continue
        mech = str(v.get("mechanism") or "").strip().lower()
        if mech not in selected or str(v.get("asset") or "").upper() != asset or v.get("horizon_seconds") != horizon_seconds:
            continue
        try:
            if parse_utc(str(e.get("observed_at") or ""), "observed_at").timestamp() > boundary:
                continue
            if parse_utc(str(e.get("received_at") or ""), "received_at").timestamp() > boundary:
                continue
        except ValueError:
            continue
        selected[mech].append(e)

    out = []
    for mechanism in MECHANISMS:
        rows = selected[mechanism]
        if not rows:
            out.append({"mechanism": mechanism, "status": "unavailable", "pressure": None, "direction": None, "evidence_ids": []})
            continue
        best = max(rows, key=lambda e: float(e.get("confidence", 0.0)))
        v = best["value"]
        kind = str(best.get("kind") or "inferred").lower()
        explicit = v.get("rule_explicit") is True
        if explicit and kind == "observed":
            status = "observed_rule"
        elif kind == "derived" and v.get("constraint_explicit") is True:
            status = "derived_constraint"
        else:
            status = "inferred_behavior"
        pressure = _finite(v.get("pressure"), "pressure")
        out.append({
            "mechanism": mechanism,
            "status": status,
            "pressure": pressure,
            "direction": str(v.get("direction") or "unknown").lower(),
            "confidence": _finite(best.get("confidence", 0.0), "confidence"),
            "evidence_ids": [str(e.get("evidence_id") or "") for e in rows],
        })
    return {
        "schema_version": "icarus-apex-institutional-v1",
        "asset": asset,
        "as_of": as_of,
        "horizon_seconds": horizon_seconds,
        "mechanisms": out,
        **authority_flags(),
    }
