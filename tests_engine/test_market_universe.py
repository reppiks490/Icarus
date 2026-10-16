from copy import deepcopy
import json
from datetime import datetime, timezone

import pytest

import icarus_engine.market_universe as market_universe
from icarus_engine.market_universe import snapshot, validate_catalog
import icarus_engine.market_universe as market_universe
from icarus_engine.bar_receipts import make_bar_batch_receipt
from icarus_engine.pine.timeframe import Bar
from tools.build_equity_catalog import _instrument_class
from icarus_engine.market_universe_adapter import MarketUniverseAdapter
import icarus_engine.market_universe_adapter as market_universe_adapter
import tools.probe_a200_yahoo as yahoo_probe
import tools.probe_a200_hybrid as hybrid_probe
from icarus_engine.calendar import get_calendar
from icarus_engine.assets import parse_spec
from icarus_engine.feeds.databento import Databento
from icarus_engine.feeds.fmp import FmpHistory
from icarus_engine.paper_workspaces import SharedFeed
from icarus_engine.runtime import AssetRunner, Journal, RunnerConfig
from icarus_engine.strategy.inputs import Inputs


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
    assert receipt.bar_close_status == "UNKNOWN"
    assert receipt.timestamp_alignment_status == "UNKNOWN"
    assert receipt.historical_bars_qualified is False


def test_workspace_shared_databento_feed_preserves_provider_and_continuous_identity():
    class FakeDatabento(Databento):
        def __init__(self):
            self.roll_rule = "v"
            self._meta = {}

        def candles(self, _symbol, _interval, start, _end):
            return [Bar(start, 10, 12, 9, 11, 4)]

        def meta(self, symbol):
            return {"provider": "databento", "continuous_symbol": self.continuous_symbol(symbol, self.roll_rule)}

    adapter = FakeDatabento()
    shared = SharedFeed(adapter)
    runner = AssetRunner(
        RunnerConfig(spec=parse_spec("NQ"), inputs=Inputs()),
        Journal(":memory:"), {"yahoo": shared},
    )

    runner._fetch_historical_candles(shared, "NQ=F", 60, 60, 120)
    receipt = runner.last_bar_batch_receipt

    assert receipt["provider"] == "databento"
    assert receipt["expected_provider_symbol"] == "NQ.v.0"
    assert receipt["observed_provider_symbol"] == "NQ.v.0"
    assert receipt["identity_status"] == "VERIFIED"


def test_a200_yahoo_adapter_rejects_unknown_id_and_provider_symbol_mismatch():
    adapter = MarketUniverseAdapter(_FakeYahooHistory("wrong"))
    with pytest.raises(ValueError, match="unknown A200 instrument ID"):
        adapter.fetch_history("missing", 60, 60, 120)
    row = snapshot()["instruments"][0]
    with pytest.raises(ValueError, match="symbol mismatch"):
        adapter.fetch_history(row["instrument_id"], 60, 60, 120)


def test_a200_yahoo_adapter_can_use_a_separately_verified_listing_crosswalk(monkeypatch):
    catalog = snapshot()
    row = catalog["instruments"][0]
    row["provider_symbol_candidates"][0]["mapping_status"] = "VERIFIED"
    monkeypatch.setattr(market_universe_adapter, "snapshot", lambda: catalog)
    symbol = row["provider_symbol_candidates"][0]["symbol"]
    fake = _FakeYahooHistory(symbol)
    _, receipt = MarketUniverseAdapter(fake).fetch_history(row["instrument_id"], 60, 60, 120)
    assert receipt.provider_mapping_status == "VERIFIED"
    assert receipt.provider_symbol_match_status == "MATCHED"
    assert receipt.identity_status == "VERIFIED"
    assert receipt.historical_bars_qualified is False


def test_a200_yahoo_sweep_persists_receipts_without_raw_ohlcv(monkeypatch, tmp_path):
    rows = snapshot()["instruments"]

    class FakeProbeAdapter:
        def __init__(self, _yahoo):
            self.by_id = {row["instrument_id"]: row for row in rows}

        def fetch_history(self, instrument_id, interval_seconds, start_ts, end_ts):
            row = self.by_id[instrument_id]
            symbol = row["provider_symbol_candidates"][0]["symbol"]
            bars = [Bar(start_ts, 10, 12, 9, 11, 4)]
            return make_bar_batch_receipt(
                instrument_id=instrument_id, provider="yahoo",
                expected_provider_symbol=symbol, observed_provider_symbol=symbol,
                interval_seconds=interval_seconds, requested_start_ts=start_ts,
                requested_end_ts=end_ts, bars=bars, fetched_at_ns=1, received_at_ns=2,
                provider_mapping_status="UNVERIFIED",
            )

    monkeypatch.setattr(yahoo_probe, "MarketUniverseAdapter", FakeProbeAdapter)
    out = tmp_path / "probe.json"
    report = yahoo_probe.run(limit=2, start_ts=60, end_ts=86460, out=out,
                             pause_seconds=0, resume=False)
    assert report["completed_count"] == 2
    assert report["counts"]["provider_symbol_match_count"] == 2
    assert report["counts"]["canonical_identity_verified_count"] == 0
    assert report["counts"]["historical_bars_qualified_count"] == 0
    saved = json.loads(out.read_text())
    assert saved["raw_ohlcv_persisted"] is False
    assert all("checksum_sha256" in row and "close" not in row for row in saved["results"])


def test_market_universe_exposes_only_matching_catalog_probe_receipts(monkeypatch, tmp_path):
    catalog = snapshot()
    row = catalog["instruments"][0]
    observed_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    probe_path = tmp_path / "probe.json"
    result = {
        "instrument_id": row["instrument_id"], "provider": "yahoo",
        "provider_symbol_candidate": row["provider_symbol_candidates"][0]["symbol"],
        "provider_mapping_status": row["provider_symbol_candidates"][0]["mapping_status"],
        "probe_started_at": observed_at,
        "probe_status": "RESPONSE_RECEIVED", "provider_symbol_match_status": "MATCHED",
        "canonical_identity_status": "PROVISIONAL", "entitlement_status": "UNKNOWN",
        "historical_bars_qualified": False, "row_count": 10, "close": 10,
    }
    results = [result]
    probe_path.write_text(json.dumps({
        "schema_version": "icarus.market-universe.source-probe.v3",
        "probe_implementation": "tools.probe_a200_yahoo.v3",
        "calendar_schedule_version": "nyse-rth-2026-2028.v1",
        "catalog_id": catalog["catalog_id"],
        "catalog_snapshot_sha256": market_universe.catalog_evidence_digest(catalog),
        "probe_provider": "yahoo",
        "probe_updated_at": observed_at,
        "window": {"start_ts": 60, "end_ts": 86460},
        "completed_count": 1,
        "requested_count": 1,
        "counts": market_universe.source_probe_counts(results),
        "results_sha256": market_universe.source_probe_results_digest(results),
        "raw_ohlcv_persisted": False,
        "results": results,
    }))
    monkeypatch.setattr(market_universe, "PROBE_PATH", probe_path)
    report = market_universe.load_source_probe_report()
    assert report["status"] == "PARTIAL"
    assert report["results"] == [{
        "instrument_id": row["instrument_id"], "probe_status": "RESPONSE_RECEIVED",
        "provider_symbol_match_status": "MATCHED", "canonical_identity_status": "PROVISIONAL",
        "row_count": 10,
    }]


def test_market_universe_uses_oldest_result_age_not_report_rewrite_time(monkeypatch, tmp_path):
    catalog = snapshot()
    row = catalog["instruments"][0]
    mapping = next(candidate for candidate in row["provider_symbol_candidates"]
                   if candidate["provider"] == "yahoo")
    now = datetime.now(timezone.utc)
    current = now.isoformat().replace("+00:00", "Z")
    old = now.replace(year=now.year - 1).isoformat().replace("+00:00", "Z")
    result = {
        "instrument_id": row["instrument_id"], "provider": "yahoo",
        "provider_symbol_candidate": mapping["symbol"],
        "provider_mapping_status": mapping["mapping_status"],
        "probe_started_at": old,
        "probe_status": "RESPONSE_RECEIVED", "provider_symbol_match_status": "MATCHED",
        "canonical_identity_status": "PROVISIONAL", "row_count": 10,
    }
    probe_path = tmp_path / "probe.json"
    probe_path.write_text(json.dumps({
        "schema_version": "icarus.market-universe.source-probe.v3",
        "probe_implementation": "tools.probe_a200_yahoo.v3",
        "calendar_schedule_version": "nyse-rth-2026-2028.v1",
        "catalog_id": catalog["catalog_id"],
        "catalog_snapshot_sha256": market_universe.catalog_evidence_digest(catalog),
        "probe_provider": "yahoo", "probe_updated_at": current,
        "window": {"start_ts": 60, "end_ts": 86460},
        "completed_count": 1, "requested_count": 1,
        "counts": market_universe.source_probe_counts([result]),
        "results_sha256": market_universe.source_probe_results_digest([result]),
        "raw_ohlcv_persisted": False, "results": [result],
    }))
    monkeypatch.setattr(market_universe, "PROBE_PATH", probe_path)

    report = market_universe.load_source_probe_report()

    assert report["status"] == "STALE"
    assert report["age_seconds"] > 86400


def test_market_universe_rejects_future_probe_timestamps(monkeypatch, tmp_path):
    catalog = snapshot()
    now = datetime.now(timezone.utc)
    future = now.replace(year=now.year + 1).isoformat().replace("+00:00", "Z")
    probe_path = tmp_path / "probe.json"
    probe_path.write_text(json.dumps({
        "schema_version": "icarus.market-universe.source-probe.v3",
        "probe_implementation": "tools.probe_a200_yahoo.v3",
        "calendar_schedule_version": "nyse-rth-2026-2028.v1",
        "catalog_id": catalog["catalog_id"],
        "catalog_snapshot_sha256": market_universe.catalog_evidence_digest(catalog),
        "probe_provider": "yahoo", "probe_updated_at": future,
        "window": {"start_ts": 60, "end_ts": 86460},
        "completed_count": 0, "requested_count": 0,
        "counts": market_universe.source_probe_counts([]),
        "results_sha256": market_universe.source_probe_results_digest([]),
        "raw_ohlcv_persisted": False, "results": [],
    }))
    monkeypatch.setattr(market_universe, "PROBE_PATH", probe_path)

    assert market_universe.load_source_probe_report()["status"] == "INVALID"


def test_market_universe_rejects_non_object_probe_ledger(monkeypatch, tmp_path):
    probe_path = tmp_path / "probe.json"
    probe_path.write_text("[]")
    monkeypatch.setattr(market_universe, "PROBE_PATH", probe_path)
    assert market_universe.load_source_probe_report()["status"] == "INVALID"


def test_a200_hybrid_provider_probe_keeps_each_source_receipt_separate():
    class FakeFmpHistory:
        GRANULARITIES = (60, 300, 900, 1800, 3600, 14400, 86400)

        def candles(self, symbol, interval, start, end):
            return [Bar(start, 10, 12, 9, 11, 4)]

        def meta(self, symbol):
            return {"symbol": symbol}

    row = snapshot()["instruments"][0]
    adapter = MarketUniverseAdapter(_FakeYahooHistory("NVDA"), fmp=FakeFmpHistory())
    results = adapter.fetch_hybrid_history(row["instrument_id"], 60, 60, 120)
    assert [result.provider for result in results] == ["yahoo", "fmp"]
    assert all(result.error is None for result in results)
    assert all(result.receipt.provider_symbol_match_status == "MATCHED" for result in results)
    assert all(result.receipt.provider_mapping_status == "UNVERIFIED" for result in results)
    assert all(result.receipt.historical_bars_qualified is False for result in results)
    assert results[0].receipt.checksum_sha256 == results[1].receipt.checksum_sha256


def test_a200_hybrid_report_records_missing_provider_without_raw_bars(monkeypatch, tmp_path):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    row = snapshot()["instruments"][0]
    yahoo_symbol = next(m["symbol"] for m in row["provider_symbol_candidates"] if m["provider"] == "yahoo")
    adapter = MarketUniverseAdapter(_FakeYahooHistory(yahoo_symbol))
    out = tmp_path / "hybrid.json"
    report = hybrid_probe.run(limit=1, start_ts=60, end_ts=86460, out=out,
                              pause_seconds=0, adapter=adapter)
    saved = json.loads(out.read_text())
    by_provider = {item["provider"]: item for item in saved["results"]}
    assert report["completed_result_count"] == 2
    assert by_provider["yahoo"]["probe_status"] == "RESPONSE_RECEIVED"
    assert by_provider["fmp"]["probe_status"] == "NOT_CONFIGURED"
    assert by_provider["fmp"]["error_code"] == "source_not_configured"
    assert saved["raw_ohlcv_persisted"] is False
    assert all("close" not in item for item in saved["results"])


def test_hybrid_probe_ledger_validates_mappings_and_reports_provider_states(monkeypatch, tmp_path):
    catalog = snapshot()
    row = catalog["instruments"][0]
    now_dt = datetime.now(timezone.utc)
    now = now_dt.isoformat().replace("+00:00", "Z")
    results = [
        {"instrument_id": row["instrument_id"], "provider": mapping["provider"],
         "provider_symbol_candidate": mapping["symbol"],
         "provider_mapping_status": mapping["mapping_status"],
         "requested_start_ts": 60, "requested_end_ts": 86460,
         "probe_started_at": now,
         "probe_status": "NOT_CONFIGURED" if mapping["provider"] == "fmp" else "NO_BARS"}
        for mapping in row["provider_symbol_candidates"]
    ]
    counts = {}
    for result in results:
        key = f"{result['provider']}_{result['probe_status'].lower()}_count"
        counts[key] = counts.get(key, 0) + 1
    path = tmp_path / "hybrid.json"
    path.write_text(json.dumps({
        "schema_version": "icarus.market-universe.hybrid-probe.v1",
        "probe_implementation": "tools.probe_a200_hybrid.v1",
        "catalog_id": catalog["catalog_id"],
        "catalog_snapshot_sha256": market_universe.catalog_evidence_digest(catalog),
        "probe_updated_at": now, "requested_instrument_count": 1,
        "window": {"start_ts": 60, "end_ts": 86460},
        "completed_result_count": len(results), "counts": counts,
        "results_sha256": market_universe.source_probe_results_digest(results),
        "raw_ohlcv_persisted": False, "results": results,
    }))
    monkeypatch.setattr(market_universe, "HYBRID_PROBE_PATH", path)
    report = market_universe.load_hybrid_probe_report()
    assert report["status"] == "PARTIAL"
    assert {result["provider"] for result in report["results"]} == {"yahoo", "fmp"}
    assert report["authority"]["pulse_enabled"] is False

    tampered_window = json.loads(path.read_text())
    tampered_window["window"] = {"start_ts": 120, "end_ts": 86400}
    path.write_text(json.dumps(tampered_window))
    assert market_universe.load_hybrid_probe_report()["status"] == "INVALID"

    tampered = json.loads(path.read_text())
    tampered["window"] = {"start_ts": 60, "end_ts": 86460}
    old = now_dt.replace(year=now_dt.year - 1).isoformat().replace("+00:00", "Z")
    tampered["results"][0]["probe_status"] = "ERROR"
    tampered["results"][0]["probe_started_at"] = old
    tampered["counts"] = {}
    for result in tampered["results"]:
        key = f"{result['provider']}_{result['probe_status'].lower()}_count"
        tampered["counts"][key] = tampered["counts"].get(key, 0) + 1
    tampered["results_sha256"] = market_universe.source_probe_results_digest(tampered["results"])
    path.write_text(json.dumps(tampered))
    assert market_universe.load_hybrid_probe_report()["status"] == "STALE"


def test_hybrid_cli_defaults_to_non_runtime_report_path(monkeypatch):
    captured = {}

    def fake_run(**kwargs):
        captured.update(kwargs)
        return {"completed_result_count": 0, "counts": {}}

    monkeypatch.setattr(hybrid_probe, "run", fake_run)
    monkeypatch.setattr("sys.argv", ["probe_a200_hybrid"])
    assert hybrid_probe.main() == 0
    assert captured["out"] == hybrid_probe.DEFAULT_OUT
    assert captured["out"] != market_universe.HYBRID_PROBE_PATH


def test_hybrid_adapter_sanitizes_provider_exception_text():
    class LeakyFailure(_FakeYahooHistory):
        def candles(self, symbol, interval, start, end):
            raise RuntimeError("https://provider.invalid/?apikey=secret-value")

    row = snapshot()["instruments"][0]
    result = MarketUniverseAdapter(LeakyFailure("unused")).fetch_hybrid_history(
        row["instrument_id"], 60, 60, 120,
    )[0]
    assert result.error == "provider_error:RuntimeError"
    assert "secret-value" not in result.error


def test_fmp_history_connector_uses_external_key_and_parses_exchange_timestamps(monkeypatch):
    monkeypatch.delenv("FMP_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="FMP_API_KEY"):
        FmpHistory()

    feed = FmpHistory(api_key="test-secret")
    requests = []

    def fake_get(path, params):
        requests.append((path, params))
        if path == "profile":
            return [{"symbol": params["symbol"], "exchangeShortName": "NASDAQ"}]
        return [{"date": "2026-10-15 09:30:00", "open": 10, "high": 12,
                 "low": 9, "close": 11, "volume": 4}]

    monkeypatch.setattr(feed, "_get", fake_get)
    start = int(datetime(2026, 10, 15, 13, 30, tzinfo=timezone.utc).timestamp())
    bars = feed.candles("NVDA", 60, start, start + 3600)
    assert bars == [Bar(start, 10, 12, 9, 11, 4)]
    assert requests[0] == ("historical-chart/1min", {
        "symbol": "NVDA", "from": "2026-10-15", "to": "2026-10-15",
    })
    assert feed.meta("NVDA")["exchangeShortName"] == "NASDAQ"
    assert "test-secret" not in repr(requests)


def test_fmp_daily_bars_use_exchange_open_anchor_without_qualifying_receipt(monkeypatch):
    feed = FmpHistory(api_key="test-secret")
    monkeypatch.setattr(feed, "_get", lambda path, params: [
        {"date": "2026-10-15", "open": 10, "high": 12,
         "low": 9, "close": 11, "volume": 4}
    ])
    start = int(datetime(2026, 10, 15, 13, 30, tzinfo=timezone.utc).timestamp())
    bars = feed.candles("NVDA", 86400, start, start + 86400)
    assert bars == [Bar(start, 10, 12, 9, 11, 4)]


def test_bar_batch_receipt_hashes_rows_but_keeps_unknowns_unqualified():
    bars = [Bar(60, 10, 12, 9, 11, 4), Bar(120, 11, 13, 10, 12, 5)]
    checked, receipt = make_bar_batch_receipt(
        instrument_id="icarus:equity:TEST", provider="test",
        expected_provider_symbol="TEST", observed_provider_symbol=None,
        interval_seconds=60, requested_start_ts=60, requested_end_ts=180,
        bars=bars, fetched_at_ns=1, received_at_ns=2,
        alignment_validator=lambda ts: ts % 60 == 0,
        bar_close_status="VERIFIED",
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
    assert receipt.gap_validation_status == "UNKNOWN"
    assert receipt.timestamp_alignment_status == "VERIFIED"
    assert receipt.bar_close_status == "VERIFIED"


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


def test_bar_batch_receipt_uses_explicit_market_session_alignment():
    bars = [Bar(1800, 10, 12, 9, 11, 4), Bar(5400, 11, 13, 10, 12, 5)]
    _, receipt = make_bar_batch_receipt(
        instrument_id="icarus:equity:TEST", provider="test",
        expected_provider_symbol="TEST", observed_provider_symbol="TEST",
        interval_seconds=3600, requested_start_ts=1800, requested_end_ts=9000,
        bars=bars, fetched_at_ns=1, received_at_ns=2,
        alignment_validator=lambda ts: (ts - 1800) % 3600 == 0,
    )
    assert receipt.timestamp_alignment_status == "VERIFIED"
    assert receipt.historical_bars_qualified is False


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
    _, fully_attested_gap_receipt = make_bar_batch_receipt(
        instrument_id="icarus:equity:TEST", provider="test",
        expected_provider_symbol="TEST", observed_provider_symbol="TEST",
        interval_seconds=60, requested_start_ts=60, requested_end_ts=300,
        bars=bars, fetched_at_ns=1, received_at_ns=2,
        entitlement_status="VERIFIED", session_validation_status="VERIFIED",
        provider_mapping_status="VERIFIED", alignment_validator=lambda ts: ts % 60 == 0,
        bar_close_status="VERIFIED",
    )
    assert fully_attested_gap_receipt.identity_status == "VERIFIED"
    assert fully_attested_gap_receipt.timestamp_alignment_status == "VERIFIED"
    assert fully_attested_gap_receipt.gap_validation_status == "UNKNOWN"
    assert fully_attested_gap_receipt.historical_bars_qualified is False
    with pytest.raises(ValueError, match="integer"):
        make_bar_batch_receipt(
            instrument_id="icarus:equity:TEST", provider="test",
            expected_provider_symbol="TEST", observed_provider_symbol="TEST",
            interval_seconds=60, requested_start_ts=60.5, requested_end_ts=300,
            bars=bars, fetched_at_ns=1, received_at_ns=2,
        )


def test_bar_batch_receipt_requires_full_expected_session_schedule_to_qualify():
    common = dict(
        instrument_id="icarus:equity:TEST", provider="test",
        expected_provider_symbol="TEST", observed_provider_symbol="TEST",
        interval_seconds=60, requested_start_ts=60, requested_end_ts=300,
        fetched_at_ns=1, received_at_ns=2,
        entitlement_status="VERIFIED", session_validation_status="VERIFIED",
        provider_mapping_status="VERIFIED", alignment_validator=lambda ts: ts % 60 == 0,
        bar_close_status="VERIFIED",
    )
    bars_with_gap = [Bar(60, 10, 12, 9, 11, 4), Bar(240, 11, 13, 10, 12, 5)]
    _, unknown_gap_receipt = make_bar_batch_receipt(
        **common, bars=bars_with_gap,
    )
    assert unknown_gap_receipt.interval_gap_count == 2
    assert unknown_gap_receipt.gap_validation_status == "UNKNOWN"
    assert not unknown_gap_receipt.historical_bars_qualified

    _, verified_gap_receipt = make_bar_batch_receipt(
        **common, bars=bars_with_gap,
        expected_bar_timestamps=[60, 120, 180, 240],
    )
    assert verified_gap_receipt.interval_gap_count == 2
    assert verified_gap_receipt.gap_validation_status == "VERIFIED"
    assert not verified_gap_receipt.historical_bars_qualified

    bars_without_gap = [Bar(60, 10, 12, 9, 11, 4), Bar(120, 11, 13, 10, 12, 5)]
    _, complete_receipt = make_bar_batch_receipt(
        **common, bars=bars_without_gap,
        expected_bar_timestamps=[60, 120],
    )
    assert complete_receipt.interval_gap_count == 0
    assert complete_receipt.gap_validation_status == "VERIFIED"
    assert complete_receipt.historical_bars_qualified


def test_one_bar_cannot_qualify_a_sparse_long_window():
    _, receipt = make_bar_batch_receipt(
        instrument_id="icarus:equity:TEST", provider="test",
        expected_provider_symbol="TEST", observed_provider_symbol="TEST",
        interval_seconds=60, requested_start_ts=60, requested_end_ts=360,
        bars=[Bar(60, 10, 12, 9, 11, 4)], fetched_at_ns=1, received_at_ns=2,
        entitlement_status="VERIFIED", session_validation_status="VERIFIED",
        provider_mapping_status="VERIFIED", alignment_validator=lambda ts: ts % 60 == 0,
        expected_bar_timestamps=[60, 120, 180, 240, 300], bar_close_status="VERIFIED",
    )
    assert receipt.row_count == 1
    assert receipt.expected_bar_count == 5
    assert receipt.interval_gap_count == 4
    assert receipt.gap_validation_status == "VERIFIED"
    assert not receipt.historical_bars_qualified


def test_receipt_identity_includes_qualification_evidence():
    args = dict(
        instrument_id="icarus:equity:TEST", provider="test",
        expected_provider_symbol="TEST", observed_provider_symbol="TEST",
        interval_seconds=60, requested_start_ts=60, requested_end_ts=120,
        bars=[Bar(60, 10, 12, 9, 11, 4)], fetched_at_ns=1, received_at_ns=2,
    )
    _, unverified = make_bar_batch_receipt(**args)
    _, entitlement_verified = make_bar_batch_receipt(**args, entitlement_status="VERIFIED")
    assert unverified.checksum_sha256 == entitlement_verified.checksum_sha256
    assert unverified.receipt_id != entitlement_verified.receipt_id


def test_expected_schedule_rejects_unsorted_or_unexpected_bars():
    args = dict(
        instrument_id="icarus:equity:TEST", provider="test",
        expected_provider_symbol="TEST", observed_provider_symbol="TEST",
        interval_seconds=60, requested_start_ts=60, requested_end_ts=240,
        bars=[Bar(120, 10, 12, 9, 11, 4)], fetched_at_ns=1, received_at_ns=2,
    )
    with pytest.raises(ValueError, match="strictly increasing and unique"):
        make_bar_batch_receipt(**args, expected_bar_timestamps=[120, 60])
    with pytest.raises(ValueError, match="expected market-session schedule"):
        make_bar_batch_receipt(**args, expected_bar_timestamps=[60, 180])


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
    assert all({c["provider"] for c in row["provider_symbol_candidates"]} == {"yahoo", "fmp"} for row in rows)
    assert data["counts"] == {
        "catalogued_count": 200,
        "source_connected_count": 0,
        "entitlement_verified_count": 0,
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

    undersized = deepcopy(base)
    undersized["instruments"] = undersized["instruments"][:-1]
    with pytest.raises(ValueError, match="exactly 200"):
        validate_catalog(undersized)


def test_us_equity_calendar_uses_bounded_exchange_schedule():
    calendar = get_calendar("US_EQUITIES")
    assert calendar.open_24_7 is False
    thanksgiving = datetime(2026, 11, 27, 14, 30, tzinfo=timezone.utc).timestamp()
    assert calendar.is_open(int(thanksgiving))
    assert calendar.bucket_end(calendar.bucket_start(int(thanksgiving), 1440), 1440) == int(
        datetime(2026, 11, 27, 18, 0, tzinfo=timezone.utc).timestamp()
    )
    with pytest.raises(ValueError, match="no verified schedule"):
        calendar.session_bounds(datetime(2029, 1, 2).date())
    assert get_calendar("crypto").open_24_7 is True


def test_a200_adapter_accepts_verified_mapping_but_keeps_missing_gates_unqualified(monkeypatch):
    import icarus_engine.market_universe_adapter as adapter_module

    catalog = snapshot()
    catalog["instruments"][0]["provider_symbol_candidates"][0]["mapping_status"] = "VERIFIED"
    monkeypatch.setattr(adapter_module, "snapshot", lambda: catalog)
    row = catalog["instruments"][0]
    provider_symbol = row["provider_symbol_candidates"][0]["symbol"]
    adapter = MarketUniverseAdapter(_FakeYahooHistory(provider_symbol))

    bars, receipt = adapter.fetch_history(row["instrument_id"], 60, 60, 120)
    assert len(bars) == 1
    assert receipt.provider_mapping_status == "VERIFIED"
    assert receipt.identity_status == "VERIFIED"
    assert receipt.entitlement_status == "UNKNOWN"
    assert receipt.session_validation_status == "UNKNOWN"
    assert receipt.bar_close_status == "UNKNOWN"
    assert receipt.historical_bars_qualified is False


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
