from __future__ import annotations

import pytest

from icarus_engine.ascendancy.work_orders import ResearchWorkOrderBoard


@pytest.mark.parametrize("outcome,completed", [("PASS", 1), ("FAIL", 1), ("INCONCLUSIVE", 0)])
def test_work_order_follows_accepted_evaluator_result(tmp_path, outcome, completed):
    from icarus_engine.ascendancy.evaluator import EvaluatorCascade
    from tests_engine.test_ascendancy_evaluator import _candidate, _receipt as evaluation

    cascade = EvaluatorCascade(tmp_path)
    candidate = _candidate()
    cascade.register_candidate(candidate)
    action = _action("RUN_EVALUATOR_STAGE", candidate["candidate_id"], "1" * 64,
                     stage="CONTRACT_VALIDATION")
    board = ResearchWorkOrderBoard(tmp_path)
    board.dispatch(_plan([action]), _executor([_receipt(action, "AWAITING_EXTERNAL_EVIDENCE")]))
    assert board.snapshot()["completed_count"] == 0
    saved = cascade.record(evaluation(candidate, "CONTRACT_VALIDATION", outcome=outcome))
    for view in (board.snapshot(), ResearchWorkOrderBoard(tmp_path).snapshot()):
        assert view["completed_count"] == completed
        order = view["orders"][0]
        assert order["domain_result"]["receipt_id"] == saved["receipt"]["receipt_id"]
        assert order["domain_result"]["outcome"] == outcome
        assert order["scientific_evidence"] is False


def _action(kind, subject, action_id, *, stage=None):
    details = {}
    if stage:
        details["stage"] = stage
    return {
        "action_id": action_id,
        "kind": kind,
        "subject_id": subject,
        "lane": "exploit",
        "niche_key": "fixture:niche",
        "estimated_cost_units": 1.0,
        "priority_score": 1.0,
        "priority_basis": "scheduler_heuristic_not_edge_score",
        "reason": "fixture",
        "details": details,
        "requires_external_evidence": True,
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


@pytest.mark.parametrize("outcome,completed", [("PASS", 1), ("FAIL", 1), ("INCONCLUSIVE", 0)])
def test_protected_holdout_work_order_follows_accepted_result(tmp_path, outcome, completed):
    from icarus_engine.ascendancy.evaluator import EvaluatorCascade, evaluation_stage_catalog
    from tests_engine.test_ascendancy_evaluator import _candidate, _receipt as evaluation

    cascade = EvaluatorCascade(tmp_path)
    candidate = _candidate()
    cascade.register_candidate(candidate)
    for stage in evaluation_stage_catalog():
        if stage["id"] == "PROTECTED_HOLDOUT":
            break
        cascade.record(evaluation(candidate, stage["id"]))
    action = _action("REQUEST_PROTECTED_HOLDOUT", candidate["candidate_id"], "2" * 64)
    board = ResearchWorkOrderBoard(tmp_path, evaluator=cascade)
    board.dispatch(_plan([action]), _executor([_receipt(action, "AWAITING_EXTERNAL_AUTHORITY")]))
    saved = cascade.record(evaluation(candidate, "PROTECTED_HOLDOUT", outcome=outcome,
                                      holdout_id="native-handoff-test-holdout"))
    view = board.snapshot()
    assert view["completed_count"] == completed
    assert view["orders"][0]["evaluator_stage"] is None
    assert view["orders"][0]["domain_result"]["receipt_id"] == saved["receipt"]["receipt_id"]


def _plan(actions):
    return {
        "schema_version": "icarus-ascendancy-governor-plan-v1",
        "plan_id": "p" * 64,
        "actions": actions,
        "execution_authorized": False,
        "production_decision_authorized": False,
        "can_mint_evaluator_receipts": False,
        "can_mint_qualification": False,
    }


def _executor(receipts):
    return {
        "schema_version": "icarus-ascendancy-safe-executor-v1",
        "plan_id": "p" * 64,
        "receipts": receipts,
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


def _receipt(action, status):
    return {
        "action_id": action["action_id"],
        "kind": action["kind"],
        "subject_id": action["subject_id"],
        "status": status,
        "scientific_evidence": False,
        "evaluator_receipt": False,
        "qualification_receipt": False,
        "trading_authority": False,
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


def test_dispatches_only_external_boundary_actions(tmp_path):
    eval_action = _action("RUN_EVALUATOR_STAGE", "a" * 64, "1" * 64, stage="ABLATION")
    internal = _action("REGISTER_WITH_EVALUATOR", "b" * 64, "2" * 64)
    holdout = _action("REQUEST_PROTECTED_HOLDOUT", "c" * 64, "3" * 64)
    plan = _plan([eval_action, internal, holdout])
    result = _executor([
        _receipt(eval_action, "AWAITING_EXTERNAL_EVIDENCE"),
        _receipt(internal, "APPLIED_INTERNAL"),
        _receipt(holdout, "AWAITING_EXTERNAL_AUTHORITY"),
    ])

    board = ResearchWorkOrderBoard(tmp_path)
    out = board.dispatch(plan, result)

    assert out["created_count"] == 2
    assert out["order_count"] == 2
    assert {x["kind"] for x in out["orders"]} == {
        "RUN_EVALUATOR_STAGE",
        "REQUEST_PROTECTED_HOLDOUT",
    }
    assert all(x["scientific_evidence"] is False for x in out["orders"])
    assert all(x["execution_authorized"] is False for x in out["orders"])


@pytest.mark.parametrize(
    "kind,stage,owner,work_type",
    [
        ("RUN_EVALUATOR_STAGE", "CONTRACT_VALIDATION", "daedalus", "EVALUATOR_EVIDENCE"),
        ("RUN_EVALUATOR_STAGE", "LOW_FIDELITY_REPLAY", "aion", "EVALUATOR_EVIDENCE"),
        ("RUN_EVALUATOR_STAGE", "CONDITIONAL_CONTRIBUTION", "daedalus", "EVALUATOR_EVIDENCE"),
        ("REQUEST_PROTECTED_HOLDOUT", None, "protected-qualification", "PROTECTED_HOLDOUT_REQUEST"),
        ("SUBMIT_FOR_INDEPENDENT_QUALIFICATION", None, "protected-qualification", "QUALIFICATION_REVIEW"),
        ("INCUBATE_CANDIDATE", None, "daedalus", "CANDIDATE_REVIEW"),
        ("GENERATE_UNKNOWN_HYPOTHESES", None, "aion", "HYPOTHESIS_SYNTHESIS"),
        ("SPAWN_GENOME_DESCENDANT", None, "omega", "ARCHITECTURE_MUTATION"),
        ("MINE_FEDERATED_CONTEXT", None, "omega", "FEDERATED_CONTEXT_ANALYSIS"),
        ("REVIEW_RESOURCE_EXHAUSTION", None, "omega", "RESOURCE_REVIEW"),
    ],
)
def test_work_order_routing_is_explicit(kind, stage, owner, work_type, tmp_path):
    action = _action(kind, "a" * 64, "1" * 64, stage=stage)
    status = (
        "AWAITING_EXTERNAL_AUTHORITY"
        if kind in {"REQUEST_PROTECTED_HOLDOUT", "SUBMIT_FOR_INDEPENDENT_QUALIFICATION"}
        else "AWAITING_EXTERNAL_EVIDENCE"
        if kind == "RUN_EVALUATOR_STAGE"
        else "AWAITING_EXTERNAL_RESEARCH"
    )
    if kind == "REVIEW_RESOURCE_EXHAUSTION":
        status = "AWAITING_EXTERNAL_REVIEW"
    out = ResearchWorkOrderBoard(tmp_path).dispatch(
        _plan([action]),
        _executor([_receipt(action, status)]),
    )
    order = out["orders"][0]
    assert order["owner_subsystem"] == owner
    assert order["work_type"] == work_type
    assert order["completion_requires_domain_receipt"] is True
    assert order["order_itself_is_evidence"] is False


def test_dispatch_is_wal_and_idempotent(tmp_path):
    action = _action("RUN_EVALUATOR_STAGE", "a" * 64, "1" * 64, stage="OOS")
    board = ResearchWorkOrderBoard(tmp_path)
    one = board.dispatch(
        _plan([action]),
        _executor([_receipt(action, "AWAITING_EXTERNAL_EVIDENCE")]),
    )
    two = board.dispatch(
        _plan([action]),
        _executor([_receipt(action, "AWAITING_EXTERNAL_EVIDENCE")]),
    )

    assert board.journal_mode == "wal"
    assert one["created_count"] == 1
    assert two["created_count"] == 0
    assert one["orders"][0]["order_id"] == two["orders"][0]["order_id"]
    assert board.snapshot()["order_count"] == 1


def test_claim_requires_declared_owner_and_is_not_evidence(tmp_path):
    action = _action("GENERATE_UNKNOWN_HYPOTHESES", "u" * 64, "1" * 64)
    board = ResearchWorkOrderBoard(tmp_path)
    order = board.dispatch(
        _plan([action]),
        _executor([_receipt(action, "AWAITING_EXTERNAL_RESEARCH")]),
    )["orders"][0]

    with pytest.raises(ValueError, match="owner"):
        board.claim(order["order_id"], worker_id="worker-1", owner_subsystem="omega")

    claimed = board.claim(
        order["order_id"],
        worker_id="aion-worker-1",
        owner_subsystem="aion",
    )
    assert claimed["status"] == "CLAIMED"
    assert claimed["claim_receipt"]["scientific_evidence"] is False
    assert claimed["claim_receipt"]["execution_authorized"] is False

    again = board.claim(
        order["order_id"],
        worker_id="aion-worker-1",
        owner_subsystem="aion",
    )
    assert again["idempotent"] is True

    with pytest.raises(ValueError, match="already claimed"):
        board.claim(
            order["order_id"],
            worker_id="aion-worker-2",
            owner_subsystem="aion",
        )


def test_work_orders_cannot_claim_authority_or_completion(tmp_path):
    action = _action("REQUEST_PROTECTED_HOLDOUT", "a" * 64, "1" * 64)
    action["execution_authorized"] = True
    with pytest.raises(ValueError, match="authority"):
        ResearchWorkOrderBoard(tmp_path).dispatch(
            _plan([action]),
            _executor([_receipt(action, "AWAITING_EXTERNAL_AUTHORITY")]),
        )


def test_snapshot_exposes_open_and_claimed_without_success_claims(tmp_path):
    first = _action("RUN_EVALUATOR_STAGE", "a" * 64, "1" * 64, stage="ROBUSTNESS")
    second = _action("MINE_FEDERATED_CONTEXT", "flow_microstructure", "2" * 64)
    board = ResearchWorkOrderBoard(tmp_path)
    out = board.dispatch(
        _plan([first, second]),
        _executor([
            _receipt(first, "AWAITING_EXTERNAL_EVIDENCE"),
            _receipt(second, "AWAITING_EXTERNAL_RESEARCH"),
        ]),
    )
    board.claim(
        out["orders"][0]["order_id"],
        worker_id=out["orders"][0]["owner_subsystem"] + "-worker",
        owner_subsystem=out["orders"][0]["owner_subsystem"],
    )
    snap = board.snapshot()
    assert snap["order_count"] == 2
    assert snap["open_count"] == 1
    assert snap["claimed_count"] == 1
    assert snap["completed_count"] == 0
    assert snap["truth_contract"]["work_order_is_not_scientific_evidence"] is True
    assert snap["truth_contract"]["domain_receipt_required_before_completion"] is True
