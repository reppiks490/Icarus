"""OMNIGENESIS Constellation: offline deterministic research-worker constellation.

Six specialized scientific harness roles, two seeded evidence shards each,
a sealed work plan and a fail-closed receipt tribunal. This is code-driven
worker orchestration through GitHub Actions, NOT freeform LLM agents,
broker processes, empirical alpha research or an autonomous live trader.

No network/API/credential/trading adapters are used by this module.
The tribunal recomputes all cases from the same source revision; that is a
consistency check, not independent scientific proof or tamper-proof signing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Mapping

from .agent_workflow import compile_research_workflow, execute_research_workflow
from .contracts import identity
from .historical_paper import run_historical_paper_replay
from .ledger import ResearchLedger
from .offline_order_router import replay_offline_order_router
from .paper_harness import run_paper_execution
from .umbra_bridge import _hash32, audit_umbra_worldlines

_AUTHORITY = {
    "research_only": True,
    "execution_authorized": False,
    "production_decision_authorized": False,
    "auto_promote": False,
}
_LANES = ("chronos", "execution", "reconciliation", "nemesis",
          "worldline", "memory")
_SHARDS = (0, 1)
_PLAN_SCHEMA = "icarus-omnigenesis-constellation-plan-v1"
_WORKER_SCHEMA = "icarus-omnigenesis-constellation-worker-v1"
_TRIBUNAL_SCHEMA = "icarus-omnigenesis-constellation-tribunal-v1"


def _integer(value: Any, name: str, lo: int, hi: int) -> int:
    if type(value) is not int or not lo <= value <= hi:
        raise ValueError("invalid " + name)
    return value


def _id(payload: dict, key: str) -> dict:
    return {**payload, key: identity(payload)}


def build_plan(seed: int) -> dict:
    """Immutable finite workload plan; 12 executable workers, no arbitrary code."""
    seed = _integer(seed, "constellation seed", 0, (1 << 32) - 1)
    jobs = [{"lane": lane, "shard": shard}
            for lane in _LANES for shard in _SHARDS]
    return _id({
        "schema_version": _PLAN_SCHEMA,
        "seed": seed,
        "authority": dict(_AUTHORITY),
        "jobs": jobs,
        "worker_count": len(jobs),
        "max_retries_per_worker": 0,
        "worker_outputs": "DERIVED_RESEARCH_SUMMARY_ONLY",
        "vendor_feed_used": False,
        "broker_calls_allowed": False,
        "automatic_promotion": False,
        "independent_review_required": True,
        "execution_mode": "GITHUB_REUSABLE_WORKFLOW_OFFLINE",
    }, "plan_id")


def _valid_plan(plan: Mapping[str, Any]) -> dict:
    if not isinstance(plan, dict) or set(plan) != set(build_plan(0)):
        raise ValueError("invalid constellation plan schema")
    expected = build_plan(_integer(plan.get("seed"), "plan seed", 0, (1 << 32) - 1))
    if expected != plan:
        raise ValueError("constellation plan mismatch or authority escalation")
    return expected


def _scenario_seed(seed: int, lane: str, shard: int) -> int:
    token = f"{seed}:{lane}:{shard}".encode("ascii")
    return int.from_bytes(hashlib.sha256(token).digest()[:4], "big")


def _paper_spec(seed: int) -> dict:
    return {
        "schema_version": "icarus-omnigenesis-paper-execution-v1",
        "seed": seed,
        "bars": 192,
        "strategy": {
            "kind": "SMA_CROSS", "fast": 3, "slow": 12,
            "direction": "trend",
        },
        "execution": {
            "contracts": 1, "tick_value_cents": 125,
            "fee_per_contract_cents": 250, "slippage_ticks": 2,
            "latency_bars": 1,
        },
        "risk": {
            "initial_cash_cents": 20_000_000,
            "max_loss_cents": 5_000_000,
            "max_drawdown_cents": 3_000_000,
            "max_order_events": 100,
        },
    }


def _historical(seed: int, shard: int) -> dict:
    origin = datetime(2026, 3, 1, tzinfo=timezone.utc)
    price = 10000 + seed % 100
    rows = []
    # Synthetic fixture masquerades as no provider. The digest is *operator*
    # supplied: it cannot authenticate a vendor, regardless of whether valid.
    for i in range(140):
        opened = origin + timedelta(minutes=i)
        closed = opened + timedelta(seconds=50)
        received = opened + timedelta(seconds=(90 if shard == 0 else 150))
        nxt = max(100, price + (5 if i // 20 % 2 else -4) + (i % 3 - 1))
        rows.append({
            "bar_id": f"simulation-{i:05d}",
            "opened_at": opened.isoformat(),
            "closed_at": closed.isoformat(),
            "received_at": received.isoformat(),
            "open_ticks": price,
            "high_ticks": max(price, nxt) + 3,
            "low_ticks": min(price, nxt) - 3,
            "close_ticks": nxt,
        })
        price = nxt
    paper = _paper_spec(seed)
    spec = {
        "schema_version": "icarus-omnigenesis-historical-paper-v1",
        "evidence": {
            "asset": "NQ", "source_commit": "a" * 40,
            "provider": "CONSTELLATION_SYNTHETIC_FIXTURE",
            "license_reference": "NO_REAL_PROVIDER",
            "captured_at": (origin + timedelta(minutes=150)).isoformat(),
            "declared_sha256": identity({"bars": rows}),
        },
        "bars": rows,
        "strategy": paper["strategy"], "execution": paper["execution"],
        "risk": paper["risk"],
    }
    out = run_historical_paper_replay(spec)
    if (out["actual_exchange_fills_verified"] is not False
            or out["profitability_verified"] is not False
            or out["modeled_results"]["extra_causality_delay_bars"] < 1):
        raise ValueError("chronos research causality/provenance failed")
    return {
        "evidence_kind": "CAUSAL_RECEIPT_CLOCK_AUDIT",
        "source_receipt": out["receipt_id"],
        "bar_count": out["bar_count"],
        "extra_causality_delay_bars": out["modeled_results"]["extra_causality_delay_bars"],
        "hypothetical_fills_only": True,
    }


def _execution(seed: int) -> dict:
    out = run_paper_execution(_paper_spec(seed))
    if (out["profitability_verified"] is not False
            or out["broker_order_count"] != 0
            or out["results"]["final_position_contracts"] != 0
            or out["results"]["minimum_marked_equity_cents"]
                > out["results"]["start_cash_cents"]):
        raise ValueError("execution sandbox authority/accounting violation")
    return {
        "evidence_kind": "SYNTHETIC_EXECUTION_STRESS",
        "source_receipt": out["receipt_id"],
        "fill_count": out["results"]["fill_count"],
        "synthetic_drawdown_cents": out["results"]["max_mark_to_market_drawdown_cents"],
        "synthetic_pnl_cents": out["results"]["net_pnl_cents"],
        "profitability_verified": False,
    }


def _router_case(seed: int) -> dict:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    def event(i: int, action: str, **more: Any) -> dict:
        return {"event_id": f"constellation_evt_{i}",
                "sequence": i,
                "received_at": (start + timedelta(seconds=i)).isoformat(),
                "action": action, **more}
    qty = 2 if seed & 1 else 3
    events = [
        event(1, "SUBMIT", order_id="mock_order_1", side="BUY",
              quantity=qty, limit_ticks=10000),
        event(2, "FILL", order_id="mock_order_1", execution_id="mock_execution_1",
              quantity=1, price_ticks=9999),
        event(3, "ACK", order_id="mock_order_1"),
        event(4, "CANCEL", order_id="mock_order_1"),
        event(5, "CANCEL_ACK", order_id="mock_order_1"),
        event(6, "RECONCILE", position_contracts=1),
    ]
    return {
        "schema_version": "icarus-omnigenesis-offline-order-router-v1",
        "mode": "OFFLINE_SANDBOX",
        "asset": "NQ",
        "max_position_contracts": 5,
        "max_single_order_contracts": 5,
        "max_active_orders": 2,
        "events": events,
    }


def _reconciliation(seed: int) -> dict:
    out = replay_offline_order_router(_router_case(seed))
    if (out["broker_order_count"] != 0 or out["halted"] is not False
            or out["reconciliation_failed"] is not False
            or out["position_contracts"] != 1
            or out["outstanding_order_ids"]):
        raise ValueError("reconciliation fail-closed invariant")
    return {
        "evidence_kind": "SANDBOX_PARTIAL_FILL_RECONCILIATION",
        "source_receipt": out["receipt_id"],
        "duplicate_delivery_count": out["duplicate_delivery_count"],
        "partial_fill_contracts": out["mock_filled_contracts"],
        "reconciliation_consistent_with_mock_input": True,
    }


def _nemesis(seed: int) -> dict:
    """Red-team deliberately-invalid sandbox inputs; all must be rejected."""
    good = _router_case(seed)
    attacks = [
        ("broker_mode", {"mode": "LIVE"}),
        ("injected_credentials", {"broker_api_key": "REJECT_ME"}),
    ]
    failures = []
    for name, change in attacks:
        forged = dict(good)
        forged.update(change)
        try:
            replay_offline_order_router(forged)
        except ValueError:
            failures.append(name)
        else:
            raise ValueError("adversarial mutation unexpectedly accepted: " + name)
    # Changed duplicate event-ID payload must not be deduplicated as valid.
    forged = dict(good)
    events = list(good["events"])
    conflicting = dict(events[0])
    conflicting["quantity"] = 4 if events[0]["quantity"] != 4 else 5
    events.append(conflicting)
    forged["events"] = events
    try:
        replay_offline_order_router(forged)
    except ValueError:
        failures.append("duplicate_event_conflict")
    else:
        raise ValueError("conflicting duplicate event unexpectedly accepted")
    return {
        "evidence_kind": "ADVERSARIAL_SANDBOX_MUTATION",
        "rejected_mutations": sorted(failures),
        "rejected_count": len(failures),
        "false_acceptance_count": 0,
    }


def _worldline(seed: int) -> dict:
    policy = {"trade": 0.55, "climate": 0.45, "medicine": 0.5,
              "innovation": 0.5, "migration": 0.5,
              "conservation": 0.5, "conflict": 0.25}
    trials = 4
    rows = [{"seed": _hash32(seed + (i + 1) * 0x9e3779b1),
             "baseline": 100 + i, "treatment": 98 + i, "diff": 2,
             "foodDiff": 0.5, "emissionsDiff": 0.1}
            for i in range(trials)]
    report = {
        "version": "5.0.0", "seed": seed,
        "trials": trials, "steps": 6,
        "baseline": policy, "treatment": {**policy, "trade": 0.4},
        "paths": rows, "mean": 2, "median": 2,
        "p05": 2, "p95": 2, "sd": 0, "positive": trials,
    }
    out = audit_umbra_worldlines(report, claimed_source_commit="a" * 40)
    if (out["engine_replay_verified"] is not False
            or out["source_commit_verified"] is not False
            or out["real_market_fidelity_verified"] is not False):
        raise ValueError("synthetic worldline evidence escalation")
    return {
        "evidence_kind": "UMBRA_MODEL_INTERNAL_WORLDLINE",
        "source_receipt": out["receipt_id"],
        "replicates": out["trials"],
        "engine_replay_verified": False,
        "source_authenticity_verified": False,
    }


def _memory(seed: int) -> dict:
    spec = {
        "schema_version": "icarus-omnigenesis-agent-workflow-v1",
        "name": "Constellation evidence-memory witness",
        "compute_budget_seconds": 90,
        "tasks": [
            {"task_id": "math", "operator": "prime",
             "depends_on": [], "parameters": {"n": 200 + seed % 31},
             "estimated_compute_seconds": 10},
            {"task_id": "paper", "operator": "paper_execution",
             "depends_on": ["math"], "parameters": {"spec": _paper_spec(seed)},
             "estimated_compute_seconds": 40},
        ],
    }
    plan = compile_research_workflow(spec)
    result = execute_research_workflow(plan)
    if (result["counts"] != {"PASS": 2, "FAIL": 0, "BLOCKED": 0}
            or result["scientific_qualification"] is not False
            or result["external_approval_required"] is not True):
        raise ValueError("scientific ledger workflow promotion detected")
    with TemporaryDirectory(prefix="icarus-constellation-") as temp:
        ledger = ResearchLedger(temp)
        one = ledger.append_artifact("agent_workflow", result)
        two = ledger.append_artifact("agent_workflow", result)
        snapshot = ledger.snapshot()
        if (one != two or snapshot["artifact_count"] != 1
                or snapshot["recent_artifacts"][0]["status"] != "RESEARCH_ONLY"):
            raise ValueError("scientific memory idempotency violated")
    return {
        "evidence_kind": "IMMUTABLE_RESEARCH_LEDGER_REPLAY",
        "source_receipt": result["run_id"],
        "persisted_artifact": one,
        "idempotent_derived_replay": True,
        "execution_authorized": False,
    }


_IMPLEMENTATIONS = {
    "chronos": lambda seed, shard: _historical(seed, shard),
    "execution": lambda seed, shard: _execution(seed),
    "reconciliation": lambda seed, shard: _reconciliation(seed),
    "nemesis": lambda seed, shard: _nemesis(seed),
    "worldline": lambda seed, shard: _worldline(seed),
    "memory": lambda seed, shard: _memory(seed),
}


def run_worker(plan: Mapping[str, Any], lane: str, shard: int) -> dict:
    p = _valid_plan(plan)
    if type(lane) is not str or lane not in _LANES:
        raise ValueError("unapproved constellation worker lane")
    shard = _integer(shard, "constellation shard", 0, 1)
    if {"lane": lane, "shard": shard} not in p["jobs"]:
        raise ValueError("worker not registered in sealed plan")
    case_seed = _scenario_seed(p["seed"], lane, shard)
    summary = _IMPLEMENTATIONS[lane](case_seed, shard)
    if not isinstance(summary, dict) or summary.get("evidence_kind") is None:
        raise ValueError("invalid derived specialist summary")
    return _id({
        "schema_version": _WORKER_SCHEMA,
        "plan_id": p["plan_id"],
        "lane": lane, "shard": shard,
        "scenario_seed": case_seed,
        "authority": dict(_AUTHORITY),
        "status": "PASS_RESEARCH_ONLY",
        "summary": summary,
        "broker_order_count": 0,
        "production_qualified": False,
        "independent_review_required": True,
    }, "receipt_id")


def arbitrate(plan: Mapping[str, Any], evidence: list[Mapping[str, Any]]) -> dict:
    """Fail closed on absent, extra, duplicate or mismatched worker receipts."""
    p = _valid_plan(plan)
    if not isinstance(evidence, list) or len(evidence) != p["worker_count"]:
        raise ValueError("missing, extra or incomplete constellation evidence")
    expected = {(x["lane"], x["shard"]) for x in p["jobs"]}
    found = {}
    for item in evidence:
        if not isinstance(item, dict) or item.get("schema_version") != _WORKER_SCHEMA:
            raise ValueError("invalid constellation worker receipt schema")
        key = (item.get("lane"), item.get("shard"))
        if key not in expected or key in found:
            raise ValueError("unexpected or duplicate constellation worker")
        if (item.get("plan_id") != p["plan_id"] or
                item.get("authority") != _AUTHORITY or
                item.get("broker_order_count") != 0 or
                item.get("production_qualified") is not False):
            raise ValueError("constellation worker authority/provenance escalation")
        if item.get("receipt_id") != identity({k: v for k, v in item.items()
                                             if k != "receipt_id"}):
            raise ValueError("constellation worker receipt hash mismatch")
        found[key] = item
    # Secondary same-revision recomputation is stronger than checking only
    # hashes but NOT an independent implementation or trusted remote witness.
    for job in p["jobs"]:
        key = (job["lane"], job["shard"])
        if found[key] != run_worker(p, *key):
            raise ValueError("constellation worker computation mismatch")
    digest = identity({"plan_id": p["plan_id"], "worker_receipts": [
        found[(j["lane"], j["shard"])]["receipt_id"] for j in p["jobs"]]})
    return _id({
        "schema_version": _TRIBUNAL_SCHEMA,
        "plan_id": p["plan_id"],
        "authority": dict(_AUTHORITY),
        "status": "RESEARCH_CONSISTENCY_PASS_PENDING_INDEPENDENT_REVIEW",
        "expected_workers": p["worker_count"],
        "passed_workers": len(found),
        "lanes": list(_LANES),
        "shards": list(_SHARDS),
        "worker_receipts_digest": digest,
        "same_source_worker_recomputation": True,
        "independent_scientific_validation": False,
        "licensed_market_data_verified": False,
        "real_market_profitability_verified": False,
        "broker_order_count": 0,
        "strategy_promoted": False,
        "release_authorized": False,
    }, "tribunal_id")


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("duplicate constellation JSON key")
        result[name] = value
    return result


def _read(path: Path) -> dict:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 2_000_000:
        raise ValueError("missing, symlinked or oversized constellation input")
    try:
        return json.loads(path.read_text(encoding="utf-8"),
                          object_pairs_hook=_unique_pairs)
    except (OSError, ValueError, UnicodeError) as exc:
        raise ValueError("malformed constellation input") from exc


def _write(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as f:
        json.dump(document, f, indent=2, sort_keys=True)
        f.write("\n")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(description="Offline GitHub research constellation; NO BROKER ACTIONS")
    sub = p.add_subparsers(dest="command", required=True)
    b = sub.add_parser("plan")
    b.add_argument("--seed", type=int, required=True)
    b.add_argument("--output", type=Path, required=True)
    w = sub.add_parser("worker")
    w.add_argument("--plan", type=Path, required=True)
    w.add_argument("--lane", required=True)
    w.add_argument("--shard", type=int, required=True)
    w.add_argument("--output", type=Path, required=True)
    t = sub.add_parser("tribunal")
    t.add_argument("--plan", type=Path, required=True)
    t.add_argument("--worker-dir", type=Path, required=True)
    t.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)
    if args.command == "plan":
        obj = build_plan(args.seed)
    elif args.command == "worker":
        obj = run_worker(_read(args.plan), args.lane, args.shard)
    else:
        plan = _read(args.plan)
        if args.worker_dir.is_symlink() or not args.worker_dir.is_dir():
            raise ValueError("constellation worker directory missing")
        worker_files = sorted(args.worker_dir.glob("worker-*.json"))
        if len(worker_files) != 12 or len(list(args.worker_dir.iterdir())) != 12:
            raise ValueError("constellation worker artifact count mismatch")
        evidence = []
        for file in worker_files:
            entry = _read(file)
            if file.name != f"worker-{entry.get('lane')}-{entry.get('shard')}.json":
                raise ValueError("constellation worker filename/identity mismatch")
            evidence.append(entry)
        obj = arbitrate(plan, evidence)
    _write(args.output, obj)
    print(json.dumps({
        "schema_version": obj["schema_version"],
        "receipt": obj.get("plan_id") or obj.get("receipt_id") or obj.get("tribunal_id"),
        "status": obj.get("status", "PLANNED"),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
