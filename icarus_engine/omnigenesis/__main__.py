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

from . import AUTHORITY, SCHEMA_VERSION, ResearchLedger, evaluate_dataset, next_prime


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
    args = parser.parse_args(argv)
    if args.command == "prime":
        print(json.dumps({"input": args.n, "next_prime": next_prime(args.n),
                          "authority": AUTHORITY}))
    elif args.command == "run":
        if args.dataset.stat().st_size > 50_000_000:
            parser.error("dataset exceeds 50 MB research input limit")
        data = json.loads(args.dataset.read_text(encoding="utf-8"))
        report = evaluate_dataset(data)
        ResearchLedger(args.root).append(report)
        print(json.dumps(report, indent=2, sort_keys=True))
    elif args.command == "status":
        print(json.dumps(ResearchLedger(args.root).snapshot(), indent=2,
                         sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
