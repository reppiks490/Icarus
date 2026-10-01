from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from icarus_engine.sibyl import SibylEngine


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _evidence(
    engine: SibylEngine,
    domain: str,
    *,
    direction: float = 1.0,
    source: str | None = None,
    observed_at: str | None = None,
    source_commit: str = "a" * 40,
):
    return engine.record_evidence(
        {
            "asset": "NQ",
            "source": source or domain,
            "domain": domain,
            "observed_at": observed_at or _now(),
            "direction": direction,
            "magnitude": 1.0,
            "confidence": 0.95,
            "horizon_seconds": 300,
            "target_price": 25075.0 if direction > 0 else 24925.0,
            "invalidation_price": 24960.0 if direction > 0 else 25040.0,
            "source_commit": source_commit,
            "payload": {"volatility_pct": 0.0025},
        }
    )


def _market(price: float = 25000.0):
    return {"assets": [{"symbol": "NQ", "continuous_symbol": "NQ1!", "price": price}]}


def test_sibyl_detects_collapse_only_with_independent_domains(tmp_path):
    engine = SibylEngine(tmp_path)
    _evidence(engine, "microstructure")
    _evidence(engine, "derivatives")
    _evidence(engine, "macro")

    state = engine.snapshot("NQ", market_status=_market())
    row = next(x for x in state["horizons"] if x["horizon_seconds"] == 300)

    assert row["domain_count"] == 3
    assert row["dominant_basin"] == "up"
    assert row["collapse_detected"] is True
    assert row["probabilities"]["up"] > row["probabilities"]["down"]
    assert state["authority"]["execution_authorized"] is False
    assert state["authority"]["deterministic_foresight_claim"] is False


def test_sibyl_correlation_guard_prevents_source_count_from_faking_consensus(tmp_path):
    engine = SibylEngine(tmp_path)
    _evidence(engine, "microstructure", source="argus-book")
    _evidence(engine, "microstructure", source="argus-trades")
    _evidence(engine, "microstructure", source="argus-imbalance")

    state = engine.snapshot("NQ", market_status=_market())
    row = next(x for x in state["horizons"] if x["horizon_seconds"] == 300)

    assert state["evidence"]["count"] == 3
    assert state["evidence"]["distinct_domain_count"] == 1
    assert row["domain_count"] == 1
    assert row["collapse_detected"] is False


def test_sibyl_uses_only_newest_source_revision_in_live_synthesis(tmp_path):
    engine = SibylEngine(tmp_path)
    first = engine.record_evidence(
        {
            "asset": "NQ",
            "source": "oracle",
            "domain": "macro",
            "observed_at": (datetime.now(timezone.utc) - timedelta(seconds=2)).isoformat(),
            "direction": -1.0,
            "magnitude": 1.0,
            "confidence": 0.95,
            "horizon_seconds": 300,
            "source_commit": "a" * 40,
        }
    )
    second = engine.record_evidence(
        {
            "asset": "NQ",
            "source": "oracle",
            "domain": "macro",
            "observed_at": _now(),
            "direction": 1.0,
            "magnitude": 1.0,
            "confidence": 0.95,
            "horizon_seconds": 300,
            "source_commit": "b" * 40,
        }
    )
    state = engine.snapshot("NQ", market_status=_market())
    row = next(x for x in state["horizons"] if x["horizon_seconds"] == 300)

    assert first["source_commit"] != second["source_commit"]
    assert state["evidence"]["ledger_count"] == 2
    assert state["evidence"]["count"] == 1
    assert row["domain_fusion"][0]["score"] > 0


def test_sibyl_exposes_world_forks_gravity_causal_radar_and_forward_surface(tmp_path):
    engine = SibylEngine(tmp_path)
    engine.record_evidence(
        {
            "asset": "NQ",
            "source": "oracle",
            "domain": "macro",
            "observed_at": _now(),
            "direction": 0.75,
            "magnitude": 1.1,
            "confidence": 0.9,
            "horizon_seconds": 300,
            "target_price": 25080.0,
            "invalidation_price": 24955.0,
            "source_commit": "c" * 40,
            "payload": {
                "volatility_pct": 0.0025,
                "causal_edges": [
                    {
                        "from": "TNX",
                        "to": "NQ",
                        "lag_ms": 18000,
                        "relation": "reported-inverse",
                        "confidence": 0.8,
                    }
                ],
                "forward_surface": [
                    {
                        "horizon_seconds": 300,
                        "expected_return": 0.0015,
                        "implied_vol": 0.18,
                        "skew": -0.12,
                        "tail_up": 0.58,
                        "tail_down": 0.42,
                    }
                ],
            },
        }
    )
    _evidence(engine, "microstructure")
    _evidence(engine, "derivatives")

    state = engine.snapshot("NQ", market_status=_market())

    worlds = state["future_world_forks"]["worlds"]
    assert worlds
    assert abs(sum(x["relative_weight"] for x in worlds) - 1.0) < 1e-9
    assert all(x["states"] for x in worlds)

    gravity = state["liquidity_gravity_field"]
    assert gravity["available"] is True
    assert len(gravity["points"]) == 17
    assert all(-1.0000001 <= x["force"] <= 1.0000001 for x in gravity["points"])

    radar = state["causal_delay_radar"]
    assert radar and radar[0]["from"] == "TNX" and radar[0]["to"] == "NQ"
    assert radar[0]["lag_ms"] == 18000

    surface = state["derivatives_forward_surface"]
    assert surface and surface[0]["horizon_seconds"] == 300
    assert surface[0]["expected_return"] == pytest.approx(0.0015)


def test_sibyl_rejects_future_or_timezone_free_evidence(tmp_path):
    engine = SibylEngine(tmp_path)
    body = {
        "asset": "NQ",
        "source": "oracle",
        "domain": "macro",
        "direction": 1.0,
        "magnitude": 1.0,
        "confidence": 0.8,
        "horizon_seconds": 300,
        "source_commit": "a" * 40,
    }
    with pytest.raises(ValueError, match="timezone"):
        engine.record_evidence({**body, "observed_at": "2026-10-01T05:00:00"})

    future = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    with pytest.raises(ValueError, match="future"):
        engine.record_evidence({**body, "observed_at": future})


def test_sibyl_counterfactual_scenario_never_mutates_evidence_ledger(tmp_path):
    engine = SibylEngine(tmp_path)
    _evidence(engine, "microstructure")
    before = engine.snapshot("NQ", market_status=_market())["evidence"]["count"]

    scenario = engine.scenario(
        {
            "asset": "NQ",
            "current_price": 25000.0,
            "volatility_pct": 0.0025,
            "horizons": [300],
            "interventions": [
                {
                    "source": "counterfactual-vix",
                    "domain": "volatility",
                    "direction": -1.0,
                    "magnitude": 1.8,
                    "confidence": 0.9,
                    "horizon_seconds": 300,
                    "invalidation_price": 25040.0,
                }
            ],
        },
        market_status=_market(),
    )

    after = engine.snapshot("NQ", market_status=_market())["evidence"]["count"]
    assert scenario["counterfactual"] is True
    assert scenario["evidence"]["count"] == before + 1
    assert before == after == 1



def test_sibyl_forecasts_are_revision_bound_and_calibrated_by_observed_outcomes(tmp_path):
    engine = SibylEngine(tmp_path)
    base = datetime.now(timezone.utc) - timedelta(minutes=10)
    forecast_at = base.isoformat().replace("+00:00", "Z")
    evidence_at = (base - timedelta(seconds=10)).isoformat().replace("+00:00", "Z")
    matured_at = (base + timedelta(seconds=300)).isoformat().replace("+00:00", "Z")
    _evidence(engine, "microstructure", observed_at=evidence_at)
    _evidence(engine, "derivatives", observed_at=evidence_at)
    _evidence(engine, "macro", observed_at=evidence_at)

    forecast = engine.record_forecast(
        {
            "asset": "NQ",
            "observed_at": forecast_at,
            "current_price": 25000.0,
            "volatility_pct": 0.0025,
            "horizons": [300],
            "source_commit": "b" * 40,
        },
        market_status=_market(99999.0),
    )
    assert forecast["source_commit"] == "b" * 40
    assert forecast["execution_authorized"] is False
    assert forecast["forecast"]["as_of"] == forecast_at
    assert forecast["forecast"]["current_price"] == 25000.0

    with pytest.raises(ValueError, match="horizon maturity"):
        engine.record_outcome(
            {
                "forecast_id": forecast["forecast_id"],
                "horizon_seconds": 300,
                "observed_at": (base + timedelta(seconds=299)).isoformat().replace("+00:00", "Z"),
                "realized_price": 25100.0,
                "evidence": ["premature-close"],
            }
        )

    outcome = engine.record_outcome(
        {
            "forecast_id": forecast["forecast_id"],
            "horizon_seconds": 300,
            "observed_at": matured_at,
            "realized_price": 25100.0,
            "evidence": ["paper-replay:observed-close"],
        }
    )
    assert outcome["realized_class"] == "up"
    assert outcome["matured_at"] == matured_at
    assert 0 <= outcome["brier"] <= 1

    calibration = engine.calibration("NQ")
    assert calibration["outcome_count"] == 1
    assert calibration["horizons"][0]["n"] == 1
    assert calibration["status"] == "measured"

    with pytest.raises(ValueError, match="immutable"):
        engine.record_outcome(
            {
                "forecast_id": forecast["forecast_id"],
                "horizon_seconds": 300,
                "observed_at": matured_at,
                "realized_price": 24900.0,
                "evidence": ["different-observation"],
            }
        )

def test_sibyl_is_visible_and_routed_in_icarus_interface():
    repo = Path(__file__).resolve().parents[1]
    dashboard = (repo / "icarus_engine" / "dashboard.html").read_text(encoding="utf-8")
    ui = (repo / "icarus_engine" / "sibyl-ui.js").read_text(encoding="utf-8")
    server = (repo / "icarus_engine" / "server.py").read_text(encoding="utf-8")
    brain = (repo / "icarus_engine" / "brain.py").read_text(encoding="utf-8")

    assert '/sibyl-ui.js' in dashboard
    assert 'data-v="sibyl">SIBYL Ω</span>' in dashboard
    assert "wireSibyl()" in dashboard
    assert "/api/sibyl" in ui
    assert "FUTURE COLLAPSE" in ui
    assert "TEMPORAL FRACTURE" in ui
    assert 'p.path == "/api/sibyl"' in server
    assert 'p.path == "/admin/sibyl/evidence"' in server
    assert 'p.path == "/admin/sibyl/forecast"' in server
    assert 'p.path == "/admin/sibyl/outcome"' in server
    assert 'p.path == "/admin/sibyl/scenario"' in server
    assert '"SIBYL"' in brain
    assert '"sibyl"' in brain

def test_sibyl_historical_forecast_excludes_future_evidence(tmp_path):
    engine = SibylEngine(tmp_path)
    base = datetime.now(timezone.utc) - timedelta(minutes=20)
    early = base.isoformat().replace("+00:00", "Z")
    cutoff = (base + timedelta(seconds=30)).isoformat().replace("+00:00", "Z")
    late = (base + timedelta(seconds=60)).isoformat().replace("+00:00", "Z")

    _evidence(engine, "macro", direction=1.0, source="oracle", observed_at=early, source_commit="a" * 40)
    _evidence(engine, "macro", direction=-1.0, source="oracle", observed_at=late, source_commit="b" * 40)

    forecast = engine.record_forecast({
        "asset": "NQ",
        "observed_at": cutoff,
        "current_price": 25000.0,
        "horizons": [300],
        "source_commit": "c" * 40,
    })
    state = forecast["forecast"]
    row = state["horizons"][0]
    assert state["evidence"]["count"] == 1
    assert row["domain_fusion"][0]["score"] > 0
    assert forecast["evidence_cutoff_at"] == cutoff


def test_sibyl_forecast_replay_is_deterministic_after_as_of_is_fixed(tmp_path):
    engine = SibylEngine(tmp_path)
    base = datetime.now(timezone.utc) - timedelta(minutes=15)
    evidence_at = (base - timedelta(seconds=5)).isoformat().replace("+00:00", "Z")
    forecast_at = base.isoformat().replace("+00:00", "Z")
    _evidence(engine, "microstructure", observed_at=evidence_at)
    _evidence(engine, "derivatives", observed_at=evidence_at)
    _evidence(engine, "macro", observed_at=evidence_at)

    body = {
        "asset": "NQ",
        "observed_at": forecast_at,
        "current_price": 25000.0,
        "volatility_pct": 0.0025,
        "horizons": [60, 300, 900],
        "source_commit": "d" * 40,
    }
    first = engine.record_forecast(body)
    second = engine.record_forecast(body)
    assert first["forecast_id"] == second["forecast_id"]
    assert first["forecast"] == second["forecast"]
    assert first["forecast"]["generated_at"] == forecast_at
    assert first["forecast"]["truth_contract"]["wall_clock_free_after_as_of_is_fixed"] is True


def test_sibyl_historical_forecast_requires_explicit_as_of_price(tmp_path):
    engine = SibylEngine(tmp_path)
    historical = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
    with pytest.raises(ValueError, match="current_price is required"):
        engine.record_forecast(
            {
                "asset": "NQ",
                "observed_at": historical,
                "horizons": [300],
                "source_commit": "e" * 40,
            },
            market_status=_market(99999.0),
        )


def _pantheon_observation(observed_at: str, *, domain: str = "structural_constraints", execution_authorized: bool = False):
    authority = {
        "shadow_only": True,
        "execution_authorized": execution_authorized,
        "production_decision_authorized": False,
        "broker_authorized": False,
        "sizing_authorized": False,
        "automatic_production_promotion": False,
    }
    return {
        "observation_id": "pan-sibyl-native",
        "asset": "NQ",
        "observed_at": observed_at,
        "source_commit": "f" * 40,
        "analysis": {
            "exports": {
                "sibyl_evidence": [{
                    "asset": "NQ",
                    "source": "pantheon-ananke",
                    "domain": domain,
                    "observed_at": observed_at,
                    "direction": 0.45,
                    "magnitude": 0.8,
                    "confidence": 0.55,
                    "horizon_seconds": 300,
                    "source_commit": "f" * 40,
                    "payload": {
                        "producer": "PANTHEON/ANANKE",
                        "authority": authority,
                        "semantics": "structural constraint evidence only",
                    },
                }]
            }
        },
    }


def test_sibyl_pantheon_ingestion_is_reserved_and_structurally_gated(tmp_path):
    engine = SibylEngine(tmp_path)
    observed_at = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat().replace("+00:00", "Z")

    with pytest.raises(ValueError, match="reserved"):
        engine.record_evidence({
            "asset": "NQ",
            "source": "pantheon-ananke",
            "domain": "structural_constraints",
            "observed_at": observed_at,
            "direction": 0.5,
            "magnitude": 1.0,
            "confidence": 0.8,
            "horizon_seconds": 300,
            "source_commit": "f" * 40,
        })

    accepted = engine.record_pantheon_exports(_pantheon_observation(observed_at))
    assert accepted["accepted"] == 1
    assert accepted["rejected"] == []
    assert accepted["evidence"][0]["source"] == "pantheon-ananke"

    wrong_domain = engine.record_pantheon_exports(_pantheon_observation(observed_at, domain="macro"))
    assert wrong_domain["accepted"] == 0
    assert "structural_constraints" in wrong_domain["rejected"][0]["reason"]

    escalated = engine.record_pantheon_exports(_pantheon_observation(observed_at, execution_authorized=True))
    assert escalated["accepted"] == 0
    assert "zero execution" in escalated["rejected"][0]["reason"]

    state = engine.snapshot("NQ", market_status=_market())
    assert state["evidence"]["count"] == 1
    assert state["evidence"]["sources"] == ["pantheon-ananke"]
    assert state["authority"]["execution_authorized"] is False


def test_sibyl_historical_scenario_requires_price_and_uses_as_of_cutoff(tmp_path):
    engine = SibylEngine(tmp_path)
    base = datetime.now(timezone.utc) - timedelta(minutes=10)
    observed_at = base.isoformat().replace("+00:00", "Z")
    with pytest.raises(ValueError, match="current_price is required"):
        engine.scenario(
            {
                "asset": "NQ",
                "observed_at": observed_at,
                "interventions": [{"direction": 1.0, "horizon_seconds": 300}],
            },
            market_status=_market(99999.0),
        )

