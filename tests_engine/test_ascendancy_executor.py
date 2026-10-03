from __future__ import annotations

import copy
import threading

import pytest

from icarus_engine.ascendancy.executor import (
    SAFE_INTERNAL_ACTION_KINDS,
    GovernorExecutor,
)
from icarus_engine.ascendancy.governor import build_governor_plan


def test_concurrent_execution_records_one_domain_transition(tmp_path):
    executor = GovernorExecutor(tmp_path)
    plan = _plan([_action("REGISTER_WITH_EVALUATOR", "a" * 64)])
    entered, second_entered, release = (threading.Event() for _ in range(3))
    calls, results, errors = [], [], []

    def handler(action):
        index = len(calls)
        calls.append(action["action_id"])
        if index == 0:
            entered.set()
            assert release.wait(5)
        else:
            second_entered.set()
        return {"candidate": {"candidate_id": action["subject_id"]},
                "idempotent": bool(index), "execution_authorized": False,
                "production_decision_authorized": False}

    def run():
        try:
            results.append(executor.execute(plan, {"REGISTER_WITH_EVALUATOR": handler}))
        except Exception as ex:
            errors.append(ex)

    first, second = threading.Thread(target=run), threading.Thread(target=run)
    first.start()
    assert entered.wait(5)
    second.start()
    second_entered.wait(0.2)
    release.set()
    first.join(5)
    second.join(5)
    assert not first.is_alive() and not second.is_alive()
    assert errors == []
    assert len(calls) == 1
    assert sorted(row["newly_applied_count"] for row in results) == [0, 1]
    assert executor.snapshot()["receipt_count"] == 1


def _plan(actions):
    plan = {
        "schema_version": "icarus-ascendancy-governor-plan-v1",
        "input_fingerprint": "f" * 64,
        "policy": {
            "max_actions_per_cycle": 8,
            "max_estimated_cost_units": 20.0,
            "exploration_fraction": 0.25,
            "max_actions_per_niche": 1,
            "allow_protected_holdout_request": True,
            "allow_federated_context_mining": True,
            "execution_authorized": False,
            "production_decision_authorized": False,
            "can_mint_qualification": False,
        },
        "candidate_action_count": len(actions),
        "action_count": len(actions),
        "selected_exploration_actions": sum(1 for x in actions if x.get("lane") == "explore"),
        "selected_exploitation_actions": sum(1 for x in actions if x.get("lane") == "exploit"),
        "selected_governance_actions": sum(1 for x in actions if x.get("lane") == "governance"),
        "estimated_cost_units": sum(float(x.get("estimated_cost_units", 0.0)) for x in actions),
        "actions": actions,
        "can_mint_evaluator_receipts": False,
        "can_mint_qualification": False,
        "execution_authorized": False,
        "production_decision_authorized": False,
        "truth_contract": {
            "governor_is_scheduler_not_evaluator": True,
            "governor_never_fabricates_evaluation_outcomes": True,
            "governor_never_invents_protected_holdout_identity": True,
            "governor_never_mints_qualification": True,
        },
    }
    import hashlib, json
    raw = json.dumps(plan, sort_keys=True, separators=(",", ":"), allow_nan=False)
    plan["plan_id"] = hashlib.sha256(raw.encode()).hexdigest()
    return plan


def _action(kind, subject, *, lane="exploit"):
    import hashlib, json
    row = {
        "kind": kind,
        "subject_id": subject,
        "lane": lane,
        "niche_key": "fixture:niche",
        "estimated_cost_units": 0.1,
        "priority_score": 1.0,
        "priority_basis": "scheduler_heuristic_not_edge_score",
        "reason": "fixture",
        "details": {},
        "requires_external_evidence": kind not in SAFE_INTERNAL_ACTION_KINDS,
        "execution_authorized": False,
        "production_decision_authorized": False,
    }
    raw = json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False)
    row["action_id"] = hashlib.sha256(raw.encode()).hexdigest()
    return row


def test_safe_internal_action_whitelist_is_narrow():
    assert SAFE_INTERNAL_ACTION_KINDS == frozenset({
        "REGISTER_WITH_EVALUATOR",
        "PROMOTE_BLUEPRINT_TO_FOUNDRY",
        "REJECT_FAILED_CANDIDATE",
    })


def test_executor_applies_only_safe_internal_actions(tmp_path):
    calls = []
    handlers = {
        "REGISTER_WITH_EVALUATOR": lambda action: calls.append(("register", action["subject_id"])) or {
            "candidate": {"candidate_id": action["subject_id"]},
            "execution_authorized": False,
            "production_decision_authorized": False,
        },
        "PROMOTE_BLUEPRINT_TO_FOUNDRY": lambda action: calls.append(("promote", action["subject_id"])) or {
            "candidate": {"candidate_id": "c" * 64},
            "execution_authorized": False,
            "production_decision_authorized": False,
        },
        "REJECT_FAILED_CANDIDATE": lambda action: calls.append(("reject", action["subject_id"])) or {
            "candidate_id": action["subject_id"],
            "stage": "REJECTED",
            "execution_authorized": False,
            "production_decision_authorized": False,
        },
        "RUN_EVALUATOR_STAGE": lambda action: (_ for _ in ()).throw(AssertionError("unsafe handler called")),
    }
    plan = _plan([
        _action("REGISTER_WITH_EVALUATOR", "a" * 64),
        _action("PROMOTE_BLUEPRINT_TO_FOUNDRY", "bp-1", lane="explore"),
        _action("REJECT_FAILED_CANDIDATE", "b" * 64, lane="governance"),
        _action("RUN_EVALUATOR_STAGE", "d" * 64),
        _action("REQUEST_PROTECTED_HOLDOUT", "e" * 64),
        _action("SUBMIT_FOR_INDEPENDENT_QUALIFICATION", "f" * 64),
    ])

    executor = GovernorExecutor(tmp_path)
    out = executor.execute(plan, handlers)

    assert calls == [
        ("register", "a" * 64),
        ("promote", "bp-1"),
        ("reject", "b" * 64),
    ]
    assert out["applied_count"] == 3
    assert out["external_count"] == 3
    assert out["failed_count"] == 0
    by_kind = {x["kind"]: x for x in out["receipts"]}
    assert by_kind["REGISTER_WITH_EVALUATOR"]["status"] == "APPLIED_INTERNAL"
    assert by_kind["RUN_EVALUATOR_STAGE"]["status"] == "AWAITING_EXTERNAL_EVIDENCE"
    assert by_kind["REQUEST_PROTECTED_HOLDOUT"]["status"] == "AWAITING_EXTERNAL_AUTHORITY"
    assert by_kind["SUBMIT_FOR_INDEPENDENT_QUALIFICATION"]["status"] == "AWAITING_EXTERNAL_AUTHORITY"
    assert out["execution_authorized"] is False
    assert out["production_decision_authorized"] is False


def test_executor_is_wal_and_idempotent_per_plan_action(tmp_path):
    calls = []
    plan = _plan([_action("REGISTER_WITH_EVALUATOR", "a" * 64)])
    handlers = {
        "REGISTER_WITH_EVALUATOR": lambda action: calls.append(action["action_id"]) or {
            "candidate": {"candidate_id": action["subject_id"]},
            "execution_authorized": False,
            "production_decision_authorized": False,
        }
    }
    executor = GovernorExecutor(tmp_path)

    one = executor.execute(plan, handlers)
    two = executor.execute(plan, handlers)

    assert executor.journal_mode == "wal"
    assert len(calls) == 1
    assert one["receipts"][0]["idempotent"] is False
    assert two["receipts"][0]["idempotent"] is True
    snap = executor.snapshot()
    assert snap["receipt_count"] == 1
    assert snap["applied_internal_count"] == 1


def test_executor_rejects_tampered_plan_and_action_identity(tmp_path):
    executor = GovernorExecutor(tmp_path)
    action = _action("REGISTER_WITH_EVALUATOR", "a" * 64)
    action["subject_id"] = "b" * 64
    # A valid outer envelope isolates the stale inner action identity. Mutating
    # an already signed plan would correctly trigger its plan_id guard first.
    plan = _plan([action])
    with pytest.raises(ValueError, match="action_id"):
        executor.execute(plan, {})

    plan = _plan([_action("REGISTER_WITH_EVALUATOR", "a" * 64)])
    plan["estimated_cost_units"] = 999.0
    with pytest.raises(ValueError, match="plan_id"):
        executor.execute(plan, {})


def test_executor_rejects_handler_output_that_claims_scientific_or_trading_authority(tmp_path):
    plan = _plan([_action("REGISTER_WITH_EVALUATOR", "a" * 64)])
    executor = GovernorExecutor(tmp_path)

    with pytest.raises(ValueError, match="authority"):
        executor.execute(plan, {
            "REGISTER_WITH_EVALUATOR": lambda _: {
                "execution_authorized": True,
            }
        })

    executor = GovernorExecutor(tmp_path / "second")
    with pytest.raises(ValueError, match="evaluator receipt"):
        executor.execute(plan, {
            "REGISTER_WITH_EVALUATOR": lambda _: {
                "receipt": {"outcome": "PASS"},
                "execution_authorized": False,
                "production_decision_authorized": False,
            }
        })


def test_executor_does_not_auto_apply_review_or_hypothesis_actions(tmp_path):
    calls = []
    plan = _plan([
        _action("INCUBATE_CANDIDATE", "a" * 64, lane="explore"),
        _action("GENERATE_UNKNOWN_HYPOTHESES", "u" * 64, lane="explore"),
        _action("SPAWN_GENOME_DESCENDANT", "g" * 64, lane="explore"),
        _action("MINE_FEDERATED_CONTEXT", "flow_microstructure", lane="explore"),
        _action("REVIEW_RESOURCE_EXHAUSTION", "b" * 64, lane="governance"),
    ])
    handlers = {
        kind: lambda action, kind=kind: calls.append((kind, action["subject_id"]))
        for kind in [x["kind"] for x in plan["actions"]]
    }
    out = GovernorExecutor(tmp_path).execute(plan, handlers)
    assert calls == []
    assert out["applied_count"] == 0
    assert out["external_count"] == len(plan["actions"])
    assert all(x["status"].startswith("AWAITING_") for x in out["receipts"])


def test_executor_receipts_are_administrative_not_evidence(tmp_path):
    plan = _plan([_action("PROMOTE_BLUEPRINT_TO_FOUNDRY", "bp-1", lane="explore")])
    executor = GovernorExecutor(tmp_path)
    out = executor.execute(plan, {
        "PROMOTE_BLUEPRINT_TO_FOUNDRY": lambda _: {
            "candidate": {"candidate_id": "c" * 64},
            "execution_authorized": False,
            "production_decision_authorized": False,
        }
    })
    receipt = out["receipts"][0]
    assert receipt["scientific_evidence"] is False
    assert receipt["evaluator_receipt"] is False
    assert receipt["qualification_receipt"] is False
    assert receipt["trading_authority"] is False
    assert executor.snapshot()["truth_contract"]["executor_receipts_are_not_scientific_evidence"] is True
