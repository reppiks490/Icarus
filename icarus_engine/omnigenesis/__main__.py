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
    book.add_argument("--steps", type=int, default=100)
    proposal = commands.add_parser("propose", help="compile a bounded capability proposal")
    proposal.add_argument("spec", type=Path)
    plan = commands.add_parser("plan", help="plan proposed projects without executing")
    plan.add_argument("proposals", type=Path)
    plan.add_argument("--seconds", type=int, required=True)
    plan.add_argument("--dollars", type=float, required=True)
    formal = commands.add_parser("formal", help="compile and formally audit a typed automaton")
    formal.add_argument("spec", type=Path)
    passage = commands.add_parser("first-passage", help="retrospective OHLC event-time labels")
    passage.add_argument("tape", type=Path)
    passage.add_argument("--up-ticks", required=True, type=int)
    passage.add_argument("--down-ticks", required=True, type=int)
    passage.add_argument("--horizon", required=True, type=int)
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
        print(json.dumps(report, indent=2, sort_keys=True))
    elif args.command == "propose":
        print(json.dumps(compile_proposal(read_limited_json(args.spec)),
                         indent=2, sort_keys=True))
    elif args.command == "plan":
        report = plan_capabilities(read_limited_json(args.proposals),
                                   max_compute_seconds=args.seconds,
                                   max_cost_usd=args.dollars)
        print(json.dumps(report, indent=2, sort_keys=True))
    elif args.command == "formal":
        report = formal_certificate(compile_automaton(read_limited_json(args.spec)))
        print(json.dumps(report, indent=2, sort_keys=True))
    elif args.command == "first-passage":
        report = label_first_passage(read_limited_json(args.tape),
                                     upper_distance_ticks=args.up_ticks,
                                     lower_distance_ticks=args.down_ticks,
                                     horizon_bars=args.horizon)
        print(json.dumps(report, indent=2, sort_keys=True))
    elif args.command == "dashboard":
        snap = ResearchLedger(args.root).snapshot(limit=100)
        path = render_observatory(snap, args.output)
        print(json.dumps({"exported": str(path), "offline": True,
                          "study_count": snap["study_count"],
                          "authority": AUTHORITY}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
