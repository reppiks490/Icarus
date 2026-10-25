"""Actual pinned NEXUS/AION cores behind a cached, scoped runtime boundary."""
from copy import deepcopy
from dataclasses import replace
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
from types import SimpleNamespace

import pytest

from icarus_engine.native_subsystems._divine.aion.contracts import Observation
from icarus_engine.native_subsystems._divine.aion.store import EventStore
from icarus_engine.native_subsystems._divine.nexus.source_health import SourceHealthRegistry
from icarus_engine.subsystem_connections import NativeSubsystemConnections, capture_portfolio


NOW = 1_800_000_000_000_000_000


class Clock:
    def __init__(self):
        self.now = NOW

    def __call__(self):
        return self.now


def portfolio(clock, **changes):
    summary = {"symbol": "NQ", "feed_provider": "fixture", "provider_symbol": "NQ=F",
               "kind": "futures", "bar_index": 10, "last_bar_ts": clock.now / 1e9 - 60,
               "poll_age": 1, "bar_age": 2, "price_age": 1, "warm": True,
               "rewarming": False, "paused": False, "last_error": "", **changes}
    runner = SimpleNamespace(_public_views=((summary, clock.now / 1e9), (None, 0)))
    return SimpleNamespace(runners={"NQ": runner})


def service(tmp_path, clock, port=None, **kwargs):
    port = port or portfolio(clock)
    return NativeSubsystemConnections(tmp_path, workspace_id="main", clock_ns=clock,
        snapshot_supplier=lambda: capture_portfolio(port, now_ns=clock()), **kwargs)


def test_capture_uses_only_published_metadata_without_feed_or_runner_calls():
    clock = Clock()
    port = portfolio(clock, price=123.45, last_error="SECRET failed request", forming={"raw": "SECRET"})
    runner = port.runners["NQ"]
    class Forbidden:
        def __getattribute__(self, _):
            raise AssertionError("provider access is forbidden")
    runner.feed = Forbidden()
    runner.summary = runner.status = lambda: pytest.fail("runner calls are forbidden")
    port.status = lambda: pytest.fail("portfolio calls are forbidden")
    clock.now += 4_000_000_000
    captured = capture_portfolio(port, now_ns=clock())
    asset = captured["assets"][0]
    assert asset["capture_age_seconds"] == 4
    assert asset["poll_age_seconds"] == 5 and asset["bar_age_seconds"] == 6
    assert asset["active_error"] is True
    assert "SECRET" not in json.dumps(captured) and "123.45" not in json.dumps(captured)
    runner._public_views = None
    assert capture_portfolio(port, now_ns=clock())["assets"][0]["state"] == "UNAVAILABLE"


def test_constructor_and_reads_are_io_free_then_actual_cores_observe_and_persist(tmp_path):
    clock = Clock()
    root = tmp_path / "not-created"
    monitor = service(root, clock)
    assert monitor.snapshot()["state"] == "STARTING" and not root.exists()
    monitor.tick()
    snap = monitor.snapshot()
    assert isinstance(monitor._registry, SourceHealthRegistry)
    assert isinstance(monitor._store, EventStore)
    assert snap["state"] == "OBSERVING"
    assert snap["nexus"]["state"] == "UNKNOWN_SLO"
    assert snap["nexus"]["unknown_slo_streams"] == 1
    assert snap["aion"]["chain_verified"] and snap["aion"]["event_count"] == 1
    assert not snap["execution_authorized"] and not snap["production_decision_authorized"]
    store = EventStore(monitor.store_path)
    assert store.asof(clock() - 1) == []
    rows = store.asof(clock())
    event = rows[0]["event"]
    assert event["kind"] == "context" and event["evidence_tier"] == 1
    assert event["available_ns"] == event["ingested_ns"] == clock()
    assert event["availability_basis"] == "observed_receipt" and event["plane"] == "research"
    assert store.sources()[0]["origin"] == "icarus_runtime_monitor"
    assert store.verify_chain()["verified"]
    snap["assets"].clear()
    assert monitor.snapshot()["assets"]
    monitor.close()


def test_stable_and_owned_appends_do_not_rescan_history_but_external_changes_do(tmp_path, monkeypatch):
    clock = Clock()
    port = portfolio(clock)
    monitor = service(tmp_path, clock, port)
    verify = EventStore.verify_chain
    calls = []
    def counted(store):
        calls.append(store.path)
        return verify(store)
    monkeypatch.setattr(EventStore, "verify_chain", counted)
    monitor.tick()
    for _ in range(20):
        clock.now += 1
        port.runners["NQ"]._public_views[0][0]["bar_index"] += 1
        monitor.tick()
    for _ in range(20):
        monitor.tick()
    assert len(calls) == 1, "unchanged reads and locally verified appends must not rescan the growing ledger"
    assert verify(monitor._store)["events"] == 21
    clock.now += 60_000_000_000
    monitor.tick()
    assert len(calls) == 2, "a bounded periodic full check must still verify an unchanged image"
    with sqlite3.connect(monitor.store_path) as db:
        db.execute("DROP TRIGGER events_no_update")
        db.execute("UPDATE events SET event_hash=? WHERE position=1", ("f" * 64,))
    monitor.tick()
    assert len(calls) == 3 and monitor.snapshot()["state"] == "UNAVAILABLE"
    monitor.close()


def test_capture_records_stable_revision_and_rejects_a_mid_capture_scope_change():
    clock = Clock()
    port = portfolio(clock)
    port.workspace = {"id": "cc1", "config_revision": 5}
    captured = capture_portfolio(port, now_ns=clock())
    assert captured["workspace_id"] == "cc1" and captured["observed_config_revision"] == 5
    class ChangingRunners(dict):
        def items(self):
            port.workspace = {"id": "cc1", "config_revision": 6}
            return super().items()
    port.runners = ChangingRunners(port.runners)
    raced = capture_portfolio(port, now_ns=clock())
    assert raced["observed_config_revision"] is None
    assert "CONFIGURATION_CHANGED_DURING_CAPTURE" in raced["warnings"]
    assert raced["assets"][0]["state"] == "UNAVAILABLE"


def test_nested_native_storage_symlink_fails_closed_before_writing_outside(tmp_path):
    clock = Clock()
    base, outside = tmp_path / "runtime", tmp_path / "outside"
    base.mkdir()
    outside.mkdir()
    try:
        (base / "audit").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks unavailable")
    monitor = service(base, clock)
    assert monitor.snapshot()["state"] == "STARTING" and list(outside.iterdir()) == []
    monitor.tick()
    assert monitor.snapshot()["state"] == "UNAVAILABLE"
    assert list(outside.iterdir()) == []
    monitor.close()


def test_dedup_ignores_capture_refresh_and_age_noise_but_records_changes_and_restart(tmp_path):
    clock = Clock()
    port = portfolio(clock)
    monitor = service(tmp_path, clock, port)
    monitor.tick()
    for _ in range(3):
        clock.now += 5_000_000_000
        summary = dict(port.runners["NQ"]._public_views[0][0], poll_age=0.002)
        port.runners["NQ"]._public_views = ((summary, clock.now / 1e9), (None, 0))
        monitor.tick()
    assert monitor.snapshot()["aion"]["event_count"] == 1
    summary["bar_index"] += 1
    monitor.tick()
    assert monitor.snapshot()["aion"]["event_count"] == 2
    summary["last_error"] = "secret provider token"
    monitor.tick()
    assert monitor.snapshot()["aion"]["event_count"] == 3
    monitor.close()
    resumed = service(tmp_path, clock, port)
    resumed.tick()
    snap = resumed.snapshot()
    assert snap["aion"]["event_count"] == snap["aion"]["recovered_event_count"] == 3
    assert "secret provider token" not in json.dumps(snap)
    resumed.close()


def test_restart_recovers_native_context_when_current_capture_is_unavailable(tmp_path):
    clock = Clock()
    monitor = service(tmp_path, clock)
    monitor.tick()
    monitor.close()
    def unavailable():
        raise RuntimeError("SECRET provider content")
    resumed = NativeSubsystemConnections(tmp_path, workspace_id="main", snapshot_supplier=unavailable, clock_ns=clock)
    resumed.tick()
    snap = resumed.snapshot()
    assert snap["state"] == "DEGRADED" and snap["assets"][0]["symbol"] == "NQ"
    assert snap["assets"][0]["state"] == "DEGRADED"
    assert snap["assets"][0]["cache_state"] == "RECOVERED"
    assert snap["aion"]["recovered_event_count"] == 1
    assert "CAPTURE_UNAVAILABLE" in snap["warnings"]
    assert "SECRET" not in json.dumps(snap)
    resumed.close()


def test_recovery_rejects_a_valid_native_chain_with_future_context_evidence(tmp_path):
    clock = Clock()
    monitor = service(tmp_path, clock)
    monitor.tick()
    monitor.close()
    store = EventStore(monitor.store_path)
    event = deepcopy(store.asof(clock())[0]["event"])
    # AION's generic context contract accepts a payload; the receiving adapter
    # must additionally reject NEXUS evidence later than this context receipt.
    event["source_event_id"] = "future-context"
    event["payload"]["nexus_plane"] = SourceHealthRegistry().snapshot(clock() + 60_000_000_000).to_dict()
    store.append(Observation.from_dict(event))
    assert store.verify_chain()["verified"]
    resumed = service(tmp_path, clock)
    resumed.tick()
    assert resumed.snapshot()["state"] == "UNAVAILABLE"
    assert not resumed.snapshot()["aion"]["chain_verified"]
    assert store.verify_chain()["events"] == 2
    resumed.close()


def test_native_chain_tampering_is_visible_and_does_not_rewrite_evidence(tmp_path):
    clock = Clock()
    monitor = service(tmp_path, clock)
    monitor.tick()
    with sqlite3.connect(monitor.store_path) as db:
        db.execute("DROP TRIGGER events_no_update")
        db.execute("UPDATE events SET event_hash=?", ("f" * 64,))
    monitor.tick()
    snap = monitor.snapshot()
    assert snap["state"] == "UNAVAILABLE" and not snap["aion"]["chain_verified"]
    assert "AION_INTEGRITY_UNAVAILABLE" in snap["warnings"]
    with sqlite3.connect(monitor.store_path) as db:
        assert db.execute("SELECT event_hash FROM events").fetchone()[0] == "f" * 64
    monitor.close()


def test_invalid_native_plane_never_reaches_aion(tmp_path, monkeypatch):
    clock = Clock()
    original = SourceHealthRegistry.snapshot
    monkeypatch.setattr(SourceHealthRegistry, "snapshot", lambda self, now: replace(original(self, now), plane_hash="0" * 64))
    monitor = service(tmp_path, clock)
    monitor.tick()
    snap = monitor.snapshot()
    assert snap["state"] == "UNAVAILABLE"
    assert "NEXUS_PLANE_INVALID" in snap["warnings"]
    assert EventStore(monitor.store_path).verify_chain()["events"] == 0
    monitor.close()


def test_future_metadata_rejects_one_asset_without_hiding_other_streams(tmp_path):
    clock = Clock()
    port = portfolio(clock, last_bar_ts=clock.now / 1e9 + 60)
    valid = portfolio(clock)
    port.runners["ES"] = valid.runners["NQ"]
    monitor = service(tmp_path, clock, port)
    monitor.tick()
    snap = monitor.snapshot()
    assert snap["state"] == "DEGRADED" and snap["nexus"]["stream_count"] == 1
    assert {a["symbol"]: a["state"] for a in snap["assets"]} == {"ES": "OBSERVING", "NQ": "UNAVAILABLE"}
    assert any("FUTURE_SOURCE_TIME" in warning for warning in snap["warnings"])
    monitor.close()


def test_all_unusable_metadata_reports_unavailable_without_hiding_asset_diagnostics(tmp_path):
    clock = Clock()
    monitor = service(tmp_path, clock, portfolio(clock, last_bar_ts=clock.now / 1e9 + 60))
    monitor.tick()
    snap = monitor.snapshot()
    assert snap["state"] == "UNAVAILABLE"
    assert snap["nexus"]["state"] == "UNAVAILABLE" and snap["nexus"]["stream_count"] == 0
    assert snap["assets"][0]["symbol"] == "NQ" and snap["assets"][0]["state"] == "UNAVAILABLE"
    assert snap["aion"]["chain_verified"], "the receipt ledger can remain valid while all observed inputs are unusable"
    monitor.close()


def test_storage_failure_and_clock_reversal_fail_closed_without_raw_errors(tmp_path):
    clock = Clock()
    blocker = tmp_path / "file"
    blocker.write_text("not a directory")
    failed = service(blocker, clock)
    assert failed.snapshot()["state"] == "STARTING"
    failed.tick()
    assert failed.snapshot()["state"] == "UNAVAILABLE"
    assert "AION_STORAGE_UNAVAILABLE" in failed.snapshot()["warnings"]
    monitor = service(tmp_path / "working", clock)
    monitor.tick()
    clock.now -= 1
    monitor.tick()
    assert monitor.snapshot()["state"] == "UNAVAILABLE"
    assert monitor._store.verify_chain()["events"] == 1
    monitor.close()


def test_busy_native_writer_does_not_block_cached_reads_and_close_drains(tmp_path, monkeypatch):
    clock = Clock()
    port = portfolio(clock)
    monitor = service(tmp_path, clock, port)
    monitor.tick()
    entered = threading.Event()
    append = monitor._store.append
    def observed_append(event):
        entered.set()
        return append(event)
    monkeypatch.setattr(monitor._store, "append", observed_append)
    db = sqlite3.connect(monitor.store_path)
    db.execute("BEGIN IMMEDIATE")
    port.runners["NQ"]._public_views[0][0]["bar_index"] += 1
    worker = threading.Thread(target=monitor.tick)
    closer = threading.Thread(target=monitor.close)
    worker.start()
    try:
        assert entered.wait(2), "native append was not reached"
        began = time.monotonic()
        for _ in range(100):
            monitor.snapshot()
        assert time.monotonic() - began < 0.25
        clock.now += 20_000_000_000
        assert "MONITOR_CACHE_STALE" in monitor.snapshot()["warnings"]
        closer.start()
        closer.join(0.03)
        assert closer.is_alive(), "close must drain the outstanding native write"
    finally:
        db.rollback()
        db.close()
        worker.join(2)
        if closer.ident is not None:
            closer.join(2)
        else:
            monitor.close()
    assert not worker.is_alive() and not closer.is_alive()
    assert monitor.snapshot()["state"] == "STOPPED"
    monitor.start()
    assert monitor.snapshot()["state"] == "STOPPED"


def test_background_start_is_idempotent_and_workspace_journals_are_separate(tmp_path):
    clock = Clock()
    sampled = threading.Event()
    count = []
    captured = capture_portfolio(portfolio(clock), now_ns=clock())
    def supply():
        count.append(threading.get_ident())
        sampled.set()
        return deepcopy(captured)
    main = NativeSubsystemConnections(tmp_path, workspace_id="main", snapshot_supplier=supply, interval=0.1, clock_ns=clock)
    main.start()
    main.start()
    assert sampled.wait(2)
    main.close()
    calls = len(count)
    main.tick()
    assert len(count) == calls and count[0] != threading.get_ident()
    cc = NativeSubsystemConnections(tmp_path, workspace_id="cc1", snapshot_supplier=lambda: captured, clock_ns=clock)
    cc.tick()
    assert main.store_path != cc.store_path
    assert EventStore(main.store_path).asof(clock())[0]["symbol"] == "main"
    assert EventStore(cc.store_path).asof(clock())[0]["symbol"] == "cc1"
    cc.close()


def test_adapter_lifecycle_and_recovery_on_actual_python310_without_site_packages(tmp_path):
    python = os.environ.get("ICARUS_NATIVE_PYTHON310")
    if python is None:
        python = sys.executable if sys.version_info[:2] == (3, 10) else shutil.which("python3.10")
    if not python:
        pytest.skip("set ICARUS_NATIVE_PYTHON310 to exercise the actual Python 3.10 adapter")
    script = r'''
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from icarus_engine.subsystem_connections import NativeSubsystemConnections, capture_portfolio
from icarus_engine.native_subsystems._divine.aion.store import EventStore

assert sys.version_info[:2] == (3, 10)
now = 1_800_000_000_000_000_000
summary = {"feed_provider": "fixture", "provider_symbol": "NQ=F", "kind": "futures",
           "bar_index": 10, "last_bar_ts": now / 1e9 - 60, "poll_age": 1,
           "bar_age": 2, "price_age": 1, "warm": True, "last_error": ""}
port = SimpleNamespace(runners={"NQ": SimpleNamespace(_public_views=((summary, now / 1e9),))})
root = Path(sys.argv[1]) / "not-created"
supplier = lambda: capture_portfolio(port, now_ns=now)
monitor = NativeSubsystemConnections(root, workspace_id="main", snapshot_supplier=supplier, clock_ns=lambda: now)
assert monitor.snapshot()["state"] == "STARTING" and not root.exists()
monitor.tick()
first = monitor.snapshot()
assert first["state"] == "OBSERVING" and first["nexus"]["state"] == "UNKNOWN_SLO"
assert first["aion"]["event_count"] == 1 and first["aion"]["chain_verified"]
for _ in range(3):
    monitor.tick()
assert monitor.snapshot()["aion"]["event_count"] == 1
summary["bar_index"] = 11
monitor.tick()
path = monitor.store_path
assert monitor.snapshot()["aion"]["event_count"] == 2
monitor.close()
assert monitor.snapshot()["state"] == "STOPPED"
def unavailable():
    raise RuntimeError("do not persist source content")
resumed = NativeSubsystemConnections(root, workspace_id="main", snapshot_supplier=unavailable, clock_ns=lambda: now)
resumed.tick()
recovered = resumed.snapshot()
assert recovered["state"] == "DEGRADED"
assert recovered["assets"][0]["cache_state"] == "RECOVERED"
assert recovered["aion"]["recovered_event_count"] == 2
assert not recovered["execution_authorized"] and not recovered["production_decision_authorized"]
store = EventStore(path)
assert store.verify_chain()["verified"] and store.asof(now - 1) == []
assert all(row["event"]["available_ns"] == row["event"]["ingested_ns"] == now for row in store.asof(now))
assert "do not persist source content" not in json.dumps(recovered)
resumed.close()
assert "numpy" not in sys.modules and "pandas" not in sys.modules
print(json.dumps({"python": list(sys.version_info[:3]), "adapter_recovery_verified": True}))
'''
    result = subprocess.run(
        [python, "-S", "-c", script, str(tmp_path)],
        cwd=tmp_path,
        env=dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]), PYTHONDONTWRITEBYTECODE="1"),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["adapter_recovery_verified"] is True
