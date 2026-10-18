"""Strict, non-executing, point-in-time contracts for ICARUS Intuition Ω.

This module accepts *research records*, not broker/strategy commands.
External callers must supply authoritative receive times; an eventual network
adapter must stamp engine-owned receipt time before admitting records.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math
from typing import Mapping


def timestamp(value: str, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a timestamp")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, TypeError) as exc:
        raise ValueError(f"{field} must be ISO-8601") from exc
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f"{field} must have a timezone")
    return dt.astimezone(timezone.utc)


def nonempty(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        raise ValueError(f"{field} must be nonempty and at most 256 characters")
    return value.strip()


def probability(value: float, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError(f"{field} must be numeric")
    value = float(value)
    if not math.isfinite(value) or not 0.0 <= value <= 1.0:
        raise ValueError(f"{field} must be a finite [0,1] probability")
    return value


def positive(value: float, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise ValueError(f"{field} must be numeric")
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{field} must be positive and finite")
    return value


def feature_vector(value: Mapping[str, float]) -> dict[str, float]:
    if not isinstance(value, Mapping) or not 1 <= len(value) <= 128:
        raise ValueError("features must contain 1-128 named numeric values")
    cleaned: dict[str, float] = {}
    for key, raw in value.items():
        name = nonempty(key, "feature name")
        if name in cleaned or isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise ValueError("feature collision or nonnumeric feature")
        number = float(raw)
        if not math.isfinite(number):
            raise ValueError("non-finite feature")
        cleaned[name] = number
    return cleaned


def check_sha(value: str) -> str:
    if not isinstance(value, str) or len(value) != 40 or any(c not in "0123456789abcdef" for c in value.lower()):
        raise ValueError("exact 40-character source_commit required")
    return value.lower()


@dataclass(frozen=True)
class Scope:
    asset: str
    venue: str
    timeframe_seconds: int
    chart: str
    execution_basis: str
    regime: str
    target: str
    horizon_seconds: int
    feature_schema: str

    def __post_init__(self) -> None:
        for name in ("asset", "venue", "chart", "execution_basis", "regime", "target", "feature_schema"):
            nonempty(getattr(self, name), name)
        if self.chart not in ("real_ohlc", "heikin_ashi"):
            raise ValueError("unrecognized chart representation")
        if self.execution_basis not in ("real_price", "synthetic_ha", "not_applicable"):
            raise ValueError("unrecognized execution basis")
        if self.chart == "real_ohlc" and self.execution_basis == "synthetic_ha":
            raise ValueError("synthetic HA fills require HA chart representation")
        if type(self.timeframe_seconds) is not int or self.timeframe_seconds <= 0:
            raise ValueError("invalid timeframe_seconds")
        if type(self.horizon_seconds) is not int or self.horizon_seconds <= 0:
            raise ValueError("invalid horizon_seconds")


@dataclass(frozen=True)
class Situation:
    """A forecast situation known at event time; timestamps are NOT optional."""
    case_id: str
    scope: Scope
    observed_at: str
    received_at: str
    source_commit: str
    features: Mapping[str, float]
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        nonempty(self.case_id, "case_id")
        check_sha(self.source_commit)
        if timestamp(self.received_at, "received_at") < timestamp(self.observed_at, "observed_at"):
            raise ValueError("receipt precedes observation")
        feature_vector(self.features)
        if not self.evidence_ids or len(self.evidence_ids) > 128:
            raise ValueError("at least one evidence reference required")
        for evidence_id in self.evidence_ids:
            nonempty(evidence_id, "evidence_id")


@dataclass(frozen=True)
class Episode:
    """Only settled binary outcomes can become training memory."""
    situation: Situation
    maturity_at: str
    outcome_received_at: str
    outcome: int
    source_dataset_id: str
    session_id: str
    root_family: str

    def __post_init__(self) -> None:
        if type(self.outcome) is not int or self.outcome not in (0, 1):
            raise ValueError("outcome must be the settled binary label")
        for name in ("source_dataset_id", "session_id", "root_family"):
            nonempty(getattr(self, name), name)
        start = timestamp(self.situation.observed_at, "observed_at")
        mature = timestamp(self.maturity_at, "maturity_at")
        received = timestamp(self.outcome_received_at, "outcome_received_at")
        if mature < start or received < mature or received < timestamp(self.situation.received_at, "received_at"):
            raise ValueError("outcome must mature and arrive after its event and input")


def authority() -> dict[str, bool]:
    return {"execution_authorized": False, "production_decision_authorized": False}
