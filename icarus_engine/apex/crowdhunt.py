"""Retail crowd topology derived from participant-state evidence."""
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from .contracts import authority_flags

_RETAIL = frozenset({"discretionary_retail", "breakout_retail", "leveraged_retail"})


def _price(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("price_grid must contain finite numbers")
    out = float(value)
    if not math.isfinite(out):
        raise ValueError("price_grid must contain finite numbers")
    return out


def _metric_value(components: list[Mapping[str, Any]], metric: str, directions: set[str], price: float) -> float | None:
    vals: list[tuple[float, float]] = []
    for c in components:
        if c.get("metric") != metric or str(c.get("direction") or "").lower() not in directions:
            continue
        lo, hi = float(c["price_low"]), float(c["price_high"])
        if lo <= price <= hi:
            vals.append((float(c["value"]), float(c.get("confidence", 0.0))))
    if not vals:
        return None
    denom = sum(max(0.0, conf) for _, conf in vals)
    if denom <= 0:
        return sum(v for v, _ in vals) / len(vals)
    return sum(v * max(0.0, conf) for v, conf in vals) / denom


def crowd_map(participant_state: Mapping[str, Any], *, price_grid: Sequence[float]) -> dict[str, Any]:
    if not isinstance(participant_state, Mapping):
        raise ValueError("participant_state must be an object")
    retail_components: list[Mapping[str, Any]] = []
    confidence_values: list[float] = []
    for cls in participant_state.get("classes", []) or []:
        if not isinstance(cls, Mapping) or cls.get("participant_class") not in _RETAIL:
            continue
        retail_components.extend(c for c in cls.get("components", []) if isinstance(c, Mapping))
        conf = cls.get("confidence")
        if isinstance(conf, (int, float)) and not isinstance(conf, bool) and math.isfinite(float(conf)):
            confidence_values.append(float(conf))

    cells = []
    for raw_price in price_grid:
        p = _price(raw_price)
        cell = {
            "price": p,
            "entry_long_density": _metric_value(retail_components, "entry_density", {"long", "buy"}, p),
            "entry_short_density": _metric_value(retail_components, "entry_density", {"short", "sell"}, p),
            "stop_density_below": _metric_value(retail_components, "stop_density", {"long", "sell"}, p),
            "stop_density_above": _metric_value(retail_components, "stop_density", {"short", "buy"}, p),
            "trapped_long_density": _metric_value(retail_components, "trapped_position_density", {"long"}, p),
            "trapped_short_density": _metric_value(retail_components, "trapped_position_density", {"short"}, p),
            "forced_exit_pressure": _metric_value(retail_components, "forced_action_propensity", {"sell", "buy", "long", "short"}, p),
        }
        cells.append(cell)

    return {
        "schema_version": "icarus-apex-crowdhunt-v1",
        "asset": participant_state.get("asset"),
        "as_of": participant_state.get("as_of"),
        "horizon_seconds": participant_state.get("horizon_seconds"),
        "status": "ACTIVE" if retail_components else "UNAVAILABLE",
        "confidence": min(confidence_values) if confidence_values else None,
        "cells": cells,
        "falsifiers": [
            "predicted crowd response fails to appear at mapped region",
            "new independent evidence contradicts the reconstructed crowd topology",
        ],
        **authority_flags(),
    }


def crowd_pain_gradient(crowd_state: Mapping[str, Any], price_grid: Sequence[float]) -> list[dict[str, Any]]:
    mapped = crowd_map(crowd_state, price_grid=price_grid)
    out = []
    for cell in mapped["cells"]:
        entry = cell["entry_long_density"]
        stop = cell["stop_density_below"]
        pressure = None if entry is None or stop is None else max(0.0, float(entry)) * max(0.0, float(stop))
        out.append({"price": cell["price"], "pain_gradient": pressure})
    return out
