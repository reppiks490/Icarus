from __future__ import annotations

from types import SimpleNamespace
import threading

import pytest

from icarus_engine.autopilot import TacticalAutopilot
from icarus_engine.strategy.inputs import Inputs


@pytest.fixture(autouse=True)
def _freeze_passthrough(monkeypatch):
    monkeypatch.setattr(
        "icarus_engine.autopilot.freeze_replay_port",
        lambda port, asset: port,
    )


class FakeRunner:
    def __init__(self):
        self.symbol = "NQ"
        self.inputs = Inputs()
        self.inputs_base = Inputs()
        self.spec = SimpleNamespace(chart_type="real")
        self.lock = threading.RLock()
        self.warm = True


class FakePort:
    def __init__(self, root):
        self.base_dir = str(root)
        self.runners = {"NQ": FakeRunner()}

    def runner_list(self):
        return list(self.runners.values())


def fake_result(inputs, *, better=False):
    capital = 100_000.0
    pnl = 600.0 if better else 200.0
    trades = []
    for i in range(12):
        trades.append({
            "open": False,
            "pnl": 100.0 if i < 8 else -50.0,
        })
    return {
        "bars": 1000,
        "equity": [[1, capital], [2, capital + pnl]],
        "drawdown": [[1, 0.0], [2, -100.0]],
        "trades": trades,
        "config": {
            "capital": capital,
            "reproducibility": {
                "historical_scale_asof_valid": True,
                "source_config_sha256": "a" * 64,
                "effective_config_sha256": "b" * 64,
                "subbars_sha256": "c" * 64,
            },
        },
    }


def test_autopilot_baseline_then_bounded_mutation_can_replace_champion(tmp_path, monkeypatch):
    port = FakePort(tmp_path)
    original = port.runners["NQ"].inputs.to_dict()
    calls = []

    def replay(_port, asset, **kwargs):
        assert asset == "NQ"
        calls.append(kwargs)
        changed = kwargs["inputs"] != original or kwargs.get("chart_type") != "real" or kwargs.get("session") is not None
        return fake_result(kwargs["inputs"], better=changed)

    monkeypatch.setattr("icarus_engine.autopilot.run_backtest", replay)
    ap = TacticalAutopilot(port)
    first = ap.cycle_once()
    assert first["champions"]["NQ"]["delta"]["kind"] == "baseline"
    baseline_score = first["champions"]["NQ"]["metrics"]["score"]

    second = ap.cycle_once()
    assert len(second["history"]) == 2
    assert second["champions"]["NQ"]["metrics"]["score"] > baseline_score
    assert second["champions"]["NQ"]["delta"]["kind"] in {"input", "context"}
    assert port.runners["NQ"].inputs.to_dict() == original
    assert second["live_input_mutation"] is False
    assert second["paper_input_mutation"] is False
    assert second["execution_authorized"] is False
    assert all(call["fill_on"] == "real" for call in calls)


def test_autopilot_state_is_durable_and_leaderboard_is_sorted(tmp_path, monkeypatch):
    port = FakePort(tmp_path)
    monkeypatch.setattr(
        "icarus_engine.autopilot.run_backtest",
        lambda _port, asset, **kwargs: fake_result(kwargs["inputs"], better=len(kwargs["inputs"]) > 0),
    )
    ap = TacticalAutopilot(port)
    ap.cycle_once()
    restored = TacticalAutopilot(port).status()
    assert "NQ" in restored["champions"]
    assert restored["history"]
    scores = [row["metrics"]["score"] for row in restored["leaderboard"]]
    assert scores == sorted(scores, reverse=True)


def test_autopilot_protects_economic_scale_inputs(tmp_path):
    ap = TacticalAutopilot(FakePort(tmp_path))
    dims = dict(ap._eligible(Inputs().to_dict()))
    assert "qty_contracts" not in dims
    assert "point_value" not in dims
    assert "size_mode" not in dims
    assert "risk_usd_per_trade" not in dims
    assert "tide_qty" not in dims
    assert "use_conviction_sizing" not in dims
    assert all(not name.endswith("_qty") for name in dims)
    assert all(not name.startswith("rate_") for name in dims)
    assert all(not name.startswith("htf_tf_") for name in dims)


def test_autopilot_configuration_is_fail_closed(tmp_path):
    ap = TacticalAutopilot(FakePort(tmp_path))
    with pytest.raises(ValueError, match="cadence_seconds"):
        ap.configure({"cadence_seconds": 1})
    with pytest.raises(ValueError, match="assets"):
        ap.configure({"assets": ["ES"]})
    with pytest.raises(ValueError, match="robustness_windows"):
        ap.configure({"robustness_windows": 4})
    with pytest.raises(ValueError, match="unknown"):
        ap.configure({"god_mode": True})


def test_score_penalizes_no_trade_and_historical_invalidity():
    good = fake_result({}, better=True)
    good_score = TacticalAutopilot._score(good, 8)["score"]

    invalid = fake_result({}, better=True)
    invalid["config"]["reproducibility"]["historical_scale_asof_valid"] = False
    assert TacticalAutopilot._score(invalid, 8)["score"] < good_score

    empty = fake_result({}, better=True)
    empty["trades"] = []
    assert TacticalAutopilot._score(empty, 8)["score"] == -999.0


def test_autopilot_cycle_lock_prevents_overlapping_replays(tmp_path, monkeypatch):
    ap = TacticalAutopilot(FakePort(tmp_path))
    monkeypatch.setattr(
        "icarus_engine.autopilot.run_backtest",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("overlapping replay launched")),
    )
    assert ap._cycle_lock.acquire(blocking=False)
    try:
        status = ap.cycle_once()
        assert status["cycle_busy"] is True
        assert status["history"] == []
        with pytest.raises(ValueError, match="cycle is active"):
            ap.reset()
    finally:
        ap._cycle_lock.release()


def test_autopilot_start_can_resume_single_worker_after_stop_signal(tmp_path):
    ap = TacticalAutopilot(FakePort(tmp_path))
    class Alive:
        @staticmethod
        def is_alive():
            return True
    ap._thread = Alive()
    ap._stop.set()
    status = ap.start()
    assert not ap._stop.is_set()
    assert status["config"]["enabled"] is True
    assert status["running"] is True


def test_new_champion_is_mirrored_to_system_intelligence(tmp_path, monkeypatch):
    port = FakePort(tmp_path)
    seen = []
    monkeypatch.setattr(
        "icarus_engine.autopilot.run_backtest",
        lambda _port, asset, **kwargs: fake_result(kwargs["inputs"], better=True),
    )
    monkeypatch.setattr(
        "icarus_engine.autopilot.append_system_event",
        lambda base, event: seen.append((base, event)) or {"status": "ok"},
    )
    ap = TacticalAutopilot(port)
    ap.cycle_once()
    assert len(seen) == 1
    event = seen[0][1]
    assert event["kind"] == "integration"
    assert "Tactical Autopilot champion" in event["title"]
    assert "shadow-only" in event["detail"]


def test_robustness_score_penalizes_recent_window_collapse(tmp_path, monkeypatch):
    port = FakePort(tmp_path)
    ap = TacticalAutopilot(port)
    candidate = {
        "id": "candidate",
        "asset": "NQ",
        "inputs": port.runners["NQ"].inputs.to_dict(),
        "chart_type": "real",
        "session": None,
        "fill_on": "real",
        "delta": {"kind": "baseline", "name": "current_engine", "from": None, "to": None},
        "reason": "test",
    }
    state = ap._read()
    state["active"] = {"candidate": candidate, "stage": "backtest", "started": 1.0}
    ap._write(state)

    def replay(_port, asset, **kwargs):
        result = fake_result(kwargs["inputs"], better=True)
        result["range"] = {"start": 0, "end": 1000}
        if kwargs.get("window_start", 0) >= 750:
            result["trades"] = []
            result["equity"] = [[750, 100000.0], [1000, 100000.0]]
            result["drawdown"] = [[750, 0.0], [1000, 0.0]]
        return result

    monkeypatch.setattr("icarus_engine.autopilot.run_backtest", replay)
    _full, metrics = ap._evaluate_candidate(
        candidate,
        {**ap._read()["config"], "robustness_windows": 3},
    )
    assert metrics["robustness_windows"] == 3
    assert metrics["full_score"] > metrics["score"]
    assert metrics["worst_window_score"] == -999.0
    assert len(metrics["window_scores"]) == 3


def test_tactical_scheduler_switches_from_exploration_to_learned_exploitation(tmp_path, monkeypatch):
    port = FakePort(tmp_path)
    original = port.runners["NQ"].inputs.to_dict()

    def replay(_port, asset, **kwargs):
        changed = kwargs["inputs"] != original or kwargs.get("chart_type") != "real" or kwargs.get("session") is not None
        return fake_result(kwargs["inputs"], better=changed)

    monkeypatch.setattr("icarus_engine.autopilot.run_backtest", replay)
    ap = TacticalAutopilot(port)
    ap.configure({"robustness_windows": 1, "enabled": False})
    ap.cycle_once()  # baseline
    second = ap.cycle_once()
    learned = second["history"][-1]["dimension_key"]
    assert second["history"][-1]["search_mode"] == "explore"
    assert learned in second["dimension_stats"]

    third = ap.cycle_once()
    assert third["history"][-1]["search_mode"] == "exploit"
    assert third["history"][-1]["dimension_key"] == learned
