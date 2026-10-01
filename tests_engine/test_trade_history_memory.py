from __future__ import annotations

from pathlib import Path
import pytest


HEADER = (
    "index,Trade number,Type,Date and time,Signal,Price USD,Size (qty),Size (value),"
    "Net PnL USD,Return %,Commission USD,Favorable excursion USD,Favorable excursion %,"
    "Adverse excursion USD,Adverse excursion %,Cumulative PnL USD,Cumulative PnL %,Duration (bars)"
)


def trade_csv(path: Path) -> Path:
    rows = [
        # One complete long, +50.
        "0,1,Exit long,2024-01-02 10:20,L_TP1,101.0,1,101,50,0.50,4,70,0.70,-10,-0.10,50,0.10,1",
        "1,1,Entry long,2024-01-02 10:00,Long,100.0,1,101,50,0.50,4,70,0.70,-10,-0.10,50,0.10,1",
        # One complete short, -25.
        "2,2,Exit short,2024-01-03 11:20,S_SL,101.0,1,101,-25,-0.25,4,15,0.15,-30,-0.30,25,0.05,1",
        "3,2,Entry short,2024-01-03 11:00,Short,100.0,1,101,-25,-0.25,4,15,0.15,-30,-0.30,25,0.05,1",
        # Two TradingView trade numbers from the same logical entry; total +50.
        "4,3,Exit long,2024-02-01 12:20,L_TP1,102.0,1,204,30,0.15,4,45,0.22,-8,-0.04,55,0.11,1",
        "5,3,Entry long,2024-02-01 12:00,Long,100.0,1,204,30,0.15,4,45,0.22,-8,-0.04,55,0.11,1",
        "6,4,Exit long,2024-02-01 12:40,L_TP2,103.0,1,206,20,0.10,4,60,0.29,-8,-0.04,75,0.15,2",
        "7,4,Entry long,2024-02-01 12:00,Long,100.0,1,206,20,0.10,4,60,0.29,-8,-0.04,75,0.15,2",
        # An open position must not be counted as settled realized performance.
        "8,5,Exit long,Open,Open,101.0,1,101,0,0.0,0,0,0,0,0,75,0.15,0",
        "9,5,Entry long,2024-02-02 13:00,Long,101.0,1,101,0,0.0,0,0,0,0,0,75,0.15,0",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(HEADER + "\n" + "\n".join(rows) + "\n", encoding="utf-8")
    return path


def test_trade_history_memory_groups_partial_exits_and_excludes_open_positions(tmp_path):
    from icarus_engine.trade_history_memory import analyze_trade_list

    report = analyze_trade_list(
        trade_csv(tmp_path / "trades.csv"),
        dataset_id="ds-test",
        asset="NQ",
    )
    assert report["schema_version"] == "icarus-trade-history-memory-v1"
    assert report["status"] == "MEASURED"
    assert report["logical_trades"] == 4
    assert report["closed_trades"] == 3
    assert report["open_trades"] == 1
    assert report["wins"] == 2
    assert report["losses"] == 1
    assert report["breakeven"] == 0
    assert report["hit_rate"] == pytest.approx(2 / 3)
    assert report["net_pnl"] == pytest.approx(75.0)
    assert report["gross_profit"] == pytest.approx(100.0)
    assert report["gross_loss_abs"] == pytest.approx(25.0)
    assert report["profit_factor"] == pytest.approx(4.0)
    assert report["max_drawdown"] == pytest.approx(25.0)
    assert report["mean_trade_pnl"] == pytest.approx(25.0)
    assert report["median_trade_pnl"] == pytest.approx(50.0)
    assert report["mean_duration_seconds"] == pytest.approx(1600.0)
    assert report["by_direction"]["LONG"]["closed_trades"] == 2
    assert report["by_direction"]["LONG"]["net_pnl"] == pytest.approx(100.0)
    assert report["by_direction"]["SHORT"]["closed_trades"] == 1
    assert report["by_direction"]["SHORT"]["net_pnl"] == pytest.approx(-25.0)
    assert report["by_export_year"]["2024"]["closed_trades"] == 3
    assert report["time_basis"] == "export_clock_timezone_unspecified"
    assert report["session_classification"] == "UNAVAILABLE"
    assert report["future_guarantee"] is False
    assert report["execution_authorized"] is False
    assert report["production_decision_authorized"] is False


def test_learning_fabric_persists_trade_history_memory_idempotently(tmp_path):
    from icarus_engine.learning_fabric import LearningFabric

    path = trade_csv(tmp_path / "history" / "drop" / "NQ-trades.csv")
    fabric = LearningFabric(tmp_path)
    dataset = fabric.register_dataset(path, asset="NQ")["dataset"]
    assert dataset["artifact_class"] == "trade_list"

    first = fabric.analyze_trade_history(dataset["dataset_id"])
    second = fabric.analyze_trade_history(dataset["dataset_id"])
    assert first["idempotent"] is False
    assert second["idempotent"] is True
    assert first["report"]["closed_trades"] == 3

    snap = fabric.snapshot()
    assert snap["trade_history"]["run_count"] == 1
    assert snap["trade_history"]["dataset_count"] == 1
    assert snap["coverage"]["historical_trade_lists"] == "realized_strategy_memory_not_forecast_accuracy"


def test_learning_cycle_auto_analyzes_bounded_new_trade_lists(tmp_path):
    from icarus_engine.learning_fabric import LearningFabric

    trade_csv(tmp_path / "history" / "drop" / "NQ-a.csv")
    trade_csv(tmp_path / "history" / "drop" / "NQ-b.csv")
    fabric = LearningFabric(tmp_path)
    fabric.configure({"max_trade_histories_per_cycle": 1})
    fabric.scan_history()

    one = fabric.tick()
    assert len(one["summary"]["trade_history"]) == 1
    assert fabric.snapshot()["trade_history"]["run_count"] == 1

    two = fabric.tick()
    assert len(two["summary"]["trade_history"]) == 1
    assert fabric.snapshot()["trade_history"]["run_count"] == 2

    with pytest.raises(ValueError, match="max_trade_histories_per_cycle"):
        fabric.configure({"max_trade_histories_per_cycle": 33})
