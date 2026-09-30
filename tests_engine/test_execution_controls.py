"""Execution controls use the real emulator and strategy, without market services."""
import json
import threading
import urllib.error
import urllib.request
from dataclasses import asdict, replace
from datetime import datetime, timezone

import pytest

from icarus_engine.assets import AssetSpec, PRIMARY_INTRADAY_TIMEFRAMES
from icarus_engine.pine.timeframe import Bar
from icarus_engine.runtime import AssetRunner, Journal, Portfolio, RunnerConfig
from icarus_engine.server import serve
from icarus_engine.strategy.inputs import Inputs


def make_runner(symbol="TEST"):
    spec = AssetSpec(symbol, symbol, "yahoo", symbol, "crypto", 1, 1,
                     chart_tf="1", commission=0, roll="none")
    r = AssetRunner(RunnerConfig(spec, Inputs(use_tide=False, use_eod_flat=False)), Journal(":memory:"))
    r._init_strategy(100)
    r.last_price = 100
    r.warm = True
    return r


def pending(r, direction=1, limit=None):
    entry = "Long" if direction == 1 else "Short"
    r.em.entry(entry, direction, 1, limit=limit)
    r.em.exit("pending_bracket", entry, stop=90 if direction == 1 else 110)
    r.strat.w_slot_queue.append(1)
    r.strat.tod_hour_queue.append(9)
    if limit is not None:
        r.strat.rate_pend_dir = direction
        r.strat.rate_pend_bar = 0


@pytest.mark.parametrize("limit", [None, 99])
def test_closed_futures_session_with_no_feed_clock_is_not_a_transport_failure(monkeypatch):
    from icarus_engine.assets import resolve
    import icarus_engine.runtime as runtime

    class EmptyFeed:
        def recent_ex(self, *args, **kwargs):
            return [], 0, None

    spec = resolve("NQ")
    feed = EmptyFeed()
    r = AssetRunner(
        RunnerConfig(spec, Inputs(use_tide=False, use_eod_flat=False)),
        Journal(":memory:"),
        {"yahoo": feed},
    )
    # Saturday: the CME futures calendar is closed.
    closed_ts = datetime(2026, 9, 26, 12, 0, tzinfo=timezone.utc).timestamp()
    monkeypatch.setattr(runtime.time, "time", lambda: closed_ts)
    r.feed_error = "stale prior warning"
    r.last_error = r.feed_error
    r.poll()
    assert r.errors == 0
    assert r.feed_error == ""
    assert r.last_error == ""
    assert r.last_poll_ok == closed_ts


def test_pause_cancels_market_and_limit_before_next_fill(limit):
    r = make_runner()
    r.strat.w_slot_queue = [0]
    r.strat.tod_hour_queue = [8]
    pending(r, limit=limit)
    assert r.set_paused(True) == 1
    assert not r.em._pending_entries and not r.em._exits
    assert r.strat.w_slot_queue == [0] and r.strat.tod_hour_queue == [8]
    assert r.strat.rate_pend_dir == 0
    r.on_sub_bar(Bar(60, 100, 105, 94, 100, 1), 1, live=True)
    assert not r.em.fills


def test_legacy_pause_flag_is_checked_before_emulator_fills():
    r = make_runner()
    pending(r)
    r.paused = True
    r.on_sub_bar(Bar(60, 100, 100, 100, 100, 1), 1, live=True)
    assert not r.em.open and not r.em.fills and not r.em._pending_entries
    assert not r.strat.w_slot_queue


def test_pause_preserves_active_protection_and_closed_trade_learning():
    r = make_runner()
    r.em.entry("Long", 1, 1)
    r.em.process_bar(Bar(0, 100, 100, 100, 100, 1), 0)
    r.em.exit("protect", "Long", stop=95, comment_loss="L_SL")
    r.strat.w_slot_queue = [0]
    r.strat.tod_hour_queue = [8]
    pending(r, -1)
    r.set_paused(True)
    assert "protect" in r.em._exits and "pending_bracket" not in r.em._exits
    assert r.strat.w_slot_queue == [0]
    r.on_sub_bar(Bar(60, 100, 100, 94, 95, 1), 1, live=True)
    assert not r.em.open
    assert r.em.closed[0].exit_comment == "L_SL"
    assert r.strat.w_outcome[0] == -1 and r.strat.tod_losses[8] == 1
    assert not r.strat.w_slot_queue and not r.strat.tod_hour_queue


def test_pause_keeps_close_order_for_open_trade():
    r = make_runner()
    r.em.entry("Long", 1, 1)
    r.em.process_bar(Bar(0, 100, 100, 100, 100, 1), 0)
    r.em.close("Long", "protective close")
    pending(r, -1)
    r.set_paused(True)
    assert [c.entry_id for c in r.em._pending_closes] == ["Long"]
    r.em.process_bar(Bar(60, 100, 100, 100, 100, 1), 1)
    assert not r.em.open and r.em.closed[0].exit_comment == "protective close"


def test_pause_clears_stale_pullback_intent_without_discarding_filled_snapshot():
    r = make_runner()
    pending(r, limit=100)
    r.em.process_bar(Bar(0, 100, 100, 100, 100, 1), 0)
    assert r.strat.rate_pend_dir == 1 and r.em.position_size == 1
    r.set_paused(True)
    assert r.strat.rate_pend_dir == 0
    assert r.strat.w_slot_queue == [1] and r.strat.tod_hour_queue == [9]


def test_flatten_pending_only_cancels_intent_without_a_fill():
    r = make_runner()
    pending(r, limit=99)
    assert r.flatten() == 0
    assert not r.em._pending_entries and not r.em._exits
    assert not r.strat.w_slot_queue and not r.strat.tod_hour_queue
    assert r.strat.rate_pend_dir == 0
    r.em.process_bar(Bar(60, 100, 101, 90, 100, 1), 1)
    assert not r.em.fills


def test_flatten_open_trade_cannot_fill_pending_reversal():
    r = make_runner()
    r.em.entry("Long", 1, 1)
    r.em.process_bar(Bar(0, 100, 100, 100, 100, 1), 0)
    r.strat.w_slot_queue = [0]
    r.strat.tod_hour_queue = [8]
    pending(r, -1)
    assert r.flatten() == 1
    assert not r.em.open and not r.em._pending_entries
    assert [f.kind for f in r.em.fills] == ["entry", "close"]
    assert r.strat.w_slot_queue == [0] and r.strat.tod_hour_queue == [8]


@pytest.fixture
def configured(tmp_path):
    (tmp_path / "presets").mkdir()
    (tmp_path / "presets" / "other.json").write_text(json.dumps({"tp1_pts": 51, "_meta": {"capital": 12345}}))
    override = tmp_path / "inputs.TEST.json"
    override.write_text('{"tp1_pts": 23}')
    port = Portfolio(Journal(":memory:"), str(tmp_path))
    r = make_runner()
    port.runners[r.symbol] = r
    port.order = [r.symbol]
    return port, r, override


@pytest.mark.parametrize("exposure", ["open", "pending"])
@pytest.mark.parametrize("operation", ["direct", "inputs", "reset", "preset", "rewarm"])
def test_configuration_rejects_exposure_before_mutating_anything(configured, exposure, operation):
    port, r, path = configured
    pending(r)
    if exposure == "open":
        r.em.process_bar(Bar(0, 100, 100, 100, 100, 1), 0)
    old = (r.em, asdict(r.spec), asdict(r.cfg), r.inputs_base.to_dict(), path.read_bytes())
    with pytest.raises(ValueError, match="flatten"):
        if operation == "direct":
            r.rewarm(replace(r.inputs_base, tp1_pts=77))
        elif operation == "inputs":
            port.rewarm_asset("TEST", {"tp1_pts": 77}, True)
        elif operation == "reset":
            port.rewarm_asset("TEST", reset=True)
        elif operation == "preset":
            port.rewarm_asset("TEST", preset="other")
        else:
            port.rewarm_asset("TEST")
    assert (r.em, asdict(r.spec), asdict(r.cfg), r.inputs_base.to_dict(), path.read_bytes()) == old


def test_unavailable_timeframe_rejects_before_persist(configured):
    port, r, path = configured
    before = path.read_bytes()
    with pytest.raises(ValueError, match="cached history unavailable"):
        port.rewarm_asset("TEST", {"htf_tf_1": "720"}, True)
    assert path.read_bytes() == before and r.inputs_base.htf_tf_1 != "720"


@pytest.mark.parametrize("operation", ["direct", "inputs", "reset", "preset", "rewarm"])
def test_initial_warmup_rejects_configuration_before_mutation_or_feed(configured, monkeypatch, operation):
    port, r, path = configured
    r.warm = False
    r.strat = None
    r.cfg.pts_ref_price = 200
    r.subbars = [(Bar(60, 100, 100, 100, 100, 1), 1)]
    def forbidden(*args, **kwargs):
        pytest.fail("initial warming configuration must not fetch market data")
    monkeypatch.setattr(r.feed, "daily_volume", forbidden)
    before = (r.em, asdict(r.spec), asdict(r.cfg), r.inputs_base.to_dict(), path.read_bytes())
    with pytest.raises(ValueError, match="initial warm-up must finish"):
        if operation == "direct":
            r.rewarm(replace(r.inputs_base, tp1_pts=77))
        elif operation == "inputs":
            port.rewarm_asset("TEST", {"tp1_pts": 77}, True)
        elif operation == "reset":
            port.rewarm_asset("TEST", reset=True)
        elif operation == "preset":
            port.rewarm_asset("TEST", preset="other")
        else:
            port.rewarm_asset("TEST")
    assert (r.em, asdict(r.spec), asdict(r.cfg), r.inputs_base.to_dict(), path.read_bytes()) == before
    assert r.strat is None and r.warm is False and r.rewarming is False


@pytest.mark.parametrize("initialized", [True, False])
def test_rewarm_uses_existing_scale_without_current_feed(configured, monkeypatch, initialized):
    port, r, _ = configured
    if not initialized:
        r.strat = None
    r.cfg.pts_ref_price = 200
    r.pts_scale = .5
    r.subbars = [(Bar(60, 100, 100, 100, 100, 1), 1)]
    def forbidden(*args, **kwargs):
        pytest.fail("configuration replay must not request a current daily reference")
    monkeypatch.setattr(r.feed, "daily_volume", forbidden)
    port.rewarm_asset("TEST", {"tp1_pts": 80})
    assert r.inputs_base.tp1_pts == 80 and r.inputs.tp1_pts == 40
    assert r.cfg.inputs == r.inputs_base and r.cfg.fixed_pts_scale == .5


def test_configuration_lock_keeps_concurrent_fill_in_new_engine(configured, monkeypatch):
    port, r, _ = configured
    attempted = threading.Event()
    filled = threading.Event()
    original_guard = r.ensure_configurable
    workers = []
    def fill():
        attempted.set()
        with r.lock:
            r.em.entry("Long", 1, 1)
            r.em.process_bar(Bar(60, 100, 100, 100, 100, 1), 1)
            filled.set()
    def guard():
        original_guard()
        if not workers:
            worker = threading.Thread(target=fill, daemon=True)
            workers.append(worker)
            worker.start()
            assert attempted.wait(3)
            assert not filled.is_set()
    monkeypatch.setattr(r, "ensure_configurable", guard)
    port.rewarm_asset("TEST", {"tp1_pts": 80}, True)
    workers[0].join(3)
    assert filled.is_set() and r.em.position_size == 1
    assert r.inputs_base.tp1_pts == 80


@pytest.fixture
def admin(configured):
    port, r, path = configured
    srv = serve(port, 0, token="test-token", start=False)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    def post(route, body):
        req = urllib.request.Request(f"http://127.0.0.1:{srv.server_address[1]}" + route,
                                     data=json.dumps(body).encode(), headers={"Authorization": "Bearer test-token"})
        try:
            with urllib.request.urlopen(req, timeout=5) as reply:
                return reply.status, json.load(reply)
        except urllib.error.HTTPError as ex:
            return ex.code, json.load(ex)
    yield port, r, path, post
    srv.shutdown()
    srv.server_close()
    thread.join(5)


def test_all_admin_configuration_routes_reject_pending_before_side_effects(admin):
    _, r, path, post = admin
    pending(r)
    before = (r.em, asdict(r.spec), path.read_bytes())
    for route, extra in [("inputs", {"values": {"tp1_pts": 80}}), ("inputs/reset", {}),
                         ("preset", {"preset": "other"}), ("rewarm", {})]:
        status, body = post("/admin/" + route, {"asset": "TEST", **extra})
        assert status == 400 and "flatten" in body["detail"]
        assert (r.em, asdict(r.spec), path.read_bytes()) == before


def test_admin_all_assets_preflight_prevents_partial_writes(admin):
    port, r, path, post = admin
    other = make_runner("OTHER")
    port.runners["OTHER"] = other
    port.order.append("OTHER")
    pending(other)
    before = path.read_bytes()
    status, _ = post("/admin/inputs", {"asset": "*", "values": {"tp1_pts": 80}})
    assert status == 400
    assert path.read_bytes() == before and r.inputs_base.tp1_pts != 80


def test_admin_all_assets_rolls_back_prior_success_on_late_replay_failure(admin, monkeypatch):
    port, first, first_path, post = admin
    other = make_runner("OTHER")
    port.runners["OTHER"] = other
    port.order.append("OTHER")
    first_before_file = first_path.read_bytes()
    first_before_inputs = first.inputs_base.to_dict()
    first_before_spec = asdict(first.spec)
    first_before_em = first.em
    first_before_strat = first.strat
    first_before_closed = list(first.em.closed)
    first_before_fills = list(first.em.fills)
    first_before_bars = list(first.bars)
    other_before_inputs = other.inputs_base.to_dict()
    other_before_em = other.em
    other_before_strat = other.strat
    original = other.rewarm
    calls = 0

    def fail_once(inputs, sources=None, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("synthetic second replay failure")
        return original(inputs, sources, **kwargs)

    monkeypatch.setattr(other, "rewarm", fail_once)
    status, body = post("/admin/inputs", {"asset": "*", "values": {"tp1_pts": 80}, "persist": True})
    assert status == 500 and "synthetic second replay failure" in body["detail"]
    assert first_path.read_bytes() == first_before_file
    assert first.inputs_base.to_dict() == first_before_inputs
    assert asdict(first.spec) == first_before_spec
    assert first.em is first_before_em and first.strat is first_before_strat
    assert first.em.closed == first_before_closed and first.em.fills == first_before_fills
    assert list(first.bars) == first_before_bars
    assert other.inputs_base.to_dict() == other_before_inputs
    assert other.em is other_before_em and other.strat is other_before_strat
    assert not (first_path.parent / "inputs.OTHER.json").exists()


def test_admin_pause_flatten_and_config_success_are_completed_on_return(admin):
    _, r, path, post = admin
    pending(r, limit=99)
    assert post("/admin/pause", {"asset": "TEST"})[0] == 200
    assert r.paused and not r.em._pending_entries
    assert post("/admin/preset", {"asset": "TEST", "preset": "other"})[0] == 200
    assert r.cfg.preset == "other" and r.spec.capital == 12345 and not r.rewarming
    assert post("/admin/inputs/reset", {"asset": "TEST"})[0] == 200
    assert not path.exists() and r.inputs_base.tp1_pts == 51
    assert post("/admin/resume", {"asset": "TEST"})[0] == 200
    assert not r.paused
    r._init_strategy(100)
    pending(r)
    status, response = post("/admin/flatten", {"asset": "TEST", "confirm": True})
    assert status == 200 and response["closed"] == {"TEST": 0}
    assert not r.em._pending_entries


def test_chart_configuration_rebuilds_paper_engine_and_persists_meta(configured):
    port, r, path = configured
    r.live_from_ts = 1
    r.subbars = [(Bar(k * 60, 100 + k, 101 + k, 99 + k, 100.5 + k, 1), 1) for k in range(12)]
    port.rewarm_asset("TEST", {}, True, chart={
        "timeframe": "2m", "chart_type": "heikin_ashi", "fill_on": "real", "security_source": "chart"
    })
    assert r.chart_minutes == 2
    assert r.spec.chart_tf == "2" and r.spec.chart_type == "heikin_ashi"
    assert r.spec.fill_on == "real" and r.spec.security_source == "chart"
    assert r.live_from_ts > 1
    assert r.live_closed_start == len(r.em.closed)
    summary = r.summary()
    assert summary["calculation_basis"] == {
        "timeframe": "2", "timeframe_minutes": 2, "chart_type": "heikin_ashi",
        "fill_on": "real", "security_source": "chart", "session": "24/7",
    }
    chart = r.chart()
    assert chart["fill_on"] == "real" and chart["security_source"] == "chart"
    persisted = json.loads(path.read_text())
    assert persisted["_meta"]["timeframe"] == "2"
    assert persisted["_meta"]["chart_type"] == "heikin_ashi"
    assert any(src.startswith("inputs.TEST.json") for src in r.cfg.sources)
    assert "override" not in r.cfg.sources
    assert len(r.bars) == 6


def test_chart_configuration_refuses_to_invent_finer_bars(configured):
    port, r, path = configured
    before = path.read_bytes()
    r.subbars = [(Bar(k * 300, 100, 101, 99, 100, 1), 5) for k in range(6)]
    caps = r.chart_capability_view()
    assert "2" not in caps["available_from_cache"]
    with pytest.raises(ValueError, match="cannot be losslessly rebuilt"):
        port.rewarm_asset("TEST", {}, True, chart={"timeframe": "2"})
    assert path.read_bytes() == before
    assert r.chart_minutes == 1


def test_failed_configuration_replay_never_persists_candidate(configured, monkeypatch):
    port, r, path = configured
    r.subbars = [(Bar(k * 60, 100 + k, 101 + k, 99 + k, 100.5 + k, 1), 1) for k in range(12)]
    before_file = path.read_bytes()
    before_spec = asdict(r.spec)
    before_em = r.em
    before_strat = r.strat
    before_closed = list(r.em.closed)
    before_fills = list(r.em.fills)
    before_bars = list(r.bars)
    r.live_from_ts = 123
    original = r.rewarm
    calls = 0

    def fail_once(inputs, sources=None, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("synthetic replay failure")
        return original(inputs, sources, **kwargs)

    monkeypatch.setattr(r, "rewarm", fail_once)
    with pytest.raises(RuntimeError, match="synthetic replay failure"):
        port.rewarm_asset("TEST", {"tp1_pts": 80}, True, chart={"timeframe": "2", "chart_type": "heikin_ashi"})
    assert path.read_bytes() == before_file
    assert asdict(r.spec) == before_spec
    assert r.chart_minutes == 1
    assert r.live_from_ts == 123
    assert r.em is before_em and r.strat is before_strat
    assert r.em.closed == before_closed and r.em.fills == before_fills
    assert list(r.bars) == before_bars


def test_reset_removes_persisted_chart_meta_and_restores_baseline(configured):
    port, r, path = configured
    r.subbars = [(Bar(k * 60, 100 + k, 101 + k, 99 + k, 100.5 + k, 1), 1) for k in range(12)]
    port.rewarm_asset("TEST", {}, True, chart={"timeframe": "2", "chart_type": "heikin_ashi"})
    assert r.chart_minutes == 2 and r.spec.chart_type == "heikin_ashi"
    assert json.loads(path.read_text())["_meta"]["timeframe"] == "2"

    port.rewarm_asset("TEST", reset=True)
    assert not path.exists()
    assert r.chart_minutes == 1
    assert r.spec.chart_tf == "1" and r.spec.chart_type == "real"


def test_heikin_ashi_signals_can_fill_on_real_market_open():
    def runner(fill_on):
        spec = AssetSpec("HA", "HA", "yahoo", "HA", "crypto", 0.25, 1,
                         chart_tf="1", chart_type="heikin_ashi", fill_on=fill_on,
                         commission=0, roll="none")
        r = AssetRunner(RunnerConfig(spec, Inputs(use_tide=False, use_eod_flat=False)), Journal(":memory:"))
        r.warm = True
        return r

    first = Bar(0, 100, 110, 90, 105, 1)
    second = Bar(60, 120, 125, 115, 122, 1)

    real_fill = runner("real")
    real_fill._on_chart_bar(first, live=False)
    real_fill.em.entry("Manual", 1, 1)
    real_fill._on_chart_bar(second, live=False)
    real_px = next(f.price for f in real_fill.em.fills if f.entry_id == "Manual" and f.kind == "entry")

    chart_fill = runner("chart")
    chart_fill._on_chart_bar(first, live=False)
    chart_fill.em.entry("Manual", 1, 1)
    chart_fill._on_chart_bar(second, live=False)
    chart_px = next(f.price for f in chart_fill.em.fills if f.entry_id == "Manual" and f.kind == "entry")

    assert real_px == 120
    assert chart_px != real_px
    assert real_fill.bars[-1].o != second.o  # strategy bar is synthetic HA while execution used the real open


def test_successful_rewarm_starts_new_paper_equity_epoch(configured):
    port, r, _ = configured
    before = port.equity_epoch
    port.rewarm_asset("TEST", {"tp1_pts": 80})
    assert port.equity_epoch >= before
    status = port.status()
    assert status["equity_epoch"] == port.equity_epoch


def test_failed_all_assets_update_restores_equity_epoch(admin, monkeypatch):
    port, first, _, post = admin
    other = make_runner("OTHER")
    port.runners["OTHER"] = other
    port.order.append("OTHER")
    epoch_before = port.equity_epoch
    original = other.rewarm
    calls = 0

    def fail_once(inputs, sources=None, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("synthetic epoch rollback failure")
        return original(inputs, sources, **kwargs)

    monkeypatch.setattr(other, "rewarm", fail_once)
    status, _ = post("/admin/inputs", {"asset": "*", "values": {"tp1_pts": 81}, "persist": True})
    assert status == 500
    assert port.equity_epoch == epoch_before


def test_live_trade_classification_uses_execution_boundary_not_bar_start_time():
    r = make_runner("BOUNDARY")

    # Historical closed trade.
    r.em.process_bar(Bar(0, 100, 100, 100, 100, 1), 0)
    r.em.entry("Hist", 1, 1)
    r.em.process_bar(Bar(60, 100, 100, 100, 100, 1), 1)
    r.em.close("Hist", "hist close")
    r.em.process_bar(Bar(120, 101, 101, 101, 101, 1), 2)
    r.live_closed_start = len(r.em.closed)

    # Wall-clock cutover is far newer than these chart-bucket timestamps.
    r.live_from_ts = 10_000
    r.em.entry("Live", 1, 1)
    r.em.process_bar(Bar(180, 102, 102, 102, 102, 1), 3)
    r.em.close("Live", "live close")
    r.em.process_bar(Bar(240, 103, 103, 103, 103, 1), 4)

    summary = r.summary()
    trades = r.trades()
    assert summary["live_trades"] == 1
    assert summary["live_profit"] == r.em.closed[-1].profit
    assert trades[-2]["live"] is False
    assert trades[-1]["live"] is True
    assert r.em.closed[-1].exit_ts < r.live_from_ts


def test_paper_equity_series_excludes_preconfiguration_samples(configured):
    port, _, _ = configured
    epoch = 10_000.5
    port.started = 9_000.0
    port.equity_epoch = epoch
    with port.journal._lock:
        port.journal.con.execute("INSERT INTO equity VALUES (?,?)", (10_000.49, 111.0))
        port.journal.con.execute("INSERT INTO equity VALUES (?,?)", (10_000.50, 222.0))
        port.journal.con.execute("INSERT INTO equity VALUES (?,?)", (10_000.51, 333.0))
        port.journal.con.commit()
    series = port.status()["equity_series"]
    assert [p["equity"] for p in series] == [222.0, 333.0]


def test_all_primary_intraday_timeframes_are_available_from_one_minute_cache(configured):
    port, r, _ = configured
    r.spec.chart_tf = "20"
    r.chart_minutes = 20
    r.subbars = [(Bar(k * 60, 100 + k / 100, 101 + k / 100, 99 + k / 100, 100.5 + k / 100, 1), 1)
                 for k in range(180)]
    caps = r.chart_capability_view()
    assert tuple(PRIMARY_INTRADAY_TIMEFRAMES) == ("1", "2", "5", "10", "20", "30")
    assert set(PRIMARY_INTRADAY_TIMEFRAMES).issubset(set(caps["available_from_cache"]))
    for tf in PRIMARY_INTRADAY_TIMEFRAMES:
        port.rewarm_asset("TEST", {}, False, chart={"timeframe": tf})
        assert r.spec.chart_tf == tf
        assert r.chart_minutes == int(tf)
        assert r.bars


def test_paper_rewarm_uses_genuine_one_minute_tail_from_mixed_cache(configured):
    port, r, _ = configured
    r.spec.chart_tf = "20"
    r.chart_minutes = 20
    five_minute_old = [(Bar(k * 300, 100, 101, 99, 100, 1), 5) for k in range(3)]
    tail_start = 900
    one_minute_tail = [(Bar(tail_start + k * 60, 110 + k, 111 + k, 109 + k, 110 + k, 1), 1) for k in range(8)]
    r.subbars = five_minute_old + one_minute_tail
    caps = r.chart_capability_view()
    assert "1" in caps["available_from_cache"] and "2" in caps["available_from_cache"]
    assert caps["cached_source_resolutions_minutes"] == [1, 5]
    status_caps = r.summary()["chart_capabilities"]
    assert status_caps["available_from_cache"] == caps["available_from_cache"]
    assert status_caps["cached_source_resolutions_minutes"] == [1, 5]

    port.rewarm_asset("TEST", {}, False, chart={"timeframe": "1"})
    assert r.chart_minutes == 1
    assert r.spec.chart_tf == "1"
    assert len(r.bars) == len(one_minute_tail)


def test_warmup_replay_trades_stay_non_live_until_live_boundary_exists():
    r = make_runner("WARM")
    r.live_from_ts = None
    r.live_closed_start = 0
    r.em.process_bar(Bar(0, 100, 100, 100, 100, 1), 0)
    r.em.entry("Hist", 1, 1)
    r.em.process_bar(Bar(60, 100, 100, 100, 100, 1), 1)
    r.em.close("Hist", "hist close")
    r.em.process_bar(Bar(120, 101, 101, 101, 101, 1), 2)
    assert r.em.closed
    assert r.summary()["live_trades"] == 0
    assert r.summary()["live_profit"] == 0
    assert r.trades()[-1]["live"] is False


def test_engine_http_api_resolves_common_asset_aliases(tmp_path):
    from icarus_engine.assets import resolve
    port = Portfolio(Journal(":memory:"), str(tmp_path))
    spec = resolve("NQ")
    spec.chart_tf = "1"
    spec.commission = 0
    r = AssetRunner(RunnerConfig(spec, Inputs(use_tide=False, use_eod_flat=False)), Journal(":memory:"))
    r._init_strategy(100)
    r.last_price = 100
    r.warm = True
    port.runners["NQ"] = r
    port.order = ["NQ"]
    srv = serve(port, 0, token="test-token", start=False)
    thread = threading.Thread(target=srv.serve_forever, daemon=True)
    thread.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{srv.server_port}/api/inputs/NQ1!", timeout=5) as reply:
            body = json.load(reply)
            assert reply.status == 200 and body["asset"] == "NQ"
        assert body["instrument"] == {
            "kind": "futures",
            "continuous_symbol": "CME_MINI:NQ1!",
            "provider_symbol": "NQ=F",
            "contract_policy": "continuous_only",
        }

        req = urllib.request.Request(
            f"http://127.0.0.1:{srv.server_port}/admin/pause",
            data=json.dumps({"asset": "NQ1!"}).encode(),
            headers={"Authorization": "Bearer test-token", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as reply:
            body = json.load(reply)
            assert reply.status == 200 and body["ok"] is True
        assert r.paused is True
    finally:
        srv.shutdown()
        srv.server_close()
        thread.join(5)
        port.journal.con.close()


def test_portfolio_mutations_accept_continuous_aliases(tmp_path):
    from icarus_engine.assets import resolve
    port = Portfolio(Journal(":memory:"), str(tmp_path))
    spec = resolve("NQ")
    spec.chart_tf = "1"
    spec.commission = 0
    r = AssetRunner(RunnerConfig(spec, Inputs(use_tide=False, use_eod_flat=False)), port.journal)
    r.subbars = [(Bar(k * 60, 100 + k, 101 + k, 99 + k, 100 + k, 1), 1) for k in range(8)]
    r.warm = True
    port.runners["NQ"] = r
    port.order = ["NQ"]

    out = port.rewarm_asset("NQ1!", {"tp1_pts": 80})
    assert out is r and r.inputs_base.tp1_pts == 80
    assert port.remove_asset("NQ1!") is True
    assert "NQ" not in port.runners and "NQ" not in port.order
