from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any

from .identity import canonical_sha256, evidence_id, normalize_utc

_HEX = frozenset("0123456789abcdef")
_PROVIDER_STATES = frozenset({
    "OK", "DEGRADED", "STALE", "UNCONFIGURED", "DISABLED",
    "PLAN_LIMITED", "ENTITLEMENT_REQUIRED", "CONFIGURATION_BLOCKED", "ERROR",
})


def _require_text(name: str, value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _require_sha256(name: str, value: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(ch not in _HEX for ch in value):
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")
    return value


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(k): _freeze(v) for k, v in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(v) for v in value)
    if isinstance(value, tuple):
        return tuple(_freeze(v) for v in value)
    return value


@dataclass(frozen=True, slots=True)
class ProviderDescriptor:
    provider_id: str
    name: str
    domain: str
    role: str
    source_class: str
    capabilities: tuple[str, ...]
    credential_names: tuple[str, ...]
    configuration_names: tuple[str, ...]
    cadence_class: str
    licensing_policy: str
    raw_retention_policy: str
    direct_execution_authority: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        for name in (
            "provider_id", "name", "domain", "role", "source_class",
            "cadence_class", "licensing_policy", "raw_retention_policy",
        ):
            _require_text(name, getattr(self, name))
        if not self.capabilities:
            raise ValueError("capabilities must not be empty")
        object.__setattr__(self, "capabilities", tuple(self.capabilities))
        object.__setattr__(self, "credential_names", tuple(self.credential_names))
        object.__setattr__(self, "configuration_names", tuple(self.configuration_names))


@dataclass(frozen=True, slots=True)
class ProviderHealth:
    provider_id: str
    state: str
    checked_at: datetime | str
    detail: str | None = None
    last_success_at: datetime | str | None = None

    def __post_init__(self) -> None:
        _require_text("provider_id", self.provider_id)
        if self.state not in _PROVIDER_STATES:
            raise ValueError(f"unsupported provider health state: {self.state}")
        checked = normalize_utc(self.checked_at)
        if checked is None:
            raise ValueError("checked_at is required")
        object.__setattr__(self, "checked_at", checked)
        object.__setattr__(self, "last_success_at", normalize_utc(self.last_success_at))


@dataclass(frozen=True, slots=True)
class SourceArtifact:
    provider_id: str
    dataset: str
    raw_artifact_sha256: str
    retrieved_at: datetime | str
    content_type: str | None = None
    source_url: str | None = None
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        _require_text("provider_id", self.provider_id)
        _require_text("dataset", self.dataset)
        _require_sha256("raw_artifact_sha256", self.raw_artifact_sha256)
        retrieved = normalize_utc(self.retrieved_at)
        if retrieved is None:
            raise ValueError("retrieved_at is required")
        object.__setattr__(self, "retrieved_at", retrieved)
        object.__setattr__(self, "metadata", _freeze(self.metadata))


@dataclass(frozen=True, slots=True)
class EvidenceEnvelope:
    source_id: str
    provider_id: str
    dataset: str
    instrument: str | None
    venue: str | None
    source_event_time: datetime | str | None
    source_publication_time: datetime | str | None
    source_available_at: datetime | str | None
    retrieved_at: datetime | str
    ingested_at: datetime | str
    revision_id: str | None
    vintage_id: str | None
    raw_artifact_sha256: str
    ingest_batch_id: str
    data: Mapping[str, Any]
    quality_flags: tuple[str, ...] = ()
    lineage_parents: tuple[str, ...] = ()
    execution_authorized: bool = field(default=False, init=False)
    production_decision_authorized: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        _require_text("source_id", self.source_id)
        _require_text("provider_id", self.provider_id)
        _require_text("dataset", self.dataset)
        _require_text("ingest_batch_id", self.ingest_batch_id)
        _require_sha256("raw_artifact_sha256", self.raw_artifact_sha256)
        retrieved = normalize_utc(self.retrieved_at)
        ingested = normalize_utc(self.ingested_at)
        if retrieved is None or ingested is None:
            raise ValueError("retrieved_at and ingested_at are required")
        object.__setattr__(self, "source_event_time", normalize_utc(self.source_event_time))
        object.__setattr__(self, "source_publication_time", normalize_utc(self.source_publication_time))
        object.__setattr__(self, "source_available_at", normalize_utc(self.source_available_at))
        object.__setattr__(self, "retrieved_at", retrieved)
        object.__setattr__(self, "ingested_at", ingested)
        object.__setattr__(self, "quality_flags", tuple(self.quality_flags))
        object.__setattr__(self, "lineage_parents", tuple(self.lineage_parents))
        object.__setattr__(self, "data", _freeze(self.data))

    @property
    def canonical_sha256(self) -> str:
        return canonical_sha256(self.data)

    def identity_payload(self) -> dict[str, Any]:
        """Identity excludes retrieval/ingest metadata so exact re-fetches dedupe."""
        return {
            "source_id": self.source_id,
            "provider_id": self.provider_id,
            "dataset": self.dataset,
            "instrument": self.instrument,
            "venue": self.venue,
            "source_event_time": self.source_event_time,
            "source_publication_time": self.source_publication_time,
            "source_available_at": self.source_available_at,
            "revision_id": self.revision_id,
            "vintage_id": self.vintage_id,
            "raw_artifact_sha256": self.raw_artifact_sha256,
            "canonical_sha256": self.canonical_sha256,
        }

    @property
    def evidence_id(self) -> str:
        return evidence_id(self.identity_payload())

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "icarus.external-evidence/1",
            "evidence_id": self.evidence_id,
            "source_id": self.source_id,
            "provider_id": self.provider_id,
            "dataset": self.dataset,
            "instrument": self.instrument,
            "venue": self.venue,
            "source_event_time": self.source_event_time,
            "source_publication_time": self.source_publication_time,
            "source_available_at": self.source_available_at,
            "retrieved_at": self.retrieved_at,
            "ingested_at": self.ingested_at,
            "revision_id": self.revision_id,
            "vintage_id": self.vintage_id,
            "raw_artifact_sha256": self.raw_artifact_sha256,
            "canonical_sha256": self.canonical_sha256,
            "ingest_batch_id": self.ingest_batch_id,
            "quality_flags": self.quality_flags,
            "lineage_parents": self.lineage_parents,
            "execution_authorized": False,
            "production_decision_authorized": False,
            "data": self.data,
        }
