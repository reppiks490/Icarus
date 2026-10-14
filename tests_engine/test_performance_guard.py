from types import SimpleNamespace

import pytest

from icarus_engine.runtime import Journal


def _piece(lot, piece, profit, *, entry_qty=1, qty=1):
    return SimpleNamespace(
        entry_id="L", direction=1, qty=qty, entry_price=100.0, entry_ts=1000 + lot,
        exit_price=101.0, exit_ts=1100 + lot, exit_comment="TP", profit=profit,
        lot_id=lot, entry_qty=entry_qty, bars=4,
    )


def test_performance_review_combines_partial_exits_and_applies_pressure_floor():
    journal = Journal(":memory:")
    context = {"regime": "TREND", "regime_attribution": "entry_fill_previous_closed_bar"}
    for lot in range(12):
        win = lot < 8
        profit = 10.0 if win else -10.0
        if lot == 0:
            journal.add_trade("NQ", _piece(lot, 0, profit / 2, entry_qty=2), True, 0, context=context)
            assert journal.performance_review("NQ")["scorecards"] == {}
            journal.add_trade("NQ", _piece(lot, 1, profit / 2, entry_qty=2), True, 1, context=context)
        else:
            journal.add_trade("NQ", _piece(lot, 0, profit), True, 0, context=context)

    score = journal.performance_review("NQ")["scorecards"]["TREND"]
    assert score["sample_lots"] == 12
    assert score["wins"] == 8
    assert score["win_rate"] == pytest.approx(8 / 12)
    assert score["status"] == "PRESSURE"
    assert score["average_hold_bars"] == 4
    assert score["average_hold_seconds"] == pytest.approx(100)
    assert score["regime_attribution"] == ["entry_fill_previous_closed_bar"]


@pytest.mark.parametrize(("wins", "expected"), [(9, "WATCH"), (10, "WATCH"), (11, "HEALTHY")])
def test_performance_review_watch_thresholds(wins, expected):
    journal = Journal(":memory:")
    for lot in range(12):
        pnl = 1.0 if lot < wins else -1.0
        journal.add_trade("ES", _piece(lot, 0, pnl), True, 0, context={"regime": "CHOP"})
    assert journal.performance_review("ES")["scorecards"]["CHOP"]["status"] == expected


def test_performance_review_starts_a_fresh_activation_cohort():
    journal = Journal(":memory:")
    for lot in range(12):
        journal.add_trade("YM", _piece(lot, 0, -1.0), True, 0, context={"regime": "TREND"})
    assert journal.performance_review("YM")["scorecards"]["TREND"]["status"] == "PRESSURE"
    assert journal.performance_review("YM", since_ts=2000)["scorecards"] == {}
