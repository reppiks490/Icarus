from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
import os
from types import MappingProxyType

from .contracts import EvidenceEnvelope
from .identity import canonical_sha256, normalize_utc
from .normalization import CollectedBatch, ConflictEdge, NormalizedObservation, StoredBatch
from .redaction import redact_text
from .registry import ProviderRegistry
from .storage import EvidenceCatalog, RawArtifactStore


class ProviderPlanLimited(RuntimeError):
    """Adapter signal that the configured account does not entitle this surface."""


@dataclass(frozen=True, slots=True)
class ProviderContext:
    provider_id: str
    run_id: str
    now: datetime
    force: bool
    environment: Mapping[str, str] = field(repr=False, compare=False)

    def getenv(self, name: str, default: str | None = None) -> str | None:
        return self.environment.get(name, default)


@dataclass(frozen=True, slots=True)
class ProviderRunReceipt:
    run_id: str
    provider_id: str
    state: str
    run_at: datetime
    raw_artifact_sha256s: tuple[str, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    conflict_edges: tuple[ConflictEdge, ...] = ()
    error: str | None = None
    execution_authorized: bool = field(default=False, init=False)
    production_decision_authorized: bool = field(default=False, init=False)


_DEFAULT_CADENCE_SECONDS: dict[str, int | None] = {
    "streaming": 1,
    "realtime": 1,
    "near_real_time": 30,
    "minute": 60,
    "five_minute": 300,
    "intraday": 900,
    "hourly": 3600,
    "daily": 86400,
    "weekly": 604800,
    "event_driven": None,
    "manual": None,
}

_BLOCKING_STATES = frozenset(
    {
        "DISABLED",
        "UNCONFIGURED",
        "PLAN_LIMITED",
        "ENTITLEMENT_REQUIRED",
        "CONFIGURATION_BLOCKED",
        "ERROR",
    }
)


class IngestPipeline:
    def __init__(
        self,
        registry: ProviderRegistry,
        raw_store: RawArtifactStore,
        catalog: EvidenceCatalog,
        *,
        environment: Mapping[str, str] | None = None,
        runtime_states: Mapping[str, str] | None = None,
        cadence_seconds: Mapping[str, int | None] | None = None,
        stale_after_seconds: Mapping[str, int] | None = None,
    ) -> None:
        self.registry = registry
        self.raw_store = raw_store
        self.catalog = catalog
        self._environment = MappingProxyType(dict(os.environ if environment is None else environment))
        self._runtime_states = {key: value.upper() for key, value in (runtime_states or {}).items()}
        self._cadence_seconds = dict(_DEFAULT_CADENCE_SECONDS)
        self._cadence_seconds.update(cadence_seconds or {})
        self._stale_after_seconds = dict(stale_after_seconds or {})
        self._last_success_at: dict[str, datetime] = {}

    @staticmethod
    def _normalize_now(now: datetime | str) -> datetime:
        normalized = normalize_utc(now)
        if normalized is None:
            raise ValueError("now is required")
        return normalized

    @staticmethod
    def _run_id(provider_id: str, now: datetime, force: bool) -> str:
        return "run_" + canonical_sha256(
            {"provider_id": provider_id, "run_at": now, "force": bool(force)}
        )

    def _receipt(
        self,
        *,
        run_id: str,
        provider_id: str,
        state: str,
        run_at: datetime,
        raw_hashes: Iterable[str] = (),
        evidence_ids: Iterable[str] = (),
        conflict_edges: Iterable[ConflictEdge] = (),
        error: str | None = None,
    ) -> ProviderRunReceipt:
        return ProviderRunReceipt(
            run_id=run_id,
            provider_id=provider_id,
            state=state,
            run_at=run_at,
            raw_artifact_sha256s=tuple(raw_hashes),
            evidence_ids=tuple(evidence_ids),
            conflict_edges=tuple(conflict_edges),
            error=error,
        )

    def _safe_error(self, adapter, exc: BaseException) -> str:
        secret_values = [
            self._environment[name]
            for name in adapter.descriptor.credential_names
            if self._environment.get(name)
        ]
        return redact_text(str(exc), secret_values)

    @staticmethod
    def _as_batches(value) -> list[CollectedBatch]:
        if isinstance(value, CollectedBatch):
            return [value]
        if value is None:
            return []
        batches = list(value)
        if not all(isinstance(batch, CollectedBatch) for batch in batches):
            raise TypeError("collect() must return CollectedBatch values")
        return batches

    @staticmethod
    def _as_observations(value) -> list[NormalizedObservation]:
        if isinstance(value, NormalizedObservation):
            return [value]
        if value is None:
            return []
        observations = list(value)
        if not all(isinstance(item, NormalizedObservation) for item in observations):
            raise TypeError("normalize() must return NormalizedObservation values")
        return observations

    def _stale_threshold(self, provider_id: str, cadence_class: str) -> int | None:
        if provider_id in self._stale_after_seconds:
            return self._stale_after_seconds[provider_id]
        cadence = self._cadence_seconds.get(cadence_class, 3600)
        return None if cadence is None else int(cadence) * 3

    def _mark_stale(
        self,
        envelope: EvidenceEnvelope,
        *,
        provider_id: str,
        cadence_class: str,
        now: datetime,
    ) -> tuple[EvidenceEnvelope, bool]:
        threshold = self._stale_threshold(provider_id, cadence_class)
        freshness = (
            envelope.source_available_at
            or envelope.source_publication_time
            or envelope.source_event_time
        )
        if threshold is None or freshness is None:
            return envelope, False
        age = (now - freshness).total_seconds()
        if age <= threshold:
            return envelope, False
        flags = tuple(dict.fromkeys((*envelope.quality_flags, "STALE")))
        return replace(envelope, quality_flags=flags), True

    def _cross_provider_conflicts(
        self,
        envelope: EvidenceEnvelope,
        *,
        now: datetime,
    ) -> tuple[ConflictEdge, ...]:
        if envelope.source_event_time is None:
            return ()
        existing = self.catalog.query_as_of(now, dataset=envelope.dataset)
        edges: list[ConflictEdge] = []
        for candidate in existing:
            if candidate.provider_id == envelope.provider_id:
                continue
            if candidate.instrument != envelope.instrument or candidate.venue != envelope.venue:
                continue
            if candidate.source_event_time != envelope.source_event_time:
                continue
            if candidate.canonical_sha256 == envelope.canonical_sha256:
                continue
            left, right = sorted((candidate.evidence_id, envelope.evidence_id))
            edge = ConflictEdge(left_evidence_id=left, right_evidence_id=right)
            if edge not in edges:
                edges.append(edge)
        return tuple(edges)

    def run_provider(
        self,
        provider_id: str,
        now: datetime | str,
        force: bool = False,
    ) -> ProviderRunReceipt:
        run_at = self._normalize_now(now)
        run_id = self._run_id(provider_id, run_at, force)
        adapter = self.registry.get(provider_id)
        descriptor = adapter.descriptor

        runtime_state = self._runtime_states.get(provider_id, "OK")
        if runtime_state in _BLOCKING_STATES:
            return self._receipt(
                run_id=run_id,
                provider_id=provider_id,
                state=runtime_state,
                run_at=run_at,
            )

        missing_credentials = [
            name for name in descriptor.credential_names if not self._environment.get(name)
        ]
        if missing_credentials:
            return self._receipt(
                run_id=run_id,
                provider_id=provider_id,
                state="UNCONFIGURED",
                run_at=run_at,
                error="missing credentials: " + ", ".join(sorted(missing_credentials)),
            )

        ctx = ProviderContext(
            provider_id=provider_id,
            run_id=run_id,
            now=run_at,
            force=bool(force),
            environment=self._environment,
        )
        raw_hashes: list[str] = []
        evidence_ids: list[str] = []
        conflict_edges: list[ConflictEdge] = []
        any_stale = False

        try:
            batches = self._as_batches(adapter.collect(ctx))
            for batch in batches:
                raw_ref = self.raw_store.put(
                    provider_id,
                    batch.dataset,
                    batch.payload,
                    {
                        **dict(batch.metadata),
                        "retrieved_at": batch.retrieved_at.isoformat(),
                        "content_type": batch.content_type,
                    },
                )
                raw_hashes.append(raw_ref.sha256)
                stored = StoredBatch(
                    dataset=batch.dataset,
                    payload=batch.payload,
                    retrieved_at=batch.retrieved_at,
                    raw_ref=raw_ref,
                    content_type=batch.content_type,
                    source_url=batch.source_url,
                    metadata=batch.metadata,
                )
                observations = self._as_observations(adapter.normalize(stored, ctx))
                for observation in observations:
                    if observation.dataset != batch.dataset:
                        raise ValueError(
                            "normalized observation dataset must match its collected batch"
                        )
                    envelope = observation.to_envelope(
                        provider_id=provider_id,
                        raw_artifact_sha256=raw_ref.sha256,
                        retrieved_at=batch.retrieved_at,
                        ingested_at=run_at,
                        ingest_batch_id=run_id,
                    )
                    envelope, is_stale = self._mark_stale(
                        envelope,
                        provider_id=provider_id,
                        cadence_class=descriptor.cadence_class,
                        now=run_at,
                    )
                    any_stale = any_stale or is_stale
                    edges = self._cross_provider_conflicts(envelope, now=run_at)
                    if edges:
                        flags = tuple(
                            dict.fromkeys((*envelope.quality_flags, "CROSS_PROVIDER_CONFLICT"))
                        )
                        envelope = replace(envelope, quality_flags=flags)
                        conflict_edges.extend(edge for edge in edges if edge not in conflict_edges)
                    self.catalog.upsert(envelope)
                    evidence_ids.append(envelope.evidence_id)
        except ProviderPlanLimited as exc:
            return self._receipt(
                run_id=run_id,
                provider_id=provider_id,
                state="PLAN_LIMITED",
                run_at=run_at,
                raw_hashes=raw_hashes,
                evidence_ids=evidence_ids,
                conflict_edges=conflict_edges,
                error=self._safe_error(adapter, exc),
            )
        except Exception as exc:
            return self._receipt(
                run_id=run_id,
                provider_id=provider_id,
                state="ERROR",
                run_at=run_at,
                raw_hashes=raw_hashes,
                evidence_ids=evidence_ids,
                conflict_edges=conflict_edges,
                error=self._safe_error(adapter, exc),
            )

        self._last_success_at[provider_id] = run_at
        return self._receipt(
            run_id=run_id,
            provider_id=provider_id,
            state="STALE" if any_stale else "OK",
            run_at=run_at,
            raw_hashes=raw_hashes,
            evidence_ids=evidence_ids,
            conflict_edges=conflict_edges,
        )

    def run_due(self, now: datetime | str) -> list[ProviderRunReceipt]:
        run_at = self._normalize_now(now)
        receipts: list[ProviderRunReceipt] = []
        for provider_id in self.registry.provider_ids():
            descriptor = self.registry.get(provider_id).descriptor
            cadence = self._cadence_seconds.get(descriptor.cadence_class, 3600)
            if cadence is None:
                continue
            last_success = self._last_success_at.get(provider_id)
            if last_success is not None:
                elapsed = (run_at - last_success).total_seconds()
                if elapsed < cadence:
                    continue
            receipts.append(self.run_provider(provider_id, run_at))
        return receipts
