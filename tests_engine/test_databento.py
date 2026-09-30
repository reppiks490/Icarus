"""Databento adapter contract tests. No credentials or network access required."""
from __future__ import annotations

import importlib.util
import inspect
from types import SimpleNamespace

import pytest

from icarus_engine.feeds.databento import Databento
from icarus_engine.runtime import Journal, Portfolio
from icarus_plant.supervisor import default_engine_service


NS = 1_000_000_000


class Ohlcv:
    def __init__(self, ts, o, h, l, c, v=1):
        self.ts_event = int(ts * NS)
        self.open = int(o * NS)
        self.high = int(h * NS)
        self.low = int(l * NS)
        self.close = int(c * NS)
        self.pretty_open = float(o)
        self.pretty_high = float(h)
        self.pretty_low = float(l)
        self.pretty_close = float(c)
        self.volume = int(v)


class Trade:
    def __init__(self, ts, price, size=1, side="B", sequence=1):
        self.ts_event = int(ts * NS)
        self.price = int(price * NS)
        self.pretty_price = float(price)
        self.size = int(size)
        self.side = side
        self.action = "T"
        self.sequence = int(sequence)


class Level:
    def __init__(self, bid, ask, bid_sz=1, ask_sz=2):
        self.bid_px = int(bid * NS)
        self.ask_px = int(ask * NS)
        self.pretty_bid_px = float(bid)
        self.pretty_ask_px = float(ask)
        self.bid_sz = bid_sz
        self.ask_sz = ask_sz
        self.bid_ct = 1
        self.ask_ct = 1


class Depth:
    def __init__(self, ts, price=100.0, *, flags=0, order_id=7, levels=None):
        self.ts_event = int(ts * NS)
        self.price = int(price * NS)
        self.pretty_price = float(price)
        self.size = 1
        self.side = "B"
        self.action = "A"
        self.sequence = 3
        self.flags = int(flags)
        self.order_id = int(order_id)
        if levels is not None:
            self.levels = levels


class FakeStore(list):
    pass


class FakeHistorical:
    def __init__(self, records_by_schema):
        self.records_by_schema = records_by_schema
        self.calls = []
        self.timeseries = self

    def get_range(self, **kwargs):
        self.calls.append(dict(kwargs))
        return FakeStore(self.records_by_schema.get(kwargs["schema"], []))


class FakeLive:
    def __init__(self, records_by_schema=None):
        self.records_by_schema = records_by_schema or {}
        self.subscriptions = []
        self.callback = None
        self.started = False
        self.stopped = False
        self._emitted = set()

    def subscribe(self, **kwargs):
        self.subscriptions.append(dict(kwargs))
        if self.started:
            self._emit(kwargs["schema"])

    def add_callback(self, callback):
        self.callback = callback

    def _emit(self, schema):
        # Subscription upgrades after start should deliver only that new schema once.
        if schema in self._emitted or self.callback is None:
            return
        self._emitted.add(schema)
        for rec in self.records_by_schema.get(schema, []):
            self.callback(rec)

    def start(self):
        self.started = True
        for sub in self.subscriptions:
            self._emit(sub["schema"])

    def stop(self):
        self.stopped = True


class FakeSDK:
    Historical = object
    Live = object
    RecordFlags = SimpleNamespace(F_LAST=1)


def make_feed(*, historical=None, lives=None):
    live_queue = list(lives or [FakeLive()])
    return Databento(
        api_key="db-test",
        sdk=FakeSDK,
        historical=historical or FakeHistorical({}),
        live_factory=lambda: live_queue.pop(0),
    )


def test_continuous_volume_front_symbology_and_capabilities():
    assert Databento.continuous_symbol("NQ=F") == "NQ.v.0"
    assert Databento.continuous_symbol("CME_MINI:MNQ1!") == "MNQ.v.0"
    assert Databento.parent_symbol("ES=F") == "ES.FUT"
    caps = Databento.capabilities()
    assert caps["continuous_futures"] is True
    assert caps["continuous_rule"] == "volume_front"
    assert caps["minimum_ohlcv_resolution_seconds"] == 1
    assert caps["ticks"] is True
    assert caps["mbp_10"] is True and caps["mbo"] is True and caps["mbo_snapshot"] is True


def test_historical_one_second_and_lossless_resampling_use_continuous_stype():
    hist = FakeHistorical({
        "ohlcv-1s": [
            Ohlcv(100, 10, 11, 9, 10.5, 1),
            Ohlcv(101, 10.5, 12, 10, 11, 2),
            Ohlcv(104, 11, 13, 10.5, 12, 3),
            Ohlcv(105, 12, 12.5, 11.5, 12.25, 4),
        ]
    })
    feed = make_feed(historical=hist)
    bars = feed.candles("NQ=F", 5, 100, 110)
    assert len(bars) == 2
    assert (bars[0].ts, bars[0].o, bars[0].h, bars[0].l, bars[0].c, bars[0].v) == (100, 10, 13, 9, 12, 6)
    assert (bars[1].ts, bars[1].o, bars[1].c, bars[1].v) == (105, 12, 12.25, 4)
    call = hist.calls[-1]
    assert call["dataset"] == "GLBX.MDP3"
    assert call["schema"] == "ohlcv-1s"
    assert call["symbols"] == "NQ.v.0"
    assert call["stype_in"] == "continuous"


def test_historical_minute_request_uses_native_ohlcv_1m():
    hist = FakeHistorical({"ohlcv-1m": [Ohlcv(120, 20, 21, 19, 20.5, 10)]})
    feed = make_feed(historical=hist)
    bars = feed.candles("ES=F", 60, 120, 180)
    assert len(bars) == 1 and bars[0].c == 20.5
    assert hist.calls[-1]["schema"] == "ohlcv-1m"
    assert hist.calls[-1]["symbols"] == "ES.v.0"


def test_live_second_bars_trades_and_depth_can_share_one_session():
    second_rows = [Ohlcv(1_000 + i, 100 + i / 10, 101 + i / 10, 99 + i / 10, 100.5 + i / 10, 1) for i in range(60)]
    trade = Trade(1_059, 106.5, 3)
    depth = Depth(1_060, 106.25, levels=[Level(106.0, 106.25)])
    live = FakeLive({"ohlcv-1s": second_rows, "trades": [trade], "mbp-10": [depth]})
    feed = make_feed(lives=[live])

    bars, ft, px = feed.recent_ex("NQ=F", 60)
    assert len(bars) == 2  # 1000-1019 partial UTC minute + 1020-1059 full minute
    assert ft == 1_059 and px == 106.5
    assert [s["schema"] for s in live.subscriptions][:2] == ["ohlcv-1s", "trades"]
    assert all(s["symbols"] == "NQ.v.0" and s["stype_in"] == "continuous" for s in live.subscriptions)

    ticks = feed.trades("NQ=F")
    assert ticks and ticks[-1].price == 106.5 and ticks[-1].size == 3

    depth_rows = feed.depth_events("NQ=F", schema="mbp-10")
    assert depth_rows and depth_rows[-1]["levels"][0]["bid_px"] == 106.0
    assert any(s["schema"] == "mbp-10" for s in live.subscriptions)


def test_mbo_snapshot_requests_continuous_snapshot_and_stops():
    snapshot = Depth(2_000, 200.25, flags=1)
    live = FakeLive({"mbo": [snapshot]})
    feed = make_feed(lives=[live])
    rows = feed.mbo_snapshot("ES=F", timeout=0.2)
    assert rows and rows[0]["order_id"] == 7
    sub = live.subscriptions[0]
    assert sub["schema"] == "mbo"
    assert sub["snapshot"] is True
    assert sub["symbols"] == "ES.v.0"
    assert sub["stype_in"] == "continuous"
    assert live.stopped is True


def test_portfolio_databento_mode_routes_futures_transport(monkeypatch, tmp_path):
    sentinel = object()
    monkeypatch.setenv("ICARUS_FEED", "databento")
    monkeypatch.setattr("icarus_engine.runtime.Databento", lambda: sentinel)
    port = Portfolio(Journal(":memory:"), str(tmp_path))
    assert port.feed_mode == "databento"
    assert port.feeds["yahoo"] is sentinel


def test_plant_databento_launch_sets_env_and_engine_flag(tmp_path):
    svc = default_engine_service(str(tmp_path), str(tmp_path), feed="databento")
    assert svc.env["ICARUS_FEED"] == "databento"
    assert "--feed" in svc.argv
    i = svc.argv.index("--feed")
    assert svc.argv[i + 1] == "databento"


def test_real_databento_sdk_is_installed_when_extra_is_present():
    if importlib.util.find_spec("databento") is None:
        pytest.skip("optional databento extra is not installed")
    import databento as db
    assert hasattr(db, "Historical")
    assert hasattr(db, "Live")
    assert hasattr(db, "RecordFlags") and hasattr(db.RecordFlags, "F_LAST")
    assert callable(getattr(db.Live, "subscribe", None))
    assert callable(getattr(db.Live, "add_callback", None))
    assert callable(getattr(db.Live, "start", None))
    assert callable(getattr(db.Live, "stop", None))
    params = inspect.signature(db.Live.subscribe).parameters
    for name in ("dataset", "schema", "symbols", "stype_in", "start", "snapshot"):
        assert name in params
