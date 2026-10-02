"""Deterministic capability contracts for ICARUS ASCENDANCY.

The committed catalog describes provider contracts.  The dated audit is only a
point-in-time observation from an external research session; it must never be
presented as permanent runtime health.
"""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "icarus-ascendancy-capabilities-v1"
_ROOT = Path(__file__).resolve().parent


def _load(name: str) -> dict[str, Any]:
    raw = json.loads((_ROOT / name).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{name} must contain an object")
    return raw


def _rows() -> list[dict[str, Any]]:
    catalog = _load("capability_catalog.json")
    audit = _load("capability_audit_2026-10-02.json")
    observed = audit.get("providers") if isinstance(audit.get("providers"), dict) else {}
    out: list[dict[str, Any]] = []
    for item in catalog.get("providers", []):
        if not isinstance(item, dict):
            continue
        row = deepcopy(item)
        evidence = observed.get(row.get("id"), {})
        if not isinstance(evidence, dict):
            evidence = {}
        row["observed_status"] = str(evidence.get("status") or "UNVERIFIED")
        row["observed_detail"] = str(evidence.get("detail") or "No point-in-time probe recorded.")
        row["public_contract_only"] = True
        row["execution_authorized"] = False
        row["production_decision_authorized"] = False
        out.append(row)
    out.sort(key=lambda x: str(x.get("id") or ""))
    return out


def capability_snapshot() -> dict[str, Any]:
    audit = _load("capability_audit_2026-10-02.json")
    rows = _rows()
    blocked = sum(1 for row in rows if str(row["observed_status"]).startswith("BLOCKED"))
    verified = sum(1 for row in rows if str(row["observed_status"]).startswith("VERIFIED"))
    unprobed = sum(1 for row in rows if row["observed_status"] in {"AVAILABLE_UNPROBED", "UNVERIFIED"})
    return {
        "schema_version": SCHEMA_VERSION,
        "audit_observed_at": audit.get("observed_at"),
        "audit_rule": audit.get("rule"),
        "provider_count": len(rows),
        "verified_count": verified,
        "blocked_count": blocked,
        "unprobed_count": unprobed,
        "providers": rows,
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


def capability_contract(provider_id: str) -> dict[str, Any] | None:
    target = str(provider_id or "").strip().lower()
    for row in _rows():
        if str(row.get("id") or "").lower() == target:
            return row
    return None



def route_capabilities(required_claims: list[str] | tuple[str, ...]) -> dict[str, Any]:
    """Plan a capability route without invoking providers.

    Matching is intentionally exact.  A related capability is not silently
    substituted because doing so would change the evidence contract.
    """
    if not isinstance(required_claims, (list, tuple)) or not required_claims:
        raise ValueError("required_claims must be a non-empty list or tuple")
    required = []
    for value in required_claims:
        item = str(value or "").strip()
        if not item:
            raise ValueError("required claim cannot be empty")
        if item not in required:
            required.append(item)

    matches = []
    for row in _rows():
        allowed = {str(x) for x in row.get("claims_allowed", [])}
        if set(required) <= allowed:
            matches.append(row)

    def route_key(row: Mapping[str, Any]) -> tuple[int, str]:
        try:
            priority = int(row.get("route_priority", 100))
        except (TypeError, ValueError):
            priority = 100
        return priority, str(row.get("id") or "")

    matches.sort(key=route_key)
    selected = [
        row for row in matches
        if str(row.get("observed_status") or "").startswith("VERIFIED")
    ]
    blocked = [
        row for row in matches
        if str(row.get("observed_status") or "").startswith("BLOCKED")
    ]
    unverified = [
        row for row in matches
        if row not in selected and row not in blocked
    ]

    if selected:
        status = "ROUTABLE"
    elif blocked:
        status = "BLOCKED_NO_AVAILABLE_PROVIDER"
    else:
        status = "UNAVAILABLE_NO_MATCHING_PROVIDER"

    return {
        "schema_version": "icarus-ascendancy-capability-route-v1",
        "required_claims": required,
        "status": status,
        "selected": selected,
        "blocked": blocked,
        "unverified": unverified,
        "rule": "Exact evidence-contract match only; routing does not invoke a tool or grant authority.",
        "execution_authorized": False,
        "production_decision_authorized": False,
    }
