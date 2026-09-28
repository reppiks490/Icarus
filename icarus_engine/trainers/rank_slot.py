# Claude (Opus 5.5) — 2026-09-27. Slot 2 per SPEC.md: will the next execution move agree with the candidate's
# latest completed move? Inputs are SPEC's sign_agree, tide_agree, macro_agree and overlap, each computed from
# the candidate's EARLIER strict-lead pairs only (a whole-history aggregate would read the future). Logistic fit
# on train, the raw holdout scored once, the holdout claimed in the ledger. execution_authorized is always false.
from __future__ import annotations
import hashlib, json, math, os
from pathlib import Path
from icarus_engine.audit.lead import pairs
from . import ledger, logit
from .dataset import purged_slices
from .xgb_slot import incremental_status, logloss, sign_accuracy

SCHEMA = "icarus.trainer.rank_slot2/1"
RANK_KEYS = ("sign_agree", "tide_agree", "macro_agree", "overlap")
WINDOW = 20                       # earlier pairs per candidate that feed the inputs
FIT = {"method": "newton", "l2": 0.02}
CODE_FILES = ("audit/lead.py", "events/calendar.py", "trainers/dataset.py", "trainers/logit.py",
              "trainers/rank_slot.py")
VALID = "VALID_RANKER"
_TOL = 1e-12

def _rate(hits, n):
    return (hits + 1) / (n + 2)   # Laplace: no history reads as a coin flip, not as certainty

def rank_rows(exec_bars, candidates, events, family="clock_minutes", future="", window=WINDOW):
    """One row per scored strict-lead pair, all candidates pooled in time order. y = +1 when the execution move
    agreed with the candidate's move."""
    exec_bars = sorted(exec_bars, key=lambda b: b["ts"])
    rows = []
    for name in sorted(candidates):
        cand = sorted(candidates[name], key=lambda b: b["ts"])
        hist = []
        for p in pairs(exec_bars, cand, events, future, family):
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

def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def _canon(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()

def rows_sha256(rows) -> str:
    return _sha(_canon([[r["ts"], r["label_ts"], r["candidate"], r["y"], [r["x"][k] for k in RANK_KEYS]]
                        for r in rows]))

def study_sha256() -> str:
    root = Path(__file__).resolve().parents[1]
    code = hashlib.sha256()
    for rel in CODE_FILES:
        code.update(rel.encode() + b"\0" + (root / rel).read_bytes().replace(b"\r\n", b"\n"))
    return _sha(_canon({"schema": SCHEMA, "features": list(RANK_KEYS), "window": WINDOW, "fit": FIT,
                        "code": code.hexdigest()}))

def evaluate(rows):
    """Fit on train and score the holdout once. Deterministic, so the validator can replay it."""
    train_rows, valid_rows, hold = purged_slices(rows)
    model = logit.fit_newton(train_rows, keys=RANK_KEYS, l2=FIT["l2"])
    ys = [r["y"] for r in hold]
    ps = [logit.predict_sign(model, r)[1] for r in hold]
    ll = logloss(ps, ys)
    base_rate = sum(1 for r in train_rows if r["y"] > 0) / len(train_rows)
    null_ll = logloss([base_rate] * len(hold), ys)
    naive_ll = logloss([r["x"]["sign_agree"] for r in hold], ys)
    return {"n_train": len(train_rows), "n_valid": len(valid_rows), "n_hold": len(hold),
            "holdout_acc": sign_accuracy(ps, ys), "holdout_logloss": ll,
            "valid_logloss": logloss([logit.predict_sign(model, r)[1] for r in valid_rows],
                                     [r["y"] for r in valid_rows]),
            "baseline": {"null_p": base_rate, "null_logloss": null_ll, "naive_logloss": naive_ll},
            "incremental_value_status": incremental_status(ll, naive_ll, null_ll),
            "model": {"w": model["w"], "mu": model["mu"], "sd": model["sd"]}}

def _locked(report):
    report["execution_authorized"] = False
    report["accuracy_guaranteed"] = False
    return report

def train(rows, symbol, family, out_path, ledger_path=ledger.LEDGER, extra=None):
    symbol = symbol.upper()
    head = {"slot": "rank", "schema": SCHEMA, "symbol": symbol, "family": family,
            "candidates": sorted({r["candidate"] for r in rows}), "features": list(RANK_KEYS),
            "window": WINDOW, **(extra or {})}
    try:
        hold = purged_slices(rows)[2]
    except ValueError as exc:
        return _locked({**head, "status": "skipped", "reason": str(exc)})
    study, rsha = study_sha256(), rows_sha256(rows)
    start, end = float(hold[0]["ts"]), float(hold[-1]["ts"])
    claim = ledger.claim_holdout(ledger_path, symbol, family, start, end, rsha, study, len(hold), slot="rank")
    claim_rec = {"status": claim, "hold_start_ts": start, "hold_end_ts": end,
                 "ledger": str(Path(ledger_path).resolve())}
    if claim not in ledger.SCORED:
        return _locked({**head, "status": "blocked", "reason": f"holdout claim {claim}",
                        "holdout_claim": claim_rec, "study_sha256": study, "rows_sha256": rsha})
    try:
        scored = evaluate(rows)
    except ValueError as exc:
        return _locked({**head, "status": "skipped", "reason": str(exc), "holdout_claim": claim_rec})
    report = _locked({**head, "status": "fitted", **scored, "holdout_claim": claim_rec,
                      "rows_sha256": rsha, "study_sha256": study})
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_name(f"{out_path.name}.{os.getpid()}.tmp")
    tmp.write_text(json.dumps(report, indent=2, allow_nan=False))
    os.replace(tmp, out_path)
    return report

def _no_constants(name):
    raise ValueError(f"non-finite number {name}")

def _close(a, b):
    return (isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(b, bool)
            and math.isfinite(b) and abs(a - b) <= _TOL)

def qualify_rank(path, symbol, family, rows):
    """(state, reason). VALID_RANKER only when the rows replay every reported number."""
    path = Path(path)
    if not path.is_file():
        return "UNKNOWN", f"no artifact at {path}"
    try:
        d = json.loads(path.read_text(encoding="utf-8"), parse_constant=_no_constants)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return "BLOCKED_MALFORMED", f"unreadable artifact: {exc}"
    if not isinstance(d, dict) or d.get("schema") != SCHEMA or d.get("status") != "fitted" \
            or not isinstance(d.get("baseline"), dict) or not isinstance(d.get("holdout_claim"), dict):
        return "BLOCKED_MALFORMED", "not a fitted Slot 2 artifact of this schema"
    if d.get("execution_authorized") is not False:
        return "BLOCKED_EXECUTION_AUTHORITY", "execution_authorized must be exactly false"
    if d.get("symbol") != symbol.upper() or d.get("family") != family or d.get("features") != list(RANK_KEYS):
        return "BLOCKED_IDENTITY_MISMATCH", "symbol, family or inputs differ"
    if rows is None:
        return "UNKNOWN", "unverifiable without the ranker rows"
    if rows_sha256(rows) != d.get("rows_sha256"):
        return "BLOCKED_IDENTITY_MISMATCH", "artifact was trained on different rows"
    claim = d["holdout_claim"]
    if claim.get("status") not in ("NEW", "REPLAY") or ledger.holdout_recorded(
            claim.get("ledger", ""), d["symbol"], family, claim.get("hold_start_ts"), claim.get("hold_end_ts"),
            d["rows_sha256"], d.get("study_sha256"), slot="rank") is not True:
        return "BLOCKED_HOLDOUT_REUSE", "holdout claim is not a ledger-confirmed first or replayed use"
    try:
        got = evaluate(rows)
    except ValueError as exc:
        return "BLOCKED_PROVENANCE", f"rows cannot be replayed: {exc}"
    b = d["baseline"]
    same = (_close(got["holdout_logloss"], d.get("holdout_logloss"))
            and _close(got["holdout_acc"], d.get("holdout_acc"))
            and _close(got["baseline"]["null_logloss"], b.get("null_logloss"))
            and _close(got["baseline"]["naive_logloss"], b.get("naive_logloss"))
            and got["incremental_value_status"] == d.get("incremental_value_status")
            and got["model"] == d.get("model"))
    if not same:
        return "BLOCKED_PROVENANCE", "reported numbers differ from the replayed ranker"
    if got["incremental_value_status"] != "PASS":
        return "BLOCKED_BASELINE_NOT_BEATEN", "ranker does not beat the null rate and the naive trailing rate"
    return VALID, "ranker replayed from its rows"
