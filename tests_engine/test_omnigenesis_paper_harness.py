"""Adversarial, causal, synthetic-only paper-execution assurance.

This module deliberately does not call external services or market APIs.
It never establishes real fill performance, market edge or live safety.
"""
from copy import deepcopy
import json

import pytest

from icarus_engine.omnigenesis.contracts import identity
from icarus_engine.omnigenesis.paper_harness import (
    _simulate, _synthetic_bars, run_paper_execution, tournament_paper_strategies
)
import icarus_engine.omnigenesis.paper_harness as mod


def config(seed=7, bars=300):
    return {
        "schema_version": "icarus-omnigenesis-paper-execution-v1",
        "seed": seed, "bars": bars,
        "strategy": {"kind": "SMA_CROSS", "fast": 3, "slow": 12,
                     "direction": "trend"},
        "execution": {"contracts": 2, "tick_value_cents": 125,
                      "fee_per_contract_cents": 250, "slippage_ticks": 2,
                      "latency_bars": 1},
        "risk": {"initial_cash_cents": 20_000_000, "max_loss_cents": 10_000_000,
                 "max_drawdown_cents": 10_000_000, "max_order_events": 150},
    }


def arena(seed=7):
    x = config(seed=seed, bars=420)
    return {
        "schema_version": "icarus-omnigenesis-paper-arena-v1",
        "seed": x["seed"], "bars": x["bars"],
        "candidates": [
            {"kind": "SMA_CROSS", "fast": 3, "slow": 12, "direction": "trend"},
            {"kind": "SMA_CROSS", "fast": 4, "slow": 20, "direction": "trend"},
            {"kind": "SMA_CROSS", "fast": 3, "slow": 12, "direction": "reversion"},
        ],
        "execution": x["execution"], "risk": x["risk"],
    }


def test_paper_result_reproducible_truth_and_no_order_routing():
    p = run_paper_execution(config())
    assert p == run_paper_execution(config())
    assert p["receipt_id"] == identity({k: v for k, v in p.items()
                                        if k != "receipt_id"})
    assert p["evidence_kind"] == "SYNTHETIC_PAPER_EXECUTION"
    assert p["authority"]["execution_authorized"] is False
    assert p["authority"]["auto_promote"] is False
    assert p["source_authenticity_verified"] is False
    assert p["exchange_execution_verified"] is False
    assert p["profitability_verified"] is False
    assert p["strategy_promoted"] is False
    assert p["broker_order_count"] == 0
    assert p["results"]["final_position_contracts"] == 0
    assert p["results"]["forced_flat_at_end"] is True
    assert p["results"]["end_cash_cents"] == (
        p["results"]["start_cash_cents"] + p["results"]["net_pnl_cents"])


def test_decisions_only_access_the_close_then_execute_on_later_open():
    cfg = config()
    path = _synthetic_bars(cfg["seed"], cfg["bars"])
    run = _simulate(path, cfg["strategy"], cfg["execution"], cfg["risk"])
    assert run["fill_count"] > 0
    assert run["decision_count"] > 0
    assert any(f["reason"] == "CAUSAL_SMA_SIGNAL" for f in run["fills"])
    for fill in run["fills"]:
        source = fill["source_close_bar_index"]
        if source is not None:
            assert source < fill["bar_index"]
            assert fill["bar_index"] - source >= cfg["execution"]["latency_bars"]
            assert fill["reason"] == "CAUSAL_SMA_SIGNAL"
    for dec in run["decisions"]:
        i = dec["decision_bar_index"]
        assert dec["decision_at"] == path[i]["observed_at"]
        assert i >= cfg["strategy"]["slow"] - 1
    assert run["fill_count"] <= cfg["risk"]["max_order_events"] + 1


def test_higher_execution_friction_never_looks_like_better_fills_in_same_path():
    a = config()
    b = deepcopy(a)
    b["execution"]["slippage_ticks"] = 8
    b["execution"]["fee_per_contract_cents"] = 700
    cheap = run_paper_execution(a)["results"]
    expensive = run_paper_execution(b)["results"]
    assert cheap["fill_count"] == expensive["fill_count"]
    assert expensive["gross_fees_cents"] > cheap["gross_fees_cents"]
    assert expensive["net_pnl_cents"] < cheap["net_pnl_cents"]


def test_risk_kill_flattens_next_open_and_blocks_new_signals():
    x = config(seed=19)
    x["risk"]["max_loss_cents"] = 1
    x["risk"]["max_drawdown_cents"] = 1
    path = _synthetic_bars(x["seed"], x["bars"])
    report = _simulate(path, x["strategy"], x["execution"], x["risk"])
    assert report["halt_reason"] in {"MAX_LOSS_CLOSE_MARK", "MAX_DRAWDOWN_CLOSE_MARK"}
    assert report["final_position_contracts"] == 0
    halt_index = report["halt_at_bar"]
    assert halt_index is not None
    assert all(f["reason"] != "CAUSAL_SMA_SIGNAL" or f["bar_index"] <= halt_index
               for f in report["fills"])
    assert not any(d["decision_bar_index"] > halt_index for d in report["decisions"])
    assert report["max_mark_to_market_drawdown_cents"] >= 0


def test_fill_event_budget_triggers_safe_halt_with_no_broker_order():
    x = config(seed=4)
    x["risk"]["max_order_events"] = 1
    result = run_paper_execution(x)
    assert result["results"]["fill_count"] <= 2
    assert result["broker_order_count"] == 0
    assert result["results"]["final_position_contracts"] == 0
    assert result["results"]["halt_reason"] == "ORDER_EVENT_CAP"


def test_tournament_preregisters_contenders_and_only_scores_chosen_on_holdout():
    x = arena()
    report = tournament_paper_strategies(x)
    assert report == tournament_paper_strategies(x)
    assert report["receipt_id"] == identity({
        k: v for k, v in report.items() if k != "receipt_id"
    })
    assert report["candidate_count"] == 3
    assert len(report["training_rankings"]) == 3
    assert report["calibration_bar_count"] + report["holdout_bar_count"] == 420
    assert report["chosen_on_training_only"] == report["training_rankings"][0]["strategy"]
    assert report["evidence_kind"] == "SYNTHETIC_CHALLENGER_TOURNAMENT"
    assert report["test_access_controlled"] is False
    assert report["real_market_holdout"] is False
    assert report["strategy_promoted"] is False
    assert report["profitability_verified"] is False
    assert report["production_qualified"] is False
    assert report["broker_order_count"] == 0
    assert report["authority"]["production_decision_authorized"] is False
    bars = _synthetic_bars(x["seed"], x["bars"])
    test = _simulate(bars[report["split_bar_index"] :],
                     report["chosen_on_training_only"], x["execution"], x["risk"])
    assert report["chosen_holdout_net_pnl_cents"] == test["net_pnl_cents"]
    assert report["chosen_holdout_drawdown_cents"] == test["max_mark_to_market_drawdown_cents"]


def test_post_split_data_mutations_cannot_change_training_ranks(monkeypatch):
    x = arena(seed=99)
    base = tournament_paper_strategies(x)
    generate = mod._synthetic_bars
    def mutated(seed, bars):
        original = generate(seed, bars)
        split = bars * 7 // 10
        for i in range(split, bars):
            # Completely change synthetic post-split prices, without making
            # the train sample, opening price or OHLC invalid.
            opened = original[i]["open_ticks"]
            close = opened + 500 if i % 2 else max(1, opened - 200)
            original[i]["close_ticks"] = close
            original[i]["high_ticks"] = max(opened, close) + 20
            original[i]["low_ticks"] = max(1, min(opened, close) - 20)
        return original
    monkeypatch.setattr(mod, "_synthetic_bars", mutated)
    altered = tournament_paper_strategies(x)
    assert altered["training_rankings"] == base["training_rankings"]
    assert altered["chosen_on_training_only"] == base["chosen_on_training_only"]
    assert altered["chosen_holdout_net_pnl_cents"] != base["chosen_holdout_net_pnl_cents"]


@pytest.mark.parametrize("field,value,pattern", [
    ("seed", True, "seed"),
    ("bars", 99, "bars"),
    ("bars", 3000, "bars"),
    ("schema_version", "icarus-live-orders-v1", "version"),
])
def test_invalid_paper_configuration_refused(field, value, pattern):
    x = config()
    x[field] = value
    with pytest.raises(ValueError, match=pattern):
        run_paper_execution(x)


@pytest.mark.parametrize("key,value,pattern", [
    ("contracts", 6, "contracts"),
    ("latency_bars", 0, "latency_bars"),
    ("fee_per_contract_cents", -1, "fees"),
    ("slippage_ticks", 0, "slippage_ticks"),
    ("tick_value_cents", True, "tick_value_cents"),
])
def test_unsafe_execution_parameters_refused(key, value, pattern):
    x = config()
    x["execution"][key] = value
    with pytest.raises(ValueError, match=pattern):
        run_paper_execution(x)


def test_strategy_injection_and_schema_expansion_refused():
    x = config()
    x["strategy"]["kind"] = "LIVE_BROKER_ORDER"
    with pytest.raises(ValueError, match="only fixed SMA"):
        run_paper_execution(x)
    x = config()
    x["strategy"]["shell"] = "curl example.com"
    with pytest.raises(ValueError, match="strategy contract"):
        run_paper_execution(x)
    x = config()
    x["execution"]["broker_api_key"] = "must-not-be-accepted"
    with pytest.raises(ValueError, match="execution contract"):
        run_paper_execution(x)


def test_risk_config_requires_positive_kill_limits_and_valid_cap():
    x = config()
    x["risk"]["max_drawdown_cents"] = 0
    with pytest.raises(ValueError, match="max_drawdown_cents"):
        run_paper_execution(x)
    x = config()
    x["risk"]["max_loss_cents"] = x["risk"]["initial_cash_cents"] + 1
    with pytest.raises(ValueError, match="max_loss_cents"):
        run_paper_execution(x)


def test_duplicate_contender_or_nonfinite_input_rejected():
    x = arena()
    x["candidates"] = [x["candidates"][0], deepcopy(x["candidates"][0])]
    with pytest.raises(ValueError, match="duplicate challenger"):
        tournament_paper_strategies(x)
    x = arena()
    x["execution"]["fee_per_contract_cents"] = float("nan")
    with pytest.raises(ValueError, match="fees"):
        tournament_paper_strategies(x)


def test_multi_seed_receipts_are_deterministic_and_end_flat():
    for seed in range(15):
        x = config(seed=seed, bars=120 + seed)
        result = run_paper_execution(x)
        assert result["receipt_id"] == run_paper_execution(x)["receipt_id"]
        assert result["results"]["final_position_contracts"] == 0
        assert result["results"]["start_cash_cents"] + result["results"]["net_pnl_cents"] == result["results"]["end_cash_cents"]
        assert result["results"]["fill_count"] >= 1


def test_final_exit_fees_are_included_in_minimum_equity_and_drawdown():
    # Monotonically rising toy prices deliberately sustain a long position
    # until forced final research settlement. Large deterministic commissions
    # ensure settlement equity is lower than any earlier marked equity.
    path = [{
        "bar_id": f"handcrafted_{i}",
        "observed_at": f"2026-01-01T00:{i:02d}:00+00:00",
        "open_ticks": 10000 + i,
        "high_ticks": 10002 + i,
        "low_ticks": 9999 + i,
        "close_ticks": 10001 + i,
    } for i in range(30)]
    strategy = {"kind": "SMA_CROSS", "fast": 2, "slow": 4,
                "direction": "trend"}
    execution = {"contracts": 1, "tick_value_cents": 10,
                 "fee_per_contract_cents": 1000, "slippage_ticks": 1,
                 "latency_bars": 1}
    risk = {"initial_cash_cents": 1_000_000, "max_loss_cents": 100_000,
            "max_drawdown_cents": 100_000, "max_order_events": 20}
    run = _simulate(path, strategy, execution, risk)
    assert run["fill_count"] == 2
    assert run["final_position_contracts"] == 0
    assert run["start_cash_cents"] > run["end_cash_cents"]
    assert run["minimum_marked_equity_cents"] == run["end_cash_cents"]
    assert run["max_mark_to_market_drawdown_cents"] >= (
        run["start_cash_cents"] - run["end_cash_cents"])
    assert run["gross_fees_cents"] == 2000
    assert run["fills"][-1]["reason"] == "SYNTHETIC_FINAL_SETTLEMENT"
