import json
from datetime import datetime, timezone

import pytest

import icarus_engine.market_universe as market_universe
from icarus_engine.calendar import get_calendar


@pytest.mark.parametrize("tamper", ["counts", "results_sha256"])
def test_a200_probe_report_rejects_tampered_aggregate_integrity(
    monkeypatch, tmp_path, tamper,
):
    report = json.loads(market_universe.PROBE_PATH.read_text(encoding="utf-8"))
    if tamper == "counts":
        report["counts"]["provider_symbol_match_count"] += 1
    else:
        report["results_sha256"] = "0" * 64
    probe_path = tmp_path / "probe.json"
    probe_path.write_text(json.dumps(report), encoding="utf-8")
    monkeypatch.setattr(market_universe, "PROBE_PATH", probe_path)

    result = market_universe.load_source_probe_report()

    assert result["status"] == "INVALID"
    assert result["results"] == []


def test_us_equity_weekly_bucket_starts_inside_supported_year_boundary():
    calendar = get_calendar("US_EQUITIES")
    friday_open = int(datetime(2026, 1, 2, 14, 30, tzinfo=timezone.utc).timestamp())

    bucket = calendar.bucket_start(friday_open, 10080)

    assert bucket == friday_open
    assert calendar.bucket_end(bucket, 10080) == int(
        datetime(2026, 1, 2, 21, 0, tzinfo=timezone.utc).timestamp()
    )


def test_us_equity_calendar_fails_closed_at_end_of_supported_year():
    calendar = get_calendar("US_EQUITIES")
    after_supported_schedule = int(
        datetime(2028, 12, 30, 17, 0, tzinfo=timezone.utc).timestamp()
    )

    assert calendar.next_open(after_supported_schedule) is None
    with pytest.raises(ValueError, match="exceeds verified 2026–2028 coverage"):
        calendar.expected_bar_timestamps(
            int(datetime(2028, 12, 29, 14, 30, tzinfo=timezone.utc).timestamp()),
            int(datetime(2029, 1, 2, 14, 30, tzinfo=timezone.utc).timestamp()),
            60,
        )
