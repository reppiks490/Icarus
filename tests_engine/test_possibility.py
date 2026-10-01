from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
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
    def __init__(self, base_dir=None):
        if base_dir is not None:
            self.base_dir = base_dir
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




def test_durable_evidence_survives_restart_without_relaxing_causal_rules(tmp_path):
    observed = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
    first = PossibilityEngine(Port(tmp_path))
    result = first.ingest_external(
        "NQ",
        {"gamma_pressure": {"value": 0.62, "confidence": 0.81}},
        source="restart-fixture",
        observed_at=observed,
        ttl_seconds=600,
    )
    assert result["durable"] is True
    assert result["inserted"] == 1

    second = PossibilityEngine(Port(tmp_path))
    feature = second._external_features("NQ")["gamma_pressure"]
    assert feature.available is True
    assert feature.value == pytest.approx(0.62)
    assert feature.confidence == pytest.approx(0.81)
    ledger = second.evidence_snapshot("NQ", include_expired=True)
    assert ledger["durable"] is True
    assert ledger["active_count"] == 1
    assert ledger["total_history_count"] == 1


def test_durable_evidence_exact_receipt_is_idempotent(tmp_path):
    observed = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
    engine = PossibilityEngine(Port(tmp_path))
    kwargs = {
        "asset": "NQ",
        "values": {"basis_pressure": {"value": 0.25, "confidence": 0.7}},
        "source": "idempotency-fixture",
        "observed_at": observed,
        "ttl_seconds": 600,
    }
    first = engine.ingest_external(**kwargs)
    second = engine.ingest_external(**kwargs)
    assert first["inserted"] == 1
    assert second["inserted"] == 0
    assert second["idempotent_duplicates"] == 1
    assert second["stored"]["basis_pressure"]["evidence_id"] == first["stored"]["basis_pressure"]["evidence_id"]
    assert second["stored"]["basis_pressure"]["received_ts"] == first["stored"]["basis_pressure"]["received_ts"]
    ledger = engine.evidence_snapshot("NQ", include_expired=True)
    assert ledger["total_history_count"] == 1


def test_durable_evidence_as_of_replay_excludes_later_observations(tmp_path):
    now = datetime.now(timezone.utc)
    early = now - timedelta(minutes=4)
    late = now - timedelta(minutes=2)
    engine = PossibilityEngine(Port(tmp_path))
    engine.ingest_external(
        "NQ",
        {"gamma_pressure": {"value": -0.35, "confidence": 0.6}},
        source="replay-fixture",
        observed_at=early.isoformat(),
        ttl_seconds=600,
    )
    engine.ingest_external(
        "NQ",
        {"gamma_pressure": {"value": 0.55, "confidence": 0.9}},
        source="replay-fixture",
        observed_at=late.isoformat(),
        ttl_seconds=600,
    )

    between = engine.evidence_snapshot(
        "NQ",
        include_expired=True,
        as_of=(early + timedelta(minutes=1)).isoformat(),
    )
    current = engine.evidence_snapshot("NQ", include_expired=True)
    assert between["active"]["gamma_pressure"]["value"] == pytest.approx(-0.35)
    assert all(row["observed_ts"] <= datetime.fromisoformat(between["as_of"].replace("Z", "+00:00")).timestamp() for row in between["history"])
    assert current["active"]["gamma_pressure"]["value"] == pytest.approx(0.55)
    assert between["active"]["gamma_pressure"]["evidence_id"] != current["active"]["gamma_pressure"]["evidence_id"]


def test_snapshot_surfaces_durable_evidence_health(tmp_path):
    engine = PossibilityEngine(Port(tmp_path), scenarios=96)
    _seed(engine)
    engine.ingest_external("NQ", {"basis_pressure": 0.2}, source="health-fixture", ttl_seconds=600)
    out = engine.snapshot("NQ")
    ledger = out["data_health"]["evidence_ledger"]
    assert ledger["durable"] is True
    assert ledger["active_count"] == 1
    assert ledger["total_history_count"] == 1
    assert ledger["schema_version"] == "icarus-psi-evidence-v1"



def _bars_from_returns(start_ts: int, start_price: float, returns, step_seconds: int):
    bars = [SimpleNamespace(ts=start_ts, c=start_price)]
    price = float(start_price)
    for i, ret in enumerate(returns, start=1):
        price *= math.exp(float(ret))
        bars.append(SimpleNamespace(ts=start_ts + i * step_seconds, c=price))
    return bars


class ReplayPort(Port):
    def __init__(self, *, nq_minutes=1, es_minutes=1):
        super().__init__()
        base = 1_700_000_000
        peer_returns = [
            0.00011, -0.00007, 0.00016, -0.00004, 0.00009, -0.00013,
            0.00018, -0.00002, 0.00006, -0.00010,
        ] * 7
        target_returns = [0.00001] + peer_returns[:-1]
        self.runners = {
            "NQ": SimpleNamespace(
                feed=Feed(),
                spec=SimpleNamespace(ticker="NQ.v.0"),
                chart_minutes=nq_minutes,
                bars=_bars_from_returns(base, 20000.0, target_returns, nq_minutes * 60),
            ),
            "ES": SimpleNamespace(
                feed=Feed(),
                spec=SimpleNamespace(ticker="ES.v.0"),
                chart_minutes=es_minutes,
                bars=_bars_from_returns(base, 6800.0, peer_returns, es_minutes * 60),
            ),
        }


def test_runner_bar_history_warms_leader_graph_on_first_snapshot():
    engine = PossibilityEngine(ReplayPort(), scenarios=96)
    out = engine.snapshot("NQ")
    leaders = out["causal_leadership"]
    assert leaders["status"] == "observed"
    assert leaders["alignment_mode"] == "exact_bar_timestamp"
    assert leaders["chart_minutes"] == 1
    assert leaders["leaders"][0]["asset"] == "ES"
    assert leaders["leaders"][0]["lag1_correlation"] > 0.95
    assert leaders["leaders"][0]["samples"] >= 50
    assert out["data_health"]["history"]["source"] == "runner_bar"
    assert out["data_health"]["history"]["poll_independent"] is True
    assert out["data_health"]["history"]["timestamp_aligned_leaders"] is True


def test_runner_bar_history_is_independent_of_snapshot_poll_frequency():
    engine = PossibilityEngine(ReplayPort(), scenarios=96)
    first = engine.snapshot("NQ")
    first_len = first["data_health"]["market_history_observations"]
    first_leader = first["causal_leadership"]["leaders"][0]
    for _ in range(8):
        again = engine.snapshot("NQ")
    assert again["data_health"]["market_history_observations"] == first_len
    assert again["causal_leadership"]["leaders"][0]["samples"] == first_leader["samples"]
    assert again["causal_leadership"]["leaders"][0]["lag1_correlation"] == pytest.approx(first_leader["lag1_correlation"])


def test_runner_bar_leader_graph_rejects_mismatched_chart_cadence():
    engine = PossibilityEngine(ReplayPort(nq_minutes=1, es_minutes=5), scenarios=96)
    out = engine.snapshot("NQ")
    leaders = out["causal_leadership"]
    assert leaders["status"] == "warming"
    assert leaders["alignment_mode"] == "exact_bar_timestamp"
    rejected = {row["asset"]: row for row in leaders["rejected_peers"]}
    assert rejected["ES"]["reason"] == "chart_cadence_mismatch"
    assert rejected["ES"]["target_minutes"] == 1
    assert rejected["ES"]["peer_minutes"] == 5


def test_runner_bar_leader_graph_uses_exact_timestamps_not_tail_position():
    port = ReplayPort()
    # Delete several ES bars from the middle. Positional tail pairing would shift
    # the series; exact timestamp pairing should simply reduce valid samples.
    port.runners["ES"].bars = [
        bar for i, bar in enumerate(port.runners["ES"].bars)
        if i not in {12, 13, 27, 41}
    ]
    engine = PossibilityEngine(port, scenarios=96)
    out = engine.snapshot("NQ")
    leader = out["causal_leadership"]["leaders"][0]
    assert leader["asset"] == "ES"
    assert leader["alignment_mode"] == "exact_bar_timestamp"
    assert leader["lag1_correlation"] > 0.95
    assert leader["samples"] < 69
    assert out["data_health"]["history"]["gap_returns_skipped"] > 0



def test_runner_bar_leaders_prefer_real_close_over_transformed_chart_close():
    port = ReplayPort()
    for runner in port.runners.values():
        original = list(runner.bars)
        runner.overlays = [{"ts": bar.ts, "real_c": bar.c} for bar in original]
        runner.bars = [
            SimpleNamespace(ts=bar.ts, c=100.0 + (i % 2) * 0.00001)
            for i, bar in enumerate(original)
        ]
    engine = PossibilityEngine(port, scenarios=96)
    out = engine.snapshot("NQ")
    leader = out["causal_leadership"]["leaders"][0]
    assert leader["asset"] == "ES"
    assert leader["lag1_correlation"] > 0.95
    assert leader["stability"] > 0.8
    assert -1.0 <= leader["latest_peer_z"] <= 1.0
    assert out["data_health"]["history"]["price_basis"] == "real_close"


def test_runner_bar_leaders_reject_stale_latest_peer_bar():
    port = ReplayPort()
    port.runners["ES"].bars = port.runners["ES"].bars[:-1]
    engine = PossibilityEngine(port, scenarios=96)
    out = engine.snapshot("NQ")
    leaders = out["causal_leadership"]
    assert leaders["status"] == "warming"
    rejected = {row["asset"]: row for row in leaders["rejected_peers"]}
    assert rejected["ES"]["reason"] == "latest_bar_not_aligned"


def test_runner_bar_leader_stability_is_exposed_and_bounded():
    engine = PossibilityEngine(ReplayPort(), scenarios=96)
    out = engine.snapshot("NQ")
    leader = out["causal_leadership"]["leaders"][0]
    assert 0.0 <= leader["stability"] <= 1.0
    assert len(leader["fold_correlations"]) >= 2
    assert 0.0 <= leader["lead_strength"] <= 1.0
