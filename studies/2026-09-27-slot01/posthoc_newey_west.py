# Claude (Opus 5.5) — 2026-09-27. POST-HOC, added after the review of the run. Not part of the pre-registered
# protocol. It replays the 23 saved models on the exact rows the study scored and re-tests XGB vs the logistic
# with Newey-West errors, because neighbouring rows share features and the pre-registered test assumed
# independence. Nothing new is scored: the predictions are the saved models' own, on already-spent holdouts.
#   py -3 studies/2026-09-27-slot01/posthoc_newey_west.py
from __future__ import annotations
import json, sys, tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from icarus_engine.trainers import logit, xgb_slot  # noqa: E402
from icarus_engine.trainers.dataset import attach_labels  # noqa: E402
from icarus_engine.trainers.integrity import inspect_ohlc  # noqa: E402
from icarus_engine.trainers.metrics import paired_test, row_loss  # noqa: E402

HERE = Path(__file__).resolve().parent
ARTIFACTS = Path(r"C:\Users\tripl\icarus-studies\2026-09-27-slot01\artifacts")

def study_rows(path, family):
    """The rows the run scored. The DATA gate now drops an export's last bar; the run kept it, so a later dummy
    row is appended for the gate to drop instead."""
    lines = Path(path).read_text(encoding="utf-8-sig").splitlines()
    head, last = lines[0].split(","), lines[-1].split(",")
    dummy = [str(float(last[0]) + 1)] + ["1"] * (len(head) - 1)
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as fh:
        fh.write("\n".join(lines + [",".join(dummy)]) + "\n")
    bars, _ = inspect_ohlc(fh.name)
    Path(fh.name).unlink()
    return attach_labels(bars, family)

def bh(pvals, q):
    order = sorted(range(len(pvals)), key=lambda i: pvals[i])
    k = max([r for r, i in enumerate(order, 1) if pvals[i] <= r / len(pvals) * q], default=0)
    return {order[j] for j in range(k)}

def main():
    import numpy as np
    import xgboost as xgb
    res = json.loads((HERE / "results.json").read_text(encoding="utf-8"))
    out = []
    for s in res["studies"]:
        art = json.loads((ARTIFACTS / f"{s['symbol']}_{s['family']}_xgb.json").read_text(encoding="utf-8"))
        labeled = study_rows(s["path"], s["family"])
        train_rows, _, hold = xgb_slot.slices(labeled)
        booster = xgb.Booster()
        booster.load_model(str(ARTIFACTS / art["model_file"]))
        raw = [float(v) for v in booster.predict(xgb_slot.matrix(xgb, np, hold, labels=False))]
        lm = logit.fit_newton(train_rows)
        d = [row_loss(p, r["y"]) - row_loss(logit.predict_sign(lm, r)[1], r["y"]) for p, r in zip(raw, hold)]
        nw = paired_test(d)
        base_rate = sum(1 for r in train_rows if r["y"] > 0) / len(train_rows)
        nw_null = paired_test([row_loss(p, r["y"]) - row_loss(base_rate, r["y"]) for p, r in zip(raw, hold)])
        replay_ok = abs(nw["mean"] - s["paired"]["mean_logloss_diff_vs_logit"]) < 1e-12
        out.append({"symbol": s["symbol"], "family": s["family"], "replay_matches_run": replay_ok,
                    "p_preregistered": s["paired"]["p_one_sided"], "p_newey_west": nw["p"], "lag": nw["lag"],
                    "p_newey_west_vs_null": nw_null["p"],
                    "gate": s["slot1"]["incremental_value_status"]})
    keep = bh([o["p_newey_west"] for o in out], res["q"])
    for i, o in enumerate(out):
        o["bh_newey_west_q10"] = i in keep
        o["qualifies_newey_west"] = o["bh_newey_west_q10"] and o["gate"] == "PASS"
    (HERE / "posthoc_newey_west.json").write_text(json.dumps(out, indent=2, allow_nan=False))
    for o in out:
        print(f"{o['symbol']:<3} {o['family']:<14} replay={o['replay_matches_run']} p_pre={o['p_preregistered']:.4f} "
              f"p_nw={o['p_newey_west']:.4f} p_nw_null={o['p_newey_west_vs_null']:.4f} gate={o['gate']} "
              f"qualifies_nw={o['qualifies_newey_west']}")

if __name__ == "__main__":
    main()
