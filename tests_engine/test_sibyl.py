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
            "source_commit": "a" * 40,
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
    forecast_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    evidence_time = (forecast_time - timedelta(seconds=30)).isoformat()
    _evidence(engine, "microstructure", observed_at=evidence_time)
    _evidence(engine, "derivatives", observed_at=evidence_time)
    _evidence(engine, "macro", observed_at=evidence_time)

    forecast = engine.record_forecast(
        {
            "asset": "NQ",
            "observed_at": forecast_time.isoformat(),
            "current_price": 25000.0,
            "volatility_pct": 0.0025,
            "horizons": [300],
            "source_commit": "b" * 40,
        },
        market_status=_market(),
    )
    assert forecast["source_commit"] == "b" * 40
    assert forecast["execution_authorized"] is False

    premature = (forecast_time + timedelta(seconds=299)).isoformat()
    with pytest.raises(ValueError, match="horizon maturity"):
        engine.record_outcome(
            {
                "forecast_id": forecast["forecast_id"],
                "horizon_seconds": 300,
                "observed_at": premature,
                "realized_price": 25100.0,
                "evidence": ["too-early"],
            }
        )

    matured = (forecast_time + timedelta(seconds=300)).isoformat()
    outcome = engine.record_outcome(
        {
            "forecast_id": forecast["forecast_id"],
            "horizon_seconds": 300,
            "observed_at": matured,
            "realized_price": 25100.0,
            "evidence": ["paper-replay:observed-close"],
        }
    )
    assert outcome["realized_class"] == "up"
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
                "observed_at": matured,
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

def test_sibyl_asof_forecast_excludes_later_evidence_and_replays_deterministically(tmp_path):
    engine = SibylEngine(tmp_path)
    as_of = datetime.now(timezone.utc) - timedelta(minutes=20)
    before = (as_of - timedelta(minutes=1)).isoformat()
    after = (as_of + timedelta(minutes=1)).isoformat()

    old = engine.record_evidence(
        {
            "asset": "NQ",
            "source": "oracle",
            "domain": "macro",
            "observed_at": before,
            "direction": -1.0,
            "magnitude": 1.0,
            "confidence": 0.95,
            "horizon_seconds": 300,
            "source_commit": "a" * 40,
        }
    )
    engine.record_evidence(
        {
            "asset": "NQ",
            "source": "oracle",
            "domain": "macro",
            "observed_at": after,
            "direction": 1.0,
            "magnitude": 1.0,
            "confidence": 0.95,
            "horizon_seconds": 300,
            "source_commit": "b" * 40,
        }
    )

    body = {
        "asset": "NQ",
        "observed_at": as_of.isoformat(),
        "current_price": 25000.0,
        "volatility_pct": 0.0025,
        "horizons": [300],
        "source_commit": "c" * 40,
    }
    first = engine.record_forecast(body, market_status=_market(99999.0))
    second = engine.record_forecast(body, market_status=_market(1.0))

    assert first["forecast_id"] == second["forecast_id"]
    assert first["computed_at"] == second["computed_at"]
    assert first["forecast"] == second["forecast"]
    assert first["forecast"]["evidence"]["count"] == 1
    assert first["forecast"]["as_of"].endswith("Z")
    assert first["forecast"]["horizons"][0]["domain_fusion"][0]["score"] < 0
    with engine._connect() as conn:
        row = conn.execute("SELECT forecast_json FROM forecasts WHERE forecast_id=?", (first["forecast_id"],)).fetchone()
    persisted = __import__("json").loads(row["forecast_json"])
    assert old["evidence_id"] in {
        e["evidence_id"] for e in engine._evidence("NQ", as_of=first["forecast"]["as_of"])
    }
    assert "generated_at" not in persisted


def test_sibyl_historical_forecast_and_scenario_never_borrow_live_price(tmp_path):
    engine = SibylEngine(tmp_path)
    past = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()

    with pytest.raises(ValueError, match="current_price is required"):
        engine.record_forecast(
            {
                "asset": "NQ",
                "observed_at": past,
                "horizons": [300],
                "source_commit": "a" * 40,
            },
            market_status=_market(99999.0),
        )

    with pytest.raises(ValueError, match="current_price is required"):
        engine.scenario(
            {
                "asset": "NQ",
                "as_of": past,
                "horizons": [300],
                "interventions": [{"domain": "macro", "direction": 1.0}],
            },
            market_status=_market(99999.0),
        )

    live = engine.record_forecast(
        {
            "asset": "NQ",
            "horizons": [60],
            "source_commit": "b" * 40,
        },
        market_status=_market(25001.0),
    )
    assert live["forecast"]["current_price"] == pytest.approx(25001.0)


def test_sibyl_counterfactual_asof_excludes_later_ledger_evidence(tmp_path):
    engine = SibylEngine(tmp_path)
    as_of = datetime.now(timezone.utc) - timedelta(minutes=20)
    _evidence(engine, "macro", direction=-1.0, observed_at=(as_of - timedelta(minutes=1)).isoformat())
    _evidence(engine, "derivatives", direction=1.0, observed_at=(as_of + timedelta(minutes=1)).isoformat())

    state = engine.scenario(
        {
            "asset": "NQ",
            "as_of": as_of.isoformat(),
            "current_price": 25000.0,
            "horizons": [300],
            "interventions": [{"source": "what-if", "domain": "volatility", "direction": -0.5}],
        }
    )
    assert state["as_of"].endswith("Z")
    assert state["counterfactual"] is True
    assert state["evidence"]["count"] == 2
    assert set(state["evidence"]["domains"]) == {"macro", "volatility"}


def test_sibyl_pantheon_source_is_reserved_validated_and_idempotent(tmp_path):
    engine = SibylEngine(tmp_path)
    export = {
        "asset": "NQ",
        "source": "pantheon-ananke",
        "domain": "structural_constraints",
        "observed_at": _now(),
        "direction": 0.6,
        "magnitude": 0.8,
        "confidence": 0.7,
        "horizon_seconds": 300,
        "source_commit": "d" * 40,
        "payload": {
            "producer": "PANTHEON/ANANKE",
            "authority": {
                "shadow_only": True,
                "execution_authorized": False,
                "production_decision_authorized": False,
                "broker_authorized": False,
                "sizing_authorized": False,
                "automatic_production_promotion": False,
            },
        },
    }

    with pytest.raises(ValueError, match="reserved"):
        engine.record_evidence(export)

    first = engine.record_pantheon_export(export)
    second = engine.record_pantheon_export(export)
    assert first["evidence_id"] == second["evidence_id"]
    assert engine.snapshot("NQ", market_status=_market())["evidence"]["ledger_count"] == 1

    with pytest.raises(ValueError, match="domain"):
        engine.record_pantheon_export({**export, "domain": "macro"})
    bad = dict(export)
    bad["payload"] = {"producer": "PANTHEON/ANANKE", "authority": {"shadow_only": True}}
    with pytest.raises(ValueError, match="authority"):
        engine.record_pantheon_export(bad)


def test_sibyl_interface_includes_pantheon_bridge_and_failure_isolation_contract():
    repo = Path(__file__).resolve().parents[1]
    server = (repo / "icarus_engine" / "server.py").read_text(encoding="utf-8")
    assert "record_pantheon_export" in server
    assert "sibyl_bridge" in server
    assert "PANTHEON→SIBYL bridge" in server
    assert "pantheon.record_observation(payload)" in server

