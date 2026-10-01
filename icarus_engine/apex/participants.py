"""Evidence-bounded participant-state reconstruction for ICARUS APEX Ω."""
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from .ancestry import EvidenceAncestry
from .contracts import authority_flags, parse_utc
from .epistemics import confidence_after_independence

PARTICIPANT_CLASSES = (
    "discretionary_retail",
    "breakout_retail",
    "leveraged_retail",
    "systematic_trend_cta",
    "volatility_control",
    "options_dealers",
    "liquidity_providers",
    "arbitrageurs",
    "leveraged_funds",
    "asset_managers",
    "passive_index",
    "crypto_leveraged",
    "onchain_large",
    "unknown",
)
_KNOWN = frozenset(PARTICIPANT_CLASSES)


def _finite_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be numeric")
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"{field} must be finite")
    return out


def _eligible(e: Mapping[str, Any], *, asset: str, boundary: float, horizon_seconds: int) -> bool:
    value = e.get("value")
    if not isinstance(value, Mapping):
        return False
    if str(value.get("asset") or "").strip().upper() != asset:
        return False
    if value.get("horizon_seconds") != horizon_seconds:
        return False
    try:
        observed = parse_utc(str(e.get("observed_at") or ""), "observed_at").timestamp()
        received = parse_utc(str(e.get("received_at") or ""), "received_at").timestamp()
    except ValueError:
        return False
    return observed <= boundary and received <= boundary


def participant_state(
    evidence: Sequence[Mapping[str, Any]], *, asset: str, as_of: str, horizon_seconds: int
) -> dict[str, Any]:
    asset = str(asset or "").strip().upper()
    if not asset:
        raise ValueError("asset is required")
    if isinstance(horizon_seconds, bool) or not isinstance(horizon_seconds, int) or horizon_seconds <= 0:
        raise ValueError("horizon_seconds must be a positive integer")
    boundary = parse_utc(as_of, "as_of").timestamp()

    rows = [e for e in evidence if isinstance(e, Mapping) and _eligible(e, asset=asset, boundary=boundary, horizon_seconds=horizon_seconds)]
    if not rows:
        return {
            "schema_version": "icarus-apex-participant-state-v1",
            "asset": asset,
            "as_of": as_of,
            "horizon_seconds": horizon_seconds,
            "status": "UNAVAILABLE",
            "classes": [],
            **authority_flags(),
        }

    ancestry = EvidenceAncestry()
    for e in evidence:
        if not isinstance(e, Mapping):
            continue
        eid = e.get("evidence_id")
        if isinstance(eid, str) and eid:
            try:
                ancestry.add(e)
            except ValueError:
                pass

    groups: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
    for e in rows:
        value = e["value"]
        reported = str(value.get("participant_class") or "unknown").strip().lower() or "unknown"
        normalized = reported if reported in _KNOWN else "unknown"
        groups.setdefault((normalized, reported), []).append(e)

    classes: list[dict[str, Any]] = []
    for (normalized, reported), items in sorted(groups.items()):
        components: list[dict[str, Any]] = []
        ids: list[str] = []
        confidences: list[float] = []
        long_support = 0
        short_support = 0
        for e in items:
            v = e["value"]
            eid = str(e.get("evidence_id") or "")
            if eid:
                ids.append(eid)
            direction = str(v.get("direction") or "unknown").strip().lower()
            if direction == "long":
                long_support += 1
            elif direction == "short":
                short_support += 1
            conf = _finite_number(e.get("confidence", 0.0), "confidence")
            if not 0.0 <= conf <= 1.0:
                raise ValueError("confidence must be in [0, 1]")
            confidences.append(conf)
            lo = _finite_number(v.get("price_low"), "price_low")
            hi = _finite_number(v.get("price_high"), "price_high")
            if hi < lo:
                raise ValueError("price_high cannot precede price_low")
            components.append({
                "metric": str(v.get("metric") or "").strip(),
                "direction": direction,
                "price_low": lo,
                "price_high": hi,
                "value": _finite_number(v.get("value"), "value"),
                "confidence": conf,
                "evidence_id": eid,
                "kind": str(e.get("kind") or "inferred").lower(),
            })
        support = ancestry.effective_support(ids)
        nominal_conf = sum(confidences) / len(confidences) if confidences else 0.0
        classes.append({
            "participant_class": normalized,
            "reported_class": reported,
            "nominal_evidence_count": len(items),
            "effective_independent_families": support["effective_independent_families"],
            "evidence_integrity_ok": support["integrity_ok"],
            "confidence": confidence_after_independence(nominal_conf, support),
            "long_support": long_support,
            "short_support": short_support,
            "components": components,
        })

    return {
        "schema_version": "icarus-apex-participant-state-v1",
        "asset": asset,
        "as_of": as_of,
        "horizon_seconds": horizon_seconds,
        "status": "ACTIVE" if classes else "UNAVAILABLE",
        "classes": classes,
        **authority_flags(),
    }


def participant_states_by_class(
    evidence: Sequence[Mapping[str, Any]], *, asset: str, as_of: str, horizon_seconds: int
) -> list[dict[str, Any]]:
    return participant_state(evidence, asset=asset, as_of=as_of, horizon_seconds=horizon_seconds)["classes"]
