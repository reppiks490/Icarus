from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from icarus_engine.external_data.pipeline import IngestPipeline
from icarus_engine.external_data.providers.cftc import CftcTffAdapter, parse_cftc_tff
from icarus_engine.external_data.providers.eia import EiaAdapter, parse_eia
from icarus_engine.external_data.providers.fred_alfred import (
    FredAlfredAdapter,
    parse_fred_observations,
)
from icarus_engine.external_data.providers.nyfed import NyFedAdapter, parse_nyfed
from icarus_engine.external_data.providers.treasury import TreasuryAdapter, parse_treasury
from icarus_engine.external_data.registry import ProviderRegistry
from icarus_engine.external_data.storage import EvidenceCatalog, RawArtifactStore
from icarus_engine.external_data.transport import FakeTransport, HttpResponse


UTC = timezone.utc
NOW = datetime(2026, 10, 6, 18, 0, tzinfo=UTC)
FIXTURES = Path(__file__).parent / "fixtures" / "external_data"


def _fixture(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def test_public_macro_descriptors_match_static_registry_contract():
    assert NyFedAdapter.descriptor.provider_id == "ny_fed"
    assert TreasuryAdapter.descriptor.provider_id == "us_treasury"
    assert CftcTffAdapter.descriptor.provider_id == "cftc_tff"
    assert EiaAdapter.descriptor.provider_id == "eia"
    assert FredAlfredAdapter.descriptor.provider_id == "fred_alfred"
    assert NyFedAdapter.descriptor.credential_names == ()
    assert TreasuryAdapter.descriptor.credential_names == ()
    assert CftcTffAdapter.descriptor.credential_names == ()
    assert EiaAdapter.descriptor.credential_names == ("EIA_API_KEY",)
    assert FredAlfredAdapter.descriptor.credential_names == ("FRED_API_KEY",)
    assert all(
        descriptor.direct_execution_authority is False
        for descriptor in (
            NyFedAdapter.descriptor,
            TreasuryAdapter.descriptor,
            CftcTffAdapter.descriptor,
            EiaAdapter.descriptor,
            FredAlfredAdapter.descriptor,
        )
    )


def test_nyfed_sofr_effr_and_repo_preserve_rate_and_quantity_units():
    observations = parse_nyfed(_fixture("nyfed_rates.json"), retrieved_at=NOW, now=NOW)
    by_kind = {item.data["kind"]: item for item in observations}

    assert by_kind["SOFR"].data["rate_percent"] == pytest.approx(4.83)
    assert by_kind["SOFR"].data["rate_unit"] == "percent"
    assert by_kind["SOFR"].data["volume_billions_usd"] == pytest.approx(2150.0)
    assert by_kind["SOFR"].source_event_time == datetime(2026, 10, 5, tzinfo=UTC)
    assert by_kind["SOFR"].source_publication_time is None
    assert by_kind["SOFR"].source_available_at == NOW
    assert "PUBLICATION_TIME_UNKNOWN" in by_kind["SOFR"].quality_flags

    rrp = by_kind["RRP"]
    assert rrp.data["amount_billions_usd"] == pytest.approx(312.5)
    assert rrp.data["amount_unit"] == "billion USD"
    assert rrp.data["award_rate_percent"] == pytest.approx(4.80)


def test_nyfed_stale_and_changed_schema_fail_closed():
    with pytest.raises(ValueError, match="stale"):
        parse_nyfed(
            _fixture("nyfed_rates.json"),
            retrieved_at=datetime(2026, 10, 20, tzinfo=UTC),
            now=datetime(2026, 10, 20, tzinfo=UTC),
            max_event_age_days=7,
        )
    with pytest.raises(ValueError):
        parse_nyfed(b'{"unexpected":[]}', retrieved_at=NOW, now=NOW)


def test_treasury_auction_preserves_announcement_availability_and_native_units():
    observations = parse_treasury(_fixture("treasury_auctions.json"), dataset="auctions", retrieved_at=NOW)
    assert len(observations) == 1
    item = observations[0]
    assert item.source_event_time == datetime(2026, 10, 5, tzinfo=UTC)
    assert item.source_publication_time == datetime(2026, 10, 1, tzinfo=UTC)
    assert item.source_available_at == datetime(2026, 10, 1, tzinfo=UTC)
    assert item.data["cusip"] == "912797ZZ9"
    assert item.data["offering_amount"] == 69_000_000_000
    assert item.data["offering_amount_unit"] == "USD"
    assert item.data["bid_to_cover_ratio"] == pytest.approx(2.54)
    assert item.data["bid_to_cover_unit"] == "ratio"
    assert item.data["high_investment_rate_percent"] == pytest.approx(4.125)
    assert item.data["rate_unit"] == "percent"


def test_treasury_missing_identity_and_schema_change_fail_closed():
    with pytest.raises(ValueError):
        parse_treasury(b'{"data":[{"auction_date":"2026-10-05"}]}', dataset="auctions", retrieved_at=NOW)
    with pytest.raises(ValueError):
        parse_treasury(b'{"records":[]}', dataset="auctions", retrieved_at=NOW)


def test_cftc_tff_preserves_contract_counts_and_does_not_invent_publication_time():
    observations = parse_cftc_tff(_fixture("cftc_tff.json"), retrieved_at=NOW, now=NOW)
    assert len(observations) == 1
    item = observations[0]
    assert item.source_event_time == datetime(2026, 9, 29, tzinfo=UTC)
    assert item.source_publication_time is None
    assert item.source_available_at == NOW
    assert item.data["open_interest_contracts"] == 355123
    assert item.data["dealer_long_contracts"] == 52110
    assert item.data["asset_manager_long_contracts"] == 125500
    assert item.data["leveraged_money_short_contracts"] == 105440
    assert item.data["position_unit"] == "contracts"
    assert "PUBLICATION_TIME_UNKNOWN" in item.quality_flags


def test_cftc_stale_or_missing_contract_identity_fails_closed():
    with pytest.raises(ValueError, match="stale"):
        parse_cftc_tff(
            _fixture("cftc_tff.json"),
            retrieved_at=datetime(2026, 10, 30, tzinfo=UTC),
            now=datetime(2026, 10, 30, tzinfo=UTC),
            max_report_age_days=14,
        )
    with pytest.raises(ValueError):
        parse_cftc_tff(
            b'[{"report_date_as_yyyy_mm_dd":"2026-09-29","open_interest_all":"1"}]',
            retrieved_at=NOW,
            now=NOW,
        )


def test_eia_values_keep_provider_units_without_silent_rescaling():
    observations = parse_eia(_fixture("eia_series.json"), retrieved_at=NOW)
    assert len(observations) == 2
    latest = observations[-1]
    assert latest.source_event_time == datetime(2026, 9, 1, tzinfo=UTC)
    assert latest.source_publication_time is None
    assert latest.source_available_at == NOW
    assert latest.data["value"] == pytest.approx(418.2)
    assert latest.data["unit"] == "million barrels"
    assert latest.data["frequency"] == "monthly"
    assert latest.data["scale_applied"] == 1.0


def test_eia_missing_unit_or_changed_response_shape_fails_closed():
    with pytest.raises(ValueError):
        parse_eia(b'{"response":{"frequency":"monthly","data":[{"period":"2026-09","value":"1"}]}}', retrieved_at=NOW)
    with pytest.raises(ValueError):
        parse_eia(b'{"data":[]}', retrieved_at=NOW)


def test_fred_alfred_vintages_are_revision_sensitive_and_point_in_time():
    observations = parse_fred_observations(
        _fixture("fred_alfred_observations.json"),
        series_id="CPIAUCSL",
        retrieved_at=NOW,
    )
    july = [item for item in observations if item.source_event_time == datetime(2026, 7, 1, tzinfo=UTC)]
    assert [item.data["value"] for item in july] == [3.0, 3.2]
    assert [item.vintage_id for item in july] == ["2026-08-01", "2026-09-01"]
    assert july[0].source_available_at == datetime(2026, 8, 1, tzinfo=UTC)
    assert july[1].source_available_at == datetime(2026, 9, 1, tzinfo=UTC)
    assert july[0].source_publication_time == datetime(2026, 8, 1, tzinfo=UTC)
    assert july[0].data["unit_code"] == "lin"


def test_alfred_future_revision_is_not_visible_in_historical_asof_query(tmp_path):
    observations = parse_fred_observations(
        _fixture("fred_alfred_observations.json"),
        series_id="CPIAUCSL",
        retrieved_at=NOW,
    )
    catalog = EvidenceCatalog(tmp_path / "catalog.sqlite3")
    for item in observations:
        envelope = item.to_envelope(
            provider_id="fred_alfred",
            raw_artifact_sha256="a" * 64,
            retrieved_at=NOW,
            ingested_at=NOW,
            ingest_batch_id="batch-fixture",
        )
        catalog.upsert(envelope)

    august_view = catalog.query_as_of(
        datetime(2026, 8, 15, tzinfo=UTC),
        provider_id="fred_alfred",
        source_id="fred:CPIAUCSL:2026-07-01",
    )
    september_view = catalog.query_as_of(
        datetime(2026, 9, 15, tzinfo=UTC),
        provider_id="fred_alfred",
        source_id="fred:CPIAUCSL:2026-07-01",
    )

    assert [item.data["value"] for item in august_view] == [3.0]
    assert [item.data["value"] for item in september_view] == [3.2]


def test_fred_missing_required_fields_and_non_numeric_value_fail_closed():
    with pytest.raises(ValueError):
        parse_fred_observations(b'{"observations":[{"date":"2026-07-01","value":"3.0"}]}', series_id="CPI", retrieved_at=NOW)
    with pytest.raises(ValueError):
        parse_fred_observations(b'{"units":"lin","observations":[{"realtime_start":"2026-08-01","realtime_end":"2026-08-31","date":"2026-07-01","value":"oops"}]}', series_id="CPI", retrieved_at=NOW)


def test_fred_adapter_uses_shared_transport_and_pipeline_with_secret_env(tmp_path):
    payload = _fixture("fred_alfred_observations.json")
    transport = FakeTransport([
        HttpResponse(status=200, body=payload, url="https://api.stlouisfed.org/fred/series/observations")
    ])
    adapter = FredAlfredAdapter(transport, series_ids=("CPIAUCSL",), as_of="2026-09-15")
    registry = ProviderRegistry()
    registry.register(adapter)
    catalog = EvidenceCatalog(tmp_path / "external" / "catalog.sqlite3")
    pipeline = IngestPipeline(
        registry,
        RawArtifactStore(tmp_path / "external"),
        catalog,
        environment={"FRED_API_KEY":"SENTINEL-FRED-KEY"},
    )

    receipt = pipeline.run_provider("fred_alfred", NOW)

    assert receipt.state == "OK"
    assert len(transport.calls) == 1
    request = transport.calls[0]
    assert request.provider_id == "fred_alfred"
    assert "realtime_start=2026-09-15" in request.url
    assert "realtime_end=2026-09-15" in request.url
    assert "SENTINEL-FRED-KEY" not in repr(request)
    stored = catalog.query_as_of(datetime(2026, 9, 15, tzinfo=UTC), provider_id="fred_alfred")
    assert stored


def test_eia_adapter_uses_shared_transport_and_requires_configured_key(tmp_path):
    payload = _fixture("eia_series.json")
    transport = FakeTransport([
        HttpResponse(status=200, body=payload, url="https://api.eia.gov/v2/petroleum/stoc/wstk/data/")
    ])
    adapter = EiaAdapter(
        transport,
        route="petroleum/stoc/wstk",
        data_fields=("value",),
        frequency="monthly",
    )
    registry = ProviderRegistry()
    registry.register(adapter)
    catalog = EvidenceCatalog(tmp_path / "external" / "catalog.sqlite3")
    pipeline = IngestPipeline(
        registry,
        RawArtifactStore(tmp_path / "external"),
        catalog,
        environment={"EIA_API_KEY":"SENTINEL-EIA-KEY"},
    )

    receipt = pipeline.run_provider("eia", NOW)

    assert receipt.state == "OK"
    assert len(transport.calls) == 1
    assert "SENTINEL-EIA-KEY" not in repr(transport.calls[0])
