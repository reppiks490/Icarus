"""Workspace power uses real isolated ledgers and event-controlled worker threads."""
import json
import sqlite3
import threading
import time

import pytest

from icarus_engine import paper_workspaces
from icarus_engine.assets import REGISTRY
from icarus_engine.pine.timeframe import Bar
from icarus_engine.runtime import Journal, Portfolio
from icarus_engine.shadow_twin import MirroredEmulator
from icarus_engine.workspace_power import WorkspacePowerControls, WorkspacePowerError

REAL_WORKSPACE_START = paper_workspaces.WorkspacePortfolio.start


class OfflineFeed:
    def ticker(self, _symbol):
        return 100.0

    def close(self):
        raise AssertionError("a workspace must never close its parent's transport")


def wait_for(predicate):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if predicate():
            return
        threading.Event().wait(0.005)
    assert predicate(), "workspace did not reach the expected state"


def row(controls, profile_id="cc1"):
    return next(item for item in controls.snapshot()["workspaces"] if item["id"] == profile_id)


@pytest.fixture
def setup_manager(tmp_path, monkeypatch):
    monkeypatch.setenv("ICARUS_FEED", "file")
    monkeypatch.setattr(paper_workspaces, "_PROFILE_DEFAULTS", tuple(
        {**profile, "assets": ["NQ"]} for profile in paper_workspaces._PROFILE_DEFAULTS))
    feed = OfflineFeed()
    parent = Portfolio(Journal(":memory:"), str(tmp_path), pts_ref_symbol="NQ",
                       feeds={"yahoo": feed, "coinbase": feed})
    parent.pts_ref_price = 100.0
    manager = paper_workspaces.PaperWorkspaceManager(parent)
    controls_list = []

    def start_workers(portfolio):
        worker = threading.Thread(target=portfolio._stop.wait, daemon=True)
        worker.start()
        portfolio._threads["NQ"] = worker
        sampler = threading.Thread(target=portfolio._stop.wait, daemon=True)
        sampler.start()
        portfolio._sampler_thread = sampler

    monkeypatch.setattr(paper_workspaces.WorkspacePortfolio, "start", start_workers)

    def make_controls(**kwargs):
        controls = WorkspacePowerControls(manager, **kwargs)
        controls_list.append(controls)
        return controls

    yield manager, make_controls, feed
    for controls in controls_list:
        controls.close()
    manager.stop()
    parent.journal.close()


def test_independent_off_on_preserves_profiles_journal_and_siblings(setup_manager):
    manager, make_controls, _ = setup_manager
    disabled = []
    controls = make_controls(on_disabled=disabled.append)
    # Server(start=False) tests are allowed to seed their own real portfolios.
    manager.start()
    assert all(controls.is_on(profile_id) for profile_id in manager.profiles)
    profiles_before = {key: manager._path(key).read_bytes() for key in manager.profiles}
    sibling = manager.portfolios["cc2"]
    journal_path = manager.root / "cc1.sqlite3"
    with manager.portfolios["cc1"].journal._lock:
        manager.portfolios["cc1"].journal.con.execute(
            "INSERT INTO trades(symbol,entry_id,direction,qty,entry_price,entry_ts,exit_price,exit_ts,profit,live) "
            "VALUES('NQ','history',1,1,100,1,101,2,20,1)")
        manager.portfolios["cc1"].journal.con.commit()
    result = controls.request("cc1", {"enabled": False, "expected_revision": 0})
    assert result["workspace"]["desired_enabled"] is False
    assert result["execution_authorized"] is False and result["paper_only"] is True
    wait_for(lambda: row(controls)["runtime_state"] == "OFF")
    assert not controls.is_on("cc1") and controls.is_on("cc2")
    assert manager.portfolios["cc2"] is sibling and not sibling._stop.is_set()
    assert "cc1" not in manager.portfolios and disabled == ["cc1"]
    assert journal_path.exists()
    assert manager.snapshot()["aggregate"]["realized_pnl"] is None
    assert profiles_before == {key: manager._path(key).read_bytes() for key in manager.profiles}
    saved = json.loads((manager.root / "runtime-power.json").read_text())
    assert saved["schema_version"] == "icarus.workspace-power.v1"
    assert next(item for item in saved["workspaces"] if item["id"] == "cc1") == {
        "id": "cc1", "desired_enabled": False, "revision": 1}
    controls.request("cc1", {"enabled": True, "expected_revision": 1})
    wait_for(lambda: controls.is_on("cc1"))
    assert manager.portfolios["cc1"].journal.closed_paper_profit()["realized_pnl"] == 20
    assert profiles_before == {key: manager._path(key).read_bytes() for key in manager.profiles}


@pytest.mark.parametrize("kind", ["open", "entry", "close", "shadow_entry", "rewarming", "activation", "busy"])
def test_off_refuses_risky_or_busy_workspace_without_mutation(setup_manager, kind):
    manager, make_controls, _ = setup_manager
    controls = make_controls(busy=lambda _id: kind == "busy")
    manager.start()
    portfolio = manager.portfolios["cc1"]
    runner = portfolio.runners["NQ"]
    if kind == "open":
        runner.em.process_bar(Bar(0, 100, 100, 100, 100, 1), 0)
        runner.em.entry("keep", 1, 1)
        runner.em.process_bar(Bar(60, 100, 100, 100, 100, 1), 1)
    elif kind == "entry":
        runner.em.entry("keep", 1, 1)
    elif kind == "close":
        runner.em._pending_closes.append(object())
    elif kind == "shadow_entry":
        runner.em = MirroredEmulator(runner.em, asset=runner.symbol)
        runner.em.shadow.entry("shadow-keep", 1, 1)
    elif kind == "rewarming":
        runner.rewarming = True
    elif kind == "activation":
        runner._activation_version_id = "keep"
    before = (list(runner.em.open), list(runner.em._pending_entries), list(runner.em._pending_closes))
    with pytest.raises(WorkspacePowerError) as error:
        controls.request("cc1", {"enabled": False, "expected_revision": 0})
    assert error.value.status == 409
    assert controls.is_on("cc1") and row(controls)["revision"] == 0
    assert not runner.paused and not portfolio._stop.is_set()
    assert before == (list(runner.em.open), list(runner.em._pending_entries), list(runner.em._pending_closes))
    assert not (manager.root / "runtime-power.json").exists()
    if kind == "shadow_entry":
        assert len(runner.em.shadow._pending_entries) == 1


def test_off_is_nonblocking_and_truthful_while_inflight_feed_drains(setup_manager, monkeypatch):
    manager, make_controls, feed = setup_manager
    controls = make_controls()
    manager.start()
    portfolio = manager.portfolios["cc1"]
    runner = portfolio.runners["NQ"]
    entered, release = threading.Event(), threading.Event()

    def blocked_recent(*_args, **_kwargs):
        entered.set()
        assert release.wait(5)
        return [Bar(0, 100, 100, 100, 100, 1)], 60, 100.0

    monkeypatch.setattr(feed, "recent_ex", blocked_recent, raising=False)
    runner.warm = True
    worker = threading.Thread(target=runner.poll, daemon=True)
    portfolio._threads["inflight"] = worker
    worker.start()
    try:
        assert entered.wait(5)
        started = time.monotonic()
        controls.request("cc1", {"enabled": False, "expected_revision": 0})
        assert time.monotonic() - started < 0.5
        assert row(controls)["runtime_state"] == "STOPPING"
        assert not controls.is_on("cc1") and controls.is_on("cc2")
        assert runner.paused and runner._removed and portfolio._stop.is_set()
        assert worker.is_alive()
        with sqlite3.connect(manager.root / "cc1.sqlite3") as read:
            before = read.execute("SELECT COUNT(*) FROM trades").fetchone()
        release.set()
        wait_for(lambda: row(controls)["runtime_state"] == "OFF")
        assert not worker.is_alive() and not runner.em.open and not runner.em._pending_entries
        with sqlite3.connect(manager.root / "cc1.sqlite3") as read:
            assert read.execute("SELECT COUNT(*) FROM trades").fetchone() == before
    finally:
        release.set()


def test_snapshot_does_not_retain_runtime_while_its_journal_closes(setup_manager, monkeypatch):
    manager, make_controls, _ = setup_manager
    controls = make_controls()
    manager.start()
    portfolio = manager.portfolios["cc1"]
    entered, release = threading.Event(), threading.Event()
    original = portfolio.journal.close

    def blocked_close():
        entered.set()
        assert release.wait(5)
        original()

    monkeypatch.setattr(portfolio.journal, "close", blocked_close)
    try:
        controls.request("cc1", {"enabled": False, "expected_revision": 0})
        assert entered.wait(5)
        snapshot = manager.snapshot()
        selected = next(item for item in snapshot["profiles"] if item["id"] == "cc1")
        assert selected["runtime_available"] is False
        assert snapshot["aggregate"]["realized_pnl"] is None
        assert row(controls)["runtime_state"] == "STOPPING"
    finally:
        release.set()
    wait_for(lambda: row(controls)["runtime_state"] == "OFF")


@pytest.mark.parametrize("phase", ["warmup", "after_warmup_check"])
def test_warmup_return_after_off_cannot_activate_startup_overlay(setup_manager, monkeypatch, phase):
    manager, make_controls, _ = setup_manager
    controls = make_controls()
    manager.start()
    portfolio = manager.portfolios["cc1"]
    runner = portfolio.runners["NQ"]
    entered, release = threading.Event(), threading.Event()
    overlays = []

    def warmup():
        if phase == "warmup":
            entered.set()
            assert release.wait(5)
        runner.bar_index = 0
        runner.warm = True

    monkeypatch.setattr(runner, "warmup", warmup)
    if phase == "after_warmup_check":
        original = portfolio._warmup_with_retry

        def blocked_after_warmup(value):
            ready = original(value)
            entered.set()
            assert release.wait(5)
            return ready

        monkeypatch.setattr(portfolio, "_warmup_with_retry", blocked_after_warmup)
    monkeypatch.setattr("icarus_engine.activation_runtime.load_startup_overlay", lambda *_: overlays.append(True))
    worker = threading.Thread(target=portfolio._run, args=(runner,), daemon=True)
    portfolio._threads["warming"] = worker
    worker.start()
    try:
        assert entered.wait(5)
        controls.request("cc1", {"enabled": False, "expected_revision": 0})
        release.set()
        wait_for(lambda: row(controls)["runtime_state"] == "OFF")
        assert overlays == []
    finally:
        release.set()


def test_panel_failure_does_not_skip_worker_drain(setup_manager):
    manager, make_controls, _ = setup_manager

    def fail_panel(_id):
        raise RuntimeError("panel failed")

    controls = make_controls(on_disabled=fail_panel)
    manager.start()
    portfolio = manager.portfolios["cc1"]
    controls.request("cc1", {"enabled": False, "expected_revision": 0})
    wait_for(lambda: row(controls)["runtime_state"] == "ERROR")
    assert all(not worker.is_alive() for worker in portfolio._threads.values())
    with pytest.raises(sqlite3.ProgrammingError):
        portfolio.journal.con.execute("SELECT 1")


def test_real_runner_and_sampler_startup_gates_cancel_without_work(setup_manager, monkeypatch):
    manager, make_controls, _ = setup_manager
    controls = make_controls()
    manager.start()
    portfolio = manager.portfolios["cc1"]
    portfolio._workspace_power_gate = threading.Event()
    work = []
    monkeypatch.setattr(portfolio, "_warmup_with_retry", lambda _runner: work.append("warmup"))
    monkeypatch.setattr(portfolio, "_refresh_continuous_feeds", lambda: work.append("sampler"))
    REAL_WORKSPACE_START(portfolio)
    controls.request("cc1", {"enabled": False, "expected_revision": 0})
    wait_for(lambda: row(controls)["runtime_state"] == "OFF")
    assert work == []
    assert all(not worker.is_alive() for worker in portfolio._threads.values())
    assert not portfolio._sampler_thread.is_alive()


def test_provider_prepare_cancellation_cannot_spawn_late_workers(setup_manager, monkeypatch):
    manager, make_controls, feed = setup_manager
    controls = make_controls()
    entered, release = threading.Event(), threading.Event()
    prepared = []

    def prepare(*_args, **_kwargs):
        prepared.append(True)
        entered.set()
        assert release.wait(5)

    monkeypatch.setattr(feed, "prepare_live", prepare, raising=False)
    monkeypatch.setattr(paper_workspaces.WorkspacePortfolio, "start", REAL_WORKSPACE_START)
    controls.request("cc1", {"enabled": True, "expected_revision": 0})
    try:
        assert entered.wait(5)
        portfolio = controls._pending["cc1"]
        controls.request("cc1", {"enabled": False, "expected_revision": 1})
        assert row(controls)["runtime_state"] == "STOPPING"
        with pytest.raises(WorkspacePowerError) as error:
            controls.request("cc1", {"enabled": True, "expected_revision": 2})
        assert error.value.status == 409
        release.set()
        wait_for(lambda: row(controls)["runtime_state"] == "OFF")
        assert prepared == [True]
        assert portfolio._threads == {} and portfolio._sampler_thread is None
    finally:
        release.set()


def test_saving_one_workspace_never_blocks_snapshots_or_loses_sibling_desire(setup_manager, monkeypatch):
    manager, make_controls, _ = setup_manager
    controls = make_controls()
    manager.start()
    entered, release = threading.Event(), threading.Event()
    original = controls._save
    errors = []

    def blocked_save(profile_id, enabled, revision):
        original(profile_id, enabled, revision)
        if profile_id == "cc1":
            entered.set()
            assert release.wait(5)

    monkeypatch.setattr(controls, "_save", blocked_save)

    def disable_first():
        try:
            controls.request("cc1", {"enabled": False, "expected_revision": 0})
        except Exception as error:
            errors.append(error)

    worker = threading.Thread(target=disable_first, daemon=True)
    worker.start()
    try:
        assert entered.wait(5)
        started = time.monotonic()
        assert controls.is_on("cc2")
        assert len(controls.snapshot()["workspaces"]) == 4
        with pytest.raises(WorkspacePowerError) as error:
            controls.request("cc2", {"enabled": False, "expected_revision": 0})
        assert error.value.status == 409
        assert time.monotonic() - started < 0.5
        release.set()
        worker.join(5)
        assert errors == []
        controls.request("cc2", {"enabled": False, "expected_revision": 0})
        saved = json.loads((manager.root / "runtime-power.json").read_text())
        desires = {item["id"]: item["desired_enabled"] for item in saved["workspaces"]}
        assert desires == {"cc1": False, "cc2": False, "cc3": True, "cc4": True}
    finally:
        release.set()
        worker.join(5)


def test_immediate_enable_after_off_completion_cannot_lose_transition_worker(setup_manager, monkeypatch):
    manager, make_controls, _ = setup_manager
    controls = make_controls()
    manager.start()
    terminal, release = threading.Event(), threading.Event()
    original_lock = controls._lock

    class TerminalBarrier:
        def __enter__(self):
            original_lock.acquire()
            return self

        def __exit__(self, *_args):
            intercept = (threading.current_thread().name == "workspace-power-cc1"
                         and controls._rows["cc1"]["runtime_state"] == "OFF" and not terminal.is_set())
            original_lock.release()
            if intercept:
                terminal.set()
                assert release.wait(5)

    monkeypatch.setattr(controls, "_lock", TerminalBarrier())
    try:
        controls.request("cc1", {"enabled": False, "expected_revision": 0})
        assert terminal.wait(5)
        controls.request("cc1", {"enabled": True, "expected_revision": 1})
        release.set()
        wait_for(lambda: controls.is_on("cc1"))
    finally:
        release.set()


def test_close_waits_for_configuration_to_finish_publishing_workers(setup_manager):
    manager, make_controls, _ = setup_manager
    controls = make_controls()
    manager.start()
    portfolio = manager.portfolios["cc1"]
    configured, publish, release_worker = threading.Event(), threading.Event(), threading.Event()
    late_worker = threading.Thread(target=release_worker.wait, daemon=True)

    def transaction():
        with manager.configuration_lock("cc1"):
            configured.set()
            assert publish.wait(5)
            late_worker.start()
            portfolio._threads["late"] = late_worker

    configuring = threading.Thread(target=transaction, daemon=True)
    configuring.start()
    try:
        assert configured.wait(5)
        controls.close()
        publish.set()
        configuring.join(5)
        assert late_worker.is_alive()
        # The state must remain STOPPING as long as the last admitted worker
        # remains in I/O, including workers published by an in-flight edit.
        threading.Event().wait(0.02)
        assert row(controls)["runtime_state"] == "STOPPING"
        release_worker.set()
        wait_for(lambda: row(controls)["runtime_state"] == "OFF")
    finally:
        publish.set()
        release_worker.set()
        configuring.join(5)


def test_warming_can_be_stopped_but_configuration_lock_never_blocks_request(setup_manager):
    manager, make_controls, _ = setup_manager
    controls = make_controls()
    manager.start()
    runner = manager.portfolios["cc1"].runners["NQ"]
    assert not runner.warm
    entered, release = threading.Event(), threading.Event()

    def hold_configuration():
        with manager.configuration_lock("cc1"):
            entered.set()
            release.wait(5)

    holder = threading.Thread(target=hold_configuration, daemon=True)
    holder.start()
    try:
        assert entered.wait(5)
        started = time.monotonic()
        with pytest.raises(WorkspacePowerError) as error:
            controls.request("cc1", {"enabled": False, "expected_revision": 0})
        assert error.value.status == 409 and time.monotonic() - started < 0.5
        assert controls.is_on("cc2")
    finally:
        release.set()
        holder.join(5)
    controls.request("cc1", {"enabled": False, "expected_revision": 0})
    wait_for(lambda: row(controls)["runtime_state"] == "OFF")


def test_persistence_failure_keeps_runtime_and_revision_unchanged(setup_manager, monkeypatch):
    manager, make_controls, _ = setup_manager
    controls = make_controls()
    manager.start()

    def fail_replace(*_args):
        raise OSError("private provider key must never reach response")

    monkeypatch.setattr("icarus_engine.workspace_power.os.replace", fail_replace)
    with pytest.raises(WorkspacePowerError) as error:
        controls.request("cc1", {"enabled": False, "expected_revision": 0})
    assert error.value.status == 503 and "private" not in error.value.detail
    assert controls.is_on("cc1") and row(controls)["revision"] == 0
    assert not manager.portfolios["cc1"]._stop.is_set()
    assert not manager.portfolios["cc1"].runners["NQ"].paused


@pytest.mark.parametrize("profile_id,body,status", [
    ("../cc1", {"enabled": False, "expected_revision": 0}, 404),
    ([], {"enabled": False, "expected_revision": 0}, 404),
    ("cc1", {"enabled": 0, "expected_revision": 0}, 400),
    ("cc1", {"enabled": False, "expected_revision": True}, 400),
    ("cc1", {"enabled": False, "expected_revision": -1}, 400),
    ("cc1", {"enabled": False, "expected_revision": 0, "force": True}, 400),
    ("cc1", {"enabled": False}, 400),
    ("cc1", {"enabled": False, "expected_revision": 99}, 409),
])
def test_strict_request_contract(setup_manager, profile_id, body, status):
    manager, make_controls, _ = setup_manager
    controls = make_controls()
    with pytest.raises(WorkspacePowerError) as error:
        controls.request(profile_id, body)
    assert error.value.status == status
    assert not manager.portfolios


def test_corrupt_control_file_fails_closed_without_stopping_parent(setup_manager):
    manager, make_controls, _ = setup_manager
    (manager.root / "runtime-power.json").write_text('{"schema_version":"unknown"}')
    controls = make_controls()
    controls.start()
    assert not manager.portfolios and not manager.parent._stop.is_set()
    assert all(item["runtime_state"] == "ERROR" and not item["desired_enabled"]
               for item in controls.snapshot()["workspaces"])
    with pytest.raises(WorkspacePowerError) as error:
        controls.request("cc1", {"enabled": True, "expected_revision": 0})
    assert error.value.status == 503


def test_startup_errors_are_isolated_and_saved_off_is_not_started(setup_manager, monkeypatch):
    manager, make_controls, _ = setup_manager
    controls = make_controls()
    controls.request("cc4", {"enabled": False, "expected_revision": 0})
    wait_for(lambda: row(controls, "cc4")["runtime_state"] == "OFF")
    controls.close()
    original = paper_workspaces.WorkspacePortfolio.start

    def start(portfolio):
        if portfolio.workspace["id"] == "cc1":
            raise RuntimeError("secret from provider")
        original(portfolio)

    monkeypatch.setattr(paper_workspaces.WorkspacePortfolio, "start", start)
    restored = make_controls()
    restored.start()
    wait_for(lambda: row(restored, "cc1")["runtime_state"] == "ERROR" and restored.is_on("cc2")
             and restored.is_on("cc3"))
    assert not restored.is_on("cc4") and "cc4" not in manager.portfolios
    assert "secret" not in row(restored)["error"]
    assert not manager.parent._stop.is_set()


@pytest.mark.parametrize("cancel", ["off", "close"])
def test_startup_cancellation_prevents_late_publish(setup_manager, monkeypatch, cancel):
    manager, make_controls, _ = setup_manager
    controls = make_controls()
    entered, release = threading.Event(), threading.Event()
    original = paper_workspaces.WorkspacePortfolio.start

    def blocked_start(portfolio):
        if portfolio.workspace["id"] == "cc1":
            entered.set()
            assert release.wait(5)
        original(portfolio)

    monkeypatch.setattr(paper_workspaces.WorkspacePortfolio, "start", blocked_start)
    controls.start()
    try:
        assert entered.wait(5)
        started = time.monotonic()
        if cancel == "off":
            controls.request("cc1", {"enabled": False, "expected_revision": 0})
        else:
            controls.close()
        assert time.monotonic() - started < 0.5
        assert not controls.is_on("cc1") and "cc1" not in manager.portfolios
        release.set()
        wait_for(lambda: row(controls)["runtime_state"] == "OFF")
        assert "cc1" not in manager.portfolios
    finally:
        release.set()


def test_cancel_during_runner_construction_finishes_off(setup_manager, monkeypatch):
    manager, make_controls, _ = setup_manager
    controls = make_controls()
    entered, release = threading.Event(), threading.Event()
    original = paper_workspaces.WorkspacePortfolio.make_runner

    def blocked_runner(portfolio, spec, **kwargs):
        entered.set()
        assert release.wait(5)
        return original(portfolio, spec, **kwargs)

    monkeypatch.setattr(paper_workspaces.WorkspacePortfolio, "make_runner", blocked_runner)
    controls.request("cc1", {"enabled": True, "expected_revision": 0})
    try:
        assert entered.wait(5)
        controls.request("cc1", {"enabled": False, "expected_revision": 1})
        release.set()
        wait_for(lambda: row(controls)["runtime_state"] in ("OFF", "ERROR"))
        assert row(controls)["runtime_state"] == "OFF"
        assert "cc1" not in manager.portfolios
    finally:
        release.set()


def test_one_lifecycle_thread_start_failure_does_not_abort_siblings(setup_manager, monkeypatch):
    manager, make_controls, _ = setup_manager
    controls = make_controls()
    original = threading.Thread.start

    def fail_one(worker):
        if worker.name == "workspace-power-cc1":
            raise RuntimeError("private system error")
        return original(worker)

    monkeypatch.setattr(threading.Thread, "start", fail_one)
    controls.start()
    wait_for(lambda: controls.is_on("cc2") and controls.is_on("cc3") and controls.is_on("cc4"))
    assert row(controls)["runtime_state"] == "ERROR"
    assert "private" not in row(controls)["error"]
    assert "cc1" not in controls._workers
    monkeypatch.setattr(threading.Thread, "start", original)
    controls.request("cc1", {"enabled": True, "expected_revision": 0})
    wait_for(lambda: controls.is_on("cc1"))


def test_off_thread_start_failure_remains_retryable_and_truthful(setup_manager, monkeypatch):
    manager, make_controls, _ = setup_manager
    controls = make_controls()
    manager.start()
    original = threading.Thread.start

    def fail_one(worker):
        if worker.name == "workspace-power-cc1":
            raise RuntimeError("private system error")
        return original(worker)

    monkeypatch.setattr(threading.Thread, "start", fail_one)
    with pytest.raises(WorkspacePowerError) as error:
        controls.request("cc1", {"enabled": False, "expected_revision": 0})
    assert error.value.status == 503
    assert row(controls)["runtime_state"] == "ERROR" and not controls.is_on("cc1")
    assert row(controls)["revision"] == 1 and "cc1" not in controls._workers
    monkeypatch.setattr(threading.Thread, "start", original)
    controls.request("cc1", {"enabled": False, "expected_revision": 1})
    wait_for(lambda: row(controls)["runtime_state"] == "OFF")


def test_on_callback_is_outside_global_locks_and_failure_keeps_runtime_on(setup_manager):
    manager, make_controls, _ = setup_manager
    called = threading.Event()
    observed = []

    def enabled(profile_id, portfolio):
        observed.append(manager.portfolios.get(profile_id) is portfolio)
        # A separate thread must be able to inspect power during the callback.
        worker = threading.Thread(target=lambda: (controls.snapshot(), called.set()), daemon=True)
        worker.start()
        assert called.wait(1)
        raise RuntimeError("private panel error")

    controls = make_controls(on_enabled=enabled)
    controls.request("cc1", {"enabled": True, "expected_revision": 0})
    wait_for(lambda: called.is_set() and controls.is_on("cc1"))
    assert observed == [True]
    assert row(controls)["runtime_state"] == "ON"
    assert "private" not in (row(controls)["error"] or "")


def test_concurrent_startup_overlays_preserve_native_store_and_runner_lock_order(setup_manager, monkeypatch):
    from icarus_engine.activation_runtime import ActivationRuntime

    manager, make_controls, _ = setup_manager
    controls = make_controls()
    manager.start()
    portfolio = manager.portfolios["cc1"]
    portfolio.add_asset(REGISTRY["CL"], start=False)
    ready = threading.Barrier(2)
    writer = threading.Lock()
    completed, loaded = set(), set()
    entering = set()
    both_entering = threading.Event()

    def overlay(port, runner):
        entering.add(runner.symbol)
        if len(entering) == 2:
            both_entering.set()
        both_entering.wait(0.1)
        try:
            # Native overlay loading takes its durable writer before its runtime
            # boundary. A timeout exposes inversion without leaking deadlocks.
            if not writer.acquire(timeout=0.2):
                raise RuntimeError("startup overlay writer lock was inverted")
            try:
                with ActivationRuntime(port).boundary(runner.symbol):
                    loaded.add(runner.symbol)
            finally:
                writer.release()
        finally:
            completed.add(runner.symbol)

    monkeypatch.setattr("icarus_engine.activation_runtime.load_startup_overlay", overlay)
    workers = []
    for runner in portfolio.runner_list():
        def warmup(value=runner):
            ready.wait(2)
            value.bar_index = 0
            value.warm = True

        monkeypatch.setattr(runner, "warmup", warmup)
        monkeypatch.setattr(runner, "poll", lambda: None)
        worker = threading.Thread(target=portfolio._run, args=(runner,), daemon=True)
        portfolio._threads[f"overlay-{runner.symbol}"] = worker
        workers.append(worker)
    try:
        for worker in workers:
            worker.start()
        wait_for(lambda: len(completed) == 2)
        assert loaded == {"NQ", "CL"}
        assert all(runner.errors == 0 for runner in portfolio.runner_list())
    finally:
        portfolio._stop.set()
        for worker in workers:
            worker.join(2)


def test_failed_sampler_thread_is_retired_and_does_not_block_retry(setup_manager, monkeypatch):
    manager, make_controls, _ = setup_manager
    controls = make_controls()
    built = []
    create = manager.create_portfolio
    start_thread = threading.Thread.start

    def create_portfolio(*args, **kwargs):
        value = create(*args, **kwargs)
        built.append(value)
        return value

    def fail_sampler(worker):
        if worker.name == "equity-sampler-cc1":
            raise RuntimeError("sampler thread unavailable")
        return start_thread(worker)

    monkeypatch.setattr(manager, "create_portfolio", create_portfolio)
    monkeypatch.setattr(paper_workspaces.WorkspacePortfolio, "start", REAL_WORKSPACE_START)
    monkeypatch.setattr(threading.Thread, "start", fail_sampler)
    controls.request("cc1", {"enabled": True, "expected_revision": 0})
    wait_for(lambda: row(controls)["runtime_state"] == "ERROR")
    assert "cc1" not in controls._pending and "cc1" not in manager.portfolios
    assert all(not worker.is_alive() for worker in built[0]._threads.values())
    with pytest.raises(sqlite3.ProgrammingError):
        built[0].journal.con.execute("SELECT 1")
    monkeypatch.setattr(threading.Thread, "start", start_thread)
    controls.request("cc1", {"enabled": True, "expected_revision": 1})
    wait_for(lambda: controls.is_on("cc1"))


def test_off_signals_runtime_created_while_its_desire_is_saving(setup_manager, monkeypatch):
    manager, make_controls, _ = setup_manager
    controls = make_controls()
    constructing, construct = threading.Event(), threading.Event()
    saving, save = threading.Event(), threading.Event()
    starting, start = threading.Event(), threading.Event()
    initialize = paper_workspaces.WorkspacePortfolio.__init__
    save_settings = controls._save
    errors = []

    def blocked_constructor(portfolio, *args, **kwargs):
        constructing.set()
        assert construct.wait(5)
        initialize(portfolio, *args, **kwargs)

    def blocked_save(profile_id, enabled, revision):
        if not enabled:
            saving.set()
            assert save.wait(5)
        save_settings(profile_id, enabled, revision)

    def blocked_start(_portfolio):
        starting.set()
        assert start.wait(5)

    def switch_off():
        try:
            controls.request("cc1", {"enabled": False, "expected_revision": 1})
        except Exception as error:
            errors.append(error)

    monkeypatch.setattr(paper_workspaces.WorkspacePortfolio, "__init__", blocked_constructor)
    monkeypatch.setattr(paper_workspaces.WorkspacePortfolio, "start", blocked_start)
    monkeypatch.setattr(controls, "_save", blocked_save)
    controls.request("cc1", {"enabled": True, "expected_revision": 0})
    off = threading.Thread(target=switch_off, daemon=True)
    try:
        assert constructing.wait(5)
        off.start()
        assert saving.wait(5)
        construct.set()
        assert starting.wait(5)
        portfolio = controls._pending["cc1"]
        save.set()
        off.join(5)
        assert errors == []
        assert portfolio._stop.is_set()
        assert row(controls)["runtime_state"] == "STOPPING"
        start.set()
        wait_for(lambda: row(controls)["runtime_state"] == "OFF")
    finally:
        construct.set()
        save.set()
        start.set()
        if off.ident is not None:
            off.join(5)
