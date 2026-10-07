from __future__ import annotations

from datetime import datetime
from typing import Any

from ..contracts import ProviderDescriptor
from ..identity import normalize_utc
from ..normalization import NormalizedObservation, StoredBatch
from ..transport import Transport
from ._public_macro import decode_json, number, period_start, request_json, require_text, response_batch


EIA_BASE = "https://api.eia.gov/v2"
_METADATA_FIELDS = {
    "period",
    "series",
    "seriesDescription",
    "series-description",
    "name",
    "description",
}


def _value_and_unit(row: dict[str, Any]) -> tuple[str, float, str]:
    if row.get("value") not in (None, ""):
        unit = row.get("unit") or row.get("value-units")
        if not isinstance(unit, str) or not unit.strip():
            raise ValueError("EIA row is missing unit for value")
        return "value", number(row["value"], field="value"), unit.strip()

    candidates: list[tuple[str, float, str]] = []
    for key, value in row.items():
        if key in _METADATA_FIELDS or key == "unit" or key.endswith("-units"):
            continue
        unit = row.get(f"{key}-units")
        if not isinstance(unit, str) or not unit.strip():
            continue
        try:
            numeric = number(value, field=key)
        except ValueError:
            continue
        candidates.append((key, numeric, unit.strip()))
    if len(candidates) != 1:
        raise ValueError("EIA row must expose exactly one value column with explicit units")
    return candidates[0]


def parse_eia(payload: bytes, *, retrieved_at: datetime | str) -> list[NormalizedObservation]:
    root = decode_json(payload)
    if not isinstance(root, dict) or not isinstance(root.get("response"), dict):
        raise ValueError("EIA schema changed: expected response object")
    response = root["response"]
    rows = response.get("data")
    if not isinstance(rows, list):
        raise ValueError("EIA response.data must be an array")
    frequency = require_text(response.get("frequency"), field="response.frequency")
    retrieved = normalize_utc(retrieved_at)
    if retrieved is None:
        raise ValueError("retrieved_at is required")

    observations: list[NormalizedObservation] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError("EIA data row must be an object")
        event_time = period_start(row.get("period"))
        value_name, value, unit = _value_and_unit(row)
        series = str(row.get("series") or row.get("seriesDescription") or row.get("series-description") or "unknown")
        if series == "unknown":
            raise ValueError("EIA row is missing series identity")
        source_id = f"eia:{series}:{event_time.date().isoformat()}:{value_name}"
        observations.append(
            NormalizedObservation(
                source_id=source_id,
                dataset="eia_series",
                instrument=series,
                venue="U.S. Energy Information Administration",
                source_event_time=event_time,
                source_publication_time=None,
                source_available_at=retrieved,
                revision_id=None,
                vintage_id=None,
                data={
                    "series": series,
                    "series_description": row.get("seriesDescription") or row.get("series-description"),
                    "metric": value_name,
                    "value": value,
                    "unit": unit,
                    "frequency": frequency,
                    "scale_applied": 1.0,
                },
                quality_flags=("PUBLICATION_TIME_UNKNOWN",),
            )
        )
    if not observations:
        raise ValueError("EIA returned zero usable observations")
    return observations


class EiaAdapter:
    descriptor = ProviderDescriptor(
        provider_id="eia",
        name="U.S. Energy Information Administration",
        domain="public_macro",
        role="energy_supply_demand_inventory_evidence",
        source_class="credentialed_public_api",
        capabilities=("petroleum", "crude_imports", "natural_gas", "electricity", "coal"),
        credential_names=("EIA_API_KEY",),
        configuration_names=(),
        cadence_class="release_driven",
        licensing_policy="public_source_terms",
        raw_retention_policy="public_cache_allowed_no_raw_git",
    )

    def __init__(
        self,
        transport: Transport,
        *,
        route: str,
        data_fields=("value",),
        frequency: str | None = None,
        facets: dict[str, tuple[str, ...]] | None = None,
        start: str | None = None,
        end: str | None = None,
        length: int = 5000,
        offset: int = 0,
    ):
        self.transport = transport
        self.route = route.strip("/")
        if not self.route:
            raise ValueError("EIA route is required")
        self.data_fields = tuple(data_fields)
        if not self.data_fields:
            raise ValueError("at least one EIA data field is required")
        self.frequency = frequency
        self.facets = dict(facets or {})
        self.start = start
        self.end = end
        self.length = int(length)
        self.offset = int(offset)

    def collect(self, ctx):
        key = ctx.getenv("EIA_API_KEY")
        if not key:
            raise ValueError("EIA_API_KEY is not configured")
        params: list[tuple[str, str]] = [("api_key", key)]
        params.extend(("data[]", field) for field in self.data_fields)
        if self.frequency:
            params.append(("frequency", self.frequency))
        for facet, values in sorted(self.facets.items()):
            params.extend((f"facets[{facet}][]", value) for value in values)
        if self.start:
            params.append(("start", self.start))
        if self.end:
            params.append(("end", self.end))
        params.extend([("length", str(self.length)), ("offset", str(self.offset))])
        _, response = request_json(
            self.transport,
            provider_id=self.descriptor.provider_id,
            base_url=f"{EIA_BASE}/{self.route}/data/",
            params=params,
            secret_keys={"api_key"},
        )
        return response_batch(
            response,
            dataset="eia_series",
            retrieved_at=ctx.now,
            metadata={"route": self.route, "offset": self.offset, "length": self.length},
        )

    def normalize(self, batch: StoredBatch, ctx):
        return parse_eia(batch.payload, retrieved_at=batch.retrieved_at)
