"""Databento adapter contract tests. No credentials or network access required."""
from __future__ import annotations

import importlib.util
import inspect
import json
import threading
import urllib.error
import urllib.request
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from icarus_engine.assets import CHART_TIMEFRAME_OPTIONS, REGISTRY, resolve
from icarus_engine.feeds.databento import Databento
from icarus_engine.pine.timeframe import tf_minutes
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
    def __init__(self, ts, price, size=1, side="B", sequence=1, ts_recv=None):
        self.ts_event = int(ts * NS)
        self.ts_recv = int((ts if ts_recv is None else ts_recv) * NS)
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
    def __init__(self, ts, price=100.0, *, flags=0, order_id=7, levels=None, ts_recv=None):
        self.ts_event = int(ts * NS)
        self.ts_recv = int((ts if ts_recv is None else ts_recv) * NS)
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
    assert caps["live_session_model"] == "shared_core_plus_schema_isolated_depth_per_dataset"
    assert caps["persistent_live_sessions_max"] == 3
    assert caps["snapshot_sessions_serialized"] is True
    assert caps["live_symbol_routing"] == "SymbolMappingMsg/instrument_id"
    assert caps["depth_failure_isolation"] is True
    assert caps["depth_schema_isolation"] is True
    assert caps["continuous_live_refresh"] == "automatic_utc_day"
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


def test_fatal_core_error_cannot_be_cleared_by_buffered_market_data_before_reconnect():
    live = FakeLive({
        "ohlcv-1s": [
            Error("invalid core subscription", code=5),
            Ohlcv(1_001, 100, 101, 99, 100.5, 1),
        ]
    })
    feed = make_feed(lives=[live])

    with pytest.raises(RuntimeError, match="code=5.*invalid core subscription"):
        feed.recent_ex("NQ=F", 1)
    assert feed._second_bars["NQ=F"]  # buffered data arrived after the fatal error
    meta = feed.meta("NQ=F")
    assert meta["core_session_ok"] is False
    assert "invalid core subscription" in meta["live_error"]

    # A real SDK reconnect establishes a new integrity boundary. Only a subsequent
    # valid market event may clear the prior fatal error.
    live.reconnect_callback("before", "after")
    live.callback(Trade(1_002, 101.0, 1, sequence=2))
    feed._raise_live_error("NQ=F")
    meta = feed.meta("NQ=F")
    assert meta["core_session_ok"] is True
    assert "live_error" not in meta


def test_fatal_core_session_error_marks_every_active_symbol_failed_closed():
    feed = make_feed()
    feed._live_started.update({"NQ=F", "ES=F"})
    feed._continuous_to_symbol.update({"NQ.v.0": "NQ=F", "ES.v.0": "ES=F"})

    feed._dispatch_shared_live(Error("NQ.v.0 invalid subscription", code=5))

    with pytest.raises(RuntimeError, match="code=5"):
        feed._raise_live_error("NQ=F")
    with pytest.raises(RuntimeError, match="code=5"):
        feed._raise_live_error("ES=F")
    assert feed.meta("NQ=F")["core_session_ok"] is False
    assert feed.meta("ES=F")["core_session_ok"] is False


def test_symbol_resolution_error_remains_scoped_on_shared_core_session():
    feed = make_feed()
    feed._live_started.update({"NQ=F", "ES=F"})
    feed._continuous_to_symbol.update({"NQ.v.0": "NQ=F", "ES.v.0": "ES=F"})

    feed._dispatch_shared_live(Error("NQ.v.0 failed to resolve", code=4))

    with pytest.raises(RuntimeError, match="code=4"):
        feed._raise_live_error("NQ=F")
    feed._raise_live_error("ES=F")
    assert feed.meta("ES=F")["core_session_ok"] is True


def test_fatal_depth_session_error_marks_every_symbol_on_that_schema_failed_closed():
    feed = make_feed()
    feed._depth_live_symbols["mbp-10"].update({"NQ=F", "ES=F"})
    feed._depth_continuous_to_symbol["mbp-10"].update({"NQ.v.0": "NQ=F", "ES.v.0": "ES=F"})
    feed._depth_wanted["NQ=F"].add("mbp-10")
    feed._depth_wanted["ES=F"].add("mbp-10")

    feed._dispatch_depth_live("mbp-10", Error("NQ.v.0 invalid depth subscription", code=5))

    with pytest.raises(RuntimeError, match="code=5"):
        feed._raise_depth_error("NQ=F", "mbp-10")
    with pytest.raises(RuntimeError, match="code=5"):
        feed._raise_depth_error("ES=F", "mbp-10")
    assert feed.meta("NQ=F")["depth_session_ok"] is False
    assert feed.meta("NQ=F")["depth_schema_health"]["mbp-10"] is False
    assert feed.meta("NQ=F")["depth_schema_health"]["mbo"] is True


def test_depth_symbol_resolution_failure_rearms_only_failed_schema_symbol():
    mbp = FakeLive()
    mbo = FakeLive()
    feed = make_feed(lives=[mbp, mbo])
    feed._prepare_depth_live(["NQ=F", "ES=F"], "mbp-10")
    feed._prepare_depth_live(["NQ=F"], "mbo")

    feed._dispatch_depth_live("mbp-10", Error("NQ.v.0 failed to resolve", code=4))

    assert "NQ=F" not in feed._depth_subscriptions["mbp-10"]
    assert "ES=F" in feed._depth_subscriptions["mbp-10"]
    assert "NQ=F" in feed._depth_subscriptions["mbo"]
    feed._prepare_depth_live(["NQ=F"], "mbp-10")
    assert "NQ=F" in feed._depth_subscriptions["mbp-10"]
    assert [row["symbols"] for row in mbp.subscriptions].count("NQ.v.0") == 2


def test_symbol_resolution_failure_rearms_only_failed_core_symbol():
    live = FakeLive()
    feed = make_feed(lives=[live])
    feed.prepare_live(["NQ=F", "ES=F"])
    before = list(live.subscriptions)

    feed._dispatch_shared_live(Error("NQ.v.0 failed to resolve", code=4))
    assert feed._subscriptions["NQ=F"] == set()
    assert feed._subscriptions["ES=F"] == {"ohlcv-1s", "trades"}

    feed.start_live("NQ=F")
    added = live.subscriptions[len(before):]
    assert {row["schema"] for row in added} == {"ohlcv-1s", "trades"}
    assert all(row["symbols"] == "NQ.v.0" for row in added)
    assert not live.stopped


def test_recoverable_core_fatal_error_rebuilds_shared_session_with_replay():
    first = FakeLive()
    second = FakeLive()
    feed = make_feed(lives=[first, second])
    feed.prepare_live(["NQ=F", "ES=F"])
    feed._dispatch_shared_live(Error("internal gateway failure", code=6))
    assert feed._core_broken is True
    assert feed._core_error_code == 6

    client = feed.start_live("NQ=F")
    assert client is second
    assert first.stopped is True
    assert second.started is True
    assert feed._core_broken is False
    assert feed._core_error_code is None
    assert {row["symbols"] for row in second.subscriptions} == {"NQ.v.0", "ES.v.0"}
    assert all("start" in row for row in second.subscriptions)


def test_connection_limit_error_never_auto_reopens_a_new_session():
    first = FakeLive()
    unused = FakeLive()
    feed = make_feed(lives=[first, unused])
    feed.prepare_live(["NQ=F", "ES=F"])
    feed._dispatch_shared_live(Error("connection limit exceeded", code=3))

    client = feed.start_live("NQ=F")
    assert client is first
    assert first.stopped is False
    assert unused.started is False
    assert feed._core_error_code == 3
    with pytest.raises(RuntimeError, match="code=3"):
        feed._raise_live_error("ES=F")


def test_nonrecoverable_core_fatal_error_stays_latched_without_reconnect_churn():
    first = FakeLive()
    unused = FakeLive()
    feed = make_feed(lives=[first, unused])
    feed.prepare_live(["NQ=F", "ES=F"])
    feed._dispatch_shared_live(Error("invalid subscription", code=5))

    client = feed.start_live("NQ=F")
    assert client is first
    assert first.stopped is False
    assert unused.started is False
    assert feed._core_error_code == 5
    with pytest.raises(RuntimeError, match="code=5"):
        feed._raise_live_error("ES=F")


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
    base = 1_700_000_000
    hist = FakeHistorical({
        "ohlcv-1s": [
            Ohlcv(base, 10, 11, 9, 10.5, 1),
            Ohlcv(base + 1, 10.5, 12, 10, 11, 2),
            Ohlcv(base + 4, 11, 13, 10.5, 12, 3),
            Ohlcv(base + 5, 12, 12.5, 11.5, 12.25, 4),
        ]
    })
    feed = make_feed(historical=hist)
    bars = feed.candles("NQ=F", 5, base, base + 10)
    assert len(bars) == 2
    assert (bars[0].ts, bars[0].o, bars[0].h, bars[0].l, bars[0].c, bars[0].v) == (base, 10, 13, 9, 12, 6)
    assert (bars[1].ts, bars[1].o, bars[1].c, bars[1].v) == (base + 5, 12, 12.25, 4)
    call = hist.calls[-1]
    assert call["dataset"] == "GLBX.MDP3"
    assert call["schema"] == "ohlcv-1s"
    assert call["symbols"] == "NQ.v.0"
    assert call["stype_in"] == "continuous"


def test_every_advertised_chart_timeframe_has_a_lossless_databento_source_path():
    for tf in CHART_TIMEFRAME_OPTIONS:
        seconds = tf_minutes(tf) * 60
        if seconds in (86400, 7 * 86400):
            assert Databento(api_key="db-test", sdk=FakeSDK, historical=FakeHistorical({}),
                             live_factory=lambda: FakeLive()).capabilities()["cme_session_daily_weekly"] is True
        else:
            base_seconds, schema = Databento._schema_for(seconds)
            assert seconds % base_seconds == 0
            assert schema in {"ohlcv-1m", "ohlcv-1h"}


@pytest.mark.parametrize("minutes", [1, 2, 5, 10, 20, 30])
def test_requested_primary_minute_timeframes_are_losslessly_resampled(minutes):
    base = 1_700_000_000 - (1_700_000_000 % 3_600)
    rows = [Ohlcv(base + 60 * k, 100 + k, 101 + k, 99 + k, 100.5 + k, 1) for k in range(60)]
    hist = FakeHistorical({"ohlcv-1m": rows})
    feed = make_feed(historical=hist)
    granularity = minutes * 60
    bars = feed.candles("NQ=F", granularity, base, base + 3_600)
    assert len(bars) == 60 // minutes
    assert all(b.ts % granularity == 0 for b in bars)
    assert sum(b.v for b in bars) == 60
    assert hist.calls[-1]["schema"] == "ohlcv-1m"
    assert hist.calls[-1]["symbols"] == "NQ.v.0"


def test_databento_daily_candles_follow_cme_session_not_utc_date():
    def ts(value):
        return int(datetime.fromisoformat(value).replace(tzinfo=timezone.utc).timestamp())

    # September 2026 is EDT: the CME session starts 18:00 ET = 22:00 UTC.
    first_open = ts("2026-09-29T22:00:00")
    next_open = ts("2026-09-30T22:00:00")
    hist = FakeHistorical({"ohlcv-1h": [
        Ohlcv(first_open, 100, 101, 99, 100.5, 1),
        Ohlcv(ts("2026-09-30T00:00:00"), 100.5, 102, 100, 101.5, 2),
        Ohlcv(ts("2026-09-30T20:00:00"), 101.5, 103, 101, 102.5, 3),
        Ohlcv(next_open, 110, 111, 109, 110.5, 4),
    ]})
    feed = make_feed(historical=hist)

    bars = feed.candles("NQ=F", 86400, first_open, next_open + 3600)
    assert len(bars) == 2
    assert bars[0].ts == first_open
    assert (bars[0].o, bars[0].h, bars[0].l, bars[0].c, bars[0].v) == (100, 103, 99, 102.5, 6)
    assert bars[1].ts == next_open and bars[1].o == 110 and bars[1].v == 4
    assert hist.calls[-1]["schema"] == "ohlcv-1h"


def test_databento_historical_requests_clamp_to_glbx_coverage_start():
    hist = FakeHistorical({"ohlcv-1m": []})
    feed = make_feed(historical=hist)
    feed.candles("NQ=F", 60, 0, Databento.HISTORICAL_START_TS + 60)
    assert hist.calls[-1]["start"].startswith("2010-06-06T00:00:00")


def test_historical_minute_request_uses_native_ohlcv_1m():
    base = 1_700_000_040
    hist = FakeHistorical({"ohlcv-1m": [Ohlcv(base, 20, 21, 19, 20.5, 10)]})
    feed = make_feed(historical=hist)
    bars = feed.candles("ES=F", 60, base, base + 60)
    assert len(bars) == 1 and bars[0].c == 20.5
    assert hist.calls[-1]["schema"] == "ohlcv-1m"
    assert hist.calls[-1]["symbols"] == "ES.v.0"


def test_live_second_bars_trades_and_depth_use_core_plus_isolated_depth_sessions():
    second_rows = [Ohlcv(1_000 + i, 100 + i / 10, 101 + i / 10, 99 + i / 10, 100.5 + i / 10, 1) for i in range(60)]
    trade = Trade(1_059, 106.5, 3)
    depth = Depth(1_060, 106.25, levels=[Level(106.0, 106.25)])
    mbo = Depth(1_061, 106.25, order_id=99)
    core = FakeLive({"ohlcv-1s": second_rows, "trades": [trade]})
    mbp_book = FakeLive({"mbp-10": [depth]})
    mbo_book = FakeLive({"mbo": [mbo]})
    feed = make_feed(lives=[core, mbp_book, mbo_book])

    bars, ft, px = feed.recent_ex("NQ=F", 60)
    assert len(bars) == 2  # 1000-1019 partial UTC minute + 1020-1059 full minute
    assert ft == 1_059 and px == 106.5
    assert [s["schema"] for s in core.subscriptions] == ["ohlcv-1s", "trades"]
    assert all(s["symbols"] == "NQ.v.0" and s["stype_in"] == "continuous" for s in core.subscriptions)

    ticks = feed.trades("NQ=F")
    assert ticks and ticks[-1].price == 106.5 and ticks[-1].size == 3
    assert ticks[-1].ts_event == 1_059 and ticks[-1].ts_event_ns == 1_059 * NS

    depth_rows = feed.depth_events("NQ=F", schema="mbp-10")
    assert depth_rows and depth_rows[-1]["levels"][0]["bid_px"] == 106.0
    assert depth_rows[-1]["schema"] == "mbp-10"
    assert depth_rows[-1]["ts_event_ns"] == 1_060 * NS
    assert [s["schema"] for s in mbp_book.subscriptions] == ["mbp-10"]

    mbo_rows = feed.depth_events("NQ=F", schema="mbo")
    assert mbo_rows and mbo_rows[-1]["order_id"] == 99
    assert mbo_rows[-1]["schema"] == "mbo"
    assert [s["schema"] for s in mbo_book.subscriptions] == ["mbo"]
    assert all(row["schema"] == "mbo" for row in mbo_rows)
    assert all(row["schema"] == "mbp-10" for row in depth_rows)


def test_depth_mbo_trade_cannot_duplicate_core_tape_or_move_core_mark():
    trade = Trade(1_059, 106.5, 3, side="B", sequence=1)
    mbo_trade = Depth(1_060, 999.0, order_id=99)
    mbo_trade.action = "T"
    mbo_trade.side = "B"
    mbo_trade.size = 3
    mbo_trade.sequence = 2
    core = FakeLive({"ohlcv-1s": [Ohlcv(1_059, 106, 107, 105, 106.5, 1)], "trades": [trade]})
    book = FakeLive({"mbo": [mbo_trade]})
    feed = make_feed(lives=[core, book])

    feed.recent_ex("NQ=F", 1)
    assert len(feed.trades("NQ=F")) == 1
    core_mark = feed._last_price["NQ=F"]
    feed.depth_events("NQ=F", schema="mbo")
    ticks = feed.trades("NQ=F")
    assert len(ticks) == 1
    assert ticks[0].price == 106.5
    assert feed._last_price["NQ=F"] == core_mark
    assert feed.depth_events("NQ=F", schema="mbo")[-1]["price"] == 999.0


def test_depth_readiness_is_independent_per_symbol_and_schema():
    core = FakeLive()
    mbp_book = FakeLive({"mbp-10": [Depth(1_000, 100.5, levels=[Level(100.25, 100.5)])]})
    mbo_book = FakeLive()
    feed = make_feed(lives=[core, mbp_book, mbo_book])
    feed.start_live("NQ=F")
    assert feed.depth_events("NQ=F", schema="mbp-10")
    assert feed._depth_ready[("NQ=F", "mbp-10")].is_set() is True

    # Adding MBO after MBP-10 must create a fresh, unsatisfied readiness gate.
    feed._prepare_depth_live(["NQ=F"], "mbo")
    assert feed._depth_ready[("NQ=F", "mbo")].is_set() is False
    assert feed._depth_ready[("NQ=F", "mbp-10")].is_set() is True


def test_mbo_subscription_failure_does_not_poison_mbp10_or_churn_mbo_session():
    core = FakeLive()
    mbp_book = FakeLive({"mbp-10": [Depth(1_000, 100.5, levels=[Level(100.25, 100.5)])]})
    mbo_book = FakeLive({"mbo": [Error("MBO entitlement missing", code=5)]})
    unused = FakeLive()
    feed = make_feed(lives=[core, mbp_book, mbo_book, unused])

    feed.start_live("NQ=F")
    assert feed.depth_events("NQ=F", schema="mbp-10")
    with pytest.raises(RuntimeError, match="MBO entitlement missing"):
        feed.depth_events("NQ=F", schema="mbo")
    with pytest.raises(RuntimeError, match="MBO entitlement missing"):
        feed.depth_events("NQ=F", schema="mbo")
    assert unused.started is False

    # The MBP-10 session and its data remain healthy.
    assert feed.depth_events("NQ=F", schema="mbp-10")
    meta = feed.meta("NQ=F")
    assert meta["depth_schema_health"]["mbp-10"] is True
    assert meta["depth_schema_health"]["mbo"] is False
    assert meta["depth_error_codes"]["mbo"] == 5
    assert "mbo" in meta["depth_errors"]


def test_recoverable_depth_internal_error_rebuilds_only_that_schema():
    core = FakeLive()
    bad_mbo = FakeLive({"mbo": [Error("temporary MBO gateway failure", code=6)]})
    good_mbo = FakeLive({"mbo": [Depth(1_010, 101.0, order_id=10)]})
    feed = make_feed(lives=[core, bad_mbo, good_mbo])

    feed.start_live("NQ=F")
    with pytest.raises(RuntimeError, match="code=6"):
        feed.depth_events("NQ=F", schema="mbo")

    rows = feed.depth_events("NQ=F", schema="mbo")
    assert bad_mbo.stopped is True
    assert good_mbo.started is True
    assert rows[-1]["order_id"] == 10
    assert feed.meta("NQ=F")["depth_schema_health"]["mbo"] is True
    assert "mbo" not in feed.meta("NQ=F").get("depth_error_codes", {})


def test_fatal_depth_subscription_error_does_not_poison_core_session():
    core = FakeLive({
        "ohlcv-1s": [Ohlcv(1_000, 100, 101, 99, 100.5, 1)],
        "trades": [Trade(1_000, 100.5, 2)],
    })
    book = FakeLive({"mbp-10": [
        Error("depth subscription rejected", code=5),
        Depth(1_001, 100.5, levels=[Level(100.25, 100.5)]),  # buffered after fatal error
    ]})
    feed = make_feed(lives=[core, book])

    bars, _, px = feed.recent_ex("NQ=F", 1)
    assert bars and px == 100.5
    with pytest.raises(RuntimeError, match="depth error code=5.*rejected"):
        feed.depth_events("NQ=F", schema="mbp-10")
    assert feed._depth[("NQ=F", "mbp-10")]  # later buffered data cannot clear the fatal state

    assert feed._shared_live is core
    assert feed._shared_started is True
    assert core.stopped is False
    assert "NQ=F" not in feed._errors
    feed._raise_live_error("NQ=F")

    # Core data remains usable even though the optional depth session is fatal.
    core.callback(Trade(1_001, 101.0, 1, sequence=2))
    ticks = feed.trades("NQ=F")
    assert ticks[-1].price == 101.0
    assert feed._last_price["NQ=F"] == 101.0


def test_mbo_snapshot_omits_non_mbo_stream_records():
    snapshot = Depth(2_000, 200.25, flags=1)
    live = FakeLive({"mbo": [SystemMsg("subscription ack"), SimpleNamespace(stype_in_symbol="ES.v.0", instrument_id=7), snapshot]})
    feed = make_feed(lives=[live])
    rows = feed.mbo_snapshot("ES=F", timeout=0.2)
    assert len(rows) == 1
    assert rows[0]["schema"] == "mbo"
    assert rows[0]["order_id"] == 7


def test_replay_rows_cannot_rewind_live_price_and_ts_event_is_not_used_as_ordering():
    feed = make_feed()
    feed._live_callback("NQ=F", Ohlcv(2_000, 200, 201, 199, 200.5, 1))
    feed._live_callback("NQ=F", Ohlcv(1_999, 100, 101, 99, 100.5, 9))
    assert len(feed._second_bars["NQ=F"]) == 1
    assert feed._second_bars["NQ=F"][-1].ts == 2_000
    assert feed._last_price["NQ=F"] == 200.5

    # Databento guarantees monotonic ts_recv per symbol, not ts_event. A later-
    # received legitimate trade may therefore have an older exchange event time.
    feed._live_callback("NQ=F", Trade(2_001, 201.0, 1, sequence=10, ts_recv=2_001.10))
    feed._live_callback("NQ=F", Trade(2_000, 202.0, 1, sequence=11, ts_recv=2_001.20))
    ticks = list(feed._trades["NQ=F"])
    assert len(ticks) == 2
    assert ticks[-1].ts_event_ns < ticks[-2].ts_event_ns
    assert ticks[-1].ts_recv_ns > ticks[-2].ts_recv_ns
    assert feed._last_price["NQ=F"] == 202.0

    # A replayed record with an older receive timestamp may be retained in the
    # time-and-sales tape if it was previously missing, but it cannot rewind mark.
    feed._live_callback("NQ=F", Trade(1_998, 50.0, 1, sequence=8, ts_recv=1_998.50))
    ticks = list(feed._trades["NQ=F"])
    assert len(ticks) == 3
    assert ticks[-1].price == 50.0
    assert feed._last_price["NQ=F"] == 202.0


def test_roll_refresh_backfills_missing_second_bar_without_duplicates():
    feed = make_feed()
    for ts in (1_000, 1_002):
        feed._live_callback("NQ=F", Ohlcv(ts, 100, 101, 99, 100.5, 1))
    assert [b.ts for b in feed._second_bars["NQ=F"]] == [1_000, 1_002]

    feed._live_callback("NQ=F", Ohlcv(1_001, 100.25, 101, 100, 100.75, 2))
    feed._live_callback("NQ=F", Ohlcv(1_002, 100, 101, 99, 100.5, 1))
    assert [b.ts for b in feed._second_bars["NQ=F"]] == [1_000, 1_001, 1_002]
    assert [b.v for b in feed._second_bars["NQ=F"]] == [1, 2, 1]


def test_replay_backfill_keeps_trade_and_depth_buffers_receive_time_ordered_and_unique():
    feed = make_feed()
    feed._live_callback("NQ=F", Trade(2_000, 200.0, sequence=20, ts_recv=2_000.20))
    feed._live_callback("NQ=F", Trade(1_999, 199.0, sequence=19, ts_recv=1_999.90))
    feed._live_callback("NQ=F", Trade(1_999, 199.0, sequence=19, ts_recv=1_999.90))
    ticks = feed.trades("NQ=F")
    assert [x.sequence for x in ticks] == [19, 20]

    newer = Databento._event_record(Depth(2_000, 200.0, order_id=20, ts_recv=2_000.20))
    older = Databento._event_record(Depth(1_999, 199.0, order_id=19, ts_recv=1_999.90))
    with feed._lock:
        assert feed._append_depth_locked("NQ=F", newer) is True
        assert feed._append_depth_locked("NQ=F", older) is True
        assert feed._append_depth_locked("NQ=F", older) is False
        rows = list(feed._depth[("NQ=F", "mbo")])
    assert [row["order_id"] for row in rows] == [19, 20]


def test_mbo_volume_cannot_evict_mbp10_buffer():
    feed = Databento(
        api_key="db-test",
        sdk=FakeSDK,
        historical=FakeHistorical({}),
        live_factory=lambda: FakeLive(),
        max_depth=1000,
    )
    mbp = Databento._event_record(Depth(1_000, 100.0, order_id=1, levels=[Level(99.75, 100.0)]))
    with feed._lock:
        assert feed._append_depth_locked("NQ=F", mbp)
        for i in range(1_250):
            mbo = Databento._event_record(Depth(1_001 + i, 100.0 + i / 1000, order_id=10_000 + i))
            assert feed._append_depth_locked("NQ=F", mbo)
    assert len(feed._depth[("NQ=F", "mbo")]) == 1000
    assert len(feed._depth[("NQ=F", "mbp-10")]) == 1
    assert feed._depth[("NQ=F", "mbp-10")][0]["order_id"] == 1


def test_mbo_snapshot_stops_collecting_after_f_last():
    snapshot = Depth(2_000, 200.25, flags=1, order_id=1)
    live_after = Depth(2_001, 201.00, flags=0, order_id=2)
    live = FakeLive({"mbo": [snapshot, live_after]})
    feed = make_feed(lives=[live])
    rows = feed.mbo_snapshot("NQ=F", timeout=0.1)
    assert [row["order_id"] for row in rows] == [1]
    assert live.stopped is True


def test_mbo_snapshot_subscribe_failure_still_closes_temporary_client():
    class FailSubscribe(FakeLive):
        def subscribe(self, **kwargs):
            raise RuntimeError("snapshot subscribe failed")

    live = FailSubscribe()
    feed = make_feed(lives=[live])
    with pytest.raises(RuntimeError, match="snapshot subscribe failed"):
        feed.mbo_snapshot("NQ=F", timeout=0.1)
    assert live.stopped is True


def test_mbo_snapshot_malformed_record_fails_closed_and_cleans_up():
    bad = Depth(2_000, 200.25, flags=1)
    # Force event serialization itself to fail instead of relying on tolerant scalar conversion.
    bad.levels = object()
    live = FakeLive({"mbo": [bad]})
    feed = make_feed(lives=[live])
    with pytest.raises(RuntimeError, match="snapshot record error"):
        feed.mbo_snapshot("NQ=F", timeout=0.1)
    assert live.stopped is True


def test_mbo_snapshot_requires_f_last_before_returning_rows():
    live = FakeLive({"mbo": [Depth(2_000, 200.25, flags=0)]})
    feed = make_feed(lives=[live])
    with pytest.raises(TimeoutError, match="snapshot timed out"):
        feed.mbo_snapshot("NQ=F", timeout=0.05)
    assert live.stopped is True


def test_mbo_snapshots_are_serialized_to_one_temporary_session_at_a_time():
    active = 0
    peak = 0
    gate = threading.Event()
    entered = threading.Event()
    lock = threading.Lock()

    class BlockingSnapshot(FakeLive):
        def start(self):
            nonlocal active, peak
            with lock:
                active += 1
                peak = max(peak, active)
                entered.set()
            gate.wait(2)
            super().start()

        def stop(self):
            nonlocal active
            super().stop()
            with lock:
                active -= 1

    clients = [
        BlockingSnapshot({"mbo": [Depth(3_000, 100.0, flags=1)]}),
        BlockingSnapshot({"mbo": [Depth(3_001, 101.0, flags=1)]}),
    ]
    feed = make_feed(lives=clients)
    results = []

    one = threading.Thread(target=lambda: results.append(feed.mbo_snapshot("NQ=F", timeout=1)))
    two = threading.Thread(target=lambda: results.append(feed.mbo_snapshot("ES=F", timeout=1)))
    one.start()
    assert entered.wait(1)
    two.start()
    assert peak == 1
    gate.set()
    one.join(3)
    two.join(3)
    assert not one.is_alive() and not two.is_alive()
    assert peak == 1
    assert len(results) == 2


def test_shared_live_start_failure_resets_client_for_clean_retry():
    class FailStart(FakeLive):
        def __init__(self):
            super().__init__()
            self.terminated = False

        def start(self):
            raise RuntimeError("shared start failed")

        def terminate(self):
            self.terminated = True

    bad = FailStart()
    good = FakeLive()
    feed = make_feed(lives=[bad, good])

    with pytest.raises(RuntimeError, match="shared start failed"):
        feed.prepare_live(["NQ=F", "ES=F"])

    assert bad.terminated is True
    assert feed._shared_live is None
    assert feed._shared_started is False
    assert not feed._live
    assert not feed._live_started
    assert not feed._subscriptions
    assert not feed._continuous_to_symbol
    assert not feed._instrument_to_symbol

    assert feed.prepare_live(["NQ=F"]) is good
    assert good.started is True
    assert feed._shared_started is True


def test_shared_live_stop_falls_back_to_terminate():
    class StopFails(FakeLive):
        def __init__(self):
            super().__init__()
            self.terminated = False
            self.blocked = 0

        def stop(self):
            raise RuntimeError("graceful stop failed")

        def terminate(self):
            self.terminated = True

        def block_for_close(self, timeout=None):
            self.blocked += 1

    live = StopFails()
    feed = make_feed(lives=[live])
    feed.start_live("NQ=F")
    feed.stop_live()

    assert live.terminated is True
    assert live.blocked == 1
    assert feed._shared_live is None
    assert feed._shared_started is False
    assert not feed._live_started


def test_all_registered_futures_share_one_core_live_session_and_depth_is_separate():
    core = FakeLive()
    book = FakeLive()
    feed = make_feed(lives=[core, book])
    futures = [spec for spec in REGISTRY.values() if spec.kind == "futures"]
    assert len(futures) > 10  # guards the Databento Standard 10-session failure mode
    client = feed.prepare_live([spec.ticker for spec in futures], start_ts=1_000)
    assert client is core
    assert core.started is True
    assert len(core.subscriptions) == len(futures) * 2
    assert {sub["symbols"] for sub in core.subscriptions} == {f"{spec.ticker[:-2]}.v.0" for spec in futures}
    assert all("start" in sub for sub in core.subscriptions)

    before = len(core.subscriptions)
    feed.start_live(futures[0].ticker, include_depth="mbp-10", start_ts=2_000)
    assert len(core.subscriptions) == before
    assert book.started is True
    assert [sub["schema"] for sub in book.subscriptions] == ["mbp-10"]

    feed.stop_live(futures[0].ticker)
    assert core.stopped is False
    assert book.stopped is True  # it was the only active depth symbol
    feed.stop_live()
    assert core.stopped is True


def test_daily_refresh_preserves_exact_core_and_depth_schema_sets():
    first_core = FakeLive()
    first_book = FakeLive()
    second_core = FakeLive()
    second_book = FakeLive()
    feed = make_feed(lives=[first_core, first_book, second_core, second_book])
    feed.prepare_live(["NQ=F", "ES=F"])
    feed.depth_events("NQ=F", schema="mbo")

    assert {sub["schema"] for sub in first_core.subscriptions} == {"ohlcv-1s", "trades"}
    assert [sub["schema"] for sub in first_book.subscriptions] == ["mbo"]

    feed.refresh_live(["NQ=F", "ES=F"], start_ts=5_000)
    assert first_core.stopped is True
    assert first_book.stopped is True
    assert second_core.started is True
    assert second_book.started is True
    nq_core = {sub["schema"] for sub in second_core.subscriptions if sub["symbols"] == "NQ.v.0"}
    es_core = {sub["schema"] for sub in second_core.subscriptions if sub["symbols"] == "ES.v.0"}
    assert nq_core == {"ohlcv-1s", "trades"}
    assert es_core == {"ohlcv-1s", "trades"}
    assert {sub["schema"] for sub in second_book.subscriptions if sub["symbols"] == "NQ.v.0"} == {"mbo"}
    assert not [sub for sub in second_book.subscriptions if sub["symbols"] == "ES.v.0"]
    assert all("start" in sub for sub in second_core.subscriptions + second_book.subscriptions)


def test_failed_depth_refresh_does_not_churn_core_and_retries_on_next_depth_request():
    class FailStart(FakeLive):
        def __init__(self):
            super().__init__()
            self.terminated = False

        def start(self):
            raise RuntimeError("depth refresh failed")

        def terminate(self):
            self.terminated = True

    first_core = FakeLive()
    first_book = FakeLive({"mbp-10": [Depth(4_900, 100.0, levels=[Level(99.75, 100.0)])]})
    refreshed_core = FakeLive()
    bad_book = FailStart()
    good_book = FakeLive({"mbp-10": [Depth(5_101, 101.0, levels=[Level(100.75, 101.0)])]})
    feed = make_feed(lives=[first_core, first_book, refreshed_core, bad_book, good_book])
    feed.prepare_live(["NQ=F", "ES=F"])
    assert feed.depth_events("NQ=F", schema="mbp-10")

    # Optional depth failure is recorded but does not fail/churn the refreshed core.
    feed.refresh_live(["NQ=F", "ES=F"], start_ts=5_000)
    assert bad_book.terminated is True
    assert refreshed_core.started is True
    assert refreshed_core.stopped is False
    meta = feed.meta("NQ=F")
    assert meta["depth_session_ok"] is False
    assert "depth refresh failed" in meta["depth_error"]

    # The next explicit book request retries only the isolated depth socket.
    rows = feed.depth_events("NQ=F", schema="mbp-10")
    assert good_book.started is True
    assert refreshed_core.stopped is False
    assert rows[-1]["price"] == 101.0
    meta = feed.meta("NQ=F")
    assert meta["depth_session_ok"] is True
    assert "depth_error" not in meta


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


def test_runner_summary_reflects_databento_transport_health():
    feed = make_feed()
    feed._live_callback("NQ=F", Error("invalid core subscription", code=5))
    journal = Journal(":memory:")
    runner = AssetRunner(
        RunnerConfig(resolve("NQ"), Inputs(use_tide=False, use_eod_flat=False)),
        journal,
        {"yahoo": feed},
    )
    try:
        summary = runner.summary()
        assert summary["feed_provider"] == "databento"
        assert summary["feed_health"]["core_session_ok"] is False
        assert summary["feed_health"]["core_error_code"] == 5
        assert "invalid core subscription" in summary["feed_health"]["live_error"]
        assert summary["feed_capabilities"]["depth_schema_isolation"] is True
    finally:
        journal.con.close()


def test_portfolio_prepares_shared_live_feed_before_spawning_futures(monkeypatch, tmp_path):
    events = []

    class Feed:
        def prepare_live(self, symbols):
            events.append(("prepare", tuple(symbols)))

    feed = Feed()
    journal = Journal(":memory:")
    port = Portfolio(journal, str(tmp_path))
    nq = AssetRunner(RunnerConfig(resolve("NQ"), Inputs(use_tide=False, use_eod_flat=False)), journal, {"yahoo": feed})
    es = AssetRunner(RunnerConfig(resolve("ES"), Inputs(use_tide=False, use_eod_flat=False)), journal, {"yahoo": feed})
    port.runners = {"NQ": nq, "ES": es}
    port.order = ["NQ", "ES"]
    monkeypatch.setattr(port, "_spawn", lambda runner: events.append(("spawn", runner.symbol)))
    port._stop.set()  # make the daemon sampler return immediately
    port.start()
    assert events[0] == ("prepare", ("NQ=F", "ES=F"))
    assert events[1:] == [("spawn", "NQ"), ("spawn", "ES")]


def test_dynamic_future_add_prepares_live_before_spawn(monkeypatch, tmp_path):
    events = []

    class Feed:
        def prepare_live(self, symbols):
            events.append(("prepare", tuple(symbols)))

    feed = Feed()
    port = Portfolio(Journal(":memory:"), str(tmp_path))
    port.feeds["yahoo"] = feed
    monkeypatch.setattr(port, "_spawn", lambda runner: events.append(("spawn", runner.symbol)))
    runner = port.add_asset(resolve("NQ"), start=True)
    assert runner.symbol == "NQ"
    assert events == [("prepare", ("NQ=F",)), ("spawn", "NQ")]


def test_portfolio_refreshes_continuous_feed_once_on_new_utc_day(tmp_path):
    calls = []

    class Feed:
        def refresh_live(self, symbols, start_ts=None):
            calls.append((tuple(symbols), start_ts))

    feed = Feed()
    port = Portfolio(Journal(":memory:"), str(tmp_path))
    port._continuous_refresh_day = 100
    port.runners = {
        "NQ": SimpleNamespace(feed=feed, spec=resolve("NQ")),
        "ES": SimpleNamespace(feed=feed, spec=resolve("ES")),
    }
    port.order = ["NQ", "ES"]
    now = 101 * 86400 + 123
    assert port._refresh_continuous_feeds(now) is True
    assert calls == [(("NQ=F", "ES=F"), int(now) - 300)]
    assert port._continuous_refresh_day == 101
    assert port._refresh_continuous_feeds(now + 60) is False
    assert len(calls) == 1


def test_portfolio_does_not_advance_roll_day_when_refresh_fails(tmp_path):
    class Feed:
        def refresh_live(self, symbols, start_ts=None):
            raise RuntimeError("refresh unavailable")

    feed = Feed()
    port = Portfolio(Journal(":memory:"), str(tmp_path))
    port._continuous_refresh_day = 100
    port.runners = {"NQ": SimpleNamespace(feed=feed, spec=resolve("NQ"))}
    port.order = ["NQ"]
    with pytest.raises(RuntimeError, match="refresh unavailable"):
        port._refresh_continuous_feeds(101 * 86400)
    assert port._continuous_refresh_day == 100


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
    core_live = FakeLive({
        "ohlcv-1s": [Ohlcv(4_000, 100, 101, 99, 100.5, 1)],
        "trades": [Trade(4_000, 100.5, 2)],
    })
    depth_live = FakeLive({
        "mbp-10": [Depth(4_001, 100.5, levels=[Level(100.25, 100.5)])],
    })
    snapshot_live = FakeLive({"mbo": [Depth(4_002, 100.5, flags=1)]})
    feed = make_feed(lives=[core_live, depth_live, snapshot_live])

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
