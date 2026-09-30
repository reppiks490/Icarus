"""Databento adapter contract tests. No credentials or network access required."""
from __future__ import annotations

import importlib.util
import inspect
import json
import threading
import urllib.error
import urllib.request
from types import SimpleNamespace

import pytest

from icarus_engine.assets import REGISTRY, resolve
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


class Error:
    def __init__(self, err="symbol failed", code=4):
        self.err = err
        self.code = code
        self.is_last = True


class SystemMsg:
    def __init__(self, msg="heartbeat"):
        self.msg = msg


class Mapping:
    def __init__(self, symbol, instrument_id):
        self.stype_in_symbol = symbol
        self.instrument_id = int(instrument_id)


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
        self.reconnect_callback = None
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

    def add_reconnect_callback(self, callback):
        self.reconnect_callback = callback

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
    assert caps["live_session_model"] == "shared_per_dataset"
    assert caps["live_symbol_routing"] == "SymbolMappingMsg/instrument_id"
    assert caps["minimum_ohlcv_resolution_seconds"] == 1
    assert caps["ticks"] is True
    assert caps["mbp_10"] is True and caps["mbo"] is True and caps["mbo_snapshot"] is True


def test_every_registered_future_maps_to_databento_continuous_front():
    futures = [spec for spec in REGISTRY.values() if spec.kind == "futures"]
    assert futures
    for spec in futures:
        root = spec.ticker[:-2]
        assert spec.ticker == f"{root}=F"
        assert spec.tv_symbol.endswith("1!")
        assert Databento.continuous_symbol(spec.symbol, "v") == f"{root}.v.0"
        assert Databento.continuous_symbol(spec.ticker, "n") == f"{root}.n.0"
        assert Databento.continuous_symbol(spec.tv_symbol, "c") == f"{root}.c.0"


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


def test_undefined_databento_price_is_never_promoted_to_a_fake_market_price():
    undef = (1 << 63) - 1
    row = Depth(1_500, 100.0, order_id=11)
    row.price = undef
    row.pretty_price = float("nan")
    event = Databento._event_record(row)
    assert event["price"] is None

    bad_trade = Trade(1_500, 100.0, 1)
    bad_trade.price = undef
    bad_trade.pretty_price = float("nan")
    with pytest.raises(ValueError, match="undefined/invalid"):
        Databento._trade_record(bad_trade)


def test_undefined_mbp_level_prices_are_serialized_as_null_not_billions():
    undef = (1 << 63) - 1
    lvl = Level(100.0, 100.25)
    lvl.bid_px = undef
    lvl.pretty_bid_px = float("nan")
    depth = Depth(1_501, 100.25, levels=[lvl])
    event = Databento._event_record(depth)
    assert event["levels"][0]["bid_px"] is None
    assert event["levels"][0]["ask_px"] == 100.25


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


@pytest.mark.parametrize("minutes", [1, 2, 5, 10, 20, 30])
def test_requested_primary_minute_timeframes_are_losslessly_resampled(minutes):
    rows = [Ohlcv(3_600 + 60 * k, 100 + k, 101 + k, 99 + k, 100.5 + k, 1) for k in range(60)]
    hist = FakeHistorical({"ohlcv-1m": rows})
    feed = make_feed(historical=hist)
    granularity = minutes * 60
    bars = feed.candles("NQ=F", granularity, 3_600, 7_200)
    assert len(bars) == 60 // minutes
    assert all(b.ts % granularity == 0 for b in bars)
    assert sum(b.v for b in bars) == 60
    assert hist.calls[-1]["schema"] == "ohlcv-1m"
    assert hist.calls[-1]["symbols"] == "NQ.v.0"


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
    mbo = Depth(1_061, 106.25, order_id=99)
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


def test_trade_tape_deduplicates_same_event_seen_in_trades_and_mbo():
    trade = Trade(1_059, 106.5, 3, side="B", sequence=1)
    mbo_trade = Depth(1_059, 106.5, order_id=99)
    mbo_trade.action = "T"
    mbo_trade.side = "B"
    mbo_trade.size = 3
    mbo_trade.sequence = 1
    live = FakeLive({"ohlcv-1s": [Ohlcv(1_059, 106, 107, 105, 106.5, 1)],
                     "trades": [trade], "mbo": [mbo_trade]})
    feed = make_feed(lives=[live])

    feed.recent_ex("NQ=F", 1)
    assert len(feed.trades("NQ=F")) == 1
    feed.depth_events("NQ=F", schema="mbo")
    ticks = feed.trades("NQ=F")
    assert len(ticks) == 1
    assert ticks[0].ts_event_ns == 1_059 * NS
    assert ticks[0].price == 106.5 and ticks[0].size == 3


def test_mbo_snapshot_omits_non_mbo_stream_records():
    snapshot = Depth(2_000, 200.25, flags=1)
    live = FakeLive({"mbo": [SystemMsg("subscription ack"), SimpleNamespace(stype_in_symbol="ES.v.0", instrument_id=7), snapshot]})
    feed = make_feed(lives=[live])
    rows = feed.mbo_snapshot("ES=F", timeout=0.2)
    assert len(rows) == 1
    assert rows[0]["schema"] == "mbo"
    assert rows[0]["order_id"] == 7


def test_all_registered_futures_share_one_live_session():
    live = FakeLive()
    feed = make_feed(lives=[live])
    futures = [spec for spec in REGISTRY.values() if spec.kind == "futures"]
    assert len(futures) > 10  # guards the Databento Standard 10-session failure mode
    client = feed.prepare_live([spec.ticker for spec in futures], start_ts=1_000)
    assert client is live
    assert live.started is True
    assert len(live.subscriptions) == len(futures) * 2
    assert {sub["symbols"] for sub in live.subscriptions} == {f"{spec.ticker[:-2]}.v.0" for spec in futures}
    # Batch preparation attaches replay before the one shared session starts.
    assert all("start" in sub for sub in live.subscriptions)

    before = len(live.subscriptions)
    feed.start_live(futures[0].ticker, include_depth="mbp-10", start_ts=2_000)
    assert len(live.subscriptions) == before + 1
    assert live.subscriptions[-1]["schema"] == "mbp-10"
    assert "start" not in live.subscriptions[-1]

    feed.stop_live(futures[0].ticker)
    assert live.stopped is False
    feed.stop_live()
    assert live.stopped is True


def test_shared_session_detach_readd_does_not_duplicate_or_misroute():
    live = FakeLive()
    feed = make_feed(lives=[live])
    feed.start_live("NQ=F")
    feed.start_live("ES=F")
    live.callback(Mapping("NQ.v.0", 101))
    live.callback(Mapping("ES.v.0", 202))
    subscriptions_before = len(live.subscriptions)

    feed.stop_live("NQ=F")
    stray = Ohlcv(6_000, 111, 112, 110, 111.5, 1)
    stray.instrument_id = 101
    live.callback(stray)
    assert not feed._second_bars["NQ=F"]
    assert not feed._second_bars["ES=F"]

    feed.start_live("NQ=F")
    assert len(live.subscriptions) == subscriptions_before
    live.callback(stray)
    assert feed._second_bars["NQ=F"][-1].c == 111.5
    assert not feed._second_bars["ES=F"]


def test_shared_live_session_routes_records_by_symbol_mapping():
    live = FakeLive()
    feed = make_feed(lives=[live])
    feed.start_live("NQ=F")
    feed.start_live("ES=F")

    live.callback(Mapping("NQ.v.0", 101))
    live.callback(Mapping(b"ES.v.0\0ignored", 202))
    nq = Ohlcv(5_000, 100, 101, 99, 100.5, 1)
    es = Ohlcv(5_001, 200, 201, 199, 200.5, 2)
    nq.instrument_id = 101
    es.instrument_id = 202
    live.callback(nq)
    live.callback(es)

    nq_rows, _, nq_px = feed.recent_ex("NQ=F", 1)
    es_rows, _, es_px = feed.recent_ex("ES=F", 1)
    assert nq_rows[-1].c == 100.5 and nq_px == 100.5
    assert es_rows[-1].c == 200.5 and es_px == 200.5
    assert all(row.c != 200.5 for row in nq_rows)
    assert all(row.c != 100.5 for row in es_rows)


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
    live.reconnect_callback("2026-09-30T10:00:00Z", "2026-09-30T10:00:02Z")
    meta = feed.meta("NQ=F")
    assert meta["reconnect_count"] == 1
    assert meta["last_reconnect_gap"]["previous"].endswith("10:00:00Z")
    assert meta["last_reconnect_gap"]["resumed"].endswith("10:00:02Z")


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


def test_live_record_conversion_error_is_contained_as_feed_health():
    feed = make_feed()
    bad = Ohlcv(3_000, 100, 101, 99, 100.5, 1)
    bad.close = (1 << 63) - 1
    bad.pretty_close = float("nan")
    feed._dispatch_live("NQ=F", bad)
    with pytest.raises(RuntimeError, match="Databento record error.*undefined/invalid"):
        feed._raise_live_error("NQ=F")
    assert "live_error" in feed.meta("NQ=F")


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
    snapshot_live = FakeLive({"mbo": [Depth(4_002, 100.5, flags=1)]})
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

        with pytest.raises(urllib.error.HTTPError) as bad_schema:
            urllib.request.urlopen(base + "/api/market-data/NQ1!/depth?schema=garbage", timeout=5)
        assert bad_schema.value.code == 400
        assert "schema must be mbp-10 or mbo" in bad_schema.value.read().decode()

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
