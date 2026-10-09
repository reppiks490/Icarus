"""Synthetic connector receipts test integrity, not empirical market evidence."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3

import pytest

from icarus_engine.brain import brain_snapshot
from icarus_engine import unusual_whales_intake as intake


NOW = datetime(2026, 10, 8, 17, 0, tzinfo=timezone.utc)
RAW = b'{"data":[{"date":"2026-10-07","value":"synthetic-private-value"}]}\n'


def manifest(**changes):
    result = {
        "observation_id": "test-yield-curve-1",
        "tool": "mcp__codex_apps__unusual_whales_get_yield_curve",
        "retrieved_at": "2026-10-08T16:59:00Z",
        "parameters": {},
        "result_status": "OBSERVED",
    }
    result.update(changes)
    return result


def observe(root, raw=RAW, **changes):
    return intake.observe(root, raw, manifest(**changes), now=lambda: NOW)


def symlink(path, target, *, directory=False):
    try:
        path.symlink_to(target, target_is_directory=directory)
    except OSError as error:
        if os.name == "nt" and getattr(error, "winerror", None) == 1314:
            pytest.skip("Windows runner does not permit symlink creation")
        raise


def test_native_consumer_receives_hash_bound_learning_metadata(tmp_path):
    result = observe(tmp_path)
    snapshot = brain_snapshot(tmp_path)
    assert len(snapshot["events"]) == 1
    event = snapshot["events"][0]
    assert event["kind"] == "learning"
    assert event["status"] == "observed"
    details = event["details"]
    assert details["raw_sha256"] == hashlib.sha256(RAW).hexdigest()
    assert details["raw_size_bytes"] == len(RAW)
    assert details["tool"] == manifest()["tool"]
    assert details["family"] == "macro_and_calendar"
    assert details["rights"] == {"retention": "UNKNOWN", "redistribution": "UNKNOWN", "training": "UNKNOWN"}
    assert details["available_at"] is None
    assert details["point_in_time_eligible"] is False
    assert details["candidate_evidence_eligible"] is False
    assert details["raw_payload_persisted"] is False
    assert event["execution_authorized"] is False
    assert event["production_decision_authorized"] is False
    assert result["delivery_status"] == "DELIVERED"


def test_exact_original_bytes_define_digest_and_private_values_are_not_persisted(tmp_path):
    result = observe(tmp_path, parameters={"ticker": "PRIVATE_SYMBOL"})
    assert result["receipt"]["raw_sha256"] == hashlib.sha256(RAW).hexdigest()
    for file in tmp_path.rglob("*"):
        if file.is_file():
            data = file.read_bytes()
            assert b"synthetic-private-value" not in data
            assert b"PRIVATE_SYMBOL" not in data
    with pytest.raises(ValueError, match="conflict"):
        observe(tmp_path, raw=RAW.rstrip())
    assert len(brain_snapshot(tmp_path)["events"]) == 1


def test_duplicate_and_reopen_are_idempotent(tmp_path):
    first = observe(tmp_path)
    second = observe(tmp_path)
    assert second["idempotent"] is True
    assert first["brain_event_id"] == second["brain_event_id"]
    assert len(brain_snapshot(tmp_path)["events"]) == 1
    assert intake.resume_pending(tmp_path) == []


@pytest.mark.parametrize("changes", [
    {"tool": "get_central_bank_rates"},
    {"parameters": {"ticker": "OTHER"}},
    {"retrieved_at": "2026-10-08T16:58:00Z"},
    {"result_status": "EMPTY"},
])
def test_observation_identity_conflicts_never_append_second_event(tmp_path, changes):
    observe(tmp_path)
    with pytest.raises(ValueError, match="conflict"):
        observe(tmp_path, **changes)
    assert len(brain_snapshot(tmp_path)["events"]) == 1


def test_pending_receipt_precedes_brain_append_and_recovers_after_failure(tmp_path, monkeypatch):
    real = intake.record_brain_event

    def fail(base_dir, event):
        with sqlite3.connect(tmp_path / ".unusual_whales_intake" / "observations.sqlite3") as db:
            assert db.execute("SELECT delivery_status FROM observations").fetchone()[0] == "PENDING"
        raise OSError("synthetic journal unavailable")

    monkeypatch.setattr(intake, "record_brain_event", fail)
    with pytest.raises(OSError):
        observe(tmp_path)
    assert brain_snapshot(tmp_path)["events"] == []
    monkeypatch.setattr(intake, "record_brain_event", real)
    resumed = intake.resume_pending(tmp_path)
    assert len(resumed) == 1
    assert resumed[0]["delivery_status"] == "DELIVERED"
    assert len(brain_snapshot(tmp_path)["events"]) == 1


def test_crash_after_brain_append_before_delivery_commit_does_not_duplicate(tmp_path, monkeypatch):
    real = intake.record_brain_event

    def append_then_fail(base_dir, event):
        real(base_dir, event)
        raise OSError("synthetic crash after append")

    monkeypatch.setattr(intake, "record_brain_event", append_then_fail)
    with pytest.raises(OSError):
        observe(tmp_path)
    assert len(brain_snapshot(tmp_path)["events"]) == 1
    monkeypatch.setattr(intake, "record_brain_event", real)
    assert intake.resume_pending(tmp_path)[0]["delivery_status"] == "DELIVERED"
    assert len(brain_snapshot(tmp_path)["events"]) == 1


@pytest.mark.parametrize("field,value", [
    ("retrieved_at", None), ("retrieved_at", "2026-10-08T16:59:00"),
    ("retrieved_at", "invalid"), ("retrieved_at", "2026-10-08T17:00:00.000001Z"),
    ("source_observed_at", "2026-10-08T17:01:00Z"),
    ("available_at", "2026-10-08T17:00:00Z"),
    ("available_at", "2026-10-08T16:58:00"),
])
def test_invalid_or_future_clocks_fail_before_storage(tmp_path, field, value):
    with pytest.raises(ValueError):
        observe(tmp_path, **{field: value})
    assert not (tmp_path / ".unusual_whales_intake").exists()


def test_injected_clock_must_be_aware_datetime(tmp_path):
    for invalid in [datetime(2026, 10, 8, 17, 0), "2026-10-08T17:00:00Z", None]:
        with pytest.raises(ValueError, match="clock"):
            intake.observe(tmp_path, RAW, manifest(), now=lambda: invalid)
    assert not (tmp_path / ".unusual_whales_intake").exists()


def test_declared_source_clocks_remain_unverified_and_do_not_grant_pit(tmp_path):
    result = observe(tmp_path, source_observed_at="2026-10-07T16:00:00Z", available_at="2026-10-07T16:01:00Z")
    receipt = result["receipt"]
    assert receipt["source_observed_at"] == "2026-10-07T16:00:00Z"
    assert receipt["availability_status"] == "DECLARED_UNVERIFIED"
    assert receipt["point_in_time_eligible"] is False


@pytest.mark.parametrize("status,brain_status", [
    ("EMPTY", "degraded"), ("DENIED", "blocked"), ("ERROR", "blocked"),
    ("TRANSFORMED_ONLY", "degraded"), ("UNCLASSIFIED", "unverified"),
])
def test_partial_empty_denied_and_transformed_results_are_honest(tmp_path, status, brain_status):
    result = observe(tmp_path, result_status=status)
    event = brain_snapshot(tmp_path)["events"][0]
    assert event["status"] == brain_status
    assert result["receipt"]["coverage_status"] == "UNKNOWN"
    assert result["receipt"]["eligible_rows_denominator"] is None
    assert result["receipt"]["candidate_evidence_eligible"] is False


@pytest.mark.parametrize("tool", ["settings_update", "settings_read", "open_unusual_whales", "get_api_examples", "query_internal_knowledge", "made_up"])
def test_non_empirical_and_mutating_tools_cannot_become_observations(tmp_path, tool):
    with pytest.raises(ValueError, match="tool"):
        observe(tmp_path, tool=tool)
    assert not (tmp_path / ".unusual_whales_intake").exists()


@pytest.mark.parametrize("changes", [
    {"raw_sha256": "0" * 64}, {"execution_authorized": True},
    {"retention_mode": "RAW"}, {"rights": {"training": "LICENSED"}},
    {"parameters": {"nested": {"api_key": "synthetic-secret"}}},
    {"parameters": {"ticker": float("nan")}}, {"reported_row_count": True},
    {"reported_row_count": -1}, {"result_status": "VERIFIED"}, {"result_status": []},
])
def test_manifest_cannot_inject_authority_rights_or_bad_hash_and_values(tmp_path, changes):
    with pytest.raises(ValueError):
        observe(tmp_path, **changes)
    assert not (tmp_path / ".unusual_whales_intake").exists()


def test_private_directory_permissions_and_symlink_rejection(tmp_path):
    observe(tmp_path)
    if os.name == "posix":
        assert (tmp_path / ".unusual_whales_intake").stat().st_mode & 0o077 == 0
        assert (tmp_path / ".unusual_whales_intake" / "observations.sqlite3").stat().st_mode & 0o077 == 0
    other = tmp_path / "other"
    other.mkdir()
    symlink(other / ".unusual_whales_intake", tmp_path / ".unusual_whales_intake", directory=True)
    with pytest.raises(ValueError, match="symlink"):
        observe(other)


def test_repository_directory_is_not_a_private_runtime(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    child = tmp_path / "private-looking"
    with pytest.raises(ValueError, match="repository"):
        observe(child)
    assert not child.exists()


@pytest.mark.parametrize("component", ["audit", "audit/brain_events.jsonl", ".unusual_whales_intake/observations.sqlite3"])
def test_all_persistence_planes_reject_symlink_escape(tmp_path, component):
    outside = tmp_path / "outside"
    outside.mkdir()
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    target = runtime / component
    target.parent.mkdir(parents=True, exist_ok=True)
    if component == "audit":
        symlink(target, outside, directory=True)
    else:
        external = outside / "must-stay-unchanged"
        external.write_bytes(b"original")
        symlink(target, external)
    with pytest.raises(ValueError, match="symlink"):
        observe(runtime)
    assert not (outside / "brain_events.jsonl").exists()
    assert all(file.read_bytes() == b"original" for file in outside.iterdir())


def test_runtime_and_both_journals_are_private_even_with_permissive_umask(tmp_path):
    runtime = tmp_path / "new-private-runtime"
    previous = os.umask(0)
    try:
        observe(runtime)
    finally:
        os.umask(previous)
    if os.name == "posix":
        for path in [runtime, runtime / "audit", runtime / "audit" / "brain_events.jsonl",
                     runtime / ".unusual_whales_intake", runtime / ".unusual_whales_intake" / "observations.sqlite3"]:
            assert path.stat().st_mode & 0o077 == 0


@pytest.mark.skipif(os.name != "posix", reason="POSIX permissions do not establish Windows ACLs")
def test_existing_public_runtime_is_rejected_before_persistence(tmp_path):
    runtime = tmp_path / "public-runtime"
    runtime.mkdir(mode=0o755)
    runtime.chmod(0o755)
    with pytest.raises(ValueError, match="group or other"):
        observe(runtime)
    assert not (runtime / "audit").exists()


@pytest.mark.parametrize("component", ["audit/brain_events.jsonl", ".unusual_whales_intake/observations.sqlite3"])
def test_hard_linked_persistence_files_are_rejected(tmp_path, component):
    runtime = tmp_path / "runtime"
    runtime.mkdir(mode=0o700)
    external = tmp_path / "must-stay-unchanged"
    external.write_bytes(b"original")
    target = runtime / component
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(external, target)
    except OSError as error:
        pytest.skip(f"Hard links are not available on this filesystem: {error}")
    with pytest.raises(ValueError, match="hard links"):
        observe(runtime)
    assert external.read_bytes() == b"original"


def test_parallel_retries_share_one_immutable_receipt_and_brain_event(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: observe(tmp_path), range(8)))
    assert len({result["brain_event_id"] for result in results}) == 1
    assert len(brain_snapshot(tmp_path)["events"]) == 1
    assert intake.resume_pending(tmp_path) == []


def test_capability_map_accounts_for_all_tools_once():
    path = Path(__file__).parents[1] / "docs" / "research" / "unusual-whales-capability-map.json"
    mapped = json.loads(path.read_text())
    tools = [tool for row in mapped["families"].values() for tool in row["tools"]]
    assert len(tools) == len(set(tools)) == mapped["exposed_tool_count"] == 100
    assert set(tools) == set(intake.TOOL_FAMILIES)
    for family, row in mapped["families"].items():
        assert all(intake.TOOL_FAMILIES[tool] == family for tool in row["tools"])
