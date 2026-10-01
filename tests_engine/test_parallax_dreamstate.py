from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from icarus_engine.dreamstate import DreamstateLab, REQUIRED_GATES, SOURCE_FDR_MAX
from icarus_engine.parallax import ParallaxStore
from icarus_engine.brain import brain_snapshot


def _contract(tag: str = "base"):
    return {
        "utility_metric": "r_multiple",
        "evaluation_horizon_bars": 20,
        "dataset_id": f"dataset:{tag}",
        "cost_model_id": f"costs:{tag}",
        "clock_id": "bar-close-v1",
        "normalization": "risk_normalized",
    }


def _record_pair(
    store: ParallaxStore,
    i: int,
    *,
    delay_utility: float = 1.0,
    source_commit: str = "a" * 40,
    contract_tag: str = "base",
    actual_evidence: bool = True,
    branch_evidence: bool = True,
    episode_id: str | None = None,
):
    context = {
        "bar": i,
        "vix_accel": 0.2,
        "session": "NY",
        "volatility_regime": "high",
    }
    if episode_id is not None:
        context["episode_id"] = episode_id
    decision = store.record_decision(
        {
            "asset": "NQ",
            "action": "long",
            "observed_at": f"2026-10-01T05:{i:02d}:00Z",
            "regime": "trend-high-vol",
            "source_commit": source_commit,
            "context": context,
            "strata": {"session": "NY", "volatility_regime": "high"},
            "comparison_contract": _contract(contract_tag),
            "subsystem_votes": {"athena": 0.8, "argus": 0.55},
        }
    )
    store.record_outcome(
        {
            "decision_id": decision["decision_id"],
            "label": "actual",
            "utility": 0.0,
            "metrics": {"r_multiple": 0.0},
            "evidence": [f"replay:{i}:actual"] if actual_evidence else [],
        }
    )
    store.record_outcome(
        {
            "decision_id": decision["decision_id"],
            "label": "delay_1",
            "utility": delay_utility,
            "metrics": {"r_multiple": delay_utility},
            "evidence": [f"replay:{i}:delay1"] if branch_evidence else [],
        }
    )
    return store.decision(decision["decision_id"])


def test_parallax_creates_richer_shadow_lattice_and_never_scores_unobserved(tmp_path):
    store = ParallaxStore(tmp_path)
    decision = store.record_decision(
        {
            "asset": "NQ",
            "action": "long",
            "observed_at": "2026-10-01T05:00:00Z",
            "regime": "trend",
            "source_commit": "a" * 40,
            "context": {"price": 25000.0, "session": "NY"},
            "comparison_contract": _contract(),
            "subsystem_votes": {"athena": 0.7, "argus": 0.4},
        }
    )
    labels = {branch["label"] for branch in decision["branches"]}
    assert {
        "actual",
        "skip",
        "opposite",
        "delay_1",
        "stop_1.25",
        "target_1.25",
        "size_0.50",
        "delay1_stop1.25",
        "delay1_stop1.25_target1.25",
        "without_athena",
    } <= labels
    assert decision["comparison_contract_complete"] is True
    assert decision["strata"]["session"] == "NY"
    assert decision["analysis"]["regret"] is None
    assert decision["analysis"]["branch_coverage_ratio"] == 0.0
    assert decision["execution_authorized"] is False
    assert decision["production_decision_authorized"] is False

    updated = store.record_outcome(
        {
            "decision_id": decision["decision_id"],
            "label": "actual",
            "utility": 0.25,
            "metrics": {"pnl": 125.0},
            "evidence": ["paper-replay:actual"],
        }
    )
    assert updated["analysis"]["actual_utility"] == 0.25
    assert updated["analysis"]["regret"] == 0.0
    assert updated["analysis"]["observed_branch_count"] == 1
    assert updated["analysis"]["observed_with_evidence_count"] == 1
    assert updated["analysis"]["evidence_coverage_ratio"] == 1.0


def test_parallax_flat_decision_does_not_invent_trade_counterfactuals(tmp_path):
    store = ParallaxStore(tmp_path)
    decision = store.record_decision(
        {
            "asset": "NQ",
            "action": "flat",
            "observed_at": "2026-10-01T05:00:00Z",
            "regime": "chop",
            "source_commit": "a" * 40,
            "context": {},
            "comparison_contract": _contract(),
            "subsystem_votes": {},
        }
    )
    assert [branch["label"] for branch in decision["branches"]] == ["actual"]


def test_parallax_identity_binds_action_regime_and_comparison_contract(tmp_path):
    store = ParallaxStore(tmp_path)
    base = {
        "asset": "NQ",
        "observed_at": "2026-10-01T05:00:00Z",
        "source_commit": "a" * 40,
        "context": {"bar": 1},
        "subsystem_votes": {"athena": 0.5},
    }
    long_trend = store.record_decision({**base, "action": "long", "regime": "trend", "comparison_contract": _contract("a")})
    short_trend = store.record_decision({**base, "action": "short", "regime": "trend", "comparison_contract": _contract("a")})
    long_chop = store.record_decision({**base, "action": "long", "regime": "chop", "comparison_contract": _contract("a")})
    long_other_contract = store.record_decision({**base, "action": "long", "regime": "trend", "comparison_contract": _contract("b")})
    ids = {x["decision_id"] for x in (long_trend, short_trend, long_chop, long_other_contract)}
    assert len(ids) == 4


def test_parallax_preserves_idempotency_for_legacy_v1_decision_identity(tmp_path):
    store = ParallaxStore(tmp_path)
    payload = {
        "asset": "NQ",
        "action": "long",
        "observed_at": "2026-09-30T10:00:00Z",
        "regime": "trend",
        "source_commit": "a" * 40,
        "context": {"bar": 1},
        "subsystem_votes": {"athena": 0.5},
    }
    context_json = json.dumps(payload["context"], sort_keys=True, separators=(",", ":"))
    votes_json = json.dumps(payload["subsystem_votes"], sort_keys=True, separators=(",", ":"))
    legacy_hash = hashlib.sha256(
        (payload["source_commit"] + "|" + payload["asset"] + "|" + payload["observed_at"] + "|" + context_json + "|" + votes_json).encode()
    ).hexdigest()
    decision_id = "px-" + legacy_hash[:24]
    with store._connect() as con:
        con.execute(
            """INSERT INTO decisions(
                   decision_id,observed_at,asset,action,regime,source_commit,context_hash,
                   context_json,votes_json,contract_json,strata_json,created_at
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                decision_id,
                payload["observed_at"],
                payload["asset"],
                payload["action"],
                payload["regime"],
                payload["source_commit"],
                legacy_hash,
                context_json,
                votes_json,
                "{}",
                "{}",
                "2026-09-30T10:00:00Z",
            ),
        )
        con.execute(
            "INSERT INTO branches(branch_id,decision_id,kind,label,params_json,status) VALUES (?,?,?,?,?,'pending')",
            ("pxb-legacy", decision_id, "actual", "actual", json.dumps({"action": "long"})),
        )
    replay = store.record_decision({**payload, "decision_id": decision_id})
    assert replay["decision_id"] == decision_id
    assert replay["comparison_contract_complete"] is False


def test_parallax_outcomes_are_immutable(tmp_path):
    store = ParallaxStore(tmp_path)
    decision = _record_pair(store, 0)
    same = store.record_outcome(
        {
            "decision_id": decision["decision_id"],
            "label": "delay_1",
            "utility": 1.0,
            "metrics": {"r_multiple": 1.0},
            "evidence": ["different-evidence-is-not-a-rescore"],
        }
    )
    assert same["analysis"]["best_observed_branch"] == "delay_1"

    with pytest.raises(ValueError, match="immutable"):
        store.record_outcome(
            {
                "decision_id": decision["decision_id"],
                "label": "delay_1",
                "utility": 2.0,
                "metrics": {"r_multiple": 2.0},
            }
        )


def test_parallax_requires_evidence_complete_pairs_and_fdr_screen(tmp_path):
    store = ParallaxStore(tmp_path)
    for i in range(4):
        _record_pair(store, i)
    assert not [s for s in store.mutation_signals(min_samples=5) if s["branch_label"] == "delay_1"]

    _record_pair(store, 4)
    signals = [s for s in store.mutation_signals(min_samples=5) if s["branch_label"] == "delay_1"]
    assert len(signals) == 1
    signal = signals[0]
    assert signal["kind"] == "delay"
    assert signal["n"] == 5
    assert signal["evidence_pair_count"] == 5
    assert signal["evidence_pair_coverage"] == 1.0
    assert signal["ci95_low"] > 0
    assert signal["q_value"] <= SOURCE_FDR_MAX
    assert signal["comparison_contract_complete"] is True
    assert signal["strata_count"] == 1
    assert signal["strata_stats"][0]["strata"]["session"] == "NY"


def test_parallax_incomplete_comparison_contract_blocks_candidate_signal(tmp_path):
    store = ParallaxStore(tmp_path)
    for i in range(5):
        decision = store.record_decision(
            {
                "asset": "NQ",
                "action": "long",
                "observed_at": f"2026-10-01T06:{i:02d}:00Z",
                "regime": "trend",
                "source_commit": "a" * 40,
                "context": {"bar": i},
                "subsystem_votes": {},
            }
        )
        store.record_outcome({"decision_id": decision["decision_id"], "label": "actual", "utility": 0.0, "evidence": [f"a:{i}"]})
        store.record_outcome({"decision_id": decision["decision_id"], "label": "delay_1", "utility": 1.0, "evidence": [f"d:{i}"]})

    assert store.mutation_signals(min_samples=5) == []
    report = store.screening_report(min_samples=5)
    delay = next(row for row in report["hypotheses"] if row["branch_label"] == "delay_1")
    assert "comparison_contract_incomplete" in delay["screen_blockers"]
    assert delay["candidate_eligible"] is False


def test_parallax_missing_path_evidence_does_not_count_toward_candidate_n(tmp_path):
    store = ParallaxStore(tmp_path)
    for i in range(5):
        _record_pair(store, i, branch_evidence=i != 4)
    assert store.mutation_signals(min_samples=5) == []
    report = store.screening_report(min_samples=5)
    delay = next(row for row in report["hypotheses"] if row["branch_label"] == "delay_1")
    assert delay["pair_count_total"] == 5
    assert delay["evidence_pair_count"] == 4
    assert delay["evidence_pair_coverage"] == 0.8
    assert "insufficient_evidence_pairs" in delay["screen_blockers"]


def test_parallax_never_pools_same_label_with_different_branch_parameters(tmp_path):
    store = ParallaxStore(tmp_path)
    for i, delay in enumerate((1, 1, 1, 2, 2, 2)):
        decision = store.record_decision(
            {
                "asset": "NQ",
                "action": "long",
                "observed_at": f"2026-10-01T08:{i:02d}:00Z",
                "regime": "trend",
                "source_commit": "a" * 40,
                "context": {"bar": i},
                "comparison_contract": _contract(),
                "subsystem_votes": {},
                "branches": [
                    {"kind": "actual", "label": "actual", "params": {"action": "long"}},
                    {"kind": "delay", "label": "custom_delay", "params": {"delay_bars": delay}},
                ],
            }
        )
        store.record_outcome(
            {
                "decision_id": decision["decision_id"],
                "label": "actual",
                "utility": 0.0,
                "observed_at": f"2026-10-01T09:{i:02d}:00Z",
                "evidence": [f"a:{i}"],
            }
        )
        store.record_outcome(
            {
                "decision_id": decision["decision_id"],
                "label": "custom_delay",
                "utility": 1.0,
                "observed_at": f"2026-10-01T09:{i:02d}:30Z",
                "evidence": [f"b:{i}"],
            }
        )
    report = store.screening_report(min_samples=5)
    rows = [row for row in report["hypotheses"] if row["branch_label"] == "custom_delay"]
    assert len(rows) == 2
    assert {row["branch_params"]["delay_bars"] for row in rows} == {1, 2}
    assert {row["evidence_pair_count"] for row in rows} == {3}
    assert store.mutation_signals(min_samples=5) == []


def test_parallax_never_pools_statistical_evidence_across_code_revisions_or_contracts(tmp_path):
    store = ParallaxStore(tmp_path)
    for i in range(3):
        _record_pair(store, i, source_commit="a" * 40, contract_tag="a")
    for i in range(3, 6):
        _record_pair(store, i, source_commit="b" * 40, contract_tag="a")
    for i in range(6, 9):
        _record_pair(store, i, source_commit="a" * 40, contract_tag="b")
    signals = [s for s in store.mutation_signals(min_samples=5) if s["branch_label"] == "delay_1"]
    assert signals == []


def test_parallax_does_not_pool_regret_across_incomparable_contracts(tmp_path):
    store = ParallaxStore(tmp_path)
    _record_pair(store, 0, contract_tag="a")
    _record_pair(store, 1, contract_tag="b")
    snap = store.snapshot()
    assert snap["regret"]["comparable_globally"] is False
    assert snap["regret"]["mean_delta"] is None
    assert len(snap["regret"]["groups"]) == 2


def test_parallax_episode_clustering_prevents_correlated_pair_inflation(tmp_path):
    store = ParallaxStore(tmp_path)
    for i in range(10):
        _record_pair(store, i, delay_utility=1.0, episode_id="single-market-shock")

    signal = next(
        row for row in store.hypotheses(min_samples=5)
        if row["branch_label"] == "delay_1"
    )
    assert signal["evidence_pair_count"] == 10
    assert signal["effective_pair_count"] == 1
    assert signal["episode_dependence"]["episode_count"] == 1
    assert signal["episode_dependence"]["clustered_pair_count"] == 9
    assert signal["episode_dependence"]["largest_episode_size"] == 10
    assert signal["episode_dependence"]["used_episode_clustering"] is True
    assert "insufficient_independent_episodes" in signal["screen_blockers"]
    assert signal["candidate_eligible"] is False
    assert not [
        row for row in store.mutation_signals(min_samples=5)
        if row["branch_label"] == "delay_1"
    ]


def test_parallax_hac_can_reject_naive_significance_under_serial_dependence(tmp_path):
    store = ParallaxStore(tmp_path)
    values = [1.5] * 6 + [-0.2] * 6
    for i, value in enumerate(values):
        _record_pair(store, i, delay_utility=value)

    signal = next(
        row for row in store.hypotheses(min_samples=5)
        if row["branch_label"] == "delay_1"
    )
    assert signal["effective_pair_count"] == 12
    assert signal["ci95_low"] > 0
    assert signal["hac_inference"]["evaluable"] is True
    assert signal["hac_inference"]["ci95_low"] < 0
    assert signal["screen_ci95_low"] == pytest.approx(signal["hac_inference"]["ci95_low"])
    assert "dependence_adjusted_lower_bound_not_positive" in signal["screen_blockers"]
    assert signal["candidate_eligible"] is False


def test_parallax_cross_revision_contradiction_blocks_robust_readiness(tmp_path):
    store = ParallaxStore(tmp_path)
    for i in range(6):
        _record_pair(store, i, delay_utility=1.0, source_commit="a" * 40)
    for i in range(6, 12):
        _record_pair(store, i, delay_utility=-1.0, source_commit="b" * 40)

    rows = [
        row for row in store.hypotheses(min_samples=5)
        if row["branch_label"] == "delay_1"
    ]
    assert len(rows) == 2
    positive = next(row for row in rows if row["source_commit"] == "a" * 40)
    negative = next(row for row in rows if row["source_commit"] == "b" * 40)
    assert positive["candidate_eligible"] is True
    assert positive["transportability"]["evaluable"] is True
    assert positive["transportability"]["supporting_revision_count"] == 1
    assert positive["transportability"]["contradictory_revision_count"] == 1
    assert "cross_revision_contradiction" in positive["robustness_blockers"]
    assert positive["robust_candidate_eligible"] is False
    assert negative["screen_ci95_high"] < 0
    assert store.mutation_signals(min_samples=5) == []


def test_parallax_consistent_revisions_create_transportability_support(tmp_path):
    store = ParallaxStore(tmp_path)
    for i in range(6):
        _record_pair(store, i, delay_utility=1.0, source_commit="a" * 40)
    for i in range(6, 12):
        _record_pair(store, i, delay_utility=1.0, source_commit="b" * 40)

    rows = [
        row for row in store.mutation_signals(min_samples=5)
        if row["branch_label"] == "delay_1"
    ]
    assert len(rows) == 2
    for row in rows:
        assert row["effective_pair_count"] == 6
        assert row["hac_inference"]["evaluable"] is True
        assert row["transportability"]["evaluable"] is True
        assert row["transportability"]["stable"] is True
        assert row["transportability"]["supporting_revision_count"] == 2
        assert row["transportability"]["contradictory_revision_count"] == 0


def test_dreamstate_carries_dependence_and_transportability_evidence(tmp_path):
    store = ParallaxStore(tmp_path)
    for i in range(6):
        _record_pair(store, i, delay_utility=1.0, source_commit="a" * 40)
    for i in range(6, 12):
        _record_pair(store, i, delay_utility=1.0, source_commit="b" * 40)

    lab = DreamstateLab(tmp_path, parallax=store)
    state = lab.refresh(min_samples=5)
    delays = [
        c for c in state["candidates"]
        if c["mutation"]["op"] == "set_execution_delay_bars"
    ]
    assert len(delays) == 2
    for candidate in delays:
        acct = candidate["search_accounting"]
        robust = candidate["policy_contract"]["scope"]["source_robustness"]
        assert acct["source_effective_pairs"] == 6
        assert acct["source_hac_evaluable"] is True
        assert acct["source_transport_evaluable"] is True
        assert acct["source_transport_stable"] is True
        assert acct["source_transport_supporting_revisions"] == 2
        assert robust["hac_inference"]["evaluable"] is True
        assert robust["transportability"]["stable"] is True


def test_parallax_temporal_instability_blocks_robust_candidate_even_when_primary_screen_passes(tmp_path):
    store = ParallaxStore(tmp_path)
    for i in range(12):
        _record_pair(store, i, delay_utility=3.0 if i < 8 else -0.5)

    signal = next(
        row for row in store.hypotheses(min_samples=5)
        if row["branch_label"] == "delay_1"
    )
    assert signal["candidate_eligible"] is True
    assert signal["temporal_stability"]["evaluable"] is True
    assert signal["temporal_stability"]["fold_count"] == 3
    assert signal["temporal_stability"]["stable"] is False
    assert signal["temporal_stability"]["worst_fold_mean"] < 0
    assert "temporal_instability" in signal["robustness_blockers"]
    assert signal["robust_candidate_eligible"] is False
    assert not [
        row for row in store.mutation_signals(min_samples=5)
        if row["branch_label"] == "delay_1"
    ]

    report = store.screening_report(min_samples=5)
    assert report["candidate_ready"] >= 1
    assert report["robust_candidate_ready"] == 0
    assert report["robustness_blocker_counts"]["temporal_instability"] >= 1


def test_parallax_temporal_stability_allows_consistent_effect(tmp_path):
    store = ParallaxStore(tmp_path)
    for i in range(9):
        _record_pair(store, i, delay_utility=1.0)

    signal = next(
        row for row in store.mutation_signals(min_samples=5)
        if row["branch_label"] == "delay_1"
    )
    assert signal["candidate_eligible"] is True
    assert signal["robust_candidate_eligible"] is True
    assert signal["temporal_stability"]["evaluable"] is True
    assert signal["temporal_stability"]["stable"] is True
    assert signal["temporal_stability"]["positive_fold_fraction"] == 1.0
    assert signal["temporal_stability"]["worst_fold_mean"] > 0


def test_parallax_isolated_parameter_spike_is_withheld_from_robust_signals(tmp_path):
    store = ParallaxStore(tmp_path)
    for i in range(6):
        decision = store.record_decision(
            {
                "asset": "NQ",
                "action": "long",
                "observed_at": f"2026-10-01T10:{i:02d}:00Z",
                "regime": "trend",
                "source_commit": "a" * 40,
                "context": {"bar": i},
                "comparison_contract": _contract(),
                "subsystem_votes": {},
            }
        )
        store.record_outcome(
            {
                "decision_id": decision["decision_id"],
                "label": "actual",
                "utility": 0.0,
                "observed_at": f"2026-10-01T11:{i:02d}:00Z",
                "evidence": [f"actual:{i}"],
            }
        )
        for label, utility in (("stop_0.75", -0.2), ("stop_1.25", 1.0), ("stop_1.50", -0.2)):
            store.record_outcome(
                {
                    "decision_id": decision["decision_id"],
                    "label": label,
                    "utility": utility,
                    "observed_at": f"2026-10-01T11:{i:02d}:30Z",
                    "evidence": [f"{label}:{i}"],
                }
            )

    middle = next(
        row for row in store.hypotheses(min_samples=5)
        if row["branch_label"] == "stop_1.25"
    )
    assert middle["candidate_eligible"] is True
    assert middle["parameter_basin"]["evaluable"] is True
    assert middle["parameter_basin"]["neighbor_count"] == 2
    assert middle["parameter_basin"]["supporting_neighbor_count"] == 0
    assert middle["parameter_basin"]["isolated_spike"] is True
    assert middle["robust_candidate_eligible"] is False
    assert "isolated_parameter_spike" in middle["robustness_blockers"]
    assert not [
        row for row in store.mutation_signals(min_samples=5)
        if row["branch_label"] == "stop_1.25"
    ]

    lab = DreamstateLab(tmp_path, parallax=store)
    state = lab.refresh(min_samples=5)
    assert not [c for c in state["candidates"] if c["mutation"]["op"] == "scale_stop_distance"]


def test_parallax_parameter_plateau_is_robust_not_a_magic_point(tmp_path):
    store = ParallaxStore(tmp_path)
    for i in range(6):
        decision = store.record_decision(
            {
                "asset": "NQ",
                "action": "long",
                "observed_at": f"2026-10-01T12:{i:02d}:00Z",
                "regime": "trend",
                "source_commit": "a" * 40,
                "context": {"bar": i},
                "comparison_contract": _contract(),
                "subsystem_votes": {},
            }
        )
        store.record_outcome(
            {
                "decision_id": decision["decision_id"],
                "label": "actual",
                "utility": 0.0,
                "observed_at": f"2026-10-01T13:{i:02d}:00Z",
                "evidence": [f"actual:{i}"],
            }
        )
        for label, utility in (("stop_0.75", 0.8), ("stop_1.25", 1.0), ("stop_1.50", 0.9)):
            store.record_outcome(
                {
                    "decision_id": decision["decision_id"],
                    "label": label,
                    "utility": utility,
                    "observed_at": f"2026-10-01T13:{i:02d}:30Z",
                    "evidence": [f"{label}:{i}"],
                }
            )

    middle = next(
        row for row in store.mutation_signals(min_samples=5)
        if row["branch_label"] == "stop_1.25"
    )
    assert middle["parameter_basin"]["evaluable"] is True
    assert middle["parameter_basin"]["supporting_neighbor_count"] == 2
    assert middle["parameter_basin"]["isolated_spike"] is False
    assert middle["parameter_basin"]["basin_support_count"] == 3
    assert middle["parameter_basin"]["basin_width"] == pytest.approx(0.75)
    assert middle["robust_candidate_eligible"] is True


def test_dreamstate_retires_when_source_remains_statistical_but_loses_temporal_robustness(tmp_path):
    store = ParallaxStore(tmp_path)
    for i in range(5):
        _record_pair(store, i, delay_utility=2.0)
    lab = DreamstateLab(tmp_path, parallax=store)
    candidate = next(
        c for c in lab.refresh(min_samples=5)["candidates"]
        if c["mutation"]["op"] == "set_execution_delay_bars"
    )

    for i in range(5, 12):
        _record_pair(store, i, delay_utility=3.0 if i < 8 else -0.5)

    source = next(
        row for row in store.hypotheses(min_samples=5)
        if row["branch_label"] == "delay_1"
    )
    assert source["candidate_eligible"] is True
    assert source["robust_candidate_eligible"] is False
    assert "temporal_instability" in source["robustness_blockers"]

    refreshed = lab.refresh(min_samples=5)
    retired = next(c for c in refreshed["candidates"] if c["candidate_id"] == candidate["candidate_id"])
    assert retired["stage"] == "retired"
    assert candidate["candidate_id"] in refreshed["refresh"]["auto_retired_source_decay"]
    assert any("robustness screen" in item for item in retired["evidence"])


def test_parallax_temporally_unstable_neighbor_does_not_support_parameter_basin(tmp_path):
    store = ParallaxStore(tmp_path)
    for i in range(12):
        decision = store.record_decision(
            {
                "asset": "NQ",
                "action": "long",
                "observed_at": f"2026-10-01T14:{i:02d}:00Z",
                "regime": "trend",
                "source_commit": "a" * 40,
                "context": {"bar": i},
                "comparison_contract": _contract(),
                "subsystem_votes": {},
            }
        )
        store.record_outcome(
            {
                "decision_id": decision["decision_id"],
                "label": "actual",
                "utility": 0.0,
                "observed_at": f"2026-10-01T15:{i:02d}:00Z",
                "evidence": [f"actual:{i}"],
            }
        )
        stop075 = 3.0 if i < 8 else -0.5
        for label, utility in (("stop_0.75", stop075), ("stop_1.25", 1.0), ("stop_1.50", -0.2)):
            store.record_outcome(
                {
                    "decision_id": decision["decision_id"],
                    "label": label,
                    "utility": utility,
                    "observed_at": f"2026-10-01T15:{i:02d}:30Z",
                    "evidence": [f"{label}:{i}"],
                }
            )

    neighbor = next(row for row in store.hypotheses(min_samples=5) if row["branch_label"] == "stop_0.75")
    middle = next(row for row in store.hypotheses(min_samples=5) if row["branch_label"] == "stop_1.25")
    assert neighbor["candidate_eligible"] is True
    assert neighbor["temporal_stability"]["stable"] is False
    assert middle["candidate_eligible"] is True
    assert middle["temporal_stability"]["stable"] is True
    assert middle["parameter_basin"]["supporting_neighbor_count"] == 0
    assert middle["parameter_basin"]["isolated_spike"] is True
    assert middle["robust_candidate_eligible"] is False


def test_parallax_temporal_fold_tiebreak_is_deterministic_for_equal_timestamps():
    timestamp = "2026-10-01T16:00:00Z"
    samples = [
        (timestamp, decision_id, value)
        for decision_id, value in reversed([
            ("px-a", 1.0), ("px-b", 2.0), ("px-c", 3.0),
            ("px-d", 4.0), ("px-e", 5.0), ("px-f", 6.0),
            ("px-g", 7.0), ("px-h", 8.0), ("px-i", 9.0),
        ])
    ]
    result = ParallaxStore._temporal_stability(samples)
    assert result["evaluable"] is True
    assert [row["mean_delta"] for row in result["folds"]] == [2.0, 5.0, 8.0]
    assert result["stable"] is True


def test_dreamstate_live_gate_recheck_retires_after_temporal_robustness_collapses(tmp_path):
    store = ParallaxStore(tmp_path)
    for i in range(5):
        _record_pair(store, i, delay_utility=2.0)
    lab = DreamstateLab(tmp_path, parallax=store)
    candidate = next(
        c for c in lab.refresh(min_samples=5)["candidates"]
        if c["mutation"]["op"] == "set_execution_delay_bars"
    )
    assert candidate["stage"] == "proposed"

    for i in range(5, 12):
        _record_pair(store, i, delay_utility=2.0 if i < 8 else -1.0)

    with pytest.raises(ValueError, match="robustness screen"):
        lab.evaluate(
            candidate["candidate_id"],
            {"validation": {"provenance": True}, "evidence": ["temporal collapse detected live"]},
        )
    retired = lab.candidate(candidate["candidate_id"])
    assert retired["stage"] == "retired"
    assert any("robustness screen" in row for row in retired["evidence"])


def test_parallax_far_apart_parameter_points_do_not_create_fake_local_basin(tmp_path):
    store = ParallaxStore(tmp_path)
    for i in range(6):
        decision = store.record_decision(
            {
                "asset": "NQ",
                "action": "long",
                "observed_at": f"2026-10-01T17:{i:02d}:00Z",
                "regime": "trend",
                "source_commit": "a" * 40,
                "context": {"bar": i},
                "comparison_contract": _contract(),
                "subsystem_votes": {},
                "branches": [
                    {"kind": "actual", "label": "actual", "params": {"action": "long"}},
                    {"kind": "stop", "label": "stop_sparse_low", "params": {"stop_multiplier": 0.50}},
                    {"kind": "stop", "label": "stop_sparse_high", "params": {"stop_multiplier": 3.00}},
                ],
            }
        )
        store.record_outcome(
            {
                "decision_id": decision["decision_id"],
                "label": "actual",
                "utility": 0.0,
                "observed_at": f"2026-10-01T18:{i:02d}:00Z",
                "evidence": [f"actual:{i}"],
            }
        )
        for label, utility in (("stop_sparse_low", 1.0), ("stop_sparse_high", 0.9)):
            store.record_outcome(
                {
                    "decision_id": decision["decision_id"],
                    "label": label,
                    "utility": utility,
                    "observed_at": f"2026-10-01T18:{i:02d}:30Z",
                    "evidence": [f"{label}:{i}"],
                }
            )

    rows = [
        row for row in store.hypotheses(min_samples=5)
        if row["branch_label"] in {"stop_sparse_low", "stop_sparse_high"}
    ]
    assert len(rows) == 2
    for row in rows:
        assert row["candidate_eligible"] is True
        assert row["parameter_basin"]["neighbor_count"] == 0
        assert row["parameter_basin"]["family_evaluable_point_count"] == 2
        assert row["parameter_basin"]["local_support_missing"] is True
        assert "parameter_local_support_missing" in row["robustness_blockers"]
        assert row["robust_candidate_eligible"] is False


def test_parallax_parameter_basin_never_crosses_hidden_non_axis_parameters(tmp_path):
    store = ParallaxStore(tmp_path)
    for i in range(6):
        decision = store.record_decision(
            {
                "asset": "NQ",
                "action": "long",
                "observed_at": f"2026-10-01T19:{i:02d}:00Z",
                "regime": "trend",
                "source_commit": "a" * 40,
                "context": {"bar": i},
                "comparison_contract": _contract(),
                "subsystem_votes": {},
                "branches": [
                    {"kind": "actual", "label": "actual", "params": {"action": "long"}},
                    {
                        "kind": "stop",
                        "label": "stop_filter_a",
                        "params": {"stop_multiplier": 1.00, "entry_filter": "a"},
                    },
                    {
                        "kind": "stop",
                        "label": "stop_filter_b",
                        "params": {"stop_multiplier": 1.25, "entry_filter": "b"},
                    },
                ],
            }
        )
        store.record_outcome(
            {
                "decision_id": decision["decision_id"],
                "label": "actual",
                "utility": 0.0,
                "observed_at": f"2026-10-01T20:{i:02d}:00Z",
                "evidence": [f"actual:{i}"],
            }
        )
        for label in ("stop_filter_a", "stop_filter_b"):
            store.record_outcome(
                {
                    "decision_id": decision["decision_id"],
                    "label": label,
                    "utility": 1.0,
                    "observed_at": f"2026-10-01T20:{i:02d}:30Z",
                    "evidence": [f"{label}:{i}"],
                }
            )

    rows = [
        row for row in store.hypotheses(min_samples=5)
        if row["branch_label"] in {"stop_filter_a", "stop_filter_b"}
    ]
    assert len(rows) == 2
    for row in rows:
        assert row["candidate_eligible"] is True
        assert row["parameter_basin"]["neighbor_count"] == 0
        assert row["parameter_basin"]["family_evaluable_point_count"] == 1
        assert row["parameter_basin"]["local_support_missing"] is False
        assert row["parameter_basin"]["evaluable"] is False
        assert row["robust_candidate_eligible"] is True


def test_dreamstate_generates_scoped_hypothesis_but_caps_authority_at_qualified_shadow(tmp_path):
    store = ParallaxStore(tmp_path)
    for i in range(5):
        _record_pair(store, i)

    lab = DreamstateLab(tmp_path, parallax=store)
    state = lab.refresh(min_samples=5)
    candidates = [c for c in state["candidates"] if c["mutation"]["op"] == "set_execution_delay_bars"]
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate["stage"] == "proposed"
    assert all(value is None for value in candidate["validation"].values())
    assert candidate["policy_contract"]["scope"]["asset"] == "NQ"
    assert candidate["policy_contract"]["scope"]["comparison_contract"]["utility_metric"] == "r_multiple"
    assert candidate["policy_contract"]["automatic_activation"] is False
    assert candidate["search_accounting"]["source_q_value"] <= SOURCE_FDR_MAX
    assert candidate["search_accounting"]["comparison_contract_complete"] is True
    assert state["authority"]["maximum_stage"] == "qualified_shadow"
    assert state["authority"]["automatic_production_promotion"] is False
    assert state["authority"]["execution_authorized"] is False

    brain = brain_snapshot(tmp_path)
    mirrored = next(c for c in brain["candidates"] if c["candidate_id"] == candidate["candidate_id"])
    assert mirrored["stage"] == "discovered"
    assert mirrored["details"]["origin"] == "DREAMSTATE"
    assert mirrored["details"]["policy_contract"]["automatic_activation"] is False
    assert mirrored["eligible_for_regime_swap"] is False

    qualified = lab.evaluate(
        candidate["candidate_id"],
        {
            "validation": {gate: True for gate in REQUIRED_GATES},
            "evidence": ["independent protected evaluation fixture"],
        },
    )
    assert qualified["stage"] == "qualified_shadow"
    assert qualified["execution_authorized"] is False
    assert qualified["production_decision_authorized"] is False
    brain = brain_snapshot(tmp_path)
    mirrored = next(c for c in brain["candidates"] if c["candidate_id"] == candidate["candidate_id"])
    assert mirrored["stage"] == "qualified_shadow"
    assert mirrored["eligible_for_regime_swap"] is True


def test_dreamstate_builds_target_and_compound_hypotheses(tmp_path):
    store = ParallaxStore(tmp_path)
    decisions = []
    for i in range(5):
        decision = store.record_decision(
            {
                "asset": "NQ",
                "action": "long",
                "observed_at": f"2026-10-01T07:{i:02d}:00Z",
                "regime": "trend",
                "source_commit": "a" * 40,
                "context": {"bar": i},
                "comparison_contract": _contract(),
                "subsystem_votes": {},
            }
        )
        decisions.append(decision)
        for label, utility in (("actual", 0.0), ("target_1.25", 1.0), ("delay1_stop1.25", 1.2)):
            store.record_outcome(
                {
                    "decision_id": decision["decision_id"],
                    "label": label,
                    "utility": utility,
                    "observed_at": f"2026-10-01T08:{i:02d}:00Z",
                    "evidence": [f"{label}:{i}"],
                }
            )
    lab = DreamstateLab(tmp_path, parallax=store)
    state = lab.refresh(min_samples=5)
    ops = {c["mutation"]["op"] for c in state["candidates"]}
    assert "scale_target_distance" in ops
    assert "compound_policy" in ops
    compound = next(c for c in state["candidates"] if c["mutation"]["op"] == "compound_policy")
    assert len(compound["mutation"]["operations"]) >= 2
    assert compound["policy_contract"]["risk_authority"] is False


def test_dreamstate_keeps_one_active_trial_per_revision_contract_family_as_evidence_grows(tmp_path):
    store = ParallaxStore(tmp_path)
    for i in range(5):
        _record_pair(store, i)
    lab = DreamstateLab(tmp_path, parallax=store)
    first = lab.refresh(min_samples=5)
    active = [c for c in first["candidates"] if c["mutation"]["op"] == "set_execution_delay_bars"]
    assert len(active) == 1
    first_id = active[0]["candidate_id"]

    _record_pair(store, 5)
    second = lab.refresh(min_samples=5)
    same_family = [c for c in second["candidates"] if c["family_id"] == active[0]["family_id"]]
    assert len(same_family) == 1
    assert same_family[0]["candidate_id"] == first_id
    assert second["refresh"]["skipped_active_family"] >= 1
    assert second["family_trial_budget"] == 12


def test_dreamstate_isolates_families_across_source_revisions(tmp_path):
    store = ParallaxStore(tmp_path)
    for i in range(5):
        _record_pair(store, i, source_commit="a" * 40)
    for i in range(5, 10):
        _record_pair(store, i, source_commit="b" * 40)
    lab = DreamstateLab(tmp_path, parallax=store)
    state = lab.refresh(min_samples=5)
    delays = [c for c in state["candidates"] if c["mutation"]["op"] == "set_execution_delay_bars"]
    assert len(delays) == 2
    assert len({c["family_id"] for c in delays}) == 2
    assert len({c["source_commit"] for c in delays}) == 2


def test_dreamstate_auto_retires_active_candidate_when_source_screen_decays(tmp_path):
    store = ParallaxStore(tmp_path)
    for i in range(5):
        _record_pair(store, i, delay_utility=1.0)
    lab = DreamstateLab(tmp_path, parallax=store)
    first = lab.refresh(min_samples=5)
    candidate = next(c for c in first["candidates"] if c["mutation"]["op"] == "set_execution_delay_bars")
    assert candidate["stage"] == "proposed"

    for i in range(5, 15):
        _record_pair(store, i, delay_utility=-3.0)
    second = lab.refresh(min_samples=5)
    retired = next(c for c in second["candidates"] if c["candidate_id"] == candidate["candidate_id"])
    assert retired["stage"] == "retired"
    assert candidate["candidate_id"] in second["refresh"]["auto_retired_source_decay"]


def test_dreamstate_evaluation_rechecks_current_source_without_refresh(tmp_path):
    store = ParallaxStore(tmp_path)
    for i in range(5):
        _record_pair(store, i, delay_utility=1.0)
    lab = DreamstateLab(tmp_path, parallax=store)
    candidate = next(
        c for c in lab.refresh(min_samples=5)["candidates"]
        if c["mutation"]["op"] == "set_execution_delay_bars"
    )
    assert candidate["stage"] == "proposed"

    # Deteriorate the exact source hypothesis, but intentionally do not call refresh.
    for i in range(5, 15):
        _record_pair(store, i, delay_utility=-3.0)

    with pytest.raises(ValueError, match="source PARALLAX hypothesis"):
        lab.evaluate(
            candidate["candidate_id"],
            {"validation": {"provenance": True}, "evidence": ["stale-source evaluation attempt"]},
        )
    retired = lab.candidate(candidate["candidate_id"])
    assert retired["stage"] == "retired"
    assert any("source PARALLAX hypothesis" in item for item in retired["evidence"])


def test_dreamstate_failed_gate_is_terminal_for_candidate_revision(tmp_path):
    store = ParallaxStore(tmp_path)
    for i in range(5):
        _record_pair(store, i)
    lab = DreamstateLab(tmp_path, parallax=store)
    candidate = lab.refresh(min_samples=5)["candidates"][0]

    rejected = lab.evaluate(
        candidate["candidate_id"],
        {"validation": {"protected_holdout": False}, "evidence": ["holdout failure"]},
    )
    assert rejected["stage"] == "rejected"
    with pytest.raises(ValueError, match="terminal"):
        lab.evaluate(candidate["candidate_id"], {"validation": {"protected_holdout": True}})


def test_dreamstate_gate_preconditions_use_current_source_not_stale_frozen_q(tmp_path):
    store = ParallaxStore(tmp_path)
    for i in range(5):
        _record_pair(store, i)
    lab = DreamstateLab(tmp_path, parallax=store)
    candidate = lab.refresh(min_samples=5)["candidates"][0]

    # Corrupt only the frozen candidate snapshot. Current PARALLAX evidence remains valid.
    with lab._connect() as con:
        source = dict(candidate["source_signal"])
        source["q_value"] = 0.99
        con.execute(
            "UPDATE candidates SET source_signal_json=? WHERE candidate_id=?",
            (
                json.dumps(source, sort_keys=True, separators=(",", ":")),
                candidate["candidate_id"],
            ),
        )

    updated = lab.evaluate(
        candidate["candidate_id"],
        {"validation": {"multiple_testing": True}, "evidence": ["current source screen is authoritative"]},
    )
    assert updated["validation"]["multiple_testing"] is True
    assert updated["stage"] == "study"



def test_parallax_rejects_action_or_regime_alias_under_same_explicit_identity(tmp_path):
    store = ParallaxStore(tmp_path)
    base = {
        "asset": "NQ",
        "action": "long",
        "observed_at": "2026-10-01T05:10:00Z",
        "regime": "trend",
        "source_commit": "a" * 40,
        "context": {"price": 25000.0},
        "comparison_contract": _contract(),
        "subsystem_votes": {"athena": 0.7},
    }
    original = store.record_decision(base)

    with pytest.raises(ValueError, match="different immutable identity"):
        store.record_decision({**base, "decision_id": original["decision_id"], "action": "short"})
    with pytest.raises(ValueError, match="different immutable identity"):
        store.record_decision({**base, "decision_id": original["decision_id"], "regime": "range"})


def test_parallax_rejects_silent_branch_plan_rewrite(tmp_path):
    store = ParallaxStore(tmp_path)
    base = {
        "asset": "NQ",
        "action": "long",
        "observed_at": "2026-10-01T05:11:00Z",
        "regime": "trend",
        "source_commit": "a" * 40,
        "context": {"price": 25000.0},
        "comparison_contract": _contract(),
        "subsystem_votes": {},
        "branches": [
            {"kind": "actual", "label": "actual", "params": {"action": "long"}},
            {"kind": "delay", "label": "delay_1", "params": {"delay_bars": 1}},
        ],
    }
    store.record_decision(base)
    rewritten = {
        **base,
        "branches": [
            {"kind": "actual", "label": "actual", "params": {"action": "long"}},
            {"kind": "delay", "label": "delay_1", "params": {"delay_bars": 5}},
        ],
    }
    with pytest.raises(ValueError, match="different immutable branch plan"):
        store.record_decision(rewritten)


def test_parallax_rejects_outcome_timestamp_before_decision(tmp_path):
    store = ParallaxStore(tmp_path)
    decision = store.record_decision(
        {
            "asset": "NQ",
            "action": "long",
            "observed_at": "2026-10-01T05:12:00Z",
            "regime": "trend",
            "source_commit": "a" * 40,
            "context": {"price": 25000.0},
            "comparison_contract": _contract(),
            "subsystem_votes": {},
        }
    )
    with pytest.raises(ValueError, match="cannot precede the decision"):
        store.record_outcome(
            {
                "decision_id": decision["decision_id"],
                "label": "actual",
                "utility": 0.0,
                "observed_at": "2026-10-01T05:11:59Z",
                "evidence": ["causally impossible fixture"],
            }
        )


def test_parallax_requires_timezone_aware_timestamps(tmp_path):
    store = ParallaxStore(tmp_path)
    with pytest.raises(ValueError, match="timezone"):
        store.record_decision(
            {
                "asset": "NQ",
                "action": "long",
                "observed_at": "2026-10-01T05:12:00",
                "regime": "trend",
                "source_commit": "a" * 40,
                "context": {},
                "comparison_contract": _contract(),
                "subsystem_votes": {},
            }
        )

def test_parallax_dreamstate_are_visible_in_trader_interface():
    repo = Path(__file__).resolve().parents[1]
    dashboard = (repo / "icarus_engine" / "dashboard.html").read_text(encoding="utf-8")
    ui = (repo / "icarus_engine" / "parallax-ui.js").read_text(encoding="utf-8")
    server = (repo / "icarus_engine" / "server.py").read_text(encoding="utf-8")

    assert '/parallax-ui.js' in dashboard
    assert 'data-v="parallax">PARALLAX / DREAMSTATE</span>' in dashboard
    assert "wireParallax()" in dashboard
    assert "/api/parallax" in ui
    assert "/api/dreamstate" in ui
    assert "SHADOW ONLY" in ui
    assert 'p.path == "/api/parallax"' in server
    assert 'p.path == "/api/dreamstate"' in server
    assert 'p.path == "/admin/parallax/decision"' in server
    assert 'p.path == "/admin/parallax/outcome"' in server
    assert 'p.path == "/admin/dreamstate/refresh"' in server
    assert 'p.path == "/admin/dreamstate/evaluate"' in server

def test_dreamstate_auto_retires_active_candidate_when_source_disappears(tmp_path, monkeypatch):
    store = ParallaxStore(tmp_path)
    for i in range(5):
        _record_pair(store, i, delay_utility=1.0)
    lab = DreamstateLab(tmp_path, parallax=store)
    first = lab.refresh(min_samples=5)
    candidate = next(c for c in first["candidates"] if c["mutation"]["op"] == "set_execution_delay_bars")
    assert candidate["stage"] == "proposed"

    monkeypatch.setattr(store, "hypotheses", lambda *args, **kwargs: [])
    second = lab.refresh(min_samples=5)
    retired = next(c for c in second["candidates"] if c["candidate_id"] == candidate["candidate_id"])
    assert retired["stage"] == "retired"
    assert candidate["candidate_id"] in second["refresh"]["auto_retired_source_decay"]
    assert any("source signal is absent" in item for item in retired["evidence"])

def test_v4_robustness_versions_are_explicit_without_breaking_v2_schema(tmp_path):
    store = ParallaxStore(tmp_path)
    for i in range(5):
        _record_pair(store, i)
    report = store.screening_report(min_samples=5)
    snap = store.snapshot()
    lab = DreamstateLab(tmp_path, parallax=store)
    lab.refresh(min_samples=5)
    dream = lab.snapshot()

    assert snap["schema_version"] == "icarus-parallax-v2"
    assert snap["robustness_version"] == "icarus-parallax-robustness-v2"
    assert report["robustness_version"] == "icarus-parallax-robustness-v2"
    assert dream["schema_version"] == "icarus-dreamstate-v2"
    assert dream["robustness_version"] == "icarus-dreamstate-robustness-v2"


def test_operator_status_is_lightweight_and_read_only(tmp_path):
    p = ParallaxStore(tmp_path)
    d = DreamstateLab(tmp_path, parallax=p)
    ps = p.status()
    ds = d.status()
    assert ps["schema_version"] == "icarus-parallax-status-v1"
    assert ps["counts"] == {"decisions": 0, "branches": 0, "observed_outcomes": 0}
    assert ps["execution_authorized"] is False
    assert ds["schema_version"] == "icarus-dreamstate-status-v1"
    assert ds["candidate_count"] == 0
    assert ds["execution_authorized"] is False

