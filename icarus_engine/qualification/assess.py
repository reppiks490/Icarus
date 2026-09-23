"""CA: fail-closed wrapper around the operator's pinned trade rules."""
from __future__ import annotations

import math
from numbers import Real

from .operator_goal import GOAL


SOURCE_COMMIT = "6e0da3524f20c859129fdd2e122a96be45d55cb4"
HOLD_FIELDS = frozenset({
    "win_rate", "trades", "trades_per_day", "mean_hold", "expectancy",
    "consistency", "positive_block_rate", "top_decile_share",
    "streak_vs_random", "streak_ratio", "mean_run_ratio", "hold_p90",
    "same_bar_rate", "hold_asymmetry", "hold_drift", "r_per_bar",
    "overnight_rate", "overnight_net_share", "runner_legs",
})
TUNE_FIELDS = frozenset({"win_rate", "expectancy"})
RUNNER_HOLD_FIELDS = frozenset({"runner_win_rate", "tp_gap_pp", "tp1_rate", "tp2_rate"})
RUNNER_TUNE_FIELDS = frozenset({"runner_win_rate", "tp_gap_pp"})


def assess_trade_metrics(hold, tune, *, tf_minutes, chart_family):
    """Test complete supplied metrics; never assert that a trade tape is genuine."""
    base = {"rule_source_commit": SOURCE_COMMIT, "execution_authorized": False,
            "trade_tape_verified": False, "candidate_qualified": False}
    if not isinstance(hold, dict) or not isinstance(tune, dict):
        return {**base, "status": "insufficient_evidence",
                "missing": ["both held-out and tune metric dictionaries required"]}
    if chart_family not in ("clock_seconds", "clock_minutes", "clock_hours"):
        return {**base, "status": "insufficient_evidence",
                "missing": ["an actual clock-bar interval is required for these duration rules"]}
    if isinstance(tf_minutes, bool) or not isinstance(tf_minutes, Real) or not math.isfinite(tf_minutes) or tf_minutes <= 0:
        return {**base, "status": "insufficient_evidence",
                "missing": ["positive finite timeframe minutes required"]}
    needs_hold, needs_tune = set(HOLD_FIELDS), set(TUNE_FIELDS)
    legs = hold.get("runner_legs")
    if isinstance(legs, Real) and math.isfinite(legs) and legs > 0:
        needs_hold.update(RUNNER_HOLD_FIELDS)
        needs_tune.update(RUNNER_TUNE_FIELDS)
    missing = []
    for prefix, report, fields in (("hold", hold, needs_hold), ("tune", tune, needs_tune)):
        for field in sorted(fields):
            value = report.get(field)
            if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
                missing.append(f"{prefix}.{field}")
    if missing:
        return {**base, "status": "insufficient_evidence", "missing": missing}
    if (hold["trades"] < 0 or int(hold["trades"]) != hold["trades"]
            or hold["runner_legs"] < 0 or int(hold["runner_legs"]) != hold["runner_legs"]):
        return {**base, "status": "insufficient_evidence",
                "missing": ["nonnegative integer trade and runner counts required"]}
    if not GOAL.clears(hold, tune, tf_minutes=float(tf_minutes)):
        gaps = GOAL.shortfall(hold, tf_minutes=float(tf_minutes))
        if tune["win_rate"] < GOAL.min_win_rate:
            gaps.append(f"tune win {tune['win_rate']:.1f}<{GOAL.min_win_rate}")
        if tune["expectancy"] <= GOAL.min_expectancy:
            gaps.append(f"tune expectancy {tune['expectancy']:+.2f}<=0")
        if hold["runner_legs"]:
            if tune["tp_gap_pp"] > GOAL.max_tp_gap_pp:
                gaps.append(f"tune TP gap {tune['tp_gap_pp']:.1f}>{GOAL.max_tp_gap_pp}")
            if abs(hold["tp_gap_pp"] - tune["tp_gap_pp"]) > GOAL.max_tp_gap_drift_pp:
                gaps.append("TP gap drift exceeds operator limit")
            if tune["runner_win_rate"] < GOAL.min_runner_win_rate:
                gaps.append("tune runner win rate below operator limit")
        return {**base, "status": "thresholds_failed", "shortfall": gaps or [
            "operator rules failed; inspect complete source rule implementation"],
            "tune_win_rate": tune["win_rate"],
            "tune_expectancy": tune["expectancy"]}
    return {**base, "status": "thresholds_met_on_supplied_metrics",
            "score_among_threshold_passes": GOAL.score(hold),
            "note": "Trade tape and held-out selection must be independently verified"}
