from __future__ import annotations
from types import SimpleNamespace
import math
import time

import pytest

from icarus_engine.chronofold import ChronofoldEngine, _entropy, _ridge_fit


class Port:
    def __init__(self):
        self.i = 0
        self.runners = {"NQ": SimpleNamespace(), "ES": SimpleNamespace()}

    def status(self):
        i = self.i
        self.i += 1
        return {
            "assets": [
                {"symbol": "NQ", "price": 20000.0 + i * (1.0 + (i % 3) * 0.2), "warm": True, "paused": False,
                 "state": {"pulse_l": 0.62 + min(i, 20) * 0.005, "pulse_s": 0.18, "rate_regime": 0.55}},
                {"symbol": "ES", "price": 6800.0 + i * (0.35 + (i % 4) * 0.03), "warm": True, "paused": False,
                 "state": {"pulse_l": 0.58, "pulse_s": 0.22, "rate_regime": 0.48}},
            ]
        }


class Possibility:
    def snapshot(self, symbol):
        return {
            "information_wave": {"score": 35.0},
            "latent_pressure_engine": {"latent_pressure": 0.25},
            "phase_transition": {"event_horizon": 0.2},
            "data_health": {"microstructure": {"depth": True}},
        }


def test_empty_port_fails_closed():
    class Empty:
        def status(self): return {"assets": []}
    out = ChronofoldEngine(Empty()).snapshot()
    assert out["status"] == "NO_STATE"
    assert out["authority"]["execution_authorized"] is False
    assert out["gnc"]["guidance"] == "NO_EDGE"


def test_chronofold_full_surface_and_truth_contract():
    engine = ChronofoldEngine(Port(), possibility=Possibility(), scenarios=96, horizon=8)
    out = None
    for _ in range(80):
        out = engine.snapshot("NQ")
    assert out is not None
    assert out["schema_version"] == "icarus-chronofold-v1"
    assert out["authority"]["research_only"] is True
    assert out["authority"]["execution_authorized"] is False
    assert out["truth_contract"]["future_data_used"] is False
    assert out["truth_contract"]["physics_literalism"] is False
    assert out["time_boundary"]["causal_integrity"] == "BOUNDED"
    assert out["time_machine"]["live_future_access"] is False
    assert out["time_machine"]["backward_smoothing_live"] is False
    assert out["chronon"]["market_proper_time"] > 0
    assert out["multitime"]["information_time"] > 0
    assert 0 <= out["geometry"]["curvature"] <= 1
    assert out["market_potential"]["literal_gravity_claim"] is False
    assert 0 <= out["market_potential"]["energy"] <= 1
    assert out["price_phase_field"]["status"] == "observed"
    assert out["macro_field"]["directional_claim"] is False
    assert out["macro_field"]["status"] == "observed"
    assert out["causal_cone"]["structural_causality_proven"] is False
    assert out["koopman"]["status"] == "observed"
    assert out["path_signature"]["status"] == "observed"
    assert set(out["density_state"]["probabilities"]) == {"UP", "FLAT", "DOWN"}
    assert sum(out["density_state"]["probabilities"].values()) == pytest.approx(1.0)
    assert 0 <= out["density_state"]["normalized_entropy"] <= 1
    assert out["density_state"]["quantum_claim"] is False
    assert out["density_state"]["probabilities_calibrated"] is False
    assert out["multiverse"]["scenarios"] == 96
    assert sum(out["multiverse"]["cluster_weights"].values()) == pytest.approx(1.0)
    assert out["multiverse"]["probabilities_calibrated"] is False
    assert out["counterfactual_shadows"]
    assert 0 <= out["epistemic_unknown_mass"] <= 1
    assert out["gnc"]["control"] == "SHADOW_ONLY"
    assert out["gnc"]["execution_authorized"] is False


def test_repeated_identical_poll_does_not_manufacture_return():
    class Flat:
        def status(self):
            return {"assets":[{"symbol":"NQ","price":100.0,"warm":True,"paused":False,"state":{"pulse_l":0.5,"pulse_s":0.2,"rate_regime":0.3}}]}
    engine = ChronofoldEngine(Flat(), scenarios=32)
    for _ in range(10):
        out = engine.snapshot("NQ")
    assert list(engine._history["NQ"])[-1].ret == pytest.approx(0.0)
    assert out["chronon"]["activity"]["statistical_surprise"] == pytest.approx(0.0)


def test_multiverse_is_deterministic_for_same_internal_state():
    p = Port(); engine = ChronofoldEngine(p, possibility=Possibility(), scenarios=64, horizon=6)
    for _ in range(25): engine.snapshot("NQ")
    poss = engine._possibility_snapshot("NQ")
    graph = engine._causal_graph("NQ")
    geom = engine._geometry("NQ", graph)
    koop = engine._koopman("NQ")
    den = engine._density_state("NQ", graph, koop, poss)
    a = engine._multiverse("NQ", den, geom, graph, poss)
    b = engine._multiverse("NQ", den, geom, graph, poss)
    assert a["cluster_weights"] == b["cluster_weights"]
    assert a["expected_return"] == pytest.approx(b["expected_return"])


def test_math_helpers_are_bounded_and_fit_linear_relation():
    assert _entropy([1, 0, 0]) == pytest.approx(0.0)
    assert _entropy([1, 1, 1]) == pytest.approx(1.0)
    rows = [[1.0, x] for x in range(1, 8)]
    ys = [2.0 + 3.0 * x for x in range(1, 8)]
    beta = _ridge_fit(rows, ys, ridge=1e-9)
    assert beta is not None
    assert beta[0] == pytest.approx(2.0, abs=1e-5)
    assert beta[1] == pytest.approx(3.0, abs=1e-5)


def test_invalid_configuration_fails_early():
    p = Port()
    with pytest.raises(ValueError, match="max_history"):
        ChronofoldEngine(p, max_history=8)
    with pytest.raises(ValueError, match="scenarios"):
        ChronofoldEngine(p, scenarios=4)
    with pytest.raises(ValueError, match="horizon"):
        ChronofoldEngine(p, horizon=1)


def test_identical_snapshot_is_idempotent_and_status_is_read_only():
    class Stable:
        def __init__(self):
            self.calls = 0
        def status(self):
            self.calls += 1
            return {"assets": [
                {"symbol": "NQ", "price": 100.0, "warm": True, "paused": False,
                 "state": {"pulse_l": 0.6, "pulse_s": 0.2, "rate_regime": 0.4}},
                {"symbol": "ES", "price": 50.0, "warm": True, "paused": False,
                 "state": {"pulse_l": 0.55, "pulse_s": 0.25, "rate_regime": 0.35}},
            ]}

    port = Stable()
    engine = ChronofoldEngine(port, scenarios=32, horizon=4)
    first = engine.snapshot("NQ")
    tau = first["chronon"]["market_proper_time"]
    obs = first["observations"]
    second = engine.snapshot("NQ")
    assert second["chronon"]["market_proper_time"] == pytest.approx(tau)
    assert second["observations"] == obs
    calls_before = port.calls
    health = engine.status()
    assert health["read_only"] is True
    assert port.calls == calls_before
    assert health["authority"]["execution_authorized"] is False


def test_extreme_finite_prices_do_not_overflow_future_worlds():
    class Extreme:
        def __init__(self):
            self.i = 0
        def status(self):
            self.i += 1
            px = 1e300 if self.i % 2 else 1e-200
            return {"assets": [
                {"symbol": "NQ", "price": px, "warm": True, "paused": False,
                 "state": {"pulse_l": 0.7, "pulse_s": 0.1, "rate_regime": 0.8}},
                {"symbol": "ES", "price": max(1e-100, px * 1e-200), "warm": True, "paused": False,
                 "state": {"pulse_l": 0.6, "pulse_s": 0.2, "rate_regime": 0.7}},
            ]}

    engine = ChronofoldEngine(Extreme(), scenarios=32, horizon=8)
    out = None
    for _ in range(12):
        out = engine.snapshot("NQ")
    assert out is not None
    mv = out["multiverse"]
    assert math.isfinite(mv["expected_return"])
    assert math.isfinite(mv["p05_return"])
    assert math.isfinite(mv["p95_return"])
    assert all(math.isfinite(x) for path in mv["sample_paths"] for x in path)

def test_chronofold_uses_observed_price_age_for_causal_time_boundary():
    class Timed:
        def status(self):
            return {"assets": [{
                "symbol": "NQ",
                "price": 100.0,
                "price_age": 0.25,
                "warm": True,
                "paused": False,
                "state": {"pulse_l": 0.5, "pulse_s": 0.2, "rate_regime": 0.3},
            }]}
    out = ChronofoldEngine(Timed(), scenarios=32).snapshot("NQ")
    boundary = out["time_boundary"]
    assert boundary["causal_integrity"] == "PASS"
    assert boundary["event_time_source"] == "price_age"
    assert boundary["source_event_time_verified"] is True
    assert boundary["event_time"] <= boundary["retrieval_time"]
    assert boundary["availability_time_exact"] is False


def test_chronofold_rejects_future_source_timestamp_and_malformed_bool_price():
    now = time.time()
    class Future:
        def status(self):
            return {"assets": [{
                "symbol": "NQ", "price": 100.0, "warm": True, "paused": False,
                "state": {"ts": now + 60.0, "pulse_l": 0.5, "pulse_s": 0.2, "rate_regime": 0.3},
            }]}
    out = ChronofoldEngine(Future(), scenarios=32).snapshot("NQ")
    assert out["status"] == "NO_STATE"

    class BoolPrice:
        def status(self):
            return {"assets": [{
                "symbol": "NQ", "price": True, "warm": True, "paused": False,
                "state": {"pulse_l": 0.5, "pulse_s": 0.2, "rate_regime": 0.3},
            }]}
    out = ChronofoldEngine(BoolPrice(), scenarios=32).snapshot("NQ")
    assert out["status"] == "NO_STATE"

