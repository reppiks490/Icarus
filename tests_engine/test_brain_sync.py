from __future__ import annotations

import json

from icarus_engine.brain import brain_snapshot
from icarus_engine.brain_sync import BrainRemoteSync, REMOTE_ROOT, _git_blob_sha


def _remote_event(**overrides):
    payload = {
        "schema": "icarus-mcp-event-v1",
        "category": "AUDIT",
        "source": "FLOW_AUTOMATION",
        "execution_authorized": False,
        "retrieval_time_utc": "2026-10-01T04:23:01Z",
        "net_new_delta": "Authenticated flow delta.",
        "evidence": {"btc": "measured spot evidence"},
        "argus": {"status": "USEFUL", "finding": "True depth snapshot preserved as snapshot-only evidence."},
        "nexus": {"status": "USEFUL", "finding": "Representations and data gaps remain separated."},
        "data_gaps": ["direct NQ unavailable"],
        "conflicts": [],
    }
    payload.update(overrides)
    return payload


def _fixture(payload):
    raw = (json.dumps(payload, sort_keys=True) + "\n").encode()
    sha = _git_blob_sha(raw)
    path = f"{REMOTE_ROOT}/flow-test.json"
    url = "https://api.github.test/flow-test"
    listing = [{"name": "flow-test.json", "path": path, "sha": sha, "url": url, "type": "file"}]
    return raw, sha, path, url, listing


def test_remote_sync_ingests_custom_agent_and_owned_subsystem_events(tmp_path):
    raw, sha, path, url, listing = _fixture(_remote_event())

    sync = BrainRemoteSync(
        tmp_path,
        interval_seconds=60,
        fetch_json=lambda _: listing,
        fetch_bytes=lambda requested: raw if requested == url else b"",
    )
    status = sync.sync_once()
    assert status["status"] == "green"
    assert status["ingested_total"] == 1
    assert status["last_ingested"] == [path]
    assert status["execution_authorized"] is False

    snap = brain_snapshot(tmp_path, remote_sync=status)
    agents = {x["id"]: x for x in snap["architecture"]["agents"]}
    subsystems = {x["id"]: x for x in snap["architecture"]["subsystems"]}
    assert agents["flow"]["detail"] == "Authenticated flow delta."
    assert subsystems["argus"]["detail"].startswith("True depth snapshot")
    assert subsystems["nexus"]["detail"].startswith("Representations and data gaps")
    assert snap["remote_sync"]["status"] == "green"

    again = sync.sync_once()
    assert again["ingested_total"] == 1
    assert len(brain_snapshot(tmp_path)["events"]) == 3


def test_remote_sync_rejects_authority_escalation(tmp_path):
    raw, _sha, _path, url, listing = _fixture(_remote_event(execution_authorized=True))
    sync = BrainRemoteSync(
        tmp_path,
        interval_seconds=60,
        fetch_json=lambda _: listing,
        fetch_bytes=lambda requested: raw if requested == url else b"",
    )
    status = sync.sync_once()
    assert status["status"] == "degraded"
    assert status["rejected_total"] == 1
    assert "execution_authorized=false" in status["last_error"]
    snap = brain_snapshot(tmp_path)
    assert snap["events"] == []


def test_remote_sync_detects_blob_substitution(tmp_path):
    raw, _sha, _path, url, listing = _fixture(_remote_event())
    listing[0]["sha"] = "a" * 40
    sync = BrainRemoteSync(
        tmp_path,
        interval_seconds=60,
        fetch_json=lambda _: listing,
        fetch_bytes=lambda requested: raw if requested == url else b"",
    )
    status = sync.sync_once()
    assert status["status"] == "degraded"
    assert status["rejected_total"] == 1
    assert "Git blob SHA mismatch" in status["last_error"]
    assert brain_snapshot(tmp_path)["events"] == []
