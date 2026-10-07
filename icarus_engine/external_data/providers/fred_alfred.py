from __future__ import annotations

from datetime import datetime
from typing import Any

from ..contracts import ProviderDescriptor
from ..identity import normalize_utc
from ..normalization import NormalizedObservation, StoredBatch
from ..transport import Transport
from ._public_macro import decode_json, number, request_json, require_text, response_batch, utc_day


FRED_OBSERVATIONS_URL = "https://api.stlouisfed.org/fred/series/observations"


def parse_fred_observations(
    payload: bytes,
    *,
    series_id: str,
    retrieved_at: datetime | str,
) -> list[NormalizedObservation]:
    root = decode_json(payload)
    if not isinstance(root, dict) or not isinstance(root.get("observations"), list):
        raise ValueError("FRED schema changed: expected observations array")
    unit_code = require_text(root.get("units"), field="units")
    retrieved = normalize_utc(retrieved_at)
    if retrieved is None:
        raise ValueError("retrieved_at is required")
    series = require_text(series_id, field="series_id")

    observations: list[NormalizedObservation] = []
    for row in root["observations"]:
        if not isinstance(row, dict):
            raise ValueError("FRED observation row must be an object")
        event_time = utc_day(row.get("date"), field="date")
        realtime_start_text = require_text(row.get("realtime_start"), field="realtime_start")
        require_text(row.get("realtime_end"), field="realtime_end")
        available_at = utc_day(realtime_start_text, field="realtime_start")
        raw_value = row.get("value")
        quality: tuple[str, ...] = ()
        if raw_value in (None, ".", ""):
            value = None
            quality = ("MISSING_VALUE",)
        else:
            value = number(raw_value, field="value")
        observations.append(
            NormalizedObservation(
                source_id=f"fred:{series}:{event_time.date().isoformat()}",
                dataset="fred_alfred_observations",
                instrument=series,
                venue="Federal Reserve Bank of St. Louis",
                source_event_time=event_time,
                source_publication_time=available_at,
                source_available_at=available_at,
                revision_id=realtime_start_text,
                vintage_id=realtime_start_text,
                data={
                    "series_id": series,
                    "value": value,
                    "unit_code": unit_code,
                    "realtime_start": realtime_start_text,
                    "realtime_end": row["realtime_end"],
                    "retrieved_at": retrieved.isoformat(),
                },
                quality_flags=quality,
            )
        )
    if not observations:
        raise ValueError("FRED returned zero usable observations")
    observations.sort(key=lambda item: (item.source_event_time, item.source_available_at, item.vintage_id or ""))
    return observations


class FredAlfredAdapter:
    descriptor = ProviderDescriptor(
        provider_id="fred_alfred",
        name="FRED and ALFRED",
        domain="public_macro",
        role="macro_series_and_vintage_evidence",
        source_class="credentialed_public_api",
        capabilities=("fred_series", "alfred_vintages", "revisions"),
        credential_names=("FRED_API_KEY",),
        configuration_names=(),
        cadence_class="release_driven",
        licensing_policy="public_source_terms",
        raw_retention_policy="public_cache_allowed_no_raw_git",
    )

    def __init__(
        self,
        transport: Transport,
        series_ids: tuple[str, ...],
        *,
        as_of: str | None = None,
        observation_start: str | None = None,
        observation_end: str | None = None,
    ):
        self.transport = transport
        self.series_ids = tuple(series_ids)
        if not self.series_ids:
            raise ValueError("at least one FRED series_id is required")
        self.as_of = as_of
        self.observation_start = observation_start
        self.observation_end = observation_end

    def collect(self, ctx):
        key = ctx.getenv("FRED_API_KEY")
        if not key:
            raise ValueError("FRED_API_KEY is not configured")
        as_of = self.as_of or ctx.now.date().isoformat()
        batches = []
        for series_id in self.series_ids:
            params: list[tuple[str, str]] = [
                ("series_id", series_id),
                ("api_key", key),
                ("file_type", "json"),
                ("realtime_start", as_of),
                ("realtime_end", as_of),
            ]
            if self.observation_start:
                params.append(("observation_start", self.observation_start))
            if self.observation_end:
                params.append(("observation_end", self.observation_end))
            _, response = request_json(
                self.transport,
                provider_id=self.descriptor.provider_id,
                base_url=FRED_OBSERVATIONS_URL,
                params=params,
                secret_keys={"api_key"},
            )
            batches.append(
                response_batch(
                    response,
                    dataset="fred_alfred_observations",
                    retrieved_at=ctx.now,
                    metadata={"series_id": series_id, "as_of": as_of},
                )
            )
        return batches

    def normalize(self, batch: StoredBatch, ctx):
        series_id = require_text(batch.metadata.get("series_id"), field="series_id")
        return parse_fred_observations(
            batch.payload,
            series_id=series_id,
            retrieved_at=batch.retrieved_at,
        )
