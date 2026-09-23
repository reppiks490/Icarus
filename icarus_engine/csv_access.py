# Grok (xAI) — 2026-09-22. Whole file.
"""Find owner-unzipped CSVs. Does not ingest. Does not scrape."""
from __future__ import annotations

import argparse, json, os, re
from pathlib import Path

from icarus_engine.ignore_trade import ignored_symbol
from icarus_plant.drop import is_candidate_export
from icarus_plant.layout import plant_root, repo_root

_EXEC_HINT = re.compile(
    r"(?:CME_MINI_|CBOT_MINI_|COMEX_|NYMEX_|CME_|CBOT_|COINBASE|BITSTAMP|BINANCE)",
    re.I,
)

def _roots(explicit=None):
    if explicit is not None:
        root = Path(explicit).resolve()
        return [root] if root.is_dir() else []
    out = []
    env = os.environ.get("ICARUS_CSV_ROOT")
    if env:
        out.append(Path(env))
    home = Path(plant_root())
    out.extend([
        home / "history" / "unzipped",
        home / "history" / "unzipped" / "execution",
        home / "history" / "unzipped" / "candidates",
        home / "history" / "drop" / "candidates",
        Path(repo_root()).parent / "multi-level-csv",
    ])
    seen = set()
    uniq = []
    for p in out:
        try:
            r = p.resolve()
        except OSError:
            continue
        if r in seen or not r.is_dir():
            continue
        seen.add(r)
        uniq.append(r)
    return uniq

def _kind_of(path: Path):
    name = path.name
    if is_candidate_export(name):
        return "candidate"
    if _EXEC_HINT.search(name):
        return "execution"
    if ignored_symbol(name):
        return "ignored"
    return "other"

def list_csvs(kind="all", asset="", explicit=None):
    rows = []
    for root in _roots(explicit):
        for p in root.rglob("*.csv"):
            if not p.is_file():
                continue
            if p.name.endswith(".example.csv"):
                continue
            k = _kind_of(p)
            if kind in ("execution", "candidates", "candidate") and k not in (
                "execution" if kind == "execution" else "candidate",
            ):
                if kind == "candidates" and k != "candidate":
                    continue
                if kind == "execution" and k != "execution":
                    continue
            if kind not in ("all", "execution", "candidates", "candidate") and k != kind:
                continue
            if kind == "all" or (
                (kind == "execution" and k == "execution")
                or (kind in ("candidates", "candidate") and k == "candidate")
                or (kind == k)
            ):
                if asset and asset.upper() not in p.name.upper():
                    continue
                rows.append({"path": str(p), "name": p.name, "kind": k, "root": str(root)})
    rows.sort(key=lambda r: r["name"])
    return rows

def main(argv=None):
    p = argparse.ArgumentParser(description="List unzipped owner CSVs")
    p.add_argument("--kind", default="all")
    p.add_argument("--asset", default="")
    p.add_argument("--root", default="")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)
    rows = list_csvs(args.kind, args.asset, args.root or None)
    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        print(f"{len(rows)} files")
        for r in rows[:200]:
            print(f"{r['kind']:10} {r['path']}")
        if len(rows) > 200:
            print(f"... {len(rows) - 200} more")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
