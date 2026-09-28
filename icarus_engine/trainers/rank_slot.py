# Claude (Opus 5.5) — 2026-09-27. Slot 2 per SPEC.md: will the next execution move agree with the candidate's
# latest completed move? Inputs are SPEC's sign_agree, tide_agree, macro_agree and overlap, each computed from
# the candidate's EARLIER strict-lead pairs only (a whole-history aggregate would read the future). Logistic fit
# on train, the raw holdout scored once, the holdout claimed in the ledger. execution_authorized is always false.
# The validator is qualify.qualify_rank.
from __future__ import annotations
from pathlib import Path
from icarus_engine.audit.lead import pairs
from . import ledger, logit
from .artifact import canon, code_digest, lock, sha, write_json_atomic
from .dataset import purged_slices
from .metrics import incremental_status, logloss, sign_accuracy, significance

SCHEMA = "icarus.trainer.rank_slot2/1"
RANK_KEYS = ("sign_agree", "tide_agree", "macro_agree", "overlap")
WINDOW = 20                       # earlier pairs per candidate that feed the inputs
FIT = {"method": "newton", "l2": 0.02}
CODE_FILES = ("audit/lead.py", "events/calendar.py", "trainers/dataset.py", "trainers/logit.py",
              "trainers/metrics.py", "trainers/rank_slot.py")

def _rate(hits, n):
    return (hits + 1) / (n + 2)   # Laplace: no history reads as a coin flip, not as certainty

def rank_rows(exec_bars, candidates, events, family="clock_minutes", future="", window=WINDOW, floored=None):
    """One row per scored strict-lead pair, all candidates pooled in time order. y = +1 when the execution move
    agreed with the candidate's move. floored: see audit.lead.pairs (None infers it per candidate)."""
    exec_bars = sorted(exec_bars, key=lambda b: b["ts"])
    rows = []
    for name in sorted(candidates):
        cand = sorted(candidates[name], key=lambda b: b["ts"])
        hist = []
        for p in pairs(exec_bars, cand, events, future, family, floored=floored):
            recent = hist[-window:]
            tide = [q for q in recent if q["tide"]]
            macro = [q for q in recent if q["macro"]]
            x = {"sign_agree": _rate(sum(q["x"] == q["y"] for q in recent), len(recent)),
                 "tide_agree": _rate(sum(q["tide"] == q["y"] for q in tide), len(tide)),
                 "macro_agree": _rate(sum(q["x"] == q["y"] for q in macro), len(macro)),
                 "overlap": len(recent) / window}
            rows.append({"ts": p["ts"], "label_ts": p["label_ts"], "candidate": name,
                         "y": 1 if p["x"] == p["y"] else -1, "x": x})
            hist.append(p)
    rows.sort(key=lambda r: (r["ts"], r["candidate"]))
    return rows

def rows_sha256(rows) -> str:
    return sha(canon([[r["ts"], r["label_ts"], r["candidate"], r["y"], [r["x"][k] for k in RANK_KEYS]]
                      for r in rows]))

def study_sha256() -> str:
    return sha(canon({"schema": SCHEMA, "features": list(RANK_KEYS), "window": WINDOW, "fit": FIT,
                      "code": code_digest(CODE_FILES)}))

def evaluate(rows):
    """Fit on train and score the holdout once. Deterministic, so the validator can replay it."""
    train_rows, valid_rows, hold = purged_slices(rows)
    model = logit.fit_newton(train_rows, keys=RANK_KEYS, l2=FIT["l2"])
    ys = [r["y"] for r in hold]
    ps = [logit.predict_sign(model, r)[1] for r in hold]
    naive = [r["x"]["sign_agree"] for r in hold]
    ll = logloss(ps, ys)
    base_rate = sum(1 for r in train_rows if r["y"] > 0) / len(train_rows)
    null_ll = logloss([base_rate] * len(hold), ys)
    naive_ll = logloss(naive, ys)
    return {"n_train": len(train_rows), "n_valid": len(valid_rows), "n_hold": len(hold),
            "holdout_acc": sign_accuracy(ps, ys), "holdout_logloss": ll,
            "valid_logloss": logloss([logit.predict_sign(model, r)[1] for r in valid_rows],
                                     [r["y"] for r in valid_rows]),
            "baseline": {"null_p": base_rate, "null_logloss": null_ll, "naive_logloss": naive_ll},
            "incremental_value_status": incremental_status(ll, naive_ll, null_ll),
            "significance": significance(ps, naive, base_rate, ys, "naive"),
            "model": {"w": model["w"], "mu": model["mu"], "sd": model["sd"]}}

def train(rows, symbol, family, out_path, ledger_path=None, extra=None):
    symbol = symbol.upper()
    head = {"slot": "rank", "schema": SCHEMA, "symbol": symbol, "family": family,
            "candidates": sorted({r["candidate"] for r in rows}), "features": list(RANK_KEYS),
            "window": WINDOW, **(extra or {})}
    try:
        hold = purged_slices(rows)[2]
    except ValueError as exc:
        return lock({**head, "status": "skipped", "reason": str(exc)})
    study, rsha = study_sha256(), rows_sha256(rows)
    start, end = float(hold[0]["ts"]), float(hold[-1]["ts"])
    ledger_path = Path(ledger_path) if ledger_path else ledger.canonical()
    claim = ledger.claim_holdout(ledger_path, symbol, family, start, end, rsha, study, len(hold), slot="rank")
    claim_rec = {"status": claim, "hold_start_ts": start, "hold_end_ts": end, "ledger": str(ledger_path.resolve())}
    if claim not in ledger.SCORED:
        return lock({**head, "status": "blocked", "reason": f"holdout claim {claim}",
                     "holdout_claim": claim_rec, "study_sha256": study, "rows_sha256": rsha})
    try:
        scored = evaluate(rows)
    except ValueError as exc:
        return lock({**head, "status": "skipped", "reason": str(exc), "holdout_claim": claim_rec})
    report = lock({**head, "status": "fitted", **scored, "holdout_claim": claim_rec,
                   "rows_sha256": rsha, "study_sha256": study})
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(out_path, report)
    return report
