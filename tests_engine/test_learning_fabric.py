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


def _trade_list(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "Trade number,Type,Date and time,Signal,Price USD,Size (qty),Net PnL USD\n"
        "1,Exit long,2024-06-03 11:00,L_TP,101.0,1,50.0\n"
        "1,Entry long,2024-06-03 10:20,Long,100.0,1,50.0\n"
        "2,Exit short,2024-06-03 12:20,S_SL,103.0,1,-75.0\n"
        "2,Entry short,2024-06-03 11:40,Short,102.0,1,-75.0\n",
        encoding="utf-8",
    )
    return path


def test_trade_list_dataset_becomes_realized_experience(tmp_path):
    from icarus_engine.learning_fabric import LearningFabric

    path = _trade_list(tmp_path / "history" / "drop" / "THE_PULSE_NQ.csv")
    fabric = LearningFabric(tmp_path)
    dataset = fabric.register_dataset(path, asset="NQ")["dataset"]
    assert dataset["artifact_class"] == "trade_list"

    result = fabric.backfill_dataset(dataset["dataset_id"], slots=["logit"])
    assert result["status"] == "complete"
    assert result["runs"][0]["slot"] == "trade_experience"
    assert result["runs"][0]["report"]["status"] == "imported"
    assert result["runs"][0]["report"]["experience_count"] == 2
    assert result["runs"][0]["report"]["time_quality"] == "UNVERIFIED_TIMEZONE"

    snap = fabric.snapshot()
    assert snap["experiences"]["count"] == 2
    row = next(x for x in snap["experiences"]["summary"] if x["source"] == "historical_trade_list")
    assert row["asset"] == "NQ"
    assert row["count"] == 2
    assert row["wins"] == 1
    assert row["losses"] == 1
    assert row["net_pnl"] == pytest.approx(-25.0)
    assert row["win_rate"] == pytest.approx(0.5)
    assert row["profit_factor"] == pytest.approx(50.0 / 75.0)

    again = fabric.backfill_dataset(dataset["dataset_id"], slots=["logit"])
    assert again["runs"][0]["idempotent"] is True
    assert fabric.snapshot()["experiences"]["count"] == 2


def test_runtime_learning_harvests_only_fully_closed_live_sim_positions(tmp_path):
    from types import SimpleNamespace
    from icarus_engine.emulator import ClosedTrade, OpenTrade
    from icarus_engine.learning_fabric import LearningFabric

    closed = [
        ClosedTrade("L", 1, 1, 100.0, 1, 100, 101.0, 2, 200, "TP1", 40.0, lot_id=7, entry_qty=2),
        ClosedTrade("L", 1, 1, 100.0, 1, 100, 102.0, 3, 220, "TP2", 80.0, lot_id=7, entry_qty=2),
        ClosedTrade("OLD", -1, 1, 105.0, 1, 50, 104.0, 2, 90, "TP", 20.0, lot_id=3, entry_qty=1),
        ClosedTrade("OPEN", 1, 1, 110.0, 1, 160, 111.0, 2, 210, "TP1", 10.0, lot_id=9, entry_qty=2),
    ]
    open_rows = [OpenTrade("OPEN", 1, 1, 2, 110.0, 1, 160)]
    runner = SimpleNamespace(
        symbol="NQ",
        live_from_ts=150,
        em=SimpleNamespace(closed=closed, open=open_rows),
    )
    port = SimpleNamespace(
        runner_list=lambda: [runner],
        status=lambda: {"assets": []},
    )
    fabric = LearningFabric(tmp_path, port=port)

    cycle = fabric.tick()
    runtime = cycle["summary"]["experience"]["runtime"]
    assert runtime["imported"] == 1
    snap = fabric.snapshot()
    assert snap["experiences"]["count"] == 1
    row = next(x for x in snap["experiences"]["summary"] if x["source"] == "runtime_live_sim")
    assert row["count"] == 1
    assert row["wins"] == 1
    assert row["net_pnl"] == pytest.approx(120.0)

    again = fabric.tick()
    assert again["summary"]["experience"]["runtime"]["imported"] == 0
    assert fabric.snapshot()["experiences"]["count"] == 1


def test_experience_records_are_immutable_and_research_only(tmp_path):
    from icarus_engine.learning_fabric import LearningFabric

    fabric = LearningFabric(tmp_path)
    body = {
        "source": "fixture",
        "source_record_id": "trade-1",
        "asset": "NQ",
        "direction": "long",
        "entry_at": "2026-09-30T14:00:00Z",
        "exit_at": "2026-09-30T14:20:00Z",
        "qty": 2,
        "entry_price": 25000.0,
        "exit_price": 25010.0,
        "pnl": 400.0,
        "metadata": {"regime": "trend"},
    }
    first = fabric.record_experience(body)
    assert first["experience"]["execution_authorized"] is False
    assert first["experience"]["production_decision_authorized"] is False
    assert fabric.record_experience(body)["idempotent"] is True
    with pytest.raises(ValueError, match="immutable"):
        fabric.record_experience({**body, "pnl": -400.0})


def test_runtime_experience_fails_closed_before_live_boundary(tmp_path):
    from types import SimpleNamespace
    from icarus_engine.emulator import ClosedTrade
    from icarus_engine.learning_fabric import LearningFabric

    runner = SimpleNamespace(
        symbol="NQ",
        live_from_ts=None,
        live_closed_start=0,
        em=SimpleNamespace(
            closed=[ClosedTrade("WARM", 1, 1, 100.0, 1, 100, 101.0, 2, 200, "TP", 40.0, lot_id=1, entry_qty=1)],
            open=[],
        ),
    )
    port = SimpleNamespace(runner_list=lambda: [runner], status=lambda: {"assets": []})
    fabric = LearningFabric(tmp_path, port=port)
    cycle = fabric.tick()
    assert cycle["summary"]["experience"]["runtime"]["imported"] == 0
    assert cycle["summary"]["experience"]["runtime"]["skipped_no_live_boundary"] == 1
    assert fabric.snapshot()["experiences"]["count"] == 0


def test_learning_health_is_durable_and_tracks_ok_partial_failure(tmp_path, monkeypatch):
    from icarus_engine.learning_fabric import LearningFabric

    fabric = LearningFabric(tmp_path)
    initial = fabric.health()
    assert initial["status"] == "WARMING"
    assert initial["attempts"] == 0
    assert initial["failures"] == 0
    assert initial["execution_authorized"] is False

    ok = fabric.run_cycle()
    assert ok["status"] == "ok"
    health = fabric.health()
    assert health["attempts"] == 1
    assert health["completed"] == 1
    assert health["ok_cycles"] == 1
    assert health["partial_cycles"] == 0
    assert health["failures"] == 0
    assert health["consecutive_failures"] == 0
    assert health["last_ok_at"] is not None
    assert health["last_completed_at"] is not None

    original_tick = fabric.tick
    monkeypatch.setattr(fabric, "tick", lambda: {"status": "partial", "errors": {"x": "fixture"}, "execution_authorized": False})
    partial = fabric.run_cycle()
    assert partial["status"] == "partial"
    health = fabric.health()
    assert health["attempts"] == 2
    assert health["completed"] == 2
    assert health["partial_cycles"] == 1
    assert health["consecutive_partial"] == 1
    assert health["failures"] == 0

    monkeypatch.setattr(fabric, "tick", lambda: (_ for _ in ()).throw(RuntimeError("fixture crash")))
    with pytest.raises(RuntimeError, match="fixture crash"):
        fabric.run_cycle()
    health = fabric.health()
    assert health["attempts"] == 3
    assert health["completed"] == 2
    assert health["failures"] == 1
    assert health["consecutive_failures"] == 1
    assert "fixture crash" in health["last_error"]

    reopened = LearningFabric(tmp_path)
    persisted = reopened.health()
    assert persisted["attempts"] == 3
    assert persisted["failures"] == 1
    assert persisted["last_error"] == health["last_error"]

    monkeypatch.setattr(fabric, "tick", original_tick)


def test_learning_health_reports_backlogs_and_staleness(tmp_path, monkeypatch):
    from icarus_engine.learning_fabric import LearningFabric

    _ohlc(tmp_path / "history" / "drop" / "NQ-20m.csv", rows=80)
    _trade_list(tmp_path / "history" / "drop" / "NQ-trades.csv")
    fabric = LearningFabric(tmp_path)
    fabric.scan_history()
    pred = fabric.record_prediction(_prediction(horizon=900))["prediction"]

    health = fabric.health()
    assert health["backlog"]["pending_predictions"] == 1
    assert health["backlog"]["untrained_ohlc_datasets"] == 1
    assert health["backlog"]["unimported_trade_lists"] == 1
    assert health["stale"] is False

    fabric.run_cycle()
    fresh = fabric.health()
    assert fresh["last_completed_at"] is not None
    assert fresh["stale"] is False
    assert fresh["backlog"]["pending_predictions"] == 1

    old = "2026-09-30T00:00:00Z"
    with fabric._lock, fabric._conn:
        fabric._conn.execute(
            "UPDATE service_health SET last_completed_at=?, last_ok_at=? WHERE service='learning'",
            (old, old),
        )
    monkeypatch.setattr("icarus_engine.learning_fabric._utc_now", lambda: "2026-10-01T20:00:00Z")
    stale = fabric.health()
    assert stale["stale"] is True
    assert stale["status"] == "STALE"


def test_background_learning_records_crashes_instead_of_silently_swallowing(tmp_path, monkeypatch):
    import time
    from icarus_engine.learning_fabric import LearningFabric

    fabric = LearningFabric(tmp_path)
    fabric.configure({"cycle_seconds": 5})
    calls = {"n": 0}

    def boom():
        calls["n"] += 1
        raise RuntimeError("background fixture crash")

    monkeypatch.setattr(fabric, "tick", boom)
    fabric.start_background()
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline and fabric.health()["failures"] < 1:
        time.sleep(0.01)
    fabric.stop()

    health = fabric.health()
    assert calls["n"] >= 1
    assert health["failures"] >= 1
    assert health["consecutive_failures"] >= 1
    assert "background fixture crash" in health["last_error"]
    assert health["background_running"] is False


def test_journal_trade_context_survives_into_learning_after_runner_memory_is_gone(tmp_path):
    from types import SimpleNamespace
    from icarus_engine.learning_fabric import LearningFabric
    from icarus_engine.runtime import Journal

    journal = Journal(str(tmp_path / "paper.sqlite3"))
    context = {
        "strategy_fingerprint": "f" * 64,
        "inputs_hash": "e" * 64,
        "chart_type": "standard",
        "timeframe": "20",
        "fill_on": "real",
        "security_source": "standard",
        "session_mode": "rth",
        "profile": "nq",
        "preset": "alpha",
    }
    one = SimpleNamespace(
        entry_id="L", direction=1, qty=1, entry_price=25000.0, entry_ts=100,
        exit_price=25010.0, exit_ts=200, exit_comment="TP1", profit=200.0,
        lot_id=7, entry_qty=2,
    )
    two = SimpleNamespace(
        entry_id="L", direction=1, qty=1, entry_price=25000.0, entry_ts=100,
        exit_price=25020.0, exit_ts=220, exit_comment="TP2", profit=400.0,
        lot_id=7, entry_qty=2,
    )
    journal.add_trade("NQ", one, True, 0, context=context)
    journal.add_trade("NQ", two, True, 0, context=context)

    port = SimpleNamespace(
        journal=journal,
        runner_list=lambda: [],
        status=lambda: {"assets": []},
    )
    fabric = LearningFabric(tmp_path, port=port)
    cycle = fabric.tick()
    runtime = cycle["summary"]["experience"]["runtime"]
    assert runtime["source"] == "journal"
    assert runtime["imported"] == 1

    row = fabric._conn.execute("SELECT semantic_json FROM experiences").fetchone()
    experience = json.loads(row["semantic_json"])
    assert experience["pnl"] == pytest.approx(600.0)
    assert experience["qty"] == pytest.approx(2.0)
    assert experience["metadata"]["strategy_fingerprint"] == "f" * 64
    assert experience["metadata"]["inputs_hash"] == "e" * 64
    assert experience["metadata"]["session_mode"] == "rth"
    assert experience["metadata"]["provenance_quality"] == "CLOSURE_TIME_CONFIG"


def test_experience_configuration_summary_never_mixes_strategy_fingerprints(tmp_path):
    from icarus_engine.learning_fabric import LearningFabric

    fabric = LearningFabric(tmp_path)
    rows = [
        ("a" * 64, 100.0, "2026-09-30T14:00:00Z", "2026-09-30T14:20:00Z"),
        ("a" * 64, -40.0, "2026-09-30T14:30:00Z", "2026-09-30T14:50:00Z"),
        ("a" * 64, -30.0, "2026-09-30T15:00:00Z", "2026-09-30T15:20:00Z"),
        ("b" * 64, 25.0, "2026-09-30T15:30:00Z", "2026-09-30T15:50:00Z"),
    ]
    for i, (fingerprint, pnl, entry_at, exit_at) in enumerate(rows):
        fabric.record_experience({
            "source": "runtime_live_sim",
            "source_record_id": f"trade-{i}",
            "asset": "NQ",
            "direction": "long",
            "entry_at": entry_at,
            "exit_at": exit_at,
            "qty": 1,
            "entry_price": 25000.0,
            "exit_price": 25001.0,
            "pnl": pnl,
            "metadata": {
                "strategy_fingerprint": fingerprint,
                "inputs_hash": ("1" if fingerprint.startswith("a") else "2") * 64,
                "chart_type": "standard",
                "timeframe": "20",
                "session_mode": "rth",
                "fill_on": "real",
                "security_source": "standard",
                "profile": "nq",
                "preset": "alpha" if fingerprint.startswith("a") else "beta",
                "provenance_quality": "CLOSURE_TIME_CONFIG",
            },
        })

    state = fabric.experience_state()
    cards = {x["strategy_fingerprint"]: x for x in state["by_configuration"]}
    assert set(cards) == {"a" * 64, "b" * 64}
    a = cards["a" * 64]
    assert a["count"] == 3
    assert a["net_pnl"] == pytest.approx(30.0)
    assert a["average_pnl"] == pytest.approx(10.0)
    assert a["max_cumulative_drawdown"] == pytest.approx(70.0)
    assert a["average_win"] == pytest.approx(100.0)
    assert a["average_loss"] == pytest.approx(-35.0)
    assert a["payoff_ratio"] == pytest.approx(100.0 / 35.0)
    assert a["preset"] == "alpha"
    assert cards["b" * 64]["count"] == 1


def test_unscoped_experience_is_not_promoted_into_configuration_scorecard(tmp_path):
    from icarus_engine.learning_fabric import LearningFabric

    fabric = LearningFabric(tmp_path)
    fabric.record_experience({
        "source": "historical_trade_list",
        "source_record_id": "legacy",
        "asset": "NQ",
        "direction": "short",
        "entry_at": "2024-06-03T10:00:00Z",
        "exit_at": "2024-06-03T10:20:00Z",
        "qty": 1,
        "entry_price": 18000.0,
        "exit_price": 17990.0,
        "pnl": 200.0,
        "metadata": {"time_quality": "UNVERIFIED_TIMEZONE"},
    })
    state = fabric.experience_state()
    assert state["count"] == 1
    assert state["by_configuration"] == []
    assert state["unscoped_count"] == 1


def test_learning_fabric_calibrates_psi_raw_scenario_shares_without_overlap(tmp_path, monkeypatch):
    import icarus_engine.learning_fabric as learning_module
    from icarus_engine.learning_fabric import LearningFabric

    clock = {"now": datetime(2026, 10, 1, 14, 0, tzinfo=timezone.utc)}
    monkeypatch.setattr(learning_module, "_utc_now", lambda: _iso(clock["now"]))
    monkeypatch.setattr(
        learning_module,
        "local_code_provenance",
        lambda: {"candidate_revision_eligible": True, "commit": "a" * 40},
        raising=False,
    )

    class Port:
        def __init__(self):
            self.price = 100.0
        def status(self):
            return {"assets": [{"symbol": "NQ", "price": self.price}]}

    class Psi:
        def status(self):
            return {"assets": {"NQ": {}}, "execution_authorized": False, "production_decision_authorized": False}
        def snapshot(self, asset=None):
            return {
                "asset": "NQ",
                "generated_at": _iso(clock["now"]),
                "price": 100.0,
                "edge_state": {"state": "NO_EDGE"},
                "forecast_calibration_contract": {
                    "status": "ELIGIBLE_UNCALIBRATED",
                    "asset": "NQ",
                    "emitted_at": _iso(clock["now"]),
                    "reference_price": 100.0,
                    "chart_minutes": 1,
                    "horizon_steps": 10,
                    "horizon_seconds": 600,
                    "classification_threshold_return": 0.005,
                    "cluster_shares": {"UP": 0.7, "FLAT": 0.2, "DOWN": 0.1},
                    "dominant_cluster": "UP",
                    "calibrated": False,
                    "execution_authorized": False,
                    "production_decision_authorized": False,
                },
            }

    port = Port()
    fabric = LearningFabric(tmp_path, port=port)
    fabric.bind_native(possibility=Psi())

    first = fabric.harvest_native()["possibility"]
    assert first["forecasts_imported"] == 1
    assert first["outcomes_imported"] == 0
    assert first["overlap_withheld"] == 0

    again = fabric.harvest_native()["possibility"]
    assert again["forecasts_imported"] == 0
    assert again["overlap_withheld"] == 1
    assert fabric.scorecards() == []

    clock["now"] += timedelta(seconds=601)
    port.price = 101.0
    matured = fabric.harvest_native()["possibility"]
    assert matured["outcomes_imported"] == 1
    assert matured["forecasts_imported"] == 1

    cards = [x for x in fabric.scorecards() if x["producer"] == "psi-scenario-v1"]
    assert len(cards) == 1
    assert cards[0]["settled"] == 1
    assert cards[0]["successes"] == 1
    assert cards[0]["mean_brier"] == pytest.approx(((0.7 - 1.0) ** 2 + 0.2 ** 2 + 0.1 ** 2) / 3.0)

    row = fabric._conn.execute(
        "SELECT semantic_json FROM predictions WHERE producer='psi-scenario-v1' ORDER BY emitted_ts LIMIT 1"
    ).fetchone()
    prediction = json.loads(row["semantic_json"])
    assert prediction["metadata"]["input_semantics"] == "UNCALIBRATED_SCENARIO_SHARE"
    assert prediction["metadata"]["classification_threshold_return"] == pytest.approx(0.005)
    assert prediction["execution_authorized"] is False
    assert prediction["production_decision_authorized"] is False


def test_psi_learning_withholds_capture_when_exact_revision_is_not_clean(tmp_path, monkeypatch):
    import icarus_engine.learning_fabric as learning_module
    from icarus_engine.learning_fabric import LearningFabric

    monkeypatch.setattr(
        learning_module,
        "local_code_provenance",
        lambda: {"candidate_revision_eligible": False, "commit": None, "reason": "dirty tree"},
        raising=False,
    )

    class Psi:
        def status(self):
            return {"assets": {"NQ": {}}}
        def snapshot(self, asset=None):
            return {
                "asset": "NQ",
                "generated_at": "2026-10-01T14:00:00Z",
                "price": 100.0,
                "edge_state": {"state": "NO_EDGE"},
                "forecast_calibration_contract": {
                    "status": "ELIGIBLE_UNCALIBRATED",
                    "asset": "NQ",
                    "emitted_at": "2026-10-01T14:00:00Z",
                    "reference_price": 100.0,
                    "chart_minutes": 1,
                    "horizon_steps": 10,
                    "horizon_seconds": 600,
                    "classification_threshold_return": 0.005,
                    "cluster_shares": {"UP": 0.6, "FLAT": 0.2, "DOWN": 0.2},
                    "dominant_cluster": "UP",
                    "calibrated": False,
                    "execution_authorized": False,
                    "production_decision_authorized": False,
                },
            }

    fabric = LearningFabric(tmp_path)
    fabric.bind_native(possibility=Psi())
    out = fabric.harvest_native()["possibility"]
    assert out["status"] == "WITHHELD_REVISION"
    assert out["forecasts_imported"] == 0
    assert fabric._conn.execute("SELECT COUNT(*) FROM predictions WHERE producer='psi-scenario-v1'").fetchone()[0] == 0


def test_learning_snapshot_reports_psi_empirical_calibration_coverage(tmp_path):
    from icarus_engine.learning_fabric import LearningFabric

    snap = LearningFabric(tmp_path).snapshot()
    assert snap["coverage"]["possibility"] == "native_non_overlapping_scenario_calibration"
    assert "forecast_contract_required" not in snap["coverage"].values()


def _settled_calibration_case(fabric, *, start, n=40):
    for i in range(n):
        p = [0.2, 0.4, 0.6, 0.8][i % 4]
        emitted = start + timedelta(minutes=i * 10)
        pred = fabric.record_prediction({
            "producer": "cal-test",
            "asset": "NQ",
            "target": "event",
            "prediction": True,
            "probability": p,
            "emitted_at": _iso(emitted),
            "horizon_seconds": 60,
            "regime": "trend",
            "evidence_ids": [f"cal:{i}"],
            "source_commit": "a" * 40,
        })["prediction"]
        # Deliberately miscalibrated but monotone and stable across the
        # chronological holdout: 0.2/0.4 never occur, 0.6/0.8 always occur.
        # Isotonic calibration should therefore improve future top-label Brier.
        bucket = i % 4
        actual = bucket >= 2
        fabric.record_outcome({
            "prediction_id": pred["prediction_id"],
            "observed_at": pred["resolves_at"],
            "actual_value": actual,
            "evidence": [f"cal-outcome:{i}"],
        })


def test_shadow_calibrator_is_holdout_validated_and_never_rewrites_raw_probability(tmp_path):
    from icarus_engine.learning_fabric import LearningFabric

    fabric = LearningFabric(tmp_path)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    _settled_calibration_case(fabric, start=start, n=40)

    rebuilt = fabric.rebuild_shadow_calibrators(min_samples=30)
    assert rebuilt["validated"] == 1
    model = rebuilt["models"][0]
    assert model["status"] == "SHADOW_VALIDATED"
    assert model["train_count"] == 32
    assert model["validation_count"] == 8
    assert model["calibrated_validation_brier"] < model["raw_validation_brier"]
    assert model["execution_authorized"] is False
    assert model["production_decision_authorized"] is False

    emitted = start + timedelta(days=2)
    fresh = fabric.record_prediction({
        "producer": "cal-test",
        "asset": "NQ",
        "target": "event",
        "prediction": True,
        "probability": 0.6,
        "emitted_at": _iso(emitted),
        "horizon_seconds": 60,
        "regime": "trend",
        "evidence_ids": ["future:1"],
        "source_commit": "a" * 40,
    })["prediction"]

    stored = fabric._conn.execute(
        "SELECT probability,semantic_json FROM predictions WHERE prediction_id=?",
        (fresh["prediction_id"],),
    ).fetchone()
    assert stored["probability"] == pytest.approx(0.6)
    assert json.loads(stored["semantic_json"])["probability"] == pytest.approx(0.6)

    shadow = fabric.shadow_calibration(fresh["prediction_id"])
    assert shadow is not None
    assert shadow["raw_probability"] == pytest.approx(0.6)
    assert shadow["calibrated_probability"] != pytest.approx(0.6)
    assert shadow["status"] == "PENDING"
    assert shadow["execution_authorized"] is False
    assert shadow["production_decision_authorized"] is False


def test_shadow_calibration_refuses_temporal_leakage(tmp_path):
    from icarus_engine.learning_fabric import LearningFabric

    fabric = LearningFabric(tmp_path)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    _settled_calibration_case(fabric, start=start, n=40)
    rebuilt = fabric.rebuild_shadow_calibrators(min_samples=30)
    assert rebuilt["validated"] == 1
    cutoff = datetime.fromisoformat(
        rebuilt["models"][0]["training_cutoff"].replace("Z", "+00:00")
    )

    old = fabric.record_prediction({
        "producer": "cal-test",
        "asset": "NQ",
        "target": "event",
        "prediction": True,
        "probability": 0.6,
        "emitted_at": _iso(cutoff - timedelta(seconds=1)),
        "horizon_seconds": 60,
        "regime": "trend",
        "evidence_ids": ["old:1"],
        "source_commit": "a" * 40,
    })["prediction"]
    assert fabric.shadow_calibration(old["prediction_id"]) is None

    equal = fabric.record_prediction({
        "producer": "cal-test",
        "asset": "NQ",
        "target": "event",
        "prediction": True,
        "probability": 0.6,
        "emitted_at": _iso(cutoff),
        "horizon_seconds": 60,
        "regime": "trend",
        "evidence_ids": ["equal-cutoff:1"],
        "source_commit": "a" * 40,
    })["prediction"]
    assert fabric.shadow_calibration(equal["prediction_id"]) is None


def test_newer_rejected_calibrator_suppresses_older_validated_map(tmp_path):
    from icarus_engine.learning_fabric import LearningFabric

    fabric = LearningFabric(tmp_path)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    _settled_calibration_case(fabric, start=start, n=40)
    first = fabric.rebuild_shadow_calibrators(min_samples=30)
    assert first["validated"] == 1
    assert first["rejected"] == 0

    # Add a later regime of ten outcomes that reverses the earlier relationship.
    # The latest chronological holdout must reject the old mapping.
    late = start + timedelta(days=3)
    for i in range(10):
        p = [0.2, 0.4, 0.6, 0.8][i % 4]
        pred = fabric.record_prediction({
            "producer": "cal-test",
            "asset": "NQ",
            "target": "event",
            "prediction": True,
            "probability": p,
            "emitted_at": _iso(late + timedelta(minutes=i * 10)),
            "horizon_seconds": 60,
            "regime": "trend",
            "evidence_ids": [f"late-reversal:{i}"],
            "source_commit": "a" * 40,
        })["prediction"]
        fabric.record_outcome({
            "prediction_id": pred["prediction_id"],
            "observed_at": pred["resolves_at"],
            "actual_value": (i % 4) < 2,
            "evidence": [f"late-reversal-truth:{i}"],
        })

    second = fabric.rebuild_shadow_calibrators(min_samples=30)
    assert second["rejected"] == 1
    assert second["models"][0]["status"] == "SHADOW_REJECTED"
    cutoff = datetime.fromisoformat(
        second["models"][0]["training_cutoff"].replace("Z", "+00:00")
    )

    future = fabric.record_prediction({
        "producer": "cal-test",
        "asset": "NQ",
        "target": "event",
        "prediction": True,
        "probability": 0.6,
        "emitted_at": _iso(cutoff + timedelta(seconds=1)),
        "horizon_seconds": 60,
        "regime": "trend",
        "evidence_ids": ["after-rejection:1"],
        "source_commit": "a" * 40,
    })["prediction"]
    assert fabric.shadow_calibration(future["prediction_id"]) is None


def test_shadow_calibration_settlement_scores_raw_and_calibrated_probability(tmp_path):
    from icarus_engine.learning_fabric import LearningFabric

    fabric = LearningFabric(tmp_path)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    _settled_calibration_case(fabric, start=start, n=40)
    fabric.rebuild_shadow_calibrators(min_samples=30)

    pred = fabric.record_prediction({
        "producer": "cal-test",
        "asset": "NQ",
        "target": "event",
        "prediction": True,
        "probability": 0.6,
        "emitted_at": _iso(start + timedelta(days=2)),
        "horizon_seconds": 60,
        "regime": "trend",
        "evidence_ids": ["future:settle"],
        "source_commit": "a" * 40,
    })["prediction"]
    before = fabric.shadow_calibration(pred["prediction_id"])
    assert before["status"] == "PENDING"

    fabric.record_outcome({
        "prediction_id": pred["prediction_id"],
        "observed_at": pred["resolves_at"],
        "actual_value": True,
        "evidence": ["future:truth"],
    })
    after = fabric.shadow_calibration(pred["prediction_id"])
    assert after["status"] == "SETTLED"
    assert after["success"] is True
    assert after["raw_brier"] == pytest.approx((0.6 - 1.0) ** 2)
    assert after["calibrated_brier"] == pytest.approx((after["calibrated_probability"] - 1.0) ** 2)
    assert after["execution_authorized"] is False


def test_shadow_calibration_state_is_research_only_and_scope_specific(tmp_path):
    from icarus_engine.learning_fabric import LearningFabric

    fabric = LearningFabric(tmp_path)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    _settled_calibration_case(fabric, start=start, n=40)
    fabric.rebuild_shadow_calibrators(min_samples=30)

    state = fabric.shadow_calibration_state()
    assert state["model_count"] == 1
    assert state["validated_model_count"] == 1
    assert state["models"][0]["producer"] == "cal-test"
    assert state["models"][0]["asset"] == "NQ"
    assert state["models"][0]["regime"] == "trend"
    assert state["models"][0]["horizon_seconds"] == 60
    assert state["models"][0]["target"] == "event"
    assert state["authority"]["shadow_only"] is True
    assert state["authority"]["automatic_probability_rewrite"] is False
    assert state["execution_authorized"] is False
    assert state["production_decision_authorized"] is False


def _label_calibration_case(fabric, *, start, label, actual_pattern, n=32):
    for i in range(n):
        p = [0.4, 0.7][i % 2]
        emitted = start + timedelta(minutes=i * 5 + (0 if label == "up" else 1))
        probs = {label: p, ("down" if label == "up" else "up"): 1.0 - p}
        pred = fabric.record_prediction({
            "producer": "label-test",
            "asset": "NQ",
            "target": "class",
            "prediction": label,
            "probabilities": probs,
            "reference_value": 100.0,
            "emitted_at": _iso(emitted),
            "horizon_seconds": 60,
            "regime": "trend",
            "evidence_ids": [f"label:{label}:{i}"],
            "source_commit": "b" * 40,
        })["prediction"]
        success = bool(actual_pattern(i, p))
        actual = label if success else ("down" if label == "up" else "up")
        fabric.record_outcome({
            "prediction_id": pred["prediction_id"],
            "observed_at": pred["resolves_at"],
            "actual_value": actual,
            "evidence": [f"truth:{label}:{i}"],
        })


def test_shadow_calibration_is_conditioned_on_predicted_label(tmp_path):
    from icarus_engine.learning_fabric import LearningFabric

    fabric = LearningFabric(tmp_path)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)

    # UP and DOWN have opposite probability→success relationships. Pooling these
    # labels would erase the asymmetry and produce a scientifically invalid map.
    _label_calibration_case(
        fabric, start=start, label="up",
        actual_pattern=lambda i, p: (p >= 0.7),
    )
    _label_calibration_case(
        fabric, start=start + timedelta(days=1), label="down",
        actual_pattern=lambda i, p: (p < 0.7),
    )

    rebuilt = fabric.rebuild_shadow_calibrators(min_samples=30)
    models = {(m["prediction_label"], m["status"]): m for m in rebuilt["models"]}
    assert any(label == "up" for label, _ in models)
    assert any(label == "down" for label, _ in models)

    state = fabric.shadow_calibration_state()
    labels = {m["prediction_label"] for m in state["models"]}
    assert labels == {"up", "down"}


def test_shadow_assignment_uses_only_matching_prediction_label(tmp_path):
    from icarus_engine.learning_fabric import LearningFabric

    fabric = LearningFabric(tmp_path)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)

    # Give UP and DOWN opposite empirical maps.
    _label_calibration_case(
        fabric, start=start, label="up",
        actual_pattern=lambda i, p: (p >= 0.7),
    )
    _label_calibration_case(
        fabric, start=start + timedelta(days=1), label="down",
        actual_pattern=lambda i, p: (p < 0.7),
    )
    rebuilt = fabric.rebuild_shadow_calibrators(min_samples=30)
    assert rebuilt["validated"] >= 1

    future = start + timedelta(days=3)
    up = fabric.record_prediction({
        "producer": "label-test",
        "asset": "NQ",
        "target": "class",
        "prediction": "up",
        "probabilities": {"up": 0.7, "down": 0.3},
        "reference_value": 100.0,
        "emitted_at": _iso(future),
        "horizon_seconds": 60,
        "regime": "trend",
        "evidence_ids": ["future:up"],
        "source_commit": "b" * 40,
    })["prediction"]
    down = fabric.record_prediction({
        "producer": "label-test",
        "asset": "NQ",
        "target": "class",
        "prediction": "down",
        "probabilities": {"up": 0.3, "down": 0.7},
        "reference_value": 100.0,
        "emitted_at": _iso(future + timedelta(minutes=1)),
        "horizon_seconds": 60,
        "regime": "trend",
        "evidence_ids": ["future:down"],
        "source_commit": "b" * 40,
    })["prediction"]

    up_shadow = fabric.shadow_calibration(up["prediction_id"])
    down_shadow = fabric.shadow_calibration(down["prediction_id"])
    assert up_shadow is not None
    assert down_shadow is not None
    assert up_shadow["prediction_label"] == "up"
    assert down_shadow["prediction_label"] == "down"
    assert up_shadow["calibrator_id"] != down_shadow["calibrator_id"]


def test_existing_calibration_schema_migrates_prediction_label_fail_closed(tmp_path):
    import sqlite3
    from icarus_engine.learning_fabric import LearningFabric

    research = tmp_path / "research"
    research.mkdir(parents=True)
    db = research / "learning.sqlite3"
    con = sqlite3.connect(db)
    con.executescript("""
        CREATE TABLE calibration_models (
            calibrator_id TEXT PRIMARY KEY,
            producer TEXT NOT NULL,
            asset TEXT NOT NULL,
            regime TEXT NOT NULL,
            horizon_seconds INTEGER NOT NULL,
            target TEXT NOT NULL,
            status TEXT NOT NULL,
            train_count INTEGER NOT NULL,
            validation_count INTEGER NOT NULL,
            fit_cutoff TEXT NOT NULL,
            training_cutoff TEXT NOT NULL,
            model_json TEXT NOT NULL,
            raw_validation_brier REAL NOT NULL,
            calibrated_validation_brier REAL NOT NULL,
            source_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(producer,asset,regime,horizon_seconds,target,source_hash)
        );
    """)
    con.commit()
    con.close()

    fabric = LearningFabric(tmp_path)
    cols = {
        row["name"] for row in fabric._conn.execute("PRAGMA table_info(calibration_models)").fetchall()
    }
    assert "prediction_label" in cols
    state = fabric.shadow_calibration_state()
    assert state["execution_authorized"] is False
    assert state["authority"]["automatic_probability_rewrite"] is False


def _revision_calibration_case(fabric, *, start, source_commit, actual_pattern, n=32):
    for i in range(n):
        p = [0.4, 0.7][i % 2]
        emitted = start + timedelta(minutes=i * 5)
        pred = fabric.record_prediction({
            "producer": "revision-test",
            "asset": "NQ",
            "target": "class",
            "prediction": "up",
            "probabilities": {"up": p, "down": 1.0 - p},
            "reference_value": 100.0,
            "emitted_at": _iso(emitted),
            "horizon_seconds": 60,
            "regime": "trend",
            "evidence_ids": [f"revision:{source_commit[:8]}:{i}"],
            "source_commit": source_commit,
        })["prediction"]
        success = bool(actual_pattern(i, p))
        fabric.record_outcome({
            "prediction_id": pred["prediction_id"],
            "observed_at": pred["resolves_at"],
            "actual_value": "up" if success else "down",
            "evidence": [f"truth:{source_commit[:8]}:{i}"],
        })


def test_shadow_calibration_is_conditioned_on_exact_source_commit(tmp_path):
    from icarus_engine.learning_fabric import LearningFabric

    fabric = LearningFabric(tmp_path)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    old_sha = "a" * 40
    new_sha = "b" * 40

    _revision_calibration_case(
        fabric, start=start, source_commit=old_sha,
        actual_pattern=lambda i, p: (p >= 0.7),
    )
    _revision_calibration_case(
        fabric, start=start + timedelta(days=1), source_commit=new_sha,
        actual_pattern=lambda i, p: (p < 0.7),
    )

    rebuilt = fabric.rebuild_shadow_calibrators(min_samples=30)
    models = [m for m in rebuilt["models"] if m["producer"] == "revision-test"]
    assert {m["source_commit"] for m in models} == {old_sha, new_sha}
    assert all(m["prediction_label"] == "up" for m in models)


def test_shadow_assignment_never_crosses_code_revision(tmp_path):
    from icarus_engine.learning_fabric import LearningFabric

    fabric = LearningFabric(tmp_path)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    old_sha = "a" * 40
    new_sha = "b" * 40

    _revision_calibration_case(
        fabric, start=start, source_commit=old_sha,
        actual_pattern=lambda i, p: (p >= 0.7),
    )
    _revision_calibration_case(
        fabric, start=start + timedelta(days=1), source_commit=new_sha,
        actual_pattern=lambda i, p: (p < 0.7),
    )
    fabric.rebuild_shadow_calibrators(min_samples=30)

    future = start + timedelta(days=3)
    old_pred = fabric.record_prediction({
        "producer": "revision-test",
        "asset": "NQ",
        "target": "class",
        "prediction": "up",
        "probabilities": {"up": 0.7, "down": 0.3},
        "reference_value": 100.0,
        "emitted_at": _iso(future),
        "horizon_seconds": 60,
        "regime": "trend",
        "evidence_ids": ["future:old"],
        "source_commit": old_sha,
    })["prediction"]
    new_pred = fabric.record_prediction({
        "producer": "revision-test",
        "asset": "NQ",
        "target": "class",
        "prediction": "up",
        "probabilities": {"up": 0.7, "down": 0.3},
        "reference_value": 100.0,
        "emitted_at": _iso(future + timedelta(minutes=1)),
        "horizon_seconds": 60,
        "regime": "trend",
        "evidence_ids": ["future:new"],
        "source_commit": new_sha,
    })["prediction"]

    old_shadow = fabric.shadow_calibration(old_pred["prediction_id"])
    new_shadow = fabric.shadow_calibration(new_pred["prediction_id"])
    assert old_shadow is not None
    assert new_shadow is not None
    assert old_shadow["source_commit"] == old_sha
    assert new_shadow["source_commit"] == new_sha
    assert old_shadow["calibrator_id"] != new_shadow["calibrator_id"]
    assert old_shadow["calibrated_probability"] != pytest.approx(new_shadow["calibrated_probability"])


def test_legacy_unversioned_calibrator_schema_migrates_fail_closed(tmp_path):
    import sqlite3
    from icarus_engine.learning_fabric import LearningFabric

    research = tmp_path / "research"
    research.mkdir(parents=True)
    db = research / "learning.sqlite3"
    con = sqlite3.connect(db)
    con.executescript("""
        CREATE TABLE calibration_models (
            calibrator_id TEXT PRIMARY KEY,
            producer TEXT NOT NULL,
            asset TEXT NOT NULL,
            regime TEXT NOT NULL,
            horizon_seconds INTEGER NOT NULL,
            target TEXT NOT NULL,
            prediction_label TEXT NOT NULL DEFAULT '',
            status TEXT NOT NULL,
            train_count INTEGER NOT NULL,
            validation_count INTEGER NOT NULL,
            fit_cutoff TEXT NOT NULL,
            training_cutoff TEXT NOT NULL,
            model_json TEXT NOT NULL,
            raw_validation_brier REAL NOT NULL,
            calibrated_validation_brier REAL NOT NULL,
            source_hash TEXT NOT NULL,
            created_at TEXT NOT NULL,
            UNIQUE(producer,asset,regime,horizon_seconds,target,source_hash)
        );
    """)
    con.commit()
    con.close()

    fabric = LearningFabric(tmp_path)
    cols = {
        row["name"] for row in fabric._conn.execute("PRAGMA table_info(calibration_models)").fetchall()
    }
    assert "source_commit" in cols
    assert fabric._conn.execute(
        "SELECT COUNT(*) FROM calibration_models WHERE source_commit<>''"
    ).fetchone()[0] == 0


def test_shadow_calibrator_retires_on_post_validation_drift(tmp_path):
    from icarus_engine.learning_fabric import LearningFabric

    fabric = LearningFabric(tmp_path)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rebuilt = None
    _settled_calibration_case(fabric, start=start, n=40)
    rebuilt = fabric.rebuild_shadow_calibrators(min_samples=30)
    model = rebuilt["models"][0]
    assert model["status"] == "SHADOW_VALIDATED"
    calibrator_id = model["calibrator_id"]
    cutoff = datetime.fromisoformat(model["training_cutoff"].replace("Z", "+00:00"))

    # Hold the validated revision stable and collect true OOS evidence. The
    # historical map sends 0.6 toward event=True; the later world reverses.
    for i in range(8):
        pred = fabric.record_prediction({
            "producer": "cal-test",
            "asset": "NQ",
            "target": "event",
            "prediction": True,
            "probability": 0.6,
            "emitted_at": _iso(cutoff + timedelta(minutes=i + 1)),
            "horizon_seconds": 60,
            "regime": "trend",
            "evidence_ids": [f"drift:{i}"],
            "source_commit": "a" * 40,
        })["prediction"]
        shadow = fabric.shadow_calibration(pred["prediction_id"])
        assert shadow is not None
        assert shadow["calibrator_id"] == calibrator_id
        fabric.record_outcome({
            "prediction_id": pred["prediction_id"],
            "observed_at": pred["resolves_at"],
            "actual_value": False,
            "evidence": [f"drift-truth:{i}"],
        })

    drift = fabric.evaluate_shadow_calibrator_drift(
        min_samples=8, recent_window=8, degradation_margin=0.05
    )
    assert drift["retired"] == 1
    row = next(x for x in drift["models"] if x["calibrator_id"] == calibrator_id)
    assert row["action"] == "DRIFT_RETIRED"
    assert row["calibrated_brier"] > row["raw_brier"] + 0.05

    state = fabric.shadow_calibration_state()
    assert state["drift_retired_model_count"] == 1
    retired = next(x for x in state["models"] if x["calibrator_id"] == calibrator_id)
    assert retired["status"] == "DRIFT_RETIRED"
    assert retired["retired_at"] is not None
    assert "out-of-sample" in retired["retirement_reason"].lower()

    future = fabric.record_prediction({
        "producer": "cal-test",
        "asset": "NQ",
        "target": "event",
        "prediction": True,
        "probability": 0.6,
        "emitted_at": _iso(cutoff + timedelta(hours=1)),
        "horizon_seconds": 60,
        "regime": "trend",
        "evidence_ids": ["after-drift-retirement"],
        "source_commit": "a" * 40,
    })["prediction"]
    assert fabric.shadow_calibration(future["prediction_id"]) is None


def test_shadow_calibrator_survives_when_oos_calibration_is_not_worse(tmp_path):
    from icarus_engine.learning_fabric import LearningFabric

    fabric = LearningFabric(tmp_path)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    _settled_calibration_case(fabric, start=start, n=40)
    model = fabric.rebuild_shadow_calibrators(min_samples=30)["models"][0]
    cutoff = datetime.fromisoformat(model["training_cutoff"].replace("Z", "+00:00"))

    for i in range(8):
        pred = fabric.record_prediction({
            "producer": "cal-test",
            "asset": "NQ",
            "target": "event",
            "prediction": True,
            "probability": 0.6,
            "emitted_at": _iso(cutoff + timedelta(minutes=i + 1)),
            "horizon_seconds": 60,
            "regime": "trend",
            "evidence_ids": [f"stable:{i}"],
            "source_commit": "a" * 40,
        })["prediction"]
        fabric.record_outcome({
            "prediction_id": pred["prediction_id"],
            "observed_at": pred["resolves_at"],
            "actual_value": True,
            "evidence": [f"stable-truth:{i}"],
        })

    drift = fabric.evaluate_shadow_calibrator_drift(
        min_samples=8, recent_window=8, degradation_margin=0.05
    )
    assert drift["retired"] == 0
    state = fabric.shadow_calibration_state()
    assert state["drift_retired_model_count"] == 0
    assert state["models"][0]["status"] == "SHADOW_VALIDATED"


def test_refresh_batch_holds_calibrator_stable_for_oos_measurement(tmp_path):
    from icarus_engine.learning_fabric import LearningFabric

    fabric = LearningFabric(tmp_path)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    _settled_calibration_case(fabric, start=start, n=40)
    first = fabric.rebuild_shadow_calibrators(min_samples=30)
    first_id = first["models"][0]["calibrator_id"]
    cutoff = datetime.fromisoformat(first["models"][0]["training_cutoff"].replace("Z", "+00:00"))

    for i in range(5):
        pred = fabric.record_prediction({
            "producer": "cal-test",
            "asset": "NQ",
            "target": "event",
            "prediction": True,
            "probability": 0.6,
            "emitted_at": _iso(cutoff + timedelta(minutes=i + 1)),
            "horizon_seconds": 60,
            "regime": "trend",
            "evidence_ids": [f"refresh:{i}"],
            "source_commit": "a" * 40,
        })["prediction"]
        fabric.record_outcome({
            "prediction_id": pred["prediction_id"],
            "observed_at": pred["resolves_at"],
            "actual_value": False,
            "evidence": [f"refresh-truth:{i}"],
        })

    held = fabric.rebuild_shadow_calibrators(min_samples=30, refresh_samples=12)
    assert held["built"] == 0
    assert held["awaiting_refresh"] == 1
    state = fabric.shadow_calibration_state()
    assert state["models"][0]["calibrator_id"] == first_id


def _overlapping_calibration_case(fabric, *, start, n, spacing_seconds, horizon_seconds=60):
    for i in range(n):
        # Pair probabilities so a 50% overlap purge still preserves both
        # confidence levels instead of aliasing onto only one phase.
        p = 0.4 if (i // 2) % 2 == 0 else 0.7
        emitted = start + timedelta(seconds=i * spacing_seconds)
        pred = fabric.record_prediction({
            "producer": "overlap-test",
            "asset": "NQ",
            "target": "event",
            "prediction": True,
            "probability": p,
            "emitted_at": _iso(emitted),
            "horizon_seconds": horizon_seconds,
            "regime": "trend",
            "evidence_ids": [f"overlap:{i}"],
            "source_commit": "c" * 40,
        })["prediction"]
        fabric.record_outcome({
            "prediction_id": pred["prediction_id"],
            "observed_at": pred["resolves_at"],
            "actual_value": p >= 0.7,
            "evidence": [f"overlap-truth:{i}"],
        })


def test_shadow_calibration_purges_overlapping_forecast_windows(tmp_path):
    from icarus_engine.learning_fabric import LearningFabric

    fabric = LearningFabric(tmp_path)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    _overlapping_calibration_case(
        fabric, start=start, n=60, spacing_seconds=30, horizon_seconds=60
    )

    rebuilt = fabric.rebuild_shadow_calibrators(min_samples=30)
    assert rebuilt["validated"] == 1
    model = rebuilt["models"][0]
    assert model["raw_sample_count"] == 60
    assert model["effective_sample_count"] == 30
    assert model["overlap_purged"] == 30
    assert model["train_count"] == 24
    assert model["validation_count"] == 6
    assert rebuilt["overlap_purged_total"] == 30


def test_overlap_purge_blocks_pseudoreplicated_minimum_sample_gate(tmp_path):
    from icarus_engine.learning_fabric import LearningFabric

    fabric = LearningFabric(tmp_path)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    _overlapping_calibration_case(
        fabric, start=start, n=40, spacing_seconds=10, horizon_seconds=60
    )

    rebuilt = fabric.rebuild_shadow_calibrators(min_samples=30)
    assert rebuilt["built"] == 0
    assert rebuilt["overlap_purged_total"] >= 30
    reason = next(iter(rebuilt["skipped"].values()))
    assert "effective non-overlapping" in reason.lower()


def test_drift_retirement_requires_non_overlapping_oos_evidence(tmp_path):
    from icarus_engine.learning_fabric import LearningFabric

    fabric = LearningFabric(tmp_path)
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    _settled_calibration_case(fabric, start=start, n=40)
    model = fabric.rebuild_shadow_calibrators(min_samples=30)["models"][0]
    cutoff = datetime.fromisoformat(model["training_cutoff"].replace("Z", "+00:00"))

    # Eight bad forecasts, but all lie inside only two independent 60-second
    # target windows. They must not be allowed to retire a calibrator as if n=8.
    for i in range(8):
        pred = fabric.record_prediction({
            "producer": "cal-test",
            "asset": "NQ",
            "target": "event",
            "prediction": True,
            "probability": 0.6,
            "emitted_at": _iso(cutoff + timedelta(minutes=1, seconds=i * 10)),
            "horizon_seconds": 60,
            "regime": "trend",
            "evidence_ids": [f"oos-overlap:{i}"],
            "source_commit": "a" * 40,
        })["prediction"]
        assert fabric.shadow_calibration(pred["prediction_id"]) is not None
        fabric.record_outcome({
            "prediction_id": pred["prediction_id"],
            "observed_at": pred["resolves_at"],
            "actual_value": False,
            "evidence": [f"oos-overlap-truth:{i}"],
        })

    drift = fabric.evaluate_shadow_calibrator_drift(
        min_samples=8, recent_window=8, degradation_margin=0.05
    )
    assert drift["retired"] == 0
    row = next(x for x in drift["models"] if x["calibrator_id"] == model["calibrator_id"])
    assert row["action"] == "INSUFFICIENT_OOS"
    assert row["raw_sample_count"] == 8
    assert row["effective_sample_count"] == 2
    assert row["overlap_purged"] == 6
    assert fabric.shadow_calibration_state()["drift_retired_model_count"] == 0


def _write_intake_manifest(path: Path, rows: list[dict[str, object]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = [
        "index","sha256","canonical_filename","duplicate_copies",
        "all_observed_filenames","bytes","format","artifact_class","symbol",
        "timeframe","chart_type","rows","first_or_trading_range",
        "last_or_backtesting_range","last_trade_number","net_profit_usd",
        "max_drawdown_intrabar_usd","notes",
    ]
    import csv
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=header)
        writer.writeheader()
        for i, row in enumerate(rows):
            writer.writerow({**{key: "" for key in header}, "index": i, **row})
    return path


def test_manifest_unique_strategy_report_links_historical_trade_configuration(tmp_path):
    import hashlib
    from icarus_engine.learning_fabric import LearningFabric

    trade_path = _trade_list(
        tmp_path / "history" / "drop" / "THE_PULSE_OF_ICARUS_CME_MINI_NQ1!_2026-09-30.csv"
    )
    trade_sha = hashlib.sha256(trade_path.read_bytes()).hexdigest()
    report_sha = "d" * 64
    _write_intake_manifest(
        tmp_path / "history" / "EXPORT_INTAKE_MANIFEST.csv",
        [
            {
                "sha256": trade_sha,
                "canonical_filename": trade_path.name,
                "all_observed_filenames": trade_path.name,
                "format": "csv",
                "artifact_class": "trade_list",
                "symbol": "CME_MINI:NQ1!",
                "rows": 4,
                "last_trade_number": 2,
                "first_or_trading_range": "2024-06-03 10:20",
                "last_or_backtesting_range": "2024-06-03 12:20",
            },
            {
                "sha256": report_sha,
                "canonical_filename": "THE_PULSE_OF_ICARUS_CME_MINI_NQ1!_2026-09-30.xlsx",
                "format": "xlsx",
                "artifact_class": "strategy_report_xlsx",
                "symbol": "CME_MINI:NQ1!",
                "timeframe": "20 minutes",
                "chart_type": "Heikin Ashi",
                "rows": 4,
                "last_trade_number": 2,
                "net_profit_usd": "700427.0",
                "max_drawdown_intrabar_usd": "165324.0",
                "notes": "commission=2; slippage=0 ticks; execution=On bar close; order_delay=One tick",
            },
        ],
    )

    fabric = LearningFabric(tmp_path)
    scan = fabric.scan_history()
    assert scan["files_seen"] == 1
    dataset = fabric.dataset(scan["dataset_ids"][0])
    assert dataset["artifact_class"] == "trade_list"
    result = fabric.backfill_dataset(dataset["dataset_id"])
    assert result["status"] == "complete"

    state = fabric.experience_state()
    assert state["by_configuration"] == []
    assert state["artifact_scoped_count"] == 2
    assert state["unscoped_count"] == 0
    assert len(state["by_artifact_configuration"]) == 1
    card = state["by_artifact_configuration"][0]
    assert card["asset"] == "NQ"
    assert card["count"] == 2
    assert card["timeframe"] == "20m"
    assert card["chart_type"] == "Heikin Ashi"
    assert card["strategy_report_sha256"] == report_sha
    assert card["strategy_report_filename"].endswith(".xlsx")
    assert card["linkage_rule"] == "UNIQUE_SYMBOL_ROWS_LAST_TRADE"
    assert len(card["artifact_configuration_fingerprint"]) == 64
    assert card["provenance_quality"] == "MANIFEST_UNIQUE_STRATEGY_REPORT_LINK"
    assert card["execution_authorized"] is False
    assert card["production_decision_authorized"] is False

    rows = fabric._conn.execute(
        "SELECT metadata_json FROM experiences ORDER BY experience_id"
    ).fetchall()
    for row in rows:
        meta = json.loads(row["metadata_json"])
        assert meta["artifact_configuration_fingerprint"] == card["artifact_configuration_fingerprint"]
        assert meta["provenance_quality"] == "MANIFEST_UNIQUE_STRATEGY_REPORT_LINK"
        assert meta["strategy_report_sha256"] == report_sha
        assert "strategy_fingerprint" not in meta


def test_manifest_ambiguous_strategy_report_linkage_fails_closed(tmp_path):
    import hashlib
    from icarus_engine.learning_fabric import LearningFabric

    trade_path = _trade_list(tmp_path / "history" / "drop" / "THE_PULSE_NQ.csv")
    trade_sha = hashlib.sha256(trade_path.read_bytes()).hexdigest()
    common = {
        "format": "xlsx",
        "artifact_class": "strategy_report_xlsx",
        "symbol": "CME_MINI:NQ1!",
        "timeframe": "20 minutes",
        "rows": 4,
        "last_trade_number": 2,
    }
    _write_intake_manifest(
        tmp_path / "history" / "EXPORT_INTAKE_MANIFEST.csv",
        [
            {
                "sha256": trade_sha,
                "canonical_filename": trade_path.name,
                "format": "csv",
                "artifact_class": "trade_list",
                "symbol": "CME_MINI:NQ1!",
                "rows": 4,
                "last_trade_number": 2,
            },
            {
                **common,
                "sha256": "a" * 64,
                "canonical_filename": "candidate-a.xlsx",
                "chart_type": "Candles",
            },
            {
                **common,
                "sha256": "b" * 64,
                "canonical_filename": "candidate-b.xlsx",
                "chart_type": "Heikin Ashi",
            },
        ],
    )

    fabric = LearningFabric(tmp_path)
    scan = fabric.scan_history()
    dataset = fabric.dataset(scan["dataset_ids"][0])
    fabric.backfill_dataset(dataset["dataset_id"])

    state = fabric.experience_state()
    assert state["by_configuration"] == []
    assert state["by_artifact_configuration"] == []
    assert state["artifact_scoped_count"] == 0
    assert state["unscoped_count"] == 2
    row = fabric._conn.execute(
        "SELECT metadata_json FROM experiences ORDER BY experience_id LIMIT 1"
    ).fetchone()
    meta = json.loads(row["metadata_json"])
    assert "artifact_configuration_fingerprint" not in meta
    assert meta["manifest_linkage_status"] == "AMBIGUOUS"
    assert meta["manifest_linkage_candidates"] == 2


def test_manifest_report_linkage_never_promotes_to_runtime_strategy_configuration(tmp_path):
    from icarus_engine.learning_fabric import LearningFabric

    fabric = LearningFabric(tmp_path)
    fabric.record_experience({
        "source": "historical_trade_list",
        "source_record_id": "manifest-linked",
        "asset": "NQ",
        "direction": "long",
        "entry_at": "2024-06-03T10:20:00Z",
        "exit_at": "2024-06-03T11:00:00Z",
        "qty": 1,
        "entry_price": 100.0,
        "exit_price": 101.0,
        "pnl": 50.0,
        "metadata": {
            "artifact_configuration_fingerprint": "f" * 64,
            "provenance_quality": "MANIFEST_UNIQUE_STRATEGY_REPORT_LINK",
            "timeframe": "20m",
            "chart_type": "Heikin Ashi",
            "strategy_report_sha256": "e" * 64,
            "strategy_report_filename": "report.xlsx",
            "linkage_rule": "UNIQUE_SYMBOL_ROWS_LAST_TRADE",
        },
    })
    state = fabric.experience_state()
    assert state["by_configuration"] == []
    assert state["artifact_scoped_count"] == 1
    assert len(state["by_artifact_configuration"]) == 1
    assert state["by_artifact_configuration"][0]["artifact_configuration_fingerprint"] == "f" * 64
