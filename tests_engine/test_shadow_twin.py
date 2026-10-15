import json

from icarus_engine.emulator import Emulator
from icarus_engine.assets import parse_spec
from icarus_engine.pine.timeframe import Bar
from icarus_engine.runtime import AssetRunner, Journal, Portfolio, RunnerConfig
from icarus_engine.shadow_twin import MirroredEmulator
from icarus_engine.strategy.inputs import Inputs


def bar(ts, o, h, l, c):
    return Bar(ts, o, h, l, c, 10.0)


def test_mirrors_orders_but_primary_reads_and_fills_remain_canonical():
    primary = Emulator(initial_capital=10_000, commission=0, mintick=1, contract_size=1)
    twin = MirroredEmulator(primary, asset="TEST")
    twin.process_bar(bar(60, 100, 101, 99, 100), 0,
                     real_bar=bar(60, 100, 101, 99, 100))
    twin.entry("L", 1, 1, comment="same-intent")

    # The strategy-facing primary bar is deliberately different from market OHLC.
    twin.process_bar(bar(120, 110, 112, 109, 111), 1,
                     real_bar=bar(120, 100, 103, 99, 102))

    assert twin.open is primary.open
    assert primary.fills[-1].price == 110
    assert twin.shadow.fills[-1].price == 100
    assert twin.intents[-1]["method"] == "entry"
    assert twin.intents[-1]["execution_authorized"] is False
    summary = twin.summary()
    assert summary["execution_authorized"] is False
    assert summary["entry_fill_parity"] == 1
    assert summary["matched_entry_intents"] == 1
    assert summary["entry_price_delta_points_shadow_minus_primary"]["mean"] == -10


def test_limit_fill_on_only_one_lane_counts_as_unmatched_entry_intent():
    primary = Emulator(initial_capital=10_000, commission=0, mintick=1, contract_size=1)
    twin = MirroredEmulator(primary)
    twin.process_bar(bar(60, 110, 112, 108, 110), 0,
                     real_bar=bar(60, 110, 112, 108, 110))
    twin.entry("L", 1, 1, limit=105)
    twin.process_bar(bar(120, 110, 112, 104, 106), 1,
                     real_bar=bar(120, 110, 112, 106, 108))
    summary = twin.summary()
    assert primary.position_size == 1
    assert twin.shadow.position_size == 0
    assert summary["primary_only_entry_fills"] == 1
    assert summary["shadow_only_entry_fills"] == 0
    assert summary["entry_fill_parity"] == 0


def test_relative_exit_uses_each_emulators_own_entry_basis():
    primary = Emulator(initial_capital=10_000, commission=0, mintick=1, contract_size=1)
    twin = MirroredEmulator(primary)
    twin.process_bar(bar(60, 100, 101, 99, 100), 0,
                     real_bar=bar(60, 100, 101, 99, 100))
    twin.entry("L", 1, 1)
    twin.process_bar(bar(120, 110, 111, 109, 110), 1,
                     real_bar=bar(120, 100, 101, 99, 100))
    twin.exit("L-tp", "L", profit=5)
    twin.process_bar(bar(180, 112, 116, 111, 115), 2,
                     real_bar=bar(180, 102, 106, 101, 105))
    assert primary.closed[-1].exit_price == 115
    assert twin.shadow.closed[-1].exit_price == 105
    assert primary.closed[-1].profit == twin.shadow.closed[-1].profit


def test_missing_or_mismatched_real_bar_degrades_without_changing_primary():
    primary = Emulator(initial_capital=10_000, commission=0, mintick=1, contract_size=1)
    twin = MirroredEmulator(primary)
    twin.process_bar(bar(60, 100, 101, 99, 100), 0, real_bar=bar(60, 100, 101, 99, 100))
    twin.entry("L", 1, 1)
    twin.process_bar(bar(120, 110, 112, 109, 111), 1, real_bar=None)
    assert primary.position_size == 1
    assert primary.fills[-1].price == 110
    assert twin.shadow.position_size == 0
    assert twin.status == "DEGRADED"
    assert "missing" in twin.reason

    invalid_primary = Emulator(initial_capital=10_000, commission=0, mintick=1)
    invalid = MirroredEmulator(invalid_primary)
    invalid.process_bar(bar(60, 100, 101, 99, 100), 0, real_bar=bar(60, 100, 101, 99, 100))
    invalid.process_bar(bar(120, 100, 101, 99, 100), 1, real_bar=bar(119, 100, 101, 99, 100))
    assert invalid.status == "INVALID"
    assert invalid_primary.last_bar.ts == 120


def test_unmatched_closed_episodes_are_counted_and_mutator_inventory_is_explicit():
    assert MirroredEmulator.mutator_contract() == frozenset({"entry", "exit", "close", "cancel"})
    public_methods = {name for name, value in Emulator.__dict__.items()
                      if not name.startswith("_") and callable(value)}
    assert public_methods == {
        "entry", "exit", "close", "cancel", "process_bar", "qty_open",
        "open_profit", "equity", "round_tick", "live_exits", "pending_view", "open_trades_view",
    }
    primary = Emulator(initial_capital=10_000, commission=0, mintick=1, contract_size=1)
    twin = MirroredEmulator(primary)
    twin.process_bar(bar(60, 100, 101, 99, 100), 0,
                     real_bar=bar(60, 100, 101, 99, 100))
    twin.entry("L", 1, 1)
    twin.process_bar(bar(120, 100, 101, 99, 100), 1,
                     real_bar=bar(120, 100, 101, 99, 100))
    twin.close("L", "flat")
    twin.process_bar(bar(180, 101, 102, 100, 101), 2,
                     real_bar=bar(180, 101, 102, 100, 101))
    result = twin.summary()
    assert result["pairable_closed_episodes"] == 1
    assert result["primary_only_closed_episodes"] == 0
    assert result["shadow_only_closed_episodes"] == 0
    assert result["outcome_agreement_rate"] == 1


def test_break_even_results_are_separate_from_directional_agreement():
    primary = Emulator(initial_capital=10_000, commission=0, mintick=1, contract_size=1)
    twin = MirroredEmulator(primary)
    twin.process_bar(bar(60, 100, 101, 99, 100), 0,
                     real_bar=bar(60, 100, 101, 99, 100))
    twin.entry("L", 1, 1)
    twin.process_bar(bar(120, 100, 101, 99, 100), 1,
                     real_bar=bar(120, 100, 101, 99, 100))
    twin.close("L")
    twin.process_bar(bar(180, 100, 100, 100, 100), 2,
                     real_bar=bar(180, 100, 100, 100, 100))
    result = twin.summary()
    assert result["pairable_closed_episodes"] == 1
    assert result["primary_break_even_episodes"] == 1
    assert result["shadow_break_even_episodes"] == 1
    assert result["outcome_agreement_denominator"] == 0
    assert result["outcome_agreement_rate"] is None


def test_shadow_reports_outcome_matrix_realization_live_boundary_and_close_drawdown():
    primary = Emulator(initial_capital=10_000, commission=0, mintick=1, contract_size=1)
    twin = MirroredEmulator(primary)
    twin.process_bar(bar(60, 100, 101, 99, 100), 0,
                     real_bar=bar(60, 100, 101, 99, 100))
    twin.entry("L", 1, 1)
    twin.process_bar(bar(120, 100, 102, 99, 101), 1,
                     real_bar=bar(120, 100, 102, 99, 101))
    twin.close("L", "paired exit")
    twin.process_bar(bar(180, 101, 102, 100, 101), 2,
                     real_bar=bar(180, 99, 100, 98, 99))

    result = twin.summary(live_from_ts=180)
    assert result["outcome_matrix"]["win"]["loss"] == 1
    assert result["outcome_matrix"]["win"]["win"] == 0
    assert result["net_realization_ratio"] == -1
    assert result["paired_profit_capture"] == -1
    # The episode belongs to its entry period even though it closes at go-live.
    assert result["primary"]["warmup_net"] == 1
    assert result["primary"]["live_net"] == 0
    assert result["bar_close_equity_observations"] == 3
    assert result["bar_close_drawdown_basis"] == "BAR_CLOSE_MARKED_EQUITY_NOT_INTRABAR"
    assert result["real_price_shadow_bar_close_max_drawdown"] == 2


def test_realization_ratios_withhold_nonpositive_primary_denominators():
    primary = Emulator(initial_capital=10_000, commission=0, mintick=1, contract_size=1)
    twin = MirroredEmulator(primary)
    twin.process_bar(bar(60, 100, 101, 99, 100), 0,
                     real_bar=bar(60, 100, 101, 99, 100))
    result = twin.summary()
    assert result["net_realization_ratio"] is None
    assert result["net_realization_ratio_unavailable_reason"]
    assert result["paired_profit_capture"] is None
    assert result["paired_profit_capture_unavailable_reason"]


def test_portfolio_shadow_view_aggregates_counts_and_ratios_without_faking_drawdown():
    primary = Emulator(initial_capital=10_000, commission=0, mintick=1, contract_size=1)
    twin = MirroredEmulator(primary, asset="TEST")
    twin.process_bar(bar(60, 100, 101, 99, 100), 0,
                     real_bar=bar(60, 100, 101, 99, 100))
    twin.entry("L", 1, 1)
    twin.process_bar(bar(120, 100, 102, 99, 101), 1,
                     real_bar=bar(120, 100, 102, 99, 101))
    twin.close("L")
    twin.process_bar(bar(180, 101, 102, 100, 101), 2,
                     real_bar=bar(180, 99, 100, 98, 99))

    class SummaryOnlyRunner:
        def summary(self, *, nonblocking=False):
            return {"symbol": "TEST", "equity": 10_000, "capital": 10_000,
                    "live_profit": 0, "open_profit": 0, "position": 0,
                    "paused": False, "warm": True, "real_price_shadow": twin.summary()}

    portfolio = Portfolio(Journal(":memory:"), ".", feeds={})
    portfolio.runners = {"TEST": SummaryOnlyRunner()}
    portfolio.order = ["TEST"]
    result = portfolio.status()["real_price_shadow"]
    assert result["outcome_matrix"]["win"]["loss"] == 1
    assert result["net_realization_ratio"] == -1
    assert result["paired_profit_capture"] == -1
    assert result["drawdown_aggregation"].startswith("per_asset_only")
    assert "max_drawdown" not in result


def test_runner_feature_is_default_off_and_runtime_passes_standard_bar():
    spec = parse_spec("NQ@1")
    spec.chart_type = "heikin_ashi"
    spec.fill_on = "chart"
    off = AssetRunner(RunnerConfig(spec=spec, inputs=Inputs(), mintick=0.25), Journal(":memory:"), feeds={})
    assert isinstance(off.em, Emulator)
    assert not isinstance(off.em, MirroredEmulator)

    on = AssetRunner(RunnerConfig(spec=spec, inputs=Inputs(), mintick=0.25,
                                  shadow_real_fills=True), Journal(":memory:"), feeds={})
    real = bar(1_800_000_000, 100, 104, 98, 102)
    on._on_chart_bar(real, live=False)
    assert isinstance(on.em, MirroredEmulator)
    assert on.em.shadow.last_bar.ts == real.ts
    summary = on._summary()["real_price_shadow"]
    assert summary["fill_basis"] == "STANDARD_REAL_BAR_EMULATOR"
    assert summary["execution_authorized"] is False


def test_runtime_replay_keeps_primary_strategy_state_and_emulator_identical():
    spec_off = parse_spec("NQ@1")
    spec_off.chart_type = "heikin_ashi"
    spec_off.fill_on = "chart"
    spec_on = parse_spec("NQ@1")
    spec_on.chart_type = "heikin_ashi"
    spec_on.fill_on = "chart"
    standard = AssetRunner(RunnerConfig(spec=spec_off, inputs=Inputs(), mintick=0.25),
                           Journal(":memory:"), feeds={})
    shadowed = AssetRunner(RunnerConfig(spec=spec_on, inputs=Inputs(), mintick=0.25,
                                        shadow_real_fills=True), Journal(":memory:"), feeds={})
    px = 18_000.0
    for i in range(320):
        step = (i % 17) - 8
        px += step * 0.25
        real = bar(1_800_000_000 + i * 60, px - 0.5, px + 1.0, px - 1.0, px)
        standard._on_chart_bar(real, live=False)
        shadowed._on_chart_bar(real, live=False)
    primary = shadowed.em.primary
    assert standard.em.fills == primary.fills
    assert standard.em.closed == primary.closed
    assert standard.em.pending_view() == primary.pending_view()
    assert standard.em.position_size == primary.position_size
    assert standard.em.netprofit == primary.netprofit
    assert json.dumps(standard.state, sort_keys=True, allow_nan=True) == json.dumps(shadowed.state, sort_keys=True, allow_nan=True)
