"""CA: synthetic checks for native models and chronological boundaries."""
import copy
import json

import numpy as np
import pytest
import xgboost as native_xgb

from icarus_engine.trainers import xgb


def _rows(n=360, horizon=1):
    rng = np.random.default_rng(42)
    returns = rng.normal(size=n)
    labels = np.where(returns + rng.normal(scale=1.3, size=n) > 0, 1, -1)
    return [{"row_index": i, "label_index": i + horizon,
             "ts": 1_700_000_000 + i, "label_ts": 1_700_000_000 + i + horizon,
             "asset": "NQ", "family": "renko", "y": int(labels[i]),
             "next_abs_return": float(abs(returns[min(i + 1, n - 1)])),
             "x": {"ret_1": float(returns[i]), "ret_3": float(returns[max(0, i - 2):i + 1].sum()),
                   "body": float(returns[i] * 0.8), "fomc": float(i % 10 == 0),
                   "vol_20": float(np.std(returns[max(0, i - 19):i + 1]))}}
            for i in range(n)]


def _fit(rows, **kwargs):
    return xgb.fit_models(rows, asset="NQ", family="renko", num_boost_round=24,
                          early_stopping_rounds=4, **kwargs)


@pytest.fixture(scope="module")
def fitted():
    return _fit(_rows())


def test_native_models_and_raw_metrics(fitted):
    assert fitted["execution_authorized"] is False
    assert fitted["accuracy_guaranteed"] is False
    assert fitted["failure"]["status"] == "deferred"
    assert fitted["baseline"]["status"] == "caller_owned"
    for name in ("primary", "agree", "regime"):
        assert fitted[name]["status"] == "fitted"
        booster = xgb.load_booster(fitted[name])
        assert isinstance(booster, native_xgb.Booster)
        assert booster.num_boosted_rounds() == fitted[name]["best_iteration"] + 1
    rows = _rows()
    parts = xgb.chronological_split(rows)
    p = np.array(xgb.predict_proba(fitted["primary"], [rows[i] for i in parts["holdout"]]))
    y = np.array([rows[i]["y"] > 0 for i in parts["holdout"]])
    assert fitted["holdout_acc"] == np.mean((p >= 0.5) == y)
    assert fitted["holdout_logloss"] == pytest.approx(-np.mean(y * np.log(p) + (1 - y) * np.log1p(-p)))
    assert fitted["regime"]["target"] == "next_family_bar_high_magnitude_state"
    assert fitted["regime"]["rate_fdi_available"] is False


def test_chronology_actual_label_horizon_and_gapped_indices():
    rows = _rows(horizon=4)
    rows = [r for i, r in enumerate(rows) if i % 7 != 2]
    parts = xgb.chronological_split(rows, horizon=4)
    for earlier, later in (("train", "valid"), ("valid", "holdout"), ("calibration", "evaluation")):
        assert max(rows[i]["label_index"] for i in parts[earlier]) < rows[parts[later][0]]["row_index"]
    a = int(len(rows) * 0.6)
    rows[0]["label_index"] = rows[a]["row_index"] + 10
    parts = xgb.chronological_split(rows, horizon=4)
    assert 0 not in parts["train"]


def test_timestamp_purge_and_nonclock_ties():
    rows = _rows()
    for row in rows:
        row["ts"] = 1_700_000_000 + row["row_index"] // 3
        row["label_ts"] = 1_700_000_000 + row["label_index"] // 3
    assert xgb.chronological_split(rows)["train"]
    boundary = int(len(rows) * 0.6)
    rows[0]["label_ts"] = rows[boundary]["ts"] + 1
    assert 0 not in xgb.chronological_split(rows)["train"]


@pytest.mark.parametrize("damage", ["order", "time", "horizon", "missing_index", "label", "mixed_family", "mixed_asset"])
def test_rejects_invalid_training_rows(damage):
    rows = _rows()
    if damage == "order":
        rows[2]["row_index"] = rows[1]["row_index"]
    elif damage == "time":
        rows[2]["ts"] = rows[1]["ts"] - 1
    elif damage == "horizon":
        rows[2]["label_index"] = rows[2]["row_index"]
    elif damage == "missing_index":
        del rows[2]["row_index"]
    elif damage == "label":
        rows[2]["y"] = 0
    elif damage == "mixed_family":
        rows[2]["family"] = "tick"
    else:
        rows[2]["asset"] = "ES"
    with pytest.raises(ValueError):
        _fit(rows)


@pytest.mark.parametrize("asset", ["MBT", "SOL", "ETH", "ETHUSD", "COINBASE:ETHUSD", "AAPL"])
def test_excluded_symbols_rejected_before_fit(asset, monkeypatch):
    def no_fit(*args, **kwargs):
        pytest.fail("excluded symbol reached native fitting")
    monkeypatch.setattr(native_xgb, "train", no_fit)
    with pytest.raises(ValueError, match="traded execution"):
        xgb.fit_models(_rows(), asset=asset)


def test_native_json_persistence_reload_equality(fitted, tmp_path):
    artifact = {**fitted, "dataset_sha256": "a" * 64}
    path = tmp_path / "NQ_renko_xgb.json"
    path.write_text(json.dumps(artifact, allow_nan=False), encoding="utf-8")
    restored = json.loads(path.read_text(encoding="utf-8"))
    assert xgb.validate_artifact(restored, asset="NQ", family="renko")
    rows = _rows()[-20:]
    for name in ("primary", "agree", "regime"):
        assert xgb.predict_proba(fitted[name], rows) == xgb.predict_proba(restored[name], rows)
        native_path = tmp_path / f"{name}.json"
        xgb.load_booster(restored[name]).save_model(native_path)
        native = native_xgb.Booster(model_file=native_path)
        np.testing.assert_array_equal(native.predict(native_xgb.DMatrix(
            xgb._matrix(rows, native.feature_names), feature_names=native.feature_names)),
            xgb.predict_proba(restored[name], rows))
    assert xgb.predict_proba(fitted["primary"], rows, calibration=fitted["calibration"]) == xgb.predict_proba(
        restored["primary"], rows, calibration=restored["calibration"])


def test_future_holdout_does_not_change_learned_models(fitted):
    rows = _rows()
    for row in rows[int(len(rows) * 0.8):]:
        row["y"] *= -1
        row["x"] = {k: v * -50 for k, v in row["x"].items()}
        row["x"]["cpi"] = 1.0
        row["next_abs_return"] *= 100.0
    altered = _fit(rows)
    assert altered["features"] == fitted["features"]
    for name in ("primary", "agree", "regime"):
        assert altered[name]["booster_json"] == fitted[name]["booster_json"]
    assert altered["regime"]["threshold"] == fitted["regime"]["threshold"]


def test_late_evaluation_cannot_change_calibration(fitted):
    rows = _rows()
    parts = xgb.chronological_split(rows)
    for i in parts["evaluation"]:
        rows[i]["y"] *= -1
        rows[i]["x"]["ret_1"] += 500
    altered = _fit(rows)
    assert altered["calibration"]["a"] == fitted["calibration"]["a"]
    assert altered["calibration"]["b"] == fitted["calibration"]["b"]
    assert fitted["calibration"]["fit_rows"] == len(parts["calibration"])
    assert fitted["calibration"]["evaluation"]["rows"] == len(parts["evaluation"])
    assert "holdout_acc" not in fitted["calibration"]
    assert "calibration_accuracy" not in fitted["calibration"]


def test_agreement_oof_chronology_and_early_stop(fitted):
    assert fitted["agree"]["label_source"] == "causal_expanding_window_oof"
    for fold in fitted["agree"]["oof_folds"]:
        assert fold["train"]["max_label_index"] < fold["valid"]["first_index"]
        assert fold["valid"]["max_label_index"] < fold["prediction"]["first_index"]


def test_fold_targets_do_not_depend_on_future_primary_selection(monkeypatch):
    captured = []
    original = xgb._train

    def spy(matrix, labels, train, valid, features, options):
        if np.isnan(labels).any():
            captured.append(labels[train].copy())
        return original(matrix, labels, train, valid, features, options)

    monkeypatch.setattr(xgb, "_train", spy)
    rows = _rows()
    _fit(rows)
    for i in xgb.chronological_split(rows)["valid"]:
        rows[i]["y"] *= -1
        rows[i]["x"]["ret_1"] += 100
    _fit(rows)
    assert len(captured) == 2
    np.testing.assert_array_equal(captured[0], captured[1])


def test_regime_fallback_is_causal_and_preserves_input():
    rows = _rows()
    for row in rows:
        del row["x"]["vol_20"]
    before = copy.deepcopy(rows)
    prepared = xgb.prepare_regime_rows(rows)
    rows[-1]["x"]["ret_1"] = 100000
    changed = xgb.prepare_regime_rows(rows)
    assert prepared[:-1] == changed[:-1]
    assert before[10] == rows[10]
    assert prepared[10]["x"]["vol_20"] == pytest.approx(np.std([r["x"]["ret_1"] for r in before[:11]]))
    assert _fit(before)["regime"]["status"] == "fitted"


def test_single_class_calibration_defers(fitted):
    rows = _rows()
    for i in xgb.chronological_split(rows)["calibration"]:
        rows[i]["y"] = 1
    model = _fit(rows)
    assert model["primary"]["booster_json"] == fitted["primary"]["booster_json"]
    assert model["calibration"]["status"] == "deferred"
    assert "evaluation" not in model["calibration"]


def test_failure_requires_labelled_journal_and_is_reloadable(fitted):
    assert "unavailable" in fitted["failure"]["reason"]
    assert _fit(_rows(), journal_rows=_rows())["failure"]["status"] == "deferred"
    journal = [{**r, "journal_id": f"closed-{i}", "realized_pnl": float(-r["y"])}
               for i, r in enumerate(_rows())]
    model = _fit(_rows(), journal_rows=journal)
    assert model["failure"]["status"] == "fitted"
    assert model["failure"]["target"] == "probability_realized_journal_loss"
    assert len(xgb.predict_proba(model["failure"], journal[-5:])) == 5


@pytest.mark.parametrize("damage", ["empty", "no_trees", "wrong_asset", "wrong_family", "authorized", "bad_hash", "fake_booster", "bad_features", "bad_calibration"])
def test_artifact_validator_rejects_invalid_manifests(fitted, damage):
    artifact = copy.deepcopy({**fitted, "dataset_sha256": "a" * 64})
    if damage == "empty":
        artifact = {}
    elif damage == "no_trees":
        native = json.loads(artifact["primary"]["booster_json"])
        native["learner"]["gradient_booster"]["model"]["trees"] = []
        artifact["primary"]["booster_json"] = native
    elif damage == "wrong_asset":
        artifact["asset"] = "ES"
    elif damage == "wrong_family":
        artifact["family"] = "tick"
    elif damage == "authorized":
        artifact["execution_authorized"] = True
    elif damage == "bad_hash":
        artifact["dataset_sha256"] = ""
    elif damage == "fake_booster":
        artifact["primary"]["booster_json"] = "{}"
    elif damage == "bad_features":
        artifact["primary"]["features"] = ["invented"]
    else:
        artifact["calibration"]["a"] = float("nan")
    assert not xgb.validate_artifact(artifact, asset="NQ", family="renko")
