import copy
import threading

from icarus_engine import paper_workspaces
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
