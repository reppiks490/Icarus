"""Read-only adapters from existing ICARUS research subsystems into PANTHEON.

Adapters intentionally copy compact evidence summaries. They do not mutate the
source subsystem and never infer authority from source data.
"""
from __future__ import annotations

from typing import Any, Mapping

from .contracts import authority_block

def _obj(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}

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
    existing: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    out = dict(existing or {})
    out.setdefault("parallax", parallax_context(parallax_snapshot))
    out.setdefault("dreamstate", dreamstate_context(dreamstate_snapshot))
    return out


def sibyl_evidence_candidates(
    *,
    observed_at: str,
    asset: str,
    horizon_ms: int,
    source_commit: str,
    faculties: Mapping[str, Any],
    aether: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Translate only epistemically identified structural constraint evidence for SIBYL.

    PANTHEON does not turn every faculty into a directional vote.  ANANKE may
    emit a structural asymmetry, while GODEL, NEMESIS and data quality only
    determine whether that asymmetry is reliable enough to publish.
    """
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
