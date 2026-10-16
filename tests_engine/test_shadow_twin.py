import json

import pytest

from icarus_engine.emulator import ClosedTrade, Emulator
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


def test_partial_exit_does_not_count_as_a_closed_shadow_episode():
    primary = Emulator(initial_capital=10_000, commission=0, mintick=1, contract_size=1)
    twin = MirroredEmulator(primary)
    twin.process_bar(bar(60, 100, 101, 99, 100), 0,
                     real_bar=bar(60, 100, 101, 99, 100))
    twin.entry("L", 1, 2)
    twin.process_bar(bar(120, 100, 101, 99, 100), 1,
                     real_bar=bar(120, 100, 101, 99, 100))
    twin.exit("half", "L", qty=1, profit=1)
    twin.process_bar(bar(180, 100, 102, 99, 101), 2,
                     real_bar=bar(180, 100, 102, 99, 101))

    partial = twin.summary()
    assert twin.primary.position_size == twin.shadow.position_size == 1
    assert partial["pairable_closed_episodes"] == 0
    assert partial["primary"]["closed_episodes"] == 0
    assert partial["real_price_shadow"]["closed_episodes"] == 0
    assert partial["primary"]["partial_realized_episodes"] == 1
    assert partial["real_price_shadow"]["partial_realized_episodes"] == 1
    assert partial["outcome_agreement_denominator"] == 0

    twin.close("L", "finish")
    twin.process_bar(bar(240, 101, 102, 100, 101), 3,
                     real_bar=bar(240, 101, 102, 100, 101))
    complete = twin.summary()
    assert complete["pairable_closed_episodes"] == 1
    assert complete["primary"]["closed_episodes"] == 1
    assert complete["real_price_shadow"]["closed_episodes"] == 1


def test_closed_episode_excursions_sum_partial_lots_and_compare_real_lane():
    primary = Emulator(initial_capital=10_000, commission=1, mintick=1, contract_size=2)
    twin = MirroredEmulator(primary, asset="TEST")
    twin.process_bar(bar(60, 100, 101, 99, 100), 0,
                     real_bar=bar(60, 100, 101, 99, 100))
    twin.entry("L", 1, 2)
    twin.process_bar(bar(120, 100, 110, 95, 105), 1,
                     real_bar=bar(120, 100, 105, 98, 101))
    twin.exit("half", "L", qty=1, limit=102)
    twin.process_bar(bar(180, 100, 108, 96, 106), 2,
                     real_bar=bar(180, 100, 104, 97, 102))
    twin.close("L", "finish")
    twin.process_bar(bar(240, 103, 104, 100, 103), 3,
                     real_bar=bar(240, 103, 104, 100, 103))

    result = twin.summary()

    assert result["pairable_closed_episodes"] == 1
    assert result["closed_episode_excursion_basis"] == (
        "EMULATOR_OBSERVED_HIGH_LOW_THROUGH_EXIT_FILL_QTY_WEIGHTED_ENTRY_COMMISSION_ADJUSTED"
    )
    assert result["primary_closed_episode_excursions"] == {
        "denominator": 1, "favorable_excursion": 38.0, "adverse_excursion": -22.0,
    }
    assert result["real_price_shadow_closed_episode_excursions"] == {
        "denominator": 1, "favorable_excursion": 18.0, "adverse_excursion": -14.0,
    }
    assert result["matched_closed_episode_favorable_excursion_delta_shadow_minus_primary"] == {
        "count": 1, "mean": -20.0, "median": -20.0, "min": -20.0, "max": -20.0,
    }
    assert result["matched_closed_episode_adverse_excursion_delta_shadow_minus_primary"] == {
        "count": 1, "mean": 8.0, "median": 8.0, "min": 8.0, "max": 8.0,
    }


def test_short_episode_excursions_preserve_signs_and_commissions():
    primary = Emulator(initial_capital=10_000, commission=1, mintick=1, contract_size=2)
    twin = MirroredEmulator(primary, asset="TEST")
    twin.process_bar(bar(60, 100, 101, 99, 100), 0,
                     real_bar=bar(60, 100, 101, 99, 100))
    twin.entry("S", -1, 1)
    twin.process_bar(bar(120, 100, 105, 90, 95), 1,
                     real_bar=bar(120, 100, 110, 95, 105))
    twin.close("S", "finish")
    twin.process_bar(bar(180, 95, 96, 90, 92), 2,
                     real_bar=bar(180, 105, 110, 100, 108))

    result = twin.summary()

    assert result["pairable_closed_episodes"] == 1
    assert result["primary_closed_episode_excursions"]["favorable_excursion"] == 19.0
    assert result["primary_closed_episode_excursions"]["adverse_excursion"] == -11.0
    assert result["real_price_shadow_closed_episode_excursions"]["favorable_excursion"] == 9.0
    assert result["real_price_shadow_closed_episode_excursions"]["adverse_excursion"] == -21.0


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


def test_file_feed_mode_is_reported_as_shadow_price_provenance(monkeypatch):
    monkeypatch.setenv("ICARUS_FEED", "file")
    runner = AssetRunner(
        RunnerConfig(spec=parse_spec("NQ@1"), inputs=Inputs(), shadow_real_fills=True),
        Journal(":memory:"), feeds={"yahoo": object()},
    )

    provenance = runner.summary()["real_price_shadow"]["provenance"]
    assert provenance["price_provider"] == "file_history_hub"
    assert provenance["feed_mode"] == "file"


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


def test_closed_episodes_do_not_pair_without_a_shared_intent_sequence():
    primary = Emulator(initial_capital=10_000, commission=0, mintick=1, contract_size=1)
    twin = MirroredEmulator(primary)
    # Identical display labels and timestamps do not prove causal identity.
    common = {"entry_id": "L", "direction": 1, "qty": 1,
              "entry_price": 100.0, "entry_bar": 1, "entry_ts": 120,
              "exit_bar": 2, "exit_ts": 180, "exit_comment": "close",
              "entry_comment": "same label", "exit_kind": "close",
              "runup": 5.0, "drawdown": -2.0, "bars": 1,
              "lot_id": 1, "entry_qty": 1}
    twin.primary.closed.append(ClosedTrade(exit_price=101.0, profit=1.0, **common))
    twin.shadow.closed.append(ClosedTrade(exit_price=99.0, profit=-1.0, **common))

    result = twin.summary()
    assert result["pairable_closed_episodes"] == 0
    assert result["primary_only_closed_episodes"] == 1
    assert result["shadow_only_closed_episodes"] == 1
    assert result["primary_closed_episode_excursions"]["favorable_excursion"] == 5.0
    assert result["real_price_shadow_closed_episode_excursions"]["adverse_excursion"] == -2.0
    assert result["matched_closed_episode_favorable_excursion_delta_shadow_minus_primary"]["count"] == 0
    assert result["matched_closed_episode_adverse_excursion_delta_shadow_minus_primary"]["count"] == 0


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


def test_closed_episode_excursions_publish_complete_and_matched_dollar_totals():
    primary = Emulator(initial_capital=10_000, commission=2, mintick=1, contract_size=1)
    twin = MirroredEmulator(primary)
    identity = {"entry_id": "L", "direction": 1, "qty": 1,
                "entry_price": 100.0, "entry_bar": 1, "entry_ts": 120,
                "exit_price": 101.0, "exit_bar": 2, "exit_ts": 180,
                "exit_comment": "close", "profit": 1.0, "entry_comment": "",
                "exit_kind": "close", "bars": 1, "lot_id": 1, "entry_qty": 1}
    twin._entry_fill_pairs[7] = {
        "intent_seq": 7,
        "primary": {"entry_id": "L", "ts": 120, "bar": 1, "side": "buy",
                    "qty": 1, "price": 100.0},
        "shadow": {"entry_id": "L", "ts": 120, "bar": 1, "side": "buy",
                   "qty": 1, "price": 100.0},
    }
    primary.closed.append(ClosedTrade(**identity, runup=5.0, drawdown=-2.0))
    twin.shadow.closed.append(ClosedTrade(**identity, runup=8.0, drawdown=-4.0))
    # A partial exit is not a complete episode and must not enter excursion totals.
    primary.closed.append(ClosedTrade(**{**identity, "entry_id": "partial", "qty": 1,
                                        "entry_qty": 2, "lot_id": 2},
                                       runup=100.0, drawdown=-100.0))

    result = twin.summary()

    assert result["primary_closed_episode_excursions"] == {
        "favorable_excursion": 5.0, "adverse_excursion": -2.0, "denominator": 1}
    assert result["real_price_shadow_closed_episode_excursions"] == {
        "favorable_excursion": 8.0, "adverse_excursion": -4.0, "denominator": 1}
    assert result["matched_closed_episode_favorable_excursion_delta_shadow_minus_primary"]["mean"] == 3.0
    assert result["matched_closed_episode_adverse_excursion_delta_shadow_minus_primary"]["mean"] == -2.0


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
            shadow = twin.summary()
            shadow["provenance"] = {"price_provider": "fixture", "timeframe_minutes": 1}
            return {"symbol": "TEST", "equity": 10_000, "capital": 10_000,
                    "live_profit": 0, "open_profit": 0, "position": 0,
                    "paused": False, "warm": True, "last_bar_ts": 180,
                    "real_price_shadow": shadow}

    portfolio = Portfolio(Journal(":memory:"), ".", feeds={})
    portfolio.runners = {"TEST": SummaryOnlyRunner()}
    portfolio.order = ["TEST"]
    from icarus_engine.intelligence_fabric import IntelligenceFabric
    with IntelligenceFabric(":memory:") as fabric:
        assert fabric.query(channel="real_price_shadow") == []
        blocked_clock = portfolio.publish_shadow_evidence(
            fabric, run_id="portfolio-01", received_at="1970-01-01T00:02:00Z")
        assert blocked_clock["status"] == "BLOCKED"
        assert fabric.query(channel="real_price_shadow") == []
        class InvalidSummaryRunner:
            def summary(self, *, nonblocking=False):
                return {"symbol": "BAD", "last_bar_ts": 180,
                        "real_price_shadow": {"schema": "wrong"}}

        portfolio.runners["BAD"] = InvalidSummaryRunner()
        portfolio.order.append("BAD")
        blocked = portfolio.publish_shadow_evidence(
            fabric, run_id="portfolio-01", received_at="1970-01-01T00:04:00Z")
        assert blocked["status"] == "BLOCKED"
        assert blocked["published_count"] == 0
        assert fabric.query(channel="real_price_shadow") == []
        del portfolio.runners["BAD"]
        portfolio.order.remove("BAD")
        publication = portfolio.publish_shadow_evidence(
            fabric, run_id="portfolio-01", received_at="1970-01-01T00:04:00Z")
        repeated = portfolio.publish_shadow_evidence(
            fabric, run_id="portfolio-01", received_at="1970-01-01T00:04:00Z")
        assert publication["status"] == "PUBLISHED"
        assert publication["published_count"] == 1
        assert publication["execution_authorized"] is False
        assert repeated["receipts"][0]["idempotent"] is True
        assert len(fabric.query(channel="real_price_shadow", assets=["TEST"])) == 1
        result = portfolio.status()["real_price_shadow"]
        assert result["outcome_matrix"]["win"]["loss"] == 1
        assert "drawdown_aggregation" in result
        assert result["net_realization_ratio"] == -1
        assert result["paired_profit_capture"] == -1
        assert result["drawdown_aggregation"].startswith("per_asset_only")
        assert "max_drawdown" not in result
        assert len(fabric.query(channel="real_price_shadow", assets=["TEST"])) == 1

        class DegradedSummaryRunner:
            def summary(self, *, nonblocking=False):
                shadow = twin.summary()
                shadow["status"] = "DEGRADED"
                shadow["reason"] = "missing real-price bar"
                return {"symbol": "TEST", "equity": 10_000, "capital": 10_000,
                        "live_profit": 0, "open_profit": 0, "position": 0,
                        "paused": False, "warm": True, "last_bar_ts": 180,
                        "real_price_shadow": shadow}

        portfolio.runners["TEST"] = DegradedSummaryRunner()
        degraded = portfolio.status()["real_price_shadow"]
        assert degraded["status"] == "DEGRADED"
        assert degraded["metrics_available"] is False
        assert "every evidenced asset to be READY" in degraded["metrics_unavailable_reason"]
        assert degraded["primary_net"] is None
        assert degraded["real_price_shadow_net"] is None
        assert degraded["outcome_matrix"] is None
        assert degraded["pairable_closed_episodes"] is None
        assert degraded["assets"][0]["reason"] == "missing real-price bar"
        assert degraded["assets"][0]["administrative_censored_shadow_positions"] is None
        public_asset = portfolio.status()["assets"][0]["real_price_shadow"]
        assert public_asset["metrics_available"] is False
        assert public_asset["primary"] is None
        assert public_asset["real_price_shadow"] is None
        assert public_asset["primary_only_entry_fills"] is None
        assert public_asset["shadow_only_entry_fills"] is None
        assert public_asset["matched_entry_intents"] is None
        assert public_asset["outcome_matrix"] is None
        assert public_asset["primary_bar_close_max_drawdown"] is None
        assert public_asset["real_price_shadow_bar_close_max_drawdown"] is None
        assert public_asset["open_primary"] is None
        assert public_asset["open_shadow"] is None
        assert public_asset["recent_intents"] is None
        assert public_asset["reason"] == "missing real-price bar"


def test_admin_pause_cancels_shadow_only_pending_limit_order():
    spec = parse_spec("NQ@1")
    runner = AssetRunner(
        RunnerConfig(spec=spec, inputs=Inputs(), mintick=1, shadow_real_fills=True),
        Journal(":memory:"), feeds={},
    )
    twin = runner.em
    twin.process_bar(bar(60, 110, 112, 108, 110), 0,
                     real_bar=bar(60, 110, 112, 108, 110))
    twin.entry("L", 1, 1, limit=105)
    twin.process_bar(bar(120, 110, 112, 104, 106), 1,
                     real_bar=bar(120, 110, 112, 106, 108))
    assert twin.primary.position_size == 1
    assert twin.shadow.position_size == 0
    assert [p.id for p in twin.shadow._pending_entries] == ["L"]

    # This is the runtime's pause/flatten cancellation path. The primary has no
    # pending ID left, but the research lane still has a working limit order.
    runner._cancel_pending_entries()
    twin.process_bar(bar(180, 110, 112, 109, 111), 2,
                     real_bar=bar(180, 110, 112, 104, 106))

    assert twin.primary.position_size == 1
    assert twin.shadow.position_size == 0
    assert twin.shadow._pending_entries == []


def test_portfolio_pairable_closed_count_includes_break_even_episode():
    primary = Emulator(initial_capital=10_000, commission=0, mintick=1, contract_size=1)
    twin = MirroredEmulator(primary, asset="TEST")
    twin.process_bar(bar(60, 100, 101, 99, 100), 0,
                     real_bar=bar(60, 100, 101, 99, 100))
    twin.entry("L", 1, 1)
    twin.process_bar(bar(120, 100, 101, 99, 100), 1,
                     real_bar=bar(120, 100, 101, 99, 100))
    twin.close("L")
    twin.process_bar(bar(180, 100, 100, 100, 100), 2,
                     real_bar=bar(180, 100, 100, 100, 100))
    per_asset = twin.summary()

    class SummaryOnlyRunner:
        def summary(self, *, nonblocking=False):
            return {"symbol": "TEST", "equity": 10_000, "capital": 10_000,
                    "live_profit": 0, "open_profit": 0, "position": 0,
                    "paused": False, "warm": True, "last_bar_ts": 180,
                    "real_price_shadow": per_asset}

    portfolio = Portfolio(Journal(":memory:"), ".", feeds={})
    portfolio.runners = {"TEST": SummaryOnlyRunner()}
    portfolio.order = ["TEST"]
    aggregate = portfolio.status()["real_price_shadow"]

    assert per_asset["pairable_closed_episodes"] == 1
    assert per_asset["outcome_agreement_denominator"] == 0
    assert aggregate["pairable_closed_episodes"] == 1
    assert aggregate["outcome_agreement_denominator"] == 0
    assert aggregate["outcome_agreement_rate"] is None
    assert aggregate["administrative_censored_shadow_positions"] == 0


def test_flatten_closes_shadow_only_position():
    spec = parse_spec("NQ@1")
    runner = AssetRunner(RunnerConfig(spec=spec, inputs=Inputs(), mintick=0.25,
                                      shadow_real_fills=True), Journal(":memory:"), feeds={})
    twin = runner.em
    twin.process_bar(bar(60, 110, 112, 106, 110), 0,
                     real_bar=bar(60, 110, 112, 104, 110))
    twin.entry("L", 1, 1, limit=105)
    twin.process_bar(bar(120, 110, 112, 106, 110), 1,
                     real_bar=bar(120, 110, 112, 104, 110))
    assert twin.primary.position_size == 0
    assert twin.shadow.position_size == 1
    runner.last_price = 125  # admin mark differs from the last observed real bar
    before = twin.summary()
    before_shadow_fills = len(twin.shadow.fills)
    before_bar_observations = before["bar_close_equity_observations"]

    assert runner.flatten("test") == 1
    assert twin.shadow.open == []
    assert twin.shadow.closed == []
    assert len(twin.shadow.fills) == before_shadow_fills
    assert twin.status == "READY"
    after = twin.summary()
    assert after["real_price_shadow"]["closed_episodes"] == before["real_price_shadow"]["closed_episodes"] == 0
    assert after["real_price_shadow"]["net"] == before["real_price_shadow"]["net"] == 0
    assert after["primary"]["closed_episodes"] == before["primary"]["closed_episodes"] == 0
    assert after["primary"]["net"] == before["primary"]["net"] == 0
    assert after["excluded_admin_flatten_lot_trade_pieces"] == {"primary": 0, "shadow": 0}
    assert after["pairable_closed_episodes"] == before["pairable_closed_episodes"] == 0
    assert after["bar_close_equity_observations"] == before_bar_observations
    assert after["administrative_censored_shadow_positions"] == 1
    assert after["recent_administrative_censors"][-1]["shadow_market_outcome_recorded"] is False


def test_flatten_closes_primary_but_censors_paired_shadow_position():
    spec = parse_spec("NQ@1")
    runner = AssetRunner(RunnerConfig(spec=spec, inputs=Inputs(), mintick=0.25,
                                      shadow_real_fills=True), Journal(":memory:"), feeds={})
    twin = runner.em
    twin.process_bar(bar(60, 110, 112, 104, 110), 0,
                     real_bar=bar(60, 110, 112, 104, 110))
    twin.entry("L", 1, 1, limit=105)
    twin.process_bar(bar(120, 110, 112, 104, 110), 1,
                     real_bar=bar(120, 110, 112, 104, 110))
    assert twin.primary.position_size == 1
    assert twin.shadow.position_size == 1
    runner.last_price = 125
    before = twin.summary()
    before_shadow_fills = len(twin.shadow.fills)

    assert runner.flatten("paired") == 1

    assert twin.primary.position_size == 0
    assert twin.primary.closed[-1].exit_comment == "FLAT_PAIRED"
    assert twin.primary.closed[-1].exit_price == 125
    assert twin.shadow.open == []
    assert twin.shadow.closed == []
    assert len(twin.shadow.fills) == before_shadow_fills
    after = twin.summary()
    assert after["pairable_closed_episodes"] == before["pairable_closed_episodes"] == 0
    assert after["outcome_agreement_denominator"] == before["outcome_agreement_denominator"] == 0
    assert after["real_price_shadow"]["closed_episodes"] == before["real_price_shadow"]["closed_episodes"] == 0
    assert after["real_price_shadow"]["net"] == before["real_price_shadow"]["net"] == 0
    assert after["primary"]["closed_episodes"] == before["primary"]["closed_episodes"] == 0
    assert after["primary"]["net"] == before["primary"]["net"] == 0
    assert after["excluded_admin_flatten_lot_trade_pieces"] == {"primary": 1, "shadow": 0}
    assert after["bar_close_equity_observations"] == before["bar_close_equity_observations"]
    assert after["administrative_censored_shadow_positions"] == 1


def test_flatten_without_market_mark_does_not_leave_queued_primary_close_or_censor_shadow():
    spec = parse_spec("NQ@1")
    runner = AssetRunner(RunnerConfig(spec=spec, inputs=Inputs(), mintick=0.25,
                                      shadow_real_fills=True), Journal(":memory:"), feeds={})
    twin = runner.em
    twin.process_bar(bar(60, 110, 112, 104, 110), 0,
                     real_bar=bar(60, 110, 112, 104, 110))
    twin.entry("L", 1, 1, limit=105)
    twin.process_bar(bar(120, 110, 112, 104, 110), 1,
                     real_bar=bar(120, 110, 112, 104, 110))
    assert twin.primary.position_size == twin.shadow.position_size == 1
    runner.last_price = None

    with pytest.raises(RuntimeError, match="no finite last market price"):
        runner.flatten("no-mark")

    assert twin.primary.position_size == twin.shadow.position_size == 1
    assert twin.primary._pending_closes == []
    assert twin._administrative_censored_positions == 0


def test_shadow_only_flatten_without_market_mark_censors_without_synthetic_close():
    spec = parse_spec("NQ@1")
    runner = AssetRunner(RunnerConfig(spec=spec, inputs=Inputs(), mintick=0.25,
                                      shadow_real_fills=True), Journal(":memory:"), feeds={})
    twin = runner.em
    twin.process_bar(bar(60, 110, 112, 106, 110), 0,
                     real_bar=bar(60, 110, 112, 104, 110))
    twin.entry("L", 1, 1, limit=105)
    twin.process_bar(bar(120, 110, 112, 106, 110), 1,
                     real_bar=bar(120, 110, 112, 104, 110))
    assert twin.primary.position_size == 0 and twin.shadow.position_size == 1
    runner.last_price = None

    assert runner.flatten("shadow-only") == 1

    assert twin.primary.position_size == 0
    assert twin.shadow.open == [] and twin.shadow.closed == []
    assert twin._administrative_censored_positions == 1
    assert twin._administrative_censor_events[-1]["bar_ts"] is None


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
    assert summary["provenance"]["instrument_id"] == on.symbol
    assert summary["provenance"]["provider_symbol"] == on.spec.ticker
    assert summary["provenance"]["primary_fill_basis"] == "chart"
    assert summary["provenance"]["shadow_fill_basis"] == "standard_real_ohlc"


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
