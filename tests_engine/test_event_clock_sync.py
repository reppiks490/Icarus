from __future__ import annotations

import json

import pytest

from icarus_engine.event_clock_sync import (
    EconomicEventClockSync,
    REMOTE_FILES,
    _REMOTE_APIS,
    _git_blob_sha,
    _normalize,
)


def docs():
    manifest = {
        "schema": "icarus.economic_events/1",
        "generated_at": "2026-10-06T01:29:11.592310+00:00",
        "sources": {
            "BEA": {"rows": 2, "status": "ok"},
            "BLS": {
                "rows": 2, "status": "degraded", "transport": "official_snapshot",
                "snapshot_as_of": "2026-10-06",
                "source_url": "https://www.bls.gov/schedule/2026/",
                "error": "live BLS transports unavailable",
            },
            "CENSUS": {"rows": 1, "status": "ok"},
            "FOMC": {"rows": 1, "status": "ok", "history_invalid_rows_removed": 38},
        },
        "current_events": 6,
        "schedule_versions": 6,
        "high_impact_current": 4,
        "time_known_current": 5,
        "upcoming_rows": 3,
        "causality": "use only schedule versions first seen by decision time",
    }
    upcoming = {
        "schema": "icarus.economic_events.upcoming/1",
        "generated_at": manifest["generated_at"],
        "timezone": "America/New_York",
        "events": [
            {
                "source": "BLS", "event_key": "cpi", "title": "Consumer Price Index for September 2026",
                "category": "inflation", "impact": "high", "reference_period": "September 2026",
                "event_date": "2026-10-14", "scheduled_at_et": "2026-10-14T08:30:00-04:00",
                "scheduled_at_utc": "2026-10-14T12:30:00+00:00", "time_known": True,
                "timing_basis": "source_schedule",
            },
            {
                "source": "CENSUS", "event_key": "retail", "title": "Advance Monthly Sales for Retail and Food Services",
                "category": "growth", "impact": "high", "reference_period": "September 2026",
                "event_date": "2026-10-15", "scheduled_at_et": "2026-10-15T08:30:00-04:00",
                "scheduled_at_utc": "2026-10-15T12:30:00+00:00", "time_known": True,
                "timing_basis": "source_schedule",
            },
            {
                "source": "FOMC", "event_key": "fomc", "title": "FOMC policy decision",
                "category": "policy", "impact": "high", "reference_period": None,
                "event_date": "2026-10-28", "scheduled_at_et": None, "scheduled_at_utc": None,
                "time_known": False, "timing_basis": "meeting_end_date; statement time not asserted",
            },
        ],
    }
    return manifest, upcoming


def make_sync(tmp_path, manifest=None, upcoming=None):
    manifest = manifest or docs()[0]
    upcoming = upcoming or docs()[1]
    payloads = {
        "manifest": (json.dumps(manifest, sort_keys=True) + "\n").encode(),
        "upcoming": (json.dumps(upcoming, sort_keys=True) + "\n").encode(),
    }
    urls = {key: f"fixture://{key}" for key in payloads}
    metadata = {
        _REMOTE_APIS[key]: {"sha": _git_blob_sha(raw), "url": urls[key]}
        for key, raw in payloads.items()
    }
    return EconomicEventClockSync(
        tmp_path,
        interval_seconds=30,
        fetch_json=lambda url: metadata[url],
        fetch_bytes=lambda url: next(payloads[key] for key in payloads if urls[key] == url),
    ), payloads, metadata


def test_verified_remote_clock_becomes_degraded_usable_local_snapshot(tmp_path):
    sync, _, _ = make_sync(tmp_path)
    state = sync.sync_once()

    assert state["status"] == "degraded"
    assert state["source_health"] == "degraded"
    assert state["sources"]["BLS"]["transport"] == "official_snapshot"
    assert state["sources"]["BLS"]["snapshot_as_of"] == "2026-10-06"
    assert state["sources"]["FOMC"]["history_invalid_rows_removed"] == 38
    assert state["current_events"] == 6
    assert state["upcoming_count"] == 3
    assert state["events"][0]["event_key"] == "cpi"
    assert state["events"][-1]["event_key"] == "fomc"
    assert state["events"][-1]["time_known"] is False
    assert state["events"][-1]["scheduled_at_utc"] is None
    assert state["execution_authorized"] is False
    assert state["production_decision_authorized"] is False
    assert set(state["remote_blobs"]) == {"manifest", "upcoming"}


def test_blob_mismatch_preserves_last_verified_schedule_and_marks_degraded(tmp_path):
    sync, payloads, metadata = make_sync(tmp_path)
    first = sync.sync_once()
    assert first["events"]

    metadata[_REMOTE_APIS["upcoming"]]["sha"] = "a" * 40
    second = sync.sync_once()

    assert second["status"] == "degraded"
    assert "Git blob SHA mismatch" in second["last_error"]
    assert second["events"] == first["events"]
    assert second["last_success_at"] == first["last_success_at"]


def test_date_only_event_must_not_smuggle_an_exact_timestamp():
    manifest, upcoming = docs()
    upcoming["events"][-1]["scheduled_at_utc"] = "2026-10-28T18:00:00+00:00"
    with pytest.raises(ValueError, match="cannot expose a timestamp"):
        _normalize(manifest, upcoming, {"manifest": "a" * 40, "upcoming": "b" * 40})


def test_exact_event_requires_timezone_aware_timestamps():
    manifest, upcoming = docs()
    upcoming["events"][0]["scheduled_at_utc"] = "2026-10-14T12:30:00"
    with pytest.raises(ValueError, match="include a timezone"):
        _normalize(manifest, upcoming, {"manifest": "a" * 40, "upcoming": "b" * 40})


def test_source_rows_must_reconcile_to_current_event_count():
    manifest, upcoming = docs()
    manifest["current_events"] += 1
    with pytest.raises(ValueError, match="source row counts"):
        _normalize(manifest, upcoming, {"manifest": "a" * 40, "upcoming": "b" * 40})


def test_disabled_sync_never_fetches(tmp_path):
    calls = []
    sync = EconomicEventClockSync(
        tmp_path,
        interval_seconds=30,
        enabled=False,
        fetch_json=lambda url: calls.append(url),
        fetch_bytes=lambda url: b"",
    )
    state = sync.sync_once()
    assert state["status"] == "disabled"
    assert calls == []
    assert state["execution_authorized"] is False


def test_remote_file_contract_points_only_at_compact_event_artifacts():
    assert REMOTE_FILES == {
        "manifest": "automation_intelligence/cl_lab/economic_events_manifest.json",
        "upcoming": "automation_intelligence/cl_lab/economic_events_upcoming.json",
    }
