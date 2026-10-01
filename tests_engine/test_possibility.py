from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from icarus_engine.possibility import Feature, PossibilityEngine, _weighted


class Tick:
    def __init__(self, price: float, size: int, side: str):
        self.price = price
        self.size = size
        self.side = side


class Feed:
    def trades(self, ticker, limit=500):
        rows = []
        for i in range(180):
            side = "B" if i % 5 else "A"
            rows.append(Tick(20000.0 + i * 0.02, 3 + (i % 4), side))
        return rows[-limit:]

    def depth_events(self, ticker, *, schema="mbp-10", limit=120):
        rows = []
        for i in range(40):
            mid = 20000.0 + i * 0.01
            levels = [
                {
                    "bid_px": mid - 0.25 - level * 0.25,
                    "ask_px": mid + 0.25 + level * 0.25,
                    "bid_sz": 30 - level,
                    "ask_sz": 10 + level,
                    "bid_ct": 3,
                    "ask_ct": 2,
                }
                for level in range(10)
            ]
            rows.append({"levels": levels, "ts_event": 1000 + i})
        return rows[-limit:]


class Port:
    def __init__(self):
        self.runners = {
            "NQ": SimpleNamespace(feed=Feed(), spec=SimpleNamespace(ticker="NQ.v.0")),
            "ES": SimpleNamespace(feed=Feed(), spec=SimpleNamespace(ticker="ES.v.0")),
        }
        self._price = 20000.0

    def status(self):
        return {
            "assets": [
                {
                    "symbol": "NQ",
                    "price": self._price,
                    "warm": True,
                    "paused": False,
                    "state": {"rate_regime": 0.82, "rate_regime_str": "STRONG", "pulse_l": 0.76, "pulse_s": 0.18},
                },
                {
                    "symbol": "ES",
                    "price": 6800.0,
                    "warm": True,
                    "paused": False,
                    "state": {"rate_regime": 0.78, "rate_regime_str": "STRONG", "pulse_l": 0.70, "pulse_s": 0.20},
                },
            ]
        }


def _seed(engine: PossibilityEngine) -> None:
    nq = engine._history["NQ"]
    es = engine._history["ES"]
    for i in range(40):
        nq_price = 20000.0 + i * 1.5
        es_price = 6800.0 + i * 0.45
        nq.append(
            {
                "ts": float(i),
                "price": nq_price,
                "ret": 0.00008 + (i % 4) * 0.00001,
                "pulse": 0.4,
                "regime": 0.8,
            }
        )
        es.append(
            {
                "ts": float(i),
                "price": es_price,
                "ret": 0.00007 + ((i + 1) % 4) * 0.00001,
                "pulse": 0.35,
                "regime": 0.75,
            }
        )


def test_empty_port_fails_closed():
    class Empty:
        runners = {}

        def status(self):
            return {"assets": []}

    out = PossibilityEngine(Empty()).snapshot()
    assert out["edge_state"]["state"] == "NO_EDGE"
    assert out["authority"]["execution_authorized"] is False
    assert out["authority"]["production_decision_authorized"] is False


def test_external_evidence_is_bounded_and_research_only():
    engine = PossibilityEngine(Port())
    result = engine.ingest_external(
        "NQ",
        {
            "gamma_pressure": {"value": 0.7, "confidence": 0.8},
            "cta_pressure": 0.5,
            "liquidation_pressure": 0.3,
        },
        source="unit-test",
        ttl_seconds=60,
    )
    assert result["execution_authorized"] is False
    assert result["production_decision_authorized"] is False
    assert result["stored"]["gamma_pressure"]["value"] == pytest.approx(0.7)

    with pytest.raises(ValueError):
        engine.ingest_external("NQ", {"made_up_force": 1.0}, source="unit-test")
    with pytest.raises(ValueError):
        engine.ingest_external("NQ", {"gamma_pressure": 1.1}, source="unit-test")


def test_psi_surface_observed_microstructure_and_future_space():
    engine = PossibilityEngine(Port(), scenarios=192)
    _seed(engine)
    engine.ingest_external(
        "NQ",
        {
            "gamma_pressure": {"value": 0.55, "confidence": 0.75},
            "basis_pressure": {"value": 0.30, "confidence": 0.60},
            "cta_pressure": {"value": 0.45, "confidence": 0.70},
            "liquidation_pressure": {"value": 0.20, "confidence": 0.65},
            "rebalance_pressure": {"value": 0.25, "confidence": 0.60},
        },
        source="unit-test",
    )
    out = engine.snapshot("NQ")

    assert out["schema_version"] == "icarus-possibility-v1"
    assert out["authority"]["execution_authorized"] is False
    assert out["truth_contract"]["scenario_probabilities_calibrated"] is False
    assert out["truth_contract"]["causality_proven"] is False
    assert out["truth_contract"]["missing_evidence_imputed"] is False

    components = out["latent_pressure_engine"]["components"]
    assert components["volume_pressure"]["available"] is True
    assert components["volume_pressure"]["value"] > 0
    assert components["queue_pressure"]["available"] is True
    assert components["queue_pressure"]["value"] > 0
    assert components["repricing_pressure"]["available"] is True
    assert components["gamma_pressure"]["available"] is True
    assert components["basis_pressure"]["available"] is True
    assert out["latent_pressure_engine"]["latent_pressure"] is not None
    assert out["latent_pressure_engine"]["evidence_coverage"] > 0.7

    assert out["causal_leadership"]["status"] == "observed"
    assert out["causal_leadership"]["leaders"][0]["asset"] == "ES"

    poss = out["possibility"]
    assert poss["status"] == "observed"
    assert poss["scenarios_generated"] == 192
    assert poss["viable_futures"] > 0
    assert 0 <= poss["future_entropy"] <= 100
    assert 0 <= poss["future_space_collapse"] <= 100
    assert poss["dominant_cluster"] in {"UP", "DOWN", "FLAT"}

    assert out["counterfactual"]["available"] is True
    assert out["phase_transition"]["available"] is True
    assert isinstance(out["market_shadows"], list)
    assert out["data_health"]["microstructure"]["ticks"] is True
    assert out["data_health"]["microstructure"]["depth"] is True
    assert out["edge_state"]["state"] in {"NO_EDGE", "LONG_BIAS", "SHORT_BIAS"}


def test_missing_optional_forces_stay_unavailable_instead_of_zero_imputation():
    engine = PossibilityEngine(Port(), scenarios=96)
    _seed(engine)
    out = engine.snapshot("NQ")
    components = out["latent_pressure_engine"]["components"]
    assert components["gamma_pressure"]["available"] is False
    assert components["gamma_pressure"]["value"] is None
    assert components["basis_pressure"]["available"] is False
    assert components["basis_pressure"]["value"] is None
    assert components["forced_flow_pressure"]["available"] is False
    assert components["forced_flow_pressure"]["value"] is None


def test_pressure_price_elasticity_detects_absorption_direction():
    engine = PossibilityEngine(Port())
    micro = {
        "aggressive_flow": {"imbalance": -0.8, "gross_size": 1000},
        "trade_displacement": -0.00001,
    }
    out = engine._elasticity([], micro)
    assert out["available"] is True
    assert out["state"] == "BUYER_ABSORPTION"

    micro["aggressive_flow"]["imbalance"] = 0.8
    out = engine._elasticity([], micro)
    assert out["state"] == "SELLER_ABSORPTION"

def test_evidence_coverage_is_confidence_weighted():
    latent, coverage = _weighted(
        {
            "a": Feature(1.0, 0.10, True, "fixture"),
            "b": Feature(None, 0.0, False, "missing"),
        },
        {"a": 1.0, "b": 1.0},
    )
    assert latent == pytest.approx(1.0)
    assert coverage == pytest.approx(0.05)


def test_forced_consensus_requires_distinct_evidence_domains():
    engine = PossibilityEngine(Port())
    same_domain = {
        "queue_pressure": Feature(0.9, 1.0, True, "fixture"),
        "repricing_pressure": Feature(0.8, 1.0, True, "fixture"),
        "volume_pressure": Feature(0.7, 1.0, True, "fixture"),
    }
    result = engine._forced_consensus(same_domain)
    assert result["active"] is False
    assert result["observed_domain_count"] == 1

    diverse = {
        **same_domain,
        "cross_asset_pressure": Feature(0.8, 1.0, True, "fixture"),
        "gamma_pressure": Feature(0.7, 1.0, True, "fixture"),
    }
    result = engine._forced_consensus(diverse)
    assert result["active"] is True
    assert result["direction"] == "UP"
    assert result["observed_domain_count"] == 3


def test_external_evidence_rejects_naive_and_future_observation_times():
    engine = PossibilityEngine(Port())
    with pytest.raises(ValueError, match="explicit timezone"):
        engine.ingest_external(
            "NQ",
            {"gamma_pressure": 0.2},
            source="fixture",
            observed_at="2026-10-01T05:00:00",
        )
    future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    with pytest.raises(ValueError, match="future"):
        engine.ingest_external(
            "NQ",
            {"gamma_pressure": 0.2},
            source="fixture",
            observed_at=future,
        )


def test_exactly_neutral_latent_pressure_has_no_directional_phase_boundary():
    engine = PossibilityEngine(Port())
    result = engine._phase_boundary(
        20000.0,
        0.001,
        0.0,
        {},
        {},
    )
    assert result["available"] is False
    assert result["direction"] == "NEUTRAL"
    assert result["phase_boundary"] is None



def test_information_wave_is_source_agnostic_and_bounded():
    engine = PossibilityEngine(Port(), scenarios=96)
    _seed(engine)
    out = engine.snapshot("NQ")
    wave = out["information_wave"]
    assert wave["status"] in {"QUIET", "WATCH", "EVENT"}
    assert 0.0 <= wave["score"] <= 100.0
    assert wave["source_identified"] is False
    assert wave["direction"] in {"UP", "DOWN", None}


def test_parallax_vote_is_distinct_fail_closed_research_context():
    engine = PossibilityEngine(Port(), scenarios=96)
    _seed(engine)
    vote = engine.parallax_vote("NQ")
    assert vote["subsystem"] == "psi"
    assert vote["state"] in {"NO_EDGE", "LONG_BIAS", "SHORT_BIAS"}
    assert vote["execution_authorized"] is False
    assert vote["production_decision_authorized"] is False
    assert "latent_pressure" in vote
    assert "future_space_collapse" in vote

def test_external_evidence_rejects_invalid_confidence_and_ttl():
    engine = PossibilityEngine(Port())
    with pytest.raises(ValueError, match="confidence"):
        engine.ingest_external(
            "NQ",
            {"gamma_pressure": {"value": 0.2, "confidence": float("nan")}},
            source="fixture",
        )
    with pytest.raises(ValueError, match="confidence"):
        engine.ingest_external(
            "NQ",
            {"gamma_pressure": {"value": 0.2, "confidence": 1.5}},
            source="fixture",
        )
    with pytest.raises(ValueError, match="ttl_seconds"):
        engine.ingest_external(
            "NQ",
            {"gamma_pressure": 0.2},
            source="fixture",
            ttl_seconds=float("nan"),
        )


def test_external_evidence_ttl_is_anchored_to_observation_time():
    engine = PossibilityEngine(Port())
    stale = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
    with pytest.raises(ValueError, match="already stale"):
        engine.ingest_external(
            "NQ",
            {"gamma_pressure": 0.2},
            source="fixture",
            observed_at=stale,
            ttl_seconds=60,
        )


def test_synthetic_price_does_not_double_count_cross_asset_leader_pressure():
    engine = PossibilityEngine(Port())
    features = {
        "cross_asset_pressure": Feature(0.8, 0.9, True, "fixture"),
        "queue_pressure": Feature(0.4, 0.8, True, "fixture"),
    }
    latent, _ = _weighted(features, {"cross_asset_pressure": 1.0, "queue_pressure": 1.10})
    positive = engine._synthetic_price(20000.0, 0.001, latent, features, {"pressure": 1.0})
    negative = engine._synthetic_price(20000.0, 0.001, latent, features, {"pressure": -1.0})
    assert positive["synthetic_price"] == pytest.approx(negative["synthetic_price"])
    assert sum(positive["contributions"].values()) == pytest.approx(positive["dislocation"])
    assert positive["known_force_contribution"] == pytest.approx(positive["dislocation"])
    assert positive["unexplained_dislocation"] is None
    assert positive["unexplained_dislocation_available"] is False


def test_information_wave_does_not_double_count_leader_graph():
    engine = PossibilityEngine(Port())
    history = [
        {"ret": 0.0001 + (i % 3) * 0.00001}
        for i in range(20)
    ]
    micro = {
        "repricing_pressure": Feature(0.2, 1.0, True, "fixture"),
        "volume_pressure": Feature(0.1, 1.0, True, "fixture"),
    }
    positive = engine._information_wave(history, 0.0001, 0.4, 0.7, micro, {"pressure": 1.0})
    negative = engine._information_wave(history, 0.0001, 0.4, 0.7, micro, {"pressure": -1.0})
    assert positive["expected_return_component"] == pytest.approx(negative["expected_return_component"])
    assert positive["score"] == pytest.approx(negative["score"])



def test_operator_status_is_read_only_and_does_not_record_market_history():
    engine = PossibilityEngine(Port())
    assert not engine._history
    before = engine.status()
    after = engine.status()
    assert before["schema_version"] == "icarus-possibility-status-v1"
    assert before["execution_authorized"] is False
    assert before["production_decision_authorized"] is False
    assert before["assets"] == {}
    assert after["assets"] == {}
    assert not engine._history

    engine.snapshot("NQ")
    count = len(engine._history["NQ"])
    status = engine.status()
    assert status["assets"]["NQ"]["history_samples"] == count
    assert len(engine._history["NQ"]) == count
