"""Phase 18: explicitly invoked, bounded, evidence-only research agent workflow.

This is a deterministic *local* DAG executor over a small allowlist of
research operators, NOT an LLM agent that can issue shell commands, trade,
install tools, schedule jobs, call paid services, or approve its results.
ASCENDANCY remains the external governor. APEX and DAEDALUS remain independent.
"""
from __future__ import annotations

import math
from pathlib import Path
import re
from typing import Any, Mapping

from .contracts import canonical_bytes, identity
from .arithmetic import next_prime
from .automata import compile_automaton
from .formal import formal_certificate
from .simulation import replay_book, synthetic_scenario
from .data_intake import inspect_market_tape
from .umbra_bridge import audit_umbra_worldlines
from .paper_harness import run_paper_execution, tournament_paper_strategies

_AUTHORITY = {"research_only": True, "execution_authorized": False,
              "production_decision_authorized": False, "auto_promote": False}
_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,47}$")
_OPERATORS = {
    "prime": {"n"},
    "synthetic_book": {"seed", "steps"},
    "market_intake": {"path", "manifest"},
    "umbra_worldline": {"report", "claimed_source_commit"},
    "formal": {"spec"},
    "paper_execution": {"spec"},
    "paper_tournament": {"spec"},
}
_EXPECTED_TASK = {"task_id", "operator", "depends_on", "parameters",
                  "estimated_compute_seconds"}


def _integer(value: Any, low: int, high: int, field: str) -> int:
    if type(value) is not int or not low <= value <= high:
        raise ValueError("invalid " + field)
    return value


def _validate_task(task: Mapping[str, Any]) -> dict:
    if not isinstance(task, Mapping) or set(task) != _EXPECTED_TASK:
        raise ValueError("invalid workflow task schema")
    tid = task["task_id"]
    if not isinstance(tid, str) or not _NAME.fullmatch(tid):
        raise ValueError("invalid task ID")
    operator = task["operator"]
    if operator not in _OPERATORS:
        raise ValueError("unapproved workflow operator")
    dependencies = task["depends_on"]
    if (not isinstance(dependencies, list) or len(dependencies) > 23
            or any(not isinstance(x, str) or not _NAME.fullmatch(x)
                   for x in dependencies)
            or len(set(dependencies)) != len(dependencies)
            or tid in dependencies):
        raise ValueError("invalid task dependencies")
    params = task["parameters"]
    if not isinstance(params, Mapping) or set(params) != _OPERATORS[operator]:
        raise ValueError("operator parameter contract mismatch")
    if operator == "prime":
        _integer(params["n"], 1, 100_000_000, "prime input")
    elif operator == "synthetic_book":
        _integer(params["seed"], 0, 0xffffffff, "synthetic seed")
        _integer(params["steps"], 2, 500, "synthetic event cap")
    elif operator == "market_intake":
        path = params["path"]
        if not isinstance(path, str) or not 1 <= len(path) <= 4096 or "\0" in path:
            raise ValueError("invalid explicit market file path")
        if not isinstance(params["manifest"], Mapping):
            raise ValueError("intake manifest must be an object")
    elif operator == "umbra_worldline":
        if not isinstance(params["report"], Mapping):
            raise ValueError("UMBRA report must be an object")
        if not isinstance(params["claimed_source_commit"], str):
            raise ValueError("missing UMBRA claimed source")
    elif operator in ("paper_execution", "paper_tournament"):
        if not isinstance(params["spec"], Mapping):
            raise ValueError("paper harness spec must be an object")
    elif operator == "formal":
        if not isinstance(params["spec"], Mapping):
            raise ValueError("formal specification must be an object")
    seconds = _integer(task["estimated_compute_seconds"], 1, 3600, "task estimate")
    return {"task_id": tid, "operator": operator,
            "depends_on": sorted(dependencies),
            "parameters": dict(params),
            "estimated_compute_seconds": seconds}


def compile_research_workflow(spec: Mapping[str, Any]) -> dict:
    """Validate and seal a finite DAG; nothing executes at compile time."""
    if not isinstance(spec, Mapping) or set(spec) != {
            "schema_version", "name", "tasks", "compute_budget_seconds"}:
        raise ValueError("invalid workflow schema")
    if spec["schema_version"] != "icarus-omnigenesis-agent-workflow-v1":
        raise ValueError("unsupported workflow version")
    name = spec["name"]
    if not isinstance(name, str) or not 3 <= len(name) <= 100:
        raise ValueError("invalid workflow name")
    budget = _integer(spec["compute_budget_seconds"], 1, 3600, "workflow estimate budget")
    raw = spec["tasks"]
    if not isinstance(raw, list) or not 1 <= len(raw) <= 24:
        raise ValueError("workflow must have 1–24 tasks")
    if len(canonical_bytes(spec)) > 2_000_000:
        raise ValueError("workflow input exceeds byte cap")
    items = [_validate_task(x) for x in raw]
    by_id = {x["task_id"]: x for x in items}
    if len(by_id) != len(items):
        raise ValueError("duplicate workflow task")
    if sum(x["estimated_compute_seconds"] for x in items) > budget:
        raise ValueError("estimated work exceeds workflow budget")
    if any(not set(x["depends_on"]).issubset(by_id) for x in items):
        raise ValueError("missing workflow dependency")
    # Input-order independence and fail-closed cycle detection.
    ready = set()
    pending = dict(by_id)
    ordered = []
    while pending:
        next_id = next((tid for tid in sorted(pending)
                        if set(pending[tid]["depends_on"]).issubset(ready)), None)
        if next_id is None:
            raise ValueError("dependency cycle")
        ordered.append(pending.pop(next_id))
        ready.add(next_id)
    plan = {
        "schema_version": spec["schema_version"],
        "name": name,
        "authority": dict(_AUTHORITY),
        "status": "PLANNED_NOT_EXECUTED",
        "estimated_compute_budget_seconds": budget,
        "task_count": len(ordered),
        "tasks": ordered,
        "unverified_estimates": True,
        "external_governance": "ASCENDANCY",
        "independent_review": ["APEX", "DAEDALUS"],
        "actual_broker_execution_authorized": False,
    }
    plan["plan_id"] = identity(plan)
    return plan


def _execute_operator(item: dict) -> dict:
    op, arg = item["operator"], item["parameters"]
    if op == "prime":
        value = next_prime(arg["n"])
        return {"kind": "MATHEMATICAL", "input": arg["n"], "next_prime": value}
    if op == "synthetic_book":
        report = replay_book(synthetic_scenario(arg["seed"], arg["steps"]))
        if report["quantity_conserved"] is not True:
            raise ValueError("synthetic quantity accounting failed")
        return {"kind": "SYNTHETIC", "scenario_id": report["scenario_id"],
                "trade_count": report["trade_count"], "submitted_quantity": report["submitted_quantity"],
                "executed_quantity": report["executed_quantity"], "quantity_conserved": True}
    if op == "market_intake":
        receipt = inspect_market_tape(arg["path"], arg["manifest"],
                                     max_bytes=50_000_000, max_records=100_000)
        return {"kind": "DECLARED_OBSERVED_BYTES_CHECKED", "receipt_id": receipt["report_id"],
                "tape_sha256": receipt["tape_sha256"], "record_count": receipt["record_count"],
                "source_authenticity_verified": False, "provider_license_verified": False}
    if op == "umbra_worldline":
        receipt = audit_umbra_worldlines(
            arg["report"], claimed_source_commit=arg["claimed_source_commit"]
        )
        return {"kind": "SYNTHETIC_MODEL_INTERNAL", "receipt_id": receipt["receipt_id"],
                "all_seed_and_aggregate_checks_passed": True, "engine_replay_verified": False}
    if op == "paper_execution":
        report = run_paper_execution(arg["spec"])
        return {"kind": "SYNTHETIC_PAPER_EXECUTION", "receipt_id": report["receipt_id"],
                "synthetic_net_pnl_cents": report["results"]["net_pnl_cents"],
                "halt_reason": report["results"]["halt_reason"], "broker_order_count": 0,
                "profitability_verified": False, "execution_authorized": False}
    if op == "paper_tournament":
        report = tournament_paper_strategies(arg["spec"])
        return {"kind": "SYNTHETIC_CHALLENGER_TOURNAMENT",
                "receipt_id": report["receipt_id"],
                "candidate_count": report["candidate_count"],
                "synthetic_holdout_net_pnl_cents": report["chosen_holdout_net_pnl_cents"],
                "strategy_promoted": False, "profitability_verified": False,
                "broker_order_count": 0, "execution_authorized": False}
    if op == "formal":
        result = formal_certificate(compile_automaton(arg["spec"]))
        return {"kind": "FORMAL_WITHIN_TYPED_GRAMMAR", "certificate_id": result["certificate_id"],
                "deterministic": result["deterministic_for_all_finite_features"],
                "execution_authorized": False}
    raise ValueError("unapproved workflow operator")


def execute_research_workflow(plan: Mapping[str, Any]) -> dict:
    """Run explicitly, synchronously and locally. No arbitrary task scripts.

    Estimates are an admission guard, NOT elapsed-time or CPU enforcement.
    A failing step yields FAILED, downstream tasks BLOCKED. A failed workflow
    does not grant any authority, nor does a fully green research workflow.
    """
    if not isinstance(plan, Mapping) or plan.get("status") != "PLANNED_NOT_EXECUTED":
        raise ValueError("only prepared research plans can be run")
    if plan.get("authority") != _AUTHORITY or plan.get("actual_broker_execution_authorized") is not False:
        raise ValueError("research authority escalation")
    seal = plan.get("plan_id")
    if seal != identity({k: v for k, v in plan.items() if k != "plan_id"}):
        raise ValueError("tampered research plan")
    if plan.get("task_count") != len(plan.get("tasks", [])) or not 1 <= plan["task_count"] <= 24:
        raise ValueError("invalid task count")
    # Rebuild the signed plan from its original semantics; no evaluator tricks.
    regenerated = compile_research_workflow({
        "schema_version": plan["schema_version"], "name": plan["name"],
        "compute_budget_seconds": plan["estimated_compute_budget_seconds"],
        "tasks": plan["tasks"],
    })
    if regenerated != plan:
        raise ValueError("invalid workflow execution contract")
    results = {}
    receipts = []
    chain = "0" * 64
    for step in plan["tasks"]:
        tid = step["task_id"]
        if any(results[x] != "PASS" for x in step["depends_on"]):
            status, detail = "BLOCKED", {"reason": "dependency did not pass"}
        else:
            try:
                summary = _execute_operator(step)
                if not isinstance(summary, dict) or len(canonical_bytes(summary)) > 100_000:
                    raise ValueError("operator output exceeds receipt budget")
                status, detail = "PASS", summary
            except (ValueError, TypeError, OSError, OverflowError, KeyError) as exc:
                status, detail = "FAIL", {"reason": type(exc).__name__,
                                          "error_code": "RESEARCH_OPERATOR_REJECTED"}
        node = {"task_id": tid, "operator": step["operator"],
                "depends_on": step["depends_on"], "status": status,
                "detail": detail, "previous_receipt": chain,
                "research_only": True, "execution_authorized": False}
        node["receipt_id"] = identity(node)
        chain = node["receipt_id"]
        results[tid] = status
        receipts.append(node)
    counts = {status: sum(x == status for x in results.values())
              for status in ("PASS", "FAIL", "BLOCKED")}
    report = {"schema_version": "icarus-omnigenesis-agent-run-v1",
              "plan_id": seal, "authority": dict(_AUTHORITY),
              "status": "RESEARCH_ONLY_COMPLETE" if not counts["FAIL"] and not counts["BLOCKED"]
                        else "RESEARCH_ONLY_REVIEW_REQUIRED",
              "counts": counts, "receipts": receipts, "final_receipt": chain,
              "no_network_or_broker_operations": True,
              "scientific_qualification": False,
              "external_approval_required": True}
    report["run_id"] = identity(report)
    return report
