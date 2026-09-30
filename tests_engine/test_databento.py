"""Databento adapter tests — all SDK/network behavior is mocked."""
from __future__ import annotations

import os

from icarus_engine.feeds.databento import Databento, _aggregate, continuous_symbol
from icarus_engine.pine.timeframe import Bar


class Rec:
    def __init__(self, ts, o, h, l, c, v=1):
        self.ts_event = int(ts) * 1_000_000_000
        self.pretty_open = o
        self.pretty_high = h
        self.pretty_low = l
        self.pretty_close = c
        self.volume = v


class Store(list):
    pass


class FakeTimeseries:
    def __init__(self, records_by_schema):
        self.records_by_schema = records_by_schema
        self.calls = []

    def get_range(self, **kwargs):
        self.calls.append(dict(kwargs))
        return Store(self.records_by_schema.get(kwargs["schema"], []))


class FakeHistorical:
    def __init__(self, records_by_schema):
        self.timeseries = FakeTimeseries(records_by_schema)


class FakeLive:
    instances = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.subscriptions = []
        self.callback = None
        self.exception_callback = None
        self.started = False
        self.stopped = False
        FakeLive.instances.append(self)

    def subscribe(self, **kwargs):
        self.subscriptions.append(dict(kwargs))

    def add_callback(self, callback, exception_callback=None):
        self.callback = callback
        self.exception_callback = exception_callback

    def start(self):
        self.started = True
        # Emit genuine 1-second OHLCV immediately so recent_ex can consume it.
        self.callback(Rec(120, 100, 101, 99, 100.5, 3))
        self.callback(Rec(121, 100.5, 102, 100, 101.5, 4))

    def stop(self):
        self.stopped = True


def test_continuous_symbol_uses_volume_front_contract():
    assert continuous_symbol("NQ=F") == "NQ.v.0"
    assert continuous_symbol("CME_MINI:NQ1!") == "NQ.v.0"
    assert continuous_symbol("ES.v.0") == "ES.v.0"
    assert continuous_symbol("GC1!") == "GC.v.0"


def test_historical_one_second_request_is_continuous_and_nanosecond_ranged():
    hist = FakeHistorical({
        "ohlcv-1s": [Rec(100, 10, 11, 9, 10.5, 2), Rec(101, 10.5, 12, 10, 11.5, 3)],
    })
    feed = Databento(historical_client=hist, live=False)
    bars = feed.candles("NQ=F", 1, 100, 102)
    assert [(b.ts, b.o, b.c, b.v) for b in bars] == [(100, 10.0, 10.5, 2.0), (101, 10.5, 11.5, 3.0)]
    call = hist.timeseries.calls[-1]
    assert call["dataset"] == "GLBX.MDP3"
    assert call["schema"] == "ohlcv-1s"
    assert call["stype_in"] == "continuous"
    assert call["symbols"] == ["NQ.v.0"]
    assert call["start"] == 100 * 1_000_000_000
    assert call["end"] == 102 * 1_000_000_000


def test_arbitrary_minute_bars_aggregate_from_native_one_minute_data():
    rows = [
        Rec(600 + 60 * k, 100 + k, 101 + k, 99 + k, 100.5 + k, k + 1)
        for k in range(5)
    ]
    hist = FakeHistorical({"ohlcv-1m": rows})
    feed = Databento(historical_client=hist, live=False)
    bars = feed.candles("ES=F", 300, 600, 900)
    assert len(bars) == 1
    b = bars[0]
    assert (b.ts, b.o, b.h, b.l, b.c, b.v) == (600, 100, 105, 99, 104.5, 15)
    assert hist.timeseries.calls[-1]["schema"] == "ohlcv-1m"
    assert hist.timeseries.calls[-1]["symbols"] == ["ES.v.0"]


def test_live_one_second_buffer_feeds_existing_minute_interface():
    FakeLive.instances.clear()
    feed = Databento(api_key="db-test", historical_client=FakeHistorical({}), live_factory=FakeLive)
    bars, feed_time, px = feed.recent_ex("NQ=F", 60, since_ts=60)
    assert len(FakeLive.instances) == 1
    live = FakeLive.instances[0]
    assert live.started is True
    assert live.subscriptions == [{
        "dataset": "GLBX.MDP3",
        "schema": "ohlcv-1s",
        "stype_in": "continuous",
        "symbols": ["NQ.v.0"],
    }]
    assert len(bars) == 1
    assert bars[0].ts == 120 and bars[0].o == 100 and bars[0].c == 101.5 and bars[0].v == 7
    assert feed_time == 122 and px == 101.5
    feed.close()
    assert live.stopped is True


def test_databento_capabilities_are_truthful_about_source_vs_chart_engine():
    feed = Databento(historical_client=FakeHistorical({}), live=False)
    caps = feed.capabilities
    assert caps["continuous_symbology"] is True
    assert caps["continuous_roll_rule"] == "volume"
    assert caps["native_seconds"] is True
    assert caps["trades_schema"] is True and caps["mbo_schema"] is True
    assert caps["engine_chart_seconds"] is False


def test_runtime_selects_databento_for_futures_when_requested(tmp_path, monkeypatch):
    import icarus_engine.runtime as runtime

    class FakeDB:
        name = "databento"
        capabilities = {"native_seconds": True}

        def close(self):
            self.closed = True

    monkeypatch.setenv("ICARUS_FEED", "databento")
    monkeypatch.setattr(runtime, "Databento", FakeDB)
    port = runtime.Portfolio(runtime.Journal(":memory:"), str(tmp_path))
    assert port.feed_mode == "databento"
    assert isinstance(port.feeds["yahoo"], FakeDB)
    assert port.feeds["yahoo"].capabilities["native_seconds"] is True
    port.stop()
    assert port.feeds["yahoo"].closed is True
