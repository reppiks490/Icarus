"""CA: inert, per-symbol/per-family native XGBoost models.

Rows are chronological dictionaries: x (causal numeric features), y (-1/+1),
ts (Unix seconds), row_index (or index), label_index, and optional label_ts.
Indices refer to the original family bars, including bars omitted from labeled
rows. Equal timestamps are allowed for non-clock bars; indices must increase.
The caller owns feature/label provenance, the separately persisted scaled L2
logit baseline, and all file I/O. No fitting or file access occurs on import.

fit_models returns a JSON-serializable payload. Add dataset_sha256 to that
payload before persisting the manifest. Each fitted slot's booster_json is a
native XGBoost JSON string, reloadable with load_booster or Booster.load_model.
Calibration uses only the first holdout partition; its reported performance is
on the later, purged evaluation partition. Raw holdout metrics remain separate.
"""
from __future__ import annotations

import json
import math
from numbers import Integral

import numpy as np
import xgboost as xgb
from scipy.optimize import minimize
from scipy.special import expit

from icarus_engine.ignore_trade import ignored_symbol


FEATURES = (
    "ret_1", "ret_3", "body", "range", "close_loc", "tide", "run", "fomc",
    "any_macro", "cpi", "nfp", "earnings", "vix_z", "tnx_z", "dxy_z",
)
TRADED = frozenset({"NQ", "ES", "YM", "GC", "SI", "PL", "PA", "BTCF", "BTC"})


def _index(row):
    return row.get("row_index", row.get("index"))


def _check_scope(rows, asset, family):
    assets = {str(r["asset"]).strip().upper() for r in rows if r.get("asset")}
    families = {r["family"] for r in rows if r.get("family")}
    if asset:
        assets.add(asset.strip().upper())
    if family:
        families.add(family)
    if any(ignored_symbol(a) or a not in TRADED for a in assets):
        raise ValueError("only traded execution symbols may be fitted")
    if len(assets) > 1 or len(families) > 1:
        raise ValueError("rows must belong to one symbol and one family")


def _check_rows(rows, horizon):
    if isinstance(horizon, bool) or not isinstance(horizon, Integral) or horizon < 1:
        raise ValueError("horizon must be a positive family-index distance")
    previous_index, previous_ts = -1, -math.inf
    for row in rows:
        index, end = _index(row), row.get("label_index")
        if any(isinstance(v, bool) or not isinstance(v, Integral) for v in (index, end)):
            raise ValueError("each row needs integer row_index and label_index")
        if index <= previous_index or end < index + horizon:
            raise ValueError("indices must increase and labels must respect horizon")
        if "index" in row and "row_index" in row and row["index"] != index:
            raise ValueError("index and row_index disagree")
        ts = float(row["ts"])
        if not math.isfinite(ts) or ts < previous_ts:
            raise ValueError("timestamps must be finite and chronological")
        if row.get("label_ts") is not None:
            label_ts = float(row["label_ts"])
            if not math.isfinite(label_ts) or label_ts < ts:
                raise ValueError("label_ts must be finite and at or after ts")
        if isinstance(row.get("y"), bool) or row.get("y") not in (-1, 1):
            raise ValueError("y must be a family next-bar sign, -1 or +1")
        if not isinstance(row.get("x"), dict):
            raise ValueError("x must be a dictionary of causal features")
        previous_index, previous_ts = index, ts


def _purge(rows, positions, boundary):
    return [i for i in positions if rows[i]["label_index"] < _index(rows[boundary])
            and (rows[i].get("label_ts") is None
                 or float(rows[i]["label_ts"]) <= float(rows[boundary]["ts"]))]


def chronological_split(labeled, *, train_frac=0.6, valid_frac=0.2,
                        calibration_frac=0.5, horizon=1):
    """Return row-position lists for train, valid, holdout, calibration, evaluation.

Purge the earlier side of every boundary using actual label_index/label_ts.
Holdout is the full raw reporting slice; calibration and evaluation partition
it with a purge gap. No sorting, shuffling, or positional horizon guessing.
"""
    _check_rows(labeled, horizon)
    if not (0 < train_frac < 1 and 0 < valid_frac < 1
            and train_frac + valid_frac < 1 and 0 < calibration_frac < 1):
        raise ValueError("invalid chronological split fractions")
    n = len(labeled)
    a, b = int(n * train_frac), int(n * (train_frac + valid_frac))
    c = b + int((n - b) * calibration_frac)
    if not 0 < a < b < c < n:
        raise ValueError("too few rows for chronological partitions")
    parts = {
        "train": _purge(labeled, range(a), a),
        "valid": _purge(labeled, range(a, b), b),
        "holdout": list(range(b, n)),
        "calibration": _purge(labeled, range(b, c), c),
        "evaluation": list(range(c, n)),
    }
    minimum = {"train": 20, "valid": 5, "calibration": 3, "evaluation": 3}
    for name, count in minimum.items():
        if len(parts[name]) < count:
            raise ValueError(f"too few {name} rows after horizon purge (need {count})")
    return parts


def _split_info(rows, positions):
    return {
        "rows": len(positions), "first_position": positions[0],
        "last_position": positions[-1], "first_index": int(_index(rows[positions[0]])),
        "last_index": int(_index(rows[positions[-1]])),
        "max_label_index": int(max(rows[i]["label_index"] for i in positions)),
        "first_ts": float(rows[positions[0]]["ts"]),
        "last_ts": float(rows[positions[-1]]["ts"]),
    }


def _matrix(rows, features):
    matrix = np.array([[np.nan if row["x"].get(k) is None else float(row["x"][k])
                        for k in features] for row in rows], dtype=np.float32)
    if np.isinf(matrix).any():
        raise ValueError("features must be finite or missing")
    return matrix.reshape(len(rows), len(features))


def _feature_names(rows, positions, choices=FEATURES):
    return [k for k in choices if any(r["x"].get(k) is not None
            and math.isfinite(float(r["x"][k])) for r in (rows[i] for i in positions))]


def _dmatrix(matrix, features, labels=None):
    return xgb.DMatrix(matrix, label=labels, feature_names=list(features), nthread=1)


def _train(matrix, labels, train, valid, features, options):
    params = {
        "objective": "binary:logistic", "eval_metric": "logloss", "booster": "gbtree",
        "tree_method": "hist", "device": "cpu", "max_depth": 3, "eta": 0.05,
        "min_child_weight": 1, "lambda": 1.0, "subsample": 1.0,
        "colsample_bytree": 1.0, "base_score": 0.5,
        "seed": options["seed"], "nthread": options["nthread"],
    }
    return xgb.train(
        params, _dmatrix(matrix[train], features, labels[train]),
        num_boost_round=options["num_boost_round"],
        evals=[(_dmatrix(matrix[valid], features, labels[valid]), "valid")],
        callbacks=[xgb.callback.EarlyStopping(
            rounds=options["early_stopping_rounds"], data_name="valid",
            metric_name="logloss", maximize=False, save_best=True)],
        verbose_eval=False,
    )


def _metrics(labels, probability):
    probability = np.asarray(probability, dtype=np.float64)
    clipped = np.clip(probability, 1e-12, 1 - 1e-12)
    return {
        "rows": len(labels),
        "accuracy": float(np.mean((probability >= 0.5) == labels)),
        "logloss": float(-np.mean(labels * np.log(clipped)
                                  + (1 - labels) * np.log1p(-clipped))),
    }


def _slot(booster, features, target):
    booster.set_attr(execution_authorized="false", target=target)
    return {
        "status": "fitted", "kind": "xgboost_classifier", "target": target,
        "features": list(features), "booster_json": booster.save_raw(raw_format="json").decode(),
        "best_iteration": int(booster.best_iteration),
        "num_boosted_rounds": booster.num_boosted_rounds(),
        "execution_authorized": False,
    }


def _deferred(reason):
    return {"status": "deferred", "reason": reason, "execution_authorized": False}


def load_booster(model):
    """Reload a fitted slot, native JSON string, or native JSON dictionary."""
    payload = model.get("booster_json", model) if isinstance(model, dict) else model
    if isinstance(payload, dict):
        payload = json.dumps(payload, allow_nan=False)
    booster = xgb.Booster(params={"nthread": 1})
    booster.load_model(bytearray(payload.encode("utf-8")))
    return booster


def predict_proba(model, rows, *, calibration=None):
    """Predict from a fitted slot. Regime rows must include its causal vol_20.

For absent vol_20, use prepare_regime_rows on chronological history first and
then select prediction rows; restarting the rolling window changes the feature.
"""
    booster = load_booster(model)
    if not rows:
        return []
    data = _dmatrix(_matrix(rows, booster.feature_names), booster.feature_names)
    if calibration is None:
        return booster.predict(data).astype(float).tolist()
    if calibration.get("status") != "fitted":
        raise ValueError("calibration is not fitted")
    margins = booster.predict(data, output_margin=True)
    return expit(calibration["a"] * margins + calibration["b"]).astype(float).tolist()


def _agreement(rows, matrix, labels, parts, features, options, oof_folds):
    # Each fold selects its own best iteration using only an earlier valid slice.
    # The final primary's outer-valid choice must never generate OOF targets.
    train = parts["train"]
    warmup = max(30, len(train) // 3)
    blocks = [block.tolist() for block in np.array_split(np.array(train[warmup:], dtype=int),
                                                       oof_folds) if len(block)]
    blocks.append(parts["valid"])
    targets = np.full(len(rows), np.nan)
    folds = []
    for block in blocks:
        past = _purge(rows, [i for i in train if i < block[0]], block[0])
        cut = int(len(past) * 0.8)
        if not 0 < cut < len(past):
            continue
        inner_train = _purge(rows, past[:cut], past[cut])
        inner_valid = past[cut:]
        if len(inner_train) < 20 or len(inner_valid) < 5:
            continue
        predictor = _train(matrix, labels, inner_train, inner_valid, features, options)
        p = predictor.predict(_dmatrix(matrix[block], features))
        targets[block] = ((p >= 0.5) == labels[block]).astype(float)
        folds.append({"train": _split_info(rows, inner_train),
                      "valid": _split_info(rows, inner_valid),
                      "prediction": _split_info(rows, block)})
    meta_train = [i for i in train if np.isfinite(targets[i])]
    meta_valid = [i for i in parts["valid"] if np.isfinite(targets[i])]
    if len(meta_train) < 20 or len(meta_valid) < 5 or len(np.unique(targets[meta_train])) < 2:
        return _deferred("insufficient causal OOF agreement labels or only one class")
    booster = _train(matrix, targets, meta_train, meta_valid, features, options)
    slot = _slot(booster, features, "probability_primary_sign_is_correct")
    slot.update({"label_source": "causal_expanding_window_oof", "oof_folds": folds,
                 "train_rows": len(meta_train), "valid_rows": len(meta_valid)})
    return slot


def prepare_regime_rows(rows, window=20):
    """Copy rows with causal vol_20, preferring caller's full-bar rolling feature.

Fallback is trailing population std of finite ret_1 on supplied observations,
including the current row. With filtered labels, callers should supply vol_20
computed on the full family bar sequence to preserve the original window.
"""
    if window < 2:
        raise ValueError("volatility window must be at least two")
    out, trailing = [], []
    for row in rows:
        value = row["x"].get("ret_1")
        trailing.append(float(value) if value is not None else np.nan)
        trailing = trailing[-window:]
        x = dict(row["x"])
        if x.get("vol_20") is None:
            finite = [v for v in trailing if math.isfinite(v)]
            x["vol_20"] = float(np.std(finite)) if len(finite) >= 2 else None
        out.append({**row, "x": x})
    return out


def _regime(rows, parts, options):
    prepared = prepare_regime_rows(rows)
    names = _feature_names(prepared, parts["train"], ("vol_20", "rate", "fdi", "RATE", "FDI"))
    if "vol_20" not in names:
        return _deferred("no causal volatility observations")
    matrix = _matrix(prepared, names)
    volatility = matrix[:, names.index("vol_20")]
    train = [i for i in parts["train"] if np.isfinite(volatility[i])]
    valid = [i for i in parts["valid"] if np.isfinite(volatility[i])]
    if len(train) < 20 or len(valid) < 5:
        return _deferred("insufficient observed volatility rows")
    threshold = float(np.median(volatility[train]))
    labels = (volatility > threshold).astype(float)
    if len(np.unique(labels[train])) < 2:
        return _deferred("training volatility has no distinct regimes")
    booster = _train(matrix, labels, train, valid, names, options)
    slot = _slot(booster, names, "current_high_trailing_volatility_state")
    slot.update({"threshold": threshold, "threshold_fit_partition": "train",
                 "state_definition": "vol_20 above training median; descriptive, not a return forecast",
                 "volatility_fallback": "trailing std(ret_1) on supplied observations",
                 "rate_fdi_available": any(k != "vol_20" for k in names)})
    for name in ("holdout", "evaluation"):
        positions = [i for i in parts[name] if np.isfinite(volatility[i])]
        slot[f"raw_{name}"] = (_metrics(labels[positions], booster.predict(
            _dmatrix(matrix[positions], names))) if positions else None)
    return slot


def _calibrate(margins, labels):
    positives = int(labels.sum())
    negatives = len(labels) - positives
    if not positives or not negatives:
        return _deferred("calibration partition needs both label classes")
    mean, scale = float(np.mean(margins)), max(float(np.std(margins)), 1e-8)
    design = np.column_stack(((margins - mean) / scale, np.ones(len(margins))))
    targets = np.where(labels > 0, (positives + 1) / (positives + 2), 1 / (negatives + 2))

    def objective(weights):
        logits = design @ weights
        loss = np.mean(np.logaddexp(0, logits) - targets * logits) + 1e-6 * (weights @ weights)
        gradient = design.T @ (expit(logits) - targets) / len(targets) + 2e-6 * weights
        return float(loss), gradient

    result = minimize(objective, np.zeros(2), method="L-BFGS-B", jac=True)
    if not result.success or not np.isfinite(result.x).all():
        return _deferred("Platt optimization did not converge")
    a = float(result.x[0] / scale)
    return {"status": "fitted", "method": "platt", "a": a,
            "b": float(result.x[1] - a * mean), "fit_partition": "calibration",
            "fit_rows": len(labels), "execution_authorized": False}


def _failure(journal_rows, asset, family, options, split_options):
    if not journal_rows:
        return _deferred("actual labelled journal data unavailable")
    if any(not r.get("journal_id") or r.get("realized_pnl") is None for r in journal_rows):
        return _deferred("journal_id and actual realized_pnl required on every journal row")
    _check_scope(journal_rows, asset, family)
    if len({str(r["journal_id"]) for r in journal_rows}) != len(journal_rows):
        raise ValueError("journal rows must have unique journal_id")
    rows = []
    for row in journal_rows:
        pnl = float(row["realized_pnl"])
        if not math.isfinite(pnl):
            raise ValueError("journal realized_pnl must be finite")
        rows.append({**row, "y": 1 if pnl < 0 else -1})
    try:
        parts = chronological_split(rows, **split_options)
    except ValueError as exc:
        return _deferred(f"journal data cannot be split: {exc}")
    features = _feature_names(rows, parts["train"])
    labels = np.array([r["y"] > 0 for r in rows], dtype=float)
    if not features or len(np.unique(labels[parts["train"]])) < 2:
        return _deferred("journal training needs causal features and both losses and non-losses")
    matrix = _matrix(rows, features)
    booster = _train(matrix, labels, parts["train"], parts["valid"], features, options)
    slot = _slot(booster, features, "probability_realized_journal_loss")
    holdout = parts["holdout"]
    slot.update({"label_source": "realized_pnl < 0 from caller-supplied journal",
                 "splits": {k: _split_info(rows, v) for k, v in parts.items()},
                 "raw_holdout": _metrics(labels[holdout], booster.predict(
                     _dmatrix(matrix[holdout], features)))})
    return slot


def fit_models(labeled, *, asset="", family="", train_frac=0.6, valid_frac=0.2,
               calibration_frac=0.5, horizon=1, num_boost_round=160,
               early_stopping_rounds=12, nthread=1, seed=17, oof_folds=3,
               journal_rows=None):
    """Fit bounded native models without writing artifacts or authorizing execution.

Optional journal rows use the same chronological metadata, entry-time x,
unique journal_id and actual realized_pnl; label_index denotes the exit index.
No journal means a deferred failure slot, never proxy labels from price bars.
Invalid primary input raises ValueError; unavailable auxiliary models defer.
"""
    _check_scope(labeled, asset, family)
    for name, value, maximum in (("num_boost_round", num_boost_round, 4096),
                                 ("early_stopping_rounds", early_stopping_rounds, 4096),
                                 ("nthread", nthread, 32), ("oof_folds", oof_folds, 10)):
        if isinstance(value, bool) or not isinstance(value, Integral) or not 1 <= value <= maximum:
            raise ValueError(f"{name} must be an integer in [1, {maximum}]")
    split_options = dict(train_frac=train_frac, valid_frac=valid_frac,
                         calibration_frac=calibration_frac, horizon=horizon)
    parts = chronological_split(labeled, **split_options)
    features = _feature_names(labeled, parts["train"])
    if not features:
        raise ValueError("no allowed finite features in training rows")
    matrix = _matrix(labeled, features)
    labels = np.array([r["y"] > 0 for r in labeled], dtype=float)
    if len(np.unique(labels[parts["train"]])) < 2:
        raise ValueError("primary training rows need both sign classes")
    options = dict(num_boost_round=int(num_boost_round),
                   early_stopping_rounds=int(early_stopping_rounds),
                   nthread=int(nthread), seed=int(seed))
    booster = _train(matrix, labels, parts["train"], parts["valid"], features, options)
    primary = _slot(booster, features, "next_family_bar_positive_sign")
    probability = booster.predict(_dmatrix(matrix, features))
    for name in ("valid", "holdout", "evaluation"):
        positions = parts[name]
        primary[f"raw_{name}"] = _metrics(labels[positions], probability[positions])
    agree = _agreement(labeled, matrix, labels, parts, features, options, oof_folds)
    if agree["status"] == "fitted":
        for name in ("holdout", "evaluation"):
            positions = parts[name]
            targets = ((probability[positions] >= 0.5) == labels[positions]).astype(float)
            agree[f"raw_{name}"] = _metrics(targets, predict_proba(
                agree, [labeled[i] for i in positions]))
    cal = parts["calibration"]
    margins = booster.predict(_dmatrix(matrix[cal], features), output_margin=True).astype(float)
    calibration = _calibrate(margins, labels[cal])
    if calibration["status"] == "fitted":
        evaluation = parts["evaluation"]
        calibration["evaluation"] = _metrics(labels[evaluation], predict_proba(
            primary, [labeled[i] for i in evaluation], calibration=calibration))
        calibration["evaluation_partition"] = "evaluation"
    return {
        "status": "fitted", "format_version": 1, "model_type": "native_xgboost",
        "asset": asset, "family": family, "features": features,
        "execution_authorized": False, "accuracy_guaranteed": False,
        "xgboost_version": xgb.__version__, "options": {**options, **split_options,
                                                        "oof_folds": int(oof_folds)},
        "splits": {k: _split_info(labeled, v) for k, v in parts.items()},
        "primary": primary, "agree": agree, "regime": _regime(labeled, parts, options),
        "calibration": calibration,
        "failure": _failure(journal_rows, asset, family, options, split_options),
        "holdout_acc": primary["raw_holdout"]["accuracy"],
        "holdout_logloss": primary["raw_holdout"]["logloss"],
        "baseline": {"status": "caller_owned", "kind": "scaled_l2_logit"},
        "limitations": ["Raw holdout is descriptive sign accuracy, not trading edge.",
                        "Only calibrated evaluation is untouched by calibration fitting.",
                        "Agreement is P(primary sign correct), not cross-asset execution equivalence.",
                        "Regime is a descriptive volatility state, not a return forecast."],
    }


def validate_artifact(artifact, *, asset=None, family=None):
    """Fail closed on invalid manifests; load every fitted native tree slot.

This checks model structure and metadata, not the authenticity of source data
or profitability. The caller must check dataset_sha256 against the actual file.
"""
    try:
        if (not isinstance(artifact, dict) or artifact.get("status") != "fitted"
                or artifact.get("execution_authorized") is not False
                or artifact.get("model_type") != "native_xgboost"
                or artifact.get("format_version") != 1):
            return False
        symbol, fam = artifact["asset"], artifact["family"]
        if symbol not in TRADED or not fam:
            return False
        if (asset is not None and symbol != asset) or (family is not None and fam != family):
            return False
        digest = artifact["dataset_sha256"]
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            return False
        if artifact["features"] != artifact["primary"]["features"]:
            return False
        for name in ("primary", "agree", "regime", "failure"):
            slot = artifact[name]
            if slot.get("execution_authorized") is not False:
                return False
            if slot["status"] == "deferred" and name != "primary" and slot.get("reason"):
                continue
            if slot["status"] != "fitted" or slot.get("kind") != "xgboost_classifier":
                return False
            native = slot["booster_json"]
            native = json.loads(native) if isinstance(native, str) else native
            if (not isinstance(native, dict) or "version" not in native
                    or native.get("learner", {}).get("objective", {}).get("name") != "binary:logistic"
                    or not native["learner"].get("gradient_booster", {}).get("model", {}).get("trees")):
                return False
            booster = load_booster(slot)
            if (booster.num_boosted_rounds() < 1 or booster.feature_names != slot["features"]
                    or not slot["features"] or booster.attr("execution_authorized") != "false"
                    or booster.num_boosted_rounds() != slot["num_boosted_rounds"]
                    or int(booster.attr("best_iteration")) != slot["best_iteration"]
                    or slot["best_iteration"] + 1 != slot["num_boosted_rounds"]):
                return False
        calibration = artifact["calibration"]
        if calibration.get("execution_authorized") is not False:
            return False
        if calibration["status"] == "deferred":
            return bool(calibration.get("reason"))
        return (calibration["status"] == "fitted" and calibration["method"] == "platt"
                and calibration["fit_partition"] == "calibration"
                and calibration["evaluation_partition"] == "evaluation"
                and math.isfinite(calibration["a"]) and math.isfinite(calibration["b"])
                and artifact["splits"]["calibration"]["max_label_index"]
                < artifact["splits"]["evaluation"]["first_index"])
    except (KeyError, TypeError, ValueError, AttributeError, xgb.core.XGBoostError):
        return False
