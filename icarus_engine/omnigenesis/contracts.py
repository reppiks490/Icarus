"""Strict, provenance-aware experiment records; no executable expressions."""
from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime, timezone
from typing import Any, Mapping

_SHA = re.compile(r"^[0-9a-f]{40}$")
_ASSET = re.compile(r"^[A-Z0-9._-]{1,24}$")


def canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValueError("value must be finite JSON") from exc


def identity(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def utc(value: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError("timestamp must be a string")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invalid ISO-8601 timestamp") from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("timestamp must have timezone")
    return result.astimezone(timezone.utc)


def normalize_dataset(dataset: Mapping[str, Any]) -> dict[str, Any]:
    """Fail closed on timestamps, raw data, duplicate IDs, and future leakage.

    Label resolution is permitted AFTER a decision because outcomes are only
    evaluated retrospectively. The training/validation/test boundaries purge
    earlier labels that were unknown at the next period's first decision.
    """
    if not isinstance(dataset, Mapping):
        raise ValueError("dataset must be an object")
    if set(dataset) != {"dataset_id", "source_commit", "records"}:
        raise ValueError("dataset requires dataset_id, source_commit, records")
    dataset_id, commit = dataset["dataset_id"], dataset["source_commit"]
    if not isinstance(dataset_id, str) or not 1 <= len(dataset_id) <= 128:
        raise ValueError("invalid dataset_id")
    if not isinstance(commit, str) or not _SHA.fullmatch(commit):
        raise ValueError("source_commit must be a 40-digit lowercase git SHA")
    raw = dataset["records"]
    if not isinstance(raw, list) or not 30 <= len(raw) <= 50000:
        raise ValueError("30 to 50000 records required")
    normalized = []
    seen = set()
    allowed = {"record_id", "asset", "decision_at", "observed_at",
               "received_at", "label_resolved_at", "feature", "outcome",
               "source_record_id"}
    for row in raw:
        if not isinstance(row, Mapping) or set(row) != allowed:
            raise ValueError("record fields mismatch")
        rec_id = row["record_id"]
        if not isinstance(rec_id, str) or not 1 <= len(rec_id) <= 128 or rec_id in seen:
            raise ValueError("invalid or duplicate record_id")
        seen.add(rec_id)
        asset = row["asset"]
        if not isinstance(asset, str) or not _ASSET.fullmatch(asset):
            raise ValueError("invalid asset")
        source_id = row["source_record_id"]
        if not isinstance(source_id, str) or not 1 <= len(source_id) <= 256:
            raise ValueError("missing source record provenance")
        observed, received, decision, resolved = (
            utc(row[k]) for k in ("observed_at", "received_at",
                                 "decision_at", "label_resolved_at")
        )
        if not (observed <= received <= decision < resolved):
            raise ValueError("feature not available as-of decision, or label not future")
        feature = row["feature"]
        if isinstance(feature, bool) or not isinstance(feature, (int, float)):
            raise ValueError("feature must be finite numeric")
        feature = float(feature)
        if not math.isfinite(feature):
            raise ValueError("feature must be finite numeric")
        outcome = row["outcome"]
        if type(outcome) is not bool:
            raise ValueError("outcome must be strictly boolean")
        normalized.append({
            "record_id": rec_id, "asset": asset,
            "decision_at": decision.isoformat(),
            "observed_at": observed.isoformat(),
            "received_at": received.isoformat(),
            "label_resolved_at": resolved.isoformat(),
            "feature": feature, "outcome": outcome,
            "source_record_id": source_id,
        })
    normalized.sort(key=lambda row: (row["decision_at"], row["record_id"]))
    assets = {row["asset"] for row in normalized}
    if len(assets) != 1:
        raise ValueError("v1 research must be one asset per dataset")
    return {"dataset_id": dataset_id, "source_commit": commit,
            "records": normalized}
