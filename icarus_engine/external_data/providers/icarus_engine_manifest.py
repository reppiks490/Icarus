from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date, datetime, time, timezone
import json
from typing import Any

from ..contracts import ProviderDescriptor
from ..identity import normalize_utc
from ..normalization import CollectedBatch, NormalizedObservation, StoredBatch


UTC = timezone.utc
DATABENTO_MANIFEST_SCHEMAS = frozenset({"mbo", "mbp-10", "tbbo", "trades", "statistics"})
_SUPPORTED_KINDS = frozenset({"external_data_fabric", "databento_corpus"})


@dataclass(frozen=True, slots=True)
class ManifestDocument:
    """Exact bytes of one upstream Icarus-engine compact manifest.

    The bytes are deliberately supplied to this adapter by the orchestration layer
    (checkout, artifact transfer, or another authenticated repository reader).  The
    bridge itself has no vendor client and performs no FMP/EODHD/Tiingo/Databento
    network requests.
    """

    payload: bytes
    kind: str
    source_repository: str
    source_ref: str
    source_path: str
    fetched_at: datetime | str

    def __post_init__(self) -> None:
        if not isinstance(self.payload, bytes):
            raise TypeError("manifest payload must be bytes")
        if self.kind not in _SUPPORTED_KINDS:
            raise ValueError(f"unsupported Icarus-engine manifest kind: {self.kind!r}")
        for field_name in ("source_repository", "source_ref", "source_path"):
            value = getattr(self, field_name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field_name} is required")
        fetched = normalize_utc(self.fetched_at)
        if fetched is None:
            raise ValueError("fetched_at is required")
        object.__setattr__(self, "fetched_at", fetched)


class IcarusEngineManifestBridge:
    """Read-only bridge for compact artifacts already produced by Icarus-engine.

    This is intentionally *not* a second vendor collector.  It captures the exact
    upstream manifest bytes in the central raw-artifact store and normalizes only
    compact research/provenance records.  Referenced upstream cache/feature hashes
    remain references; they are never represented as if their licensed raw rows had
    been copied into central ICARUS.
    """

    descriptor = ProviderDescriptor(
        provider_id="icarus_engine_manifest",
        name="Icarus-engine manifest bridge",
        domain="cross_repo_evidence",
        role="reuse_existing_vendor_collection_without_duplicate_calls",
        source_class="upstream_compact_manifest",
        capabilities=(
            "fmp_compact_manifest",
            "eodhd_compact_manifest",
            "tiingo_compact_manifest",
            "databento_mbo_manifest",
            "databento_mbp10_manifest",
            "databento_tbbo_manifest",
            "databento_trades_manifest",
            "databento_statistics_manifest",
        ),
        credential_names=(),
        configuration_names=(),
        cadence_class="manual",
        licensing_policy="bridge compact manifests only; preserve upstream licensing boundaries",
        raw_retention_policy="retain exact compact manifest bytes; do not copy upstream licensed raw rows",
    )

    def __init__(self, documents: Iterable[ManifestDocument]):
        self._documents = tuple(documents)
        if not self._documents:
            raise ValueError("at least one manifest document is required")
        identities = [(doc.kind, doc.source_repository, doc.source_ref, doc.source_path) for doc in self._documents]
        if len(identities) != len(set(identities)):
            raise ValueError("duplicate upstream manifest document identity")

    def collect(self, ctx) -> list[CollectedBatch]:
        batches: list[CollectedBatch] = []
        for document in self._documents:
            batches.append(
                CollectedBatch(
                    dataset=self._dataset_name(document.kind),
                    payload=document.payload,
                    retrieved_at=document.fetched_at,
                    content_type="application/json",
                    source_url=None,
                    metadata={
                        "manifest_kind": document.kind,
                        "source_repository": document.source_repository,
                        "source_ref": document.source_ref,
                        "source_path": document.source_path,
                        "manifest_fetched_at": document.fetched_at.isoformat(),
                        "bridge_mode": "read_only_no_vendor_calls",
                    },
                )
            )
        return batches

    def normalize(self, batch: StoredBatch, ctx) -> list[NormalizedObservation]:
        try:
            manifest = json.loads(batch.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("upstream Icarus-engine manifest is not valid UTF-8 JSON") from exc
        if not isinstance(manifest, dict):
            raise ValueError("upstream Icarus-engine manifest root must be an object")

        kind = str(batch.metadata.get("manifest_kind") or "")
        if kind == "external_data_fabric":
            return self._normalize_external_fabric(manifest, batch)
        if kind == "databento_corpus":
            return self._normalize_databento_corpus(manifest, batch)
        raise ValueError(f"unsupported manifest kind in stored batch: {kind!r}")

    @staticmethod
    def _dataset_name(kind: str) -> str:
        return f"icarus_engine_{kind}"

    @staticmethod
    def _publication_time(manifest: Mapping[str, Any], batch: StoredBatch) -> datetime:
        generated = manifest.get("generated_at")
        if generated is None:
            return batch.retrieved_at
        normalized = normalize_utc(generated)
        if normalized is None:
            return batch.retrieved_at
        return normalized

    @staticmethod
    def _provenance(batch: StoredBatch) -> dict[str, Any]:
        return {
            "source_repository": str(batch.metadata["source_repository"]),
            "source_ref": str(batch.metadata["source_ref"]),
            "source_path": str(batch.metadata["source_path"]),
            "manifest_fetched_at": batch.retrieved_at.isoformat(),
            "raw_market_payload_copied": False,
            "bridge_mode": "read_only_no_vendor_calls",
        }

    def _normalize_external_fabric(
        self,
        manifest: Mapping[str, Any],
        batch: StoredBatch,
    ) -> list[NormalizedObservation]:
        if manifest.get("execution_authorized") is True or manifest.get("production_decision_authorized") is True:
            raise ValueError("upstream external-data manifest unexpectedly claims production authority")

        providers = manifest.get("providers")
        if not isinstance(providers, Mapping):
            raise ValueError("external_data_fabric manifest requires a providers object")
        published = self._publication_time(manifest, batch)
        provenance = self._provenance(batch)
        observations: list[NormalizedObservation] = []

        for provider_name in sorted(providers):
            provider = providers[provider_name]
            if not isinstance(provider, Mapping):
                continue
            datasets = provider.get("datasets")
            if not isinstance(datasets, Mapping):
                continue
            for dataset_name in sorted(datasets):
                dataset = datasets[dataset_name]
                if not isinstance(dataset, Mapping):
                    continue
                symbols = dataset.get("symbols")
                if isinstance(symbols, Mapping) and symbols:
                    for symbol in sorted(symbols):
                        compact = symbols[symbol]
                        if not isinstance(compact, Mapping):
                            continue
                        observations.append(
                            self._external_observation(
                                batch=batch,
                                published=published,
                                provenance=provenance,
                                provider_name=str(provider_name),
                                dataset_name=str(dataset_name),
                                instrument=str(symbol),
                                compact=compact,
                                provider_status=provider.get("status"),
                                dataset_status=dataset.get("status"),
                            )
                        )
                else:
                    observations.append(
                        self._external_observation(
                            batch=batch,
                            published=published,
                            provenance=provenance,
                            provider_name=str(provider_name),
                            dataset_name=str(dataset_name),
                            instrument=None,
                            compact=dataset,
                            provider_status=provider.get("status"),
                            dataset_status=dataset.get("status"),
                        )
                    )
        return observations

    def _external_observation(
        self,
        *,
        batch: StoredBatch,
        published: datetime,
        provenance: Mapping[str, Any],
        provider_name: str,
        dataset_name: str,
        instrument: str | None,
        compact: Mapping[str, Any],
        provider_status: Any,
        dataset_status: Any,
    ) -> NormalizedObservation:
        cache = compact.get("cache") if isinstance(compact.get("cache"), Mapping) else {}
        cache_sha = cache.get("sha256") if isinstance(cache, Mapping) else None
        cache_bytes = cache.get("bytes") if isinstance(cache, Mapping) else None
        compact_fields = {key: value for key, value in compact.items() if key != "cache"}
        source_suffix = instrument or "summary"
        data = {
            **provenance,
            "evidence_kind": "upstream_compact_manifest",
            "upstream_provider": provider_name,
            "upstream_dataset": dataset_name,
            "upstream_provider_status": provider_status,
            "upstream_dataset_status": dataset_status,
            "upstream_cache_sha256": cache_sha,
            "upstream_cache_bytes": cache_bytes,
            "compact_fields": compact_fields,
        }
        return NormalizedObservation(
            source_id=(
                f"icarus-engine:{provider_name}:{dataset_name}:{source_suffix}"
            ),
            dataset=batch.dataset,
            instrument=instrument,
            venue=None,
            source_event_time=None,
            source_publication_time=published,
            source_available_at=published,
            revision_id=str(batch.metadata["source_ref"]),
            vintage_id=None,
            data=data,
            quality_flags=("UPSTREAM_COMPACT_MANIFEST",),
        )

    def _normalize_databento_corpus(
        self,
        manifest: Mapping[str, Any],
        batch: StoredBatch,
    ) -> list[NormalizedObservation]:
        if manifest.get("execution_authorized") is True or manifest.get("production_decision_authorized") is True:
            raise ValueError("upstream Databento manifest unexpectedly claims production authority")

        requests = manifest.get("requests")
        if not isinstance(requests, list):
            raise ValueError("Databento corpus manifest requires a requests array")
        published = self._publication_time(manifest, batch)
        provenance = self._provenance(batch)
        raw_retention = manifest.get("raw_retention")
        observations: list[NormalizedObservation] = []

        for index, row in enumerate(requests):
            if not isinstance(row, Mapping):
                continue
            schema = str(row.get("schema") or "").strip().lower()
            if schema not in DATABENTO_MANIFEST_SCHEMAS:
                continue
            root = str(row.get("root") or row.get("symbol") or "").strip() or None
            symbol = str(row.get("symbol") or "").strip() or None
            day = row.get("day")
            event_time = self._day_to_utc(day)
            feature_sha = row.get("feature_sha256")
            source_key = f"{schema}:{symbol or root or 'unknown'}:{day or index}"
            compact_fields = {
                key: value
                for key, value in row.items()
                if key not in {"feature_sha256", "feature_path", "feature_bytes"}
            }
            data = {
                **provenance,
                "evidence_kind": "upstream_derived_feature_manifest",
                "upstream_provider": "databento",
                "upstream_dataset": row.get("dataset") or manifest.get("dataset"),
                "databento_schema": schema,
                "upstream_symbol": symbol,
                "upstream_feature_sha256": feature_sha,
                "upstream_feature_path": row.get("feature_path"),
                "upstream_feature_bytes": row.get("feature_bytes"),
                "upstream_raw_retention": raw_retention,
                "compact_fields": compact_fields,
            }
            quality = ["UPSTREAM_DERIVED_FEATURE_MANIFEST", "LICENSED_RAW_NOT_COPIED"]
            if row.get("status") not in {None, "ok", "cached"}:
                quality.append("UPSTREAM_NON_OK_STATUS")
            observations.append(
                NormalizedObservation(
                    source_id=f"icarus-engine:databento:{source_key}",
                    dataset=batch.dataset,
                    instrument=root,
                    venue=str(row.get("dataset") or manifest.get("dataset") or "") or None,
                    source_event_time=event_time,
                    source_publication_time=published,
                    source_available_at=published,
                    revision_id=str(batch.metadata["source_ref"]),
                    vintage_id=None,
                    data=data,
                    quality_flags=tuple(quality),
                )
            )
        return observations

    @staticmethod
    def _day_to_utc(value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return normalize_utc(value)
        if isinstance(value, date):
            return datetime.combine(value, time.min, tzinfo=UTC)
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            try:
                parsed_day = date.fromisoformat(text[:10])
            except ValueError:
                return None
            return datetime.combine(parsed_day, time.min, tzinfo=UTC)
        return None
