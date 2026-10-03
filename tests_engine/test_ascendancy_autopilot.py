from __future__ import annotations

import time

from icarus_engine.ascendancy.autopilot import GovernorAutopilot


def _plan(pid, actions=1):
    return {
        "plan": {
            "schema_version": "icarus-ascendancy-governor-plan-v1",
            "plan_id": pid,
            "action_count": actions,
            "actions": [{"action_id": (pid[0] * 64), "kind": "FIXTURE"}] if actions else [],
            "execution_authorized": False,
            "production_decision_authorized": False,
            "can_mint_evaluator_receipts": False,
            "can_mint_qualification": False,
        },
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


def _execution(plan, *, new, external=0, failed=0):
    return {
        "plan_id": plan["plan_id"],
        "receipt_count": new + external + failed,
        "applied_count": new,
        "newly_applied_count": new,
        "external_count": external,
        "failed_count": failed,
        "receipts": [],
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


def test_autopilot_replans_after_new_safe_transition_then_stops_at_external_boundary(tmp_path):
    plans = [_plan("a" * 64), _plan("b" * 64)]
    calls = {"plan": 0, "execute": 0}

    def planner():
        row = plans[calls["plan"]]
        calls["plan"] += 1
        return row

    def execute(plan):
        calls["execute"] += 1
        if calls["execute"] == 1:
            return _execution(plan, new=1)
        return _execution(plan, new=0, external=2)

    auto = GovernorAutopilot(
        tmp_path,
        plan_callback=planner,
        execute_callback=execute,
        interval_seconds=30,
        max_internal_iterations=5,
    )
    out = auto.run_cycle()

    assert calls == {"plan": 2, "execute": 2}
    assert out["status"] == "GREEN"
    assert out["stop_reason"] == "AWAITING_EXTERNAL_OR_QUIESCENT"
    assert out["iteration_count"] == 2
    assert out["new_internal_transition_count"] == 1
    assert out["awaiting_external_count"] == 2
    assert out["execution_authorized"] is False
    assert out["production_decision_authorized"] is False


def test_autopilot_stops_on_idempotent_replay_not_fake_progress(tmp_path):
    plan = _plan("c" * 64)
    calls = {"execute": 0}

    auto = GovernorAutopilot(
        tmp_path,
        plan_callback=lambda: plan,
        execute_callback=lambda p: calls.__setitem__("execute", calls["execute"] + 1) or _execution(p, new=0, external=1),
        interval_seconds=30,
        max_internal_iterations=5,
    )
    out = auto.run_cycle()
    assert calls["execute"] == 1
    assert out["new_internal_transition_count"] == 0
    assert out["stop_reason"] == "AWAITING_EXTERNAL_OR_QUIESCENT"


def test_autopilot_halts_on_internal_blocker(tmp_path):
    plan = _plan("d" * 64)
    auto = GovernorAutopilot(
        tmp_path,
        plan_callback=lambda: plan,
        execute_callback=lambda p: _execution(p, new=0, failed=1),
        interval_seconds=30,
    )
    out = auto.run_cycle()
    assert out["status"] == "DEGRADED"
    assert out["stop_reason"] == "BLOCKED_INTERNAL"
    assert out["blocked_count"] == 1


def test_autopilot_respects_internal_iteration_limit(tmp_path):
    counter = {"n": 0}

    def planner():
        counter["n"] += 1
        digit = format(counter["n"] % 16, "x")
        return _plan(digit * 64)

    auto = GovernorAutopilot(
        tmp_path,
        plan_callback=planner,
        execute_callback=lambda p: _execution(p, new=1),
        interval_seconds=30,
        max_internal_iterations=3,
    )
    out = auto.run_cycle()
    assert out["iteration_count"] == 3
    assert out["new_internal_transition_count"] == 3
    assert out["stop_reason"] == "INTERNAL_ITERATION_LIMIT"
    assert out["status"] == "DEGRADED"


def test_autopilot_cycle_ledger_is_wal_and_idempotent_for_same_quiescent_state(tmp_path):
    plan = _plan("e" * 64)
    auto = GovernorAutopilot(
        tmp_path,
        plan_callback=lambda: plan,
        execute_callback=lambda p: _execution(p, new=0, external=1),
        interval_seconds=30,
    )
    first = auto.run_cycle()
    second = auto.run_cycle()

    assert auto.journal_mode == "wal"
    assert first["idempotent"] is False
    assert second["idempotent"] is True
    assert first["cycle_id"] == second["cycle_id"]
    snap = auto.status()
    assert snap["cycle_count"] == 1
    assert snap["latest_cycle_id"] == first["cycle_id"]
    assert snap["execution_authorized"] is False
    assert snap["production_decision_authorized"] is False


def test_autopilot_failure_is_recorded_not_silently_treated_as_success(tmp_path):
    auto = GovernorAutopilot(
        tmp_path,
        plan_callback=lambda: (_ for _ in ()).throw(RuntimeError("planner exploded")),
        execute_callback=lambda _: {},
        interval_seconds=30,
    )
    out = auto.run_cycle()
    assert out["status"] == "DEGRADED"
    assert out["stop_reason"] == "ERROR"
    assert "planner exploded" in out["last_error"]
    assert out["new_internal_transition_count"] == 0


def test_background_worker_can_be_disabled_and_closed(tmp_path):
    calls = {"plan": 0}

    def planner():
        calls["plan"] += 1
        return _plan("f" * 64)

    auto = GovernorAutopilot(
        tmp_path,
        plan_callback=planner,
        execute_callback=lambda p: _execution(p, new=0, external=1),
        interval_seconds=1,
        enabled=False,
    )
    auto.start()
    time.sleep(0.05)
    assert calls["plan"] == 0
    assert auto.status()["worker_running"] is False
    auto.close()


def test_autopilot_truth_contract_keeps_external_evidence_and_qualification_outside_loop(tmp_path):
    plan = _plan("1" * 64)
    auto = GovernorAutopilot(
        tmp_path,
        plan_callback=lambda: plan,
        execute_callback=lambda p: _execution(p, new=0, external=3),
        interval_seconds=30,
    )
    auto.run_cycle()
    truth = auto.status()["truth_contract"]
    assert truth["autopilot_only_executes_safe_internal_actions"] is True
    assert truth["external_evidence_stops_internal_progression"] is True
    assert truth["protected_holdout_authority_remains_external"] is True
    assert truth["qualification_authority_remains_external"] is True
    assert truth["autopilot_cannot_trade"] is True
