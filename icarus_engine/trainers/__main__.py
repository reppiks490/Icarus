# Grok (xAI) — 2026-09-22. Slots 1-4 CLI: Claude (Opus 5.5) 2026-09-27.
from __future__ import annotations
import argparse, json
from icarus_engine import brand
from .run import train_file, train_rank_file, train_xgb_file, write_report

def main(argv=None):
    p = argparse.ArgumentParser(description=f"{brand.NAME} - fit one trainer slot on one CSV")
    p.add_argument("--path", required=True, help="execution OHLC csv (slot fail: the paper-trade journal)")
    p.add_argument("--chart-type", default="", help="required for logit, xgb and rank")
    p.add_argument("--schema", default="ohlc")
    p.add_argument("--asset", default="")
    p.add_argument("--out", default="")
    p.add_argument("--slot", choices=("logit", "xgb", "rank", "regime", "fail"), default="logit")
    p.add_argument("--ledger", default="", help="holdout ledger (default $ICARUS_LEDGER, else ~/.icarus/holdout_ledger.sqlite3)")
    p.add_argument("--cand", action="append", default=[], metavar="NAME=CSV", help="rank: a candidate series")
    p.add_argument("--cand-chart", default="", help="rank: the candidates' chart type; only a clock chart "
                                                   "(1m, 60m, 1D) gets exact timing, anything else is minute-floored")
    p.add_argument("--root", default=".", help="rank: plant root for history/events")
    args = p.parse_args(argv)
    if args.slot in ("logit", "xgb", "rank") and not args.chart_type:
        p.error(f"--chart-type is required for --slot {args.slot}")
    bad = [c for c in args.cand if "=" not in c or not c.split("=", 1)[0] or not c.split("=", 1)[1]]
    if bad:
        p.error(f"--cand must be NAME=CSV, got {bad}")
    try:
        report = _run(args)
    except (ValueError, OSError) as exc:          # an unknown chart type, an unreadable file: report, never trace
        report = {"status": "blocked", "reason": str(exc), "slot": args.slot, "execution_authorized": False}
    print(json.dumps(report, indent=2))
    return 0 if report.get("status") in ("fitted", "skipped") else 1

def _run(args):
    if args.slot == "xgb":
        report = train_xgb_file(args.path, args.chart_type, args.schema, args.asset,
                                out=args.out or None, ledger=args.ledger or None)
    elif args.slot == "rank":
        cands = dict(c.split("=", 1) for c in args.cand)
        report = train_rank_file(args.path, args.chart_type, args.schema, args.asset, cands,
                                 out=args.out or None, ledger=args.ledger or None, root=args.root,
                                 cand_chart=args.cand_chart or None)
    elif args.slot == "regime":
        from .regime_slot import train as regime
        report = regime(args.path, args.asset)
    elif args.slot == "fail":
        from .fail_slot import train as fail
        report = fail(args.path, args.asset)
    else:
        report = train_file(args.path, args.chart_type, args.schema, args.asset)
        if args.out:
            write_report(report, args.out)
    return report

if __name__ == "__main__":
    raise SystemExit(main())
