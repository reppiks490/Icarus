from __future__ import annotations

from datetime import datetime
from typing import Any

from ..contracts import ProviderDescriptor
from ..identity import normalize_utc
from ..normalization import NormalizedObservation, StoredBatch
from ..transport import Transport
from ._public_macro import decode_json, number, request_json, require_text, response_batch, utc_day


BASE = "https://api.fiscaldata.treasury.gov/services/api/fiscal_service"
TREASURY_ENDPOINTS = {
    "auctions": "/v1/accounting/od/auctions_query",
    "debt": "/v2/accounting/od/debt_to_penny",
    "rates": "/v2/accounting/od/avg_interest_rates",
}


def parse_treasury(
    payload: bytes,
    *,
    dataset: str,
    retrieved_at: datetime | str,
) -> list[NormalizedObservation]:
    root = decode_json(payload)
    if not isinstance(root, dict) or "data" not in root:
        raise ValueError("Treasury schema changed: expected data array")
    rows = root.get("data")
    if not isinstance(rows, list):
        raise ValueError("Treasury data must be an array")
    retrieved = normalize_utc(retrieved_at)
    if retrieved is None:
        raise ValueError("retrieved_at is required")
    if dataset not in TREASURY_ENDPOINTS:
        raise ValueError(f"unsupported Treasury dataset {dataset!r}")

    observations: list[NormalizedObservation] = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError("Treasury row must be an object")
        if dataset == "auctions":
            cusip = require_text(row.get("cusip"), field="cusip")
            auction_date = utc_day(row.get("auction_date"), field="auction_date")
            announcement_date = utc_day(row.get("announcement_date"), field="announcement_date")
            data: dict[str, Any] = {
                "kind": "auction",
                "cusip": cusip,
                "security_type": require_text(row.get("security_type"), field="security_type"),
                "security_term": require_text(row.get("security_term"), field="security_term"),
                "offering_amount": int(number(row.get("offering_amt"), field="offering_amt")),
                "offering_amount_unit": "USD",
                "bid_to_cover_ratio": number(row.get("bid_to_cover_ratio"), field="bid_to_cover_ratio"),
                "bid_to_cover_unit": "ratio",
                "high_investment_rate_percent": number(
                    row.get("high_investment_rate"), field="high_investment_rate"
                ),
                "rate_unit": "percent",
                "announcement_date": announcement_date.date().isoformat(),
                "issue_date": utc_day(row.get("issue_date"), field="issue_date").date().isoformat(),
                "maturity_date": utc_day(row.get("maturity_date"), field="maturity_date").date().isoformat(),
            }
            observations.append(
                NormalizedObservation(
                    source_id=f"treasury:auction:{cusip}:{auction_date.date().isoformat()}",
                    dataset="treasury_auctions",
                    instrument=cusip,
                    venue="U.S. Treasury",
                    source_event_time=auction_date,
                    source_publication_time=announcement_date,
                    source_available_at=announcement_date,
                    revision_id=str(row.get("record_date") or announcement_date.date().isoformat()),
                    vintage_id=None,
                    data=data,
                )
            )
            continue

        record_date = utc_day(row.get("record_date"), field="record_date")
        if dataset == "debt":
            total = number(row.get("tot_pub_debt_out_amt"), field="tot_pub_debt_out_amt")
            held = number(row.get("debt_held_public_amt"), field="debt_held_public_amt")
            data = {
                "kind": "debt",
                "total_public_debt_outstanding": total,
                "debt_held_by_public": held,
                "amount_unit": "USD",
                "scale_applied": 1.0,
            }
            source_id = f"treasury:debt:{record_date.date().isoformat()}"
            instrument = "US_PUBLIC_DEBT"
        else:
            security = require_text(
                row.get("security_desc") or row.get("security_type_desc"),
                field="security_desc",
            )
            rate = number(row.get("avg_interest_rate_amt"), field="avg_interest_rate_amt")
            data = {
                "kind": "average_interest_rate",
                "security_description": security,
                "rate_percent": rate,
                "rate_unit": "percent",
                "scale_applied": 1.0,
            }
            source_id = f"treasury:rates:{security}:{record_date.date().isoformat()}"
            instrument = security
        observations.append(
            NormalizedObservation(
                source_id=source_id,
                dataset=f"treasury_{dataset}",
                instrument=instrument,
                venue="U.S. Treasury",
                source_event_time=record_date,
                source_publication_time=None,
                source_available_at=retrieved,
                revision_id=str(row.get("record_date") or record_date.date().isoformat()),
                vintage_id=None,
                data=data,
                quality_flags=("PUBLICATION_TIME_UNKNOWN",),
            )
        )
    if not observations:
        raise ValueError(f"Treasury {dataset} returned zero usable rows")
    return observations


class TreasuryAdapter:
    descriptor = ProviderDescriptor(
        provider_id="us_treasury",
        name="U.S. Treasury Fiscal Data",
        domain="public_macro",
        role="auction_supply_rates_and_fiscal_evidence",
        source_class="public_api",
        capabilities=("auctions", "issuance", "debt", "rates", "fiscal_data"),
        credential_names=(),
        configuration_names=(),
        cadence_class="daily",
        licensing_policy="public_source_terms",
        raw_retention_policy="public_cache_allowed_no_raw_git",
    )

    def __init__(self, transport: Transport, datasets=("auctions", "debt", "rates")):
        self.transport = transport
        self.datasets = tuple(datasets)
        unknown = set(self.datasets) - set(TREASURY_ENDPOINTS)
        if unknown:
            raise ValueError(f"unsupported Treasury datasets: {sorted(unknown)}")

    def collect(self, ctx):
        batches = []
        for dataset in self.datasets:
            _, response = request_json(
                self.transport,
                provider_id=self.descriptor.provider_id,
                base_url=BASE + TREASURY_ENDPOINTS[dataset],
                params=[("sort", "auction_date" if dataset == "auctions" else "record_date"), ("page[size]", "10000")],
            )
            batches.append(
                response_batch(
                    response,
                    dataset=f"treasury_{dataset}",
                    retrieved_at=ctx.now,
                    metadata={"treasury_dataset": dataset},
                )
            )
        return batches

    def normalize(self, batch: StoredBatch, ctx):
        dataset = str(batch.metadata.get("treasury_dataset") or batch.dataset.removeprefix("treasury_"))
        return parse_treasury(batch.payload, dataset=dataset, retrieved_at=batch.retrieved_at)
