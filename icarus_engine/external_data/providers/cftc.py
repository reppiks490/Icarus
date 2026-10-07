from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from ..contracts import ProviderDescriptor
from ..identity import normalize_utc
from ..normalization import NormalizedObservation, StoredBatch
from ..transport import Transport
from ._public_macro import decode_json, integer, request_json, require_text, response_batch, utc_day


CFTC_TFF_URL = "https://publicreporting.cftc.gov/resource/gpe5-46if.json"


def _position(row: dict[str, Any], *names: str, required: bool = True) -> int | None:
    for name in names:
        if row.get(name) not in (None, ""):
            return integer(row[name], field=name)
    if required:
        raise ValueError(f"missing required CFTC position field: {names[0]}")
    return None


def parse_cftc_tff(
    payload: bytes,
    *,
    retrieved_at: datetime | str,
    now: datetime | str | None = None,
    max_report_age_days: int | None = None,
) -> list[NormalizedObservation]:
    rows = decode_json(payload)
    if not isinstance(rows, list):
        raise ValueError("CFTC TFF payload root must be an array")
    retrieved = normalize_utc(retrieved_at)
    current = normalize_utc(now) if now is not None else retrieved
    if retrieved is None or current is None:
        raise ValueError("retrieved_at/now must be timezone-aware")

    observations: list[NormalizedObservation] = []
    report_dates: list[datetime] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("CFTC TFF row must be an object")
        report_date = utc_day(row.get("report_date_as_yyyy_mm_dd"), field="report_date_as_yyyy_mm_dd")
        code = require_text(row.get("cftc_contract_market_code"), field="cftc_contract_market_code")
        market = require_text(row.get("market_and_exchange_names"), field="market_and_exchange_names")
        report_dates.append(report_date)
        data = {
            "market": market,
            "contract_market_code": code,
            "open_interest_contracts": _position(row, "open_interest_all"),
            "dealer_long_contracts": _position(row, "dealer_positions_long_all"),
            "dealer_short_contracts": _position(row, "dealer_positions_short_all"),
            "asset_manager_long_contracts": _position(row, "asset_mgr_positions_long", "asset_mgr_positions_long_all"),
            "asset_manager_short_contracts": _position(row, "asset_mgr_positions_short", "asset_mgr_positions_short_all"),
            "leveraged_money_long_contracts": _position(row, "lev_money_positions_long", "lev_money_positions_long_all"),
            "leveraged_money_short_contracts": _position(row, "lev_money_positions_short", "lev_money_positions_short_all"),
            "other_reportables_long_contracts": _position(row, "other_rept_positions_long", "other_rept_positions_long_all"),
            "other_reportables_short_contracts": _position(row, "other_rept_positions_short", "other_rept_positions_short_all"),
            "nonreportable_long_contracts": _position(row, "nonrept_positions_long_all", "nonrept_positions_long"),
            "nonreportable_short_contracts": _position(row, "nonrept_positions_short_all", "nonrept_positions_short"),
            "position_unit": "contracts",
            "scale_applied": 1.0,
        }
        observations.append(
            NormalizedObservation(
                source_id=f"cftc:tff:{code}:{report_date.date().isoformat()}",
                dataset="cftc_tff",
                instrument=code,
                venue=market,
                source_event_time=report_date,
                source_publication_time=None,
                source_available_at=retrieved,
                revision_id=None,
                vintage_id=None,
                data=data,
                quality_flags=("PUBLICATION_TIME_UNKNOWN",),
            )
        )
    if not observations:
        raise ValueError("CFTC TFF returned zero usable rows")
    if max_report_age_days is not None:
        if max_report_age_days < 0:
            raise ValueError("max_report_age_days must be non-negative")
        latest = max(report_dates)
        if current - latest > timedelta(days=max_report_age_days):
            raise ValueError(
                f"CFTC TFF release is stale: latest report {latest.date().isoformat()} exceeds {max_report_age_days} days"
            )
    return observations


class CftcTffAdapter:
    descriptor = ProviderDescriptor(
        provider_id="cftc_tff",
        name="CFTC Traders in Financial Futures",
        domain="positioning",
        role="weekly_futures_positioning_evidence",
        source_class="public_api",
        capabilities=(
            "dealer_positions",
            "asset_manager_positions",
            "leveraged_money_positions",
            "other_reportables",
            "nonreportables",
        ),
        credential_names=(),
        configuration_names=(),
        cadence_class="weekly",
        licensing_policy="public_source_terms",
        raw_retention_policy="public_cache_allowed_no_raw_git",
    )

    def __init__(self, transport: Transport, *, max_report_age_days: int = 14, limit: int = 50000):
        self.transport = transport
        self.max_report_age_days = max_report_age_days
        self.limit = int(limit)

    def collect(self, ctx):
        _, response = request_json(
            self.transport,
            provider_id=self.descriptor.provider_id,
            base_url=CFTC_TFF_URL,
            params=[
                ("$order", "report_date_as_yyyy_mm_dd,cftc_contract_market_code"),
                ("$limit", str(self.limit)),
            ],
        )
        return response_batch(
            response,
            dataset="cftc_tff",
            retrieved_at=ctx.now,
            metadata={"report_kind": "tff"},
        )

    def normalize(self, batch: StoredBatch, ctx):
        return parse_cftc_tff(
            batch.payload,
            retrieved_at=batch.retrieved_at,
            now=ctx.now,
            max_report_age_days=self.max_report_age_days,
        )
