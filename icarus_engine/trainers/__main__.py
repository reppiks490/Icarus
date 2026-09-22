# Grok (xAI) — 2026-09-22.
from __future__ import annotations
import argparse, json
from .run import train_file, write_report

def main(argv=None):
    p = argparse.ArgumentParser(description="Fit one Icarus trainer family on one CSV")
    p.add_argument("--path", required=True)
    p.add_argument("--chart-type", required=True)
    p.add_argument("--schema", default="ohlc")
    p.add_argument("--asset", default="")
    p.add_argument("--out", default="")
    args = p.parse_args(argv)
    report = train_file(args.path, args.chart_type, args.schema, args.asset)
    if args.out:
        write_report(report, args.out)
    print(json.dumps(report, indent=2))
    return 0 if report.get("status") in ("fitted", "skipped") else 1

if __name__ == "__main__":
    raise SystemExit(main())
