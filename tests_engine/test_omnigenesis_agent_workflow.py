"""Phase 18 research DAG orchestration tests: no live order or auto-promotion."""
import copy
import hashlib
import json
from datetime import datetime, timedelta, timezone

import pytest

from icarus_engine.omnigenesis.agent_workflow import (
    compile_research_workflow, execute_research_workflow
)

SOURCE = "b" * 40


def hash32(n):
    n &= 0xffffffff
    n = ((n ^ (n >> 16)) * 0x7feb352d) & 0xffffffff
    n = ((n ^ (n >> 15)) * 0x846ca68b) & 0xffffffff
    return (n ^ (n >> 16)) & 0xffffffff


def umbra_report():
    policy = {"trade": .72, "climate": .38, "medicine": .48,
              "innovation": .58, "migration": .48, "conservation": .48,
              "conflict": .25}
    rows = [{"seed": hash32(49021 + (i + 1) * 0x9e3779b1),
             "baseline": 90 + i, "treatment": 88 + i, "diff": 2,
             "foodDiff": 1.5, "emissionsDiff": -0.2} for i in range(3)]
    return {"version": "5.0.0", "seed": 49021, "trials": 3,
            "steps": 6, "baseline": policy,
            "treatment": {**policy, "trade": 0.0},
            "mean": 2, "median": 2, "p05": 2, "p95": 2,
            "sd": 0, "positive": 3, "paths": rows}


def job(name, op, args, deps=None, seconds=10):
    return {"task_id": name, "operator": op,
            "depends_on": deps or [], "parameters": args,
            "estimated_compute_seconds": seconds}


def manifest(tasks, budget=200):
    return {"schema_version": "icarus-omnigenesis-agent-workflow-v1",
            "name": "Validated ICARUS x UMBRA research-only workflow",
            "tasks": tasks, "compute_budget_seconds": budget}


def test_agentic_research_dag_sealed_replayed_and_read_only():
    spec = manifest([
        job("book", "synthetic_book", {"seed": 17, "steps": 20}, ["math"]),
        job("world", "umbra_worldline", {
            "report": umbra_report(), "claimed_source_commit": SOURCE}, ["math"]),
        job("math", "prime", {"n": 100}),
    ])
    plan = compile_research_workflow(spec)
    assert plan["status"] == "PLANNED_NOT_EXECUTED"
    assert [x["task_id"] for x in plan["tasks"]] == ["math", "book", "world"]
    assert plan["authority"]["execution_authorized"] is False
    assert plan["actual_broker_execution_authorized"] is False
    a = execute_research_workflow(plan)
    b = execute_research_workflow(plan)
    assert a == b
    assert a["counts"] == {"PASS": 3, "FAIL": 0, "BLOCKED": 0}
    assert a["status"] == "RESEARCH_ONLY_COMPLETE"
    assert a["scientific_qualification"] is False
    assert a["external_approval_required"] is True
    assert all(x["execution_authorized"] is False for x in a["receipts"])
    assert a["receipts"][0]["detail"]["next_prime"] == 101
    assert a["receipts"][-1]["detail"]["kind"] == "SYNTHETIC_MODEL_INTERNAL"
    assert a["receipts"][1]["previous_receipt"] == a["receipts"][0]["receipt_id"]
    assert a["final_receipt"] == a["receipts"][-1]["receipt_id"]
    assert len(a["run_id"]) == 64


def test_task_input_order_irrelevant_and_dependency_cycle_rejected():
    tasks = [job("second", "prime", {"n": 5}, ["first"]),
             job("first", "prime", {"n": 3})]
    assert compile_research_workflow(manifest(tasks)) == (
        compile_research_workflow(manifest(list(reversed(tasks)))))
    cyclic = [job("alpha", "prime", {"n": 1}, ["beta"]),
              job("beta", "prime", {"n": 2}, ["alpha"])]
    with pytest.raises(ValueError, match="dependency cycle"):
        compile_research_workflow(manifest(cyclic))


def test_fail_closed_status_and_downstream_blocking_on_missing_file():
    flow = compile_research_workflow(manifest([
        job("intake", "market_intake", {"path": "/not/a/real/tape.jsonl",
                                      "manifest": {}}, seconds=10),
        job("theory", "prime", {"n": 3}, ["intake"]),
    ]))
    result = execute_research_workflow(flow)
    assert result["counts"] == {"PASS": 0, "FAIL": 1, "BLOCKED": 1}
    assert result["status"] == "RESEARCH_ONLY_REVIEW_REQUIRED"
    assert result["receipts"][0]["detail"]["error_code"] == "RESEARCH_OPERATOR_REJECTED"
    assert result["receipts"][1]["detail"]["reason"] == "dependency did not pass"


@pytest.mark.parametrize("operation,pattern", [
    (lambda p: p["authority"].update(execution_authorized=True), "authority"),
    (lambda p: p.update(actual_broker_execution_authorized=True), "authority"),
    (lambda p: p["tasks"][0]["parameters"].update(n=999), "tampered"),
    (lambda p: p.update(status="RUNNING"), "prepared"),
])
def test_reject_mutated_seal_or_authority(operation, pattern):
    plan = compile_research_workflow(manifest([job("math", "prime", {"n": 5})]))
    operation(plan)
    with pytest.raises(ValueError, match=pattern):
        execute_research_workflow(plan)


def test_unknown_agents_shell_or_order_operations_refused():
    for op in ("execute_order", "shell", "pip_install", "broker_connect",
               "arbitrary_llm", "deploy", "external_http"):
        with pytest.raises(ValueError, match="unapproved workflow operator"):
            compile_research_workflow(manifest([job("bad", op, {})]))


def test_invalid_budget_unknown_dependency_and_huge_steps_refused():
    with pytest.raises(ValueError, match="budget"):
        compile_research_workflow(manifest(
            [job("math", "prime", {"n": 7}, seconds=100)], budget=2))
    with pytest.raises(ValueError, match="missing workflow dependency"):
        compile_research_workflow(manifest(
            [job("math", "prime", {"n": 7}, ["phantom"])]))
    with pytest.raises(ValueError, match="synthetic event cap"):
        compile_research_workflow(manifest(
            [job("book", "synthetic_book", {"seed": 0, "steps": 2000})]))


def test_worker_intake_uses_actual_operator_bytes_without_promoting_provenance(tmp_path):
    received = "2026-01-01T00:00:01+00:00"
    row = {"event_id": "x1", "sequence": 1, "contract": "NQZ6",
           "observed_at": "2026-01-01T00:00:00+00:00", "received_at": received,
           "event_type": "trade", "side": "buy", "price_ticks": 2000, "quantity": 1}
    path = tmp_path / "local_tape.jsonl"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    intake_manifest = {
        "schema_version": "icarus-omnigenesis-market-manifest-v1",
        "dataset_id": "local-adversarial-fixture",
        "provider": "TEST FIXTURE", "venue": "TEST", "asset": "NQ",
        "source_category": "TRADES_NORMALIZED",
        "license_reference": "NO REAL RIGHTS ASSERTED",
        "expected_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "expected_records": 1,
        "contracts": [{"symbol": "NQZ6", "start_at": "2025-12-31T00:00:00Z",
                       "end_at": "2026-01-02T00:00:00Z", "tick_size": "0.25"}],
        "capture_cutoff": "2026-01-03T00:00:00Z",
    }
    plan = compile_research_workflow(manifest([
        job("intake", "market_intake", {
            "path": str(path), "manifest": intake_manifest})]))
    result = execute_research_workflow(plan)
    assert result["counts"] == {"PASS": 1, "FAIL": 0, "BLOCKED": 0}
    detail = result["receipts"][0]["detail"]
    assert detail["kind"] == "DECLARED_OBSERVED_BYTES_CHECKED"
    assert detail["source_authenticity_verified"] is False
    assert detail["provider_license_verified"] is False
    assert detail["record_count"] == 1
    assert "x1" not in json.dumps(result)


def test_verified_run_stored_as_immutable_scientific_artifact(tmp_path):
    from icarus_engine.omnigenesis import ResearchLedger
    store = ResearchLedger(tmp_path)
    plan = compile_research_workflow(manifest([
        job("math", "prime", {"n": 100}),
        job("world", "umbra_worldline", {"report": umbra_report(),
                                        "claimed_source_commit": SOURCE}, ["math"]),
    ]))
    result = execute_research_workflow(plan)
    first = store.append_artifact("agent_workflow", result)
    assert first == store.append_artifact("agent_workflow", result)
    snap = store.snapshot()
    assert snap["artifact_count"] == 1
    assert snap["study_count"] == 0
    assert snap["recent_artifacts"][0]["kind"] == "agent_workflow"
    assert snap["recent_artifacts"][0]["status"] == "RESEARCH_ONLY"
    assert snap["recent_artifacts"][0]["metric"] == 2
    assert snap["recent_artifacts"][0]["research_only"] is True
    assert snap["authority"]["execution_authorized"] is False


def test_ledger_rejects_spoofed_workflow_status_and_receipt_chain(tmp_path):
    from icarus_engine.omnigenesis import ResearchLedger
    from icarus_engine.omnigenesis.contracts import identity
    store = ResearchLedger(tmp_path)
    original = execute_research_workflow(compile_research_workflow(
        manifest([job("math", "prime", {"n": 6})])))
    changed = copy.deepcopy(original)
    changed["receipts"][0]["detail"]["next_prime"] = 999
    changed["run_id"] = identity({k: v for k, v in changed.items() if k != "run_id"})
    with pytest.raises(ValueError, match="tampered workflow receipt"):
        store.append_artifact("agent_workflow", changed)
    changed = copy.deepcopy(original)
    changed["status"] = "APPROVED_FOR_TRADING"
    changed["run_id"] = identity({k: v for k, v in changed.items() if k != "run_id"})
    with pytest.raises(ValueError, match="authority or status"):
        store.append_artifact("agent_workflow", changed)
    changed = copy.deepcopy(original)
    changed["counts"]["PASS"] = 0
    changed["run_id"] = identity({k: v for k, v in changed.items() if k != "run_id"})
    with pytest.raises(ValueError, match="workflow count"):
        store.append_artifact("agent_workflow", changed)


def test_operator_cli_workflow_execution_persists_only_derived_receipts(tmp_path):
    import subprocess
    import sys
    from icarus_engine.omnigenesis import ResearchLedger

    payload = manifest([job("math", "prime", {"n": 1009})])
    spec = tmp_path / "workflow.json"
    spec.write_text(json.dumps(payload), encoding="utf-8")
    target = tmp_path / "first-run.json"
    cmd = [sys.executable, "-m", "icarus_engine.omnigenesis",
           "workflow", str(spec), "--execute", "--root", str(tmp_path),
           "--output", str(target)]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    report = json.loads(proc.stdout)
    assert report["counts"]["PASS"] == 1
    assert report["receipts"][0]["detail"]["next_prime"] == 1013
    assert json.loads(target.read_text()) == report
    snap = ResearchLedger(tmp_path).snapshot()
    assert snap["recent_artifacts"][0]["kind"] == "agent_workflow"
    assert snap["recent_artifacts"][0]["source_id"] == report["run_id"]
    # Exclusive receipt creation: second run must not overwrite operator evidence.
    again = subprocess.run(cmd, capture_output=True, text=True)
    assert again.returncode != 0
    assert json.loads(target.read_text()) == report


def _paper_cfg():
    return {"schema_version": "icarus-omnigenesis-paper-execution-v1",
            "seed": 12, "bars": 160,
            "strategy": {"kind": "SMA_CROSS", "fast": 3, "slow": 10,
                         "direction": "trend"},
            "execution": {"contracts": 1, "tick_value_cents": 125,
                          "fee_per_contract_cents": 200, "slippage_ticks": 2,
                          "latency_bars": 1},
            "risk": {"initial_cash_cents": 10_000_000,
                     "max_loss_cents": 5_000_000,
                     "max_drawdown_cents": 5_000_000,
                     "max_order_events": 100}}


def test_agent_workflow_paper_execution_and_tournament_only_in_science_ledger(tmp_path):
    from icarus_engine.omnigenesis import ResearchLedger
    from icarus_engine.omnigenesis.contracts import identity
    paper = _paper_cfg()
    tournament = {
        "schema_version": "icarus-omnigenesis-paper-arena-v1",
        "seed": paper["seed"], "bars": 180,
        "candidates": [
            {"kind": "SMA_CROSS", "fast": 3, "slow": 10, "direction": "trend"},
            {"kind": "SMA_CROSS", "fast": 4, "slow": 15, "direction": "reversion"},
        ],
        "execution": paper["execution"], "risk": paper["risk"]
    }
    plan = compile_research_workflow(manifest([
        job("paper", "paper_execution", {"spec": paper}),
        job("arena", "paper_tournament", {"spec": tournament}, ["paper"]),
    ]))
    report = execute_research_workflow(plan)
    assert report["counts"] == {"PASS": 2, "FAIL": 0, "BLOCKED": 0}
    assert report["no_network_or_broker_operations"] is True
    assert report["authority"]["execution_authorized"] is False
    assert report["receipts"][0]["detail"]["broker_order_count"] == 0
    assert report["receipts"][0]["detail"]["profitability_verified"] is False
    assert report["receipts"][1]["detail"]["strategy_promoted"] is False
    assert report["receipts"][1]["detail"]["kind"] == "SYNTHETIC_CHALLENGER_TOURNAMENT"
    assert report["receipts"][0]["detail"]["kind"] == "SYNTHETIC_PAPER_EXECUTION"
    assert report["run_id"] == identity({k: v for k, v in report.items() if k != "run_id"})
    ledger = ResearchLedger(tmp_path)
    ledger.append_artifact("agent_workflow", report)
    snapshot = ledger.snapshot()
    assert snapshot["artifact_count"] == 1
    assert snapshot["recent_artifacts"][0]["kind"] == "agent_workflow"
    assert snapshot["recent_artifacts"][0]["status"] == "RESEARCH_ONLY"


def test_agent_workflow_rejects_paper_broker_injection_and_blocks_dependencies():
    bad = _paper_cfg()
    bad["execution"]["exchange_api_key"] = "should-not-be-accepted"
    plan = compile_research_workflow(manifest([
        job("unsafe", "paper_execution", {"spec": bad}),
        job("downstream", "prime", {"n": 17}, ["unsafe"]),
    ]))
    run = execute_research_workflow(plan)
    assert run["status"] == "RESEARCH_ONLY_REVIEW_REQUIRED"
    assert run["counts"] == {"PASS": 0, "FAIL": 1, "BLOCKED": 1}
    assert run["receipts"][0]["detail"]["error_code"] == "RESEARCH_OPERATOR_REJECTED"
    assert run["receipts"][1]["status"] == "BLOCKED"
    assert run["authority"]["auto_promote"] is False


def test_paper_cli_prints_research_receipt_without_mutating_ledger(tmp_path):
    import subprocess
    import sys
    from icarus_engine.omnigenesis import ResearchLedger
    payload = _paper_cfg()
    path = tmp_path / "paper.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    cmd = [sys.executable, "-m", "icarus_engine.omnigenesis", "paper", str(path)]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    report = json.loads(proc.stdout)
    assert report["authority"]["execution_authorized"] is False
    assert report["broker_order_count"] == 0
    assert report["results"]["final_position_contracts"] == 0
    assert ResearchLedger(tmp_path).snapshot()["artifact_count"] == 0


def _router_spec(mismatch=False):
    def evt(n, action, **kwargs):
        return {"event_id": f"evt_{n}", "sequence": n,
                "received_at": f"2026-01-01T00:00:0{n}+00:00",
                "action": action, **kwargs}
    return {
        "schema_version": "icarus-omnigenesis-offline-order-router-v1",
        "mode": "OFFLINE_SANDBOX", "asset": "NQ",
        "max_position_contracts": 2, "max_single_order_contracts": 2,
        "max_active_orders": 2,
        "events": [
            evt(1, "SUBMIT", order_id="o1", side="BUY",
                quantity=1, limit_ticks=10000),
            evt(2, "ACK", order_id="o1"),
            evt(3, "FILL", order_id="o1", execution_id="x1",
                quantity=1, price_ticks=10000),
            evt(4, "RECONCILE", position_contracts=0 if mismatch else 1),
        ],
    }


def test_router_operator_receipt_can_enter_research_ledger_without_broker_actions(tmp_path):
    from icarus_engine.omnigenesis import ResearchLedger
    plan = compile_research_workflow(manifest([
        job("mock_orders", "offline_order_router", {"spec": _router_spec()}),
        job("inspect", "prime", {"n": 10}, ["mock_orders"]),
    ]))
    run = execute_research_workflow(plan)
    assert run["counts"] == {"PASS": 2, "FAIL": 0, "BLOCKED": 0}
    node = run["receipts"][0]["detail"]
    assert node["kind"] == "SIMULATED_ORDER_LIFECYCLE"
    assert node["broker_order_count"] == 0
    assert node["mock_filled_contracts"] == 1
    assert node["source_authenticity_verified"] is False
    assert node["execution_authorized"] is False
    store = ResearchLedger(tmp_path)
    store.append_artifact("agent_workflow", run)
    assert store.snapshot()["recent_artifacts"][0]["status"] == "RESEARCH_ONLY"


def test_reconciliation_mismatch_fails_and_blocks_downstream_agent_research():
    plan = compile_research_workflow(manifest([
        job("router", "offline_order_router", {"spec": _router_spec(mismatch=True)}),
        job("downstream", "prime", {"n": 10}, ["router"]),
    ]))
    run = execute_research_workflow(plan)
    assert run["counts"] == {"PASS": 0, "FAIL": 1, "BLOCKED": 1}
    assert run["status"] == "RESEARCH_ONLY_REVIEW_REQUIRED"
    assert run["receipts"][0]["detail"]["error_code"] == "RESEARCH_OPERATOR_REJECTED"
    assert run["receipts"][1]["status"] == "BLOCKED"
    assert run["authority"]["execution_authorized"] is False


def test_router_cli_is_local_and_does_not_touch_research_ledger(tmp_path):
    import subprocess
    import sys
    from icarus_engine.omnigenesis import ResearchLedger
    payload = _router_spec()
    path = tmp_path / "offline-router.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "icarus_engine.omnigenesis",
         "offline-router", str(path)],
        capture_output=True, text=True, check=True)
    report = json.loads(proc.stdout)
    assert report["broker_order_count"] == 0
    assert report["position_contracts"] == 1
    assert report["actual_exchange_reconciled"] is False
    assert report["authority"]["execution_authorized"] is False
    assert ResearchLedger(tmp_path).snapshot()["artifact_count"] == 0
