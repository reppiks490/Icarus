from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
import sqlite3
import time
from types import SimpleNamespace

import pytest

from icarus_engine.possibility import Feature, PossibilityEngine, _weighted
from icarus_engine.psi_evidence import PsiEvidenceLedger
from icarus_engine.server import _current_parallax_payload


class Tick:
    def __init__(self, price: float, size: int, side: str, ts_event: int, sequence: int = 0):
        self.price = price
        self.size = size
        self.side = side
        self.ts_event = ts_event
        self.ts_event_ns = ts_event * 1_000_000_000
        self.sequence = sequence


class Feed:
    def trades(self, ticker, limit=500):
        rows = []
        now = int(time.time())
        for i in range(180):
            side = "B" if i % 5 else "A"
            rows.append(Tick(20000.0 + i * 0.02, 3 + (i % 4), side, now - 179 + i, i))
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
            rows.append({"levels": levels, "ts_event": int(time.time()) - (39 - i)})
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
    assert 0 < poss["effective_scenarios"] <= poss["scenarios_generated"]
    assert 0 < poss["effective_sample_ratio"] <= 1
    assert 0 <= poss["reliability"] <= 1
    assert poss["endpoint_return_p10"] <= poss["endpoint_return_p25"] <= poss["endpoint_return_p50"]
    assert poss["endpoint_return_p50"] <= poss["endpoint_return_p75"] <= poss["endpoint_return_p90"]
    assert poss["shock_model"] in {"empirical_block_bootstrap", "low_discrepancy_gaussian_fallback"}
    assert poss["empirical_sample_count"] >= 8

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



def test_information_wave_is_source_agnostic_causal_and_bounded():
    engine = PossibilityEngine(ReplayPort(), scenarios=96)
    out = engine.snapshot("NQ")
    wave = out["information_wave"]
    assert wave["status"] in {"QUIET", "WATCH", "EVENT"}
    assert 0.0 <= wave["score"] <= 100.0
    assert wave["causal_leading"] is True
    assert wave["source_identified"] is False
    assert wave["direction"] in {"UP", "DOWN", None}
    assert wave["tick_last_ts"] > wave["completed_bar_close_ts"]


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
    assert "information_wave_status" in vote
    assert "information_wave_causal_leading" in vote
    assert "leader_alignment_mode" in vote

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


def test_information_wave_does_not_use_contemporaneous_latent_pressure():
    engine = PossibilityEngine(ReplayPort())
    engine._sync_history_from_runners()
    history = list(engine._history["NQ"])
    close_ts = history[-1]["ts"] + 60
    now = time.time()
    start = max(close_ts + 1, now - 10)
    micro = {
        "tick_samples": [
            {"ts": start + i, "price": 20000.0 + i * 0.25, "size": 5.0, "side": "B"}
            for i in range(6)
        ],
    }
    positive = engine._information_wave(history, 0.0002, 0.9, 1.0, micro, {"pressure": 0.2})
    negative = engine._information_wave(history, 0.0002, -0.9, 0.1, micro, {"pressure": 0.2})
    assert positive["causal_leading"] is True
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


def test_backfilled_evidence_does_not_leak_before_receipt_time(tmp_path):
    now = datetime.now(timezone.utc)
    early = now - timedelta(minutes=4)
    late = now - timedelta(minutes=2)
    engine = PossibilityEngine(Port(tmp_path))
    first = engine.ingest_external(
        "NQ",
        {"gamma_pressure": {"value": -0.35, "confidence": 0.6}},
        source="replay-fixture",
        observed_at=early.isoformat(),
        ttl_seconds=600,
    )
    second = engine.ingest_external(
        "NQ",
        {"gamma_pressure": {"value": 0.55, "confidence": 0.9}},
        source="replay-fixture",
        observed_at=late.isoformat(),
        ttl_seconds=600,
    )

    historical = engine.evidence_snapshot(
        "NQ",
        include_expired=True,
        as_of=(early + timedelta(minutes=1)).isoformat(),
    )
    current = engine.evidence_snapshot("NQ", include_expired=True)
    assert historical["active_count"] == 0
    assert historical["history"] == []
    assert current["active"]["gamma_pressure"]["value"] == pytest.approx(0.55)
    assert first["stored"]["gamma_pressure"]["received_ts"] > datetime.fromisoformat(
        historical["as_of"].replace("Z", "+00:00")
    ).timestamp()
    assert second["stored"]["gamma_pressure"]["received_ts"] > datetime.fromisoformat(
        historical["as_of"].replace("Z", "+00:00")
    ).timestamp()


def test_evidence_replay_uses_both_observation_and_receipt_time(tmp_path):
    ledger = PsiEvidenceLedger(tmp_path)
    base = datetime.now(timezone.utc) - timedelta(minutes=10)
    base_ts = base.timestamp()

    def row(value, observed_offset, received_offset, suffix):
        observed = base + timedelta(seconds=observed_offset)
        return {
            "asset": "NQ",
            "feature": "gamma_pressure",
            "value": value,
            "confidence": 0.8,
            "source": f"historical-{suffix}",
            "observed_at": observed.isoformat().replace("+00:00", "Z"),
            "observed_ts": base_ts + observed_offset,
            "received_ts": base_ts + received_offset,
            "expires_ts": base_ts + observed_offset + 600,
            "ttl_seconds": 600.0,
            "created_at": observed.isoformat().replace("+00:00", "Z"),
        }

    ledger.record_many([
        row(-0.4, 0, 30, "a"),
        row(0.6, 120, 180, "b"),
    ])

    before_receipt = ledger.snapshot(
        "NQ", as_of_ts=base_ts + 20,
        as_of=(base + timedelta(seconds=20)).isoformat(),
        include_expired=True,
    )
    after_first = ledger.snapshot(
        "NQ", as_of_ts=base_ts + 60,
        as_of=(base + timedelta(seconds=60)).isoformat(),
        include_expired=True,
    )
    observed_but_not_received = ledger.snapshot(
        "NQ", as_of_ts=base_ts + 150,
        as_of=(base + timedelta(seconds=150)).isoformat(),
        include_expired=True,
    )
    after_second = ledger.snapshot(
        "NQ", as_of_ts=base_ts + 200,
        as_of=(base + timedelta(seconds=200)).isoformat(),
        include_expired=True,
    )

    assert before_receipt["active_count"] == 0
    assert after_first["active"]["gamma_pressure"]["value"] == pytest.approx(-0.4)
    assert observed_but_not_received["active"]["gamma_pressure"]["value"] == pytest.approx(-0.4)
    assert after_second["active"]["gamma_pressure"]["value"] == pytest.approx(0.6)


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
        peer_returns = [
            0.00011, -0.00007, 0.00016, -0.00004, 0.00009, -0.00013,
            0.00018, -0.00002, 0.00006, -0.00010,
        ] * 7
        target_returns = [0.00001] + peer_returns[:-1]
        now = int(time.time())
        nq_step = nq_minutes * 60
        es_step = es_minutes * 60
        nq_last_start = (now // nq_step) * nq_step - 2 * nq_step
        es_last_start = (now // es_step) * es_step - 2 * es_step
        nq_base = nq_last_start - len(target_returns) * nq_step
        es_base = es_last_start - len(peer_returns) * es_step
        self.runners = {
            "NQ": SimpleNamespace(
                feed=Feed(),
                spec=SimpleNamespace(ticker="NQ.v.0"),
                chart_minutes=nq_minutes,
                bars=_bars_from_returns(nq_base, 20000.0, target_returns, nq_step),
            ),
            "ES": SimpleNamespace(
                feed=Feed(),
                spec=SimpleNamespace(ticker="ES.v.0"),
                chart_minutes=es_minutes,
                bars=_bars_from_returns(es_base, 6800.0, peer_returns, es_step),
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



def test_current_parallax_capture_stamps_decision_after_psi_vote():
    generated = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat().replace("+00:00", "Z")

    class Psi:
        def parallax_vote(self, asset):
            return {"subsystem": "psi", "asset": asset, "generated_at": generated, "state": "NO_EDGE"}

    payload, vote = _current_parallax_payload(Psi(), {
        "asset": "nq",
        "action": "long",
        "subsystem_votes": {"argus": {"state": "aligned"}},
    })
    decision_time = datetime.fromisoformat(payload["observed_at"].replace("Z", "+00:00"))
    vote_time = datetime.fromisoformat(vote["generated_at"].replace("Z", "+00:00"))
    assert payload["asset"] == "NQ"
    assert payload["subsystem_votes"]["psi"] == vote
    assert decision_time >= vote_time


def test_current_parallax_capture_rejects_historical_timestamp_and_supplied_psi():
    class Psi:
        def parallax_vote(self, asset):
            return {"subsystem": "psi", "asset": asset}

    with pytest.raises(ValueError, match="owns observed_at"):
        _current_parallax_payload(Psi(), {
            "asset": "NQ",
            "action": "long",
            "observed_at": "2026-10-01T06:00:00Z",
        })
    with pytest.raises(ValueError, match="owns the psi vote"):
        _current_parallax_payload(Psi(), {
            "asset": "NQ",
            "action": "long",
            "subsystem_votes": {"psi": {"state": "forged"}},
        })


def test_current_parallax_capture_rejects_future_psi_timestamp():
    future = (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat().replace("+00:00", "Z")

    class Psi:
        def parallax_vote(self, asset):
            return {"subsystem": "psi", "asset": asset, "generated_at": future}

    with pytest.raises(ValueError, match="cannot follow"):
        _current_parallax_payload(Psi(), {"asset": "NQ", "action": "long"})



def test_information_wave_fails_closed_without_runner_bar_timing():
    engine = PossibilityEngine(Port(), scenarios=96)
    _seed(engine)
    out = engine.snapshot("NQ")
    assert out["information_wave"]["status"] == "UNAVAILABLE"
    assert out["information_wave"]["causal_leading"] is False


def test_information_wave_rejects_future_tick_clock_skew():
    engine = PossibilityEngine(ReplayPort(), scenarios=96)
    engine._sync_history_from_runners()
    history = list(engine._history["NQ"])
    close_ts = history[-1]["ts"] + 60
    future = time.time() + 60
    micro = {
        "tick_samples": [
            {"ts": max(close_ts + 1, future) + i, "price": 20000 + i, "size": 1, "side": "B"}
            for i in range(4)
        ]
    }
    wave = engine._information_wave(history, 0.0002, 0.0, 0.0, micro, {"pressure": 0.0})
    assert wave["status"] == "CLOCK_SKEW"
    assert wave["causal_leading"] is False



def test_edge_gate_fails_closed_on_weak_scenario_support():
    engine = PossibilityEngine(Port())
    edge = engine._edge_gate(
        latent=0.8,
        coverage=0.9,
        collapse=80.0,
        future_reliability=0.2,
        effective_sample_ratio=0.9,
        consensus={"active": True, "alignment": 0.9},
        micro={"health": {"ticks": True, "depth": True}},
        leaders={"status": "observed", "confidence": 0.8},
    )
    assert edge["state"] == "NO_EDGE"
    assert "future-space reliability below 35%" in edge["blockers"]

    edge = engine._edge_gate(
        latent=0.8,
        coverage=0.9,
        collapse=80.0,
        future_reliability=0.9,
        effective_sample_ratio=0.2,
        consensus={"active": True, "alignment": 0.9},
        micro={"health": {"ticks": True, "depth": True}},
        leaders={"status": "observed", "confidence": 0.8},
    )
    assert edge["state"] == "NO_EDGE"
    assert "effective scenario support below 35%" in edge["blockers"]



def test_multi_force_evidence_batch_is_atomic_and_idempotent(tmp_path):
    engine = PossibilityEngine(Port(tmp_path))
    values = {
        "gamma_pressure": {"value": 0.4, "confidence": 0.8},
        "basis_pressure": {"value": 0.2, "confidence": 0.7},
        "cta_pressure": {"value": -0.1, "confidence": 0.6},
    }
    first = engine.ingest_external("NQ", values, source="batch-fixture", ttl_seconds=600)
    second = engine.ingest_external("NQ", values, source="batch-fixture", ttl_seconds=600)
    assert first["inserted"] == 3
    assert second["inserted"] == 0
    assert second["idempotent_duplicates"] == 3
    ledger = engine.evidence_snapshot("NQ", include_expired=True)
    assert ledger["total_history_count"] == 3
    assert ledger["active_count"] == 3


def test_invalid_multi_force_request_leaves_no_partial_evidence(tmp_path):
    engine = PossibilityEngine(Port(tmp_path))
    with pytest.raises(ValueError, match="basis_pressure"):
        engine.ingest_external(
            "NQ",
            {
                "gamma_pressure": {"value": 0.4, "confidence": 0.8},
                "basis_pressure": {"value": 2.0, "confidence": 0.7},
            },
            source="atomic-failure-fixture",
            ttl_seconds=600,
        )
    ledger = engine.evidence_snapshot("NQ", include_expired=True)
    assert ledger["total_history_count"] == 0
    assert ledger["active_count"] == 0



def test_external_force_fusion_penalizes_opposing_sources(tmp_path):
    now = datetime.now(timezone.utc)
    engine = PossibilityEngine(Port(tmp_path))
    engine.ingest_external(
        "NQ", {"gamma_pressure": {"value": 0.8, "confidence": 0.9}},
        source="provider-a", observed_at=(now - timedelta(seconds=10)).isoformat(), ttl_seconds=600,
    )
    engine.ingest_external(
        "NQ", {"gamma_pressure": {"value": -0.8, "confidence": 0.9}},
        source="provider-b", observed_at=(now - timedelta(seconds=5)).isoformat(), ttl_seconds=600,
    )
    feature = engine._external_features("NQ")["gamma_pressure"]
    assert feature.available is True
    assert abs(feature.value) < 1e-9
    assert feature.confidence == pytest.approx(0.0)
    ledger = engine.evidence_snapshot("NQ", include_expired=True)
    assert ledger["disagreement"]["gamma_pressure"]["sign_conflict"] is True


def test_external_force_fusion_preserves_agreeing_sources(tmp_path):
    now = datetime.now(timezone.utc)
    engine = PossibilityEngine(Port(tmp_path))
    engine.ingest_external(
        "NQ", {"basis_pressure": {"value": 0.6, "confidence": 0.8}},
        source="provider-a", observed_at=(now - timedelta(seconds=10)).isoformat(), ttl_seconds=600,
    )
    engine.ingest_external(
        "NQ", {"basis_pressure": {"value": 0.8, "confidence": 0.8}},
        source="provider-b", observed_at=(now - timedelta(seconds=5)).isoformat(), ttl_seconds=600,
    )
    feature = engine._external_features("NQ")["basis_pressure"]
    assert feature.value == pytest.approx(0.7)
    assert 0.5 < feature.confidence < 0.8
    assert feature.source == "fused:2 sources"


def test_external_force_fusion_uses_latest_receipt_per_source(tmp_path):
    now = datetime.now(timezone.utc)
    engine = PossibilityEngine(Port(tmp_path))
    engine.ingest_external(
        "NQ", {"gamma_pressure": {"value": -0.7, "confidence": 0.8}},
        source="provider-a", observed_at=(now - timedelta(seconds=20)).isoformat(), ttl_seconds=600,
    )
    engine.ingest_external(
        "NQ", {"gamma_pressure": {"value": 0.7, "confidence": 0.8}},
        source="provider-a", observed_at=(now - timedelta(seconds=10)).isoformat(), ttl_seconds=600,
    )
    engine.ingest_external(
        "NQ", {"gamma_pressure": {"value": 0.5, "confidence": 0.8}},
        source="provider-b", observed_at=(now - timedelta(seconds=5)).isoformat(), ttl_seconds=600,
    )
    groups = engine._evidence_ledger.active_by_source("NQ")
    assert len(groups["gamma_pressure"]) == 2
    by_source = {row["source"]: row for row in groups["gamma_pressure"]}
    assert by_source["provider-a"]["value"] == pytest.approx(0.7)
    feature = engine._external_features("NQ")["gamma_pressure"]
    assert feature.value == pytest.approx(0.6)



def test_distance_weighted_queue_pressure_prioritizes_near_book_liquidity():
    engine = PossibilityEngine(Port())
    levels = []
    for i in range(10):
        levels.append({
            "bid_px": 100.0 - i * 0.25,
            "ask_px": 100.5 + i * 0.25,
            "bid_sz": 100 if i == 0 else 1,
            "ask_sz": 1 if i == 0 else 20,
        })

    class DepthFeed(Feed):
        def depth_events(self, ticker, *, schema="mbp-10", limit=120):
            return [{"levels": levels, "ts_event": int(time.time())}]

    engine.port.runners["NQ"].feed = DepthFeed()
    micro = engine._microstructure("NQ")
    assert micro["queue_pressure"].available is True
    assert micro["queue_pressure"].value > 0
    assert micro["book_pressure"]["weighted_bid_size"] > 0
    assert micro["book_pressure"]["depth_coverage"] == pytest.approx(1.0)


def test_elasticity_uses_realized_volatility_window_when_available():
    engine = PossibilityEngine(Port())
    history = [
        {
            "ret": 0.001 if i % 2 == 0 else -0.001,
            "chart_minutes": 1,
        }
        for i in range(30)
    ]
    micro = {
        "aggressive_flow": {"imbalance": 0.8, "gross_size": 1000},
        "trade_displacement": 0.00001,
        "tick_window": {"duration_seconds": 30},
    }
    out = engine._elasticity(history, micro)
    assert out["normalization"] == "realized_vol_window"
    assert out["response_z"] is not None
    assert out["state"] == "SELLER_ABSORPTION"


def test_elasticity_vacuum_threshold_scales_with_volatility():
    engine = PossibilityEngine(Port())
    history = [
        {
            "ret": 0.0001 if i % 2 == 0 else -0.0001,
            "chart_minutes": 1,
        }
        for i in range(30)
    ]
    micro = {
        "aggressive_flow": {"imbalance": 0.10, "gross_size": 200},
        "trade_displacement": 0.001,
        "tick_window": {"duration_seconds": 30},
    }
    out = engine._elasticity(history, micro)
    assert out["normalization"] == "realized_vol_window"
    assert out["response_z"] > 1.25
    assert out["state"] == "OFFER_VACUUM"


def test_edge_gate_rejects_polling_derived_leader_graph():
    engine = PossibilityEngine(Port())
    edge = engine._edge_gate(
        latent=0.8,
        coverage=0.9,
        collapse=80.0,
        future_reliability=0.9,
        effective_sample_ratio=0.9,
        consensus={"active": True, "alignment": 0.9},
        micro={"health": {"ticks": True, "depth": True}},
        leaders={
            "status": "observed",
            "alignment_mode": "poll_snapshot_fallback",
            "confidence": 0.8,
        },
    )
    assert edge["state"] == "NO_EDGE"
    assert "dynamic leader graph is not exact-bar aligned" in edge["blockers"]


def test_edge_gate_rejects_low_confidence_exact_leaders():
    engine = PossibilityEngine(Port())
    edge = engine._edge_gate(
        latent=0.8,
        coverage=0.9,
        collapse=80.0,
        future_reliability=0.9,
        effective_sample_ratio=0.9,
        consensus={"active": True, "alignment": 0.9},
        micro={"health": {"ticks": True, "depth": True}},
        leaders={
            "status": "observed",
            "alignment_mode": "exact_bar_timestamp",
            "confidence": 0.05,
        },
    )
    assert edge["state"] == "NO_EDGE"
    assert "dynamic leader confidence below 10%" in edge["blockers"]



def test_stale_depth_snapshot_is_not_admitted_as_queue_pressure():
    engine = PossibilityEngine(Port())

    class StaleDepthFeed(Feed):
        def depth_events(self, ticker, *, schema="mbp-10", limit=120):
            levels = [{
                "bid_px": 100.0,
                "ask_px": 100.5,
                "bid_sz": 100,
                "ask_sz": 1,
            }]
            return [{"levels": levels, "ts_event": int(time.time()) - 120}]

    engine.port.runners["NQ"].feed = StaleDepthFeed()
    micro = engine._microstructure("NQ")
    assert micro["queue_pressure"].available is False
    assert micro["health"]["depth"] is False
    assert any("stale" in error for error in micro["health"]["errors"])


def test_future_clock_depth_snapshot_is_not_admitted():
    engine = PossibilityEngine(Port())

    class FutureDepthFeed(Feed):
        def depth_events(self, ticker, *, schema="mbp-10", limit=120):
            levels = [{
                "bid_px": 100.0,
                "ask_px": 100.5,
                "bid_sz": 100,
                "ask_sz": 1,
            }]
            return [{"levels": levels, "ts_event": int(time.time()) + 60}]

    engine.port.runners["NQ"].feed = FutureDepthFeed()
    micro = engine._microstructure("NQ")
    assert micro["queue_pressure"].available is False
    assert micro["health"]["depth"] is False
    assert any("future" in error for error in micro["health"]["errors"])



def test_stale_trade_tape_is_not_admitted_to_latent_pressure():
    engine = PossibilityEngine(Port())

    class StaleTradeFeed(Feed):
        def trades(self, ticker, limit=500):
            now = int(time.time())
            return [
                Tick(100.0 + i * 0.01, 10, "B", now - 180 - i, i)
                for i in range(20)
            ]

    engine.port.runners["NQ"].feed = StaleTradeFeed()
    micro = engine._microstructure("NQ")
    assert micro["volume_pressure"].available is False
    assert micro["health"]["ticks"] is False
    assert any("stale" in error for error in micro["health"]["errors"])


def test_future_clock_trade_tape_is_not_admitted():
    engine = PossibilityEngine(Port())

    class FutureTradeFeed(Feed):
        def trades(self, ticker, limit=500):
            now = int(time.time())
            return [
                Tick(100.0 + i * 0.01, 10, "B", now + 60 + i, i)
                for i in range(20)
            ]

    engine.port.runners["NQ"].feed = FutureTradeFeed()
    micro = engine._microstructure("NQ")
    assert micro["volume_pressure"].available is False
    assert micro["health"]["ticks"] is False
    assert any("future" in error for error in micro["health"]["errors"])


def test_trade_pressure_uses_fresh_window_not_entire_adapter_buffer():
    engine = PossibilityEngine(Port())
    engine.port.runners["NQ"].chart_minutes = 1

    class MixedAgeTradeFeed(Feed):
        def trades(self, ticker, limit=500):
            now = int(time.time())
            old = [
                Tick(100.0, 50, "A", now - 300 + i, i)
                for i in range(100)
            ]
            fresh = [
                Tick(100.0 + i * 0.01, 10, "B", now - 5 + i, 100 + i)
                for i in range(6)
            ]
            return old + fresh

    engine.port.runners["NQ"].feed = MixedAgeTradeFeed()
    micro = engine._microstructure("NQ")
    assert micro["volume_pressure"].available is True
    assert micro["volume_pressure"].value > 0
    assert micro["aggressive_flow"]["tick_count"] == 6
    assert micro["tick_window"]["requested_window_seconds"] == pytest.approx(60.0)



def test_zero_confidence_external_forces_do_not_leak_into_forced_flow():
    engine = PossibilityEngine(Port())
    external = {
        "basis_pressure": Feature(None, 0.0, False, "unavailable"),
        "gamma_pressure": Feature(None, 0.0, False, "unavailable"),
        "cta_pressure": Feature(1.0, 0.0, True, "conflicted"),
        "liquidation_pressure": Feature(-1.0, 0.0, True, "conflicted"),
        "rebalance_pressure": Feature(0.8, 0.0, True, "conflicted"),
    }
    features = engine._features(
        "NQ",
        {},
        {},
        {"status": "warming"},
        external,
    )
    forced = features["forced_flow_pressure"]
    assert forced.available is False
    assert forced.value is None
    assert forced.confidence == 0.0



def test_future_space_uses_empirical_block_shocks_with_sufficient_runner_history():
    engine = PossibilityEngine(ReplayPort(), scenarios=192)
    out = engine.snapshot("NQ")
    poss = out["possibility"]
    assert poss["shock_model"] == "empirical_block_bootstrap"
    assert poss["empirical_sample_count"] >= 60
    assert poss["empirical_return_vol"] is not None
    assert poss["empirical_tail_ratio"] is not None
    assert 0.0 <= poss["empirical_tail_ratio"] <= 1.0


def test_phase_boundary_is_derived_from_same_direction_endpoint_quantiles():
    engine = PossibilityEngine(Port())
    features = {
        "gamma_pressure": Feature(0.8, 0.8, True, "fixture"),
        "cross_asset_pressure": Feature(0.6, 0.7, True, "fixture"),
    }
    futures = {
        "reliability": 0.8,
        "future_space_collapse": 60.0,
        "endpoint_return_p75": 0.004,
        "endpoint_return_p90": 0.008,
        "endpoint_return_p25": -0.003,
        "endpoint_return_p10": -0.007,
    }
    up = engine._phase_boundary(20000.0, 0.001, 0.7, futures, features)
    assert up["available"] is True
    assert up["phase_boundary"] == pytest.approx(20080.0)
    assert up["event_horizon"] == pytest.approx(20160.0)
    assert up["calibrated"] is False

    down = engine._phase_boundary(20000.0, 0.001, -0.7, futures, {
        "gamma_pressure": Feature(-0.8, 0.8, True, "fixture"),
    })
    assert down["available"] is True
    assert down["phase_boundary"] == pytest.approx(19940.0)
    assert down["event_horizon"] == pytest.approx(19860.0)


def test_phase_boundary_fails_closed_when_scenarios_do_not_support_direction():
    engine = PossibilityEngine(Port())
    futures = {
        "reliability": 0.8,
        "future_space_collapse": 70.0,
        "endpoint_return_p75": -0.001,
        "endpoint_return_p90": 0.0005,
        "endpoint_return_p25": 0.001,
        "endpoint_return_p10": -0.0005,
    }
    up = engine._phase_boundary(20000.0, 0.001, 0.8, futures, {})
    assert up["available"] is False
    assert "does not support" in up["note"]

    down = engine._phase_boundary(20000.0, 0.001, -0.8, futures, {})
    assert down["available"] is False
    assert "does not support" in down["note"]


def test_phase_boundary_fails_closed_on_weak_scenario_reliability():
    engine = PossibilityEngine(Port())
    result = engine._phase_boundary(
        20000.0,
        0.001,
        0.8,
        {
            "reliability": 0.1,
            "endpoint_return_p75": 0.01,
            "endpoint_return_p90": 0.02,
        },
        {},
    )
    assert result["available"] is False
    assert "too weak" in result["note"]



def test_forced_consensus_domain_weight_does_not_scale_with_feature_count():
    engine = PossibilityEngine(Port())
    features = {
        "queue_pressure": Feature(1.0, 1.0, True, "fixture"),
        "repricing_pressure": Feature(1.0, 1.0, True, "fixture"),
        "volume_pressure": Feature(1.0, 1.0, True, "fixture"),
        "gamma_pressure": Feature(-1.0, 1.0, True, "fixture"),
        "basis_pressure": Feature(-1.0, 1.0, True, "fixture"),
    }
    result = engine._forced_consensus(features)
    domains = {row["name"]: row for row in result["domains"]}
    assert domains["microstructure"]["component_count"] == 3
    assert domains["microstructure"]["strength"] == pytest.approx(1.0)
    assert domains["gamma"]["strength"] == pytest.approx(1.0)
    assert domains["basis"]["strength"] == pytest.approx(1.0)
    assert result["active"] is False


def test_market_shadow_declares_first_order_noncausal_approximation():
    engine = PossibilityEngine(Port())
    rows = engine._market_shadows(
        100.0,
        {
            "available": True,
            "synthetic_price": 102.0,
            "contributions": {"gamma_pressure": 1.0, "basis_pressure": 1.0},
        },
        {},
    )
    assert rows
    assert all(row["approximation"] == "first_order_local_ablation" for row in rows)
    assert all(row["causal_effect_proven"] is False for row in rows)



def test_runner_bar_leader_applies_multiple_testing_screen():
    engine = PossibilityEngine(ReplayPort(), scenarios=96)
    out = engine.snapshot("NQ")
    leaders = out["causal_leadership"]
    assert leaders["multiple_testing_method"] == "bonferroni_fisher_z_heuristic"
    assert leaders["peer_test_count"] >= 1
    leader = leaders["leaders"][0]
    assert leader["adjusted_p_value_heuristic"] <= 0.10
    assert leader["raw_p_value_heuristic"] <= leader["adjusted_p_value_heuristic"]


def test_multiple_testing_rejects_weak_spurious_peer():
    port = ReplayPort()
    nq_bars = port.runners["NQ"].bars
    base_ts = nq_bars[0].ts
    step = 60
    weak_returns = [
        0.0001 if i % 4 in (0, 1) else -0.0001
        for i in range(len(nq_bars) - 1)
    ]
    port.runners["WEAK"] = SimpleNamespace(
        feed=Feed(),
        spec=SimpleNamespace(ticker="WEAK.v.0"),
        chart_minutes=1,
        bars=_bars_from_returns(base_ts, 1000.0, weak_returns, step),
    )
    engine = PossibilityEngine(port, scenarios=96)
    out = engine.snapshot("NQ")
    accepted = {row["asset"] for row in out["causal_leadership"]["leaders"]}
    assert "ES" in accepted
    if "WEAK" not in accepted:
        rejected = {
            row["asset"]: row
            for row in out["causal_leadership"]["rejected_peers"]
            if row.get("asset")
        }
        assert rejected["WEAK"]["reason"] in {
            "multiple_testing_screen",
            "degenerate_lag_series",
        }



def test_psi_evidence_integrity_detects_receipt_tampering(tmp_path):
    engine = PossibilityEngine(Port(tmp_path))
    engine.ingest_external(
        "NQ",
        {"gamma_pressure": {"value": 0.4, "confidence": 0.8}},
        source="integrity-fixture",
        ttl_seconds=600,
    )
    healthy = engine._evidence_ledger.integrity(max_age_seconds=0)
    assert healthy["ok"] is True
    assert healthy["invalid_receipt_count"] == 0
    assert healthy["receipt_count"] == 1
    original_digest = healthy["ledger_digest_sha256"]

    db = tmp_path / "research" / "psi_evidence.sqlite3"
    with sqlite3.connect(db) as con:
        con.execute("UPDATE evidence SET value=0.9")

    corrupted = engine._evidence_ledger.integrity(max_age_seconds=0)
    assert corrupted["ok"] is False
    assert corrupted["invalid_receipt_count"] >= 1
    assert corrupted["ledger_digest_sha256"] != original_digest


def test_psi_evidence_startup_fails_closed_on_incompatible_schema(tmp_path):
    research = tmp_path / "research"
    research.mkdir(parents=True)
    db = research / "psi_evidence.sqlite3"
    with sqlite3.connect(db) as con:
        con.execute("CREATE TABLE evidence (evidence_id TEXT PRIMARY KEY)")

    with pytest.raises(RuntimeError, match="schema is incompatible"):
        PsiEvidenceLedger(tmp_path)



def test_external_evidence_rejects_unknown_asset_and_bad_source_identity():
    engine = PossibilityEngine(Port())
    with pytest.raises(ValueError, match="not active"):
        engine.ingest_external(
            "UNKNOWN",
            {"gamma_pressure": 0.2},
            source="fixture",
        )
    with pytest.raises(ValueError, match="control characters"):
        engine.ingest_external(
            "NQ",
            {"gamma_pressure": 0.2},
            source="provider\nforged",
        )
    with pytest.raises(ValueError, match="source exceeds"):
        engine.ingest_external(
            "NQ",
            {"gamma_pressure": 0.2},
            source="x" * 181,
        )
