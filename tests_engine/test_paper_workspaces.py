import copy
import threading

from icarus_engine import paper_workspaces
from icarus_engine.assets import REGISTRY as ASSET_REGISTRY
from icarus_engine.pine.timeframe import Bar
from icarus_engine.runtime import Inputs, Journal


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
        self.journal.con.close()

    def runner_list(self):
        return self.runners

    def status(self, *, nonblocking=False):
        return {"assets": [], "all_warm": self.started, "net": 0.0}

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
