"""Read-only projection of canonical forecasts into the Unified Spine.

The learning ledger owns durability and first-receipt time. This adapter adds
no scheduler, forecast store, inferred market observations or outcome feedback.
Source-scoped semantics prevent unrelated labels/revisions becoming consensus.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from .unified_intelligence import IntelligenceClaim, UnifiedIntelligenceSpine
from .unified_intelligence import _parse_time


def forecast_spine(rows: Sequence[Mapping[str, Any]], *, as_of: str,
                   window_limited: bool) -> dict[str, Any]:
    spine = UnifiedIntelligenceSpine()
    claims, unprojected = [], []
    for row in rows:
        pred = row["prediction"]
        target = pred["target"]
        labels = pred["probabilities"]
        reason = ("RECEIPT_PRECEDES_EMISSION" if _parse_time(row["recorded_at"], "recorded_at") <
                  _parse_time(pred["emitted_at"], "emitted_at") else
                  "NUMERIC_HAS_NO_STANCE_CONTRACT" if target == "numeric" else
                  "CLASS_CARDINALITY_EXCEEDS_64" if len(labels) > 64 else
                  "SPINE_CONTRACT_LIMIT" if len(pred["regime"]) > 120 or
                  any(len(item) > 240 for item in pred["evidence_ids"]) else None)
        if reason:
            unprojected.append({"prediction_id": pred["prediction_id"],
                                "source": pred["producer"], "reason": reason})
            continue
        # Exact revision, original target definition and observation instant all
        # remain separate until an independently validated comparability adapter exists.
        scope = {k: pred[k] for k in ("producer", "source_commit", "target",
                                     "reference_value", "metadata")}
        scope["class_labels"] = sorted(labels)
        digest = hashlib.sha256(json.dumps(scope, sort_keys=True, separators=(",", ":"),
                                          allow_nan=False).encode()).hexdigest()
        key = f"{pred['asset']}:{target}:{digest}:{pred['emitted_at']}"
        if target == "class":
            propositions = [(label, 2 * probability - 1, probability)
                            for label, probability in sorted(labels.items())]
        else:
            stance = ({"up": 1.0, "down": -1.0, "flat": 0.0}[pred["prediction"]]
                      if target == "direction" else (1.0 if pred["prediction"] else -1.0))
            propositions = [("", stance, pred["probability"])]
        for label, stance, confidence in propositions:
            claim = IntelligenceClaim(
                source=pred["producer"], source_kind="experiment",
                semantic_key=key + (":" + label if label else ""),
                stance=stance, confidence=confidence, evidence_class="derived",
                observed_at=pred["emitted_at"], received_at=row["recorded_at"],
                regime=pred["regime"], horizon_seconds=pred["horizon_seconds"],
                lineage=tuple(pred["evidence_ids"]),
                falsifiers=("A matured outcome contradicts this forecast proposition.",),
                details={"prediction_id": pred["prediction_id"], "asset": pred["asset"],
                         "source_commit": pred["source_commit"], "label": label,
                         "source_revision_verified": False,
                         "confidence_is_raw_forecast_probability": True,
                         "calibrated_confidence_established": False,
                         "adapter": "canonical-learning-forecast-v1"},
            )
            receipt = spine.ingest(claim)
            claims.append({"claim_id": receipt["claim_id"], **claim.normalized()})
    result = spine.snapshot(as_of=as_of)
    result["claims"] = claims
    result["feed"] = {
        "storage": "CANONICAL_LEARNING_LEDGER",
        "prediction_count": len(rows), "projected_prediction_count": len(rows) - len(unprojected),
        "unprojected_count": len(unprojected), "unprojected": unprojected,
        "window_limited": window_limited,
        "scope": "BOUNDED_CAUSALLY_AVAILABLE_FORECAST_WINDOW",
        "source_semantics": "SOURCE_AND_REVISION_SCOPED_NO_ASSUMED_COMPARABILITY",
        "durable_first_receipt_time": True, "outcomes_used_for_claims": False,
        "source_identity_is_not_source_attestation": True,
        "automatic_feed": "EXISTING_LEARNING_HARVEST_AND_FORECAST_WRITES",
    }
    return result
