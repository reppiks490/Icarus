"""CA: derive operator metrics from bounded, real-fill engine replay tapes.

This authenticates internal replay structure, not exchange execution or an
untouched final holdout. No result from this module authorizes a trade.
The operator's numeric gates are pinned. Date classification intentionally
uses the IANA America/New_York database rather than the source metrics.py
hardcoded 2024-2026 DST table; this changes historical overnight counts for
other years and is reported as a versioned metric-definition correction.
"""
from __future__ import annotations

import hashlib
import json
import math
import statistics
from collections import defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo

from .assess import assess_trade_metrics
from icarus_engine.calendar import get_calendar
from icarus_engine.pine.timeframe import tf_minutes
from icarus_engine.strategy.inputs import Inputs


_ET = ZoneInfo("America/New_York")
_SAME_SOURCE = ("source_config_sha256", "subbars_sha256", "deep_sha256")
_SAME_CONDITIONS = ("asset", "fill_on", "chart_type", "tf", "session", "point_value",
                    "commission", "slippage_ticks", "capital", "pts_scale")


def _digest(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _number(value, name, *, positive=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name}: finite number required")
    if positive and value <= 0:
        raise ValueError(f"{name}: positive number required")
    return float(value)


def _integer(value, name, *, positive=False):
    if type(value) is not int or (positive and value <= 0):
        raise ValueError(f"{name}: {'positive ' if positive else ''}integer required")
    return value


def _pct(count, total):
    return 100.0 * count / total if total else 0.0


def _runs(flags):
    wins, losses = [], []
    previous = None
    for value in flags:
        target = wins if value else losses
        if target and value == previous:
            target[-1] += 1
        else:
            target.append(1)
        previous = value
    return wins, losses


def _quantile(sorted_values, q):
    return float(sorted_values[min(int(q * len(sorted_values)), len(sorted_values) - 1)])


def _date_et(ts):
    return datetime.fromtimestamp(ts, _ET).date()


def _check_replay(result):
    if not isinstance(result, dict):
        raise ValueError("replay result dictionary required")
    cfg = result.get("config")
    if not isinstance(cfg, dict) or cfg.get("fill_on") != "real":
        raise ValueError("real-price fills required")
    boundary = cfg.get("window_boundary")
    if (cfg.get("window_boundary_clean") is not True or not isinstance(boundary, dict)
            or any(type(boundary.get(key)) is not int or boundary[key] != 0
                   for key in ("open_lots", "pending_entries", "pending_closes", "pending_exits"))):
        raise ValueError("scored window inherited a position/order or has no boundary evidence")
    if cfg.get("historical_scale_asof_valid") is not True:
        raise ValueError("point scale was not known at the scored window")
    start = _integer(cfg.get("window_start"), "window_start", positive=True)
    end = _integer(cfg.get("window_end"), "window_end", positive=True)
    if end <= start:
        raise ValueError("scored window must have positive duration")
    tf = _integer(cfg.get("tf"), "tf", positive=True)
    point_value = _number(cfg.get("point_value"), "point_value", positive=True)
    commission = _number(cfg.get("commission"), "commission")
    if commission < 0:
        raise ValueError("commission cannot be negative")
    if _integer(cfg.get("slippage_ticks"), "slippage_ticks") < 0:
        raise ValueError("slippage cannot be negative")
    rep = cfg.get("reproducibility")
    if not isinstance(rep, dict):
        raise ValueError("replay provenance missing")
    for name in ("source_config", "effective_config"):
        if not isinstance(rep.get(name), dict) or rep.get(name + "_sha256") != _digest(rep[name]):
            raise ValueError(f"{name} digest mismatch")
    source, effective = rep["source_config"], rep["effective_config"]
    spec = effective.get("spec")
    if not isinstance(spec, dict) or not isinstance(source.get("spec"), dict):
        raise ValueError("source/effective asset specs missing")
    if not isinstance(source.get("base_inputs"), dict) or not isinstance(effective.get("base_inputs"), dict):
        raise ValueError("source/effective input snapshots missing")
    patch = cfg.get("overrides")
    if not isinstance(patch, dict) or effective["base_inputs"] != {**source["base_inputs"], **patch}:
        raise ValueError("candidate patch differs from replayed inputs")
    if source["spec"].get("symbol") != result.get("asset") or spec.get("symbol") != result.get("asset"):
        raise ValueError("source asset identity mismatch")
    if not isinstance(spec.get("chart_tf"), str) or tf_minutes(spec["chart_tf"]) != tf or spec.get("multiplier") != point_value:
        raise ValueError("asset timeframe or point value differs from scoring configuration")
    resolved_session = spec.get("session") if spec.get("calendar") == "cme" else "eth"
    if cfg.get("session") != resolved_session:
        raise ValueError("resolved calendar session differs from scoring configuration")
    for name in ("window_start", "window_end", "pts_scale", "leverage"):
        if effective.get(name) != cfg.get(name):
            raise ValueError(f"effective replay {name} mismatch")
    for name in ("chart_type", "fill_on", "commission", "slippage_ticks", "capital"):
        if effective.get("spec", {}).get(name) != cfg.get(name):
            raise ValueError(f"effective replay {name} mismatch")
    if source.get("pts_scale") != cfg.get("pts_scale") or effective.get("pts_scale") != cfg.get("pts_scale"):
        raise ValueError("point scale differs across replay snapshots")
    if effective.get("mintick") != source.get("mintick"):
        raise ValueError("effective tick size differs from frozen source")
    runner_cfg = source.get("runner_config")
    if not isinstance(runner_cfg, dict):
        raise ValueError("source runner configuration missing")
    literal = runner_cfg.get("pts_ref_price") == 0 and cfg.get("pts_scale") == 1.0
    known_at = rep.get("scale_known_at")
    if runner_cfg.get("scale_known_at") != known_at:
        raise ValueError("source and replay point-scale receipt timestamps disagree")
    if known_at is not None and (type(known_at) is not int or known_at <= 0 or known_at > start):
        raise ValueError("point scale receipt timestamp is after scored window start")
    if (not literal and (type(known_at) is not int or known_at <= 0 or known_at > start)):
        raise ValueError("point scale was not known at scored window start")
    if rep.get("historical_scale_asof_valid") is not True:
        raise ValueError("scale provenance contradicts validity flag")
    expected_inputs = dict(effective["base_inputs"])
    if runner_cfg.get("pts_ref_price", 0) > 0 or runner_cfg.get("fixed_pts_scale") is not None:
        scale = _number(cfg.get("pts_scale"), "pts_scale", positive=True)
        if abs(scale - 1.0) > 1e-6:
            for name in ("tp1_pts", "tp2_pts", "sl_pts"):
                expected_inputs[name] *= scale
            expected_inputs["be_offset_pts"] = max(effective["mintick"], expected_inputs["be_offset_pts"] * scale)
    if expected_inputs.get("point_value") == Inputs().point_value and expected_inputs["point_value"] != point_value:
        expected_inputs["point_value"] = point_value
    if effective.get("effective_inputs") != expected_inputs:
        raise ValueError("scaled effective inputs differ from replayed input snapshot")
    for name in ("subbars_sha256", "deep_sha256"):
        value = rep.get(name)
        if not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ValueError(f"{name} missing")
    stamps = rep.get("chart_bar_times")
    if (not isinstance(stamps, list) or not stamps
            or rep.get("chart_bar_times_sha256") != _digest(stamps)):
        raise ValueError("chart-bar timestamp evidence missing or mismatched")
    calendar = get_calendar(spec.get("calendar"), spec.get("anchor_et"),
                            session=resolved_session, group=spec.get("group", "equity"))
    previous_idx, previous_ts, previous_end = -1, -1, None
    for item in stamps:
        if (not isinstance(item, list) or len(item) != 2
                or type(item[0]) is not int or type(item[1]) is not int
                or item[0] != previous_idx + 1 or item[1] <= previous_ts):
            raise ValueError("chart-bar timestamp sequence is invalid")
        bar_ts = item[1]
        if not calendar.intraday_open(bar_ts) or calendar.bucket_start(bar_ts, tf) != bar_ts:
            raise ValueError("chart-bar timestamp is outside its calendar bucket")
        bar_end = calendar.bucket_end(bar_ts, tf)
        if bar_end <= bar_ts:
            raise ValueError("chart-bar bucket has no duration")
        if previous_end is not None and bar_ts != previous_end:
            next_open = calendar.next_open(previous_end)
            if next_open != bar_ts:
                raise ValueError("chart-bar timestamp sequence has an unexplained gap")
        previous_idx, previous_ts = item
        previous_end = bar_end
    dates = result.get("range")
    if not isinstance(dates, dict) or type(dates.get("start")) is not int or type(dates.get("end")) is not int:
        raise ValueError("replay bar range missing")
    scored = [ts for _, ts in stamps if start <= ts and calendar.bucket_end(ts, tf) <= end]
    if not scored or dates["start"] != scored[0] or dates["end"] != calendar.bucket_end(scored[-1], tf):
        raise ValueError("declared replay range differs from recorded chart bars")
    if dates["start"] > start + tf * 60 or dates["end"] < end - tf * 60:
        raise ValueError("replay does not cover the complete requested window")
    if not isinstance(result.get("trades"), list):
        raise ValueError("replay trade rows missing")
    summary = result.get("summary")
    if not isinstance(summary, dict):
        raise ValueError("replay summary missing")
    if any(not isinstance(summary.get(name), dict) for name in ("open_trades", "open_pnl", "net_profit", "total_trades")):
        raise ValueError("replay summary counts missing")
    if (summary["open_trades"].get("all") != 0
            or summary["open_pnl"].get("all") != 0):
        raise ValueError("scored window has an unfinished position")
    return cfg, rep, start, end, tf, point_value, commission, {idx: ts for idx, ts in stamps}


def metrics_from_replay(result):
    """Compute position-level metrics from a completed native backtest result.

    The emulator lot ID, rather than entry timestamp or Pine label, joins
    partial exits. A censored lot or a row inconsistent with its fill math
    makes the whole scored window ineligible for qualification.
    """
    cfg, _, start, end, _, point_value, commission, stamps = _check_replay(result)
    groups = defaultdict(list)
    trade_numbers = set()
    for row in result["trades"]:
        if not isinstance(row, dict) or row.get("open") is not False:
            raise ValueError("open or malformed trade inside scored window")
        no = _integer(row.get("no"), "trade number", positive=True)
        lot = _integer(row.get("lot_id"), "lot_id", positive=True)
        qty = _integer(row.get("qty"), "qty", positive=True)
        entry_qty = _integer(row.get("entry_qty"), "entry_qty", positive=True)
        entry_ts = _integer(row.get("entry_ts"), "entry_ts", positive=True)
        exit_ts = _integer(row.get("exit_ts"), "exit_ts", positive=True)
        bars = _integer(row.get("bars"), "bars")
        entry_bar = _integer(row.get("entry_bar"), "entry_bar")
        exit_bar = _integer(row.get("exit_bar"), "exit_bar")
        if no in trade_numbers or not start <= entry_ts <= exit_ts <= end or bars < 0:
            raise ValueError("duplicate trade number or trade outside its scored window")
        if (entry_bar < 0 or exit_bar < entry_bar or exit_bar - entry_bar != bars
                or stamps.get(entry_bar) != entry_ts or stamps.get(exit_bar) != exit_ts):
            raise ValueError("trade bar duration contradicts its timestamps or indices")
        trade_numbers.add(no)
        direction = 1 if row.get("type") == "long" else -1 if row.get("type") == "short" else 0
        if not direction or not isinstance(row.get("entry_signal"), str) or not isinstance(row.get("exit_signal"), str):
            raise ValueError("trade direction or signal missing")
        entry = _number(row.get("entry_px"), "entry_px", positive=True)
        exit_px = _number(row.get("exit_px"), "exit_px", positive=True)
        pnl = _number(row.get("pnl"), "pnl")
        fees = _number(row.get("commission"), "trade commission")
        expected_fees = 2.0 * commission * qty
        expected_pnl = direction * (exit_px - entry) * qty * point_value - expected_fees
        if not math.isclose(fees, expected_fees, abs_tol=0.0001) or not math.isclose(pnl, expected_pnl, abs_tol=0.001):
            raise ValueError("trade fill/PnL/commission arithmetic mismatch")
        groups[lot].append(row)

    positions = []
    for lot, legs in groups.items():
        legs.sort(key=lambda r: (r["exit_ts"], r["no"]))
        first = legs[0]
        if len(legs) > 2 or any((leg["entry_ts"], leg["entry_px"], leg["type"], leg["entry_signal"])
                                 != (first["entry_ts"], first["entry_px"], first["type"], first["entry_signal"])
                                 for leg in legs):
            raise ValueError("lot identity is inconsistent or has unsupported exit structure")
        if any(leg["entry_qty"] != first["entry_qty"] for leg in legs) or sum(leg["qty"] for leg in legs) != first["entry_qty"]:
            raise ValueError("entry lot is not completely accounted for")
        positions.append({"lot_id": lot, "entry_ts": first["entry_ts"],
                          "exit_ts": max(leg["exit_ts"] for leg in legs),
                          "bars": max(leg["bars"] for leg in legs),
                          "pnl": sum(leg["pnl"] for leg in legs), "legs": legs})
    positions.sort(key=lambda p: (p["entry_ts"], p["lot_id"]))
    profits = [p["pnl"] for p in positions]
    net = sum(profits)
    summary = result["summary"]
    reported_net = summary.get("net_profit", {}).get("all")
    if not isinstance(reported_net, (int, float)) or not math.isclose(net, reported_net, abs_tol=0.01):
        raise ValueError("trade tape does not reconcile with replay summary")
    if summary.get("total_trades", {}).get("all") != len(result["trades"]):
        raise ValueError("trade tape count does not reconcile with replay summary")
    n = len(positions)
    wins = [p for p in positions if p["pnl"] > 0]
    losers = [p for p in positions if p["pnl"] < 0]
    holds = [p["bars"] for p in positions]
    mean_hold = statistics.fmean(holds) if holds else 0.0
    blocks = [profits[i:i + 25] for i in range(0, n, 25)]
    block_means = [statistics.fmean(b) for b in blocks if len(b) >= 8]
    block_mean = statistics.fmean(block_means) if block_means else 0.0
    consistency = (max(0.0, 1.0 - statistics.pstdev(block_means) / abs(block_mean))
                   if len(block_means) > 1 and block_mean else 0.0)
    win_runs, loss_runs = _runs([p["pnl"] > 0 for p in positions])
    loss_p = (n - len(wins)) / n if n else 0.0
    expected_streak = (math.log(n * (1 - loss_p)) / -math.log(loss_p)
                       if 0 < loss_p < 1 and n * (1 - loss_p) > 0 else 0.0)
    runners = [p["legs"][1] for p in positions if len(p["legs"]) == 2]
    tp1 = sum(p["legs"][0]["exit_signal"].endswith("TP1") for p in positions)
    tp2 = sum(len(p["legs"]) == 2 and p["legs"][1]["exit_signal"].endswith("TP2") for p in positions)
    tp1_rate, tp2_rate = _pct(tp1, n), _pct(tp2, n)
    crossed = [p for p in positions if _date_et(p["entry_ts"]) != _date_et(p["exit_ts"])]
    first_half = statistics.fmean(holds[:n // 2]) if n >= 4 else 0.0
    second_half = statistics.fmean(holds[n // 2:]) if n >= 4 else 0.0
    ordered_holds = sorted(holds)
    expectancy = net / n if n else 0.0
    overnight_net = sum(p["pnl"] for p in crossed)
    return {
        "trades": n, "win_rate": _pct(len(wins), n), "expectancy": expectancy,
        "trades_per_day": n / ((end - start) / 86400), "mean_hold": mean_hold,
        "consistency": consistency, "positive_block_rate": _pct(sum(x > 0 for x in block_means), len(block_means)),
        "top_decile_share": (100.0 * sum(sorted(profits, reverse=True)[:max(1, n // 10)]) / net) if n and net > 0 else 0.0,
        "streak_vs_random": max(loss_runs, default=0) / max(expected_streak, 1e-9) if expected_streak else 0.0,
        "streak_ratio": max(win_runs, default=0) / max(max(loss_runs, default=0), 1),
        "mean_run_ratio": ((statistics.fmean(win_runs) / max(statistics.fmean(loss_runs) if loss_runs else 0.0, 1e-9))
                           if win_runs else 0.0),
        "runner_legs": len(runners), "runner_win_rate": _pct(sum(r["pnl"] > 0 for r in runners), len(runners)),
        "tp1_rate": tp1_rate, "tp2_rate": tp2_rate, "tp_gap_pp": abs(tp1_rate - tp2_rate),
        "hold_p90": _quantile(ordered_holds, 0.90) if ordered_holds else 0.0,
        "same_bar_rate": _pct(sum(h == 0 for h in holds), n),
        "hold_asymmetry": ((statistics.fmean([p["bars"] for p in wins]) /
                            statistics.fmean([p["bars"] for p in losers]))
                           if wins and losers and statistics.fmean([p["bars"] for p in losers]) else 0.0),
        "hold_drift": abs(first_half - second_half) / mean_hold if n >= 4 and mean_hold else 0.0,
        "r_per_bar": expectancy / mean_hold if mean_hold else 0.0,
        "overnight_rate": _pct(len(crossed), n),
        "overnight_net_share": 100.0 * overnight_net / net if net else 0.0,
    }


def assess_replay_pair(tune, hold, *, chart_family="clock_minutes", expected_chart_type="heikin_ashi"):
    """Apply pinned thresholds to two disjoint, internally consistent replays.

    Even a pass is not a qualified candidate: neither exchange-tape parity nor
    an independently protected, never-inspected final holdout is proved here.
    """
    base = {"candidate_qualified": False, "execution_authorized": False,
            "trade_tape_verified": False, "engine_replay_checked": False,
            "replay_structure_checked": False}
    try:
        tune_cfg, tune_rep, ts, te, tune_tf, _, _, _ = _check_replay(tune)
        hold_cfg, hold_rep, hs, he, hold_tf, _, _, _ = _check_replay(hold)
        if te >= hs or tune_tf != hold_tf:
            raise ValueError("tune and hold windows must be strictly ordered and disjoint")
        if tune.get("asset") != hold.get("asset"):
            raise ValueError("asset mismatch")
        if tune_cfg.get("chart_type") != expected_chart_type or hold_cfg.get("chart_type") != expected_chart_type:
            raise ValueError("chart type differs from the required strategy chart")
        for name in _SAME_SOURCE:
            if tune_rep[name] != hold_rep[name]:
                raise ValueError(f"paired replay source differs: {name}")
        for name in _SAME_CONDITIONS:
            left = tune.get("asset") if name == "asset" else tune_cfg.get(name)
            right = hold.get("asset") if name == "asset" else hold_cfg.get(name)
            if left != right:
                raise ValueError(f"paired replay condition differs: {name}")
        if tune_cfg.get("overrides") != hold_cfg.get("overrides"):
            raise ValueError("candidate input patch differs between windows")
        tune_effective = dict(tune_rep["effective_config"])
        hold_effective = dict(hold_rep["effective_config"])
        for snapshot in (tune_effective, hold_effective):
            snapshot.pop("window_start", None)
            snapshot.pop("window_end", None)
        if tune_effective != hold_effective:
            raise ValueError("effective replay configuration differs between windows")
        tm = metrics_from_replay(tune)
        hm = metrics_from_replay(hold)
        tune_hash, hold_hash = _digest(tune), _digest(hold)
    except (ValueError, KeyError, TypeError, OverflowError, AttributeError) as exc:
        return {**base, "status": "insufficient_evidence", "reason": str(exc)}
    assessed = assess_trade_metrics(hm, tm, tf_minutes=hold_tf, chart_family=chart_family)
    if assessed["status"] == "thresholds_met_on_supplied_metrics":
        assessed["status"] = "thresholds_met_on_declared_replay"
    return {**base, **assessed, "replay_structure_checked": True,
            "asset": hold["asset"], "tune": tm, "hold": hm,
            "tune_result_sha256": tune_hash, "hold_result_sha256": hold_hash,
            "source_config_sha256": hold_rep["source_config_sha256"],
            "subbars_sha256": hold_rep["subbars_sha256"], "deep_sha256": hold_rep["deep_sha256"],
            "note": "Replay metrics only; final untouched holdout and market-tape parity are unverified"}


def assess_port_windows(port, asset, *, patch, tune_start, tune_end, hold_start, hold_end,
                        expected_chart_type="heikin_ashi"):
    """Run both windows from a frozen port; do not consume a final holdout.

    This is a research screen. Repeated calls inspect the same hold window, so
    it must not be used as the separately protected final acceptance test.
    """
    from icarus_engine.backtest import freeze_replay_port, run_backtest

    shared = {"inputs": patch, "fill_on": "real", "chart_type": expected_chart_type}
    frozen = freeze_replay_port(port, asset)
    tune = run_backtest(frozen, asset, window_start=tune_start, window_end=tune_end, **shared)
    hold = run_backtest(frozen, asset, window_start=hold_start, window_end=hold_end, **shared)
    report = assess_replay_pair(tune, hold, expected_chart_type=expected_chart_type)
    report["engine_replay_checked"] = True
    report["note"] = "Native engine replay only; final untouched holdout and market-tape parity are unverified"
    if report["status"] == "thresholds_met_on_declared_replay":
        report["status"] = "thresholds_met_on_engine_replay"
    return report
