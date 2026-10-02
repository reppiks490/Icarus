import json
from pathlib import Path

import pytest

import icarus_engine.evolution_sync as evolution_sync_module
from icarus_engine.evolution_sync import (
    EvolutionRemoteSync,
    REMOTE_ROOT,
    VALIDATOR_REVISION,
    _IGNORED_SCHEMA_VERSIONS,
    _git_blob_sha,
    normalize_interface_event,
)
from icarus_engine.system_audit import load_repository_audit
from icarus_engine.brain import SUBSYSTEMS, brain_snapshot


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
    assert "event_id_bindings" not in state
    assert "rejected_blob_shas" not in state
    assert "rejected_blob_errors" not in state
    assert "rejected_history_blob_shas" not in state
    assert state["validator_revision"] == VALIDATOR_REVISION
    assert state["events"][0]["event_id"] == "fixture-evolution-1"
    assert set(state["subsystems"]) >= {"argus", "athena", "parallax"}

    audit = load_repository_audit(tmp_path)
    assert audit["events"][0]["title"] == "Fixture subsystem evolution"
    assert audit["events"][0]["repository"] == "reppiks490/divine-providence"

    brain = brain_snapshot(tmp_path)
    subjects = {x["subject"] for x in brain["events"] if x["kind"] == "subsystem"}
    assert {"argus", "athena", "parallax"} <= subjects


def test_backfilled_older_receipt_cannot_regress_latest_subsystem_state(tmp_path):
    newer = event_payload(
        event_id="newer-argus-state",
        subsystems=["argus"],
        status="verified",
        title="Newer ARGUS state",
        summary="Newer state must remain authoritative in the Evolution view.",
        recorded_at="2026-10-01T05:00:00Z",
    )
    # Raw text looks later than 05:00Z but is actually 04:30Z.
    older = event_payload(
        event_id="older-argus-backfill",
        subsystems=["argus"],
        status="blocked",
        title="Older ARGUS backfill",
        summary="Historical backfill must not regress current subsystem state.",
        recorded_at="2026-10-01T06:30:00+02:00",
    )
    raws = {
        "fixture://newer": (
            json.dumps(newer, sort_keys=True) + "\n"
        ).encode(),
        "fixture://older": (
            json.dumps(older, sort_keys=True) + "\n"
        ).encode(),
    }
    stage = {"include_old": False}

    def listing(_url):
        rows = [{
            "type": "file",
            "name": "20261001T050000Z_newer.json",
            "path": REMOTE_ROOT + "/20261001T050000Z_newer.json",
            "sha": _git_blob_sha(raws["fixture://newer"]),
            "url": "fixture://newer",
        }]
        if stage["include_old"]:
            rows.append({
                "type": "file",
                "name": "zz_historical_backfill.json",
                "path": REMOTE_ROOT + "/zz_historical_backfill.json",
                "sha": _git_blob_sha(raws["fixture://older"]),
                "url": "fixture://older",
            })
        return rows

    sync = EvolutionRemoteSync(
        tmp_path,
        interval_seconds=30,
        fetch_json=listing,
        fetch_bytes=lambda url: raws[url],
        enabled=True,
    )

    first = sync.sync_once()
    assert first["status"] == "green"
    assert first["subsystems"]["argus"]["event_id"] == "newer-argus-state"

    stage["include_old"] = True
    second = sync.sync_once()

    assert second["status"] == "green"
    assert second["ingested_total"] == 2
    assert second["subsystems"]["argus"]["event_id"] == "newer-argus-state"
    assert [row["event_id"] for row in second["events"][:2]] == [
        "newer-argus-state",
        "older-argus-backfill",
    ]


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


@pytest.mark.parametrize("schema_field", ["schema_version", "schema"])
def test_foreign_schema_receipt_is_ignored_not_rejected(tmp_path, schema_field):
    payload = {
        schema_field: "icarus-mcp-event-v1",
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


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"schema_version": "wrong"},
        {"schema": "wrong"},
    ],
)
def test_missing_or_unknown_schema_is_rejected(tmp_path, payload):
    raw = (json.dumps(payload, sort_keys=True) + "\n").encode()
    sha = _git_blob_sha(raw)
    listing = [{
        "type": "file",
        "name": "unknown.json",
        "path": REMOTE_ROOT + "/unknown.json",
        "sha": sha,
        "url": "fixture://unknown",
    }]
    fetches = {"bytes": 0}

    def fetch_bytes(_url):
        fetches["bytes"] += 1
        return raw

    sync = EvolutionRemoteSync(
        tmp_path,
        interval_seconds=30,
        fetch_json=lambda _url: listing,
        fetch_bytes=fetch_bytes,
        enabled=True,
    )
    first = sync.sync_once()
    second = sync.sync_once()

    assert first["status"] == "degraded"
    assert first["ignored_total"] == 0
    assert first["rejected_total"] == 1
    assert first["current_rejected_count"] == 1
    assert first["ingested_total"] == 0
    assert first["last_success_at"] is None

    # The same immutable bad Git blob remains a current error, but repeated
    # polls do not inflate the historical rejection counter or refetch it.
    assert second["status"] == "degraded"
    assert second["rejected_total"] == 1
    assert second["current_rejected_count"] == 1
    assert fetches["bytes"] == 1


def test_rejected_receipt_recovers_when_git_blob_is_replaced(tmp_path):
    current = {"payload": {"schema_version": "wrong"}}
    fetches = {"bytes": 0}

    def raw():
        return (
            json.dumps(current["payload"], sort_keys=True) + "\n"
        ).encode()

    def listing(_url):
        payload = raw()
        return [{
            "type": "file",
            "name": "replaceable.json",
            "path": REMOTE_ROOT + "/replaceable.json",
            "sha": _git_blob_sha(payload),
            "url": "fixture://replaceable",
        }]

    def fetch_bytes(_url):
        fetches["bytes"] += 1
        return raw()

    sync = EvolutionRemoteSync(
        tmp_path,
        interval_seconds=30,
        fetch_json=listing,
        fetch_bytes=fetch_bytes,
        enabled=True,
    )

    first = sync.sync_once()
    again = sync.sync_once()
    assert first["status"] == "degraded"
    assert first["rejected_total"] == 1
    assert again["rejected_total"] == 1
    assert again["current_rejected_count"] == 1
    assert fetches["bytes"] == 1

    current["payload"] = event_payload(
        event_id="replacement-valid-event",
        title="Replacement valid event",
    )
    recovered = sync.sync_once()

    assert recovered["status"] == "green"
    assert recovered["rejected_total"] == 1
    assert recovered["current_rejected_count"] == 0
    assert recovered["ingested_total"] == 1
    assert recovered["last_success_at"] is not None
    assert recovered["events"][0]["event_id"] == "replacement-valid-event"
    assert fetches["bytes"] == 2


def test_transient_fetch_failure_retries_without_rejecting_receipt(tmp_path):
    payload = event_payload(event_id="retry-after-fetch")
    raw = (json.dumps(payload, sort_keys=True) + "\n").encode()
    sha = _git_blob_sha(raw)
    listing = [{
        "type": "file",
        "name": "retry.json",
        "path": REMOTE_ROOT + "/retry.json",
        "sha": sha,
        "url": "fixture://retry",
    }]
    attempts = {"bytes": 0}

    def fetch_bytes(_url):
        attempts["bytes"] += 1
        if attempts["bytes"] == 1:
            raise OSError("temporary fetch failure")
        return raw

    sync = EvolutionRemoteSync(
        tmp_path,
        interval_seconds=30,
        fetch_json=lambda _url: listing,
        fetch_bytes=fetch_bytes,
        enabled=True,
    )

    first = sync.sync_once()
    second = sync.sync_once()

    assert first["status"] == "degraded"
    assert first["rejected_total"] == 0
    assert first["current_rejected_count"] == 0
    assert first["ingested_total"] == 0
    assert first["last_success_at"] is None

    assert second["status"] == "green"
    assert second["rejected_total"] == 0
    assert second["current_rejected_count"] == 0
    assert second["ingested_total"] == 1
    assert attempts["bytes"] == 2


def test_transient_local_projection_failure_retries_valid_receipt(
    tmp_path,
    monkeypatch,
):
    payload = event_payload(event_id="retry-after-projection")
    raw = (json.dumps(payload, sort_keys=True) + "\n").encode()
    sha = _git_blob_sha(raw)
    listing = [{
        "type": "file",
        "name": "projection.json",
        "path": REMOTE_ROOT + "/projection.json",
        "sha": sha,
        "url": "fixture://projection",
    }]
    real_append = evolution_sync_module.append_system_event
    attempts = {"append": 0}

    def flaky_append(*args, **kwargs):
        attempts["append"] += 1
        if attempts["append"] == 1:
            raise OSError("temporary local journal failure")
        return real_append(*args, **kwargs)

    monkeypatch.setattr(
        evolution_sync_module,
        "append_system_event",
        flaky_append,
    )
    sync = EvolutionRemoteSync(
        tmp_path,
        interval_seconds=30,
        fetch_json=lambda _url: listing,
        fetch_bytes=lambda _url: raw,
        enabled=True,
    )

    first = sync.sync_once()
    second = sync.sync_once()

    assert first["status"] == "degraded"
    assert first["rejected_total"] == 0
    assert first["current_rejected_count"] == 0
    assert first["ingested_total"] == 0

    assert second["status"] == "green"
    assert second["rejected_total"] == 0
    assert second["current_rejected_count"] == 0
    assert second["ingested_total"] == 1
    assert attempts["append"] == 2


def test_partial_brain_projection_does_not_publish_partial_subsystem_state(
    tmp_path,
    monkeypatch,
):
    payload = event_payload(event_id="retry-mid-brain-projection")
    raw = (json.dumps(payload, sort_keys=True) + "\n").encode()
    sha = _git_blob_sha(raw)
    listing = [{
        "type": "file",
        "name": "brain-projection.json",
        "path": REMOTE_ROOT + "/brain-projection.json",
        "sha": sha,
        "url": "fixture://brain-projection",
    }]
    real_record = evolution_sync_module.record_brain_event
    attempts = {"brain": 0}

    def flaky_record(*args, **kwargs):
        attempts["brain"] += 1
        if attempts["brain"] == 2:
            raise OSError("temporary brain journal failure")
        return real_record(*args, **kwargs)

    monkeypatch.setattr(
        evolution_sync_module,
        "record_brain_event",
        flaky_record,
    )
    sync = EvolutionRemoteSync(
        tmp_path,
        interval_seconds=30,
        fetch_json=lambda _url: listing,
        fetch_bytes=lambda _url: raw,
        enabled=True,
    )

    first = sync.sync_once()
    second = sync.sync_once()

    assert first["status"] == "degraded"
    assert first["rejected_total"] == 0
    assert first["ingested_total"] == 0
    assert first["events"] == []
    assert first["subsystems"] == {}

    assert second["status"] == "green"
    assert second["rejected_total"] == 0
    assert second["ingested_total"] == 1
    assert set(second["subsystems"]) >= {"argus", "athena", "parallax"}
    assert attempts["brain"] == 5


def test_malformed_legacy_rejection_state_is_normalized(tmp_path):
    state_path = tmp_path / "audit" / "mcp_evolution_sync.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        json.dumps(
            {
                "execution_authorized": False,
                "production_decision_authorized": False,
                "validator_revision": VALIDATOR_REVISION,
                "ingested_total": "bad",
                "ignored_total": None,
                "rejected_total": -7,
                "processed_blob_shas": None,
                "events": {"not": "a list"},
                "subsystems": ["not", "a", "mapping"],
                "rejected_blob_shas": None,
                "rejected_history_blob_shas": "not-a-list",
                "rejected_blob_errors": [],
                "event_id_bindings": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )

    sync = EvolutionRemoteSync(
        tmp_path,
        interval_seconds=30,
        fetch_json=lambda _url: [],
        fetch_bytes=lambda _url: b"",
        enabled=True,
    )
    state = sync.sync_once()

    assert state["status"] == "green"
    assert state["current_rejected_count"] == 0
    assert state["ingested_total"] == 0
    assert state["ignored_total"] == 0
    assert state["rejected_total"] == 0
    assert state["events"] == []
    assert state["subsystems"] == {}
    assert state["validator_revision"] == VALIDATOR_REVISION


def test_legacy_attempt_counter_is_not_mislabeled_as_unique_versions(tmp_path):
    state_path = tmp_path / "audit" / "mcp_evolution_sync.json"
    state_path.parent.mkdir(parents=True)
    state_path.write_text(
        json.dumps(
            {
                "execution_authorized": False,
                "production_decision_authorized": False,
                # Legacy v1 state had only a polling-attempt counter.
                "rejected_total": 27,
                "processed_blob_shas": [],
                "events": [],
                "subsystems": {},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    sync = EvolutionRemoteSync(
        tmp_path,
        interval_seconds=30,
        fetch_json=lambda _url: [],
        fetch_bytes=lambda _url: b"",
        enabled=True,
    )
    state = sync.sync_once()

    assert state["status"] == "green"
    assert state["rejected_total"] == 0
    assert state["current_rejected_count"] == 0
    assert state["legacy_rejection_attempt_total"] == 27

    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["rejected_total"] == 0
    assert persisted["legacy_rejection_attempt_total"] == 27
    assert persisted["rejected_history_blob_shas"] == []


def test_validator_revision_change_retries_known_bad_blob_without_double_count(
    tmp_path,
):
    payload = {"schema_version": "wrong"}
    raw = (json.dumps(payload, sort_keys=True) + "\n").encode()
    sha = _git_blob_sha(raw)
    listing = [{
        "type": "file",
        "name": "validator-retry.json",
        "path": REMOTE_ROOT + "/validator-retry.json",
        "sha": sha,
        "url": "fixture://validator-retry",
    }]
    fetches = {"bytes": 0}

    def fetch_bytes(_url):
        fetches["bytes"] += 1
        return raw

    sync = EvolutionRemoteSync(
        tmp_path,
        interval_seconds=30,
        fetch_json=lambda _url: listing,
        fetch_bytes=fetch_bytes,
        enabled=True,
    )
    first = sync.sync_once()
    assert first["rejected_total"] == 1
    assert first["current_rejected_count"] == 1
    assert fetches["bytes"] == 1

    state_path = tmp_path / "audit" / "mcp_evolution_sync.json"
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    persisted["validator_revision"] = "legacy-validator"
    state_path.write_text(
        json.dumps(persisted, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    retried = sync.sync_once()

    assert retried["status"] == "degraded"
    assert retried["validator_revision"] == VALIDATOR_REVISION
    assert retried["rejected_total"] == 1
    assert retried["current_rejected_count"] == 1
    assert fetches["bytes"] == 2


def test_event_id_cannot_be_rebound_to_different_git_blob(tmp_path):
    current = {
        "payload": event_payload(
            event_id="immutable-event-id",
            summary="original immutable receipt",
        )
    }

    def raw():
        return (
            json.dumps(current["payload"], sort_keys=True) + "\n"
        ).encode()

    def listing(_url):
        payload = raw()
        return [{
            "type": "file",
            "name": "immutable.json",
            "path": REMOTE_ROOT + "/immutable.json",
            "sha": _git_blob_sha(payload),
            "url": "fixture://immutable",
        }]

    sync = EvolutionRemoteSync(
        tmp_path,
        interval_seconds=30,
        fetch_json=listing,
        fetch_bytes=lambda _url: raw(),
        enabled=True,
    )

    first = sync.sync_once()
    assert first["status"] == "green"
    assert first["ingested_total"] == 1
    assert first["events"][0]["summary"] == "original immutable receipt"

    current["payload"] = event_payload(
        event_id="immutable-event-id",
        summary="mutated receipt under reused event id",
    )
    collision = sync.sync_once()

    assert collision["status"] == "degraded"
    assert collision["ingested_total"] == 1
    assert collision["rejected_total"] == 1
    assert collision["current_rejected_count"] == 1
    assert collision["events"][0]["summary"] == "original immutable receipt"
    assert "already bound to a different immutable Git blob" in (
        collision["last_error"]
    )


def test_event_id_binding_survives_display_history_truncation(tmp_path):
    current = {
        "payload": event_payload(
            event_id="long-lived-immutable-event-id",
            summary="original bound event",
        )
    }

    def raw():
        return (
            json.dumps(current["payload"], sort_keys=True) + "\n"
        ).encode()

    def listing(_url):
        payload = raw()
        return [{
            "type": "file",
            "name": "long-lived.json",
            "path": REMOTE_ROOT + "/long-lived.json",
            "sha": _git_blob_sha(payload),
            "url": "fixture://long-lived",
        }]

    sync = EvolutionRemoteSync(
        tmp_path,
        interval_seconds=30,
        fetch_json=listing,
        fetch_bytes=lambda _url: raw(),
        enabled=True,
    )
    first = sync.sync_once()
    assert first["status"] == "green"

    # Simulate this old event falling out of the bounded UI/history window.
    state_path = tmp_path / "audit" / "mcp_evolution_sync.json"
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    persisted["events"] = []
    state_path.write_text(
        json.dumps(persisted, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    current["payload"] = event_payload(
        event_id="long-lived-immutable-event-id",
        summary="attempted historical rewrite",
    )
    collision = sync.sync_once()

    assert collision["status"] == "degraded"
    assert collision["ingested_total"] == 1
    assert collision["rejected_total"] == 1
    assert collision["events"] == []
    assert "already bound to a different immutable Git blob" in (
        collision["last_error"]
    )


def test_blob_sha_mismatch_is_retryable_integrity_failure(tmp_path):
    payload = event_payload()
    raw = (json.dumps(payload, sort_keys=True) + "\n").encode()
    listing = [{
        "type": "file",
        "name": "fixture.json",
        "path": REMOTE_ROOT + "/fixture.json",
        "sha": "b" * 40,
        "url": "fixture://event",
    }]
    fetches = {"bytes": 0}

    def fetch_bytes(_url):
        fetches["bytes"] += 1
        return raw

    sync = EvolutionRemoteSync(
        tmp_path,
        interval_seconds=30,
        fetch_json=lambda _url: listing,
        fetch_bytes=fetch_bytes,
        enabled=True,
    )
    first = sync.sync_once()
    second = sync.sync_once()

    assert first["status"] == "degraded"
    assert first["rejected_total"] == 0
    assert first["current_rejected_count"] == 0
    assert first["ingested_total"] == 0
    assert "Git blob SHA mismatch" in first["last_error"]

    assert second["status"] == "degraded"
    assert second["rejected_total"] == 0
    assert second["current_rejected_count"] == 0
    assert fetches["bytes"] == 2


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


def test_every_registered_brain_subsystem_is_evolution_ingestible(tmp_path):
    subsystem_ids = [row["id"] for row in SUBSYSTEMS]
    sync = make_sync(
        tmp_path,
        event_payload(
            subsystems=subsystem_ids,
            title="Brain registry compatibility fixture",
        ),
    )
    state = sync.sync_once()

    assert state["status"] == "green"
    assert state["rejected_total"] == 0
    assert {
        subsystem_id.replace("_", "-")
        for subsystem_id in subsystem_ids
    } <= set(state["subsystems"])


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
        declared_schema = payload.get("schema_version")
        if declared_schema is None:
            declared_schema = payload.get("schema")
        if declared_schema != "icarus-interface-event-v1":
            assert declared_schema in _IGNORED_SCHEMA_VERSIONS, (
                f"{path.name} introduces an unregistered shared-directory "
                f"schema: {declared_schema!r}"
            )
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


def test_evolution_ui_separates_current_invalid_from_historical_rejects():
    ui = (
        Path(__file__).resolve().parents[1]
        / "icarus_engine"
        / "evolution-ui.js"
    ).read_text(encoding="utf-8")

    assert "Current invalid receipts" in ui
    assert "current_rejected_count" in ui
    assert "Rejected versions total" in ui
    assert "unique versions since dedupe accounting" in ui
    assert "legacy attempts" in ui
    assert "counted only once" in ui


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
    brain = brain_snapshot(tmp_path)
    staged_brain_events = [
        row for row in brain["events"]
        if row["kind"] == "subsystem"
    ]
    assert staged_brain_events
    assert {row["status"] for row in staged_brain_events} == {"observed"}

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
