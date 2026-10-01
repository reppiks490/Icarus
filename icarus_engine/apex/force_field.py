"""Multi-source market-pressure tensor for APEX Ω."""
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from .contracts import authority_flags


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be numeric")
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"{field} must be finite")
    return out


def _direction_sign(direction: str) -> float | None:
    d = direction.lower()
    if d in {"buy", "long", "up"}:
        return 1.0
    if d in {"sell", "short", "down"}:
        return -1.0
    return None


def pressure_tensor(*, participants: Mapping[str, Any], crowd: Mapping[str, Any], institutional: Mapping[str, Any], liquidity: Mapping[str, Any], price_grid: Sequence[float], horizons: Sequence[int]) -> dict[str, Any]:
    cells: list[dict[str, Any]] = []
    classes = participants.get("classes", []) if isinstance(participants, Mapping) else []
    for h in horizons:
        if isinstance(h, bool) or not isinstance(h, int) or h <= 0:
            raise ValueError("horizons must contain positive integers")
        for raw_price in price_grid:
            p = _finite(raw_price, "price")
            contributions: list[dict[str, Any]] = []
            for cls in classes or []:
                if not isinstance(cls, Mapping):
                    continue
                for c in cls.get("components", []) or []:
                    if not isinstance(c, Mapping) or c.get("metric") != "forced_action_propensity":
                        continue
                    lo, hi = _finite(c.get("price_low"), "price_low"), _finite(c.get("price_high"), "price_high")
                    if not lo <= p <= hi:
                        continue
                    direction = str(c.get("direction") or "unknown").lower()
                    sign = _direction_sign(direction)
                    if sign is None:
                        continue
                    value = _finite(c.get("value"), "value")
                    conf = _finite(c.get("confidence", 0.0), "confidence")
                    contributions.append({
                        "source": "participant",
                        "participant_class": cls.get("participant_class", "unknown"),
                        "direction": direction,
                        "pressure": value,
                        "signed_pressure": sign * value,
                        "confidence": conf,
                        "evidence_id": c.get("evidence_id"),
                    })
            for m in (institutional.get("mechanisms", []) if isinstance(institutional, Mapping) else []) or []:
                if not isinstance(m, Mapping) or m.get("pressure") is None or m.get("status") == "unavailable":
                    continue
                direction = str(m.get("direction") or "unknown").lower()
                sign = _direction_sign(direction)
                if sign is None:
                    continue
                value = _finite(m.get("pressure"), "pressure")
                contributions.append({
                    "source": "institutional",
                    "mechanism": m.get("mechanism"),
                    "direction": direction,
                    "pressure": value,
                    "signed_pressure": sign * value,
                    "confidence": m.get("confidence"),
                    "evidence_ids": m.get("evidence_ids", []),
                })
            net = None if not contributions else round(sum(float(x["signed_pressure"]) for x in contributions), 12)
            cells.append({
                "price": p,
                "horizon_seconds": h,
                "status": "ACTIVE" if contributions else "UNAVAILABLE",
                "contributions": contributions,
                "net_pressure": net,
                "confidence": None if not contributions else min(float(x.get("confidence") or 0.0) for x in contributions),
            })
    return {
        "schema_version": "icarus-apex-pressure-tensor-v1",
        "cells": cells,
        "liquidity_context": liquidity if isinstance(liquidity, Mapping) else {},
        "crowd_context": crowd if isinstance(crowd, Mapping) else {},
        **authority_flags(),
    }


def dominant_forces(tensor: Mapping[str, Any], *, limit: int = 10) -> list[dict[str, Any]]:
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError("limit must be a positive integer")
    forces = []
    for cell in tensor.get("cells", []) if isinstance(tensor, Mapping) else []:
        for c in cell.get("contributions", []) if isinstance(cell, Mapping) else []:
            forces.append({**c, "price": cell.get("price"), "horizon_seconds": cell.get("horizon_seconds")})
    forces.sort(key=lambda x: (-abs(float(x.get("signed_pressure", 0.0))), str(x.get("source")), str(x.get("participant_class") or x.get("mechanism") or "")))
    return forces[:limit]
