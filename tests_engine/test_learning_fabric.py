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


def test_export_intake_manifest_enriches_real_icarius_filename_metadata(tmp_path):
    from icarus_engine.learning_fabric import LearningFabric

    data = _ohlc(tmp_path / "history" / "drop" / "CME_MINI_DL_NQ1!, 2(1).csv", rows=80)
    raw_sha = __import__("hashlib").sha256(data.read_bytes()).hexdigest()
    manifest = tmp_path / "history" / "EXPORT_INTAKE_MANIFEST.csv"
    manifest.write_text(
        "index,sha256,canonical_filename,duplicate_copies,all_observed_filenames,bytes,format,artifact_class,symbol,timeframe,chart_type,rows,first_or_trading_range,last_or_backtesting_range,last_trade_number,net_profit_usd,max_drawdown_intrabar_usd,notes\n"
        f'0,{raw_sha},"CME_MINI_DL_NQ1!, 2(1).csv",0,"CME_MINI_DL_NQ1!, 2(1).csv",123,csv,chart_data,CME_MINI:NQ1!,20 minutes,Heikin Ashi (verified transform),80,2024-06-02T22:00:00+00:00,2026-09-30T13:20:00+00:00,,,,verified\n',
        encoding="utf-8",
    )
    fabric = LearningFabric(tmp_path)
    scan = fabric.scan_history()
    dataset = fabric.dataset(scan["dataset_ids"][0])
    assert dataset["asset"] == "NQ"
    assert dataset["chart_type"] == "20m"
    assert dataset["manifest"]["intake"]["chart_type"] == "Heikin Ashi (verified transform)"
    assert dataset["manifest"]["intake"]["timeframe"] == "20 minutes"
    assert dataset["manifest"]["intake"]["manifest_sha256"] == raw_sha


def test_empirical_scorecards_publish_research_only_apex_credibility(tmp_path):
    from icarus_engine.learning_fabric import LearningFabric

    class Store:
        def __init__(self):
            self.rows = []
        def record_model_credibility(self, row):
            self.rows.append(dict(row))
            return {"ok": True}

    class Apex:
        def __init__(self):
            self.store = Store()

    fabric = LearningFabric(tmp_path)
    apex = Apex()
    fabric.bind_native(apex=apex)
    pred = fabric.record_prediction(_prediction())["prediction"]
    fabric.record_outcome(
        {
            "prediction_id": pred["prediction_id"],
            "observed_at": pred["resolves_at"],
            "actual_value": 102.0,
            "evidence": ["historical:close"],
        }
    )
    cycle = fabric.tick()
    assert cycle["status"] == "ok"
    assert len(apex.store.rows) == 1
    row = apex.store.rows[0]
    assert row["model_id"].startswith("learning:psi:NQ:trend:300:direction")
    assert row["status"] == "EARLY"
    assert 0.0 <= row["score"] <= 1.0
    assert row["execution_authorized"] is False
    assert row["production_decision_authorized"] is False


def test_background_learning_never_blocks_engine_startup(tmp_path, monkeypatch):
    import threading
    import time
    from icarus_engine.learning_fabric import LearningFabric

    fabric = LearningFabric(tmp_path)
    entered = threading.Event()
    release = threading.Event()

    def slow_cycle():
        entered.set()
        release.wait(2)
        return {"status": "ok", "execution_authorized": False}

    monkeypatch.setattr(fabric, "tick", slow_cycle)
    started = time.monotonic()
    fabric.start_background()
    elapsed = time.monotonic() - started
    assert elapsed < 0.5
    assert entered.wait(1)
    release.set()
    fabric.stop()


def test_native_harvest_absorbs_performance_proof_and_source_reliability(tmp_path):
    from icarus_engine.learning_fabric import LearningFabric
    from icarus_engine.performance_proof import PerformanceProofStore
    from icarus_engine.source_reliability import SourceReliabilityStore

    now = datetime.now(timezone.utc)
    decision = now - timedelta(minutes=20)
    maturity = decision + timedelta(minutes=5)
    observed = maturity + timedelta(seconds=1)

    proof = PerformanceProofStore(tmp_path)
    registered = proof.register_forecast({
        "candidate_id": "nq-alpha-v3",
        "asset": "NQ",
        "regime": "TREND",
        "decision_at": _iso(decision),
        "matures_at": _iso(maturity),
        "probability_success": 0.75,
        "success_definition": "positive net outcome after configured costs",
        "source_repo": "reppiks490/Icarus",
        "source_commit": "d" * 40,
        "dataset_hash": "1" * 64,
        "evidence_hash": "2" * 64,
    })
    proof.record_outcome({
        "forecast_id": registered["forecast_id"],
        "observed_at": _iso(observed),
        "success": True,
        "realized_value": 12.5,
        "outcome_hash": "3" * 64,
        "source": "observed holdout result",
    })

    reliability = SourceReliabilityStore(tmp_path)
    reliability.record_observation({
        "source_id": "provider-a",
        "stream": "NQ-trades",
        "observed_at": _iso(now - timedelta(seconds=1)),
        "event_time": _iso(now - timedelta(seconds=3)),
        "retrieval_time": _iso(now - timedelta(seconds=2)),
        "expected_freshness_seconds": 5.0,
        "complete": True,
        "agreement_bps": 0.5,
        "agreement_tolerance_bps": 1.0,
        "revision": False,
        "evidence_hash": "4" * 64,
    })

    fabric = LearningFabric(tmp_path)
    fabric.bind_native(performance_proof=proof, source_reliability=reliability)
    out = fabric.harvest_native()

    assert out["performance_proof"]["forecasts_imported"] == 1
    assert out["performance_proof"]["outcomes_imported"] == 1
    imported_id = next(x for x in fabric.scorecards() if x["producer"].startswith("performance-proof:"))["producer"]
    stored = fabric._conn.execute("SELECT semantic_json FROM predictions WHERE producer=?", (imported_id,)).fetchone()
    imported = json.loads(stored["semantic_json"])
    assert imported["reference_value"] is None
    assert out["source_reliability"]["status"] == "ok"
    assert out["source_reliability"]["observation_count"] == 1
    assert out["source_reliability"]["source_stream_count"] == 1

    again = fabric.harvest_native()
    assert again["performance_proof"]["forecasts_imported"] == 0
    assert again["performance_proof"]["outcomes_imported"] == 0

    cards = [x for x in fabric.scorecards() if x["producer"].startswith("performance-proof:")]
    assert len(cards) == 1
    assert cards[0]["asset"] == "NQ"
    assert cards[0]["settled"] == 1
    assert cards[0]["successes"] == 1
    assert cards[0]["mean_brier"] == pytest.approx((0.75 - 1.0) ** 2)

    snap = fabric.snapshot()
    assert snap["coverage"]["performance_proof"] == "native_immutable_forecast_outcome"
    assert snap["coverage"]["source_reliability"] == "native_observed_quality_context"
