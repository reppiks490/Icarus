"""Read-only adapters from existing ICARUS research subsystems into PANTHEON.

Adapters intentionally copy compact evidence summaries. They do not mutate the
source subsystem and never infer authority from source data.
"""
from __future__ import annotations

from typing import Any, Mapping

from .contracts import authority_block

def _obj(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}

def oracle_context(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    src = _obj(snapshot)
    oracle = _obj(src.get("oracle"))
    possibility = _obj(src.get("possibility"))
    edge = _obj(src.get("edge_state"))
    phase = _obj(src.get("phase_transition"))
    consensus = _obj(src.get("forced_consensus"))
    leadership = _obj(src.get("causal_leadership"))
    return {
        "status": "observed" if src else "unavailable",
        "schema_version": src.get("schema_version"),
        "asset": src.get("asset"),
        "generated_at": src.get("generated_at"),
        "latent_pressure": oracle.get("latent_pressure"),
        "latent_pressure_score": oracle.get("latent_pressure_score"),
        "evidence_coverage": oracle.get("evidence_coverage"),
        "future_entropy": possibility.get("future_entropy"),
        "future_space_collapse": possibility.get("future_space_collapse"),
        "edge_state": edge.get("state"),
        "edge_confidence": edge.get("confidence"),
        "phase_direction": phase.get("direction"),
        "forced_consensus_active": consensus.get("active"),
        "forced_consensus_direction": consensus.get("direction"),
        "causal_leadership_status": leadership.get("status"),
        "authority": authority_block(),
        "source_semantics": "compact read-only ORACLE Psi diagnostics; association/scenario shares are not causal or calibrated probability",
    }

def parallax_context(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    src = _obj(snapshot)
    signals = src.get("mutation_signals")
    if not isinstance(signals, list):
        signals = []
    attribution = src.get("paired_ablation_attribution")
    if not isinstance(attribution, list):
        attribution = []
    return {
        "schema_version": src.get("schema_version"),
        "counts": dict(_obj(src.get("counts"))),
        "regret": dict(_obj(src.get("regret"))),
        "mutation_signals": signals[:12],
        "paired_ablation_attribution": attribution[:12],
        "authority": authority_block(),
        "source_semantics": "compact read-only PARALLAX evidence; no causal proof implied",
    }

def dreamstate_context(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    src = _obj(snapshot)
    candidates = src.get("candidates")
    if not isinstance(candidates, list):
        candidates = []
    compact = []
    for row in candidates[:20]:
        if not isinstance(row, Mapping):
            continue
        compact.append({
            "candidate_id": row.get("candidate_id"),
            "family_id": row.get("family_id"),
            "stage": row.get("stage"),
            "asset": row.get("asset"),
            "regime": row.get("regime"),
        })
    return {
        "schema_version": src.get("schema_version"),
        "stages": dict(_obj(src.get("stages"))),
        "candidates": compact,
        "required_gates": list(src.get("required_gates") or [])[:32],
        "authority": authority_block(),
        "source_semantics": "compact read-only DREAMSTATE evidence; qualified shadow is not production authority",
    }

def subsystem_context(
    parallax_snapshot: Mapping[str, Any],
    dreamstate_snapshot: Mapping[str, Any],
    *,
    oracle_snapshot: Mapping[str, Any] | None = None,
    existing: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    out = dict(existing or {})
    out["oracle"] = oracle_context(oracle_snapshot or {})
    out["parallax"] = parallax_context(parallax_snapshot)
    out["dreamstate"] = dreamstate_context(dreamstate_snapshot)
    return out
