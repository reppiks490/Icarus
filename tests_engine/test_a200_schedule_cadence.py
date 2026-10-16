from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from icarus_engine.bar_receipts import make_bar_batch_receipt
from icarus_engine.calendar import get_calendar
from icarus_engine.market_universe import snapshot
from icarus_engine.market_universe_adapter import MarketUniverseAdapter
from icarus_engine.pine.timeframe import Bar


def _qualified_receipt(interval_seconds, timestamps, calendar_timezone=None):
    return make_bar_batch_receipt(
        instrument_id="icarus:equity:TEST",
        provider="test",
        expected_provider_symbol="TEST",
        observed_provider_symbol="TEST",
        interval_seconds=interval_seconds,
        requested_start_ts=timestamps[0],
        requested_end_ts=timestamps[-1] + interval_seconds,
        bars=[Bar(ts, 10, 12, 9, 11, 1) for ts in timestamps],
        fetched_at_ns=1,
        received_at_ns=2,
        entitlement_status="VERIFIED",
        session_validation_status="VERIFIED",
        provider_mapping_status="VERIFIED",
        alignment_validator=lambda _ts: True,
        expected_bar_timestamps=timestamps,
        calendar_timezone=calendar_timezone,
        bar_close_status="VERIFIED",
    )


def test_expected_schedule_rejects_starts_closer_than_declared_interval():
    with pytest.raises(ValueError, match="closer than the declared interval"):
        _qualified_receipt(3600, [100, 160])


def test_expected_daily_schedule_allows_dst_shortened_calendar_day():
    eastern = ZoneInfo("America/New_York")
    timestamps = [
        int(datetime(2026, 3, 7, 9, 30, tzinfo=eastern).timestamp()),
        int(datetime(2026, 3, 8, 9, 30, tzinfo=eastern).timestamp()),
    ]
    _, receipt = _qualified_receipt(86400, timestamps, "America/New_York")

    assert receipt.historical_bars_qualified is True
    assert receipt.calendar_timezone == "America/New_York"


def test_expected_daily_schedule_rejects_23_hour_gap_outside_dst_transition():
    eastern = ZoneInfo("America/New_York")
    timestamps = [
        int(datetime(2026, 1, 10, 9, 30, tzinfo=eastern).timestamp()),
        int(datetime(2026, 1, 11, 8, 30, tzinfo=eastern).timestamp()),
    ]
    with pytest.raises(ValueError, match="closer than the declared interval"):
        _qualified_receipt(86400, timestamps, "America/New_York")


def test_expected_daily_schedule_allows_half_hour_dst_transition():
    lord_howe = ZoneInfo("Australia/Lord_Howe")
    timestamps = [
        int(datetime(2026, 10, 3, 9, 30, tzinfo=lord_howe).timestamp()),
        int(datetime(2026, 10, 4, 9, 30, tzinfo=lord_howe).timestamp()),
    ]
    _, receipt = _qualified_receipt(86400, timestamps, "Australia/Lord_Howe")

    assert timestamps[1] - timestamps[0] == 86400 - 1800
    assert receipt.historical_bars_qualified is True


def test_a200_adapter_records_timezone_from_authoritative_equity_calendar():
    class FakeYahoo:
        GRANULARITIES = (86400,)

        def candles(self, _symbol, interval_seconds, start_ts, end_ts):
            schedule = get_calendar("US_EQUITIES").expected_bar_timestamps(
                start_ts, end_ts, interval_seconds,
            )
            return [Bar(ts, 10, 12, 9, 11, 1) for ts in schedule]

        def meta(self, symbol):
            return {"symbol": symbol}

    row = snapshot()["instruments"][0]
    _, receipt = MarketUniverseAdapter(FakeYahoo()).fetch_history(
        row["instrument_id"], 86400,
        int(datetime(2026, 3, 6, tzinfo=ZoneInfo("UTC")).timestamp()),
        int(datetime(2026, 3, 10, tzinfo=ZoneInfo("UTC")).timestamp()),
    )

    assert receipt.calendar_timezone == "America/New_York"

