# Claude (Opus 5.5) — 2026-09-27. Pre-registered Slot 0/1 study; the protocol is PREREGISTRATION.md.
#   py -3 studies/2026-09-27-slot01/run_study.py --plan    # selection only, trains nothing
#   py -3 studies/2026-09-27-slot01/run_study.py --run     # the single run; refuses if results exist
from __future__ import annotations
import argparse, json, math, sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from icarus_engine.spec import TRADED  # noqa: E402
from icarus_engine.trainers import logit, xgb_slot  # noqa: E402
from icarus_engine.trainers.dataset import attach_labels, load_ohlc  # noqa: E402
from icarus_engine.trainers.families import FAMILIES, family_for  # noqa: E402
from icarus_engine.trainers.qualify import qualify_xgb  # noqa: E402
from icarus_engine.trainers.run import file_hash, train_file, train_xgb_file  # noqa: E402

ARCHIVE = Path(r"C:\Users\tripl\Downloads\Csv\Csv")
CLASSIFICATION = Path(r"C:\Users\tripl\icarus-bridge\research\tv-exports\classification.json")
OUT = Path(r"C:\Users\tripl\icarus-studies\2026-09-27-slot01")
LEDGER = Path(r"C:\Users\tripl\icarus-studies\holdout_ledger.sqlite3")
CANDLES = "candles/bars/hollow/line "
Q = 0.10            # Benjamini-Hochberg false discovery rate across all fitted studies
_EPS = 1e-15

def chart_of(chart_type: str):
    """Trainer chart type for a classified export, or None (Kagi, P&F, Line Break, irregular: no family)."""
    if chart_type.startswith(CANDLES):
        return chart_type[len(CANDLES):]
    if chart_type.startswith("Range"):
        return "range"
    return None

def plan():
    files = json.loads(CLASSIFICATION.read_text(encoding="utf-8"))["files"]
    best, excluded = {}, []
    for f in files:
        sym, chart = f["symbol"].upper(), chart_of(f["chart_type"])
        if sym not in TRADED or chart is None:
            continue
        try:
            fam = family_for(chart)
        except ValueError:
            excluded.append((f["file"], "no family"))
            continue
        if f["rows"] < FAMILIES[fam].min_rows:
            excluded.append((f["file"], f"{f['rows']} rows < {FAMILIES[fam].min_rows} for {fam}"))
            continue
        best.setdefault((sym, fam), []).append((-f["rows"], f["file"], chart))
    chosen = []
    for (sym, fam), options in sorted(best.items()):
        rows, name, chart = min(options)          # most rows; a tie goes to the first file name
        chosen.append({"symbol": sym, "family": fam, "file": name, "chart": chart, "rows": -rows})
    return chosen, excluded

def _loss(p, y):
    p = min(max(p, _EPS), 1 - _EPS)
    return -math.log(p) if y > 0 else -math.log(1 - p)

def _phi(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))

def _wilson(k, n, z=1.96):
    if not n:
        return None
    p = k / n
    den = 1 + z * z / n
    mid = (p + z * z / (2 * n)) / den
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [mid - half, mid + half]

def paired(report, artifact, labeled):
    """Per-row holdout log-loss differences, XGB minus the converged logistic. One-sided p for XGB < logit."""
    import numpy as np
    import xgboost as xgb
    booster = xgb.Booster()
    booster.load_model(str(artifact.parent / report["model_file"]))
    train_rows, _, hold = xgb_slot.slices(labeled)
    raw = [float(v) for v in booster.predict(xgb_slot.matrix(xgb, np, hold, labels=False))]
    lm = logit.fit_newton(train_rows)
    d = [_loss(p, r["y"]) - _loss(logit.predict_sign(lm, r)[1], r["y"]) for p, r in zip(raw, hold)]
    n = len(d)
    mean = sum(d) / n
    sd = math.sqrt(sum((x - mean) ** 2 for x in d) / (n - 1)) if n > 1 else 0.0
    z = mean / (sd / math.sqrt(n)) if sd > 0 else 0.0
    hits = sum(1 for p, r in zip(raw, hold) if (1 if p >= 0.5 else -1) == r["y"])
    return {"n_hold": n, "mean_logloss_diff_vs_logit": mean, "sd": sd, "z": z, "p_one_sided": _phi(z),
            "holdout_acc_wilson95": _wilson(hits, n)}

def bh(pvals, q=Q):
    order = sorted(range(len(pvals)), key=lambda i: pvals[i])
    k = 0
    for rank, i in enumerate(order, start=1):
        if pvals[i] <= rank / len(pvals) * q:
            k = rank
    keep = set(order[:k])
    return [i in keep for i in range(len(pvals))]

def run():
    results_path = OUT / "results.json"
    if results_path.exists():
        raise SystemExit(f"{results_path} exists: this pre-registered study runs once")
    chosen, excluded = plan()
    OUT.mkdir(parents=True, exist_ok=True)
    studies = []
    for s in chosen:
        path = ARCHIVE / f"{s['file']}.csv"
        art = OUT / "artifacts" / f"{s['symbol']}_{s['family']}_xgb.json"
        rec = {**s, "path": str(path), "raw_sha256": file_hash(path)}
        slot0 = train_file(path, s["chart"], "ohlc", s["symbol"])
        rec["slot0"] = {k: slot0.get(k) for k in ("status", "reason", "holdout_acc", "holdout_rows")}
        r = train_xgb_file(path, s["chart"], "ohlc", s["symbol"], out=art, ledger=LEDGER)
        rec["slot1"] = {k: r.get(k) for k in ("status", "reason", "n_train", "n_valid", "n_hold", "best_iteration",
                                             "holdout_acc", "holdout_logloss", "baseline",
                                             "incremental_value_status", "holdout_claim")}
        rec["dataset_manifest"] = r.get("dataset_manifest")
        if r.get("status") == "fitted":
            labeled = attach_labels(load_ohlc(path), s["family"])
            rec["qualification"] = list(qualify_xgb(art, s["symbol"], s["family"], dataset_sha256=rec["raw_sha256"],
                                                    labeled=labeled))
            rec["paired"] = paired(r, art, labeled)
        studies.append(rec)
        print(f"{s['symbol']:>3} {s['family']:<14} {r.get('status'):<8} "
              f"{r.get('incremental_value_status', '-'):<5} {rec.get('qualification', ['-'])[0]}", flush=True)
    fitted = [i for i, s in enumerate(studies) if "paired" in s]
    rejected = bh([studies[i]["paired"]["p_one_sided"] for i in fitted]) if fitted else []
    for i, rej in zip(fitted, rejected):
        studies[i]["bh_significant_q10"] = rej
    out = {"study": "2026-09-27-slot01", "repo_revision": xgb_slot.revision(), "q": Q,
           "n_selected": len(chosen), "n_fitted": len(fitted), "excluded": excluded, "studies": studies,
           "execution_authorized": False}
    results_path.write_text(json.dumps(out, indent=2, allow_nan=False))
    print(f"wrote {results_path}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--plan", action="store_true")
    g.add_argument("--run", action="store_true")
    a = ap.parse_args()
    if a.plan:
        chosen, excluded = plan()
        print(json.dumps({"chosen": chosen, "excluded": excluded}, indent=2))
    else:
        run()
