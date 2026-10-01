"""CA: operator thresholds are evaluated only on complete supplied metrics."""
from icarus_engine.qualification.assess import assess_trade_metrics
from icarus_engine.qualification.operator_goal import GOAL


FAMILY = "clock_minutes"


def _hold(**changes):
    report = dict(
        win_rate=85.0, trades=200, trades_per_day=1.5, mean_hold=8.0,
        expectancy=300.0, runner_legs=0, consistency=0.6,
        positive_block_rate=75.0, top_decile_share=40.0,
        streak_vs_random=1.2, streak_ratio=3.0, mean_run_ratio=1.8,
        hold_p90=18.0, same_bar_rate=1.0, hold_asymmetry=1.67,
        hold_drift=0.05, r_per_bar=37.5, overnight_rate=0.0,
        overnight_net_share=0.0,
    )
    report.update(changes)
    return report


def test_complete_operator_metrics_can_pass_without_execution_authority():
    assert GOAL.min_win_rate == 82.0 and GOAL.min_runner_win_rate == 90.0
    report = assess_trade_metrics(_hold(), {"win_rate": 85.0, "expectancy": 300.0},
                                  tf_minutes=20, chart_family=FAMILY)
    assert report["status"] == "thresholds_met_on_supplied_metrics"
    assert report["candidate_qualified"] is False
    assert report["trade_tape_verified"] is False
    assert report["execution_authorized"] is False


def test_missing_tune_or_metric_is_insufficient_not_a_zero_value():
    assert assess_trade_metrics(_hold(), None, tf_minutes=20, chart_family=FAMILY)["status"] == "insufficient_evidence"
    report = assess_trade_metrics(_hold(top_decile_share=None),
                                  {"win_rate": 85.0, "expectancy": 300.0},
                                  tf_minutes=20, chart_family=FAMILY)
    assert report["status"] == "insufficient_evidence"
    assert "hold.top_decile_share" in report["missing"]


def test_tune_and_runner_thresholds_are_enforced():
    weak = assess_trade_metrics(_hold(), {"win_rate": 70.0, "expectancy": 300.0},
                                tf_minutes=20, chart_family=FAMILY)
    assert weak["status"] == "thresholds_failed"
    assert any("tune win" in gap for gap in weak["shortfall"])
    runner = _hold(runner_legs=40, runner_win_rate=95.0,
                   tp1_rate=20.0, tp2_rate=18.0, tp_gap_pp=2.0)
    incomplete = assess_trade_metrics(runner, {"win_rate": 85.0, "expectancy": 300.0},
                                      tf_minutes=20, chart_family=FAMILY)
    assert incomplete["status"] == "insufficient_evidence"
    assert "tune.tp_gap_pp" in incomplete["missing"]
    tune = {"win_rate": 85.0, "expectancy": 300.0,
            "runner_win_rate": 95.0, "tp_gap_pp": 2.0}
    assert assess_trade_metrics(runner, tune, tf_minutes=20,
                                chart_family=FAMILY)["status"] == "thresholds_met_on_supplied_metrics"
    assert assess_trade_metrics(runner, {**tune, "tp_gap_pp": 20.0},
                                tf_minutes=20, chart_family=FAMILY)["status"] == "thresholds_failed"


def test_nonfinite_metric_or_unknown_timeframe_cannot_pass():
    tune = {"win_rate": 85.0, "expectancy": 300.0}
    assert assess_trade_metrics(_hold(win_rate=float("nan")), tune,
                                tf_minutes=20, chart_family=FAMILY)["status"] == "insufficient_evidence"
    assert assess_trade_metrics(_hold(), tune,
                                tf_minutes=0, chart_family=FAMILY)["status"] == "insufficient_evidence"
    assert assess_trade_metrics(_hold(runner_legs=-1), tune,
                                tf_minutes=20, chart_family=FAMILY)["status"] == "insufficient_evidence"
    assert assess_trade_metrics(_hold(), tune, tf_minutes=20,
                                chart_family="range")["status"] == "insufficient_evidence"
