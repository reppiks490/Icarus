"""Databento adapter contract tests. No credentials or network access required."""
from __future__ import annotations

import importlib.util
import inspect
import json
import threading
import urllib.request
from types import SimpleNamespace

import pytest

from icarus_engine.assets import CHART_TIMEFRAME_OPTIONS, resolve
from icarus_engine.pine.timeframe import tf_minutes
from icarus_engine.feeds.databento import Databento
from icarus_engine.runtime import AssetRunner, Journal, Portfolio, RunnerConfig
from icarus_engine.server import serve
from icarus_engine.strategy.inputs import Inputs
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
    def __init__(self, ts, price, size=1, side="B", sequence=1, instrument_id=0):
        self.ts_event = int(ts * NS)
        self.price = int(price * NS)
        self.pretty_price = float(price)
        self.size = int(size)
        self.side = side
        self.action = "T"
        self.sequence = int(sequence)
        self.instrument_id = int(instrument_id)


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
    def __init__(self, ts, price=100.0, *, flags=0, order_id=7, levels=None, action="A"):
        self.ts_event = int(ts * NS)
        self.price = int(price * NS)
        self.pretty_price = float(price)
        self.size = 1
        self.side = "B"
        self.action = action
        self.sequence = 3
        self.flags = int(flags)
        self.order_id = int(order_id)
        if levels is not None:
            self.levels = levels


class Mapping:
    def __init__(self, instrument_id, input_symbol="NQ.v.0", raw_symbol="NQZ6"):
        self.instrument_id = int(instrument_id)
        self.stype_in_symbol = input_symbol
        self.stype_out_symbol = raw_symbol
        self.start_ts = 0
        self.end_ts = 0


class Error:
    def __init__(self, err="symbol failed", code=4):
        self.err = err
        self.code = code
        self.is_last = True


class SystemMsg:
    def __init__(self, msg="heartbeat", code=0):
        self.msg = msg
        self.code = int(code)


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
        self.exception_callback = None
        self.reconnect_callback = None
        self.reconnect_exception_callback = None
        self.started = False
        self.stopped = False
        self._emitted = set()

    def subscribe(self, **kwargs):
        self.subscriptions.append(dict(kwargs))
        if self.started:
            self._emit(kwargs["schema"])

    def add_callback(self, callback, exception_callback=None):
        self.callback = callback
        self.exception_callback = exception_callback

    def _emit(self, schema):
        # Subscription upgrades after start should deliver only that new schema once.
        if schema in self._emitted or self.callback is None:
            return
        self._emitted.add(schema)
        for rec in self.records_by_schema.get(schema, []):
            self.callback(rec)

    def add_reconnect_callback(self, callback, exception_callback=None):
        self.reconnect_callback = callback
        self.reconnect_exception_callback = exception_callback

    def start(self):
        self.started = True
        for sub in self.subscriptions:
            self._emit(sub["schema"])

    def stop(self):
        self.stopped = True


class FakeSDK:
    Historical = object
    Live = object
    RecordFlags = SimpleNamespace(F_LAST=128, F_SNAPSHOT=32)


def make_feed(*, historical=None, lives=None):
    live_queue = list(lives or [FakeLive()])
    return Databento(
        api_key="db-test",
        sdk=FakeSDK,
        historical=historical or FakeHistorical({}),
        live_factory=lambda: live_queue.pop(0),
    )


def test_continuous_volume_front_symbology_and_capabilities(monkeypatch):
    monkeypatch.delenv("DATABENTO_ROLL_RULE", raising=False)
    assert Databento.continuous_symbol("NQ=F") == "NQ.v.0"
    assert Databento.continuous_symbol("CME_MINI:MNQ1!") == "MNQ.v.0"
    assert Databento.continuous_symbol("BTCF") == "BTC.v.0"
    assert Databento.parent_symbol("ES=F") == "ES.FUT"
    feed = make_feed()
    caps = feed.capabilities()
    assert caps["continuous_futures"] is True
    assert caps["continuous_rule"] == "volume_front"
    assert caps["continuous_rule_code"] == "v"
    assert caps["live_roll_verified"] is True
    assert caps["live_roll_verification"] == "daily_symbology_resolution_and_session_rotation"
    assert caps["minimum_ohlcv_resolution_seconds"] == 1
    assert caps["ticks"] is True
    assert caps["mbp_10"] is True and caps["mbo"] is True and caps["mbo_snapshot"] is True


def test_roll_rule_is_real_configuration_not_a_dead_setting(monkeypatch):
    monkeypatch.setenv("DATABENTO_ROLL_RULE", "n")
    feed = make_feed()
    assert feed.roll_rule == "n"
    assert feed.continuous_symbol("NQ=F", feed.roll_rule) == "NQ.n.0"
    assert feed.capabilities()["continuous_rule"] == "open_interest_front"
    with pytest.raises(ValueError, match="ROLL_RULE|roll rule"):
        Databento(api_key="db-test", sdk=FakeSDK, historical=FakeHistorical({}), live_factory=lambda: FakeLive(), roll_rule="bad")


def test_databento_rejects_spot_and_unknown_symbols():
    feed = make_feed()
    with pytest.raises(ValueError, match="registered futures"):
        feed.continuous_symbol("BTCUSD", feed.roll_rule)
    with pytest.raises(ValueError):
        feed.continuous_symbol("../NQ", feed.roll_rule)


def test_live_error_message_fails_closed_instead_of_silently_waiting():
    live = FakeLive({"ohlcv-1s": [Error("NQ.v.0 failed to resolve", code=4)]})
    feed = make_feed(lives=[live])
    with pytest.raises(RuntimeError, match="code=4"):
        feed.recent_ex("NQ=F", 60)
    meta = feed.meta("NQ=F")
    assert "failed to resolve" in meta["live_error"]


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


def test_every_exposed_intraday_chart_interval_is_losslessly_supported():
    intraday_seconds = [tf_minutes(tf) * 60 for tf in CHART_TIMEFRAME_OPTIONS if tf not in ("D", "W")]
    for seconds in intraday_seconds:
        base, schema = Databento._schema_for(seconds)
        assert seconds % base == 0
        assert schema in ("ohlcv-1s", "ohlcv-1m", "ohlcv-1h")
        assert seconds in Databento.GRANULARITIES


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
    mbo = Depth(1_061, 106.25, order_id=99, action="T")
    live = FakeLive({"ohlcv-1s": second_rows, "trades": [trade], "mbp-10": [depth], "mbo": [mbo]})
    feed = make_feed(lives=[live])

    bars, ft, px = feed.recent_ex("NQ=F", 60)
    assert len(bars) == 2  # 1000-1019 partial UTC minute + 1020-1059 full minute
    assert ft == 1_059 and px == 106.5
    assert [s["schema"] for s in live.subscriptions][:2] == ["ohlcv-1s", "trades"]
    assert all(s["symbols"] == "NQ.v.0" and s["stype_in"] == "continuous" for s in live.subscriptions)

    ticks = feed.trades("NQ=F")
    assert ticks and ticks[-1].price == 106.5 and ticks[-1].size == 3
    assert ticks[-1].ts_event == 1_059 and ticks[-1].ts_event_ns == 1_059 * NS

    depth_rows = feed.depth_events("NQ=F", schema="mbp-10")
    assert depth_rows and depth_rows[-1]["levels"][0]["bid_px"] == 106.0
    assert depth_rows[-1]["schema"] == "mbp-10"
    assert depth_rows[-1]["ts_event_ns"] == 1_060 * NS
    assert any(s["schema"] == "mbp-10" for s in live.subscriptions)

    mbo_rows = feed.depth_events("NQ=F", schema="mbo")
    assert mbo_rows and mbo_rows[-1]["order_id"] == 99
    assert mbo_rows[-1]["schema"] == "mbo"
    assert all(row["schema"] == "mbo" for row in mbo_rows)
    assert all(row["schema"] == "mbp-10" for row in depth_rows)
    # MBO action=T describes the same economic trade but must not duplicate the
    # dedicated Databento trades-schema tick stream.
    assert len(feed.trades("NQ=F")) == 1


def test_mbo_snapshot_requests_continuous_snapshot_and_stops():
    snapshot = Depth(2_000, 200.25, flags=160)
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



def test_replay_overlap_deduplicates_second_bars_and_trades():
    feed = make_feed()
    bar = Ohlcv(4_500, 100, 101, 99, 100.5, 7)
    trade = Trade(4_500, 100.5, 2, sequence=17, instrument_id=4242)
    feed._live_callback("NQ=F", bar)
    feed._live_callback("NQ=F", bar)
    feed._live_callback("NQ=F", trade)
    feed._live_callback("NQ=F", trade)
    assert len(feed._second_bars["NQ=F"]) == 1
    assert feed._second_bars["NQ=F"][0].v == 7
    ticks = feed.trades("NQ=F")
    assert len(ticks) == 1
    assert ticks[0].instrument_id == 4242
    assert ticks[0].ts_event_ns == 4_500 * NS


def test_depth_schema_queues_do_not_evict_each_other():
    mbp = Depth(5_000, 100.0, levels=[Level(99.75, 100.0)])
    mbo_flood = [Depth(5_001 + i, 100.0, order_id=10_000 + i) for i in range(1001)]
    live = FakeLive({"mbp-10": [mbp], "mbo": mbo_flood})
    feed = make_feed(lives=[live])

    mbp_rows = feed.depth_events("NQ=F", schema="mbp-10")
    assert len(mbp_rows) == 1
    feed.depth_events("NQ=F", schema="mbo")
    # A busy MBO stream cannot consume the independent MBP-10 retention budget.
    still_mbp = feed.depth_events("NQ=F", schema="mbp-10")
    assert len(still_mbp) == 1 and still_mbp[0]["schema"] == "mbp-10"


def test_mbo_snapshot_filters_system_and_realtime_records():
    live = FakeLive({"mbo": [
        SystemMsg("symbol mapping / heartbeat"),
        Depth(6_000, 100.0, flags=0, order_id=8),
        Depth(6_001, 100.25, flags=160, order_id=9),
    ]})
    feed = make_feed(lives=[live])
    rows = feed.mbo_snapshot("NQ=F", timeout=0.2)
    assert [row["order_id"] for row in rows] == [9]
    assert rows[0]["schema"] == "mbo"
    assert rows[0]["snapshot"] is True


def test_slow_reader_gap_forces_bounded_replay_recovery(monkeypatch):
    monkeypatch.setattr("icarus_engine.feeds.databento.time.time", lambda: 20_100)
    live1 = FakeLive({
        "ohlcv-1s": [Ohlcv(20_000, 100, 101, 99, 100.5)],
        "trades": [Error("records skipped", code=7)],
    })
    live2 = FakeLive({
        "ohlcv-1s": [Ohlcv(20_000, 200, 201, 199, 200.5)],
        "trades": [Trade(20_000, 200.5, sequence=2, instrument_id=202)],
    })
    feed = make_feed(lives=[live1, live2])
    feed.start_live("NQ=F")
    assert "NQ=F" in feed._recovery_required
    assert "records skipped" in feed.meta("NQ=F")["live_error"]

    feed.start_live("NQ=F")
    assert live1.stopped is True and live2.started is True
    assert "NQ=F" not in feed._recovery_required
    meta = feed.meta("NQ=F")
    assert meta["recovery_count"] == 1
    assert "records skipped" in meta["last_recovery_reason"]
    assert [b.c for b in feed._second_bars["NQ=F"]] == [200.5]


def test_gateway_fatal_error_stays_visible_after_later_market_record():
    feed = make_feed()
    feed._live_callback("NQ=F", Error("invalid subscription", code=5))
    feed._live_callback("NQ=F", Trade(7_100, 100.75, 1))
    with pytest.raises(RuntimeError, match="invalid subscription"):
        feed._raise_live_error("NQ=F")
    assert "invalid subscription" in feed.meta("NQ=F")["live_error"]


def test_symbol_resolution_error_clears_when_mapping_later_resolves():
    feed = make_feed()
    feed._live_callback("NQ=F", Error("not listed yet", code=4))
    with pytest.raises(RuntimeError, match="not listed yet"):
        feed._raise_live_error("NQ=F")
    feed._live_callback("NQ=F", Mapping(777, "NQ.v.0", "NQZ6"))
    feed._raise_live_error("NQ=F")
    assert "live_error" not in feed.meta("NQ=F")


def test_system_slow_reader_and_replay_status_are_persistent_metadata(monkeypatch):
    monkeypatch.setattr("icarus_engine.feeds.databento.time.time", lambda: 30_000)
    feed = make_feed()
    feed._live_callback("NQ=F", SystemMsg("falling behind", code=2))
    assert feed.meta("NQ=F")["slow_reader_warning"] == "falling behind"
    assert feed.meta("NQ=F")["slow_reader_warning_ts"] == 30_000
    feed._live_callback("NQ=F", SystemMsg("replay caught up", code=3))
    meta = feed.meta("NQ=F")
    assert meta["last_replay_completed_ts"] == 30_000
    assert "slow_reader_warning" not in meta


def test_async_live_exception_is_surfaced_to_engine():
    live = FakeLive({"ohlcv-1s": [Ohlcv(7_000, 100, 101, 99, 100.5)]})
    feed = make_feed(lives=[live])
    feed.recent_ex("NQ=F", 1)
    assert callable(live.exception_callback)
    live.exception_callback(RuntimeError("socket reader failed"))
    # A subsequent valid market event must not erase an adapter callback failure
    # before the synchronous poll path observes it, including feed metadata.
    feed._live_callback("NQ=F", Trade(7_001, 100.75, 1))
    assert "socket reader failed" in feed.meta("NQ=F")["live_error"]
    with pytest.raises(RuntimeError, match="socket reader failed"):
        feed.trades("NQ=F")


def test_failed_live_start_cleans_subscription_state():
    class BrokenLive(FakeLive):
        def start(self):
            self.started = True
            raise RuntimeError("cannot start")

    live = BrokenLive()
    feed = make_feed(lives=[live])
    with pytest.raises(RuntimeError, match="cannot start"):
        feed.start_live("NQ=F")
    assert live.stopped is True
    assert "NQ=F" not in feed._subscriptions
    assert "NQ=F" not in feed._live_started


def test_recent_ex_uses_historical_seed_when_new_live_session_is_idle(monkeypatch):
    monkeypatch.setattr("icarus_engine.feeds.databento.time.time", lambda: 10_020)
    hist = FakeHistorical({"ohlcv-1m": [Ohlcv(9_960, 100, 101, 99, 100.5, 5)]})
    feed = make_feed(historical=hist, lives=[FakeLive()])
    # Avoid spending the normal live-ready timeout in this deterministic idle test.
    feed._ready["NQ=F"].set()
    bars, ft, px = feed.recent_ex("NQ=F", 60, since_ts=9_900)
    assert len(bars) == 1 and bars[0].ts == 9_960
    assert ft == 10_020 and px == 100.5
    assert hist.calls[-1]["schema"] == "ohlcv-1m"
    assert feed.meta("NQ=F")["historical_seed"] is True

    # Once the historical seed establishes the feed clock, another idle poll does
    # not hit the paid Historical API again.
    calls = len(hist.calls)
    feed.recent_ex("NQ=F", 60, since_ts=9_960)
    assert len(hist.calls) == calls


def test_historical_seed_failure_surfaces_root_cause(monkeypatch):
    class FailingHistorical(FakeHistorical):
        def get_range(self, **kwargs):
            self.calls.append(dict(kwargs))
            raise PermissionError("historical entitlement denied")

    monkeypatch.setattr("icarus_engine.feeds.databento.time.time", lambda: 10_020)
    feed = make_feed(historical=FailingHistorical({}), lives=[FakeLive()])
    feed._ready["NQ=F"].set()
    with pytest.raises(RuntimeError, match="historical seed failed.*entitlement denied"):
        feed.recent_ex("NQ=F", 60, since_ts=9_900)


def test_mbo_snapshot_requires_last_flag_contract():
    class SDK(FakeSDK):
        RecordFlags = SimpleNamespace(F_SNAPSHOT=32)

    live = FakeLive({"mbo": [Depth(8_000, flags=32)]})
    feed = Databento(
        api_key="db-test",
        sdk=SDK,
        historical=FakeHistorical({}),
        live_factory=lambda: live,
    )
    with pytest.raises(RuntimeError, match="F_LAST"):
        feed.mbo_snapshot("NQ=F", timeout=0.1)
    assert live.started is False


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
    assert hasattr(db, "RecordFlags") and hasattr(db.RecordFlags, "F_LAST") and hasattr(db.RecordFlags, "F_SNAPSHOT")
    assert int(db.RecordFlags.F_LAST) == 128
    assert int(db.RecordFlags.F_SNAPSHOT) == 32
    assert callable(getattr(db.Live, "subscribe", None))
    assert callable(getattr(db.Live, "add_callback", None))
    assert callable(getattr(db.Live, "add_reconnect_callback", None))
    assert callable(getattr(db.Live, "start", None))
    assert callable(getattr(db.Live, "stop", None))
    params = inspect.signature(db.Live.subscribe).parameters
    for name in ("dataset", "schema", "symbols", "stype_in", "start", "snapshot"):
        assert name in params
    cb_params = inspect.signature(db.Live.add_callback).parameters
    assert "record_callback" in cb_params and "exception_callback" in cb_params
    reconnect_params = inspect.signature(db.Live.add_reconnect_callback).parameters
    assert "reconnect_callback" in reconnect_params and "exception_callback" in reconnect_params


def test_real_live_factory_requests_heartbeats_reconnect_and_no_skip():
    captured = {}

    class SDK(FakeSDK):
        @staticmethod
        def Live(**kwargs):
            captured.update(kwargs)
            return FakeLive({"ohlcv-1s": [Ohlcv(1000, 100, 101, 99, 100.5)]})

    feed = Databento(api_key="db-test", sdk=SDK, historical=FakeHistorical({}))
    feed.recent_ex("NQ=F", 1)
    assert captured["heartbeat_interval_s"] == 10
    assert captured["reconnect_policy"] == "reconnect"
    assert captured["slow_reader_behavior"] == "warn"


def test_reconnect_gap_is_published_in_feed_metadata():
    live = FakeLive({"ohlcv-1s": [Ohlcv(1000, 100, 101, 99, 100.5)]})
    feed = make_feed(lives=[live])
    feed.recent_ex("NQ=F", 1)
    assert callable(live.reconnect_callback)
    assert callable(live.reconnect_exception_callback)
    live.reconnect_callback("2026-09-30T10:00:00Z", "2026-09-30T10:00:02Z")
    meta = feed.meta("NQ=F")
    assert meta["reconnect_count"] == 1
    assert meta["last_reconnect_gap"]["previous"].endswith("10:00:00Z")
    assert meta["last_reconnect_gap"]["resumed"].endswith("10:00:02Z")
    # Later market data must not erase reconnect diagnostics.
    feed._live_callback("NQ=F", Trade(1_001, 100.75, 1))
    meta = feed.meta("NQ=F")
    assert meta["reconnect_count"] == 1
    assert meta["last_reconnect_gap"]["previous"].endswith("10:00:00Z")


def test_live_continuous_mapping_is_recorded_without_faking_market_readiness():
    feed = make_feed()
    feed._live_callback("NQ=F", Mapping(4242, "NQ.v.0", "NQZ6"))
    meta = feed.meta("NQ=F")
    assert meta["continuous_symbol"] == "NQ.v.0"
    assert meta["active_contract"] == "NQZ6"
    assert meta["active_instrument_id"] == 4242
    assert feed._ready["NQ=F"].is_set() is False


def test_live_session_rotates_when_daily_continuous_mapping_changes(monkeypatch):
    class Resolver:
        def __init__(self):
            self.instrument = 101
            self.calls = []

        def resolve(self, **kwargs):
            self.calls.append(dict(kwargs))
            sym = kwargs["symbols"]
            return {"status": 0, "message": "OK", "result": {sym: [{"d0": kwargs["start_date"], "d1": "2099-01-01", "s": str(self.instrument)}]}}

    resolver = Resolver()
    hist = FakeHistorical({})
    hist.symbology = resolver
    monkeypatch.setattr("icarus_engine.feeds.databento.time.time", lambda: 10_100)
    # The stale session has already emitted ts=10000 from physical instrument 101.
    # The replacement session replays that same timestamp from instrument 202;
    # the old row/tick must be removed, not kept by timestamp dedupe.
    live1 = FakeLive({
        "ohlcv-1s": [Mapping(101), Ohlcv(10_000, 100, 101, 99, 100.5)],
        "trades": [Trade(10_000, 100.5, sequence=1, instrument_id=101)],
    })
    live2 = FakeLive({
        "ohlcv-1s": [Mapping(202, raw_symbol="NQH7"), Ohlcv(10_000, 200, 201, 199, 200.5)],
        "trades": [Trade(10_000, 200.5, sequence=1, instrument_id=202)],
    })
    feed = make_feed(historical=hist, lives=[live1, live2])

    feed.start_live("NQ=F")
    assert live1.started is True
    assert feed._resolved_instrument["NQ=F"] == 101
    assert resolver.calls[-1]["stype_in"] == "continuous"
    assert resolver.calls[-1]["stype_out"] == "instrument_id"

    # Simulate the next UTC mapping day and a changed .v.0 instrument.
    resolver.instrument = 202
    feed._resolution_day["NQ=F"] = "1900-01-01"
    feed.start_live("NQ=F")
    assert live1.stopped is True
    assert live2.started is True
    # Controlled-roll replay overlaps only stateless bars/trades. If depth had
    # been active it would restart live-now and be rebuilt/snapshotted separately.
    for sub in live2.subscriptions:
        if sub["schema"] in ("ohlcv-1s", "trades"):
            assert "start" in sub
        else:
            assert "start" not in sub
    assert feed._resolved_instrument["NQ=F"] == 202
    meta = feed.meta("NQ=F")
    assert meta["roll_count"] == 1
    assert meta["previous_instrument_id"] == 101
    assert meta["resolved_instrument_id"] == 202
    assert meta["active_contract"] == "NQH7"
    assert [b.c for b in feed._second_bars["NQ=F"]] == [200.5]
    ticks = feed.trades("NQ=F")
    assert len(ticks) == 1 and ticks[0].instrument_id == 202 and ticks[0].price == 200.5
    assert not feed.depth_events("NQ=F", schema="mbo", limit=1)


def test_continuous_resolution_failure_is_fail_closed():
    class Resolver:
        def resolve(self, **kwargs):
            return {"status": 2, "message": "Not found", "result": {}}

    hist = FakeHistorical({})
    hist.symbology = Resolver()
    feed = make_feed(historical=hist, lives=[FakeLive()])
    with pytest.raises(RuntimeError, match="did not resolve"):
        feed.start_live("NQ=F")


def test_remove_asset_releases_its_databento_live_session(monkeypatch, tmp_path):
    class Feed:
        def __init__(self):
            self.stopped = []
        def stop_live(self, symbol=None):
            self.stopped.append(symbol)

    feed = Feed()
    monkeypatch.setenv("ICARUS_FEED", "databento")
    monkeypatch.setattr("icarus_engine.runtime.Databento", lambda: feed)
    port = Portfolio(Journal(":memory:"), str(tmp_path))
    runner = SimpleNamespace(spec=resolve("NQ"), feed=feed, paused=False, _removed=False)
    port.runners["NQ"] = runner
    port.order = ["NQ"]
    assert port.remove_asset("NQ") is True
    assert feed.stopped == ["NQ=F"]
    assert runner.paused is True and runner._removed is True
    port.journal.con.close()


def test_portfolio_stop_closes_databento_live_sessions(monkeypatch, tmp_path):
    class Feed:
        def __init__(self):
            self.stops = 0
        def stop_live(self):
            self.stops += 1

    feed = Feed()
    monkeypatch.setenv("ICARUS_FEED", "databento")
    monkeypatch.setattr("icarus_engine.runtime.Databento", lambda: feed)
    port = Portfolio(Journal(":memory:"), str(tmp_path))
    port.stop()
    assert feed.stops == 1


def test_system_message_before_first_market_event_does_not_crash_or_fake_readiness():
    feed = make_feed()
    feed._live_callback("NQ=F", SystemMsg())
    assert feed.meta("NQ=F")["regularMarketTime"] == 0
    assert feed._ready["NQ=F"].is_set() is False


def test_valid_market_event_clears_transient_live_error():
    feed = make_feed()
    feed._live_callback("NQ=F", Error("temporarily unresolved", code=4))
    with pytest.raises(RuntimeError, match="temporarily unresolved"):
        feed._raise_live_error("NQ=F")
    feed._live_callback("NQ=F", Trade(3_000, 123.25, 2))
    feed._raise_live_error("NQ=F")
    meta = feed.meta("NQ=F")
    assert "live_error" not in meta
    assert meta["regularMarketTime"] == 3_000


def test_mbo_snapshot_surfaces_live_error_instead_of_timing_out():
    live = FakeLive({"mbo": [Error("snapshot permission denied", code=7)]})
    feed = make_feed(lives=[live])
    with pytest.raises(RuntimeError, match="code=7.*snapshot permission denied"):
        feed.mbo_snapshot("NQ=F", timeout=0.2)
    assert live.stopped is True


def test_doctor_roll_rule_contract_matches_adapter(monkeypatch, tmp_path):
    from datetime import date
    from icarus_engine.doctor import inspect
    monkeypatch.setenv("ICARUS_FEED", "databento")
    monkeypatch.setenv("DATABENTO_API_KEY", "db-test")
    monkeypatch.setenv("DATABENTO_ROLL_RULE", "n")
    rep = inspect(str(tmp_path), today=date(2026, 9, 20))
    item = {i["name"]: i for i in rep["items"]}["Databento adapter prerequisites"]
    assert item["ok"] is True
    assert "continuous=open-interest .n.0" in item["detail"]


def test_engine_http_exposes_databento_capabilities_ticks_depth_and_mbo(tmp_path):
    live = FakeLive({
        "ohlcv-1s": [Ohlcv(4_000, 100, 101, 99, 100.5, 1)],
        "trades": [Trade(4_000, 100.5, 2)],
        "mbp-10": [Depth(4_001, 100.5, levels=[Level(100.25, 100.5)])],
    })
    snapshot_live = FakeLive({"mbo": [Depth(4_002, 100.5, flags=160)]})
    feed = make_feed(lives=[live, snapshot_live])

    journal = Journal(":memory:")
    port = Portfolio(journal, str(tmp_path))
    spec = resolve("NQ")
    spec.chart_tf = "1"
    runner = AssetRunner(
        RunnerConfig(spec, Inputs(use_tide=False, use_eod_flat=False), base_dir=str(tmp_path)),
        journal,
        {"yahoo": feed},
    )
    runner.warm = True
    feed._live_callback("NQ=F", Mapping(4242, "NQ.v.0", "NQZ6"))
    summary = runner.summary()
    assert summary["active_contract"] == "NQZ6"
    assert summary["active_instrument_id"] == 4242
    assert summary["feed_meta"]["continuous_symbol"] == "NQ.v.0"
    chart_caps = runner.chart_capability_view()
    assert chart_caps["seconds"] is False and chart_caps["ticks"] is False
    assert chart_caps["raw_feed_provider"] == "databento"
    assert chart_caps["raw_seconds"] is True and chart_caps["raw_ticks"] is True and chart_caps["raw_depth"] is True
    assert chart_caps["raw_minimum_resolution_seconds"] == 1
    port.runners["NQ"] = runner
    port.order = ["NQ"]

    srv = serve(port, 0, token="test-token", start=False)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{srv.server_port}"
    try:
        with urllib.request.urlopen(base + "/api/market-data/NQ1!/capabilities", timeout=5) as reply:
            body = json.load(reply)
            assert reply.status == 200
            assert body["provider"] == "databento"
            assert body["capabilities"]["ticks"] is True
            assert body["capabilities"]["mbp_10"] is True

        with urllib.request.urlopen(base + "/api/market-data/NQ1!/ticks?limit=10", timeout=5) as reply:
            body = json.load(reply)
            assert body["ticks"][-1]["price"] == 100.5
            assert body["ticks"][-1]["size"] == 2

        with urllib.request.urlopen(base + "/api/market-data/NQ1!/depth?schema=mbp-10&limit=10", timeout=5) as reply:
            body = json.load(reply)
            assert body["schema"] == "mbp-10"
            assert body["events"][-1]["levels"][0]["bid_px"] == 100.25

        req = urllib.request.Request(
            base + "/admin/market-data/mbo-snapshot",
            data=json.dumps({"asset": "NQ1!", "timeout": 0.2}).encode(),
            headers={"Authorization": "Bearer test-token", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as reply:
            body = json.load(reply)
            assert reply.status == 200
            assert body["schema"] == "mbo"
            assert body["snapshot"][-1]["order_id"] == 7
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join(5)
        journal.con.close()
