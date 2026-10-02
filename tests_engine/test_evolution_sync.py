import json
from pathlib import Path

import pytest

from icarus_engine.evolution_sync import (
    EvolutionRemoteSync,
    REMOTE_ROOT,
    _git_blob_sha,
    normalize_interface_event,
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


def test_foreign_schema_receipt_is_ignored_not_rejected(tmp_path):
    payload = {
        "schema_version": "icarus-mcp-event-v1",
        "event_id": "foreign-family-fixture",
        "category": "EVOLUTION",
        "execution_authorized": False,
        "production_decision_authorized": False,
    }
    raw = (json.dumps(payload, sort_keys=True) + "\n").encode()
    sha = _git_blob_sha(raw)
    path = REMOTE_ROOT + "/foreign.json"
    listing = [{
        "type": "file",
        "name": "foreign.json",
        "path": path,
        "sha": sha,
        "url": "fixture://foreign",
    }]
    sync = EvolutionRemoteSync(
        tmp_path,
        interval_seconds=30,
        fetch_json=lambda _url: listing,
        fetch_bytes=lambda url: raw if url == "fixture://foreign" else b"",
        enabled=True,
    )

    first = sync.sync_once()
    second = sync.sync_once()

    assert first["status"] == "green"
    assert first["ignored_total"] == 1
    assert first["rejected_total"] == 0
    assert first["ingested_total"] == 0
    assert first["events"] == []
    assert second["ignored_total"] == 1
    assert second["rejected_total"] == 0


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


def test_committed_interface_receipts_match_current_ingestion_contract():
    root = (
        Path(__file__).resolve().parents[1]
        / "automation_intelligence"
        / "mcp_interface"
        / "events"
    )
    checked = 0
    foreign = 0

    for path in sorted(root.glob("*.json")):
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
        if payload.get("schema_version") != "icarus-interface-event-v1":
            foreign += 1
            continue
        normalized = normalize_interface_event(
            payload,
            source_path=f"{REMOTE_ROOT}/{path.name}",
            blob_sha=_git_blob_sha(raw),
        )
        assert normalized["execution_authorized"] is False
        assert normalized["production_decision_authorized"] is False
        checked += 1

    assert checked > 0
    # The directory is intentionally shared with macro/audit/integration
    # receipt families; runtime sync must ignore those rather than degrade.
    assert foreign > 0


def test_repository_native_interface_vocabulary_is_accepted(tmp_path):
    # These names already exist in committed icarus-interface-event-v1 receipts.
    # Underscore payload spelling is normalized to the dashboard's hyphen form.
    raw_names = [
        "pantheon",
        "aether",
        "nemesis",
        "godel",
        "socrates",
        "ananke",
        "ex_nihilo",
        "mint",
        "nullspace",
        "archon",
        "ui",
        "sibyl",
        "execution_research",
        "order_blocks",
        "research_validation",
        "uncertainty",
        "calibration",
        "prospective_validation",
        "transfer_validation",
        "tail_validation",
        "liquidity_load",
        "cluster_bootstrap",
    ]
    sync = make_sync(
        tmp_path,
        event_payload(
            subsystems=raw_names,
            status="staged",
            title="Repository-native vocabulary fixture",
        ),
    )
    state = sync.sync_once()

    assert state["status"] == "green"
    assert state["ingested_total"] == 1
    assert state["rejected_total"] == 0
    assert {
        "pantheon",
        "aether",
        "nemesis",
        "godel",
        "socrates",
        "ananke",
        "ex-nihilo",
        "mint",
        "nullspace",
        "archon",
        "ui",
        "sibyl",
        "execution-research",
        "order-blocks",
        "research-validation",
        "uncertainty",
        "calibration",
        "prospective-validation",
        "transfer-validation",
        "tail-validation",
        "liquidity-load",
        "cluster-bootstrap",
    } <= set(state["subsystems"])
