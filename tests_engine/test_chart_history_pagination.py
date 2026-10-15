from collections import deque

from icarus_engine.assets import AssetSpec
from icarus_engine.pine.timeframe import Bar
from icarus_engine.runtime import AssetRunner, Journal, RunnerConfig
from icarus_engine.strategy.inputs import Inputs


def make_runner_with_history(count=8):
    spec = AssetSpec("TEST", "TEST", "yahoo", "TEST", "crypto", 1, 1,
                     chart_tf="1", commission=0, roll="none")
    runner = AssetRunner(
        RunnerConfig(spec, Inputs(use_tide=False, use_eod_flat=False)),
        Journal(":memory:"),
    )
    runner.bars = deque(
        [Bar(index * 60, 100 + index, 101 + index, 99 + index, 100.5 + index, 1)
         for index in range(count)],
        maxlen=runner.bars.maxlen,
    )
    runner.overlays = deque(
        [{"ts": index * 60, "marker": index} for index in range(count)],
        maxlen=runner.overlays.maxlen,
    )
    runner.recent_fills = deque(
        [{"ts": index * 60, "id": f"fill-{index}"} for index in range(count)],
        maxlen=runner.recent_fills.maxlen,
    )
    return runner


def test_chart_history_pages_align_bars_overlays_fills_and_metadata():
    runner = make_runner_with_history()

    page = runner.chart(n=3, offset=2)

    assert [row[0] for row in page["bars"]] == [180, 240, 300]
    assert [row["ts"] for row in page["overlays"]] == [180, 240, 300]
    assert [row["id"] for row in page["fills"]] == ["fill-3", "fill-4", "fill-5"]
    assert page["history"] == {
        "available": 8, "offset": 2, "page_size": 3,
        "has_older": True, "has_newer": True,
    }


def test_chart_history_latest_page_and_empty_out_of_range_page():
    runner = make_runner_with_history()

    latest = runner.chart(n=3)
    assert [row[0] for row in latest["bars"]] == [300, 360, 420]
    assert latest["history"]["has_older"] is True
    assert latest["history"]["has_newer"] is False

    beyond_history = runner.chart(n=3, offset=99)
    assert beyond_history["bars"] == []
    assert beyond_history["overlays"] == []
    assert beyond_history["fills"] == []
    assert beyond_history["history"] == {
        "available": 8, "offset": 99, "page_size": 3,
        "has_older": False, "has_newer": True,
    }


def test_chart_history_direct_page_arguments_are_bounded():
    runner = make_runner_with_history()

    empty = runner.chart(n=0, offset=-4)
    assert len(empty["bars"]) == 1
    assert empty["history"]["page_size"] == 1
    assert empty["history"]["offset"] == 0

    far = runner.chart(n=9_000, offset=60_000)
    assert far["bars"] == []
    assert far["history"]["page_size"] == 5_000
    assert far["history"]["offset"] == 50_000
