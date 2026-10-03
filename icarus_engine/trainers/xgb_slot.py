# Claude (Opus 5.5) — 2026-09-27. Slot 1 per SPEC.md: frozen XGB params on FEATURE_KEYS, 60/20/20 time split,
# validation-only early stopping, the raw booster scored once on the terminal holdout, isotonic layer fitted on
# that holdout only after scoring and kept PENDING_FORWARD. execution_authorized is always false.
from __future__ import annotations
import os, platform, subprocess
from pathlib import Path
from icarus_engine.spec import CALIBRATE, FEATURE_KEYS, LABEL, WALK, XGB_CLASSIFIER
from . import ledger, logit
from .artifact import canon, code_digest, lock, sha, write_json_atomic
from .calibrate import isotonic_fit
from .dataset import walk_slices
from .metrics import incremental_status, logloss, sign_accuracy, significance

SCHEMA = "icarus.trainer.xgb_slot1/1"
# Everything that decides what a study computes from its rows. The ledger treats a change here as a new study.
CODE_FILES = ("spec.py", "events/calendar.py", "evidence/timestamps.py", "trainers/dataset.py", "trainers/families.py",
              "trainers/integrity.py", "trainers/logit.py", "trainers/calibrate.py", "trainers/metrics.py",
              "trainers/xgb_slot.py")
EXECUTION = {"nthread": 1}           # single-threaded hist: bit-reproducible model files

def params():
    return dict(XGB_CLASSIFIER)

def code_sha256() -> str:
    return code_digest(CODE_FILES)

def study_sha256() -> str:
    return sha(canon({"schema": SCHEMA, "features": list(FEATURE_KEYS), "params": params(),
                      "execution": EXECUTION, "walk": WALK, "calibrate": CALIBRATE, "label": LABEL,
                      "code": code_sha256()}))

def _vec(row):
    return [float(row["x"].get(k) or 0.0) for k in FEATURE_KEYS]

def rows_sha256(rows) -> str:
    return sha(canon([[r["ts"], r["y"], _vec(r)] for r in rows]))

def matrix(xgb, np, rows, labels=True):
    X = np.array([_vec(r) for r in rows], dtype=float)
    y = [1 if r["y"] > 0 else 0 for r in rows] if labels else None
    return xgb.DMatrix(X, label=y, feature_names=list(FEATURE_KEYS))

def slices(labeled):
    tr, va, ho = walk_slices(len(labeled))
    return labeled[tr[0]:tr[1]], labeled[va[0]:va[1]], labeled[ho[0]:ho[1]]

def split_bounds(labeled):
    train_rows, valid_rows, hold = slices(labeled)
    return {"train_end_ts": float(train_rows[-1]["ts"]), "valid_start_ts": float(valid_rows[0]["ts"]),
            "valid_end_ts": float(valid_rows[-1]["ts"]), "hold_start_ts": float(hold[0]["ts"]),
            "hold_end_ts": float(hold[-1]["ts"])}

def evaluate(labeled, raw_hold):
    """Everything the artifact reports about the holdout, from the rows and the raw booster's holdout scores.
    The validator calls this too, so a report can be replayed rather than trusted."""
    train_rows, _, hold = slices(labeled)
    ys = [r["y"] for r in hold]
    xgb_ll = logloss(raw_hold, ys)
    base_rate = sum(1 for r in train_rows if r["y"] > 0) / len(train_rows)
    null_ll = logloss([base_rate] * len(hold), ys)
    lm = logit.fit_newton(train_rows)      # converged baseline: a weak one would flatter XGB
    logit_ps = [logit.predict_sign(lm, r)[1] for r in hold]
    logit_ll = logloss(logit_ps, ys)
    return {"holdout_acc": sign_accuracy(raw_hold, ys), "holdout_logloss": xgb_ll,
            "baseline": {"null_p": base_rate, "null_logloss": null_ll, "logit_logloss": logit_ll,
                         "logit_acc": logit.accuracy(lm, hold)},
            "incremental_value_status": incremental_status(xgb_ll, logit_ll, null_ll),
            "significance": significance(raw_hold, logit_ps, base_rate, ys, "logit")}

def revision() -> str:
    from ..process_launch import background_kwargs
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parent,
                             capture_output=True, text=True, timeout=10, **background_kwargs())
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    rev = out.stdout.strip()
    return rev if out.returncode == 0 and len(rev) == 40 else "unknown"

def train(labeled, symbol, family, out_path, ledger_path=None, dataset_sha256=None, extra=None):
    symbol = symbol.upper()
    head = {"slot": "xgb", "schema": SCHEMA, "symbol": symbol, "family": family, **(extra or {})}
    try:
        import numpy as np
        import xgboost as xgb
    except ImportError:
        return lock({**head, "status": "blocked", "reason": "xgboost not installed: pip install 'xgboost>=2.0'"})
    try:
        train_rows, valid_rows, hold = slices(labeled)
    except ValueError as exc:
        return lock({**head, "status": "skipped", "reason": str(exc)})
    p = params()
    study, rsha = study_sha256(), rows_sha256(labeled)
    bounds = split_bounds(labeled)
    start, end = bounds["hold_start_ts"], bounds["hold_end_ts"]
    ledger_path = Path(ledger_path) if ledger_path else ledger.canonical()
    claim = ledger.claim_holdout(ledger_path, symbol, family, start, end, rsha, study, len(hold))
    claim_rec = {"status": claim, "hold_start_ts": start, "hold_end_ts": end, "ledger": str(ledger_path.resolve())}
    if claim not in ledger.SCORED:
        return lock({**head, "status": "blocked", "reason": f"holdout claim {claim}",
                     "holdout_claim": claim_rec, "study_sha256": study, "rows_sha256": rsha})

    booster = xgb.train({**{k: v for k, v in p.items() if k not in ("n_estimators", "early_stopping_rounds")},
                         **EXECUTION},
                        matrix(xgb, np, train_rows), num_boost_round=p["n_estimators"],
                        evals=[(matrix(xgb, np, valid_rows), "valid")],
                        early_stopping_rounds=p["early_stopping_rounds"], verbose_eval=False)
    best = int(booster.best_iteration)
    frozen = booster[: best + 1]

    # The booster is frozen. The terminal holdout is scored once, raw.
    dho = matrix(xgb, np, hold, labels=False)
    raw = [float(v) for v in frozen.predict(dho)]
    scored = evaluate(labeled, raw)

    # Calibration consumes the holdout, so it carries no holdout authority and reports no holdout metric.
    iso = isotonic_fit(raw, [r["y"] for r in hold])
    calibration = {"method": CALIBRATE, "fitted_on": "terminal_holdout", "status": "PENDING_FORWARD",
                   "rows": len(hold), "x": iso["x"], "y": iso["y"],
                   "note": "Fitted after raw scoring. No authority until fresh forward data validates it."}

    # Content-addressed model file, then the artifact replaced last: a crash leaves the previous pair intact.
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_model = out_path.with_name(f"{out_path.stem}.model.{os.getpid()}.tmp.json")
    frozen.save_model(str(tmp_model))
    model_sha = sha(tmp_model.read_bytes())
    model_path = out_path.with_name(f"{out_path.stem}.{model_sha[:16]}.model.json")
    os.replace(tmp_model, model_path)
    reloaded = xgb.Booster()
    reloaded.load_model(str(model_path))
    replay = [float(v) for v in reloaded.predict(dho)] == raw

    report = lock({
        **head, "status": "fitted",
        "n_train": len(train_rows), "n_valid": len(valid_rows), "n_hold": len(hold),
        "holdout_acc": scored["holdout_acc"], "holdout_logloss": scored["holdout_logloss"],
        "features": list(FEATURE_KEYS), "params": p, "execution": dict(EXECUTION),
        "best_iteration": best, "best_score": float(booster.best_score),
        "early_stopping": {"eval_set": "valid", "rounds": p["early_stopping_rounds"]},
        "split": {"policy": dict(WALK), **bounds},
        "baseline": scored["baseline"],
        "incremental_value_status": scored["incremental_value_status"],
        "significance": scored["significance"],
        "holdout_claim": claim_rec,
        "holdout_touched_before_final": False,
        "calibration": calibration,
        "model_file": model_path.name, "model_sha256": model_sha,
        "serialization_replay": replay,
        "dataset_sha256": dataset_sha256, "rows_sha256": rsha, "study_sha256": study,
        "code_sha256": code_sha256(), "repo_revision": revision(),
        "xgboost_version": xgb.__version__, "numpy_version": np.__version__,
        "python_version": platform.python_version(),
    })
    write_json_atomic(out_path, report)
    return report
