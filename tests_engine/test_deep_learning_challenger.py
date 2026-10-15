from __future__ import annotations

import builtins

import pytest

from icarus_engine.spec import FEATURE_KEYS, SLOTS
from icarus_engine.trainers import deep_challenger
from icarus_engine.trainers.sequence import causal_sequence_rows, fit_standardizer, standardize_sequence


def _row(i: int, *, y: int | None = None, scale: float = 1.0):
    return {
        "ts": float(i),
        "label_ts": float(i + 1),
        "y": (1 if i % 2 == 0 else -1) if y is None else y,
        "x": {key: scale * float(i + j + 1) for j, key in enumerate(FEATURE_KEYS)},
    }


def test_causal_sequences_end_at_decision_row_and_never_read_future():
    rows = [_row(i) for i in range(12)]
    seqs = causal_sequence_rows(rows, start=5, stop=9, sequence_length=4)

    assert [seq["end_index"] for seq in seqs] == [5, 6, 7, 8]
    assert [seq["ts"] for seq in seqs] == [5.0, 6.0, 7.0, 8.0]
    assert [seq["label_ts"] for seq in seqs] == [6.0, 7.0, 8.0, 9.0]

    for seq in seqs:
        end = seq["end_index"]
        first_feature = FEATURE_KEYS[0]
        observed = [step[first_feature] for step in seq["steps"]]
        assert observed == [rows[i]["x"][first_feature] for i in range(end - 3, end + 1)]
        assert max(observed) == rows[end]["x"][first_feature]


def test_standardizer_is_fit_only_on_training_rows_and_handles_constant_features():
    train = [_row(i) for i in range(8)]
    for row in train:
        row["x"][FEATURE_KEYS[-1]] = 7.0

    standardizer = fit_standardizer(train)
    before = dict(standardizer["mean"]), dict(standardizer["scale"])

    future = _row(1000, scale=1000.0)
    normalized = standardize_sequence([future["x"]], standardizer)

    assert before == (standardizer["mean"], standardizer["scale"])
    assert standardizer["scale"][FEATURE_KEYS[-1]] == 1.0
    assert len(normalized) == 1
    assert set(normalized[0]) == set(FEATURE_KEYS)


def test_deep_challenger_does_not_modify_frozen_trainer_slots():
    assert SLOTS == {
        "logit": "slot0",
        "xgb": "slot1",
        "rank": "slot2",
        "regime": "slot3",
        "fail": "slot4",
    }
    contract = deep_challenger.contract()
    assert contract["existing_trainer_slots_modified"] is False
    assert "slot" not in contract


def test_gru_challenger_fails_closed_on_short_history_without_importing_torch(monkeypatch, tmp_path):
    rows = [_row(i) for i in range(30)]
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "torch" or name.startswith("torch."):
            raise AssertionError("torch must not be imported before dataset preflight passes")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    report = deep_challenger.train(
        rows, "NQ", "clock_minutes", tmp_path / "gru.json", ledger_path=tmp_path / "ledger.sqlite3"
    )

    assert report["status"] == "skipped"
    assert "rows" in report["reason"] or "walk-forward" in report["reason"]
    assert report["execution_authorized"] is False
    assert report["production_decision_authorized"] is False


def test_gru_challenger_blocks_cleanly_when_optional_backend_is_missing(monkeypatch, tmp_path):
    rows = [_row(i) for i in range(240)]

    def missing_backend():
        return None, "PyTorch is not installed"

    monkeypatch.setattr(deep_challenger, "_load_torch", missing_backend)
    report = deep_challenger.train(
        rows, "NQ", "clock_minutes", tmp_path / "gru.json", ledger_path=tmp_path / "ledger.sqlite3"
    )

    assert report["status"] == "blocked"
    assert "PyTorch" in report["reason"]
    assert report["execution_authorized"] is False
    assert report["production_decision_authorized"] is False


def test_gru_challenger_contract_is_research_only_and_reuses_frozen_feature_keys():
    contract = deep_challenger.contract()

    assert contract["lane"] == "deep_learning_challenger"
    assert contract["model"] == "gru"
    assert contract["features"] == list(FEATURE_KEYS)
    assert contract["sequence_length"] >= 4
    assert contract["significance"]["minimum_lag"] == contract["sequence_length"] - 1
    assert contract["execution_authorized"] is False
    assert contract["production_decision_authorized"] is False
    assert contract["auto_promote"] is False


def test_gru_challenger_end_to_end_when_torch_is_available(monkeypatch, tmp_path):
    pytest.importorskip("torch")
    rows = [_row(i, y=(1 if (i // 4) % 2 == 0 else -1)) for i in range(240)]

    monkeypatch.setitem(deep_challenger._MODEL, "epochs", 2)
    monkeypatch.setitem(deep_challenger._MODEL, "patience", 1)
    monkeypatch.setitem(deep_challenger._MODEL, "hidden_size", 4)
    monkeypatch.setitem(deep_challenger._MODEL, "layers", 1)
    monkeypatch.setitem(deep_challenger._MODEL, "dropout", 0.0)
    monkeypatch.setitem(deep_challenger._MODEL, "batch_size", 64)

    report = deep_challenger.train(
        rows,
        "NQ",
        "clock_minutes",
        tmp_path / "gru.json",
        ledger_path=tmp_path / "ledger.sqlite3",
        dataset_sha256="synthetic-contract",
    )

    assert report["status"] == "fitted"
    assert report["lane"] == "deep_learning_challenger"
    assert report["model"] == "gru"
    assert report["holdout_touched_before_final"] is False
    assert report["serialization_replay"] is True
    assert report["holdout_claim"]["status"] == "NEW"
    assert report["holdout_claim"]["ledger_namespace"] == "deep_challenger_gru"
    assert report["execution_authorized"] is False
    assert report["production_decision_authorized"] is False
    assert report["auto_promote"] is False
    significance = report["significance"]
    assert significance["minimum_lag"] == report["sequence_length"] - 1
    assert significance["vs_logit"]["lag"] >= significance["minimum_lag"]
    assert significance["vs_null"]["lag"] >= significance["minimum_lag"]
    assert (tmp_path / report["model_file"]).is_file()
