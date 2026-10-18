"""Read-only, fail-closed bridge from the canonical ICARUS Learning Fabric.

A historical replay ingested *after* its outcome matured is NOT a prospective
forecast. The bridge refuses such rows. It requires exact chart/venue/fill/label
metadata and uses Learning Fabric's database-owned recorded_at receipt stamps,
not caller claims. It never writes to the source database.
"""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Any

from .calibration import Forecast, ForecastLedger, Resolution
from .contracts import Scope, authority, timestamp


_REQUIRED_META = (
    "venue", "timeframe_seconds", "chart", "execution_basis",
    "feature_schema", "session_id", "intuition_target_contract",
)


def import_verified_learning_pairs(
    source_database: str | Path, destination: ForecastLedger, *,
    as_of: str,
) -> dict[str, Any]:
    """Import only source-receipt-verifiable settled pairs into research ledger.

    The source database must be the trusted canonical Learning Fabric database;
    never point this at caller-provided SQLite. Database origin and signature
    verification are responsibilities of the invoking authenticated service.
    """
    cutoff = timestamp(as_of, "as_of")
    path = Path(source_database)
    if not path.is_file():
        raise ValueError("trusted learning fabric database unavailable")
    # mode=ro must be enforced by SQLite itself; query_only adds defense in depth.
    with sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True) as source:
        source.row_factory = sqlite3.Row
        source.execute("PRAGMA query_only=ON")
        # Schemas are owned by LearningFabric, not recreated or migrated here.
        try:
            cursor = source.execute(
                "SELECT p.prediction_id,p.producer,p.asset,p.target,p.prediction_json,"
                "p.probability,p.emitted_at,p.resolves_at,p.horizon_seconds,p.regime,"
                "p.source_commit,p.evidence_json,p.metadata_json,p.recorded_at,"
                "o.observed_at AS outcome_observed,o.recorded_at AS outcome_recorded,"
                "o.success,o.evidence_json AS outcome_evidence "
                "FROM predictions p JOIN outcomes o ON o.prediction_id=p.prediction_id "
                "ORDER BY p.emitted_at,p.prediction_id"
            )
        except sqlite3.OperationalError as exc:
            raise ValueError("incompatible Learning Fabric schema") from exc
        imported = 0
        existing = 0
        rejected: dict[str, int] = {}
        seen = 0
        for row in cursor:
            seen += 1
            reason = None
            try:
                recorded = timestamp(row["recorded_at"], "source_prediction_recorded_at")
                result_recorded = timestamp(row["outcome_recorded"], "source_outcome_recorded_at")
                emitted = timestamp(row["emitted_at"], "source_emitted_at")
                matured = timestamp(row["resolves_at"], "source_resolves_at")
                observed_result = timestamp(row["outcome_observed"], "source_outcome_observed")
                if recorded > cutoff or result_recorded > cutoff:
                    reason = "not_known_as_of"
                elif recorded >= matured or recorded < emitted:
                    reason = "retrospectively_recorded_or_invalid_forecast"
                elif result_recorded < observed_result or observed_result < matured:
                    reason = "invalid_or_premature_outcome"
                elif type(row["success"]) is not int or row["success"] not in (0, 1):
                    reason = "no_settled_binary_label"
                else:
                    meta = json.loads(row["metadata_json"])
                    if not isinstance(meta, dict) or any(k not in meta for k in _REQUIRED_META):
                        reason = "missing_exact_scope_metadata"
                    else:
                        scope = Scope(
                            asset=row["asset"], venue=meta["venue"],
                            timeframe_seconds=meta["timeframe_seconds"],
                            chart=meta["chart"], execution_basis=meta["execution_basis"],
                            regime=row["regime"], target=meta["intuition_target_contract"],
                            horizon_seconds=row["horizon_seconds"],
                            feature_schema=meta["feature_schema"],
                        )
                        # Do NOT retrofit missing source identities.
                        source_evidence = tuple(json.loads(row["evidence_json"]))
                        outcome_evidence = tuple(json.loads(row["outcome_evidence"]))
                        f = Forecast(
                            forecast_id=row["prediction_id"], producer=row["producer"],
                            scope=scope, issued_at=row["emitted_at"],
                            maturity_at=row["resolves_at"],
                            received_at=row["recorded_at"], probability=row["probability"],
                            source_commit=row["source_commit"], evidence_ids=source_evidence,
                            session_id=meta["session_id"],
                        )
                        res = Resolution(
                            forecast_id=row["prediction_id"],
                            observed_at=row["outcome_observed"],
                            received_at=row["outcome_recorded"],
                            label=int(row["success"]), evidence_ids=outcome_evidence,
                        )
                        was_added = destination.commit(f)
                        destination.settle(res)
                        if was_added:
                            imported += 1
                        else:
                            existing += 1
            except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
                # The source record is never normalized into a fictitious valid
                # prediction. Destination identity collisions remain fatal.
                if isinstance(exc, ValueError) and "collision" in str(exc):
                    raise
                reason = "invalid_or_incompatible_record"
            if reason:
                rejected[reason] = rejected.get(reason, 0) + 1
    return {
        "schema_version": "icarus-intuition-learning-bridge-v1",
        "status": "IMPORTED_RESEARCH_ONLY" if imported else "NO_QUALIFIED_NEW_PAIRS",
        "total_examined": seen, "imported": imported, "already_present": existing,
        "rejected_by_reason": dict(sorted(rejected.items())),
        "source_mutated": False,
        **authority(),
    }
