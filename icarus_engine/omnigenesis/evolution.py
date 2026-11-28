"""Phase 6: finite, non-executing capability evolution planner.

Creates reproducible proposals and resource-feasible research *plans*, never
autonomous workers, code commits, deployment, trading mutations or scheduling.
The proposal's "expected information gain" is a subjective estimate, not
measured market evidence. Every actual experiment requires independent review.
"""
from __future__ import annotations

import math
import re
from typing import Any, Mapping

from .contracts import identity

_HASH = re.compile(r"^[0-9a-f]{64}$")
_KIND = {"algorithm", "data_instrument", "model_family",
         "simulation", "verification_tool", "visualization"}
_AUTHORITY = {"research_only": True, "execution_authorized": False,
              "production_decision_authorized": False, "auto_promote": False}


def _real(value: Any, name: str, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    out = float(value)
    if not math.isfinite(out) or not low <= out <= high:
        raise ValueError(f"{name} out of bounds")
    return out


def compile_proposal(payload: Mapping[str, Any]) -> dict:
    fields = {"name", "kind", "objective", "falsifier", "evidence_ids",
              "depends_on", "estimated_compute_seconds",
              "estimated_cost_usd", "estimated_information_gain"}
    if not isinstance(payload, Mapping) or set(payload) != fields:
        raise ValueError("invalid proposal schema")
    name, kind = payload["name"], payload["kind"]
    if not isinstance(name, str) or not 3 <= len(name) <= 100:
        raise ValueError("invalid proposal name")
    if kind not in _KIND:
        raise ValueError("unsupported capability kind")
    objective, falsifier = payload["objective"], payload["falsifier"]
    for value in (objective, falsifier):
        if not isinstance(value, str) or not 15 <= len(value) <= 2000:
            raise ValueError("objective and falsifier must be explicit and bounded")
    evidence = payload["evidence_ids"]
    deps = payload["depends_on"]
    if (not isinstance(evidence, list) or not 1 <= len(evidence) <= 32
            or any(not isinstance(x, str) or not _HASH.fullmatch(x)
                   for x in evidence) or len(set(evidence)) != len(evidence)):
        raise ValueError("1–32 unique evidence identifiers required")
    if (not isinstance(deps, list) or len(deps) > 16
            or any(not isinstance(x, str) or not _HASH.fullmatch(x)
                   for x in deps) or len(set(deps)) != len(deps)):
        raise ValueError("invalid dependency identifiers")
    body = {
        "schema_version": "icarus-omnigenesis-proposal-v1",
        "name": name, "kind": kind, "objective": objective,
        "falsifier": falsifier, "evidence_ids": sorted(evidence),
        "depends_on": sorted(deps),
        "estimated_compute_seconds": _real(
            payload["estimated_compute_seconds"], "compute", 1, 10**7),
        "estimated_cost_usd": _real(
            payload["estimated_cost_usd"], "cost", 0, 10**6),
        "estimated_information_gain": _real(
            payload["estimated_information_gain"], "information gain", 0, 1),
        "stage": "DRAFT_REVIEW_REQUIRED",
        "authority": dict(_AUTHORITY),
    }
    body["proposal_id"] = identity(body)
    if body["proposal_id"] in deps:
        raise ValueError("self dependency")
    return body


def plan_capabilities(proposals: list[Mapping[str, Any]], *,
                      max_compute_seconds: int, max_cost_usd: float,
                      max_projects: int = 5) -> dict:
    if not isinstance(proposals, list) or not 1 <= len(proposals) <= 128:
        raise ValueError("1–128 proposals required")
    if type(max_compute_seconds) is not int or not 0 <= max_compute_seconds <= 10**8:
        raise ValueError("invalid compute budget")
    max_cost_usd = _real(max_cost_usd, "cost budget", 0, 10**7)
    if type(max_projects) is not int or not 1 <= max_projects <= 128:
        raise ValueError("invalid project cap")
    proposals = list(proposals)
    ids = set()
    for p in proposals:
        if not isinstance(p, Mapping) or p.get("stage") != "DRAFT_REVIEW_REQUIRED":
            raise ValueError("only reviewed-schema draft proposals permitted")
        if p.get("authority") != _AUTHORITY:
            raise ValueError("authority escalation detected")
        pid = p.get("proposal_id")
        if pid != identity({k: v for k, v in p.items() if k != "proposal_id"}):
            raise ValueError("proposal tampered")
        if pid in ids:
            raise ValueError("duplicate proposal")
        ids.add(pid)
    for p in proposals:
        if not set(p["depends_on"]).issubset(ids):
            raise ValueError("dependencies must be inside the plan batch")
    chosen, pending = [], {p["proposal_id"]: p for p in proposals}
    seconds_left, dollars_left = max_compute_seconds, max_cost_usd
    # Ready proposals are sorted by stated information gain / total normalized
    # compute+cost. This is resource-planning arithmetic, not alpha ranking.
    while pending and len(chosen) < max_projects:
        completed = {p["proposal_id"] for p in chosen}
        ready = [p for p in pending.values()
                 if set(p["depends_on"]).issubset(completed)]
        if not ready:
            break
        ready.sort(key=lambda p: (
            -p["estimated_information_gain"] /
            (1 + p["estimated_compute_seconds"] / 3600
               + p["estimated_cost_usd"] / 100),
            p["proposal_id"],
        ))
        selected = next((p for p in ready
                         if p["estimated_compute_seconds"] <= seconds_left
                         and p["estimated_cost_usd"] <= dollars_left), None)
        if selected is None:
            # Discard all currently ready unaffordable tasks so that their
            # dependent proposals cannot be selected without them.
            for p in ready:
                pending.pop(p["proposal_id"])
            break
        chosen.append(selected)
        pending.pop(selected["proposal_id"])
        seconds_left -= selected["estimated_compute_seconds"]
        dollars_left -= selected["estimated_cost_usd"]
    proposal_ids = [p["proposal_id"] for p in chosen]
    manifest = {
        "schema_version": "icarus-omnigenesis-plan-v1",
        "status": "PROPOSED_NOT_EXECUTED",
        "authority": dict(_AUTHORITY),
        "selected_proposal_ids": proposal_ids,
        "unselected_proposal_ids": sorted(ids.difference(proposal_ids)),
        "estimated_compute_seconds": max_compute_seconds - seconds_left,
        "estimated_cost_usd": max_cost_usd - dollars_left,
        "available_compute_seconds": seconds_left,
        "available_cost_usd": dollars_left,
        "independent_approval_required": True,
        "candidate_count": len(proposals),
    }
    manifest["plan_id"] = identity(manifest)
    return manifest
