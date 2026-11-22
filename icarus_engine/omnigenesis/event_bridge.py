"""Phase 16: strictly retrospective first-passage-to-hypothesis research bridge.

Joins a verified derived first-passage report with exactly one as-of numeric
feature per decision. Never infers labels for censored/ambiguous outcomes,
never accepts post-decision feature arrivals, and never grants market authority.

This adapter trusts the caller for source authenticity and vendor licensing,
but not for event/label timestamp or report-integrity claims.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

from .contracts import identity, normalize_dataset, utc

_AUTHORITY = {"research_only": True, "execution_authorized": False,
              "production_decision_authorized": False, "auto_promote": False}
_ALLOWED_FEATURE = {"decision_record_id", "source_record_id", "source_commit",
                    "observed_at", "received_at", "feature"}


def bridge_first_passage(
    report: Mapping[str, Any],
    feature_rows: list[Mapping[str, Any]],
    *,
    positive_event: str = "UPPER",
) -> dict:
    """Create a historical event study without introducing lookahead.

    Every eligible (UPPER/LOWER) event requires an independently timestamped
    feature with received_at <= decision_at. Data from future outcomes is
    never promoted into features. Unsupported or incomplete inputs fail closed.
    """
    if positive_event not in {"UPPER", "LOWER"}:
        raise ValueError("positive_event must be UPPER or LOWER")
    if (not isinstance(report, Mapping)
            or report.get("schema_version") != "icarus-omnigenesis-first-passage-v1"
            or report.get("authority") != _AUTHORITY
            or report.get("evidence_kind") != "DERIVED_FROM_OBSERVED_TAPE"):
        raise ValueError("not a verified historical first-passage report")
    report_id = report.get("report_id")
    if report_id != identity({k: v for k, v in report.items() if k != "report_id"}):
        raise ValueError("tampered event-time report")
    labels = report.get("labels")
    if not isinstance(labels, list) or len(labels) != report.get("label_count"):
        raise ValueError("inconsistent event labels")
    if not isinstance(feature_rows, list) or not 30 <= len(feature_rows) <= 50000:
        raise ValueError("30–50000 timestamped features required")
    features = {}
    for record in feature_rows:
        if not isinstance(record, Mapping) or set(record) != _ALLOWED_FEATURE:
            raise ValueError("invalid source feature schema")
        key = record["decision_record_id"]
        source_id = record["source_record_id"]
        if (not isinstance(key, str) or not 1 <= len(key) <= 128
                or not isinstance(source_id, str) or not 1 <= len(source_id) <= 256):
            raise ValueError("missing feature identity")
        if key in features:
            raise ValueError("duplicate feature decision")
        if record["source_commit"] != report["source_commit"]:
            raise ValueError("cross-revision source mismatch")
        observed, received = utc(record["observed_at"]), utc(record["received_at"])
        if observed > received:
            raise ValueError("feature time travel")
        value = record["feature"]
        if (type(value) not in (int, float) or
                not math.isfinite(float(value))):
            raise ValueError("feature must be finite numeric")
        features[key] = (observed, received, float(value), source_id)
    used = set()
    output = []
    skipped = {"AMBIGUOUS_BOTH": 0, "CENSORED": 0}
    last_decision = None
    for row in labels:
        if not isinstance(row, Mapping):
            raise ValueError("invalid label entry")
        event = row.get("event")
        if event in skipped:
            skipped[event] += 1
            continue
        if event not in {"UPPER", "LOWER"}:
            raise ValueError("unrecognized outcome")
        key = row.get("decision_record_id")
        if key not in features:
            raise ValueError("missing source feature for resolved event")
        observed, received, value, source_id = features[key]
        decision, resolved = utc(row["decision_at"]), utc(row["label_resolved_at"])
        if not observed <= received <= decision < resolved:
            raise ValueError("future feature or invalid event resolution")
        if last_decision is not None and decision <= last_decision:
            raise ValueError("non-increasing event decisions")
        last_decision = decision
        if row.get("label_is_ambiguous") is not False or row.get("label_is_censored") is not False:
            raise ValueError("contradictory event classification")
        used.add(key)
        output.append({
            "record_id": key,
            "asset": report["asset"],
            "decision_at": decision.isoformat(),
            "observed_at": observed.isoformat(),
            "received_at": received.isoformat(),
            "label_resolved_at": resolved.isoformat(),
            "feature": value,
            "outcome": event == positive_event,
            "source_record_id": source_id,
        })
    if len(output) < 30:
        raise ValueError("fewer than 30 unambiguous resolved events")
    if len(used) != len(features):
        raise ValueError("unused or mismatched source feature IDs")
    name = "firstpassage-" + identity({
        "report_id": report_id,
        "event": positive_event,
        "features": sorted((r["record_id"], r["source_record_id"], r["received_at"])
                           for r in output)
    })
    dataset = normalize_dataset({
        "dataset_id": name,
        "source_commit": report["source_commit"],
        "records": output,
    })
    audit = {
        "schema_version": "icarus-omnigenesis-event-bridge-v1",
        "report_id": report_id,
        "dataset_sha256": identity(dataset),
        "positive_event": positive_event,
        "eligible_records": len(dataset["records"]),
        "excluded_ambiguous": skipped["AMBIGUOUS_BOTH"],
        "excluded_censored": skipped["CENSORED"],
        "feature_count": len(features),
        "research_only": True,
        "execution_authorized": False,
        "future_feature_used": False,
        "qualified_edge_claim": False,
        "limitations": [
            "as-of timestamp validation does not verify vendor source authenticity",
            "OHLC event labels are not broker-executable fills",
            "independent data, regime and cost validation remains required",
        ],
    }
    audit["bridge_id"] = identity(audit)
    return {"dataset": dataset, "audit": audit}
