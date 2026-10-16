"""Provenance-bearing evidence contract for ICARUS Brain decisions.

Raw provider values and corpus rows are not decision objects.  Brain receives typed
evidence whose source hashes, transformation revision, timestamps, regime state,
and unresolved validation gates are explicit.  Validation is fail-closed and causal:
information observed or retrieved after a decision timestamp cannot justify that
decision.

Live execution remains disabled by owner policy.  This module can authorize evidence
for decision support and paper workflows; it cannot arm live trading.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Tuple


_ALLOWED_SOURCE_STATUS = {"verified", "degraded", "blocked", "missing", "stale"}


def _aware(value: datetime, name: str) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError(f"{name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _looks_sha256(value: str) -> bool:
    text = str(value or "").strip().lower()
    return len(text) == 64 and all(ch in "0123456789abcdef" for ch in text)


@dataclass(frozen=True)
class EvidenceSource:
    source_id: str
    provider: str
    event_time: datetime
    retrieved_at: datetime
    source_sha256: str
    transformation_revision: str
    required: bool = True
    status: str = "verified"
    max_age_seconds: Optional[int] = None

    def __post_init__(self) -> None:
        _aware(self.event_time, "event_time")
        _aware(self.retrieved_at, "retrieved_at")
        if self.max_age_seconds is not None and (
            isinstance(self.max_age_seconds, bool)
            or not isinstance(self.max_age_seconds, (int, float))
            or not math.isfinite(float(self.max_age_seconds))
            or self.max_age_seconds < 0
        ):
            raise ValueError("max_age_seconds must be finite and non-negative")
        if self.status not in _ALLOWED_SOURCE_STATUS:
            raise ValueError(f"unsupported evidence source status {self.status!r}")


@dataclass(frozen=True)
class RegimeSnapshot:
    label: str
    confidence: float
    observed_at: datetime
    model_revision: str
    inputs_sha256: str
    drift_state: str = "unknown"
    ood_state: str = "unknown"

    def __post_init__(self) -> None:
        _aware(self.observed_at, "regime observed_at")
        if not 0.0 <= float(self.confidence) <= 1.0:
            raise ValueError("regime confidence must be between 0 and 1")


@dataclass(frozen=True)
class BrainEvidence:
    asset: str
    feature_revision: str
    evidence_sha256: str
    sources: Tuple[EvidenceSource, ...]
    regime: RegimeSnapshot
    unresolved_validation_gates: Tuple[str, ...] = ()
    decision_authorized: bool = False
    execution_authorized: bool = False


@dataclass(frozen=True)
class EvidenceValidation:
    valid: bool
    blockers: Tuple[str, ...]


def validate_brain_evidence(
    evidence: BrainEvidence,
    *,
    decision_time: datetime,
    now: Optional[datetime] = None,
) -> EvidenceValidation:
    """Validate provenance, freshness, causality, and owner authorization policy."""
    decision = _aware(decision_time, "decision_time")
    if now is not None:
        current = _aware(now, "now")
        if current < decision:
            raise ValueError("now cannot precede decision_time")

    blockers: list[str] = []

    if not str(evidence.asset or "").strip():
        blockers.append("asset identity is missing")
    if not str(evidence.feature_revision or "").strip():
        blockers.append("feature revision is missing")
    if not _looks_sha256(evidence.evidence_sha256):
        blockers.append("evidence SHA-256 hash is missing or malformed")
    if not evidence.sources:
        blockers.append("no evidence sources are attached")

    for source in evidence.sources:
        label = source.source_id or source.provider or "source"
        event_time = _aware(source.event_time, f"{label} event_time")
        retrieved_at = _aware(source.retrieved_at, f"{label} retrieved_at")
        if not str(source.source_id or "").strip():
            blockers.append("evidence source_id is missing")
        if not str(source.provider or "").strip():
            blockers.append(f"{label}: provider is missing")
        if not _looks_sha256(source.source_sha256):
            blockers.append(f"{label}: source SHA-256 hash is missing or malformed")
        if not str(source.transformation_revision or "").strip():
            blockers.append(f"{label}: transformation revision is missing")
        if event_time > decision:
            blockers.append(f"{label}: event_time occurs after decision_time")
        if retrieved_at > decision:
            blockers.append(f"{label}: retrieved_at occurs after decision_time")
        if retrieved_at < event_time:
            blockers.append(f"{label}: retrieved_at precedes event_time")
        if source.required and source.status != "verified":
            blockers.append(f"{label}: required source status is {source.status!r}, not verified")
        if source.required and source.max_age_seconds is None:
            blockers.append(f"{label}: required source freshness bound is missing")
        elif source.required:
            age = (decision - event_time).total_seconds()
            if age > source.max_age_seconds:
                blockers.append(
                    f"{label}: required source is stale at decision_time "
                    f"({int(age)}s > {source.max_age_seconds}s)"
                )

    regime = evidence.regime
    regime_time = _aware(regime.observed_at, "regime observed_at")
    if regime_time > decision:
        blockers.append("regime snapshot was observed after decision_time")
    if not str(regime.label or "").strip():
        blockers.append("regime label is missing")
    if not str(regime.model_revision or "").strip():
        blockers.append("regime model revision is missing")
    if not _looks_sha256(regime.inputs_sha256):
        blockers.append("regime input SHA-256 hash is missing or malformed")
    if regime.drift_state not in {"normal", "unknown"}:
        blockers.append(f"regime drift state is {regime.drift_state!r}")
    if regime.ood_state not in {"in_distribution", "unknown"}:
        blockers.append(f"regime OOD state is {regime.ood_state!r}")

    for gate in evidence.unresolved_validation_gates:
        blockers.append(f"unresolved validation gate: {gate}")

    if not evidence.decision_authorized:
        blockers.append("decision authorization is false")
    if evidence.execution_authorized:
        blockers.append("live execution authorization violates current owner policy")

    # Stable de-duplication keeps downstream evidence receipts deterministic.
    blockers = list(dict.fromkeys(blockers))
    return EvidenceValidation(valid=not blockers, blockers=tuple(blockers))
