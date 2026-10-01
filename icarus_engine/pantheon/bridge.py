"""Read-only adapters from existing ICARUS research subsystems into PANTHEON.

Adapters intentionally copy compact evidence summaries. They do not mutate the
source subsystem and never infer authority from source data.
"""
from __future__ import annotations

from typing import Any, Mapping

from .contracts import authority_block

def _obj(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}

def psi_context(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Compact read-only adapter for ICARUS Ψ.

    Ψ is distinct from ORACLE. The adapter intentionally reads only the
    current Psi schema and never relabels Psi evidence as ORACLE evidence.
    """
    src = _obj(snapshot)
    latent = _obj(src.get("latent_pressure_engine"))
    possibility = _obj(src.get("possibility"))
    edge = _obj(src.get("edge_state"))
    phase = _obj(src.get("phase_transition"))
    consensus = _obj(src.get("forced_consensus"))
    leadership = _obj(src.get("causal_leadership"))
    return {
        "status": "observed" if src else "unavailable",
        "subsystem": "psi",
        "schema_version": src.get("schema_version"),
        "asset": src.get("asset"),
        "generated_at": src.get("generated_at"),
        "latent_pressure": latent.get("latent_pressure"),
        "latent_pressure_score": latent.get("latent_pressure_score"),
        "evidence_coverage": latent.get("evidence_coverage"),
        "future_entropy": possibility.get("future_entropy"),
        "future_space_collapse": possibility.get("future_space_collapse"),
        "edge_state": edge.get("state"),
        "edge_confidence": edge.get("confidence"),
        "phase_direction": phase.get("direction"),
        "forced_consensus_active": consensus.get("active"),
        "forced_consensus_direction": consensus.get("direction"),
        "causal_leadership_status": leadership.get("status"),
        "authority": authority_block(),
        "source_semantics": "compact read-only ICARUS Psi diagnostics; Psi is distinct from ORACLE; association/scenario shares are not causal or calibrated probability",
    }


def oracle_context(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Deprecated compatibility alias for legacy callers.

    The returned payload is explicitly identified as Psi so callers cannot
    mistake this adapter for the separate ORACLE subsystem.
    """
    return psi_context(snapshot)

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
    psi_snapshot: Mapping[str, Any] | None = None,
    oracle_snapshot: Mapping[str, Any] | None = None,
    existing: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    out = dict(existing or {})
    # Preserve a caller-supplied ORACLE payload. ICARUS Ψ must never overwrite
    # or masquerade as the separate ORACLE subsystem.
    psi_source = psi_snapshot if psi_snapshot is not None else oracle_snapshot
    out["psi"] = psi_context(psi_source or {})
    out["parallax"] = parallax_context(parallax_snapshot)
    out["dreamstate"] = dreamstate_context(dreamstate_snapshot)
    return out

def sibyl_evidence_candidates(
    *,
    observed_at: str,
    asset: str,
    horizon_ms: int,
    source_commit: str,
    origin_observation_id: str,
    evidence_refs: list[str],
    faculties: Mapping[str, Any],
    aether: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Translate only epistemically identified structural constraint evidence for SIBYL.

    PANTHEON does not turn every faculty into a directional vote.  ANANKE may
    emit a structural asymmetry, while GODEL, NEMESIS and data quality only
    determine whether that asymmetry is reliable enough to publish.

    A downstream SIBYL record is also evidence, so it must remain traceable to
    the exact PANTHEON observation and at least one immutable origin-evidence
    reference. Evidence-free structural votes are suppressed rather than
    laundered into a downstream source.
    """
    if not isinstance(origin_observation_id, str) or not origin_observation_id.strip():
        return []
    if not isinstance(evidence_refs, list) or not evidence_refs:
        return []
    if any(not isinstance(ref, str) or not ref.strip() for ref in evidence_refs):
        return []
    origin_observation_id = origin_observation_id.strip()
    clean_evidence_refs = [ref.strip() for ref in evidence_refs]
    f = _obj(faculties)
    ananke = _obj(f.get("ananke"))
    godel = _obj(f.get("godel"))
    nemesis = _obj(f.get("nemesis"))
    field = _obj(_obj(aether).get("field"))

    if ananke.get("status") == "abstain":
        return []
    try:
        asymmetry = float(ananke.get("asymmetry"))
        ambiguity = float(godel.get("ambiguity", 1.0))
        survival = float(nemesis.get("survival_score", 0.0))
        data_quality = float(field.get("data_quality", 0.0))
        freedom = float(ananke.get("freedom", 1.0))
    except (TypeError, ValueError):
        return []

    if not all(x == x and x not in (float("inf"), float("-inf")) for x in (asymmetry, ambiguity, survival, data_quality, freedom)):
        return []

    direction = max(-1.0, min(1.0, asymmetry))
    confidence = max(0.0, min(1.0, data_quality * (1.0 - max(0.0, min(1.0, ambiguity))) * max(0.0, min(1.0, survival))))
    magnitude = max(0.0, min(4.0, abs(direction) * (1.0 + max(0.0, min(1.0, 1.0 - freedom)))))

    if abs(direction) < 0.05 or confidence < 0.10:
        return []

    return [{
        "asset": str(asset).upper(),
        "source": "pantheon-ananke",
        "domain": "structural_constraints",
        "observed_at": observed_at,
        "direction": direction,
        "magnitude": magnitude,
        "confidence": confidence,
        "horizon_seconds": max(1, min(604800, int(max(1, horizon_ms) / 1000))),
        "source_commit": source_commit,
        "payload": {
            "producer": "PANTHEON/ANANKE",
            "origin_observation_id": origin_observation_id,
            "origin_evidence_refs": clean_evidence_refs,
            "origin_evidence_count": len(clean_evidence_refs),
            "provenance_contract": {
                "explicit_origin_evidence_required": True,
                "source_commit_bound": True,
            },
            "least_cost_direction": ananke.get("least_cost_direction"),
            "freedom": freedom,
            "causal_event_horizon_side": ananke.get("causal_event_horizon_side"),
            "godel_ambiguity": ambiguity,
            "nemesis_survival_score": survival,
            "data_quality": data_quality,
            "authority": authority_block(),
            "semantics": "structural constraint evidence only; not a trade signal and not a calibrated forecast probability",
        },
    }]
