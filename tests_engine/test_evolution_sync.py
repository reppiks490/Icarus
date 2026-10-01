import json

import pytest

from icarus_engine.evolution_sync import (
    EvolutionRemoteSync,
    REMOTE_ROOT,
    _git_blob_sha,
)
from icarus_engine.system_audit import load_repository_audit
from icarus_engine.brain import brain_snapshot


def event_payload(**overrides):
    base = {
        "schema_version": "icarus-interface-event-v1",
        "event_id": "fixture-evolution-1",
        "category": "EVOLUTION",
        "severity": "success",
        "status": "verified",
        "subsystems": ["argus", "athena", "parallax"],
        "recorded_at": "2026-10-01T05:00:00Z",
        "title": "Fixture subsystem evolution",
        "summary": "Verified fixture event for the trader MCP Evolution panel.",
        "source_repository": "reppiks490/divine-providence",
        "source_ref": "fixture",
        "source_commit": "a" * 40,
        "evidence": ["pytest fixture", "execution authority remains false"],
        "execution_authorized": False,
        "production_decision_authorized": False,
    }
    base.update(overrides)
    return base


def make_sync(tmp_path, payload):
    raw = (json.dumps(payload, sort_keys=True) + "\n").encode()
    sha = _git_blob_sha(raw)
    path = REMOTE_ROOT + "/fixture.json"
    listing = [{"type": "file", "name": "fixture.json", "path": path, "sha": sha, "url": "fixture://event"}]

    def fetch_json(_url):
        return listing

    def fetch_bytes(url):
        assert url == "fixture://event"
        return raw

    return EvolutionRemoteSync(
        tmp_path,
        interval_seconds=30,
        fetch_json=fetch_json,
        fetch_bytes=fetch_bytes,
        enabled=True,
    )


def test_verified_event_reaches_evolution_system_and_brain_surfaces(tmp_path):
    sync = make_sync(tmp_path, event_payload())
    state = sync.sync_once()

    assert state["status"] == "green"
    assert state["ingested_total"] == 1
    assert state["rejected_total"] == 0
    assert state["execution_authorized"] is False
    assert state["production_decision_authorized"] is False
    assert state["events"][0]["event_id"] == "fixture-evolution-1"
    assert set(state["subsystems"]) >= {"argus", "athena", "parallax"}

    audit = load_repository_audit(tmp_path)
    assert audit["events"][0]["title"] == "Fixture subsystem evolution"
    assert audit["events"][0]["repository"] == "reppiks490/divine-providence"

    brain = brain_snapshot(tmp_path)
    subjects = {x["subject"] for x in brain["events"] if x["kind"] == "subsystem"}
    assert {"argus", "athena", "parallax"} <= subjects


def test_sync_is_idempotent_by_verified_git_blob(tmp_path):
    sync = make_sync(tmp_path, event_payload())
    first = sync.sync_once()
    second = sync.sync_once()

    assert first["ingested_total"] == 1
    assert second["ingested_total"] == 1
    assert len(second["events"]) == 1
    assert second["rejected_total"] == 0


@pytest.mark.parametrize(
    "change",
    [
        {"execution_authorized": True},
        {"production_decision_authorized": True},
        {"schema_version": "wrong"},
        {"category": "TRADE"},
        {"subsystems": ["unknown-subsystem"]},
        {"source_commit": "short"},
        {"source_commit": ""},
        {"recorded_at": "2026-10-01T05:00:00"},
    ],
)
def test_invalid_or_authority_escalating_event_is_rejected(tmp_path, change):
    sync = make_sync(tmp_path, event_payload(**change))
    state = sync.sync_once()

    assert state["status"] == "degraded"
    assert state["ingested_total"] == 0
    assert state["rejected_total"] == 1
    assert state["events"] == []
    assert state["execution_authorized"] is False


def test_blob_sha_mismatch_is_rejected(tmp_path):
    payload = event_payload()
    raw = (json.dumps(payload, sort_keys=True) + "\n").encode()
    listing = [{
        "type": "file",
        "name": "fixture.json",
        "path": REMOTE_ROOT + "/fixture.json",
        "sha": "b" * 40,
        "url": "fixture://event",
    }]
    sync = EvolutionRemoteSync(
        tmp_path,
        interval_seconds=30,
        fetch_json=lambda _url: listing,
        fetch_bytes=lambda _url: raw,
        enabled=True,
    )
    state = sync.sync_once()
    assert state["status"] == "degraded"
    assert state["rejected_total"] == 1
    assert state["ingested_total"] == 0


def test_disabled_sync_never_fetches_network(tmp_path):
    def boom(_url):
        raise AssertionError("network should not be called")

    sync = EvolutionRemoteSync(
        tmp_path,
        interval_seconds=30,
        fetch_json=boom,
        fetch_bytes=boom,
        enabled=False,
    )
    state = sync.sync_once()
    assert state["status"] == "disabled"
    assert state["execution_authorized"] is False


def test_psi_is_a_supported_mcp_subsystem(tmp_path):
    sync = make_sync(tmp_path, event_payload(subsystems=["psi", "parallax"]))
    state = sync.sync_once()
    assert state["status"] == "green"
    assert state["ingested_total"] == 1
    assert set(state["subsystems"]) >= {"psi", "parallax"}
