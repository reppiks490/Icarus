from __future__ import annotations

import json

import pytest

from icarus_engine.system_audit import (
    DEFAULT_REPOSITORY_AUDIT,
    LoopIntelligenceSync,
    collect_loop_snapshot,
    git_blob_sha,
    load_repository_audit,
    normalize_repository_audit,
    repository_audit_path,
    save_repository_audit,
)


def test_repository_audit_defaults_are_visible_without_runtime_file(tmp_path):
    out = load_repository_audit(tmp_path)
    assert out["status"] == "green"
    assert out["main"]["sha"] == DEFAULT_REPOSITORY_AUDIT["main"]["sha"]
    assert out["summary"]["current_head_failures"] == 0
    assert out["storage"]["source"] == "bundled-default"


def test_repository_audit_persists_atomically_and_round_trips(tmp_path):
    payload = {
        "repository": "reppiks490/Icarus",
        "source": "test-mcp",
        "status": "warn",
        "recorded_at": "2026-10-01T02:10:00Z",
        "main": {"sha": "abc123", "workflow_run": 42, "linux": "success", "windows": "success"},
        "summary": {"branches_audited": 3, "current_head_failures": 0, "pending": 1, "unresolved": 0},
        "checks": [{"name": "branch-x", "status": "queued", "detail": "waiting for exact-head run"}],
        "issue": {"number": 62, "url": "https://github.com/reppiks490/Icarus/issues/62"},
        "note": "test",
    }
    saved = save_repository_audit(tmp_path, payload)
    assert saved["storage"]["source"] == "runtime"
    path = repository_audit_path(tmp_path)
    assert path.exists()
    assert not list(tmp_path.glob(".repository_audit.json.*.tmp"))
    assert json.loads(path.read_text(encoding="utf-8"))["status"] == "warn"

    loaded = load_repository_audit(tmp_path)
    assert loaded["status"] == "warn"
    assert loaded["main"]["workflow_run"] == 42
    assert loaded["summary"]["pending"] == 1
    assert loaded["checks"][0]["name"] == "branch-x"


@pytest.mark.parametrize("bad", [None, [], "green"])
def test_repository_audit_requires_object(bad):
    with pytest.raises(ValueError):
        normalize_repository_audit(bad)


def test_repository_audit_rejects_invalid_status_and_negative_counts():
    with pytest.raises(ValueError):
        normalize_repository_audit({"status": "perfect"})
    with pytest.raises(ValueError):
        normalize_repository_audit({"status": "green", "summary": {"current_head_failures": -1}})


def test_repository_audit_normalizes_loop_receipts_and_mcp_events():
    payload = {
        "status": "warn",
        "loops": [{
            "id": "alpha-synthesis",
            "title": "Alpha Synthesis Evolution",
            "scheduler_id": "sched-alpha",
            "schedule": ":25 hourly",
            "status": "RUN_PERSISTED",
            "run_id": "alpha-synthesis-20261001T012500Z",
            "recorded_at": "2026-10-01T01:26:00Z",
            "repository": "reppiks490/Icarus-engine",
            "finalization_commit_sha": "abc123",
            "finalization_state_blob_sha": "def456",
            "detail": "durability verified",
        }],
        "events": [{
            "id": "evt-1",
            "kind": "repair",
            "severity": "success",
            "title": "Alpha durability repaired",
            "detail": "Restored matching finalization and heartbeat receipts.",
            "recorded_at": "2026-10-01T01:27:00Z",
            "repository": "reppiks490/Icarus-engine",
            "ref": "abc123",
        }],
    }
    out = normalize_repository_audit(payload)
    assert out["schema_version"] == 2
    assert out["execution_authorized"] is False
    assert out["loops"][0]["id"] == "alpha-synthesis"
    assert out["loops"][0]["status"] == "RUN_PERSISTED"
    assert out["events"][0]["kind"] == "repair"
    assert out["events"][0]["severity"] == "success"


def test_repository_audit_rejects_bad_system_event_enums():
    with pytest.raises(ValueError):
        normalize_repository_audit({"events": [{"kind": "trade", "title": "bad"}]})
    with pytest.raises(ValueError):
        normalize_repository_audit({"events": [{"kind": "audit", "severity": "panic", "title": "bad"}]})


def test_git_blob_sha_matches_git_object_encoding():
    raw = b'{"RUN_ID":"alpha-synthesis-20261001T022500Z"}'
    import hashlib
    expected = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    assert git_blob_sha(raw) == expected


def test_collect_loop_snapshot_verifies_exact_receipt_and_extracts_signals():
    final = {
        "schema_version": "scheduler-finalization-v5.7",
        "RUN_ID": "alpha-synthesis-20261001T022500Z",
        "RUN_STATUS": "RUN_PERSISTED",
        "completion_semantics": "DURABILITY_RECEIPT_ONLY",
        "work_status": "BASELINE_PERSISTED",
        "payload": {
            "result": "NEW_EVIDENCE",
            "NET_NEW_DELTA": 4,
            "NEXT": "Evaluate cost sensitivity",
            "findings": ["cost model advanced"],
        },
        "execution_authorized": False,
    }
    final_raw = json.dumps(final, sort_keys=True).encode()
    blob = git_blob_sha(final_raw)
    heartbeat = {
        "RUN_ID": final["RUN_ID"],
        "RUN_STATUS": "RUN_PERSISTED",
        "scheduler_id": "sched-alpha",
        "finalization_commit_sha": "commit-alpha",
        "finalization_state_blob_sha": blob,
        "execution_authorized": False,
    }
    latest = {
        "RUN_ID": final["RUN_ID"],
        "findings": ["bootstrap stable"],
        "risks": ["cost uncertainty"],
        "NEXT": "Stress test",
        "ignored_chatty_field": "x" * 5000,
    }
    spec = {
        "id": "alpha-synthesis",
        "title": "Alpha Synthesis Evolution",
        "scheduler_id": "sched-alpha",
        "schedule": ":25 hourly",
        "repository": "owner/repo",
        "root": "automation/alpha",
    }
    files = {
        ("owner/repo", "main", "automation/alpha/finalization_state.json"): final_raw,
        ("owner/repo", "main", "automation/alpha/heartbeat.json"): json.dumps(heartbeat).encode(),
        ("owner/repo", "commit-alpha", "automation/alpha/finalization_state.json"): final_raw,
        ("owner/repo", "main", "automation/alpha/latest.json"): json.dumps(latest).encode(),
    }

    def fetch(repo, ref, path):
        if (repo, ref, path) not in files:
            raise FileNotFoundError(path)
        return files[(repo, ref, path)]

    row, event = collect_loop_snapshot(spec, fetch_bytes=fetch)
    assert row["status"] == "RUN_PERSISTED"
    assert row["run_id"] == final["RUN_ID"]
    assert row["finalization_state_blob_sha"] == blob
    assert row["verification"]["commit_blob_matches"] is True
    assert row["signals"]["finalization"]["payload"]["NET_NEW_DELTA"] == 4
    assert row["signals"]["latest"]["risks"] == ["cost uncertainty"]
    assert "ignored_chatty_field" not in row["signals"]["latest"]
    assert event["severity"] == "success"
    assert event["ref"] == "commit-alpha"
    assert "NEW_EVIDENCE" in event["detail"]
    assert "cost model advanced" in event["detail"]


def test_collect_loop_snapshot_fails_closed_on_blob_mismatch():
    final = {
        "RUN_ID": "flow-20261001T023500Z",
        "RUN_STATUS": "RUN_PERSISTED",
        "payload": {"result": "NO_NEW_EVIDENCE_YET"},
        "execution_authorized": False,
    }
    final_raw = json.dumps(final).encode()
    heartbeat = {
        "RUN_ID": final["RUN_ID"],
        "RUN_STATUS": "RUN_PERSISTED",
        "scheduler_id": "sched-flow",
        "finalization_commit_sha": "commit-flow",
        "finalization_state_blob_sha": "0" * 40,
        "execution_authorized": False,
    }
    spec = {
        "id": "flow",
        "title": "Microstructure Sensor Grid",
        "scheduler_id": "sched-flow",
        "schedule": ":35 hourly",
        "repository": "owner/repo",
        "root": "automation/flow",
    }
    files = {
        ("owner/repo", "main", "automation/flow/finalization_state.json"): final_raw,
        ("owner/repo", "main", "automation/flow/heartbeat.json"): json.dumps(heartbeat).encode(),
        ("owner/repo", "commit-flow", "automation/flow/finalization_state.json"): final_raw,
    }

    def fetch(repo, ref, path):
        if (repo, ref, path) not in files:
            raise FileNotFoundError(path)
        return files[(repo, ref, path)]

    row, event = collect_loop_snapshot(spec, fetch_bytes=fetch)
    assert row["status"] == "RECEIPT_MISMATCH"
    assert row["verification"]["current_blob_matches"] is False
    assert event["severity"] == "error"


def test_loop_intelligence_sync_updates_runtime_state_and_deduplicates_events(tmp_path):
    final = {
        "RUN_ID": "robustness-guardian-20261001T030500Z",
        "RUN_STATUS": "RUN_PERSISTED",
        "payload": {"result": "NO_NEW_EVIDENCE_YET", "NEXT": "Continue"},
        "execution_authorized": False,
    }
    final_raw = json.dumps(final).encode()
    blob = git_blob_sha(final_raw)
    heartbeat = {
        "RUN_ID": final["RUN_ID"],
        "RUN_STATUS": "RUN_PERSISTED",
        "scheduler_id": "sched-rg",
        "finalization_commit_sha": "commit-rg",
        "finalization_state_blob_sha": blob,
        "execution_authorized": False,
    }
    spec = {
        "id": "robustness-guardian",
        "title": "Robustness Guardian Evolution",
        "scheduler_id": "sched-rg",
        "schedule": ":05 hourly",
        "repository": "owner/repo",
        "root": "automation/rg",
    }
    files = {
        ("owner/repo", "main", "automation/rg/finalization_state.json"): final_raw,
        ("owner/repo", "main", "automation/rg/heartbeat.json"): json.dumps(heartbeat).encode(),
        ("owner/repo", "commit-rg", "automation/rg/finalization_state.json"): final_raw,
    }

    def fetch(repo, ref, path):
        if (repo, ref, path) not in files:
            raise FileNotFoundError(path)
        return files[(repo, ref, path)]

    sync = LoopIntelligenceSync(tmp_path, specs=[spec], fetch_bytes=fetch, interval_seconds=60)
    first = sync.sync_once()
    second = sync.sync_once()
    assert first["loop_sync"]["status"] == "green"
    assert second["loops"][0]["run_id"] == final["RUN_ID"]
    ids = [x["id"] for x in second["events"]]
    assert ids.count("loop:robustness-guardian:" + final["RUN_ID"]) == 1
    assert second["execution_authorized"] is False


def test_loop_signal_extraction_captures_real_nested_run_core_and_provider_gaps():
    final = {
        "RUN_ID": "apex-council-20261001T034500Z",
        "RUN_STATUS": "RUN_PERSISTED",
        "payload": {"result": "NO_NEW_EVIDENCE_YET"},
        "execution_authorized": False,
    }
    final_raw = json.dumps(final).encode()
    blob = git_blob_sha(final_raw)
    heartbeat = {
        "RUN_ID": final["RUN_ID"],
        "RUN_STATUS": "RUN_PERSISTED",
        "scheduler_id": "sched-apex",
        "finalization_commit_sha": "commit-apex",
        "finalization_state_blob_sha": blob,
        "execution_authorized": False,
    }
    latest = {
        "RUN_ID": "apex-council-20260929T174500Z",
        "RUN_STATUS": "RUN_PERSISTED",
        "RUN_CORE": {
            "findings": ["dependence evidence missing"],
            "built_changes": ["new council guard"],
            "unresolved_risks": ["shared contract collision"],
            "NEXT": "Add auditable dependence semantics",
        },
        "PROVIDER_CONFLICTS": [{"field": "price", "explanation": "different timestamps"}],
        "DATA_GAPS": ["no depth snapshot"],
        "schema_representation_availability_findings": ["schema stable"],
        "irrelevant_blob": "x" * 5000,
    }
    spec = {
        "id": "apex-council",
        "title": "Apex Council Evolution",
        "scheduler_id": "sched-apex",
        "schedule": ":45 hourly",
        "repository": "owner/repo",
        "root": "automation/apex",
    }
    files = {
        ("owner/repo", "main", "automation/apex/finalization_state.json"): final_raw,
        ("owner/repo", "main", "automation/apex/heartbeat.json"): json.dumps(heartbeat).encode(),
        ("owner/repo", "commit-apex", "automation/apex/finalization_state.json"): final_raw,
        ("owner/repo", "main", "automation/apex/latest.json"): json.dumps(latest).encode(),
    }

    def fetch(repo, ref, path):
        if (repo, ref, path) not in files:
            raise FileNotFoundError(path)
        return files[(repo, ref, path)]

    row, _ = collect_loop_snapshot(spec, fetch_bytes=fetch)
    sig = row["signals"]["latest"]
    assert sig["RUN_ID"] == "apex-council-20260929T174500Z"
    assert sig["RUN_CORE"]["findings"] == ["dependence evidence missing"]
    assert sig["RUN_CORE"]["NEXT"] == "Add auditable dependence semantics"
    assert sig["PROVIDER_CONFLICTS"][0]["field"] == "price"
    assert sig["DATA_GAPS"] == ["no depth snapshot"]
    assert sig["schema_representation_availability_findings"] == ["schema stable"]
    assert "irrelevant_blob" not in sig


def test_private_loop_can_fail_over_to_verified_public_ui_mirror():
    spec = {
        "id": "advanced-csv",
        "title": "Advanced CSV Data Collector",
        "scheduler_id": "sched-csv",
        "schedule": ":15 hourly",
        "repository": "private/csv",
        "root": "automation/csv",
        "mirror_repository": "public/engine",
        "mirror_path": "automation_intelligence/ui_feeds/advanced-csv.json",
    }
    mirror = {
        "schema_version": "icarus-ui-loop-feed-v1",
        "loop_id": "advanced-csv",
        "source_repository": "private/csv",
        "RUN_ID": "advanced-csv-20261001T031500Z",
        "RUN_STATUS": "RUN_PERSISTED",
        "scheduler_id": "sched-csv",
        "finalization_commit_sha": "csv-final-commit",
        "finalization_state_blob_sha": "a" * 40,
        "source_verified": True,
        "execution_authorized": False,
        "signals": {
            "latest": {
                "NET_NEW_DELTA": {"corpus": "NO_NEW_CORPUS_EVIDENCE"},
                "conflicts_gaps": ["MNQ overlap unresolved"],
                "PASSES_COMPLETED": 10,
            }
        },
    }
    mirror_raw = json.dumps(mirror).encode()

    def fetch(repo, ref, path):
        if (repo, ref, path) == ("public/engine", "main", spec["mirror_path"]):
            return mirror_raw
        raise FileNotFoundError(path)

    row, event = collect_loop_snapshot(spec, fetch_bytes=fetch)
    assert row["status"] == "RUN_PERSISTED"
    assert row["run_id"] == mirror["RUN_ID"]
    assert row["verification"]["source_mode"] == "verified-public-mirror"
    assert row["signals"]["latest"]["PASSES_COMPLETED"] == 10
    assert event["severity"] == "success"
    assert "mirror" in row["detail"].lower()
