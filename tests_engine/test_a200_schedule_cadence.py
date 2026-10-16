import pytest

from icarus_engine.bar_receipts import make_bar_batch_receipt
from icarus_engine.pine.timeframe import Bar


def _qualified_receipt(interval_seconds, timestamps):
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
        bar_close_status="VERIFIED",
    )


def test_expected_schedule_rejects_starts_closer_than_declared_interval():
    with pytest.raises(ValueError, match="closer than the declared interval"):
        _qualified_receipt(3600, [100, 160])


def test_expected_daily_schedule_allows_dst_shortened_calendar_day():
    _, receipt = _qualified_receipt(86400, [100, 100 + 23 * 3600])

    assert receipt.historical_bars_qualified is True

