"""Phase 19: causal synthetic paper-execution and challenger evaluation.

Deliberately contains NO broker adapter, market feed, model download,
network call, dynamic code, scheduling, order-routing credentials or API.
All prices are generated from seeded toy paths, NOT a market-data source.
Accounting is integer tick/cent based; fills are hypothetical and do not
model order queues, missed fills, funding, margin or exchange entitlements.
"""
from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from .contracts import canonical_bytes, identity

AUTHORITY = {"research_only": True, "execution_authorized": False,
             "production_decision_authorized": False, "auto_promote": False}
_SCHEMA = "icarus-omnigenesis-paper-execution-v1"
_ARENA = "icarus-omnigenesis-paper-arena-v1"
_STRATEGY = {"kind", "fast", "slow", "direction"}
_EXECUTION = {"contracts", "tick_value_cents", "fee_per_contract_cents",
              "slippage_ticks", "latency_bars"}
_RISK = {"initial_cash_cents", "max_loss_cents", "max_drawdown_cents",
         "max_order_events"}
_SEED_MAX = (1 << 32) - 1


def _int(value: Any, key: str, lo: int, hi: int) -> int:
    if type(value) is not int or not lo <= value <= hi:
        raise ValueError(f"{key} must be an integer in [{lo}, {hi}]")
    return value


def _strategy(value: Any) -> dict:
    if not isinstance(value, Mapping) or set(value) != _STRATEGY:
        raise ValueError("invalid strategy contract")
    if value["kind"] != "SMA_CROSS":
        raise ValueError("only fixed SMA_CROSS is permitted")
    fast = _int(value["fast"], "fast", 2, 30)
    slow = _int(value["slow"], "slow", 4, 80)
    if fast >= slow:
        raise ValueError("fast must precede slow")
    if value["direction"] not in ("trend", "reversion"):
        raise ValueError("invalid strategy direction")
    return {"kind": "SMA_CROSS", "fast": fast, "slow": slow,
            "direction": value["direction"]}


def _execution(value: Any) -> dict:
    if not isinstance(value, Mapping) or set(value) != _EXECUTION:
        raise ValueError("invalid execution contract")
    return {
        "contracts": _int(value["contracts"], "contracts", 1, 5),
        "tick_value_cents": _int(value["tick_value_cents"], "tick_value_cents", 1, 100_000),
        "fee_per_contract_cents": _int(value["fee_per_contract_cents"], "fees", 0, 10_000),
        "slippage_ticks": _int(value["slippage_ticks"], "slippage_ticks", 1, 100),
        "latency_bars": _int(value["latency_bars"], "latency_bars", 1, 10),
    }


def _risk(value: Any) -> dict:
    if not isinstance(value, Mapping) or set(value) != _RISK:
        raise ValueError("invalid risk contract")
    cash = _int(value["initial_cash_cents"], "initial_cash_cents", 10_000, 10**12)
    loss = _int(value["max_loss_cents"], "max_loss_cents", 1, cash)
    dd = _int(value["max_drawdown_cents"], "max_drawdown_cents", 1, cash)
    return {"initial_cash_cents": cash, "max_loss_cents": loss,
            "max_drawdown_cents": dd,
            "max_order_events": _int(value["max_order_events"], "max_order_events", 1, 1000)}


def _config(spec: Mapping[str, Any]) -> dict:
    if not isinstance(spec, Mapping) or set(spec) != {
            "schema_version", "seed", "bars", "strategy", "execution", "risk"}:
        raise ValueError("invalid paper-execution schema")
    if spec["schema_version"] != _SCHEMA:
        raise ValueError("unsupported paper-execution version")
    seed = _int(spec["seed"], "seed", 0, _SEED_MAX)
    bars = _int(spec["bars"], "bars", 100, 2048)
    cfg = {"schema_version": _SCHEMA, "seed": seed, "bars": bars,
           "strategy": _strategy(spec["strategy"]),
           "execution": _execution(spec["execution"]),
           "risk": _risk(spec["risk"])}
    if len(canonical_bytes(cfg)) > 10_000:
        raise ValueError("paper spec exceeds limit")
    return cfg


def _synthetic_bars(seed: int, steps: int) -> list[dict]:
    rng = random.Random(seed)
    price = 10000
    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    path = []
    for i in range(steps):
        # Trending and countertrending regimes; intentionally toy non-market law.
        drift = (2 if (i // 80) % 2 == 0 else -2)
        delta = rng.randint(-11, 11) + drift
        opened = price
        price = max(150, opened + delta)
        high = max(opened, price) + rng.randint(0, 5)
        low = max(1, min(opened, price) - rng.randint(0, 5))
        path.append({"bar_id": f"synthetic-{i:05d}",
                     "observed_at": (t + timedelta(minutes=i)).isoformat(),
                     "open_ticks": opened, "high_ticks": high,
                     "low_ticks": low, "close_ticks": price})
    return path


def _simulate(path: list[dict], strategy: dict, execution: dict,
              risk: dict) -> dict:
    """Causal close(i) decision => strictly later open(j) fill. No API side effects."""
    fast, slow = strategy["fast"], strategy["slow"]
    qty, tick = execution["contracts"], execution["tick_value_cents"]
    fee, slip, latency = (execution["fee_per_contract_cents"],
                          execution["slippage_ticks"],
                          execution["latency_bars"])
    cash = risk["initial_cash_cents"]
    highwater = cash
    min_equity = cash
    pos = 0
    entry = 0
    filled_orders = 0
    rejected_signals = 0
    delayed_signals = []
    fills = []
    decisions = []
    closed = [p["close_ticks"] for p in path]
    halted = False
    halt_reason = None
    halt_at = None
    gross_fees = 0
    max_drawdown = 0

    def fill(index: int, price: int, target: int, reason: str,
             source_index: int | None) -> None:
        nonlocal cash, pos, entry, filled_orders, gross_fees
        if pos == target:
            return
        if not -qty <= target <= qty or target not in (-qty, 0, qty):
            raise AssertionError("invalid research target")
        diff = target - pos
        side = "BUY" if diff > 0 else "SELL"
        actual = price + slip if diff > 0 else price - slip
        if actual <= 0:
            raise ValueError("adverse slippage exhausted positive tick price")
        n = abs(diff)
        cost = n * fee
        cash -= cost
        gross_fees += cost
        if pos and (target == 0 or pos * target <= 0):
            cash += abs(pos) * (actual - entry) * tick * (1 if pos > 0 else -1)
        if target and (pos == 0 or pos * target <= 0):
            entry = actual
        if not target:
            entry = 0
        pos = target
        filled_orders += 1
        fills.append({"bar_index": index, "bar_id": path[index]["bar_id"],
                      "source_close_bar_index": source_index,
                      "side": side, "contracts": n, "price_ticks": actual,
                      "fee_cents": cost, "reason": reason})
        if source_index is not None and not source_index < index:
            raise AssertionError("lookahead fill impossible")

    for i, row in enumerate(path):
        # Process orders only after signals from PREVIOUS closes. When a risk
        # kill was latched, exit at THIS open; never pretend to exit on a prior
        # close that was only learned after the bar ended.
        if halt_at is not None and pos:
            fill(i, row["open_ticks"], 0, "RISK_KILL_NEXT_OPEN", None)
        if not halted:
            eligible = [x for x in delayed_signals if x[0] <= i]
            delayed_signals = [x for x in delayed_signals if x[0] > i]
            if eligible:
                rejected_signals += len(eligible) - 1
                _, source_index, target = eligible[-1]
                if target != pos:
                    if filled_orders >= risk["max_order_events"]:
                        halted = True
                        halt_reason = "ORDER_EVENT_CAP"
                        halt_at = i
                        if pos:
                            fill(i, row["open_ticks"], 0, "RISK_KILL_EVENT_CAP", None)
                    else:
                        fill(i, row["open_ticks"], target, "CAUSAL_SMA_SIGNAL",
                             source_index)
        unrealized = pos * (row["close_ticks"] - entry) * tick
        equity = cash + unrealized
        min_equity = min(min_equity, equity)
        highwater = max(highwater, equity)
        max_drawdown = max(max_drawdown, highwater - equity)
        if not halted:
            if equity <= risk["initial_cash_cents"] - risk["max_loss_cents"]:
                halted, halt_reason, halt_at = True, "MAX_LOSS_CLOSE_MARK", i
            elif highwater - equity >= risk["max_drawdown_cents"]:
                halted, halt_reason, halt_at = True, "MAX_DRAWDOWN_CLOSE_MARK", i
        # Form signal from fully observed close ONLY; schedule on a later open.
        if not halted and i + 1 >= slow:
            fast_sum = sum(closed[i - fast + 1: i + 1])
            slow_sum = sum(closed[i - slow + 1: i + 1])
            direction = (1 if fast_sum * slow > slow_sum * fast else
                         -1 if fast_sum * slow < slow_sum * fast else 0)
            if strategy["direction"] == "reversion":
                direction = -direction
            target = qty * direction
            if not decisions or decisions[-1]["target"] != target:
                decisions.append({"decision_bar_index": i,
                                  "decision_at": row["observed_at"], "target": target})
                if i + latency < len(path):
                    delayed_signals.append((i + latency, i, target))
    if pos:
        # Forced research settlement at final close, with adverse slippage.
        # No evidence of a real order at that quote is implied.
        fill(len(path) - 1, path[-1]["close_ticks"], 0,
             "SYNTHETIC_FINAL_SETTLEMENT", None)
    ending = cash
    return {"start_cash_cents": risk["initial_cash_cents"],
            "end_cash_cents": ending,
            "net_pnl_cents": ending - risk["initial_cash_cents"],
            "net_return_basis_points": ((ending - risk["initial_cash_cents"]) * 10000 //
                                        risk["initial_cash_cents"]),
            "gross_fees_cents": gross_fees,
            "max_mark_to_market_drawdown_cents": max_drawdown,
            "minimum_marked_equity_cents": min_equity,
            "halt_reason": halt_reason, "halt_at_bar": halt_at,
            "forced_flat_at_end": True, "final_position_contracts": pos,
            "fill_count": len(fills), "decision_count": len(decisions),
            "stale_signal_count": rejected_signals, "fills": fills,
            "decisions": decisions}


def run_paper_execution(spec: Mapping[str, Any]) -> dict:
    cfg = _config(spec)
    path = _synthetic_bars(cfg["seed"], cfg["bars"])
    simulation = _simulate(path, cfg["strategy"], cfg["execution"], cfg["risk"])
    receipt = {
        "schema_version": _SCHEMA, "evidence_kind": "SYNTHETIC_PAPER_EXECUTION",
        "authority": dict(AUTHORITY), "source_authenticity_verified": False,
        "exchange_execution_verified": False, "profitability_verified": False,
        "strategy_promoted": False, "broker_order_count": 0,
        "scenario_id": identity({"seed": cfg["seed"], "bars": path}),
        "configuration": cfg,
        "event_hash": identity({"decisions": simulation.pop("decisions"),
                                "fills": simulation.pop("fills")}),
        "results": simulation,
        "limitations": {
            "market_data": "DETERMINISTIC_SYNTHETIC_GENERATOR",
            "liquidity_model": "IDEALIZED_NEXT_OPEN_WITH_FIXED_ADVERSE_SLIPPAGE",
            "risk_limit_guaranteed": False,
            "bar_close_as_of_only": True,
            "observed_fills": False,
        },
    }
    receipt["receipt_id"] = identity(receipt)
    return receipt


def tournament_paper_strategies(spec: Mapping[str, Any]) -> dict:
    """Select on synthetic calibration data; test only the chosen contender.

    Important: holdout is reproducible, not access-controlled or one-time
    cryptographically sealed. External independently collected OOD data
    remains a blocker to claims of predictive edge or approved models.
    """
    if not isinstance(spec, Mapping) or set(spec) != {
            "schema_version", "seed", "bars", "candidates", "execution", "risk"}:
        raise ValueError("invalid tournament schema")
    if spec["schema_version"] != _ARENA:
        raise ValueError("unsupported tournament version")
    seed = _int(spec["seed"], "seed", 0, _SEED_MAX)
    bars = _int(spec["bars"], "bars", 160, 2048)
    candidates = spec["candidates"]
    if not isinstance(candidates, list) or not 2 <= len(candidates) <= 8:
        raise ValueError("tournament needs 2–8 preregistered contenders")
    strategies = [_strategy(x) for x in candidates]
    if len({identity(x) for x in strategies}) != len(strategies):
        raise ValueError("duplicate challenger")
    exe, risk = _execution(spec["execution"]), _risk(spec["risk"])
    if len(canonical_bytes(spec)) > 40_000:
        raise ValueError("tournament spec exceeds byte cap")
    path = _synthetic_bars(seed, bars)
    split = (bars * 7) // 10
    training, test = path[:split], path[split:]
    ranks = []
    for strategy in strategies:
        run = _simulate(training, strategy, exe, risk)
        # Max drawdown penalizes a nominally profitable but fragile path.
        objective = run["net_pnl_cents"] - run["max_mark_to_market_drawdown_cents"]
        ranks.append({"strategy": strategy, "train_net_pnl_cents": run["net_pnl_cents"],
                      "train_drawdown_cents": run["max_mark_to_market_drawdown_cents"],
                      "train_objective_cents": objective,
                      "train_halted": run["halt_reason"] is not None})
    # Deterministic tie-breaker, no random reranking or holdout peeking.
    ranked = sorted(ranks, key=lambda x: (-x["train_objective_cents"],
                                          identity(x["strategy"])))
    champion = ranked[0]["strategy"]
    out = _simulate(test, champion, exe, risk)
    summary = {
        "schema_version": _ARENA, "evidence_kind": "SYNTHETIC_CHALLENGER_TOURNAMENT",
        "authority": dict(AUTHORITY), "strategy_promoted": False,
        "production_qualified": False, "profitability_verified": False,
        "test_access_controlled": False, "real_market_holdout": False,
        "split_bar_index": split, "calibration_bar_count": len(training),
        "holdout_bar_count": len(test), "candidate_count": len(strategies),
        "scenario_id": identity({"seed": seed, "bars": path}),
        "predeclared_contenders": strategies,
        "training_rankings": ranked,
        "chosen_on_training_only": champion,
        "chosen_holdout_net_pnl_cents": out["net_pnl_cents"],
        "chosen_holdout_drawdown_cents": out["max_mark_to_market_drawdown_cents"],
        "chosen_holdout_halt_reason": out["halt_reason"],
        "chosen_holdout_fill_count": out["fill_count"],
        "heldout_details_sealed": False,
        "broker_order_count": 0,
        "independent_scientific_approval_required": True,
        "risk_limits_not_guaranteed_against_gaps": True,
    }
    summary["receipt_id"] = identity(summary)
    return summary
