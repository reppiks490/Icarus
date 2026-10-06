from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType
from typing import Any

from .contracts import EvidenceEnvelope
from .identity import normalize_utc
from .storage import RawArtifactRef


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, tuple):
        return tuple(_freeze(item) for item in value)
    return value


@dataclass(frozen=True, slots=True)
class CollectedBatch:
    """Exact provider bytes plus retrieval metadata, before raw persistence."""

    dataset: str
    payload: bytes = field(repr=False)
    retrieved_at: datetime | str
    content_type: str | None = None
    source_url: str | None = field(default=None, repr=False)
    metadata: Mapping[str, Any] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.dataset, str) or not self.dataset.strip():
            raise ValueError("dataset is required")
        if not isinstance(self.payload, bytes):
            raise TypeError("payload must be bytes")
        retrieved = normalize_utc(self.retrieved_at)
        if retrieved is None:
            raise ValueError("retrieved_at is required")
        object.__setattr__(self, "retrieved_at", retrieved)
        object.__setattr__(self, "metadata", _freeze(self.metadata))


@dataclass(frozen=True, slots=True)
class StoredBatch:
    """A collected batch after its exact bytes have been durably content-addressed."""

    dataset: str
    payload: bytes = field(repr=False)
    retrieved_at: datetime
    raw_ref: RawArtifactRef
    content_type: str | None = None
    source_url: str | None = field(default=None, repr=False)
    metadata: Mapping[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True, slots=True)
class NormalizedObservation:
    source_id: str
    dataset: str
    instrument: str | None
    venue: str | None
    source_event_time: datetime | str | None
    source_publication_time: datetime | str | None
    source_available_at: datetime | str | None
    revision_id: str | None
    vintage_id: str | None
    data: Mapping[str, Any]
    quality_flags: tuple[str, ...] = ()
    lineage_parents: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not isinstance(self.source_id, str) or not self.source_id.strip():
            raise ValueError("source_id is required")
        if not isinstance(self.dataset, str) or not self.dataset.strip():
            raise ValueError("dataset is required")
        object.__setattr__(self, "source_event_time", normalize_utc(self.source_event_time))
        object.__setattr__(self, "source_publication_time", normalize_utc(self.source_publication_time))
        object.__setattr__(self, "source_available_at", normalize_utc(self.source_available_at))
        object.__setattr__(self, "data", _freeze(self.data))
        object.__setattr__(self, "quality_flags", tuple(self.quality_flags))
        object.__setattr__(self, "lineage_parents", tuple(self.lineage_parents))

    def to_envelope(
        self,
        *,
        provider_id: str,
        raw_artifact_sha256: str,
        retrieved_at: datetime | str,
        ingested_at: datetime | str,
        ingest_batch_id: str,
    ) -> EvidenceEnvelope:
        return EvidenceEnvelope(
            source_id=self.source_id,
            provider_id=provider_id,
            dataset=self.dataset,
            instrument=self.instrument,
            venue=self.venue,
            source_event_time=self.source_event_time,
            source_publication_time=self.source_publication_time,
            source_available_at=self.source_available_at,
            retrieved_at=retrieved_at,
            ingested_at=ingested_at,
            revision_id=self.revision_id,
            vintage_id=self.vintage_id,
            raw_artifact_sha256=raw_artifact_sha256,
            ingest_batch_id=ingest_batch_id,
            data=self.data,
            quality_flags=self.quality_flags,
            lineage_parents=self.lineage_parents,
        )


@dataclass(frozen=True, slots=True)
class ConflictEdge:
    left_evidence_id: str
    right_evidence_id: str
    reason: str = "CROSS_PROVIDER_DISAGREEMENT"
