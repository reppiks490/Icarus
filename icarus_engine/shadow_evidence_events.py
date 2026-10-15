"""Explicit bridge from read-only Pulse shadow evidence to the intelligence fabric.

Publishing is opt-in at the call site. This module never reads bars, submits
orders, or runs as a side effect of a status/summary request.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from icarus_engine.intelligence_fabric import IntelligenceEvent, IntelligenceFabric


_EVIDENCE_FIELDS = (
    "schema", "status", "asset", "fill_basis", "signal_basis", "provenance",
    "primary_entry_fills", "shadow_entry_fills", "entry_fill_parity",
    "primary_only_entry_fills", "shadow_only_entry_fills", "matched_entry_intents",
    "entry_price_delta_points_shadow_minus_primary",
    "entry_price_delta_ticks_shadow_minus_primary",
    "entry_price_delta_dollars_shadow_minus_primary",
    "primary_only_closed_episodes", "shadow_only_closed_episodes",
    "pairable_closed_episodes", "excluded_admin_flatten_lot_trade_pieces",
    "outcome_matrix", "outcome_agreement_denominator",
    "outcome_agreement_rate", "outcome_agreement_count", "primary_break_even_episodes",
    "shadow_break_even_episodes", "primary_win_count", "primary_win_preserved_count",
    "primary_win_preservation", "primary", "real_price_shadow", "net_realization_ratio",
    "net_realization_ratio_unavailable_reason", "paired_profit_capture",
    "paired_profit_capture_unavailable_reason", "paired_primary_winner_net",
    "paired_shadow_net_on_primary_winners", "bar_close_drawdown_basis",
    "bar_close_equity_observations", "primary_bar_close_max_drawdown",
    "real_price_shadow_bar_close_max_drawdown",
)


def shadow_evidence_event(
    summary: Mapping[str, Any],
    *,
    run_id: str,
    observed_at: str,
    received_at: str,
) -> IntelligenceEvent:
    """Create a content-addressed research event from a shadow summary.

    Only an explicit allowlist of compact metrics and their source provenance
    enters the event. Raw bars, recent intents, and execution controls do not.
    """
    if not isinstance(summary, Mapping):
        raise ValueError("shadow summary must be a mapping")
    if summary.get("schema") != "icarus.real_price_shadow/1":
        raise ValueError("unsupported shadow summary schema")
    if summary.get("enabled") is not True:
        raise ValueError("shadow evidence must come from an enabled twin")
    if summary.get("execution_authorized") is not False:
        raise ValueError("shadow evidence must explicitly deny execution authority")
    asset = summary.get("asset")
    if not isinstance(asset, str) or not asset.strip():
        raise ValueError("shadow evidence requires an asset identity")
    if summary.get("status") not in {"READY", "DEGRADED", "INVALID"}:
        raise ValueError("shadow evidence has an unsupported status")

    evidence = {key: summary[key] for key in _EVIDENCE_FIELDS if key in summary}
    if not isinstance(evidence.get("provenance"), Mapping) or not evidence["provenance"]:
        raise ValueError("shadow evidence requires a provenance mapping")
    try:
        evidence_json = json.dumps(evidence, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError("shadow evidence must contain finite JSON values") from exc
    evidence_digest = hashlib.sha256(evidence_json.encode("utf-8")).hexdigest()
    # Snapshot nested mappings/lists so caller mutation cannot change the event
    # after its digest was computed and before it is persisted.
    evidence = json.loads(evidence_json)
    if not isinstance(run_id, str) or not run_id.strip() or len(run_id) > 240:
        raise ValueError("run_id is required and must not exceed 240 characters")

    return IntelligenceEvent(
        event_type="research",
        source="icarus_engine.real_price_shadow",
        source_kind="experiment",
        channel="real_price_shadow",
        thread_key=f"real_price_shadow/{asset.strip()}/{run_id.strip()}",
        title=f"Real-price shadow evidence: {asset.strip()}",
        body=("Read-only same-decision standard-real-OHLC emulator evidence. "
              "This event is research evidence, not a broker fill or strategy qualification."),
        observed_at=observed_at,
        received_at=received_at,
        severity=0,
        urgency=0.0,
        confidence=None,
        assets=(asset.strip(),),
        correlation_id=run_id.strip(),
        evidence_ids=(f"sha256:{evidence_digest}",),
        tags=("real_price_shadow", "research_only", summary["status"].lower()),
        payload={
            "evidence_digest": evidence_digest,
            "evidence": evidence,
            "execution_authorized": False,
            "production_decision_authorized": False,
        },
    )


def publish_shadow_evidence(
    fabric: IntelligenceFabric,
    summary: Mapping[str, Any],
    *,
    run_id: str,
    observed_at: str,
    received_at: str,
) -> dict[str, Any]:
    """Explicitly append an RT01 summary to the shared immutable event fabric."""
    if not isinstance(fabric, IntelligenceFabric):
        raise ValueError("fabric must be an IntelligenceFabric")
    event = shadow_evidence_event(summary, run_id=run_id,
                                  observed_at=observed_at, received_at=received_at)
    receipt = fabric.publish(event)
    return {
        **receipt,
        "evidence_id": event.evidence_ids[0],
        "execution_authorized": False,
        "production_decision_authorized": False,
    }
