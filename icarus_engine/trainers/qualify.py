# Claude (Opus 5.5) — 2026-09-27. Fail-closed XGB Slot 1 artifact validator. A file existing is evidence of a
# file, not of a model. VALID_RAW_CHALLENGER needs the execution rows: the validator reloads the booster,
# re-scores the holdout and recomputes both baselines, so a hand-edited or forged report cannot pass. Anything
# missing, unreadable or unverifiable can only keep or lower authority, never promote swap_recommend.
from __future__ import annotations
import hashlib, json, math
from pathlib import Path
from icarus_engine.spec import FEATURE_KEYS, XGB_CLASSIFIER
from . import xgb_slot
from .ledger import holdout_recorded

VALID = "VALID_RAW_CHALLENGER"
QUALIFYING_CLAIMS = ("NEW", "REPLAY")
_TOL = 1e-12

def _no_constants(name):
    raise ValueError(f"non-finite number {name}")

def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)

def _hex64(v):
    return isinstance(v, str) and len(v) == 64 and all(c in "0123456789abcdef" for c in v)

def _malformed(d):
    if not isinstance(d, dict):
        return "artifact is not a JSON object"
    if d.get("schema") != xgb_slot.SCHEMA or d.get("slot") != "xgb" or d.get("status") != "fitted":
        return "not a fitted Slot 1 artifact of this schema"
    for key, kind in (("symbol", str), ("family", str), ("features", list), ("params", dict),
                      ("baseline", dict), ("holdout_claim", dict), ("calibration", dict), ("split", dict),
                      ("model_file", str), ("incremental_value_status", str)):
        if not isinstance(d.get(key), kind):
            return f"{key} missing or not {kind.__name__}"
    if not isinstance(d.get("best_iteration"), int) or isinstance(d["best_iteration"], bool) or d["best_iteration"] < 0:
        return "best_iteration missing or not a non-negative int"
    b = d["baseline"]
    for name, v in (("holdout_logloss", d.get("holdout_logloss")), ("holdout_acc", d.get("holdout_acc")),
                    ("baseline.null_logloss", b.get("null_logloss")),
                    ("baseline.logit_logloss", b.get("logit_logloss"))):
        if not _num(v):
            return f"{name} missing or not finite"
    return ""

def _close(a, b):
    return _num(a) and _num(b) and abs(a - b) <= _TOL

def qualify_xgb(path, symbol, family, dataset_sha256=None, labeled=None):
    """(state, reason). Only VALID_RAW_CHALLENGER may unlock swap_recommend."""
    path = Path(path)
    if not path.is_file():
        return "UNKNOWN", f"no artifact at {path}"
    try:
        d = json.loads(path.read_text(encoding="utf-8"), parse_constant=_no_constants)
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return "BLOCKED_MALFORMED", f"unreadable artifact: {exc}"
    why = _malformed(d)
    if why:
        return "BLOCKED_MALFORMED", why

    if d.get("execution_authorized") is not False:
        return "BLOCKED_EXECUTION_AUTHORITY", "execution_authorized must be exactly false"

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
    if not all(_num(v) for v in bounds) or not (bounds[0] < bounds[1] <= bounds[2] < bounds[3] <= bounds[4]):
        return "BLOCKED_TEMPORAL_INTEGRITY", "split boundaries are not strictly time-ordered"

    claim = d["holdout_claim"]
    if claim.get("status") not in QUALIFYING_CLAIMS:
        return "BLOCKED_HOLDOUT_REUSE", f"holdout claim {claim.get('status')!r}"
    recorded = holdout_recorded(claim.get("ledger", ""), d["symbol"], d["family"], bounds[3], bounds[4],
                                d.get("rows_sha256"), d.get("study_sha256"))
    if recorded is not True:
        return "BLOCKED_HOLDOUT_REUSE", "holdout claim is not confirmed by the ledger"

    for key in ("dataset_sha256", "rows_sha256", "study_sha256", "code_sha256", "model_sha256"):
        if not _hex64(d.get(key)):
            return "BLOCKED_PROVENANCE", f"{key} missing"
    model_name = d["model_file"]
    if Path(model_name).name != model_name or model_name in ("", ".", ".."):
        return "BLOCKED_PROVENANCE", "model_file must sit beside the artifact"
    model = path.parent / model_name
    try:
        digest = hashlib.sha256(model.read_bytes()).hexdigest()
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
        if booster.num_boosted_rounds() != d["best_iteration"] + 1:
            return "BLOCKED_PROVENANCE", "model rounds differ from best_iteration + 1"
        hold = xgb_slot.slices(labeled)[2]
        raw = [float(v) for v in booster.predict(xgb_slot.matrix(xgb, np, hold, labels=False))]
    except Exception as exc:          # any load/predict failure means the file is not the model it claims
        return "BLOCKED_PROVENANCE", f"model cannot be replayed: {type(exc).__name__}"
    got = xgb_slot.evaluate(labeled, raw)
    b = d["baseline"]
    if not (_close(got["holdout_logloss"], d["holdout_logloss"]) and _close(got["holdout_acc"], d["holdout_acc"])
            and _close(got["baseline"]["logit_logloss"], b["logit_logloss"])
            and _close(got["baseline"]["null_logloss"], b["null_logloss"])
            and got["incremental_value_status"] == d["incremental_value_status"]):
        return "BLOCKED_PROVENANCE", "reported holdout numbers differ from the replayed model"
    if got["incremental_value_status"] != "PASS":
        return "BLOCKED_BASELINE_NOT_BEATEN", "raw holdout logloss does not beat logit and null"
    return VALID, "raw challenger replayed from the execution rows; calibrated layer is PENDING_FORWARD"
