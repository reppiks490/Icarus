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
):
    decision = store.record_decision(
        {
            "asset": "NQ",
            "action": "long",
            "observed_at": f"2026-10-01T05:{i:02d}:00Z",
            "regime": "trend-high-vol",
            "source_commit": source_commit,
            "context": {
                "bar": i,
                "vix_accel": 0.2,
                "session": "NY",
                "volatility_regime": "high",
            },
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
            {"decision_id": decision["decision_id"], "label": "actual", "utility": 0.0, "evidence": [f"a:{i}"]}
        )
        store.record_outcome(
            {"decision_id": decision["decision_id"], "label": "custom_delay", "utility": 1.0, "evidence": [f"b:{i}"]}
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


def test_dreamstate_multiple_testing_gate_cannot_bypass_source_screen(tmp_path):
    store = ParallaxStore(tmp_path)
    for i in range(5):
        _record_pair(store, i)
    lab = DreamstateLab(tmp_path, parallax=store)
    candidate = lab.refresh(min_samples=5)["candidates"][0]

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
    with pytest.raises(ValueError, match="FDR"):
        lab.evaluate(
            candidate["candidate_id"],
            {"validation": {"multiple_testing": True}, "evidence": ["attempted bypass"]},
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
