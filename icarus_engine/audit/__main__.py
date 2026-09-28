# Grok (xAI) — 2026-09-22.
from __future__ import annotations
import argparse, json
from icarus_engine.events.calendar import load_events
from icarus_engine.trainers.dataset import load_ohlc
from icarus_engine.trainers.run import file_hash
from .run import score_pair, write_audit

def main(argv=None):
    p = argparse.ArgumentParser(description="Candidate vs execution audit")
    p.add_argument("--exec", required=True, help="execution OHLCV csv")
    p.add_argument("--cand", required=True, help="candidate OHLCV csv")
    p.add_argument("--future", default="NQ")
    p.add_argument("--family", default="clock_minutes", help="trainer family of the XGB artifact")
    p.add_argument("--cand-family", default="", help="renko/range/tick: the candidate's stamps are minute floors")
    p.add_argument("--ledger", default="", help="holdout ledger (default $ICARUS_LEDGER, else ~/.icarus/...)")
    p.add_argument("--asset", default="")
    p.add_argument("--root", default=".")
    p.add_argument("--out", default="")
    p.add_argument("--require-xgb", action="store_true",
                   help="block unless run/trainers/{FUTURE}_{family}_xgb.json qualifies for --exec")
    p.add_argument("--xgb", default="", help="explicit XGB artifact path")
    args = p.parse_args(argv)
    ev = load_events(args.root)
    try:
        exec_bars, cand_bars = load_ohlc(args.exec), load_ohlc(args.cand)
    except (ValueError, OSError) as exc:  # the DATA gate refused a file, or it cannot be read: never audit it
        print(json.dumps({"status": "blocked", "reason": str(exc), "execution": args.future,
                          "candidate": args.asset, "swap_recommend": False, "execution_authorized": False},
                         indent=2))
        return 2
    report = score_pair(
        exec_bars, cand_bars, ev, args.asset, args.future,
        require_xgb=args.require_xgb, xgb_path=args.xgb or None, family=args.family,
        exec_sha256=file_hash(args.exec), ledger_path=args.ledger or None,
        cand_floored=True if args.cand_family in ("renko", "range", "tick") else None,
    )
    if args.out:
        write_audit(report, args.out)
    print(json.dumps(report, indent=2))
    return 0 if report.get("status") not in ("blocked", "ignored") else 2

if __name__ == "__main__":
    raise SystemExit(main())
