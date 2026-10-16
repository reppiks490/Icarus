"""Futures replay must stay on one continuous-contract price basis."""

from icarus_engine.assets import resolve
from icarus_engine.pine.timeframe import Bar
from icarus_engine.runtime import AssetRunner, Journal, RunnerConfig
from icarus_engine.strategy.inputs import Inputs


class Yahoo:
    def __init__(self):
        self.calls = []

    def candles(self, symbol, granularity, start, end):
        self.calls.append((symbol, granularity, start, end))
        return [Bar(start, 100, 101, 99, 100, 1), Bar(start + granularity, 101, 102, 100, 101, 1)]

    def ticker(self, symbol):
        return 101


class Databento(Yahoo):
    def candles(self, symbol, granularity, start, end):
        self.calls.append((symbol, granularity, start, end))
        return [Bar(start, 5000, 5001, 4999, 5000, 1), Bar(start + granularity, 5001, 5002, 5000, 5001, 1)]


def make_runner(tmp_path, primary, auxiliary):
    spec = resolve("NQ")
    cfg = RunnerConfig(spec, Inputs(), fixed_pts_scale=1, mintick=spec.mintick, base_dir=str(tmp_path))
    return AssetRunner(cfg, Journal(":memory:"), {"yahoo": primary, "databento_history": auxiliary})


def test_warmup_uses_only_selected_primary_continuous_source(tmp_path, monkeypatch):
    monkeypatch.delenv("ICARUS_FEED", raising=False)
    monkeypatch.setenv("ICARUS_DATABENTO_HISTORY_DAYS", "7")
    now = 1_800_000_000

    yahoo, databento = Yahoo(), Databento()
    yahoo_runner = make_runner(tmp_path / "yahoo", yahoo, databento)
    yahoo_bars = []
    yahoo_on_sub_bar = yahoo_runner.on_sub_bar
    def capture_yahoo(bar, minutes, live=False):
        yahoo_bars.append(bar.c)
        yahoo_on_sub_bar(bar, minutes, live=live)
    yahoo_runner.on_sub_bar = capture_yahoo
    yahoo_runner.warmup(now)
    assert yahoo.calls and not databento.calls
    assert yahoo_bars and set(yahoo_bars) == {100, 101}

    databento, yahoo = Databento(), Yahoo()
    databento_runner = make_runner(tmp_path / "databento", databento, yahoo)
    databento_bars = []
    databento_on_sub_bar = databento_runner.on_sub_bar
    def capture_databento(bar, minutes, live=False):
        databento_bars.append(bar.c)
        databento_on_sub_bar(bar, minutes, live=live)
    databento_runner.on_sub_bar = capture_databento
    databento_runner.warmup(now)
    assert databento.calls and not yahoo.calls
    assert databento_bars and set(databento_bars) == {5000}
    assert all(start >= now - 7 * 86400 for _, _, start, _ in databento.calls)


def test_databento_primary_failure_does_not_fall_back_to_yahoo(tmp_path, monkeypatch):
    monkeypatch.delenv("ICARUS_FEED", raising=False)
    monkeypatch.setenv("ICARUS_DATABENTO_HISTORY_DAYS", "7")
    databento, yahoo = Databento(), Yahoo()

    def unavailable(*args):
        raise RuntimeError("history unavailable")

    databento.candles = unavailable
    runner = make_runner(tmp_path, databento, yahoo)
    try:
        runner.warmup(1_800_000_000)
    except RuntimeError as exc:
        assert "history unavailable" in str(exc)
    else:
        raise AssertionError("Databento history failure must fail warm-up")
    assert not yahoo.calls


def test_empty_databento_history_does_not_mark_runner_warm(tmp_path, monkeypatch):
    monkeypatch.delenv("ICARUS_FEED", raising=False)
    monkeypatch.setenv("ICARUS_DATABENTO_HISTORY_DAYS", "7")

    def empty_candles(self, symbol, granularity, start, end):
        self.calls.append((symbol, granularity, start, end))
        return []

    EmptyDatabento = type("Databento", (Databento,), {"candles": empty_candles})

    databento, yahoo = EmptyDatabento(), Yahoo()
    runner = make_runner(tmp_path, databento, yahoo)
    try:
        runner.warmup(1_800_000_000)
    except RuntimeError as exc:
        assert "returned no replay bars" in str(exc)
    else:
        raise AssertionError("empty Databento history must not mark warm-up complete")
    assert not runner.warm
    assert not yahoo.calls
