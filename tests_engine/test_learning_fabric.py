from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import json

import pytest


def _iso(dt):
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _prediction(*, producer="psi", regime="trend", horizon=300, probability=0.8, direction="up", emitted=None):
    emitted = emitted or datetime(2026, 10, 1, 14, 0, tzinfo=timezone.utc)
    return {
        "producer": producer,
        "asset": "NQ",
        "target": "direction",
        "prediction": direction,
        "probability": probability,
        "reference_value": 100.0,
        "emitted_at": _iso(emitted),
        "horizon_seconds": horizon,
        "regime": regime,
        "evidence_ids": ["e1"],
        "source_commit": "a" * 40,
        "metadata": {"test": True},
    }


def _ohlc(path: Path, rows: int = 500) -> Path:
    start = 1_700_000_000
    px = 100.0
    out = ["time,open,high,low,close"]
    for i in range(rows):
        step = 1.0 if (i // 8) % 2 == 0 else -1.0
        nxt = px + step
        out.append(f"{start+i},{px},{max(px,nxt)},{min(px,nxt)},{nxt}")
        px = nxt
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return path


def test_prediction_outcome_maturity_immutability_and_authority(tmp_path):
    from icarus_engine.learning_fabric import LearningFabric

    fabric = LearningFabric(tmp_path)
    p = fabric.record_prediction(_prediction())
    assert p["prediction"]["execution_authorized"] is False
    assert p["prediction"]["production_decision_authorized"] is False

    with pytest.raises(ValueError, match="maturity"):
        fabric.record_outcome(
            {
                "prediction_id": p["prediction"]["prediction_id"],
                "observed_at": "2026-10-01T14:04:59Z",
                "actual_value": 102.0,
                "evidence": ["bar:early"],
            }
        )

    first = fabric.record_outcome(
        {
            "prediction_id": p["prediction"]["prediction_id"],
            "observed_at": "2026-10-01T14:05:00Z",
            "actual_value": 102.0,
            "evidence": ["bar:close"],
        }
    )
    assert first["outcome"]["success"] is True
    assert first["outcome"]["brier"] == pytest.approx(0.04)
    assert first["outcome"]["execution_authorized"] is False

    repeat = fabric.record_outcome(
        {
            "prediction_id": p["prediction"]["prediction_id"],
            "observed_at": "2026-10-01T14:05:00Z",
            "actual_value": 102.0,
            "evidence": ["bar:close"],
        }
    )
    assert repeat["idempotent"] is True

    with pytest.raises(ValueError, match="immutable"):
        fabric.record_outcome(
            {
                "prediction_id": p["prediction"]["prediction_id"],
                "observed_at": "2026-10-01T14:05:00Z",
                "actual_value": 99.0,
                "evidence": ["different"],
            }
        )


def test_scorecards_are_producer_regime_horizon_specific(tmp_path):
    from icarus_engine.learning_fabric import LearningFabric

    fabric = LearningFabric(tmp_path)
    base = datetime(2026, 10, 1, 14, 0, tzinfo=timezone.utc)
    cases = [
        (_prediction(producer="psi", regime="trend", horizon=300, probability=0.8, direction="up", emitted=base), 102.0),
        (_prediction(producer="psi", regime="trend", horizon=300, probability=0.7, direction="up", emitted=base+timedelta(minutes=10)), 99.0),
        (_prediction(producer="sibyl", regime="volatile", horizon=900, probability=0.9, direction="down", emitted=base+timedelta(minutes=20)), 95.0),
    ]
    for body, actual in cases:
        p = fabric.record_prediction(body)["prediction"]
        mature = datetime.fromisoformat(p["resolves_at"].replace("Z", "+00:00"))
        fabric.record_outcome(
            {
                "prediction_id": p["prediction_id"],
                "observed_at": _iso(mature),
                "actual_value": actual,
                "evidence": ["historical:close"],
            }
        )

    cards = fabric.scorecards()
    assert len(cards) == 2
    psi = next(x for x in cards if x["producer"] == "psi")
    assert psi["regime"] == "trend"
    assert psi["horizon_seconds"] == 300
    assert psi["settled"] == 2
    assert psi["successes"] == 1
    assert psi["hit_rate"] == pytest.approx(0.5)
    assert psi["mean_brier"] == pytest.approx(((0.8-1)**2 + (0.7-0)**2) / 2)
    assert psi["calibration_gap"] == pytest.approx(abs(0.75 - 0.5))


def test_observed_price_settles_due_predictions_without_future_leakage(tmp_path):
    from icarus_engine.learning_fabric import LearningFabric

    fabric = LearningFabric(tmp_path)
    base = datetime(2026, 10, 1, 14, 0, tzinfo=timezone.utc)
    due = fabric.record_prediction(_prediction(horizon=300, emitted=base))["prediction"]
    future = fabric.record_prediction(_prediction(horizon=900, emitted=base))["prediction"]

    result = fabric.observe_price(
        "NQ",
        "2026-10-01T14:06:00Z",
        103.0,
        evidence=["historical:bar"],
    )
    assert result["settled"] == 1
    assert result["prediction_ids"] == [due["prediction_id"]]
    assert fabric.outcome(due["prediction_id"])["actual_value"] == 103.0
    assert fabric.outcome(future["prediction_id"]) is None


def test_dataset_catalog_dedupes_hash_and_records_coverage(tmp_path):
    from icarus_engine.learning_fabric import LearningFabric

    data = _ohlc(tmp_path / "history" / "drop" / "NQ-20m.csv", rows=80)
    fabric = LearningFabric(tmp_path)

    one = fabric.register_dataset(data, asset="NQ", chart_type="20m")
    two = fabric.register_dataset(data, asset="NQ", chart_type="20m")
    assert one["dataset"]["dataset_id"] == two["dataset"]["dataset_id"]
    assert two["idempotent"] is True
    assert one["dataset"]["artifact_class"] == "ohlc"
    assert one["dataset"]["rows"] == 80
    assert one["dataset"]["first_timestamp"] is not None
    assert one["dataset"]["last_timestamp"] is not None

    scan = fabric.scan_history()
    assert scan["unique_datasets"] == 1
    assert scan["files_seen"] >= 1


def test_backfill_dataset_runs_existing_protected_trainer_and_persists_report(tmp_path):
    from icarus_engine.learning_fabric import LearningFabric

    data = _ohlc(tmp_path / "history" / "NQ-renko.csv", rows=500)
    fabric = LearningFabric(tmp_path)
    dataset = fabric.register_dataset(data, asset="NQ", chart_type="renko")["dataset"]

    result = fabric.backfill_dataset(dataset["dataset_id"], slots=["logit"])
    assert result["runs"][0]["slot"] == "logit"
    assert result["runs"][0]["report"]["status"] == "fitted"
    assert result["runs"][0]["report"]["holdout_rows"] >= 10
    assert result["runs"][0]["report"]["execution_authorized"] is False

    snap = fabric.snapshot()
    assert snap["datasets"]["count"] == 1
    assert snap["training"]["run_count"] == 1
    assert snap["authority"]["automatic_production_promotion"] is False
    assert snap["execution_authorized"] is False


def test_sibyl_native_harvest_imports_real_forecast_outcomes(tmp_path):
    from icarus_engine.learning_fabric import LearningFabric
    from icarus_engine.sibyl import SibylEngine

    sibyl = SibylEngine(tmp_path)
    forecast_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    sibyl.record_evidence(
        {
            "asset": "NQ",
            "source": "oracle",
            "domain": "macro",
            "observed_at": _iso(forecast_time - timedelta(minutes=1)),
            "direction": 1.0,
            "magnitude": 1.0,
            "confidence": 0.8,
            "horizon_seconds": 300,
            "source_commit": "b" * 40,
        }
    )
    forecast = sibyl.record_forecast(
        {
            "asset": "NQ",
            "observed_at": _iso(forecast_time),
            "current_price": 100.0,
            "volatility_pct": 0.01,
            "horizons": [300],
            "source_commit": "c" * 40,
        }
    )
    sibyl.record_outcome(
        {
            "forecast_id": forecast["forecast_id"],
            "horizon_seconds": 300,
            "observed_at": _iso(forecast_time + timedelta(seconds=300)),
            "realized_price": 102.0,
            "evidence": ["historical:bar"],
        }
    )

    fabric = LearningFabric(tmp_path)
    result = fabric.harvest_native()
    assert result["sibyl"]["forecasts_imported"] == 1
    assert result["sibyl"]["outcomes_imported"] == 1
    card = next(x for x in fabric.scorecards() if x["producer"] == "sibyl")
    assert card["settled"] == 1
    assert card["mean_brier"] is not None


def test_learning_fabric_config_and_cycles_are_bounded_and_research_only(tmp_path):
    from icarus_engine.learning_fabric import LearningFabric

    fabric = LearningFabric(tmp_path)
    status = fabric.configure(
        {
            "enabled": True,
            "cycle_seconds": 60,
            "history_scan_seconds": 3600,
            "max_backfills_per_cycle": 1,
            "auto_train_slots": ["logit"],
        }
    )
    assert status["config"]["enabled"] is True
    assert status["execution_authorized"] is False

    cycle = fabric.tick()
    assert cycle["status"] in {"ok", "partial"}
    assert cycle["execution_authorized"] is False
    saved = json.loads((tmp_path / "research" / "learning.json").read_text(encoding="utf-8"))
    assert saved["enabled"] is True

    with pytest.raises(ValueError):
        fabric.configure({"cycle_seconds": 0})
