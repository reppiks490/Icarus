# Claude (Opus 5.5) — 2026-09-27. XGB Slot 1: frozen params, validation-only early stopping, raw terminal
# holdout scored once, provisional isotonic layer, holdout ledger, fail-closed artifact validator.
import hashlib
import json
import math
import random
import shutil
import sys
from pathlib import Path

import pytest

from icarus_engine.audit.run import score_pair
from icarus_engine.events.calendar import seed_events
from icarus_engine.spec import FEATURE_KEYS, XGB_CLASSIFIER

T0 = 1_700_000_000
DATASET = "d" * 64


def _rows(n=900, seed=3, noise=0.1):
    rng = random.Random(seed)
    out = []
    for i in range(n):
        x = {k: rng.uniform(-1.0, 1.0) for k in FEATURE_KEYS}
        x["fomc"] = float(rng.random() < 0.05)
        x["any_macro"] = float(rng.random() < 0.1)
        y = 1 if (x["ret_1"] > 0) == (x["body"] > 0) else -1  # an interaction a linear model cannot fit
        if rng.random() < noise:
            y = -y
        out.append({"ts": T0 + i * 60, "y": y, "family": "clock_minutes", "x": x})
    return out


def _train(tmp, rows=None, ledger=None, sym="NQ", fam="clock_minutes"):
    from icarus_engine.trainers import xgb_slot
    out = Path(tmp) / f"{sym}_{fam}_xgb.json"
    report = xgb_slot.train(rows or _rows(), sym, fam, out_path=out,
                            ledger_path=ledger or Path(tmp) / "ledger.sqlite3", dataset_sha256=DATASET)
    return report, out


def _raw_predict(report, out, rows):
    import numpy as np
    import xgboost as xgb
    booster = xgb.Booster()
    booster.load_model(str(out.parent / report["model_file"]))
    X = np.array([[float(r["x"][k]) for k in FEATURE_KEYS] for r in rows], dtype=float)
    dm = xgb.DMatrix(X, feature_names=list(FEATURE_KEYS))
    return booster.predict(dm, iteration_range=(0, report["best_iteration"] + 1)).tolist()


def _logloss(ps, ys):
    eps = 1e-15
    total = 0.0
    for p, y in zip(ps, ys):
        p = min(max(p, eps), 1 - eps)
        total += -math.log(p) if y > 0 else -math.log(1 - p)
    return total / len(ps)


def _audit_bars(n=250):
    out, px = [], 100.0
    for i in range(n):
        px += 0.1
        out.append({"ts": T0 + i * 60, "open": px, "high": px + 0.2, "low": px - 0.2,
                    "close": px, "tide_long": 1.0, "tide_short": 0.0})
    return out


# ---- isotonic (PAVA) -------------------------------------------------------------------------------

def test_isotonic_pools_adjacent_violators():
    from icarus_engine.trainers.calibrate import isotonic_apply, isotonic_fit
    m = isotonic_fit([0.1, 0.2, 0.3, 0.4], [0, 1, 0, 1])
    assert isotonic_apply(m, 0.1) <= 1e-6
    assert isotonic_apply(m, 0.2) == 0.5 and isotonic_apply(m, 0.3) == 0.5
    assert isotonic_apply(m, 0.4) >= 1 - 1e-6


def test_isotonic_gives_tied_scores_one_value():
    from icarus_engine.trainers.calibrate import isotonic_apply, isotonic_fit
    m = isotonic_fit([0.5, 0.5, 0.9], [0, 1, 1])
    assert isotonic_apply(m, 0.5) == 0.5


def test_isotonic_is_monotone():
    from icarus_engine.trainers.calibrate import isotonic_apply, isotonic_fit
    rng = random.Random(11)
    ps = [rng.random() for _ in range(300)]
    ys = [int(rng.random() < p) for p in ps]
    m = isotonic_fit(ps, ys)
    grid = [i / 200 for i in range(201)]
    vals = [isotonic_apply(m, g) for g in grid]
    assert all(a <= b for a, b in zip(vals, vals[1:]))


# ---- holdout ledger --------------------------------------------------------------------------------

def test_ledger_new_replay_reuse_and_disjoint(tmp_path):
    from icarus_engine.trainers.ledger import claim_holdout
    db = tmp_path / "l.sqlite3"
    assert claim_holdout(db, "NQ", "clock_minutes", 100.0, 200.0, "r1", "s1", 10) == "NEW"
    assert claim_holdout(db, "NQ", "clock_minutes", 100.0, 200.0, "r1", "s1", 10) == "REPLAY"
    assert claim_holdout(db, "NQ", "clock_minutes", 150.0, 250.0, "r2", "s2", 10) == "BLOCKED_HOLDOUT_REUSE"
    assert claim_holdout(db, "NQ", "clock_minutes", 150.0, 250.0, "r2", "s1", 10) == "OVERLAP_SAME_STUDY"
    assert claim_holdout(db, "NQ", "clock_minutes", 251.0, 300.0, "r3", "s2", 10) == "NEW"
    assert claim_holdout(db, "ES", "clock_minutes", 100.0, 200.0, "r1", "s2", 10) == "NEW"


def test_unreadable_ledger_fails_closed(tmp_path):
    from icarus_engine.trainers.ledger import claim_holdout
    db = tmp_path / "l.sqlite3"
    db.write_bytes(b"not a sqlite database " * 50)
    assert claim_holdout(db, "NQ", "clock_minutes", 1.0, 2.0, "r", "s", 1) == "LEDGER_UNAVAILABLE"


# ---- trainer ---------------------------------------------------------------------------------------

def test_missing_xgboost_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "xgboost", None)
    r, out = _train(tmp_path)
    assert r["status"] == "blocked" and r["execution_authorized"] is False
    assert "holdout_logloss" not in r and not out.exists()


def test_fitted_artifact_binds_identity_and_stays_locked(tmp_path):
    r, out = _train(tmp_path)
    assert json.loads(out.read_text()) == r
    assert r["status"] == "fitted" and r["slot"] == "xgb" and r["symbol"] == "NQ"
    assert r["family"] == "clock_minutes"
    assert (r["n_train"], r["n_valid"], r["n_hold"]) == (540, 180, 180)
    assert r["features"] == list(FEATURE_KEYS) and r["params"] == XGB_CLASSIFIER
    assert r["execution_authorized"] is False and r["accuracy_guaranteed"] is False
    assert r["holdout_touched_before_final"] is False and r["serialization_replay"] is True
    assert r["holdout_claim"]["status"] == "NEW"
    assert r["dataset_sha256"] == DATASET
    assert len(r["study_sha256"]) == 64 and len(r["rows_sha256"]) == 64 and len(r["code_sha256"]) == 64
    model = out.parent / r["model_file"]
    assert hashlib.sha256(model.read_bytes()).hexdigest() == r["model_sha256"]


def test_booster_never_sees_the_terminal_holdout(tmp_path):
    rows = _rows()
    flipped = [dict(r, y=-r["y"]) if i >= 720 else r for i, r in enumerate(rows)]
    a, _ = _train(tmp_path / "a", rows)
    b, _ = _train(tmp_path / "b", flipped)
    assert a["model_sha256"] == b["model_sha256"] and a["best_iteration"] == b["best_iteration"]
    assert a["holdout_logloss"] != b["holdout_logloss"]


def test_early_stopping_is_scored_on_the_validation_slice(tmp_path):
    rows = _rows()
    r, out = _train(tmp_path, rows)
    valid = rows[540:720]
    ps = _raw_predict(r, out, valid)
    assert r["best_score"] == pytest.approx(_logloss(ps, [v["y"] for v in valid]), abs=1e-4)


def test_reported_holdout_metrics_are_the_raw_booster(tmp_path):
    rows = _rows()
    r, out = _train(tmp_path, rows)
    hold = rows[720:]
    ps = _raw_predict(r, out, hold)
    ys = [h["y"] for h in hold]
    assert r["holdout_logloss"] == pytest.approx(_logloss(ps, ys), abs=1e-12)
    assert r["holdout_acc"] == sum((1 if p >= 0.5 else -1) == y for p, y in zip(ps, ys)) / len(ys)
    cal = r["calibration"]
    assert cal["method"] == "isotonic" and cal["fitted_on"] == "terminal_holdout"
    assert cal["status"] == "PENDING_FORWARD" and cal["rows"] == 180
    assert not any("logloss" in k or "acc" in k for k in cal)


def test_incremental_value_is_measured_on_the_same_holdout(tmp_path):
    r, _ = _train(tmp_path)
    b = r["baseline"]
    assert r["holdout_logloss"] < b["logit_logloss"] and r["holdout_logloss"] < b["null_logloss"]
    assert r["incremental_value_status"] == "PASS"


def test_training_is_reproducible(tmp_path):
    a, _ = _train(tmp_path / "a")
    b, _ = _train(tmp_path / "b")
    assert a["model_sha256"] == b["model_sha256"] and a["holdout_logloss"] == b["holdout_logloss"]


def test_rerunning_the_same_study_is_a_replay(tmp_path):
    first, _ = _train(tmp_path)
    again, _ = _train(tmp_path)
    assert first["holdout_claim"]["status"] == "NEW"
    assert again["holdout_claim"]["status"] == "REPLAY" and again["status"] == "fitted"
    assert again["model_sha256"] == first["model_sha256"]


def test_changed_study_on_a_seen_holdout_is_blocked_before_scoring(tmp_path, monkeypatch):
    _train(tmp_path)
    monkeypatch.setitem(XGB_CLASSIFIER, "max_depth", 5)
    r, out = _train(tmp_path / "second", ledger=tmp_path / "ledger.sqlite3")
    assert r["status"] == "blocked" and r["holdout_claim"]["status"] == "BLOCKED_HOLDOUT_REUSE"
    assert r["execution_authorized"] is False
    assert "holdout_logloss" not in r and not out.exists()


def test_unreadable_ledger_blocks_training(tmp_path):
    db = tmp_path / "ledger.sqlite3"
    db.write_bytes(b"garbage " * 100)
    r, out = _train(tmp_path, ledger=db)
    assert r["status"] == "blocked" and r["holdout_claim"]["status"] == "LEDGER_UNAVAILABLE"
    assert not out.exists()


def test_train_xgb_file_binds_the_csv_and_the_cli_writes_it(tmp_path, capsys):
    from icarus_engine.trainers.__main__ import main
    from icarus_engine.trainers.run import file_hash, train_xgb_file
    rows, px = [], 100.0
    for i in range(700):
        step = 1 if (i // 8) % 2 == 0 else -1
        nxt = px + step
        rows.append(f"{T0 + i},{px},{max(px, nxt)},{min(px, nxt)},{nxt}")
        px = nxt
    csv = tmp_path / "s.csv"
    csv.write_text("time,open,high,low,close\n" + "\n".join(rows) + "\n")
    r = train_xgb_file(csv, "renko", "ohlc", "NQ", out=tmp_path / "a" / "NQ_renko_xgb.json",
                       ledger=tmp_path / "l.sqlite3")
    assert r["status"] == "fitted" and r["family"] == "renko" and r["execution_authorized"] is False
    assert r["dataset_sha256"] == file_hash(csv)
    ignored = train_xgb_file(csv, "renko", "ohlc", "ETHUSD", out=tmp_path / "x.json", ledger=tmp_path / "l.sqlite3")
    assert ignored["status"] == "ignored" and ignored["execution_authorized"] is False
    out = tmp_path / "b" / "NQ_renko_xgb.json"
    rc = main(["--path", str(csv), "--chart-type", "renko", "--asset", "NQ", "--slot", "xgb",
               "--out", str(out), "--ledger", str(tmp_path / "l.sqlite3")])
    assert rc == 0 and json.loads(out.read_text())["holdout_claim"]["status"] == "REPLAY"
    from icarus_engine.audit.__main__ import main as audit_main
    capsys.readouterr()
    audit_main(["--exec", str(csv), "--cand", str(csv), "--future", "NQ", "--asset", "AAPL",
                "--family", "renko", "--xgb", str(out)])
    audited = json.loads(capsys.readouterr().out)
    assert audited["family"] == "renko" and audited["xgb_state"] == "VALID_RAW_CHALLENGER"
    assert audited["swap_recommend"] is True and audited["execution_authorized"] is False


# ---- validator -------------------------------------------------------------------------------------

def _pattern_csv(path, n=900, seed=None):
    rows, px = [], 100.0
    rng = random.Random(seed) if seed is not None else None
    for i in range(n):
        step = rng.choice((1, -1)) if rng else (1 if (i // 8) % 2 == 0 else -1)
        nxt = px + step
        rows.append(f"{T0 + i * 60},{px},{max(px, nxt)},{min(px, nxt)},{nxt}")
        px = nxt
    path.write_text("time,open,high,low,close\n" + "\n".join(rows) + "\n")
    return path


def _fit_csv(tmp, seed=None):
    from icarus_engine.trainers.dataset import attach_labels, load_ohlc
    from icarus_engine.trainers.run import file_hash, train_xgb_file
    csv = _pattern_csv(tmp / "NQ_20m.csv", seed=seed)
    out = tmp / "NQ_clock_minutes_xgb.json"
    r = train_xgb_file(csv, "minutes", "ohlc", "NQ", out=out, ledger=tmp / "ledger.sqlite3")
    bars = load_ohlc(csv)
    return {"report": r, "out": out, "bars": bars, "labeled": attach_labels(bars, "clock_minutes"),
            "sha": file_hash(csv)}


@pytest.fixture(scope="module")
def trained(tmp_path_factory):
    t = _fit_csv(tmp_path_factory.mktemp("xgb"))
    assert t["report"]["status"] == "fitted" and t["report"]["incremental_value_status"] == "PASS"
    return t


def _copy(src, dst_dir, edit=None, raw=None, model=True):
    dst_dir.mkdir(parents=True, exist_ok=True)
    d = json.loads(src.read_text())
    if model:
        shutil.copy(src.parent / d["model_file"], dst_dir / d["model_file"])
    if edit:
        edit(d)
    dst = dst_dir / src.name
    dst.write_text(raw if raw is not None else json.dumps(d))
    return dst


_DEFAULT = object()


def _state(path, t, sym="NQ", fam="clock_minutes", dataset=_DEFAULT, labeled=_DEFAULT):
    from icarus_engine.trainers.qualify import qualify_xgb
    return qualify_xgb(path, sym, fam, dataset_sha256=t["sha"] if dataset is _DEFAULT else dataset,
                       labeled=t["labeled"] if labeled is _DEFAULT else labeled)[0]


def test_incremental_value_needs_both_baselines_beaten():
    from icarus_engine.trainers.xgb_slot import incremental_status
    assert incremental_status(0.5, 0.6, 0.7) == "PASS"
    assert incremental_status(0.5, 0.4, 0.7) == "FAIL"   # logit better
    assert incremental_status(0.5, 0.6, 0.4) == "FAIL"   # null better
    assert incremental_status(0.5, 0.5, 0.7) == "FAIL"   # a tie is not an improvement


def test_qualify_accepts_a_valid_raw_challenger(trained):
    assert _state(trained["out"], trained) == "VALID_RAW_CHALLENGER"
    assert _state(trained["out"], trained, dataset=None) == "VALID_RAW_CHALLENGER"


def test_qualify_will_not_vouch_without_the_dataset(trained):
    assert _state(trained["out"], trained, labeled=None) == "UNKNOWN"


def test_qualify_missing_artifact_is_unknown(trained, tmp_path):
    assert _state(tmp_path / "nope.json", trained) == "UNKNOWN"


@pytest.mark.parametrize("raw", ["", "not json", "{}", "[]"])
def test_qualify_rejects_malformed(trained, tmp_path, raw):
    assert _state(_copy(trained["out"], tmp_path, raw=raw), trained) == "BLOCKED_MALFORMED"


def test_qualify_rejects_non_finite_metrics(trained, tmp_path):
    p = _copy(trained["out"], tmp_path, edit=lambda d: d.update(holdout_logloss=float("nan")))
    assert _state(p, trained) == "BLOCKED_MALFORMED"


@pytest.mark.parametrize("value", [True, 1, "false", None])
def test_qualify_rejects_anything_but_a_false_execution_lock(trained, tmp_path, value):
    p = _copy(trained["out"], tmp_path, edit=lambda d: d.update(execution_authorized=value))
    assert _state(p, trained) == "BLOCKED_EXECUTION_AUTHORITY"


def test_qualify_rejects_identity_mismatches(trained, tmp_path):
    out = trained["out"]
    assert _state(out, trained, sym="ES") == "BLOCKED_IDENTITY_MISMATCH"
    assert _state(out, trained, fam="renko") == "BLOCKED_IDENTITY_MISMATCH"
    assert _state(out, trained, dataset="e" * 64) == "BLOCKED_IDENTITY_MISMATCH"
    other = [dict(r, y=-r["y"]) if i == 5 else r for i, r in enumerate(trained["labeled"])]
    assert _state(out, trained, labeled=other) == "BLOCKED_IDENTITY_MISMATCH"
    rev = _copy(out, tmp_path / "f", edit=lambda d: d.update(features=d["features"][::-1]))
    assert _state(rev, trained) == "BLOCKED_IDENTITY_MISMATCH"
    deeper = _copy(out, tmp_path / "p", edit=lambda d: d["params"].update(max_depth=6))
    assert _state(deeper, trained) == "BLOCKED_IDENTITY_MISMATCH"


def test_qualify_rejects_a_touched_holdout(trained, tmp_path):
    p = _copy(trained["out"], tmp_path, edit=lambda d: d.update(holdout_touched_before_final=True))
    assert _state(p, trained) == "BLOCKED_TEMPORAL_INTEGRITY"


@pytest.mark.parametrize("claim", ["BLOCKED_HOLDOUT_REUSE", "OVERLAP_SAME_STUDY", "LEDGER_UNAVAILABLE", "NEWISH"])
def test_qualify_rejects_holdout_reuse(trained, tmp_path, claim):
    p = _copy(trained["out"], tmp_path, edit=lambda d: d["holdout_claim"].update(status=claim))
    assert _state(p, trained) == "BLOCKED_HOLDOUT_REUSE"


@pytest.mark.parametrize("edit", [
    lambda d: d.update(holdout_logloss=d["holdout_logloss"] * 0.9),
    lambda d: d.update(holdout_acc=d["holdout_acc"] - 0.01),
    lambda d: d["baseline"].update(logit_logloss=d["baseline"]["logit_logloss"] + 0.05),
    lambda d: d["baseline"].update(null_logloss=d["baseline"]["null_logloss"] + 0.05),
    lambda d: d.update(best_iteration=d["best_iteration"] - 1),
    lambda d: d.update(incremental_value_status="FAIL"),
], ids=["logloss", "acc", "logit", "null", "rounds", "gate"])
def test_qualify_replays_the_holdout_and_rejects_forged_numbers(trained, tmp_path, edit):
    assert _state(_copy(trained["out"], tmp_path, edit=edit), trained) == "BLOCKED_PROVENANCE"


def test_qualify_rejects_a_forged_model_even_with_a_matching_hash(trained, tmp_path):
    p = _copy(trained["out"], tmp_path)
    d = json.loads(p.read_text())
    blob = b'{"learner": "not a booster"}'
    (tmp_path / d["model_file"]).write_bytes(blob)
    d["model_sha256"] = hashlib.sha256(blob).hexdigest()
    p.write_text(json.dumps(d))
    assert _state(p, trained) == "BLOCKED_PROVENANCE"


def test_qualify_blocks_a_genuine_baseline_failure(tmp_path):
    t = _fit_csv(tmp_path, seed=5)   # a random walk: nothing to learn
    assert t["report"]["status"] == "fitted" and t["report"]["incremental_value_status"] == "FAIL"
    assert _state(t["out"], t) == "BLOCKED_BASELINE_NOT_BEATEN"


def test_qualify_rejects_broken_provenance(trained, tmp_path):
    out = trained["out"]
    assert _state(_copy(out, tmp_path / "a", model=False), trained) == "BLOCKED_PROVENANCE"
    tampered = _copy(out, tmp_path / "b")
    model = tampered.parent / json.loads(tampered.read_text())["model_file"]
    model.write_bytes(model.read_bytes() + b" ")
    assert _state(tampered, trained) == "BLOCKED_PROVENANCE"
    cal = _copy(out, tmp_path / "c", edit=lambda d: d["calibration"].update(status="VALIDATED"))
    assert _state(cal, trained) == "BLOCKED_PROVENANCE"
    replay = _copy(out, tmp_path / "d", edit=lambda d: d.update(serialization_replay=False))
    assert _state(replay, trained) == "BLOCKED_PROVENANCE"
    escape = _copy(out, tmp_path / "e", edit=lambda d: d.update(model_file="../elsewhere.json"))
    assert _state(escape, trained) == "BLOCKED_PROVENANCE"


def test_model_file_is_content_addressed_and_fit_single_threaded(trained):
    r = trained["report"]
    assert r["model_file"] == f"NQ_clock_minutes_xgb.{r['model_sha256'][:16]}.model.json"
    assert r["execution"] == {"nthread": 1}


# ---- audit gate ------------------------------------------------------------------------------------

def test_audit_does_not_trust_an_artifact_that_merely_exists(tmp_path):
    p = tmp_path / "NQ_clock_minutes_xgb.json"
    p.write_text("{}")
    r = score_pair(_audit_bars(), _audit_bars(), seed_events(), "AAPL", "NQ", xgb_path=p)
    assert r["overlap"] >= 200 and r["sign_agree"] >= 0.55
    assert r["swap_recommend"] is False and r["xgb_state"] == "BLOCKED_MALFORMED"


def test_audit_swaps_only_with_an_artifact_the_execution_bars_vouch_for(trained):
    bars, out = trained["bars"], trained["out"]
    r = score_pair(bars, bars, seed_events(), "AAPL", "NQ", xgb_path=out)
    assert r["swap_recommend"] is True and r["xgb_state"] == "VALID_RAW_CHALLENGER"
    assert r["execution_authorized"] is False
    hashed = score_pair(bars, bars, seed_events(), "AAPL", "NQ", xgb_path=out, exec_sha256="e" * 64)
    assert hashed["swap_recommend"] is False and hashed["xgb_state"] == "BLOCKED_IDENTITY_MISMATCH"
    foreign = score_pair(_audit_bars(), _audit_bars(), seed_events(), "AAPL", "NQ", xgb_path=out)
    assert foreign["swap_recommend"] is False and foreign["xgb_state"] == "BLOCKED_IDENTITY_MISMATCH"


def test_require_xgb_blocks_on_an_unqualified_artifact(tmp_path):
    p = tmp_path / "x.json"
    p.write_text("{}")
    r = score_pair(_audit_bars(), _audit_bars(), seed_events(), "AAPL", "NQ", require_xgb=True, xgb_path=p)
    assert r["status"] == "blocked" and r["swap_recommend"] is False and r["execution_authorized"] is False
