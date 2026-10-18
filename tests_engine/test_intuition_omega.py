"""Adversarial controls for Intuition Ω research (never execution)."""
from datetime import datetime, timedelta, timezone

import pytest

from icarus_engine.intuition_omega import (
    AnaloguePolicy, AnalogueReasoner, Episode, EpisodicStore,
    FeedObservation, Forecast, ForecastLedger, Resolution,
    Scope, Situation, assemble_situation, calibration_report,
)

BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)
SHA = "a" * 40
SCOPE = Scope("NQ1!", "CME", 600, "heikin_ashi", "real_price",
              "liquidity_reclaim", "tp1_before_stop_real_friction", 600, "features-v1")
HA_SCOPE = Scope("NQ1!", "CME", 600, "heikin_ashi", "synthetic_ha",
                 "liquidity_reclaim", "tp1_before_stop_real_friction", 600, "features-v1")


def iso(t):
    return t.isoformat()


def situation(case_id, at, scope=SCOPE, receipt=None, value=1.0):
    return Situation(case_id, scope, iso(at), iso(receipt or at), SHA,
                     {"absorption": value}, ("source:1",))


def episode(i, *, start=BASE, scope=SCOPE, receipt_delay=0, outcome=1, at=None):
    event = at if at is not None else start + timedelta(days=i)
    s = situation(f"ep-{i}", event, scope)
    mature = event + timedelta(minutes=10)
    return Episode(s, iso(mature), iso(mature + timedelta(seconds=receipt_delay)),
                   outcome, "feed-archive", f"session:{event.date()}", "databento")


def policy(min_samples=30):
    return AnaloguePolicy({"absorption": 1.0}, {"absorption": 1.0},
                          min_independent_episodes=min_samples, min_sessions=10,
                          half_life_days=10000)


def test_scope_refuses_real_synthetic_conflation():
    assert SCOPE != HA_SCOPE
    with pytest.raises(ValueError):
        Scope("NQ1!", "CME", 600, "real_ohlc", "synthetic_ha",
              "r", "label", 600, "v1")


def test_immutable_memory_and_duplicate_identity(tmp_path):
    with pytest.raises(ValueError, match="outcome"):
        Episode(situation("invalid", BASE), iso(BASE), iso(BASE), 2, "dataset", "sess", "family")
    store = EpisodicStore(tmp_path / "episodes.sqlite")
    e = episode(0)
    assert store.add(e)
    assert store.add(e) is False
    other = Episode(e.situation, e.maturity_at, e.outcome_received_at, 0,
                    e.source_dataset_id, e.session_id, e.root_family)
    with pytest.raises(ValueError, match="collision"):
        store.add(other)
    store.close()


def test_time_travel_outcome_is_ineligible_even_if_event_old(tmp_path):
    store = EpisodicStore(tmp_path / "episodes.sqlite")
    late = episode(0, receipt_delay=86400 * 120)
    store.add(late)
    query = situation("query", BASE + timedelta(days=20))
    assert store.eligible(query) == []
    after = situation("later", BASE + timedelta(days=130))
    assert len(store.eligible(after)) == 1
    store.close()


def test_memory_separates_synthetic_fills_from_real_execution(tmp_path):
    store = EpisodicStore(tmp_path / "e.sqlite")
    store.add(episode(0, scope=HA_SCOPE))
    assert not store.eligible(situation("q", BASE + timedelta(days=2)))
    store.close()


def test_overlap_purge_and_abstain_on_small_samples(tmp_path):
    store = EpisodicStore(tmp_path / "e.sqlite")
    at = BASE
    store.add(episode(0, at=at))
    store.add(episode(1, at=at + timedelta(minutes=5)))
    q = situation("query", at + timedelta(days=1))
    report = AnalogueReasoner(store, policy()).infer(q)
    assert report["status"] == "ABSTAIN"
    assert report["support"]["raw_analogues"] == 2
    assert report["support"]["independent_episodes"] == 1
    assert report["support"]["overlap_purged"] == 1
    assert report["execution_authorized"] is False
    store.close()


def test_analogues_can_support_a_diagnostic_but_never_execution(tmp_path):
    store = EpisodicStore(tmp_path / "episodes.sqlite")
    for i in range(60):
        store.add(episode(i, outcome=int(i % 3 != 0)))
    report = AnalogueReasoner(store, policy()).infer(
        situation("future", BASE + timedelta(days=75)))
    assert report["status"] == "RESEARCH_HYPOTHESIS"
    assert 0 < report["empirical_hit_rate"] < 1
    assert report["uncertainty_interval"][0] <= report["empirical_hit_rate"] <= report["uncertainty_interval"][1]
    assert report["support"]["independent_episodes"] == 60
    assert report["production_decision_authorized"] is False
    store.close()


def test_unknown_features_and_corrupt_database_fail_closed(tmp_path):
    store = EpisodicStore(tmp_path / "episodes.sqlite")
    store.add(episode(0))
    with pytest.raises(ValueError, match="feature schema"):
        AnalogueReasoner(store, policy()).infer(
            Situation("new", SCOPE, iso(BASE + timedelta(days=3)), iso(BASE + timedelta(days=3)),
                      SHA, {"something_else": 2.0}, ("source:1",)))
    store._conn.execute("UPDATE episodes SET content='{}'")
    store._conn.commit()
    with pytest.raises(ValueError, match="integrity"):
        store.eligible(situation("new", BASE + timedelta(days=3)))
    store.close()


def forecast(i, *, probability=0.8, scope=SCOPE, producer="omega"):
    t = BASE + timedelta(days=i)
    return Forecast(f"fc-{i}", producer, scope, iso(t), iso(t + timedelta(minutes=10)),
                    iso(t), probability, SHA, ("evidence:1",), f"session:{t.date()}")


def resolution(i, *, label=1, receive_delay=0):
    t = BASE + timedelta(days=i, minutes=10)
    return Resolution(f"fc-{i}", iso(t), iso(t + timedelta(seconds=receive_delay)),
                      label, ("bar-close",))


def test_forecast_maturity_and_resolution_immutability(tmp_path):
    ledger = ForecastLedger(tmp_path / "fc.sqlite")
    f = forecast(0)
    assert ledger.commit(f) is True
    assert ledger.commit(f) is False
    with pytest.raises(ValueError, match="premature"):
        ledger.settle(Resolution(f.forecast_id, iso(BASE), iso(BASE), 1, ("early",)))
    assert ledger.settle(resolution(0))
    assert ledger.settle(resolution(0)) is False
    with pytest.raises(ValueError, match="collision"):
        ledger.settle(resolution(0, label=0))
    ledger.close()


def test_calibration_strictly_mature_and_scope_specific(tmp_path):
    ledger = ForecastLedger(tmp_path / "fc.sqlite")
    for i in range(60):
        ledger.commit(forecast(i))
        ledger.settle(resolution(i))
    earlier = calibration_report(ledger, producer="omega", scope=SCOPE,
                                 as_of=iso(BASE + timedelta(days=20)))
    assert earlier["status"] == "UNMEASURED"
    full = calibration_report(ledger, producer="omega", scope=SCOPE,
                              as_of=iso(BASE + timedelta(days=65)), baseline_probability=0.5)
    assert full["status"] == "MEASURED"
    assert full["sample_count"] == 60
    assert full["brier"] == pytest.approx(0.04)
    assert full["ece"] == pytest.approx(0.2)
    assert full["brier_skill_vs_locked_baseline"] > 0
    other = calibration_report(ledger, producer="omega", scope=HA_SCOPE,
                               as_of=iso(BASE + timedelta(days=65)))
    assert other["status"] == "UNMEASURED"
    ledger.close()


def test_calibration_detects_deterioration_without_promoting(tmp_path):
    ledger = ForecastLedger(tmp_path / "fc.sqlite")
    for i in range(60):
        ledger.commit(forecast(i, probability=0.9 if i < 30 else 0.1))
        ledger.settle(resolution(i))
    result = calibration_report(ledger, producer="omega", scope=SCOPE,
                                as_of=iso(BASE + timedelta(days=65)))
    assert result["status"] == "DEGRADED"
    assert result["drift_state"] == "DRIFT_SUSPECTED"
    assert result["execution_authorized"] is False
    ledger.close()


def feed(*, provider="fred", vintage="vintage:1", authorized=True,
         received=None, local=None, observed=None):
    event = observed or BASE
    received = received or event + timedelta(days=1)
    local = local or received
    return FeedObservation(
        provider, "dataset", "inflation", 3.0,
        iso(event), iso(received), iso(local), SHA, "record:1", "macro",
        "observed", vintage, "periodic", True, authorized, True,
    )


def test_provider_requires_macro_vintage_and_licensed_research(tmp_path):
    with pytest.raises(ValueError, match="vintage"):
        feed(vintage=None)
    disallowed = feed(authorized=False)
    verdict = assemble_situation(
        case_id="q", scope=SCOPE, observed_at=iso(BASE),
        as_of=iso(BASE + timedelta(days=2)), source_commit=SHA,
        observations=[disallowed], max_age_seconds={"fred": 86400 * 5},
    )
    assert verdict["status"] == "ABSTAIN"
    assert verdict["rejected"][0]["reason"] == "entitlement_rights_or_quality_unverified"
    assert verdict["execution_authorized"] is False


def test_provider_knows_when_a_release_was_not_yet_available():
    item = feed(received=BASE + timedelta(days=5))
    verdict = assemble_situation(
        case_id="q", scope=SCOPE, observed_at=iso(BASE),
        as_of=iso(BASE + timedelta(days=2)), source_commit=SHA,
        observations=[item], max_age_seconds={"fred": 86400 * 20},
    )
    assert verdict["status"] == "ABSTAIN"
    assert verdict["rejected"][0]["reason"] == "not_yet_known_at_forecast_time"
    accepted = assemble_situation(
        case_id="later", scope=SCOPE, observed_at=iso(BASE + timedelta(days=6)),
        as_of=iso(BASE + timedelta(days=6)), source_commit=SHA,
        observations=[item], max_age_seconds={"fred": 86400 * 20},
    )
    assert accepted["status"] == "RESEARCH_INPUT"
    assert accepted["situation"].features["fred:inflation"] == 3.0


def test_backdated_model_receipt_is_rejected():
    event = BASE
    with pytest.raises(ValueError, match="receipt/maturity"):
        Forecast("retro", "omega", SCOPE, iso(event),
                 iso(event + timedelta(minutes=10)),
                 iso(event + timedelta(minutes=20)),
                 0.9, SHA, ("e1",), "session:1")
    with pytest.raises(ValueError, match="outcome must mature"):
        Episode(situation("late-input", event, receipt=event + timedelta(minutes=20)),
                iso(event + timedelta(minutes=10)),
                iso(event + timedelta(minutes=21)), 1,
                "dataset", "sess", "family")


def test_independent_experts_reconcile_without_claiming_calibration():
    from dataclasses import asdict
    from icarus_engine.intuition_omega.expertise import ExpertClaim, reconcile_experts
    report = {
        "scope": asdict(SCOPE), "status": "MEASURED",
        "sample_count": 100, "independent_sessions": 50,
        "drift_state": "NO_LARGE_SHIFT_DETECTED",
        "brier": 0.08, "as_of": iso(BASE + timedelta(days=60)),
    }
    a = ExpertClaim("omega", SCOPE, iso(BASE + timedelta(days=70)),
                    iso(BASE + timedelta(days=70)), SHA, 0.65,
                    ("source-A",), {**report, "producer": "omega"}, ("a1",))
    b = ExpertClaim("sibyl", SCOPE, iso(BASE + timedelta(days=70)),
                    iso(BASE + timedelta(days=70)), SHA, 0.70,
                    ("source-B",), {**report, "producer": "sibyl"}, ("b1",))
    result = reconcile_experts([a, b], scope=SCOPE,
                               as_of=iso(BASE + timedelta(days=70)))
    assert result["status"] == "RESEARCH_CONSENSUS_UNCALIBRATED"
    assert result["consensus"] == pytest.approx(0.675)
    assert result["execution_authorized"] is False
    shared = ExpertClaim("sibyl", SCOPE, iso(BASE + timedelta(days=70)),
                         iso(BASE + timedelta(days=70)), SHA, 0.70,
                         ("source-A",), {**report, "producer": "sibyl"}, ("b1",))
    rejected = reconcile_experts([a, shared], scope=SCOPE,
                                 as_of=iso(BASE + timedelta(days=70)))
    assert rejected["status"] == "ABSTAIN"
    future_scorecard = ExpertClaim("sibyl", SCOPE, iso(BASE + timedelta(days=70)),
                        iso(BASE + timedelta(days=70)), SHA, 0.7, ("source-B",),
                        {**report, "producer": "sibyl", "as_of": iso(BASE + timedelta(days=90))},
                        ("b1",))
    assert reconcile_experts([a, future_scorecard], scope=SCOPE,
                              as_of=iso(BASE + timedelta(days=70)))["status"] == "ABSTAIN"


def test_walkforward_retains_a_frozen_final_fold():
    from icarus_engine.intuition_omega.evaluation import (
        EvaluationPolicy, walkforward_analogue_evaluation
    )
    records = [episode(i, outcome=int(i % 3 != 0)) for i in range(360)]
    result = walkforward_analogue_evaluation(
        records, policy=policy(30), evaluation=EvaluationPolicy(folds=5))
    assert len(result["folds"]) == 5
    assert result["folds"][-1]["frozen"] is True
    assert result["execution_authorized"] is False
    assert result["folds"][0]["test_window_episodes"] == 60
    assert all(0 <= fold["coverage"] <= 1 for fold in result["folds"])
