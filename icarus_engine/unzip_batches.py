# Grok (xAI) — 2026-09-22. Whole file.
from __future__ import annotations
import argparse, json, os, shutil, subprocess, zipfile
from pathlib import Path
from icarus_engine.spec import BATCHES, CSV_REPO
from icarus_plant.drop import is_candidate_export
from icarus_plant.layout import ensure, plant_root, repo_root

def _run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, check=True)

def fetch_repo(dest: Path):
    dest = Path(dest)
    if (dest / ".git").is_dir():
        _run(["git", "-C", str(dest), "pull", "--ff-only"])
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    _run(["git", "clone", "--depth", "1", CSV_REPO, str(dest)])
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
                if not target.exists():
                    with zf.open(info) as src_f, target.open("wb") as out:
                        shutil.copyfileobj(src_f, out)
                rec["files"] += 1
        rec["ok"] = True
        report.append(rec)
    return {"source": str(src), "execution": str(exec_dir), "candidates": str(cand_dir),
            "batches": report, "ingested_to_historyhub": False}

def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--src", default="")
    p.add_argument("--plant", default="")
    p.add_argument("--fetch", action="store_true")
    args = p.parse_args(argv)
    plant = args.plant or plant_root()
    if args.src:
        src = Path(args.src)
    else:
        sibling = Path(repo_root()).parent / "multi-level-csv"
        src = sibling if sibling.is_dir() else Path(plant) / "history" / "unzipped" / "_repo"
    if args.fetch or not src.is_dir():
        src = fetch_repo(src)
    print(json.dumps(unzip_batches(src, plant), indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
