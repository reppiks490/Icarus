from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from ..contracts import ProviderDescriptor
from ..identity import normalize_utc
from ..normalization import NormalizedObservation, StoredBatch
from ..transport import Transport
from ._public_macro import decode_json, number, request_json, require_text, response_batch, utc_day


NYFED_ENDPOINTS = (
    ("sofr", "https://markets.newyorkfed.org/api/rates/secured/sofr/search.json"),
    ("effr", "https://markets.newyorkfed.org/api/rates/unsecured/effr/search.json"),
    ("repo", "https://markets.newyorkfed.org/api/rp/reverserepo/propositions/search.json"),
)


def parse_nyfed(
    payload: bytes,
    *,
    retrieved_at: datetime | str,
    now: datetime | str | None = None,
    max_event_age_days: int | None = None,
) -> list[NormalizedObservation]:
    root = decode_json(payload)
    if not isinstance(root, dict):
        raise ValueError("NY Fed payload root must be an object")
    retrieved = normalize_utc(retrieved_at)
    current = normalize_utc(now) if now is not None else retrieved
    if retrieved is None or current is None:
        raise ValueError("retrieved_at/now must be timezone-aware")

    ref_rates = root.get("refRates")
    repo_rows = root.get("repoOperations")
    if ref_rates is None and repo_rows is None:
        raise ValueError("NY Fed schema changed: no refRates or repoOperations")
    if ref_rates is not None and not isinstance(ref_rates, list):
        raise ValueError("NY Fed refRates must be an array")
    if repo_rows is not None and not isinstance(repo_rows, list):
        raise ValueError("NY Fed repoOperations must be an array")

    observations: list[NormalizedObservation] = []
    event_times: list[datetime] = []
    for index, row in enumerate(ref_rates or []):
        if not isinstance(row, dict):
            raise ValueError("NY Fed refRates row must be an object")
        kind = require_text(row.get("type"), field="type").upper()
        if kind not in {"SOFR", "EFFR", "OBFR", "TGCR", "BGCR"}:
            raise ValueError(f"unsupported NY Fed reference-rate type {kind!r}")
        event_time = utc_day(row.get("effectiveDate"), field="effectiveDate")
        event_times.append(event_time)
        rate = number(row.get("percentRate"), field="percentRate")
        volume = row.get("volumeInBillions")
        data: dict[str, Any] = {
            "kind": kind,
            "rate_percent": rate,
            "rate_unit": "percent",
        }
        if volume not in (None, ""):
            data["volume_billions_usd"] = number(volume, field="volumeInBillions")
            data["volume_unit"] = "billion USD"
        observations.append(
            NormalizedObservation(
                source_id=f"nyfed:{kind}:{event_time.date().isoformat()}",
                dataset="nyfed_rates_repo",
                instrument=kind,
                venue="Federal Reserve Bank of New York",
                source_event_time=event_time,
                source_publication_time=None,
                source_available_at=retrieved,
                revision_id=None,
                vintage_id=None,
                data=data,
                quality_flags=("PUBLICATION_TIME_UNKNOWN",),
            )
        )

    for index, row in enumerate(repo_rows or []):
        if not isinstance(row, dict):
            raise ValueError("NY Fed repoOperations row must be an object")
        operation_type = require_text(row.get("operationType"), field="operationType").upper()
        event_time = utc_day(row.get("operationDate"), field="operationDate")
        event_times.append(event_time)
        amount = number(row.get("amountBillions"), field="amountBillions")
        award_rate = number(row.get("awardRatePercent"), field="awardRatePercent")
        observations.append(
            NormalizedObservation(
                source_id=f"nyfed:{operation_type}:{event_time.date().isoformat()}:{index}",
                dataset="nyfed_rates_repo",
                instrument=operation_type,
                venue="Federal Reserve Bank of New York",
                source_event_time=event_time,
                source_publication_time=None,
                source_available_at=retrieved,
                revision_id=None,
                vintage_id=None,
                data={
                    "kind": operation_type,
                    "amount_billions_usd": amount,
                    "amount_unit": "billion USD",
                    "award_rate_percent": award_rate,
                    "rate_unit": "percent",
                },
                quality_flags=("PUBLICATION_TIME_UNKNOWN",),
            )
        )

    if not observations:
        raise ValueError("NY Fed payload contains zero usable observations")
    if max_event_age_days is not None:
        if max_event_age_days < 0:
            raise ValueError("max_event_age_days must be non-negative")
        latest = max(event_times)
        if current - latest > timedelta(days=max_event_age_days):
            raise ValueError(
                f"NY Fed release is stale: latest event {latest.date().isoformat()} exceeds {max_event_age_days} days"
            )
    return observations


class NyFedAdapter:
    descriptor = ProviderDescriptor(
        provider_id="ny_fed",
        name="Federal Reserve Bank of New York",
        domain="public_macro",
        role="rates_repo_and_liquidity_evidence",
        source_class="public_api",
        capabilities=("sofr", "effr", "obfr", "repo", "reverse_repo", "dealer_statistics"),
        credential_names=(),
        configuration_names=(),
        cadence_class="daily",
        licensing_policy="public_source_terms",
        raw_retention_policy="public_cache_allowed_no_raw_git",
    )

    def __init__(self, transport: Transport, endpoints=NYFED_ENDPOINTS, *, max_event_age_days: int = 7):
        self.transport = transport
        self.endpoints = tuple(endpoints)
        self.max_event_age_days = max_event_age_days

    def collect(self, ctx):
        batches = []
        for surface, url in self.endpoints:
            _, response = request_json(
                self.transport,
                provider_id=self.descriptor.provider_id,
                base_url=url,
            )
            batches.append(
                response_batch(
                    response,
                    dataset="nyfed_rates_repo",
                    retrieved_at=ctx.now,
                    metadata={"surface": surface},
                )
            )
        return batches

    def normalize(self, batch: StoredBatch, ctx):
        return parse_nyfed(
            batch.payload,
            retrieved_at=batch.retrieved_at,
            now=ctx.now,
            max_event_age_days=self.max_event_age_days,
        )
