"""Liquidity topology that keeps true depth distinct from proxies."""
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from .contracts import authority_flags, parse_utc


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be numeric")
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"{field} must be finite")
    return out


def liquidity_topology(evidence: Sequence[Mapping[str, Any]], *, asset: str, as_of: str, price_grid: Sequence[float]) -> dict[str, Any]:
    asset = str(asset or "").strip().upper()
    boundary = parse_utc(as_of, "as_of").timestamp()
    rows: list[Mapping[str, Any]] = []
    proxy_fields: set[str] = set()
    for e in evidence:
        if not isinstance(e, Mapping):
            continue
        v = e.get("value")
        if not isinstance(v, Mapping) or str(v.get("asset") or "").upper() != asset:
            continue
        try:
            if parse_utc(str(e.get("observed_at") or ""), "observed_at").timestamp() > boundary:
                continue
            if parse_utc(str(e.get("received_at") or ""), "received_at").timestamp() > boundary:
                continue
        except ValueError:
            continue
        rows.append(e)
        if v.get("proxy") is True or str(e.get("kind") or "") != "observed":
            for key in ("fragility", "resilience", "replenishment", "spread", "absorption"):
                if key in v:
                    proxy_fields.add(key)

    cells = []
    any_depth = False
    for raw in price_grid:
        p = _finite(raw, "price")
        depth = None
        spread = None
        proxies: dict[str, float] = {}
        for e in rows:
            v = e["value"]
            if "price" not in v or _finite(v["price"], "price") != p:
                continue
            if str(e.get("kind") or "") == "observed" and v.get("proxy") is not True and "depth" in v:
                depth = _finite(v["depth"], "depth")
                any_depth = True
            if "spread" in v:
                spread = _finite(v["spread"], "spread")
            if v.get("proxy") is True or str(e.get("kind") or "") != "observed":
                for key in proxy_fields:
                    if key in v:
                        proxies[key] = _finite(v[key], key)
        cells.append({"price": p, "depth": depth, "spread": spread, "proxies": proxies})
    return {
        "schema_version": "icarus-apex-liquidity-v1",
        "asset": asset,
        "as_of": as_of,
        "depth_status": "OBSERVED" if any_depth else "UNAVAILABLE",
        "proxy_fields": sorted(proxy_fields),
        "cells": cells,
        **authority_flags(),
    }
