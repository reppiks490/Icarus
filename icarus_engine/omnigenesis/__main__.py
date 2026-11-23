"""Command-line research-only interface. No runtime/broker connections.

Examples:
  python -m icarus_engine.omnigenesis prime 100
  python -m icarus_engine.omnigenesis run dataset.json --root /path/to/icarus
  python -m icarus_engine.omnigenesis status --root /path/to/icarus
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from . import AUTHORITY, ResearchLedger, evaluate_dataset, next_prime
from .automata import compile_automaton, replay_automaton
from .simulation import replay_book, synthetic_scenario
from .evolution import compile_proposal, plan_capabilities
from .observatory import render_observatory
from .formal import formal_certificate
from .first_passage import label_first_passage
from .event_bridge import bridge_first_passage
from .data_intake import inspect_market_tape
from .umbra_bridge import audit_umbra_worldlines
from .agent_workflow import compile_research_workflow, execute_research_workflow
from .paper_harness import run_paper_execution, tournament_paper_strategies
from .offline_order_router import replay_offline_order_router


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="icarus-omnigenesis")
    commands = parser.add_subparsers(dest="command", required=True)
    prime = commands.add_parser("prime", help="exact smallest prime > n")
    prime.add_argument("n", type=int)
    run = commands.add_parser("run", help="study complete local historical dataset")
    run.add_argument("dataset", type=Path)
    run.add_argument("--root", required=True, type=Path,
                     help="working directory for derived research ledger")
    status = commands.add_parser("status", help="derived research snapshot")
    status.add_argument("--root", required=True, type=Path)
    machine = commands.add_parser("automaton", help="replay a safe state machine")
    machine.add_argument("spec", type=Path)
    machine.add_argument("observations", type=Path)
    book = commands.add_parser("synthetic-book", help="run a seeded, toy exchange")
    book.add_argument("--seed", type=int, required=True)
    book.add_argument("--root", type=Path, required=True)
    book.add_argument("--steps", type=int, default=100)
    proposal = commands.add_parser("propose", help="compile a bounded capability proposal")
    proposal.add_argument("spec", type=Path)
    plan = commands.add_parser("plan", help="plan proposed projects without executing")
    plan.add_argument("proposals", type=Path)
    plan.add_argument("--seconds", type=int, required=True)
    plan.add_argument("--dollars", type=float, required=True)
    plan.add_argument("--root", type=Path, required=True)
    formal = commands.add_parser("formal", help="compile and formally audit a typed automaton")
    formal.add_argument("spec", type=Path)
    formal.add_argument("--root", type=Path, required=True)
    passage = commands.add_parser("first-passage", help="retrospective OHLC event-time labels")
    passage.add_argument("tape", type=Path)
    passage.add_argument("--up-ticks", required=True, type=int)
    passage.add_argument("--down-ticks", required=True, type=int)
    passage.add_argument("--horizon", required=True, type=int)
    passage.add_argument("--root", type=Path, required=True)
    bridge = commands.add_parser("bridge-event", help="join historical event labels with as-of features")
    bridge.add_argument("report", type=Path)
    bridge.add_argument("features", type=Path)
    bridge.add_argument("--positive-event", choices=["UPPER", "LOWER"], default="UPPER")
    bridge.add_argument("--output", type=Path, required=True,
                        help="new local dataset file; refuses overwrite")
    intake = commands.add_parser("market-intake", help="inspect explicit local normalized JSONL tape; no feed/network")
    intake.add_argument("tape", type=Path)
    intake.add_argument("manifest", type=Path)
    worldline = commands.add_parser("audit-umbra", help="audit a synthetic UMBRA v5 paired-run report")
    worldline.add_argument("report", type=Path)
    worldline.add_argument("--claimed-source-commit", required=True)
    workflow = commands.add_parser("workflow", help="compile explicit bounded local research workflow")
    workflow.add_argument("spec", type=Path)
    workflow.add_argument("--execute", action="store_true", help="explicitly run allowable research-only operators")
    workflow.add_argument("--root", type=Path, help="persist verified derived run summary in existing research ledger")
    workflow.add_argument("--output", type=Path, help="write new receipt JSON; exclusive creation, never overwrites")
    paper = commands.add_parser("paper", help="causal offline synthetic paper-execution harness")
    paper.add_argument("spec", type=Path)
    arena = commands.add_parser("paper-arena", help="select a predeclared strategy on synthetic training only")
    arena.add_argument("spec", type=Path)
    router = commands.add_parser("offline-router", help="replay sandbox-only order message lifecycle; never connect to broker")
    router.add_argument("spec", type=Path)
    constellation_import = commands.add_parser("constellation-import", help="verify completed swarm artifacts and append local read-only evidence")
    constellation_import.add_argument("--plan", required=True, type=Path)
    constellation_import.add_argument("--checkpoint", required=True, type=Path)
    constellation_import.add_argument("--tribunal", required=True, type=Path)
    constellation_import.add_argument("--predecessor", type=Path)
    constellation_import.add_argument("--root", required=True, type=Path)
    dashboard = commands.add_parser("dashboard", help="export offline animated observatory")
    dashboard.add_argument("--root", required=True, type=Path)
    dashboard.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    def read_limited_json(path: Path):
        if path.stat().st_size > 50_000_000:
            parser.error("input exceeds 50 MB research limit")
        return json.loads(path.read_text(encoding="utf-8"))
    if args.command == "prime":
        print(json.dumps({"input": args.n, "next_prime": next_prime(args.n),
                          "authority": AUTHORITY}))
    elif args.command == "run":
        data = read_limited_json(args.dataset)
        report = evaluate_dataset(data)
        ResearchLedger(args.root).append(report)
        print(json.dumps(report, indent=2, sort_keys=True))
    elif args.command == "status":
        print(json.dumps(ResearchLedger(args.root).snapshot(), indent=2,
                         sort_keys=True))
    elif args.command == "automaton":
        program = compile_automaton(read_limited_json(args.spec))
        report = replay_automaton(program, read_limited_json(args.observations))
        print(json.dumps(report, indent=2, sort_keys=True))
    elif args.command == "synthetic-book":
        report = replay_book(synthetic_scenario(args.seed, args.steps))
        ResearchLedger(args.root).append_artifact("synthetic_book", report)
        print(json.dumps(report, indent=2, sort_keys=True))
    elif args.command == "propose":
        print(json.dumps(compile_proposal(read_limited_json(args.spec)),
                         indent=2, sort_keys=True))
    elif args.command == "plan":
        report = plan_capabilities(read_limited_json(args.proposals),
                                   max_compute_seconds=args.seconds,
                                   max_cost_usd=args.dollars)
        ResearchLedger(args.root).append_artifact("capability_plan", report)
        print(json.dumps(report, indent=2, sort_keys=True))
    elif args.command == "formal":
        report = formal_certificate(compile_automaton(read_limited_json(args.spec)))
        ResearchLedger(args.root).append_artifact("formal", report)
        print(json.dumps(report, indent=2, sort_keys=True))
    elif args.command == "first-passage":
        report = label_first_passage(read_limited_json(args.tape),
                                     upper_distance_ticks=args.up_ticks,
                                     lower_distance_ticks=args.down_ticks,
                                     horizon_bars=args.horizon)
        ResearchLedger(args.root).append_artifact("first_passage", report)
        print(json.dumps(report, indent=2, sort_keys=True))
    elif args.command == "bridge-event":
        result = bridge_first_passage(read_limited_json(args.report),
                                     read_limited_json(args.features),
                                     positive_event=args.positive_event)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive create protects existing user artifacts. Nothing is sent
        # to market APIs, and no real strategy is modified.
        with args.output.open("x", encoding="utf-8") as fp:
            json.dump(result["dataset"], fp, indent=2, sort_keys=True)
        print(json.dumps({"output": str(args.output),
                          "audit": result["audit"]}, indent=2, sort_keys=True))
    elif args.command == "market-intake":
        report = inspect_market_tape(args.tape, read_limited_json(args.manifest))
        print(json.dumps(report, indent=2, sort_keys=True))
    elif args.command == "audit-umbra":
        report = audit_umbra_worldlines(read_limited_json(args.report),
                                        claimed_source_commit=args.claimed_source_commit)
        print(json.dumps(report, indent=2, sort_keys=True))
    elif args.command == "workflow":
        plan = compile_research_workflow(read_limited_json(args.spec))
        result = execute_research_workflow(plan) if args.execute else plan
        if args.root is not None:
            if not args.execute:
                parser.error("--root requires --execute for a completed receipt")
            ResearchLedger(args.root).append_artifact("agent_workflow", result)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as fp:
                json.dump(result, fp, indent=2, sort_keys=True)
        print(json.dumps(result, indent=2, sort_keys=True))
    elif args.command == "paper":
        report = run_paper_execution(read_limited_json(args.spec))
        print(json.dumps(report, indent=2, sort_keys=True))
    elif args.command == "paper-arena":
        report = tournament_paper_strategies(read_limited_json(args.spec))
        print(json.dumps(report, indent=2, sort_keys=True))
    elif args.command == "offline-router":
        report = replay_offline_order_router(read_limited_json(args.spec))
        print(json.dumps(report, indent=2, sort_keys=True))
    elif args.command == "constellation-import":
        from .constellation_recovery import _read as read_sealed_json
        artifact_id = ResearchLedger(args.root).append_constellation(
            read_sealed_json(args.plan),
            read_sealed_json(args.checkpoint),
            read_sealed_json(args.tribunal),
            predecessor=read_sealed_json(args.predecessor)
                if args.predecessor else None,
        )
        print(json.dumps({"artifact_id": artifact_id,
                          "status": "LOCAL_REPLAY_ONLY",
                          "research_only": True,
                          "broker_order_count": 0,
                          "github_api_provenance_verified": False},
                         sort_keys=True))
    elif args.command == "dashboard":
        snap = ResearchLedger(args.root).snapshot(limit=100)
        path = render_observatory(snap, args.output)
        print(json.dumps({"exported": str(path), "offline": True,
                          "study_count": snap["study_count"],
                          "authority": AUTHORITY}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
