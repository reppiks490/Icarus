# Grok (xAI) — 2026-09-22. Whole file.
"""Clone/pull reppiks490/multi-level-csv and unzip the six newest batches.
Does not ingest into HistoryHub. BATS/LSE/BCBA go to candidates/.
"""
from __future__ import annotations

import argparse, os, shutil, subprocess, zipfile
from pathlib import Path

from icarus_plant.drop import is_candidate_export
from icarus_plant.layout import ensure, plant_root, repo_root

REPO = "https://github.com/reppiks490/multi-level-csv.git"
BATCHES = (
    "Csv first 60.zip",
    "First 60 half.zip",
    "Csv 2nd 60.zip",
    "2nd 60 half.zip",
    "Csv last 57.zip",
    "Last 57 half.zip",
)

def _run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, check=True)

def fetch_repo(dest: Path):
    dest = Path(dest)
    if (dest / ".git").is_dir():
        _run(["git", "-C", str(dest), "pull", "--ff-only"])
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    _run(["git", "clone", "--depth", "1", REPO, str(dest)])
    return dest

def _classify(name: str) -> str:
    if is_candidate_export(name):
        return "candidates"
    upper = name.upper()
    if any(tag in upper for tag in ("CME_", "CBOT_", "COMEX_", "NYMEX_", "COINBASE", "BITSTAMP")):
        return "execution"
    return "candidates"

def unzip_batches(src: Path, plant=None):
    paths = ensure(plant)
    root = Path(paths["history/unzipped"])
    exec_dir = root / "execution"
    cand_dir = root / "candidates"
    exec_dir.mkdir(parents=True, exist_ok=True)
    cand_dir.mkdir(parents=True, exist_ok=True)
    report = []
    for name in BATCHES:
        zpath = src / name
        rec = {"zip": name, "ok": False, "files": 0, "missing": not zpath.is_file()}
        if rec["missing"]:
            report.append(rec)
            continue
        with zipfile.ZipFile(zpath) as zf:
            for info in zf.infolist():
                if info.is_dir() or not info.filename.lower().endswith(".csv"):
                    continue
                base = os.path.basename(info.filename)
                if not base or base.startswith("."):
                    continue
                dest_dir = cand_dir if _classify(base) == "candidates" else exec_dir
                target = dest_dir / base
                if target.exists():
                    rec["files"] += 1
                    continue
                with zf.open(info) as src_f, target.open("wb") as out:
                    shutil.copyfileobj(src_f, out)
                rec["files"] += 1
        rec["ok"] = True
        report.append(rec)
    return {
        "source": str(src),
        "execution": str(exec_dir),
        "candidates": str(cand_dir),
        "batches": report,
        "ingested_to_historyhub": False,
    }

def main(argv=None):
    p = argparse.ArgumentParser(description="Unzip six newest candidate batches")
    p.add_argument("--src", default="", help="existing multi-level-csv checkout")
    p.add_argument("--plant", default="", help="ICARUS_HOME")
    p.add_argument("--fetch", action="store_true", help="git clone/pull the csv repo first")
    args = p.parse_args(argv)
    plant = args.plant or plant_root()
    if args.src:
        src = Path(args.src)
    else:
        sibling = Path(repo_root()).parent / "multi-level-csv"
        src = sibling if sibling.is_dir() else Path(plant) / "history" / "unzipped" / "_repo"
    if args.fetch or not src.is_dir():
        src = fetch_repo(src)
    import json
    print(json.dumps(unzip_batches(src, plant), indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
