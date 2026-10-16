from copy import deepcopy
from dataclasses import replace
from datetime import datetime
import time
from zoneinfo import ZoneInfo

import pytest

import icarus_engine.a200_runtime_feed as a200_runtime_feed
from icarus_engine.a200_runtime_feed import A200PulseResearchRuntime, qualify_a200_pulse_batch
from icarus_engine.bar_receipts import make_bar_batch_receipt
from icarus_engine.calendar import get_calendar
from icarus_engine.market_universe import snapshot
from icarus_engine.pine.timeframe import Bar


def _qualified_snapshot():
    catalog = deepcopy(snapshot())
    row = catalog["instruments"][0]
    row.update({
        "source_connection": "VERIFIED",
        "identity_status": "VERIFIED",
        "entitlement": "VERIFIED",
        "historical_bars": "QUALIFIED",
        "pulse_enabled": True,
        "strategy_qualified": True,
        "minimum_price_increment": 0.01,
        "point_value": 1.0,
        "share_lot_size": 1,
    })
    yahoo = next(item for item in row["provider_symbol_candidates"] if item["provider"] == "yahoo")
    yahoo["mapping_status"] = "VERIFIED"
    catalog["counts"].update({
        "source_connected_count": 1,
        "entitlement_verified_count": 1,
        "historical_bars_qualified_count": 1,
        "pulse_enabled_count": 1,
        "strategy_qualified_count": 1,
    })
    return catalog, row


def _qualified_batch(row):
    calendar = get_calendar(row["calendar"])
    start = int(datetime(2026, 10, 15, 9, 30, tzinfo=ZoneInfo(row["timezone"])).timestamp())
    end = start + 2 * 300
    expected = calendar.expected_bar_timestamps(start, end, 300)
    bars = [Bar(ts, 100.0 + i, 101.0 + i, 99.0 + i, 100.5 + i, 1000.0 + i)
            for i, ts in enumerate(expected)]
    yahoo = next(item for item in row["provider_symbol_candidates"] if item["provider"] == "yahoo")
    fetched = time.time_ns() - 1_000_000
    received = fetched + 500_000
    checked_bars, receipt = make_bar_batch_receipt(
        instrument_id=row["instrument_id"],
        provider="yahoo",
        expected_provider_symbol=yahoo["symbol"],
        observed_provider_symbol=yahoo["symbol"],
        interval_seconds=300,
        requested_start_ts=start,
        requested_end_ts=end,
        bars=bars,
        fetched_at_ns=fetched,
        received_at_ns=received,
        entitlement_status="VERIFIED",
        session_validation_status="VERIFIED",
        provider_mapping_status="VERIFIED",
        alignment_validator=lambda ts: calendar.is_aligned(ts, 300),
        expected_bar_timestamps=expected,
        calendar_timezone=calendar.timezone_name,
        bar_close_status="VERIFIED",
    )
    return checked_bars, receipt


def test_current_a200_catalog_rows_are_blocked_before_pulse_runner_creation():
    catalog = snapshot()
    row = catalog["instruments"][0]
    timestamp = int(datetime(2026, 10, 15, 9, 30, tzinfo=ZoneInfo("America/New_York")).timestamp())
    bars = [Bar(timestamp, 10, 11, 9, 10, 1)]
    receipt = make_bar_batch_receipt(
        instrument_id=row["instrument_id"], provider="yahoo", expected_provider_symbol="NVDA",
        observed_provider_symbol="NVDA", interval_seconds=60, requested_start_ts=bars[0].ts,
        requested_end_ts=bars[0].ts + 60, bars=bars, fetched_at_ns=time.time_ns(),
        received_at_ns=time.time_ns(), entitlement_status="UNKNOWN",
        provider_mapping_status="UNVERIFIED",
    )[1]

    runtime = A200PulseResearchRuntime()
    result = runtime.ingest_history(row["instrument_id"], bars, receipt)

    assert result["processed_bars"] == 0
    assert result["pulse"] is None
    assert result["execution_authorized"] is False
    assert result["admission"]["admitted"] is False
    assert "PULSE_DISABLED" in result["admission"]["reasons"]
    assert "ENTITLEMENT_NOT_VERIFIED" in result["admission"]["reasons"]
    assert runtime._sessions == {}


def test_qualified_historical_batch_runs_pulse_in_signal_only_research_mode(monkeypatch):
    catalog, row = _qualified_snapshot()
    monkeypatch.setattr(a200_runtime_feed, "snapshot", lambda: catalog)
    bars, receipt = _qualified_batch(row)
    runtime = A200PulseResearchRuntime(chart_minutes=5)

    result = runtime.ingest_history(row["instrument_id"], bars, receipt)

    assert result["admission"]["admitted"] is True
    assert result["processed_bars"] == len(bars)
    assert result["pulse"] is not None
    assert result["bar_index"] == len(bars) - 1
    assert result["research_only"] is True
    assert result["execution_authorized"] is False
    assert result["live_authorized"] is False
    assert result["strategy_command_semantics"].startswith("signal-only")
    runner = runtime._sessions[row["instrument_id"]]["runner"]
    assert runner.em.open == []
    assert runner.em.closed == []
    assert runner.em.fills == []


def test_qualified_catalog_does_not_admit_tampered_bars(monkeypatch):
    catalog, row = _qualified_snapshot()
    monkeypatch.setattr(a200_runtime_feed, "snapshot", lambda: catalog)
    bars, receipt = _qualified_batch(row)
    tampered = [replace(bars[0], c=bars[0].c + 10), *bars[1:]]

    admission = qualify_a200_pulse_batch(row["instrument_id"], tampered, receipt,
                                         now_ns=receipt.received_at_ns)

    assert admission.admitted is False
    assert "BAR_RECEIPT_INVALID_OR_UNQUALIFIED" in admission.reasons


def test_qualified_catalog_rejects_stale_history_receipts(monkeypatch):
    catalog, row = _qualified_snapshot()
    monkeypatch.setattr(a200_runtime_feed, "snapshot", lambda: catalog)
    bars, receipt = _qualified_batch(row)

    admission = qualify_a200_pulse_batch(
        row["instrument_id"], bars, receipt,
        now_ns=receipt.received_at_ns + a200_runtime_feed.MAX_RECEIPT_AGE_NS + 1,
    )

    assert admission.admitted is False
    assert "RECEIPT_STALE" in admission.reasons


def test_portfolio_entrypoint_keeps_a200_research_outside_live_asset_registry(monkeypatch):
    catalog, row = _qualified_snapshot()
    monkeypatch.setattr(a200_runtime_feed, "snapshot", lambda: catalog)
    bars, receipt = _qualified_batch(row)
    from icarus_engine.runtime import Journal, Portfolio

    portfolio = Portfolio(Journal(":memory:"), "/tmp/icarus-a200-runtime-test", feeds={})
    before = dict(portfolio.runners)
    result = portfolio.ingest_a200_research_history(
        row["instrument_id"], bars, receipt,
    )

    assert result["admission"]["admitted"] is True
    assert portfolio.runners == before
    assert portfolio._a200_pulse_research is not None


def test_research_runtime_rejects_missing_bars_between_admitted_batches(monkeypatch):
    catalog, row = _qualified_snapshot()
    monkeypatch.setattr(a200_runtime_feed, "snapshot", lambda: catalog)
    first_bars, first_receipt = _qualified_batch(row)
    runtime = A200PulseResearchRuntime(chart_minutes=5)
    first = runtime.ingest_history(row["instrument_id"], first_bars, first_receipt)
    assert first["admission"]["admitted"] is True

    calendar = get_calendar(row["calendar"])
    gap_start = first_bars[-1].ts + 2 * 300
    gap = [Bar(gap_start, 102, 103, 101, 102.5, 1002)]
    yahoo = next(item for item in row["provider_symbol_candidates"] if item["provider"] == "yahoo")
    fetched = time.time_ns() - 1_000_000
    _, gap_receipt = make_bar_batch_receipt(
        instrument_id=row["instrument_id"], provider="yahoo",
        expected_provider_symbol=yahoo["symbol"], observed_provider_symbol=yahoo["symbol"],
        interval_seconds=300, requested_start_ts=gap_start, requested_end_ts=gap_start + 300,
        bars=gap, fetched_at_ns=fetched, received_at_ns=fetched + 500_000,
        entitlement_status="VERIFIED", session_validation_status="VERIFIED",
        provider_mapping_status="VERIFIED",
        alignment_validator=lambda ts: calendar.is_aligned(ts, 300),
        expected_bar_timestamps=calendar.expected_bar_timestamps(gap_start, gap_start + 300, 300),
        calendar_timezone=calendar.timezone_name, bar_close_status="VERIFIED",
    )

    result = runtime.ingest_history(row["instrument_id"], gap, gap_receipt)

    assert result["admission"]["admitted"] is False
    assert "BATCH_NOT_CONTIGUOUS_WITH_PRIOR_HISTORY" in result["admission"]["reasons"]
    assert result["processed_bars"] == 0


def test_research_runtime_rejects_catalog_economics_change_mid_session(monkeypatch):
    catalog, row = _qualified_snapshot()
    monkeypatch.setattr(a200_runtime_feed, "snapshot", lambda: catalog)
    bars, receipt = _qualified_batch(row)
    runtime = A200PulseResearchRuntime(chart_minutes=5)
    assert runtime.ingest_history(row["instrument_id"], bars, receipt)["admission"]["admitted"] is True

    row["point_value"] = 2.0
    calendar = get_calendar(row["calendar"])
    next_start = bars[-1].ts + 300
    next_bars = [Bar(next_start, 102, 103, 101, 102.5, 1002)]
    yahoo = next(item for item in row["provider_symbol_candidates"] if item["provider"] == "yahoo")
    fetched = time.time_ns() - 1_000_000
    _, next_receipt = make_bar_batch_receipt(
        instrument_id=row["instrument_id"], provider="yahoo",
        expected_provider_symbol=yahoo["symbol"], observed_provider_symbol=yahoo["symbol"],
        interval_seconds=300, requested_start_ts=next_start, requested_end_ts=next_start + 300,
        bars=next_bars, fetched_at_ns=fetched, received_at_ns=fetched + 500_000,
        entitlement_status="VERIFIED", session_validation_status="VERIFIED",
        provider_mapping_status="VERIFIED",
        alignment_validator=lambda ts: calendar.is_aligned(ts, 300),
        expected_bar_timestamps=calendar.expected_bar_timestamps(next_start, next_start + 300, 300),
        calendar_timezone=calendar.timezone_name, bar_close_status="VERIFIED",
    )

    result = runtime.ingest_history(row["instrument_id"], next_bars, next_receipt)

    assert result["admission"]["admitted"] is False
    assert "RESEARCH_SESSION_IDENTITY_OR_QUALIFICATION_CHANGED" in result["admission"]["reasons"]
    assert result["processed_bars"] == 0
