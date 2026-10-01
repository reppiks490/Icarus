# Claude (Opus 5.5) — 2026-09-27. Fail-closed validators for Slot 1 (XGB) and Slot 2 (ranker) artifacts. A file
# existing is evidence of a file, not of a model. A VALID state needs the rows: the validator replays the holdout
# (Slot 1 reloads the booster, Slot 2 refits the logistic), recomputes every baseline and the significance tests,
# and trusts only the canonical ledger, never the ledger an artifact names. Anything missing, unreadable or
# unverifiable can only keep or lower authority, never promote swap_recommend.
from __future__ import annotations
from pathlib import Path
from icarus_engine.spec import FEATURE_KEYS, XGB_CLASSIFIER
from . import ledger, xgb_slot
from .artifact import close, finite, read_json, sha

VALID = "VALID_RAW_CHALLENGER"
VALID_RANKER = "VALID_RANKER"
QUALIFYING_CLAIMS = ("NEW", "REPLAY")

def _hex64(v):
    return isinstance(v, str) and len(v) == 64 and all(c in "0123456789abcdef" for c in v)

def _load(path, schema, slot):
    """(artifact, None) or (None, (state, reason))."""
    path = Path(path)
    if not path.is_file():
        return None, ("UNKNOWN", f"no artifact at {path}")
    try:
        d = read_json(path)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return None, ("BLOCKED_MALFORMED", f"unreadable artifact: {exc}")
    if not isinstance(d, dict) or d.get("schema") != schema or d.get("slot") != slot or d.get("status") != "fitted":
        return None, ("BLOCKED_MALFORMED", f"not a fitted {slot} artifact of this schema")
    for key, kind in (("symbol", str), ("family", str), ("features", list), ("baseline", dict),
                      ("holdout_claim", dict), ("incremental_value_status", str), ("significance", dict)):
        if not isinstance(d.get(key), kind):
            return None, ("BLOCKED_MALFORMED", f"{key} missing or not {kind.__name__}")
    for key in ("holdout_logloss", "holdout_acc"):
        if not finite(d.get(key)):
            return None, ("BLOCKED_MALFORMED", f"{key} missing or not finite")
    claim = d["holdout_claim"]
    if not isinstance(claim.get("ledger"), str) or not all(finite(claim.get(k)) for k in ("hold_start_ts", "hold_end_ts")):
        return None, ("BLOCKED_MALFORMED", "holdout_claim needs a ledger path and finite bounds")
    if d.get("execution_authorized") is not False:
        return None, ("BLOCKED_EXECUTION_AUTHORITY", "execution_authorized must be exactly false")
    return d, None

def _claim_state(d, slot, ledger_path, start, end):
    """None when the canonical ledger confirms exactly this claim; otherwise (state, reason)."""
    claim = d["holdout_claim"]
    try:
        expected = Path(ledger_path).resolve() if ledger_path else ledger.canonical()
    except ValueError as exc:
        return "UNKNOWN", str(exc)
    if claim.get("status") not in QUALIFYING_CLAIMS:
        return "BLOCKED_HOLDOUT_REUSE", f"holdout claim {claim.get('status')!r}"
    if Path(claim["ledger"]).resolve() != expected:
        return "BLOCKED_HOLDOUT_REUSE", f"claim was recorded in {claim['ledger']}, not the canonical ledger {expected}"
    recorded = ledger.holdout_recorded(expected, d["symbol"], d["family"], start, end,
                                       d.get("rows_sha256"), d.get("study_sha256"), slot=slot)
    if recorded is None:
        return "UNKNOWN", f"ledger {expected} cannot be read"
    if recorded is not True:
        return "BLOCKED_HOLDOUT_REUSE", "holdout claim is not in the canonical ledger"
    return None

def _same_significance(got, stored, baseline):
    keys = (f"vs_{baseline}", "vs_null")
    return (got["significant"] == stored.get("significant")
            and all(isinstance(stored.get(k), dict) and close(got[k]["p"], stored[k].get("p")) for k in keys))

def qualify_xgb(path, symbol, family, dataset_sha256=None, labeled=None, ledger_path=None):
    """(state, reason). Only VALID_RAW_CHALLENGER may unlock swap_recommend."""
    d, bad = _load(path, xgb_slot.SCHEMA, "xgb")
    if bad:
        return bad
    path = Path(path)
    for key, kind in (("params", dict), ("split", dict), ("calibration", dict), ("model_file", str)):
        if not isinstance(d.get(key), kind):
            return "BLOCKED_MALFORMED", f"{key} missing or not {kind.__name__}"
    b = d["baseline"]
    if not (finite(b.get("null_logloss")) and finite(b.get("logit_logloss"))):
        return "BLOCKED_MALFORMED", "baseline log losses missing or not finite"
    bi = d.get("best_iteration")
    if not isinstance(bi, int) or isinstance(bi, bool) or bi < 0:
        return "BLOCKED_MALFORMED", "best_iteration missing or not a non-negative int"

    if d["symbol"] != symbol.upper() or d["family"] != family:
        return "BLOCKED_IDENTITY_MISMATCH", f"artifact is {d['symbol']}/{d['family']}, audit wants {symbol.upper()}/{family}"
    if d["features"] != list(FEATURE_KEYS):
        return "BLOCKED_IDENTITY_MISMATCH", "feature order differs from spec.FEATURE_KEYS"
    if d["params"] != XGB_CLASSIFIER:
        return "BLOCKED_IDENTITY_MISMATCH", "params differ from spec.XGB_CLASSIFIER"
    if dataset_sha256 is not None and d.get("dataset_sha256") != dataset_sha256:
        return "BLOCKED_IDENTITY_MISMATCH", "artifact was trained on a different dataset file"

    s = d["split"]
    bounds = [s.get(k) for k in ("train_end_ts", "valid_start_ts", "valid_end_ts", "hold_start_ts", "hold_end_ts")]
    if d.get("holdout_touched_before_final") is not False:
        return "BLOCKED_TEMPORAL_INTEGRITY", "holdout touched before the booster was frozen"
    if not all(finite(v) for v in bounds) or not (bounds[0] < bounds[1] <= bounds[2] < bounds[3] <= bounds[4]):
        return "BLOCKED_TEMPORAL_INTEGRITY", "split boundaries are not strictly time-ordered"

    state = _claim_state(d, "xgb", ledger_path, bounds[3], bounds[4])
    if state:
        return state

    for key in ("dataset_sha256", "rows_sha256", "study_sha256", "code_sha256", "model_sha256"):
        if not _hex64(d.get(key)):
            return "BLOCKED_PROVENANCE", f"{key} missing"
    model_name = d["model_file"]
    if Path(model_name).name != model_name or model_name in ("", ".", ".."):
        return "BLOCKED_PROVENANCE", "model_file must sit beside the artifact"
    model = path.parent / model_name
    try:
        digest = sha(model.read_bytes())
    except OSError:
        return "BLOCKED_PROVENANCE", f"model file {model_name} unreadable"
    if digest != d["model_sha256"]:
        return "BLOCKED_PROVENANCE", "model file does not match model_sha256"
    if d.get("serialization_replay") is not True:
        return "BLOCKED_PROVENANCE", "saved model did not replay the scored predictions"
    cal = d["calibration"]
    if cal.get("method") != "isotonic" or cal.get("status") != "PENDING_FORWARD":
        return "BLOCKED_PROVENANCE", "calibration must be isotonic and PENDING_FORWARD"

    # Replay: the rows must be the rows it was trained on, and the numbers must be what the model produces.
    if labeled is None:
        return "UNKNOWN", "unverifiable without the execution dataset rows"
    if xgb_slot.rows_sha256(labeled) != d["rows_sha256"]:
        return "BLOCKED_IDENTITY_MISMATCH", "artifact was trained on different rows"
    try:
        if xgb_slot.split_bounds(labeled) != {k: s[k] for k in xgb_slot.split_bounds(labeled)}:
            return "BLOCKED_TEMPORAL_INTEGRITY", "split boundaries differ from the rows' 60/20/20 split"
    except (ValueError, KeyError):
        return "BLOCKED_TEMPORAL_INTEGRITY", "rows cannot be split 60/20/20"
    try:
        import numpy as np
        import xgboost as xgb
    except ImportError:
        return "UNKNOWN", "xgboost not installed; the model cannot be replayed"
    if d.get("xgboost_version") != xgb.__version__:
        return "UNKNOWN", (f"trained with xgboost {d.get('xgboost_version')}, validating with {xgb.__version__}: "
                           "exact replay is not possible")
    try:
        booster = xgb.Booster()
        booster.load_model(str(model))
        if list(booster.feature_names or []) != list(FEATURE_KEYS):
            return "BLOCKED_PROVENANCE", "model feature names differ from spec.FEATURE_KEYS"
        if booster.num_boosted_rounds() != bi + 1:
            return "BLOCKED_PROVENANCE", "model rounds differ from best_iteration + 1"
        hold = xgb_slot.slices(labeled)[2]
        raw = [float(v) for v in booster.predict(xgb_slot.matrix(xgb, np, hold, labels=False))]
    except Exception as exc:          # any load/predict failure means the file is not the model it claims
        return "BLOCKED_PROVENANCE", f"model cannot be replayed: {type(exc).__name__}"
    got = xgb_slot.evaluate(labeled, raw)
    if not (close(got["holdout_logloss"], d["holdout_logloss"]) and close(got["holdout_acc"], d["holdout_acc"])
            and close(got["baseline"]["logit_logloss"], b["logit_logloss"])
            and close(got["baseline"]["null_logloss"], b["null_logloss"])
            and got["incremental_value_status"] == d["incremental_value_status"]
            and _same_significance(got["significance"], d["significance"], "logit")):
        return "BLOCKED_PROVENANCE", "reported holdout numbers differ from the replayed model"
    if got["incremental_value_status"] != "PASS":
        return "BLOCKED_BASELINE_NOT_BEATEN", "raw holdout logloss does not beat logit and null"
    if not got["significance"]["significant"]:
        return "BLOCKED_BASELINE_NOT_BEATEN", "the improvement is not significant against both baselines (alpha 0.05)"
    return VALID, "raw challenger replayed from the execution rows; calibrated layer is PENDING_FORWARD"

def qualify_rank(path, symbol, family, rows, ledger_path=None):
    """(state, reason). VALID_RANKER only when the rows replay every reported number."""
    from . import rank_slot   # here, not at the top: rank_slot imports audit.lead, whose package imports this module
    d, bad = _load(path, rank_slot.SCHEMA, "rank")
    if bad:
        return bad
    if d["symbol"] != symbol.upper() or d["family"] != family or d["features"] != list(rank_slot.RANK_KEYS):
        return "BLOCKED_IDENTITY_MISMATCH", "symbol, family or inputs differ"
    if rows is None:
        return "UNKNOWN", "unverifiable without the ranker rows"
    if rank_slot.rows_sha256(rows) != d.get("rows_sha256"):
        return "BLOCKED_IDENTITY_MISMATCH", "artifact was trained on different rows"
    try:
        hold = rank_slot.purged_slices(rows)[2]
    except ValueError as exc:
        return "BLOCKED_PROVENANCE", f"rows cannot be split: {exc}"
    start, end = float(hold[0]["ts"]), float(hold[-1]["ts"])
    claim = d["holdout_claim"]
    if not (close(claim["hold_start_ts"], start) and close(claim["hold_end_ts"], end)):
        return "BLOCKED_TEMPORAL_INTEGRITY", "claimed holdout bounds differ from the rows' holdout"
    state = _claim_state(d, "rank", ledger_path, start, end)
    if state:
        return state
    got = rank_slot.evaluate(rows)
    b, m = d["baseline"], d.get("model")
    same_model = (isinstance(m, dict) and all(isinstance(m.get(k), list) and len(m[k]) == len(got["model"][k])
                                              and all(close(u, v) for u, v in zip(got["model"][k], m[k]))
                                              for k in ("w", "mu", "sd")))
    if not (close(got["holdout_logloss"], d["holdout_logloss"]) and close(got["holdout_acc"], d["holdout_acc"])
            and close(got["baseline"]["null_logloss"], b.get("null_logloss"))
            and close(got["baseline"]["naive_logloss"], b.get("naive_logloss"))
            and got["incremental_value_status"] == d["incremental_value_status"] and same_model
            and _same_significance(got["significance"], d["significance"], "naive")):
        return "BLOCKED_PROVENANCE", "reported numbers differ from the replayed ranker"
    if got["incremental_value_status"] != "PASS":
        return "BLOCKED_BASELINE_NOT_BEATEN", "ranker does not beat the null rate and the naive trailing rate"
    if not got["significance"]["significant"]:
        return "BLOCKED_BASELINE_NOT_BEATEN", "the improvement is not significant against both baselines (alpha 0.05)"
    return VALID_RANKER, "ranker replayed from its rows"
