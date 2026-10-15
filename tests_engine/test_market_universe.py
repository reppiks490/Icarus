from copy import deepcopy

import pytest

import icarus_engine.market_universe as market_universe
from icarus_engine.market_universe import snapshot, validate_catalog
from icarus_engine.bar_receipts import make_bar_batch_receipt
from icarus_engine.pine.timeframe import Bar
from tools.build_equity_catalog import _instrument_class
from icarus_engine.market_universe_adapter import MarketUniverseAdapter


def test_catalog_security_type_filter_distinguishes_equity_forms():
    assert _instrument_class("Sample Corp. Common Stock") == ("common_stock", None)
    assert _instrument_class("Foreign Co. Ordinary Shares") == ("ordinary_share", None)
    assert _instrument_class("Issuer American Depositary Shares (each representing two (2) Ordinary Shares)") == ("depositary_receipt", 2)
    assert _instrument_class("Bank Pfd 3 Ordinary Shares") is None
    assert _instrument_class("Acquisition Corp. Unit") is None
    assert _instrument_class("UnitedHealth Group Incorporated Common Stock") == ("common_stock", None)
    assert _instrument_class("United Parcel Service, Inc. Common Stock") == ("common_stock", None)
    assert _instrument_class("United Airlines Holdings Common Stock") == ("common_stock", None)
    assert _instrument_class("United Rentals Common Stock") == ("common_stock", None)
    assert _instrument_class("BHP American Depositary Shares (Each representing two Ordinary Shares)") == ("depositary_receipt", 2)


class _FakeYahooHistory:
    GRANULARITIES = (60, 300, 900, 1800, 3600, 86400)

    def __init__(self, observed_symbol):
        self.observed_symbol = observed_symbol
        self.requested = []

    def candles(self, symbol, interval, start, end):
        self.requested.append((symbol, interval, start, end))
        return [Bar(start, 10, 12, 9, 11, 4)]

    def meta(self, symbol):
        return {"symbol": self.observed_symbol}


def test_a200_yahoo_adapter_resolves_mapping_and_keeps_entitlement_unqualified():
    row = snapshot()["instruments"][0]
    provider_symbol = row["provider_symbol_candidates"][0]["symbol"]
    fake = _FakeYahooHistory(provider_symbol)
    adapter = MarketUniverseAdapter(fake)
    bars, receipt = adapter.fetch_history(row["instrument_id"], 60, 60, 120)
    assert fake.requested == [(provider_symbol, 60, 60, 120)]
    assert len(bars) == receipt.row_count == 1
    assert receipt.provider_symbol_match_status == "MATCHED"
    assert receipt.provider_mapping_status == "UNVERIFIED"
    assert receipt.identity_status == "PROVISIONAL"
    assert receipt.entitlement_status == "UNKNOWN"
    assert receipt.session_validation_status == "UNKNOWN"
    assert receipt.historical_bars_qualified is False


def test_a200_yahoo_adapter_rejects_unknown_id_and_provider_symbol_mismatch():
    adapter = MarketUniverseAdapter(_FakeYahooHistory("wrong"))
    with pytest.raises(ValueError, match="unknown A200 instrument ID"):
        adapter.fetch_history("missing", 60, 60, 120)
    row = snapshot()["instruments"][0]
    with pytest.raises(ValueError, match="symbol mismatch"):
        adapter.fetch_history(row["instrument_id"], 60, 60, 120)


def test_bar_batch_receipt_hashes_rows_but_keeps_unknowns_unqualified():
    bars = [Bar(60, 10, 12, 9, 11, 4), Bar(120, 11, 13, 10, 12, 5)]
    checked, receipt = make_bar_batch_receipt(
        instrument_id="icarus:equity:TEST", provider="test",
        expected_provider_symbol="TEST", observed_provider_symbol=None,
        interval_seconds=60, requested_start_ts=60, requested_end_ts=180,
        bars=bars, fetched_at_ns=1, received_at_ns=2,
    )
    assert checked == bars
    assert receipt.row_count == 2
    assert receipt.checksum_sha256
    assert receipt.identity_status == "UNKNOWN"
    assert receipt.entitlement_status == "UNKNOWN"
    assert receipt.historical_bars_qualified is False
    assert receipt.execution_authorized is False
    assert receipt.session_validation_status == "UNKNOWN"
    assert receipt.interval_gap_count == 0
    assert receipt.timestamp_alignment_status == "VERIFIED"


def test_bar_batch_receipt_rejects_symbol_mismatch_and_bad_ohlcv():
    common = dict(
        instrument_id="icarus:equity:TEST", provider="test",
        expected_provider_symbol="TEST", interval_seconds=60,
        requested_start_ts=60, requested_end_ts=180, fetched_at_ns=1,
        received_at_ns=2,
    )
    with pytest.raises(ValueError, match="symbol mismatch"):
        make_bar_batch_receipt(
            **common, observed_provider_symbol="OTHER",
            bars=[Bar(60, 10, 12, 9, 11, 1)],
        )
    with pytest.raises(ValueError, match="malformed OHLCV"):
        make_bar_batch_receipt(
            **common, observed_provider_symbol="TEST",
            bars=[Bar(60, 10, 8, 9, 11, 1)],
        )


def test_bar_batch_receipt_records_gaps_and_never_qualifies_without_session_review():
    bars = [Bar(60, 10, 12, 9, 11, 4), Bar(240, 11, 13, 10, 12, 5)]
    _, receipt = make_bar_batch_receipt(
        instrument_id="icarus:equity:TEST", provider="test",
        expected_provider_symbol="TEST", observed_provider_symbol="TEST",
        interval_seconds=60, requested_start_ts=60, requested_end_ts=300,
        bars=bars, fetched_at_ns=1, received_at_ns=2,
        entitlement_status="VERIFIED",
        session_validation_status="VERIFIED",
        provider_mapping_status="VERIFIED",
    )
    assert receipt.identity_status == "VERIFIED"
    assert receipt.interval_gap_count == 2
    assert receipt.historical_bars_qualified is False
    with pytest.raises(ValueError, match="integer"):
        make_bar_batch_receipt(
            instrument_id="icarus:equity:TEST", provider="test",
            expected_provider_symbol="TEST", observed_provider_symbol="TEST",
            interval_seconds=60, requested_start_ts=60.5, requested_end_ts=300,
            bars=bars, fetched_at_ns=1, received_at_ns=2,
        )


def test_bar_batch_receipt_gap_blocks_otherwise_qualified_history():
    common = dict(
        instrument_id="icarus:equity:TEST", provider="test",
        expected_provider_symbol="TEST", observed_provider_symbol="TEST",
        interval_seconds=60, requested_start_ts=60, requested_end_ts=300,
        fetched_at_ns=1, received_at_ns=2, entitlement_status="VERIFIED",
        session_validation_status="VERIFIED", provider_mapping_status="VERIFIED",
    )
    _, complete = make_bar_batch_receipt(
        **common, bars=[Bar(60, 10, 12, 9, 11, 4), Bar(120, 11, 13, 10, 12, 5)],
    )
    _, gapped = make_bar_batch_receipt(
        **common, bars=[Bar(60, 10, 12, 9, 11, 4), Bar(240, 11, 13, 10, 12, 5)],
    )
    assert complete.historical_bars_qualified is True
    assert gapped.interval_gap_count == 2
    assert gapped.historical_bars_qualified is False


def test_catalog_contains_two_hundred_unique_disabled_equity_candidates():
    data = snapshot()
    rows = data["instruments"]
    assert len(rows) == 200
    assert len({row["instrument_id"] for row in rows}) == 200
    assert len({(row["venue"], row["display_symbol"]) for row in rows}) == 200
    assert all(row["asset_class"] == "equity" for row in rows)
    assert all(row["source_connection"] == "UNVERIFIED" for row in rows)
    assert all(row["historical_bars"] == "UNVERIFIED" for row in rows)
    assert all(row["live_bars"] == "UNVERIFIED" for row in rows)
    assert all(row["entitlement"] == "UNKNOWN" for row in rows)
    assert all(row["pulse_enabled"] is False for row in rows)
    assert all(row["strategy_qualified"] is False for row in rows)
    assert data["counts"] == {
        "catalogued_count": 200,
        "entitlement_verified_count": 0,
        "source_connected_count": 0,
        "historical_bars_qualified_count": 0,
        "live_bars_qualified_count": 0,
        "pulse_enabled_count": 0,
        "strategy_qualified_count": 0,
    }
    assert data["execution_authorized"] is False
    assert data["production_decision_authorized"] is False


def test_market_universe_counts_verified_entitlements(monkeypatch):
    catalog = market_universe._load()
    catalog["instruments"][0]["entitlement"] = "VERIFIED"
    catalog["counts"]["entitlement_verified_count"] = 1
    monkeypatch.setattr(market_universe, "_load", lambda: catalog)
    assert snapshot()["counts"]["entitlement_verified_count"] == 1


def test_catalog_validation_rejects_duplicate_ids_and_pulse_enablement():
    rows = snapshot()["instruments"]
    base = {
        "schema_version": "icarus.market-universe.catalog.v1",
        "instruments": rows,
        "sources": {"test": {"sha256": "a" * 64}},
        "authority": {"execution_authorized": False, "production_decision_authorized": False},
    }
    duplicate = deepcopy(base)
    duplicate["instruments"][1]["instrument_id"] = duplicate["instruments"][0]["instrument_id"]
    with pytest.raises(ValueError, match="duplicate catalog instrument ID"):
        validate_catalog(duplicate)

    enabled = deepcopy(base)
    enabled["instruments"][0]["pulse_enabled"] = True
    with pytest.raises(ValueError, match="must remain disabled"):
        validate_catalog(enabled)


def test_market_universe_read_api_returns_catalog_without_auth_or_feed_calls(tmp_path):
    import json
    import threading
    import urllib.request

    from icarus_engine.runtime import Journal, Portfolio
    from icarus_engine.server import serve

    portfolio = Portfolio(Journal(":memory:"), str(tmp_path), feeds={})
    server = serve(portfolio, 0, token="catalog-test", start=False)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_address[1]}/api/market-universe"
        with urllib.request.urlopen(url, timeout=5) as response:
            assert response.status == 200
            body = json.loads(response.read())
        assert body["counts"]["catalogued_count"] == 200
        assert body["counts"]["source_connected_count"] == 0
        assert body["execution_authorized"] is False
        assert len(body["instruments"]) == 200
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
