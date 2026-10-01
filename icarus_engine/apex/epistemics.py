"""Epistemic invariants and compact kernel state for APEX Ω."""
from __future__ import annotations
from datetime import datetime, timezone
import math
from typing import Any, Mapping
from .contracts import authority_flags, parse_utc
from .store import ApexStore


def _unit(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be numeric")
    x = float(value)
    if not math.isfinite(x) or not 0 <= x <= 1:
        raise ValueError(f"{field} must be in [0, 1]")
    return x


def validate_authority_invariants(payload: Mapping[str, Any]) -> None:
    if payload.get("execution_authorized") is True:
        raise ValueError("execution authority is forbidden in APEX research state")
    if payload.get("production_decision_authorized") is True:
        raise ValueError("production decision authority is forbidden in APEX research state")


def confidence_after_independence(nominal: float, support: Mapping[str, Any]) -> float:
    conf = _unit(nominal, "nominal")
    if not support.get("integrity_ok"):
        return 0.0
    nominal_n = support.get("nominal_support", 0)
    effective = support.get("effective_independent_families", 0)
    if isinstance(nominal_n, bool) or isinstance(effective, bool) or not isinstance(nominal_n, (int, float)) or not isinstance(effective, (int, float)):
        raise ValueError("support counts must be numeric")
    if nominal_n <= 0 or effective <= 0:
        return 0.0
    ratio = max(0.0, min(1.0, float(effective) / float(nominal_n)))
    return min(conf, conf * ratio)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def epistemic_kernel_snapshot(store: ApexStore, *, as_of: str | None = None) -> dict[str, Any]:
    boundary = as_of or _now()
    boundary_ts = parse_utc(boundary, "as_of").timestamp()
    evidence = store.evidence_as_of(boundary)
    with store._lock:
        belief_count = int(store._conn.execute("SELECT COUNT(*) FROM beliefs WHERE created_ts<=?", (boundary_ts,)).fetchone()[0])
    integrity = store.integrity_status()
    status = "DEGRADED" if not integrity["integrity_ok"] else "EMPTY" if not evidence and belief_count == 0 else "ACTIVE"
    snap = {
        "schema_version": "icarus-apex-epistemic-kernel-v1",
        "as_of": boundary,
        "status": status,
        "evidence_count": len(evidence),
        "belief_count": belief_count,
        "store": integrity,
        **authority_flags(),
    }
    validate_authority_invariants(snap)
    return snap
