import shutil
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
from tempfile import TemporaryDirectory

from icarus_engine.access_control import AccessRegistry, AccessUnavailable
from tests_engine.test_workspace_api import workspace_http  # noqa: F401
from icarus_engine.ascendancy.autopilot import GovernorAutopilot
from icarus_engine.ascendancy.foundry import CandidateFoundry
from icarus_engine.psi_evidence import PsiEvidenceLedger
from icarus_engine.source_reliability import SourceReliabilityStore


def test_authentication_does_not_wait_for_access_activity_database_writer(tmp_path):
    registry = AccessRegistry(tmp_path, "owner-token")
    writer = sqlite3.connect(registry.path)
    writer.execute("BEGIN IMMEDIATE")
    result = []
    finished = threading.Event()
    def authenticate():
        try:
            result.append(registry.authenticate("owner-token"))
        finally:
            finished.set()
    thread = threading.Thread(target=authenticate)
    thread.start()
    try:
        assert finished.wait(.4), "activity logging held authentication behind SQLite writes"
        assert result[0]["role"] == "owner"
    finally:
        writer.rollback()
        writer.close()
        thread.join(2)


def test_owner_rotation_and_viewer_revocation_remain_authoritative(tmp_path):
    registry = AccessRegistry(tmp_path, "owner-token")
    viewer = registry.add("observer")
    assert registry.authenticate(viewer["token"])["role"] == "viewer"
    assert registry.kick(viewer["id"])
    assert registry.authenticate(viewer["token"]) is None
    rotated = AccessRegistry(tmp_path, "new-owner-token")
    assert rotated.authenticate("owner-token") is None
    assert rotated.authenticate("new-owner-token")["role"] == "owner"
    assert registry.authenticate("owner-token") is None


def test_external_revocation_and_authority_failure_do_not_trust_cached_credentials(tmp_path):
    registry = AccessRegistry(tmp_path, "owner-token")
    viewer = registry.add("observer")
    assert registry.authenticate(viewer["token"])["role"] == "viewer"
    with sqlite3.connect(registry.path) as db:
        db.execute("UPDATE users SET active=0 WHERE id=?", (viewer["id"],))
    assert registry.authenticate(viewer["token"]) is None
    assert registry.is_active_token(viewer["token"]) is False
    registry.path.write_bytes(b"not a SQLite authority")
    started = time.monotonic()
    with pytest.raises(AccessUnavailable):
        registry.authenticate("owner-token")
    assert time.monotonic() - started < .5


def test_unknown_authority_role_fails_closed_for_direct_and_phone_reads(tmp_path):
    registry = AccessRegistry(tmp_path, "owner-token")
    with sqlite3.connect(registry.path) as db:
        db.execute("UPDATE users SET role='unknown' WHERE id='owner'")
    with pytest.raises(AccessUnavailable):
        registry.authenticate("owner-token")
    with pytest.raises(AccessUnavailable):
        registry.is_active_token("owner-token")


def test_parallel_actual_http_reads_do_not_wait_behind_activity_writer(workspace_http):
    server, parent, request = workspace_http
    writer = sqlite3.connect(parent.base_dir + "/access_registry.sqlite3")
    writer.execute("BEGIN IMMEDIATE")
    paths = ("/status/public", "/api/command-centers/cc1/status", "/api/workspace-runtime",
             "/_internal/access/validate")
    try:
        began = time.monotonic()
        with ThreadPoolExecutor(max_workers=4) as pool:
            responses = list(pool.map(request, paths))
        assert all(response[0] == 200 for response in responses), responses
        assert time.monotonic() - began < 1, "parallel auth waited for activity database writes"
    finally:
        writer.rollback()
        writer.close()
    assert request("/status/public")[0] == 200


def test_exclusive_authority_lock_returns_prompt_503_then_automatically_recovers(workspace_http):
    _, parent, request = workspace_http
    writer = sqlite3.connect(parent.base_dir + "/access_registry.sqlite3")
    writer.execute("BEGIN EXCLUSIVE")
    try:
        began = time.monotonic()
        code, data, _ = request("/status/public")
        assert code == 503 and data["error"] == "ACCESS_AUTHORITY_UNAVAILABLE", data
        assert time.monotonic() - began < .5
        assert request("/healthz")[0] == 200
        assert request("/_internal/access/validate")[0] == 503
    finally:
        writer.rollback()
        writer.close()
    assert request("/status/public")[0] == 200


def test_bounded_audit_batches_preserve_counts_retry_busy_storage_and_drain(tmp_path):
    registry = AccessRegistry(tmp_path, "owner-token")
    for _ in range(40):
        assert registry.authenticate("owner-token")["role"] == "owner"
    for _ in range(3):
        registry.failed_auth()
    writer = sqlite3.connect(registry.path)
    writer.execute("BEGIN IMMEDIATE")
    try:
        assert registry.flush() is False
        pending = registry.audit_status()
        assert pending["pending_requests"] == 43
        assert pending["error"] == "AUDIT_STORAGE_UNAVAILABLE"
        for number in range(1000):
            registry.failed_auth("rejected reason " + str(number))
        assert registry.audit_status()["pending_groups"] <= 130
    finally:
        writer.rollback()
        writer.close()
    registry.start()
    registry.start()
    deadline = time.monotonic() + 2
    while registry.audit_status()["pending_requests"] and time.monotonic() < deadline:
        time.sleep(.01)
    registry.close()
    assert not registry._thread.is_alive()
    snapshot = registry.snapshot()
    assert snapshot["activity_audit"]["pending_requests"] == 0
    assert snapshot["activity_audit"]["error"] is None
    assert snapshot["activity_audit"]["overflow_coalesced_requests"] > 0
    assert snapshot["activity_summary"]["authenticated_requests_24h"] == 40
    assert snapshot["activity_summary"]["failed_auth_24h"] == 1003
    owner = next(row for row in snapshot["users"] if row["role"] == "owner")
    assert owner["request_count"] == 40
    assert all("owner-token" not in str(row) for row in snapshot["events"])


def test_access_registry_closes_sqlite_handles_before_directory_removal():
    with TemporaryDirectory() as directory:
        registry = AccessRegistry(directory, "owner-token")
        assert registry.authenticate("owner-token")["role"] == "owner"
        viewer = registry.add("reviewer")
        assert registry.authenticate(viewer["token"])["role"] == "viewer"
        assert registry.kick(viewer["id"])
        registry.failed_auth()
        registry.snapshot()

        # This raises WinError 32 on Windows if any short-lived connection is
        # left open; TemporaryDirectory cleanup then becomes deterministic.
        shutil.rmtree(directory)


def test_ascendancy_autopilot_closes_sqlite_handles_before_directory_removal():
    with TemporaryDirectory() as directory:
        autopilot = GovernorAutopilot(
            directory,
            plan_callback=lambda: {},
            execute_callback=lambda _action: {},
            enabled=False,
        )
        autopilot.status()

        # The same Windows file-lock check covers the WAL-backed status store.
        shutil.rmtree(directory)


def test_source_reliability_closes_sqlite_handles_before_directory_removal():
    with TemporaryDirectory() as directory:
        store = SourceReliabilityStore(directory)
        store.snapshot()
        shutil.rmtree(directory)


def test_candidate_foundry_closes_sqlite_handles_before_directory_removal():
    with TemporaryDirectory() as directory:
        store = CandidateFoundry(directory)
        assert store.journal_mode == "wal"
        shutil.rmtree(directory)


def test_psi_evidence_closes_sqlite_handles_before_directory_removal():
    with TemporaryDirectory() as directory:
        ledger = PsiEvidenceLedger(directory)
        assert ledger.active("NQ", as_of_ts=1.0) == {}
        shutil.rmtree(directory)
