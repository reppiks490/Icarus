"""Workspace jobs freeze offline replay sources and never cross ledger boundaries."""
import copy
import importlib
import json
import threading
import time
from dataclasses import replace

import pytest

from icarus_engine import backtest, paper_workspaces
from icarus_engine.assets import REGISTRY
from icarus_engine.pine.timeframe import Bar
from icarus_engine.runtime import AssetRunner, Journal, Portfolio, RunnerConfig
from icarus_engine.strategy.inputs import Inputs


@pytest.fixture
def jobs_module():
    try:
        return importlib.import_module("icarus_engine.workspace_jobs")
    except ModuleNotFoundError:
        pytest.fail("workspace job service has not been implemented", pytrace=False)


@pytest.fixture
def manager(tmp_path, monkeypatch):
    monkeypatch.setenv("ICARUS_FEED", "file")
    monkeypatch.setattr(paper_workspaces, "_PROFILE_DEFAULTS", tuple(
        {**p, "assets": ["NQ", "ES"],
         "chart": {"timeframe": "1", "chart_type": "real", "fill_on": "real", "security_source": "standard"},
         "inputs": {"use_tide": False, "use_eod_flat": False, "tp1_pts": i + 11}}
        for i, p in enumerate(paper_workspaces._PROFILE_DEFAULTS)))
    monkeypatch.setattr(paper_workspaces.WorkspacePortfolio, "start", lambda self: None)
    parent = Portfolio(Journal(":memory:"), str(tmp_path))
    parent.pts_ref_price = 100
    spec = replace(REGISTRY["NQ"], chart_tf="1", calendar="crypto", session="eth")
    parent.runners["NQ"] = AssetRunner(RunnerConfig(spec, Inputs(tp1_pts=99)), parent.journal, parent.feeds)
    parent.order = ["NQ"]
    manager = paper_workspaces.PaperWorkspaceManager(parent)
    manager.start()
    for i, port in enumerate([parent, *manager.portfolios.values()]):
        for runner in port.runner_list():
            runner.spec.calendar = "crypto"
            runner.spec.session = "eth"
            runner._init_strategy(100)
            runner.warm = True
            runner.subbars = [(Bar(1_700_000_000 // 60 * 60 + k * 60,
                                  100 + i * 100 + k, 102 + i * 100 + k,
                                  99 + i * 100 + k, 101 + i * 100 + k, 1), 1)
                              for k in range(24 + i)]
    yield manager
    manager.stop()
    parent.journal.close()


class DeferredThreads:
    """Replace only scheduling; execute the genuine worker/replay explicitly."""
    def __init__(self):
        self.pending = []

    def thread(self, *, target, **_kwargs):
        scheduler = self

        class Thread:
            def start(self):
                scheduler.pending.append(target)
        return Thread()

    def run(self, index=0):
        self.pending.pop(index)()


@pytest.fixture
def deferred(jobs_module, monkeypatch):
    scheduler = DeferredThreads()
    monkeypatch.setattr(jobs_module, "Thread", scheduler.thread)
    return scheduler


def _error(module, status, fn):
    with pytest.raises(module.WorkspaceJobError) as caught:
        fn()
    assert caught.value.status == status
    assert caught.value.detail


def test_foreign_job_get_csv_and_compare_are_typed_404(jobs_module, manager, deferred):
    jobs = jobs_module.ScopedWorkspaceJobs(manager)
    receipt = jobs.submit_backtest("cc1", "NQ", {"expected_revision": 0})
    for workspace in ("cc2", "main", "unknown"):
        _error(jobs_module, 404, lambda: jobs.get(workspace, receipt["job"]))
        _error(jobs_module, 404, lambda: jobs.export_csv(workspace, receipt["job"]))
        _error(jobs_module, 404, lambda: jobs.compare(workspace, receipt["job"], ""))
    deferred.run()
    row = jobs.get("cc1", receipt["job"])
    assert row["status"] == "done", row
    assert row["kind"] == "backtest" and row["asset"] == "NQ"
    assert row["workspace_id"] == "cc1" and row["config_revision"] == 0
    assert "csv" not in row["result"]
    assert "result" not in jobs.get("cc1", receipt["job"], full=False)
    csv_text = jobs.export_csv("cc1", receipt["job"])
    assert csv_text.startswith("Trade number,")
    compared = jobs.compare("cc1", receipt["job"], csv_text)
    assert compared["workspace_id"] == "cc1" and compared["config_revision"] == 0
    assert "report" in compared
    row["result"]["config"]["commission"] = 999
    assert jobs.get("cc1", receipt["job"])["result"]["config"]["commission"] != 999
    _error(jobs_module, 404, lambda: jobs.get("cc1", "missing"))


def test_same_symbol_five_sources_remain_distinct(jobs_module, manager, deferred):
    jobs = jobs_module.ScopedWorkspaceJobs(manager)
    parent_jobs = dict(backtest.JOBS)
    for index, port in enumerate([manager.parent, *manager.portfolios.values()], 1):
        runner = port.runners["NQ"]
        runner.spec.chart_tf = str(index)
        runner.spec.commission = index
        if hasattr(port, "workspace"):
            port.workspace["chart"]["timeframe"] = str(index)
    main = backtest.run_backtest(manager.parent, "NQ")
    receipts = [jobs.submit_backtest(w, "NQ", {"expected_revision": 0}) for w in manager.profiles]
    while deferred.pending:
        deferred.run()
    results = [main, *(jobs.get(w, r["job"])["result"] for w, r in zip(manager.profiles, receipts))]
    assert len({r["config"]["reproducibility"]["subbars_sha256"] for r in results}) == 5
    assert [r["config"]["reproducibility"]["source_config"]["base_inputs"]["tp1_pts"] for r in results] == [99, 11, 12, 13, 14]
    assert [r["config"]["tf"] for r in results] == [1, 2, 3, 4, 5]
    assert [r["config"]["commission"] for r in results] == [1, 2, 3, 4, 5]
    assert [r["config"]["reproducibility"]["subbars_count"] for r in results] == [24, 25, 26, 27, 28]
    assert backtest.JOBS == parent_jobs


def test_submission_freezes_real_tape_inputs_costs_and_mutable_body(jobs_module, manager, deferred):
    jobs = jobs_module.ScopedWorkspaceJobs(manager)
    runner = manager.portfolios["cc1"].runners["NQ"]
    body = {"expected_revision": 0, "commission": 4, "timeframe": "2",
            "inputs": {"tp1_pts": 37, "use_tide": False}}
    receipt = jobs.submit_backtest("cc1", "NQ", body)
    body["commission"] = 999
    body["inputs"]["tp1_pts"] = 999
    runner.subbars.clear()
    runner.inputs_base.tp1_pts = 999
    runner.spec.commission = 999
    (manager.root.parent / "inputs.json").write_text('{"tp1_pts":999}')
    (manager.root.parent / "inputs.NQ.json").write_text('{"tp1_pts":999}')
    deferred.run()
    result = jobs.get("cc1", receipt["job"])["result"]
    assert result["bars"] > 0
    assert result["config"]["commission"] == 4 and result["config"]["tf"] == 2
    assert result["config"]["reproducibility"]["effective_config"]["base_inputs"]["tp1_pts"] == 37
    assert result["config"]["reproducibility"]["subbars_count"] == 25


def test_explicit_preset_resolves_workspace_before_poisoned_files_change(jobs_module, manager, deferred):
    preset = manager.root.parent / "presets" / "scoped.json"
    preset.parent.mkdir(exist_ok=True)
    preset.write_text('{"tp2_pts":43,"_meta":{"commission":7}}')
    poison = manager.root.parent / "inputs.NQ.json"
    poison.write_text('{"tp2_pts":999}')
    jobs = jobs_module.ScopedWorkspaceJobs(manager)
    receipt = jobs.submit_backtest("cc1", "NQ", {"expected_revision": 0, "preset": "scoped"})
    preset.write_text('{"tp2_pts":999,"_meta":{"commission":999}}')
    (manager.root.parent / "inputs.json").write_text('{"tp2_pts":999}')
    deferred.run()
    result = jobs.get("cc1", receipt["job"])["result"]
    assert result["config"]["preset"] == "scoped"
    assert result["config"]["commission"] == 7
    effective = result["config"]["reproducibility"]["effective_config"]["base_inputs"]
    assert effective["tp2_pts"] == 43 and effective["tp1_pts"] == 11
    assert not any("inputs.NQ.json" in s for s in result["sources"])
    assert poison.read_text() == '{"tp2_pts":999}'


def test_explicit_null_workspace_preset_identity_survives_replay(jobs_module, manager, deferred):
    manager.profiles["cc1"]["asset_overrides"]["NQ"] = {"preset": None}
    runner = manager.portfolios["cc1"].runners["NQ"]
    runner.cfg.preset = "fallback-identity-must-not-leak"
    jobs = jobs_module.ScopedWorkspaceJobs(manager)
    receipt = jobs.submit_backtest("cc1", "NQ", {"expected_revision": 0})
    deferred.run()
    assert jobs.get("cc1", receipt["job"])["result"]["config"]["preset"] is None


@pytest.mark.parametrize("method", ["submit_config", "submit_backtest"])
@pytest.mark.parametrize("body,status", [({}, 400), ({"expected_revision": True}, 400),
    ({"expected_revision": -1}, 400), ({"expected_revision": 1}, 409)])
def test_revision_rejections_never_schedule(jobs_module, manager, deferred, method, body, status):
    jobs = jobs_module.ScopedWorkspaceJobs(manager)
    before = manager._path("cc1").read_bytes()
    _error(jobs_module, status, lambda: getattr(jobs, method)("cc1", "NQ", body))
    assert not deferred.pending and manager._path("cc1").read_bytes() == before


@pytest.mark.parametrize("body", [
    {"commission": -1}, {"timeframe": "30S"}, {"inputs": {"tp1_pts": float("nan")}},
    {"inputs": {"unknown": 2}}, {"preset": "../escape"}, {"unknown": True},
    {"inputs": {"htf_tf_1": "999"}},
])
def test_invalid_replay_is_rejected_before_acceptance(jobs_module, manager, deferred, body):
    jobs = jobs_module.ScopedWorkspaceJobs(manager)
    _error(jobs_module, 400, lambda: jobs.submit_backtest("cc1", "NQ", {"expected_revision": 0, **body}))
    assert not deferred.pending


def test_missing_unwarmed_noncanonical_assets_never_schedule(jobs_module, manager, deferred):
    jobs = jobs_module.ScopedWorkspaceJobs(manager)
    for symbol in ("nq", " NQ", "NOPE", "*"):
        _error(jobs_module, 400 if symbol != "NOPE" else 404,
               lambda: jobs.submit_backtest("cc1", symbol, {"expected_revision": 0}))
    manager.portfolios["cc1"].runners["NQ"].warm = False
    for method in (jobs.submit_backtest, jobs.submit_config):
        _error(jobs_module, 409, lambda: method("cc1", "NQ", {"expected_revision": 0, "inputs": {"tp1_pts": 31}}))
    manager.portfolios.pop("cc4")
    _error(jobs_module, 503, lambda: jobs.submit_backtest("cc4", "NQ", {"expected_revision": 0}))
    assert not deferred.pending


def test_config_idempotency_overlapping_conflicts_and_body_freeze(jobs_module, manager, deferred):
    jobs = jobs_module.ScopedWorkspaceJobs(manager)
    body = {"expected_revision": 0, "inputs": {"tp1_pts": 31}}
    first = jobs.submit_config("cc1", "NQ", body)
    duplicate = jobs.submit_config("cc1", "NQ", copy.deepcopy(body))
    assert first == {"job": first["job"], "workspace_id": "cc1", "config_revision": 0, "created": True}
    assert duplicate == {**first, "created": False}
    _error(jobs_module, 409, lambda: jobs.submit_config("cc1", "NQ", {**body, "inputs": {"tp1_pts": 32}}))
    _error(jobs_module, 409, lambda: jobs.submit_config("cc1", "*", body))
    sibling = jobs.submit_config("cc2", "NQ", body)
    body["inputs"]["tp1_pts"] = 999
    deferred.run(1)
    deferred.run()
    for workspace, receipt in (("cc1", first), ("cc2", sibling)):
        row = jobs.get(workspace, receipt["job"])
        assert row["status"] == "done", row
        assert row["result"]["config_revision"] == 1
        assert manager.portfolios[workspace].runners["NQ"].inputs_base.tp1_pts == 31
    assert manager.portfolios["cc1"].runners["ES"].inputs_base.tp1_pts == 11


def test_config_commit_rechecks_revision_and_preserves_file(jobs_module, manager, deferred):
    jobs = jobs_module.ScopedWorkspaceJobs(manager)
    receipt = jobs.submit_config("cc1", "NQ", {"expected_revision": 0, "inputs": {"tp1_pts": 31}})
    manager.update_asset("cc1", "NQ", {"expected_revision": 0, "inputs": {"tp1_pts": 17}})
    expected = manager._path("cc1").read_bytes()
    deferred.run()
    row = jobs.get("cc1", receipt["job"])
    assert row["status"] == "error" and "revision" in row["error"]
    assert manager.profiles["cc1"]["config_revision"] == 1
    assert manager._path("cc1").read_bytes() == expected


def test_config_replay_failure_retains_exact_bytes_and_revision(jobs_module, manager, deferred, monkeypatch):
    jobs = jobs_module.ScopedWorkspaceJobs(manager)
    expected = manager._path("cc1").read_bytes()
    def fail(*_args, **_kwargs):
        raise RuntimeError("offline replay injection")
    monkeypatch.setattr(manager.portfolios["cc1"].runners["ES"], "rewarm", fail)
    receipt = jobs.submit_config("cc1", "*", {"expected_revision": 0, "inputs": {"tp1_pts": 31}})
    deferred.run()
    assert jobs.get("cc1", receipt["job"])["status"] == "error"
    assert manager._path("cc1").read_bytes() == expected
    assert manager.profiles["cc1"]["config_revision"] == 0


def test_global_cap_preserves_active_and_evicts_oldest_completed(jobs_module, manager, deferred):
    jobs = jobs_module.ScopedWorkspaceJobs(manager)
    receipts = [jobs.submit_backtest("cc1", "NQ", {"expected_revision": 0}) for _ in range(20)]
    _error(jobs_module, 409, lambda: jobs.submit_backtest("cc2", "NQ", {"expected_revision": 0}))
    assert len(deferred.pending) == 20
    deferred.run(1)
    newest = jobs.submit_backtest("cc2", "NQ", {"expected_revision": 0})
    _error(jobs_module, 404, lambda: jobs.get("cc1", receipts[1]["job"]))
    assert jobs.get("cc1", receipts[0]["job"])["status"] == "running"
    assert jobs.get("cc2", newest["job"])["status"] == "running"
    while deferred.pending:
        deferred.run()


@pytest.mark.parametrize("failure", ["construct", "start"])
def test_worker_start_failure_is_not_acknowledged_or_reserved(jobs_module, manager, deferred, monkeypatch, failure):
    jobs = jobs_module.ScopedWorkspaceJobs(manager)
    expected = manager._path("cc1").read_bytes()
    def cannot_start(**_kwargs):
        if failure == "construct":
            raise RuntimeError("thread construction injection")
        class Thread:
            def start(self):
                raise RuntimeError("thread capacity injection")
        return Thread()
    monkeypatch.setattr(jobs_module, "Thread", cannot_start)
    body = {"expected_revision": 0, "inputs": {"tp1_pts": 31}}
    _error(jobs_module, 503, lambda: jobs.submit_config("cc1", "NQ", body))
    assert manager._path("cc1").read_bytes() == expected
    monkeypatch.setattr(jobs_module, "Thread", deferred.thread)
    receipt = jobs.submit_config("cc1", "NQ", body)
    assert receipt["created"] is True
    deferred.run()
    assert jobs.get("cc1", receipt["job"])["status"] == "done"


def test_identical_config_reuses_running_job_during_locked_commit(jobs_module, manager, monkeypatch):
    jobs = jobs_module.ScopedWorkspaceJobs(manager)
    entered, release, answered = threading.Event(), threading.Event(), threading.Event()
    original = manager.portfolios["cc1"].reconfigure
    def hold_commit(*args, **kwargs):
        entered.set()
        assert release.wait(3)
        return original(*args, **kwargs)
    monkeypatch.setattr(manager.portfolios["cc1"], "reconfigure", hold_commit)
    body = {"expected_revision": 0, "inputs": {"tp1_pts": 31}}
    first = jobs.submit_config("cc1", "NQ", body)
    assert entered.wait(3)
    answers = []
    def duplicate():
        try:
            answers.append(jobs.submit_config("cc1", "NQ", body))
        except Exception as error:
            answers.append(error)
        finally:
            answered.set()
    caller = threading.Thread(target=duplicate)
    caller.start()
    try:
        assert answered.wait(.5), "active duplicate must reuse the receipt while the commit lock is held"
        assert answers == [{**first, "created": False}]
    finally:
        release.set()
        caller.join(3)
    deadline = time.monotonic() + 3
    while jobs.get("cc1", first["job"])["status"] == "running" and time.monotonic() < deadline:
        time.sleep(.005)
    assert jobs.get("cc1", first["job"])["status"] == "done"


def test_real_backtest_threads_in_two_workspaces_run_independently(jobs_module, manager, monkeypatch):
    jobs = jobs_module.ScopedWorkspaceJobs(manager)
    entered, release = threading.Event(), threading.Event()
    original = jobs_module.run_backtest
    def held_replay(port, symbol, **kwargs):
        if port.runners[symbol].inputs_base.tp1_pts == 11:
            entered.set()
            assert release.wait(3)
        return original(port, symbol, **kwargs)
    monkeypatch.setattr(jobs_module, "run_backtest", held_replay)
    first = jobs.submit_backtest("cc1", "NQ", {"expected_revision": 0})
    assert entered.wait(3)
    try:
        second = jobs.submit_backtest("cc2", "NQ", {"expected_revision": 0})
        deadline = time.monotonic() + 2
        while jobs.get("cc2", second["job"])["status"] == "running" and time.monotonic() < deadline:
            time.sleep(.005)
        assert jobs.get("cc2", second["job"])["status"] == "done"
        assert jobs.get("cc1", first["job"])["status"] == "running"
    finally:
        release.set()
    deadline = time.monotonic() + 3
    while jobs.get("cc1", first["job"])["status"] == "running" and time.monotonic() < deadline:
        time.sleep(.005)
    assert jobs.get("cc1", first["job"])["status"] == "done"


@pytest.mark.parametrize("symbol", ["NQ", "*"])
@pytest.mark.parametrize("cost,value", [("commission", -7), ("capital", 0),
                                       ("slippage_ticks", -1), ("slippage_ticks", 1.5)])
def test_configuration_preset_costs_fail_before_acceptance(jobs_module, manager, deferred, symbol, cost, value):
    preset = manager.root.parent / "presets" / "invalid-costs.json"
    preset.parent.mkdir(exist_ok=True)
    preset.write_text(json.dumps({"_meta": {cost: value}}))
    jobs = jobs_module.ScopedWorkspaceJobs(manager)
    settings = {"preset": "invalid-costs"}
    body = {"expected_revision": 0, **(settings if symbol == "NQ" else {"asset_overrides": {"NQ": settings}})}
    before = manager._path("cc1").read_bytes()
    _error(jobs_module, 400, lambda: jobs.submit_config("cc1", symbol, body))
    assert not deferred.pending and not jobs._jobs
    assert manager.profiles["cc1"]["config_revision"] == 0
    assert manager._path("cc1").read_bytes() == before


def test_explicit_preset_invalid_costs_fail_before_acceptance(jobs_module, manager, deferred):
    preset = manager.root.parent / "presets" / "invalid-costs.json"
    preset.parent.mkdir(exist_ok=True)
    preset.write_text('{"tp2_pts":43,"_meta":{"commission":-7}}')
    jobs = jobs_module.ScopedWorkspaceJobs(manager)
    _error(jobs_module, 400, lambda: jobs.submit_backtest("cc1", "NQ", {"expected_revision": 0, "preset": "invalid-costs"}))
    assert not deferred.pending


def test_real_configuration_jobs_in_two_workspaces_commit_independently(jobs_module, manager, monkeypatch):
    jobs = jobs_module.ScopedWorkspaceJobs(manager)
    entered, release, answered = threading.Event(), threading.Event(), threading.Event()
    original = manager.portfolios["cc1"].reconfigure
    def held_config(*args, **kwargs):
        entered.set()
        assert release.wait(3)
        return original(*args, **kwargs)
    monkeypatch.setattr(manager.portfolios["cc1"], "reconfigure", held_config)
    body = {"expected_revision": 0, "inputs": {"tp1_pts": 31}}
    first = jobs.submit_config("cc1", "NQ", body)
    assert entered.wait(3)
    answers = []
    def other_workspace():
        try:
            second = jobs.submit_config("cc2", "NQ", body)
            deadline = time.monotonic() + 2
            while jobs.get("cc2", second["job"])["status"] == "running" and time.monotonic() < deadline:
                time.sleep(.005)
            answers.append(jobs.get("cc2", second["job"]))
        except Exception as error:
            answers.append(error)
        finally:
            answered.set()
    caller = threading.Thread(target=other_workspace)
    caller.start()
    try:
        assert answered.wait(.5), "CC2 configuration must finish while CC1 owns its replay transaction"
        assert answers[0]["status"] == "done", answers
        assert manager.profiles["cc2"]["config_revision"] == 1
        assert jobs.get("cc1", first["job"])["status"] == "running"
    finally:
        release.set()
        caller.join(3)
    deadline = time.monotonic() + 3
    while jobs.get("cc1", first["job"])["status"] == "running" and time.monotonic() < deadline:
        time.sleep(.005)
    assert jobs.get("cc1", first["job"])["status"] == "done"


def test_rewarm_job_reuses_active_request_and_commits_only_selected_runner(jobs_module, manager, deferred, monkeypatch):
    jobs = jobs_module.ScopedWorkspaceJobs(manager)
    port = manager.portfolios["cc1"]
    before = port.runners["ES"].em
    body = {"expected_revision": 0}
    receipt = jobs.submit_rewarm("cc1", "NQ", body)
    again = jobs.submit_rewarm("cc1", "NQ", body)
    assert receipt["created"] is True and again["created"] is False and receipt["job"] == again["job"]
    assert len(deferred.pending) == 1
    _error(jobs_module, 409, lambda: jobs.submit_config("cc1", "NQ", {"expected_revision": 0, "inputs": {"tp1_pts": 17}}))
    _error(jobs_module, 404, lambda: jobs.get("cc2", receipt["job"]))
    deferred.run()
    row = jobs.get("cc1", receipt["job"])
    assert row["status"] == "done" and row["kind"] == "config" and row["config_revision"] == 0
    assert row["result"]["config_revision"] == 1 and row["result"]["rewarmed_assets"] == ["NQ"]
    assert port.runners["ES"].em is before


@pytest.mark.parametrize("body,status", [({}, 400), ({"expected_revision": True}, 400),
                                        ({"expected_revision": 1}, 409),
                                        ({"expected_revision": 0, "asset": "ES"}, 400)])
def test_rewarm_job_admission_is_revisioned_and_exact(jobs_module, manager, deferred, body, status):
    jobs = jobs_module.ScopedWorkspaceJobs(manager)
    _error(jobs_module, status, lambda: jobs.submit_rewarm("cc1", "NQ", body))
    assert not jobs._jobs and not deferred.pending


def test_rewarm_job_rechecks_revision_at_commit(jobs_module, manager, deferred):
    jobs = jobs_module.ScopedWorkspaceJobs(manager)
    receipt = jobs.submit_rewarm("cc1", "NQ", {"expected_revision": 0})
    manager.update_asset("cc1", "ES", {"expected_revision": 0, "inputs": {"tp1_pts": 71}})
    deferred.run()
    row = jobs.get("cc1", receipt["job"])
    assert row["status"] == "error" and "revision" in row["error"]
    assert manager.profiles["cc1"]["config_revision"] == 1
