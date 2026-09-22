# Grok (xAI) — 2026-09-22.
from __future__ import annotations
import argparse, json
from pathlib import Path
from icarus_engine.events.calendar import load_events
from icarus_engine.trainers.dataset import load_ohlc
from .run import score_pair, write_audit

def main(argv=None):
    p = argparse.ArgumentParser(description="Candidate vs execution audit")
    p.add_argument("--exec", required=True, help="execution OHLCV csv")
    p.add_argument("--cand", required=True, help="candidate OHLCV csv")
    p.add_argument("--future", default="NQ")
    p.add_argument("--asset", default="")
    p.add_argument("--root", default=".")
    p.add_argument("--out", default="")
    args = p.parse_args(argv)
    ev = load_events(args.root)
    report = score_pair(load_ohlc(args.exec), load_ohlc(args.cand), ev, args.asset, args.future)
    if args.out:
        write_audit(report, args.out)
    print(json.dumps(report, indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
