from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from icarus_engine.commissioning import CommissioningEngine


class Port:
    def __init__(self):
        self.price = 100.0
        self.runners = {"NQ": SimpleNamespace()}
    def status(self):
        return {"assets": [{"symbol": "NQ", "price": self.price}]}


class Chronofold:
    def __init__(self):
        self.tau = 0.0
        self.expected = 0.01
    def status(self):
        return {"authority": {"execution_authorized": False}}
    def snapshot(self, asset):
        self.tau += 1.0
        return {
            "asset": asset,
            "authority": {"execution_authorized": False, "broker_authority": False},
            "truth_contract": {"future_data_used": False},
            "chronon": {"market_proper_time": self.tau},
            "time_boundary": {
                "event_time": self.tau,
                "retrieval_time": self.tau,
                "event_time_source": "test",
                "causal_integrity": "PASS",
                "availability_time_exact": False,
            },
            "multiverse": {
                "horizon_chronons": 3,
                "expected_return": self.expected,
                "p05_return": -0.02,
                "p50_return": 0.008,
                "p95_return": 0.03,
                "cluster_weights": {"UP": 0.62, "FLAT": 0.18, "DOWN": 0.20},
            },
            "counterfactual_shadows": [
                {"removed_force": "causal_pressure", "shadow_expected_return": 0.006},
                {"removed_force": "latent_pressure", "shadow_expected_return": 0.004},
            ],
            "epistemic_unknown_mass": 0.2,
            "phase_transition": {"state": "STABLE"},
            "koopman": {"mode": "PERSISTENT"},
            "geometry": {"curvature": 0.1},
            "macro_field": {"stress": 0.2},
            "market_potential": {"energy": 0.3},
            "causal_cone": {"incoming_pressure": 0.4},
            "gnc": {"guidance": "LONG_BIAS", "confidence": 0.4},
        }


def test_capture_and_settle_are_append_only_and_hash_chained(tmp_path: Path):
    port = Port()
    cf = Chronofold()
    engine = CommissioningEngine(tmp_path, port, cf, capture_step_chronons=1.0, min_promotion_samples=20)

    captured = engine.capture("NQ")
    assert captured["captured"] is True
    pid = captured["prediction"]["prediction_id"]
    assert captured["prediction"]["authority"]["execution_authorized"] is False
    assert captured["prediction"]["record_hash"]

    port.price = 102.0
    # target is start tau + 3, so advance to target before settlement.
    cf.snapshot("NQ")
    cf.snapshot("NQ")
    settled = engine.settle_ready("NQ")
    assert settled["settled"] == 1
    out = settled["outcomes"][0]
    assert out["prediction_id"] == pid
    assert out["settle_price"] == 102.0
    assert out["authority"]["broker_authority"] is False
    assert out["record_hash"]

    prediction_lines = engine.prediction_path.read_text(encoding="utf-8").splitlines()
    outcome_lines = engine.outcome_path.read_text(encoding="utf-8").splitlines()
    assert len(prediction_lines) == 1
    assert len(outcome_lines) == 1

    reloaded = CommissioningEngine(tmp_path, port, cf)
    status = reloaded.status("NQ")
    assert status["ledger"]["integrity_errors"] == []
    assert status["ledger"]["predictions"] == 1
    assert status["ledger"]["settled"] == 1


def test_duplicate_chronon_capture_is_suppressed(tmp_path: Path):
    port = Port()
    cf = Chronofold()
    engine = CommissioningEngine(tmp_path, port, cf, capture_step_chronons=5.0)
    first = engine.capture("NQ")
    second = engine.capture("NQ")
    assert first["captured"] is True
    assert second["captured"] is False
    assert second["reason"] == "chronon_step_not_reached"


def test_metrics_calibration_variants_and_promotion_never_arm_execution(tmp_path: Path):
    port = Port()
    cf = Chronofold()
    engine = CommissioningEngine(tmp_path, port, cf, capture_step_chronons=0.05, min_promotion_samples=20)

    for i in range(24):
        pred = engine.capture("NQ", force=True)["prediction"]
        port.price = pred["start_price"] * (1.01 if i % 3 else 0.995)
        cf.snapshot("NQ")
        cf.snapshot("NQ")
        engine.settle_ready("NQ")

    metrics = engine.metrics("NQ")
    assert metrics["settled_predictions"] >= 20
    assert 0 <= metrics["direction_accuracy"] <= 1
    assert metrics["rmse"] >= 0
    assert metrics["brier_score"] >= 0
    assert metrics["variants"]
    gate = engine.promotion_gate("NQ")
    assert gate["execution_authorized"] is False
    assert gate["production_decision_authorized"] is False
    assert gate["broker_authority"] is False


def test_replay_contract_and_adversarial_matrix_are_fail_closed(tmp_path: Path):
    port = Port()
    cf = Chronofold()
    engine = CommissioningEngine(tmp_path, port, cf)
    engine.capture("NQ", force=True)
    replay = engine.replay_contract()
    assert replay["future_data_allowed"] is False
    assert replay["execution_authorized"] is False
    stress = engine.adversarial_matrix("NQ")
    assert len(stress) == 4
    assert all(row["contract_pass"] is True for row in stress)


def test_corrupt_ledger_is_reported_and_blocks_research_promotion(tmp_path: Path):
    port = Port()
    cf = Chronofold()
    engine = CommissioningEngine(tmp_path, port, cf)
    engine.capture("NQ", force=True)
    engine.prediction_path.write_text(engine.prediction_path.read_text(encoding="utf-8") + "{bad json\n", encoding="utf-8")
    reloaded = CommissioningEngine(tmp_path, port, cf, min_promotion_samples=20)
    status = reloaded.status()
    assert status["status"] == "degraded"
    assert status["ledger"]["integrity_errors"]
    assert status["promotion_gate"]["research_influence_eligible"] is False


def test_truth_or_authority_violation_refuses_capture(tmp_path: Path):
    port = Port()
    cf = Chronofold()
    original = cf.snapshot
    def bad(asset):
        row = original(asset)
        row["truth_contract"]["future_data_used"] = True
        return row
    cf.snapshot = bad
    engine = CommissioningEngine(tmp_path, port, cf)
    with pytest.raises(RuntimeError, match="future-data"):
        engine.capture("NQ")
