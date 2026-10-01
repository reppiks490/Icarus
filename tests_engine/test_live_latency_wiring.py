from __future__ import annotations

from types import SimpleNamespace

from icarus_engine.pine.timeframe import Bar
from icarus_engine.runtime import AssetRunner


class _Telemetry:
    def __init__(self, fail=False):
        self.fail = fail
        self.samples = []

    def observe_ns(self, stage, elapsed_ns):
        if self.fail:
            raise RuntimeError("telemetry sink failure")
        self.samples.append((stage, elapsed_ns))


class _Journal:
    def __init__(self):
        self.rows = []

    def log(self, level, msg):
        self.rows.append((level, msg))

    def add_fill(self, *args, **kwargs):
        return None

    def add_trade(self, *args, **kwargs):
        return None


class _Emulator:
    def __init__(self):
        self.fills = []
        self.closed = []

    def process_bar(self, bar, index):
        return None


class _Chain:
    def htf_values(self, ts):
        return {}

    def ltf_values(self, ts, chart_minutes, t_close):
        return {}


class _Calendar:
    def bucket_end(self, ts, minutes):
        return int(ts) + int(minutes) * 60


class _Strategy:
    def __init__(self):
        self.paused = False
        self.events = []

    def on_bar(self, chart, bar_index, htf, ltf, *, time_close):
        return {
            "rate_st_line": chart.c,
            "rate_uptrend": True,
            "tp1_price": chart.c + 1,
            "tp2_price": chart.c + 2,
            "sl_price": chart.c - 1,
            "vwap": chart.c,
            "kf_level": chart.c,
            "rate_qty_open": 0,
            "rate_pos_long": True,
            "tide_hi": chart.h,
            "tide_lo": chart.l,
            "pulse_l": 0.25,
            "pulse_s": 0.10,
        }


def _runner(telemetry):
    r = object.__new__(AssetRunner)
    r.latency_telemetry = telemetry
    r.strat = _Strategy()
    r.ha = None
    r.inputs_base = SimpleNamespace(use_real_ohlc=False)
    r.spec = SimpleNamespace(security_source="standard", fill_on="real")
    r._real_ohlc_warned = False
    r.journal = _Journal()
    r.symbol = "NQ"
    r.bar_index = -1
    r.paused = False
    r.em = _Emulator()
    r.chains = {2: _Chain(), 5: _Chain()}
    r.htf_tfs = []
    r.chart_mode = "minutes"
    r.chart_minutes = 1
    r.chart_value = 1
    r.cal = _Calendar()
    r.state = {}
    r.bars = []
    r.overlays = []
    r.last_bar_wall = 0.0
    r.recent_fills = []
    r._fills_seen = 0
    r.rewarming = False
    r._closed_seen = 0
    r.recent_events = []
    return r


def test_live_chart_bar_records_shadow_decision_latency():
    telemetry = _Telemetry()
    runner = _runner(telemetry)
    runner._on_chart_bar(Bar(1000, 10.0, 11.0, 9.0, 10.5, 100.0), live=True)
    assert len(telemetry.samples) == 1
    stage, elapsed_ns = telemetry.samples[0]
    assert stage == "shadow_decision_total"
    assert isinstance(elapsed_ns, int)
    assert elapsed_ns >= 0


def test_warmup_or_replay_bar_never_contaminates_live_latency():
    telemetry = _Telemetry()
    runner = _runner(telemetry)
    runner._on_chart_bar(Bar(1000, 10.0, 11.0, 9.0, 10.5, 100.0), live=False)
    assert telemetry.samples == []


def test_telemetry_failure_cannot_break_live_decision_path():
    runner = _runner(_Telemetry(fail=True))
    runner._on_chart_bar(Bar(1000, 10.0, 11.0, 9.0, 10.5, 100.0), live=True)
    assert runner.state["rate_uptrend"] is True
    assert len(runner.bars) == 1
