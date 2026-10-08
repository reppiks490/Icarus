from __future__ import annotations

import json
from datetime import datetime, timedelta

import pytest

from icarus_engine import brain_sync
from icarus_engine.brain_sync import BrainRemoteSync
from tests_engine.test_brain_sync import _fixture, _remote_event


def _unexpected_io(*args, **kwargs):
    raise AssertionError("status must not fetch or write")


@pytest.fixture
def accepted_packet(tmp_path):
    remote = _fixture(_remote_event())
    clock = [remote["now_utc"]()]
    sync = BrainRemoteSync(
        tmp_path,
        interval_seconds=60,
        fetch_json=remote["fetch_json"],
        fetch_bytes=remote["fetch_bytes"],
        now_utc=lambda: clock[0],
    )
    assert sync.sync_once()["peer_packet_fresh"] is True
    sync.close()
    path = tmp_path / "audit" / "brain_remote_sync.json"
    persisted = json.loads(path.read_text())
    observed = datetime.fromisoformat(persisted["peer_observed_at"].replace("Z", "+00:00"))
    reader = BrainRemoteSync(
        tmp_path,
        interval_seconds=60,
        fetch_json=_unexpected_io,
        fetch_bytes=_unexpected_io,
        now_utc=lambda: clock[0],
    )
    return reader, clock, path, persisted, observed


@pytest.mark.parametrize(
    ("age", "fresh"),
    [
        (-300.000001, False), (-300, True), (0, True), (900, True),
        (1800, True), (1800.000001, False),
    ],
)
def test_status_recalculates_age_with_exact_contract_boundaries(accepted_packet, age, fresh):
    reader, clock, _, persisted, observed = accepted_packet
    clock[0] = observed + timedelta(seconds=age)

    status = reader.status()

    assert status["peer_packet_age_seconds"] == round(age, 3)
    assert status["peer_packet_fresh"] is fresh
    assert status["peer_packet_status"] == ("green" if fresh else "degraded")
    assert status["status"] == ("green" if fresh else "degraded")
    if fresh:
        assert status["last_error"] is None
    else:
        assert ("stale" if age > 1800 else "future clock skew") in status["last_error"]
    changed_fields = {
        "peer_packet_age_seconds", "peer_packet_fresh", "peer_packet_status",
        "status", "last_error", "processed_blob_shas", "processed_historical_blob_shas",
    }
    assert {k: v for k, v in status.items() if k not in changed_fields} == {
        k: v for k, v in persisted.items() if k not in changed_fields
    }


def test_status_expires_after_sync_stops_without_fetching_or_mutating(accepted_packet, monkeypatch):
    reader, clock, path, _, observed = accepted_packet
    before = {
        p.relative_to(reader.base_dir): p.read_bytes()
        for p in reader.base_dir.rglob("*") if p.is_file()
    }
    monkeypatch.setattr(brain_sync, "_write_state", _unexpected_io)
    monkeypatch.setattr(brain_sync, "record_brain_event", _unexpected_io)

    assert reader.status()["peer_packet_age_seconds"] == 60.0
    for age in (1801, 7200):
        clock[0] = observed + timedelta(seconds=age)
        status = reader.status()
        assert status["peer_packet_age_seconds"] == age
        assert status["peer_packet_fresh"] is False
        assert status["peer_packet_status"] == "degraded"
    assert json.loads(path.read_text())["peer_packet_fresh"] is True
    assert {
        p.relative_to(reader.base_dir): p.read_bytes()
        for p in reader.base_dir.rglob("*") if p.is_file()
    } == before


@pytest.mark.parametrize("observed", [None, "", "invalid", "2026-10-02T20:43:00", 42, []])
def test_status_fails_closed_for_invalid_persisted_timestamp(accepted_packet, observed):
    reader, _, path, persisted, _ = accepted_packet
    persisted["peer_observed_at"] = observed
    path.write_text(json.dumps(persisted))

    status = reader.status()

    assert status["peer_packet_age_seconds"] is None
    assert status["peer_packet_fresh"] is False
    assert status["peer_packet_status"] == "degraded"
    assert status["status"] == "degraded"
    assert status["last_error"]


def test_status_fails_closed_for_missing_persisted_timestamp(accepted_packet):
    reader, _, path, persisted, _ = accepted_packet
    del persisted["peer_observed_at"]
    path.write_text(json.dumps(persisted))

    status = reader.status()

    assert status["peer_packet_age_seconds"] is None
    assert status["peer_packet_fresh"] is False
    assert status["peer_packet_status"] == "degraded"


@pytest.mark.parametrize("now", [None, "2026-10-02T20:44:00Z", datetime(2026, 10, 2, 20, 44)])
def test_status_fails_closed_for_invalid_current_clock(accepted_packet, now):
    reader, clock, _, _, _ = accepted_packet
    clock[0] = now

    status = reader.status()

    assert status["peer_packet_age_seconds"] is None
    assert status["peer_packet_fresh"] is False
    assert status["peer_packet_status"] == "degraded"
    assert status["status"] == "degraded"
    assert "clock" in status["last_error"]


def test_status_fails_closed_when_current_clock_raises(accepted_packet):
    reader, _, _, _, _ = accepted_packet

    def broken_clock():
        raise RuntimeError("clock unavailable")

    reader._now_utc = broken_clock

    status = reader.status()

    assert status["peer_packet_age_seconds"] is None
    assert status["peer_packet_fresh"] is False
    assert status["peer_packet_status"] == "degraded"
    assert "clock unavailable" in status["last_error"]


@pytest.mark.parametrize("age", [60, 1801])
@pytest.mark.parametrize(
    "peer_status, fresh",
    [("degraded", False), ("degraded", True), ("blocked", True), ("green", False), ("green", True)],
)
def test_status_preserves_prior_failures(accepted_packet, age, peer_status, fresh):
    reader, clock, path, persisted, observed = accepted_packet
    persisted.update(
        status="degraded", last_error="prior verification failure",
        peer_packet_status=peer_status, peer_packet_fresh=fresh,
    )
    path.write_text(json.dumps(persisted))
    clock[0] = observed + timedelta(seconds=age)

    status = reader.status()

    assert status["status"] == "degraded"
    assert status["last_error"] == "prior verification failure"
    assert status["peer_packet_fresh"] is (fresh and peer_status == "green" and age <= 1800)
    if peer_status != "green":
        assert status["peer_packet_status"] == peer_status


def test_status_before_first_sync_stays_not_started_without_creating_state(tmp_path):
    reader = BrainRemoteSync(
        tmp_path, fetch_json=_unexpected_io, fetch_bytes=_unexpected_io, now_utc=_unexpected_io,
    )

    status = reader.status()

    assert status["status"] == "not_started"
    assert status["peer_packet_status"] == "not_started"
    assert status["peer_packet_fresh"] is False
    assert status["peer_packet_age_seconds"] is None
    assert status["last_error"] is None
    assert list(tmp_path.iterdir()) == []
