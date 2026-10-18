import copy
import sqlite3
import threading
from types import SimpleNamespace
from http.server import ThreadingHTTPServer

import pytest

from icarus_engine import paper_workspaces
from icarus_engine.assets import REGISTRY as ASSET_REGISTRY
from icarus_engine.pine.timeframe import Bar
from icarus_engine.runtime import Inputs, Journal, Portfolio
from icarus_engine.server import serve


class _Parent:
    def __init__(self, base_dir):
        self.base_dir = str(base_dir)
        self.poll_sec = 5.0
        self.profile = "nq"
        self.preset = None
        self.warmup_bars = 1200
        self.pts_ref_symbol = "NQ"
        self.pts_ref_price = 0.0
        self.feeds = {"yahoo": object(), "coinbase": object()}


class _Runner:
    def __init__(self):
        self.paused = False
        self.pause_calls = []
        self.flatten_calls = []
        self.symbol = "NQ"
        self.inputs_base = Inputs()

    def set_paused(self, paused):
        self.paused = paused
        self.pause_calls.append(paused)
        return 0

    def flatten(self, reason):
        self.flatten_calls.append(reason)
        return 1


class _WorkspacePortfolio:
    def __init__(self, journal, *_args, workspace, **kwargs):
        self.journal = journal
        self.workspace = workspace
        self.feeds = kwargs["feeds"]
        self.pts_ref_price = 0.0
        self.paused = False
        self._lock = threading.RLock()
        self.runners = [_Runner()]
        self.assets = []
        self.reconfigure_calls = []
        self.started = False

    def add_asset(self, spec, *, start):
        self.assets.append(spec)

    def start(self):
        self.started = True

    def stop(self):
        self.journal.close()

    def runner_list(self):
        return self.runners

    def status(self, *, nonblocking=False):
        return getattr(self, "status_data", {"assets": [], "all_warm": self.started, "net": 0.0})

    def reconfigure(self, candidate):
        self.reconfigure_calls.append(copy.deepcopy(candidate))
        return {"ok": True, "id": candidate["id"]}


def _manager(tmp_path, monkeypatch):
    monkeypatch.setattr(
        paper_workspaces,
        "_PROFILE_DEFAULTS",
        tuple({**profile, "assets": ["NQ"]} for profile in paper_workspaces._PROFILE_DEFAULTS),
    )
    monkeypatch.setattr(paper_workspaces, "REGISTRY", {"NQ": object()})
    monkeypatch.setattr(paper_workspaces, "WorkspacePortfolio", _WorkspacePortfolio)
    return paper_workspaces.PaperWorkspaceManager(_Parent(tmp_path))


def _real_manager(tmp_path, monkeypatch):
    """Use real portfolios/runners but suppress their live polling threads."""
    monkeypatch.setattr(
        paper_workspaces,
        "_PROFILE_DEFAULTS",
        tuple({**profile, "assets": ["NQ"]} for profile in paper_workspaces._PROFILE_DEFAULTS),
    )
    monkeypatch.setattr(paper_workspaces, "REGISTRY", {"NQ": copy.deepcopy(ASSET_REGISTRY["NQ"])})
    monkeypatch.setattr(paper_workspaces.WorkspacePortfolio, "start", lambda self: None)
    return paper_workspaces.PaperWorkspaceManager(_Parent(tmp_path))


def test_default_profiles_keep_the_requested_starting_assumptions():
    defaults = {profile["id"]: profile for profile in paper_workspaces._PROFILE_DEFAULTS}
    baseline = Inputs()

    assert len(defaults) == 4
    assert defaults["cc1"]["chart"]["timeframe"] == "20"
    assert defaults["cc1"]["chart"]["chart_type"] == "heikin_ashi"
    assert defaults["cc2"]["chart"]["timeframe"] == "5"
    assert defaults["cc2"]["inputs"] == {
        "tp1_pts": baseline.tp1_pts / 2,
        "tp2_pts": baseline.tp2_pts / 2,
        "qty_contracts": baseline.qty_contracts * 2,
    }
    assert "ETH" in defaults["cc2"]["assets"]
    assert defaults["cc3"]["chart"]["timeframe"] == "20"
    assert defaults["cc4"]["chart"]["timeframe"] == "5"


def test_start_uses_separate_ledgers_and_shared_feed_wrappers(tmp_path, monkeypatch):
    manager = _manager(tmp_path, monkeypatch)
    manager.start()
    try:
        assert set(manager.portfolios) == {"cc1", "cc2", "cc3", "cc4"}
        portfolios = list(manager.portfolios.values())
        assert all(portfolio.started for portfolio in portfolios)
        assert len({portfolio.journal.path for portfolio in portfolios}) == 4
        assert all(portfolio.feeds is manager._feeds for portfolio in portfolios)
        assert len({id(portfolio.feeds["yahoo"]) for portfolio in portfolios}) == 1
        assert [len(portfolio.assets) for portfolio in portfolios] == [1, 1, 1, 1]
    finally:
        manager.stop()


def test_edit_pause_and_flatten_only_touch_the_selected_workspace(tmp_path, monkeypatch):
    manager = _manager(tmp_path, monkeypatch)
    manager.start()
    try:
        result = manager.update("cc2", {"inputs": {"tp1_pts": 9.0}})
        assert result["id"] == "cc2"
        assert manager.portfolios["cc2"].reconfigure_calls
        assert not manager.portfolios["cc1"].reconfigure_calls
        assert manager.profiles["cc2"]["inputs"]["tp1_pts"] == 9.0
        assert manager.profiles["cc1"]["inputs"] == {}

        manager.pause("cc3", True)
        assert manager.portfolios["cc3"].paused is True
        assert manager.portfolios["cc3"].runners[0].pause_calls == [True]
        assert manager.portfolios["cc1"].paused is False
        assert manager.portfolios["cc1"].runners[0].pause_calls == []

        flattened = manager.flatten("cc4")
        assert flattened["flattened_positions"] == 1
        assert manager.portfolios["cc4"].paused is True
        assert manager.portfolios["cc4"].runners[0].flatten_calls == ["workspace"]
        assert manager.portfolios["cc3"].runners[0].flatten_calls == []

        saved = manager._path("cc2")
        assert '"tp1_pts": 9.0' in saved.read_text(encoding="utf-8")
    finally:
        manager.stop()


def test_manager_stop_closes_real_workspace_journals_idempotently(tmp_path, monkeypatch):
    monkeypatch.setattr(
        paper_workspaces,
        "_PROFILE_DEFAULTS",
        tuple({**profile, "assets": []} for profile in paper_workspaces._PROFILE_DEFAULTS),
    )
    parent = _Parent(tmp_path)
    parent.feeds = {}
    manager = paper_workspaces.PaperWorkspaceManager(parent)
    manager.start()
    journals = [portfolio.journal for portfolio in manager.portfolios.values()]

    manager.stop()
    manager.stop()

    assert all(not portfolio._sampler_thread.is_alive() for portfolio in manager.portfolios.values())
    for journal in journals:
        with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
            journal.con.execute("SELECT 1")


def test_manager_stop_continues_cleanup_after_workspace_stop_error(tmp_path, monkeypatch):
    manager = _real_manager(tmp_path, monkeypatch)
    manager.start()
    portfolios = list(manager.portfolios.values())
    journals = [portfolio.journal for portfolio in portfolios]
    stopped = []
    for portfolio in portfolios:
        original_stop = portfolio.stop

        def stop_with_one_failure(original_stop=original_stop, portfolio=portfolio):
            stopped.append(portfolio.workspace["id"])
            if portfolio.workspace["id"] == "cc4":
                raise RuntimeError("forced workspace stop failure")
            return original_stop()

        portfolio.stop = stop_with_one_failure

    with pytest.raises(RuntimeError, match="forced workspace stop failure"):
        manager.stop()

    assert set(stopped) == set(manager.portfolios)
    for journal in journals:
        with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
            journal.con.execute("SELECT 1")


def test_manager_start_failure_closes_every_created_workspace_journal(tmp_path, monkeypatch):
    monkeypatch.setattr(
        paper_workspaces,
        "_PROFILE_DEFAULTS",
        tuple({**profile, "assets": []} for profile in paper_workspaces._PROFILE_DEFAULTS),
    )
    parent = _Parent(tmp_path)
    parent.feeds = {}
    manager = paper_workspaces.PaperWorkspaceManager(parent)
    real_start = paper_workspaces.WorkspacePortfolio.start

    def fail_second_workspace(portfolio):
        if portfolio.workspace["id"] == "cc2":
            raise RuntimeError("forced workspace start failure")
        real_start(portfolio)

    monkeypatch.setattr(paper_workspaces.WorkspacePortfolio, "start", fail_second_workspace)
    try:
        with pytest.raises(RuntimeError, match="forced workspace start failure"):
            manager.start()
        for portfolio in manager.portfolios.values():
            with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
                portfolio.journal.con.execute("SELECT 1")
    finally:
        manager.stop()


def test_manager_start_closes_journal_when_workspace_constructor_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(
        paper_workspaces,
        "_PROFILE_DEFAULTS",
        tuple({**profile, "assets": []} for profile in paper_workspaces._PROFILE_DEFAULTS),
    )
    parent = _Parent(tmp_path)
    parent.feeds = {}
    manager = paper_workspaces.PaperWorkspaceManager(parent)
    created_journals = []
    real_journal = paper_workspaces.Journal

    def capture_journal(*args, **kwargs):
        journal = real_journal(*args, **kwargs)
        created_journals.append(journal)
        return journal

    def fail_constructor(*_args, **_kwargs):
        raise RuntimeError("forced workspace constructor failure")

    monkeypatch.setattr(paper_workspaces, "Journal", capture_journal)
    monkeypatch.setattr(paper_workspaces.WorkspacePortfolio, "__init__", fail_constructor)
    try:
        with pytest.raises(RuntimeError, match="forced workspace constructor failure"):
            manager.start()

        assert len(created_journals) == 1
        with pytest.raises(sqlite3.ProgrammingError, match="closed database"):
            created_journals[0].con.execute("SELECT 1")
    finally:
        manager.stop()
        for journal in created_journals:
            journal.close()


def test_manager_defers_journal_close_until_slow_worker_exits(tmp_path, monkeypatch):
    monkeypatch.setattr(
        paper_workspaces,
        "_PROFILE_DEFAULTS",
        tuple({**profile, "assets": []} for profile in paper_workspaces._PROFILE_DEFAULTS),
    )
    parent = _Parent(tmp_path)
    parent.feeds = {}
    manager = paper_workspaces.PaperWorkspaceManager(parent)
    manager.start()
    portfolio = manager.portfolios["cc1"]
    journal = portfolio.journal
    release_worker = threading.Event()
    closer_waiting = threading.Event()
    journal_closed = threading.Event()
    real_close = journal.close

    def record_close():
        real_close()
        journal_closed.set()

    journal.close = record_close

    class _SlowWorker:
        def is_alive(self):
            return not release_worker.is_set()

        def join(self, timeout=None):
            if timeout is None:
                closer_waiting.set()
                release_worker.wait()

    portfolio._threads["slow"] = _SlowWorker()
    try:
        manager.stop()
        assert closer_waiting.wait(timeout=1)
        assert not journal_closed.is_set()
        assert journal.con.execute("SELECT 1").fetchone() == (1,)
        release_worker.set()
        assert journal_closed.wait(timeout=1)
    finally:
        release_worker.set()
        manager.stop()
def test_workspace_configuration_persists_only_to_its_own_profile(tmp_path, monkeypatch):
    manager = _manager(tmp_path, monkeypatch)
    manager.start()
    try:
        manager.update("cc2", {
            "chart": {"timeframe": "10", "chart_type": "real"},
            "inputs": {"tp1_pts": 9.0},
        })
        manager.update("cc4", {"inputs": {"tp1_pts": 11.0}})
    finally:
        manager.stop()

    reloaded = _manager(tmp_path, monkeypatch)
    assert reloaded.profiles["cc2"]["chart"]["timeframe"] == "10"
    assert reloaded.profiles["cc2"]["chart"]["chart_type"] == "real"
    assert reloaded.profiles["cc2"]["inputs"]["tp1_pts"] == 9.0
    assert reloaded.profiles["cc4"]["inputs"]["tp1_pts"] == 11.0
    assert reloaded.profiles["cc1"]["inputs"] == {}
    assert reloaded.profiles["cc3"]["inputs"] == {}
    assert reloaded.profiles["cc1"]["chart"]["timeframe"] == "20"
    assert reloaded.profiles["cc4"]["chart"]["timeframe"] == "5"


def test_shared_feed_candle_cache_fetches_only_uncovered_ranges():
    class Feed:
        def __init__(self):
            self.calls = []

        def candles(self, symbol, granularity, start_ts, end_ts):
            self.calls.append((symbol, granularity, start_ts, end_ts))
            return [
                Bar(ts, 1.0, 2.0, 0.5, 1.5, 10.0)
                for ts in range(start_ts, end_ts, granularity)
            ]

    raw = Feed()
    shared = paper_workspaces.SharedFeed(raw)

    assert [bar.ts for bar in shared.candles("NQ", 60, 0, 180)] == [0, 60, 120]
    assert [bar.ts for bar in shared.candles("NQ", 60, 60, 240)] == [60, 120, 180]
    assert raw.calls == [("NQ", 60, 0, 180), ("NQ", 60, 180, 240)]


def test_real_workspace_runners_positions_journals_and_pnl_are_isolated(tmp_path, monkeypatch):
    manager = _real_manager(tmp_path, monkeypatch)
    manager.start()
    try:
        assert set(manager.portfolios) == {"cc1", "cc2", "cc3", "cc4"}
        portfolios = [manager.portfolios[key] for key in ("cc1", "cc2", "cc3", "cc4")]
        runners = [portfolio.runner_list()[0] for portfolio in portfolios]

        # Each profile owns its runner, input object, emulator, and journal. The
        # shared feed wrapper is only a market-data dependency.
        assert len({id(runner) for runner in runners}) == 4
        assert len({id(runner.inputs_base) for runner in runners}) == 4
        assert len({id(runner.em) for runner in runners}) == 4
        assert len({id(portfolio.journal) for portfolio in portfolios}) == 4
        assert len({portfolio.journal.path for portfolio in portfolios}) == 4
        assert all(runner.journal is portfolio.journal for runner, portfolio in zip(runners, portfolios))
        assert runners[1].inputs_base.tp1_pts == Inputs().tp1_pts / 2
        assert runners[0].inputs_base.tp1_pts == Inputs().tp1_pts

        # Place positions through each actual emulator. No runner/feed polling
        # is started, so this exercises paper accounting without network access.
        for runner, direction, qty, entry, mark in (
            (runners[0], 1, 2, 100.0, 110.0),
            (runners[1], -1, 1, 200.0, 190.0),
        ):
            runner.em.entry("isolation", direction, qty)
            runner.em.process_bar(Bar(1, entry, entry, entry, entry, 0), 0)
            runner.last_price = mark

        snapshot = manager.snapshot()
        assert snapshot["mode"] == "concurrent_paper"
        assert snapshot["execution_authorized"] is False
        profiles = {profile["id"]: profile for profile in snapshot["profiles"]}
        assert set(profiles) == {"cc1", "cc2", "cc3", "cc4"}
        assert all(profile["paper_only"] and profile["execution_authorized"] is False for profile in profiles.values())

        multiplier = runners[0].em.contract_size
        expected_cc1 = (110.0 - 100.0) * 2 * multiplier - runners[0].em.commission * 2
        expected_cc2 = (200.0 - 190.0) * multiplier - runners[1].em.commission
        assert profiles["cc1"]["status"]["positions"] == 1
        assert profiles["cc1"]["status"]["net"] == expected_cc1
        assert profiles["cc2"]["status"]["positions"] == 1
        assert profiles["cc2"]["status"]["net"] == expected_cc2
        for profile_id in ("cc3", "cc4"):
            assert profiles[profile_id]["status"]["positions"] == 0
            assert profiles[profile_id]["status"]["net"] == 0.0

        # This is the per-profile data the dashboard sums for Combined paper P&L.
        assert sum(profile["status"]["net"] for profile in profiles.values()) == expected_cc1 + expected_cc2
    finally:
        manager.stop()
        for portfolio in manager.portfolios.values():
            portfolio.journal.con.close()


def test_server_close_attempts_all_services_and_closes_socket_after_workspace_error(tmp_path, monkeypatch):
    port = Portfolio(Journal(":memory:"), str(tmp_path))
    server = serve(port, 0, start=False)
    closed_services = []
    base_server_close = ThreadingHTTPServer.server_close

    def fail_workspace_stop(_manager):
        raise RuntimeError("fixture workspace shutdown failure")

    def record_autopilot_close(_autopilot):
        closed_services.append("autopilot")

    def record_base_server_close(instance):
        closed_services.append("http-server")
        return base_server_close(instance)

    monkeypatch.setattr(type(server.command_centers), "stop", fail_workspace_stop)
    monkeypatch.setattr(type(server.autopilot), "close", record_autopilot_close)
    monkeypatch.setattr(ThreadingHTTPServer, "server_close", record_base_server_close)

    with pytest.raises(RuntimeError, match="background service\\(s\\) failed to close"):
        server.server_close()

    assert closed_services == ["autopilot", "http-server"]
    assert server.fileno() == -1
    port.journal.close()


def test_snapshot_tallies_distinct_paper_ledgers_without_replay_profit(tmp_path, monkeypatch):
    manager = _manager(tmp_path, monkeypatch)
    manager.start()
    try:
        for profile_id, profit, live in (("cc1", 125.0, 1), ("cc2", -30.0, 1), ("cc3", 900.0, 0)):
            journal = manager.portfolios[profile_id].journal
            journal.con.execute(
                "INSERT INTO trades (symbol,entry_id,direction,qty,entry_price,entry_ts,exit_price,exit_ts,exit_comment,profit,live) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                ("NQ", profile_id, 1, 1, 100.0, 1000, 101.0, 1060, "test", profit, live),
            )
            journal.con.commit()
        for idx, portfolio in enumerate(manager.portfolios.values()):
            portfolio.status_data = {
                "assets": [{"symbol": "NQ", "feed_provider": "yahoo", "warm": True,
                            "poll_age": 4.0, "market": {"open": True}, "feed_delay": 600.0}],
                "all_warm": True, "capital": 1000.0, "equity": 1000.0 + idx,
                "net": float(idx), "open_profit": 2.0, "positions": 1,
            }
        snapshot = manager.snapshot()
        assert snapshot["aggregate"]["paper_pnl"] == 95.0
        assert snapshot["aggregate"]["open_pnl"] == 8.0
        assert snapshot["aggregate"]["net"] == 6.0
        assert snapshot["aggregate"]["open_positions"] == 4
        assert snapshot["profiles"][2]["pnl"]["realized_pnl"] == 0.0
        assert snapshot["connections"]["feeds"][0]["status"] == "delayed"
        assert all(not adapter["execution_authorized"] for adapter in snapshot["connections"]["adapters"])
    finally:
        manager.stop()


def test_shared_databento_wrapper_exposes_cached_session_health():
    class Databento:
        def meta(self, symbol):
            assert symbol == "NQ"
            return {"core_session_ok": False, "mapping_active": True}

    feed = paper_workspaces.SharedFeed(Databento())
    assert feed.provider_name == "databento"
    assert feed.cached_meta("NQ") == {"core_session_ok": False, "mapping_active": True}


def test_flatten_attempts_every_runner_and_reports_partial_failures(tmp_path, monkeypatch):
    manager = _manager(tmp_path, monkeypatch)
    manager.start()
    try:
        portfolio = manager.portfolios["cc1"]
        first, second, third = _Runner(), _Runner(), _Runner()
        first.symbol, second.symbol, third.symbol = "NQ", "ES", "YM"
        first.flatten = lambda _reason: 2

        def fail_flatten(_reason):
            raise RuntimeError("paper journal unavailable")

        second.flatten = fail_flatten
        third.flatten = lambda _reason: 1
        portfolio.runners = [first, second, third]

        with pytest.raises(paper_workspaces.FlattenUnavailableError, match=r"3 position\(s\) closed") as caught:
            manager.flatten("cc1")

        assert [runner.flatten_calls for runner in (first, second, third)] == [[], [], []]
        assert [runner.paused for runner in (first, second, third)] == [True, True, True]
        assert caught.value.flattened_positions == 3
        assert caught.value.partial is True
        assert caught.value.failed_assets == [{"asset": "ES", "detail": "RuntimeError: paper journal unavailable"}]
    finally:
        manager.stop()


def test_flatten_counts_primary_closures_when_runner_raises_after_mutation(tmp_path, monkeypatch):
    manager = _manager(tmp_path, monkeypatch)
    manager.start()
    try:
        portfolio = manager.portfolios["cc1"]
        first, second = _Runner(), _Runner()
        first.symbol, second.symbol = "NQ", "ES"
        first.em = SimpleNamespace(open=[SimpleNamespace(entry_id="first")], shadow=None)
        second.em = SimpleNamespace(open=[SimpleNamespace(entry_id="second")], shadow=None)
        first.last_price = second.last_price = 100.0
        first.flatten = lambda _reason: first.em.open.clear() or 1

        def close_then_raise(_reason):
            second.em.open.clear()
            raise RuntimeError("receipt write failed")

        second.flatten = close_then_raise
        portfolio.runners = [first, second]
        with pytest.raises(paper_workspaces.FlattenUnavailableError) as caught:
            manager.flatten("cc1")
        assert caught.value.flattened_positions == 2
        assert caught.value.partial is True
        assert caught.value.failed_assets == [{"asset": "ES", "detail": "RuntimeError: receipt write failed"}]
    finally:
        manager.stop()


def test_flatten_reports_shadow_censor_separately_from_primary_closures(tmp_path, monkeypatch):
    manager = _manager(tmp_path, monkeypatch)
    manager.start()
    try:
        runner = manager.portfolios["cc1"].runners[0]
        runner.em = SimpleNamespace(
            open=[], shadow=SimpleNamespace(open=[SimpleNamespace(entry_id="shadow-only")]))
        runner.last_price = 100.0
        runner.flatten = lambda _reason: runner.em.shadow.open.clear() or 1
        result = manager.flatten("cc1")
        assert result["flattened_positions"] == 0
        assert result["shadow_censored_positions"] == 1
    finally:
        manager.stop()


def test_flatten_separates_primary_close_and_shadow_censor_counts(tmp_path, monkeypatch):
    manager = _manager(tmp_path, monkeypatch)
    manager.start()
    try:
        runner = manager.portfolios["cc1"].runners[0]
        runner.em = SimpleNamespace(
            open=[SimpleNamespace(entry_id="primary")],
            shadow=SimpleNamespace(open=[SimpleNamespace(entry_id="shadow")]),
        )
        runner.last_price = 100.0

        def flatten(_reason):
            runner.em.open.clear()
            runner.em.shadow.open.clear()
            return 2

        runner.flatten = flatten
        result = manager.flatten("cc1")
        assert result["flattened_positions"] == 1
        assert result["shadow_censored_positions"] == 1
    finally:
        manager.stop()


def test_flatten_requires_mark_for_primary_or_shadow_open_positions(tmp_path, monkeypatch):
    manager = _manager(tmp_path, monkeypatch)
    manager.start()
    try:
        runner = manager.portfolios["cc1"].runners[0]
        runner.symbol = "NQ"
        runner.em = SimpleNamespace(open=[], shadow=SimpleNamespace(open=[object()]))
        runner.last_price = None

        with pytest.raises(paper_workspaces.FlattenUnavailableError, match="valid observed mark"):
            manager.flatten("cc1")

        assert runner.paused is True
        assert runner.flatten_calls == []
    finally:
        manager.stop()


def _selection_manager(tmp_path, monkeypatch):
    monkeypatch.setenv("ICARUS_FEED", "file")
    monkeypatch.setattr(paper_workspaces, "_PROFILE_DEFAULTS", tuple(
        {**profile, "assets": ["NQ"]} for profile in paper_workspaces._PROFILE_DEFAULTS))
    monkeypatch.setattr(paper_workspaces.WorkspacePortfolio, "start", lambda self: None)
    parent = _Parent(tmp_path)
    parent.feeds = {"yahoo": SimpleNamespace(ticker=lambda _s: 100.0), "coinbase": object()}
    manager = paper_workspaces.PaperWorkspaceManager(parent)
    manager.start()
    return manager


def test_explicit_asset_selection_survives_reload_for_every_workspace(tmp_path, monkeypatch):
    manager = _selection_manager(tmp_path, monkeypatch)
    try:
        for profile_id in ("cc1", "cc2", "cc3", "cc4"):
            result = manager.update(profile_id, {"assets": ["NQ", "CL", "MCL", "ETH"]})
            assert result["assets"] == ["NQ", "CL", "MCL", "ETH"]
            assert list(manager.portfolios[profile_id].runners) == ["NQ", "CL", "MCL", "ETH"]
        reloaded = paper_workspaces.PaperWorkspaceManager(manager.parent)
        assert all(p["assets"] == ["NQ", "CL", "MCL", "ETH"] for p in reloaded.profiles.values())
    finally:
        manager.stop()


@pytest.mark.parametrize("assets", [[], "NQ", None, ["NQ", "NQ"], ["nq"], ["UNKNOWN"], [True], ["NQ"] * 100])
def test_asset_selection_rejects_invalid_payload_without_mutation(tmp_path, monkeypatch, assets):
    manager = _selection_manager(tmp_path, monkeypatch)
    try:
        before = manager._path("cc1").read_bytes()
        runner = manager.portfolios["cc1"].runners["NQ"]
        with pytest.raises(ValueError):
            manager.update("cc1", {"assets": assets})
        assert manager._path("cc1").read_bytes() == before
        assert manager.portfolios["cc1"].runners == {"NQ": runner}
    finally:
        manager.stop()


def test_asset_only_change_preserves_retained_open_runner_and_journal(tmp_path, monkeypatch):
    manager = _selection_manager(tmp_path, monkeypatch)
    try:
        portfolio = manager.portfolios["cc1"]
        runner = portfolio.runners["NQ"]
        runner.em.process_bar(Bar(0, 100, 100, 100, 100, 1), 0)
        runner.em.entry("keep", 1, 1)
        runner.em.process_bar(Bar(60, 100, 100, 100, 100, 1), 1)
        original = runner.configuration_snapshot()
        journal = portfolio.journal
        manager.update("cc1", {"assets": ["NQ", "CL"]})
        assert portfolio.runners["NQ"] is runner and runner.em.position_size == 1
        assert portfolio.journal is journal and runner.configuration_snapshot() == original
        assert manager.profiles["cc2"]["assets"] == ["NQ"]
        with pytest.raises(ValueError, match="open|pending|flatten"):
            manager.update("cc1", {"assets": ["CL"]})
        assert portfolio.runners["NQ"] is runner and runner.em.position_size == 1
        assert manager.profiles["cc1"]["assets"] == ["NQ", "CL"]
    finally:
        manager.stop()


@pytest.mark.parametrize("pending", ["_pending_entries", "_pending_closes"])
def test_asset_removal_preserves_pending_orders(tmp_path, monkeypatch, pending):
    manager = _selection_manager(tmp_path, monkeypatch)
    try:
        runner = manager.portfolios["cc1"].runners["NQ"]
        getattr(runner.em, pending).append(object())
        with pytest.raises(ValueError, match="pending|flatten"):
            manager.update("cc1", {"assets": ["CL"]})
        assert manager.portfolios["cc1"].runners["NQ"] is runner
        assert len(getattr(runner.em, pending)) == 1
    finally:
        manager.stop()


def test_asset_selection_failure_rolls_back_maps_profile_and_gated_workers(tmp_path, monkeypatch):
    manager = _selection_manager(tmp_path, monkeypatch)
    try:
        portfolio = manager.portfolios["cc1"]
        original_runner = portfolio.runners["NQ"]
        before = manager._path("cc1").read_bytes()
        spawned = []
        original_spawn = portfolio._spawn
        def fail_second(runner):
            original_spawn(runner)
            spawned.append(portfolio._threads[runner.symbol])
            if len(spawned) == 2:
                raise RuntimeError("injected thread start failure")
        monkeypatch.setattr(portfolio, "_spawn", fail_second)
        monkeypatch.setattr(paper_workspaces.Portfolio, "_run", lambda *_: pytest.fail("uncommitted runner started"))
        # Mark this test portfolio as started without starting its baseline worker.
        portfolio._sampler_thread = SimpleNamespace(is_alive=lambda: True, join=lambda *_: None)
        with pytest.raises(RuntimeError, match="injected"):
            manager.update("cc1", {"assets": ["NQ", "CL", "MCL"]})
        assert portfolio.runners == {"NQ": original_runner}
        assert portfolio.order == ["NQ"]
        assert manager._path("cc1").read_bytes() == before
        assert manager.profiles["cc1"]["assets"] == ["NQ"]
        assert all(not t.is_alive() for t in spawned)
    finally:
        manager.stop()


def test_snapshot_exposes_catalog_without_promoting_execution_or_access(tmp_path, monkeypatch):
    manager = _selection_manager(tmp_path, monkeypatch)
    try:
        available = {r["symbol"]: r for r in manager.snapshot()["available_assets"]}
        assert set(available) == set(ASSET_REGISTRY)
        assert len([r for r in available.values() if r["kind"] == "futures"]) == 32
        assert available["CL"]["selectable"] is True
        assert available["CL"]["execution_qualified"] is False
        assert available["MCL"]["full_root"] == "CL"
        assert available["CL"]["feed_mode"] == "public_delayed"
        assert available["CL"]["data_access_verified"] is False
        assert all(r["execution_authorized"] is False for r in available.values())
    finally:
        manager.stop()


def test_saved_invalid_assets_fail_closed_on_reload(tmp_path, monkeypatch):
    import json
    manager = _selection_manager(tmp_path, monkeypatch)
    try:
        profile = copy.deepcopy(manager.profiles["cc3"])
        profile["assets"] = ["a200:equity:NVDA"]
        manager._path("cc3").write_text(json.dumps(profile))
        with pytest.raises(ValueError, match="assets"):
            paper_workspaces.PaperWorkspaceManager(manager.parent)
    finally:
        manager.stop()


def test_flat_asset_removal_and_construction_failure_preserve_other_runners(tmp_path, monkeypatch):
    manager = _selection_manager(tmp_path, monkeypatch)
    try:
        portfolio = manager.portfolios["cc4"]
        old = portfolio.runners["NQ"]
        old.warm = True
        original_make = portfolio.make_runner
        def fail_second(spec, **kwargs):
            if spec.symbol == "MCL":
                raise RuntimeError("injected construction failure")
            return original_make(spec, **kwargs)
        monkeypatch.setattr(portfolio, "make_runner", fail_second)
        before = manager._path("cc4").read_bytes()
        with pytest.raises(RuntimeError, match="injected"):
            manager.update("cc4", {"assets": ["CL", "MCL"]})
        assert portfolio.runners == {"NQ": old} and not old._removed
        assert manager._path("cc4").read_bytes() == before
        manager.update("cc4", {"assets": ["CL"]})
        assert list(portfolio.runners) == ["CL"] and old._removed and old.paused
        assert manager.portfolios["cc1"].runners["NQ"]._removed is False
    finally:
        manager.stop()


def test_snapshot_marks_missing_runtime_accounting_unknown(tmp_path, monkeypatch):
    manager = _selection_manager(tmp_path, monkeypatch)
    try:
        snapshot = manager.snapshot()
        assert snapshot["aggregate"]["accounting_complete"] is True
        missing = manager.portfolios.pop("cc2")
        snapshot = manager.snapshot()
        assert snapshot["aggregate"]["accounting_complete"] is False
        assert snapshot["aggregate"]["runtime_count"] == 3
        assert snapshot["aggregate"]["missing_runtime_ids"] == ["cc2"]
        assert next(p for p in snapshot["profiles"] if p["id"] == "cc2")["runtime_available"] is False
        assert snapshot["aggregate"]["reconciliation_status"] == "NO_BROKER_RECONCILIATION"
        assert snapshot["aggregate"]["fees_status"] == "SIMULATOR_CONFIGURED_NOT_BROKER_RECONCILED"
        manager.portfolios["cc2"] = missing
    finally:
        manager.stop()


def test_asset_selection_save_failure_never_changes_running_portfolio(tmp_path, monkeypatch):
    manager = _selection_manager(tmp_path, monkeypatch)
    try:
        original = manager.portfolios["cc1"].runners["NQ"]
        before = manager._path("cc1").read_bytes()
        monkeypatch.setattr(manager, "_save", lambda *_: (_ for _ in ()).throw(OSError("disk refused")))
        with pytest.raises(OSError, match="disk refused"):
            manager.update("cc1", {"assets": ["NQ", "CL"]})
        assert manager.portfolios["cc1"].runners == {"NQ": original}
        assert manager._path("cc1").read_bytes() == before
        assert manager.profiles["cc1"]["assets"] == ["NQ"]
    finally:
        manager.stop()


def test_removal_keeps_worker_handle_until_shutdown_and_new_asset_inherits_pause(tmp_path, monkeypatch):
    manager = _selection_manager(tmp_path, monkeypatch)
    try:
        portfolio = manager.portfolios["cc1"]
        portfolio.runners["NQ"].warm = True
        worker = SimpleNamespace(is_alive=lambda: False)
        portfolio._threads["NQ"] = worker
        portfolio.paused = True
        manager.update("cc1", {"assets": ["CL"]})
        assert portfolio.runners["CL"].paused is True
        assert worker in portfolio._threads.values()
        assert "NQ" not in portfolio._threads
    finally:
        manager.stop()


def test_asset_start_failure_restores_successfully_replayed_existing_configuration(tmp_path, monkeypatch):
    manager = _selection_manager(tmp_path, monkeypatch)
    try:
        portfolio = manager.portfolios["cc1"]
        runner = portfolio.runners["NQ"]
        runner.warm = True
        before = runner.configuration_snapshot()
        before_profile = manager._path("cc1").read_bytes()
        monkeypatch.setattr(runner, "ensure_cached_timeframes", lambda *_: None)
        monkeypatch.setattr(runner, "ensure_cached_chart_timeframe", lambda tf: tf)
        replayed = []
        def replay(inputs, sources, **kwargs):
            replayed.append(inputs.tp1_pts)
            runner.inputs_base = inputs
            runner.bar_index = 123
        monkeypatch.setattr(runner, "rewarm", replay)
        portfolio._sampler_thread = SimpleNamespace(is_alive=lambda: True, join=lambda *_: None)
        monkeypatch.setattr(portfolio, "_spawn", lambda *_: (_ for _ in ()).throw(RuntimeError("spawn refused")))
        with pytest.raises(RuntimeError, match="spawn refused"):
            manager.update("cc1", {"assets": ["NQ", "CL"], "inputs": {"tp1_pts": 17.0}})
        assert replayed == [17.0]
        assert runner.configuration_snapshot() == before
        assert portfolio.runners == {"NQ": runner}
        assert manager._path("cc1").read_bytes() == before_profile
        assert portfolio.workspace["inputs"] == {}
    finally:
        manager.stop()


def test_removal_does_not_orphan_active_strategy_overlay(tmp_path, monkeypatch):
    manager = _selection_manager(tmp_path, monkeypatch)
    try:
        portfolio = manager.portfolios["cc1"]
        runner = portfolio.runners["NQ"]
        runner.warm = True
        runner._activation_version_id = "active-overlay"
        with pytest.raises(ValueError, match="overlay"):
            manager.update("cc1", {"assets": ["CL"]})
        assert portfolio.runners == {"NQ": runner} and not runner._removed
    finally:
        manager.stop()


def test_open_position_without_mark_or_stale_view_makes_aggregate_incomplete(tmp_path, monkeypatch):
    manager = _selection_manager(tmp_path, monkeypatch)
    try:
        portfolio = manager.portfolios["cc1"]
        runner = portfolio.runners["NQ"]
        runner.em.entry("missing-mark", 1, 1)
        runner.em.process_bar(Bar(1, 100, 100, 100, 100, 0), 0)
        assert runner.last_price is None
        snapshot = manager.snapshot()
        profile = next(p for p in snapshot["profiles"] if p["id"] == "cc1")
        assert profile["runtime_available"] is True
        assert profile["valuation_complete"] is False and profile["missing_mark_symbols"] == ["NQ"]
        assert snapshot["aggregate"]["accounting_complete"] is False
        assert snapshot["aggregate"]["valuation_status"] == "PAPER_VALUATION_INCOMPLETE"
        runner.last_price = 101.0
        assert manager.snapshot()["aggregate"]["accounting_complete"] is True
        original_status = portfolio.status
        monkeypatch.setattr(portfolio, "status", lambda **kwargs: {**original_status(**kwargs), "view_stale": True})
        assert manager.snapshot()["aggregate"]["accounting_complete"] is False
    finally:
        manager.stop()
