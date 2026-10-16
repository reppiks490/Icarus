from __future__ import annotations

import builtins
import hashlib

import pytest

from icarus_engine.spec import FEATURE_KEYS, SLOTS
from icarus_engine.trainers import deep_challenger
from icarus_engine.trainers import run
from icarus_engine.trainers.dataset import walk_slices
from icarus_engine.trainers.sequence import causal_sequence_rows, fit_standardizer, standardize_sequence


def _row(i: int, *, y: int | None = None, scale: float = 1.0):
    return {
        "ts": float(i),
        "label_ts": float(i + 1),
        "y": (1 if i % 2 == 0 else -1) if y is None else y,
        "x": {key: scale * float(i + j + 1) for j, key in enumerate(FEATURE_KEYS)},
    }


def _write_source(path, count=240, *, changed_at=None):
    lines = ["time,open,high,low,close,volume"]
    close = 100.0
    for i in range(count):
        if i:
            close += 1.0 if i % 2 else -0.75
        if i == changed_at:
            close += 4.0
        ts = 1_700_000_000 + i * 60
        lines.append(f"{ts},{close},{close + 1},{close - 1},{close},100")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


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
    source = _write_source(tmp_path / "short.csv", 30)
    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "torch" or name.startswith("torch."):
            raise AssertionError("torch must not be imported before dataset preflight passes")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    report = deep_challenger.train_source(
        source, "NQ", "clock_minutes", tmp_path / "gru.json", ledger_path=tmp_path / "ledger.sqlite3"
    )

    assert report["status"] == "skipped"
    assert "rows" in report["reason"] or "walk-forward" in report["reason"]
    assert report["execution_authorized"] is False
    assert report["production_decision_authorized"] is False


def test_gru_challenger_blocks_cleanly_when_optional_backend_is_missing(monkeypatch, tmp_path):
    source = _write_source(tmp_path / "source.csv", 240)

    def missing_backend():
        return None, "PyTorch is not installed"

    monkeypatch.setattr(deep_challenger, "_load_torch", missing_backend)
    report = deep_challenger.train_source(
        source, "NQ", "clock_minutes", tmp_path / "gru.json", ledger_path=tmp_path / "ledger.sqlite3"
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
    source = _write_source(tmp_path / "source.csv", 501)
    hold_start = walk_slices(499)[2][0]
    claimed = {"value": False}
    original_inspect = deep_challenger.inspect_ohlc

    class GuardedBar(dict):
        def __init__(self, index, row):
            super().__init__(row)
            self.index = index

        def __getitem__(self, key):
            if key in {"open", "high", "low", "close", "volume", "tide_long", "tide_short"}:
                if self.index >= hold_start and not claimed["value"]:
                    raise AssertionError("holdout feature/label source read before ledger claim")
            return super().__getitem__(key)

        def get(self, key, default=None):
            if key in {"open", "high", "low", "close", "volume", "tide_long", "tide_short"}:
                if self.index >= hold_start and not claimed["value"]:
                    raise AssertionError("holdout feature source read before ledger claim")
            return super().get(key, default)

    def guarded_inspect(path, *, raw_bytes=None, **kwargs):
        bars, manifest = original_inspect(path, raw_bytes=raw_bytes, **kwargs)
        if not claimed["value"] and len(bars) > hold_start:
            raise AssertionError("full holdout price/features parsed before ledger claim")
        return [GuardedBar(i, row) for i, row in enumerate(bars)], manifest

    monkeypatch.setattr(deep_challenger, "inspect_ohlc", guarded_inspect)
    original_claim = deep_challenger.ledger.claim_holdout

    def guarded_claim(*args, **kwargs):
        result = original_claim(*args, **kwargs)
        claimed["value"] = True
        return result

    monkeypatch.setattr(deep_challenger.ledger, "claim_holdout", guarded_claim)

    monkeypatch.setitem(deep_challenger._MODEL, "epochs", 2)
    monkeypatch.setitem(deep_challenger._MODEL, "patience", 1)
    monkeypatch.setitem(deep_challenger._MODEL, "hidden_size", 4)
    monkeypatch.setitem(deep_challenger._MODEL, "layers", 1)
    monkeypatch.setitem(deep_challenger._MODEL, "dropout", 0.0)
    monkeypatch.setitem(deep_challenger._MODEL, "batch_size", 64)

    report = run.train_deep_gru_file(
        source, "minutes", "ohlc", "NQ", out=tmp_path / "gru.json",
        ledger=tmp_path / "ledger.sqlite3",
    )

    assert claimed["value"] is True
    assert report["status"] == "fitted"
    assert report["lane"] == "deep_learning_challenger"
    assert report["model"] == "gru"
    assert report["holdout_touched_before_final"] is False
    assert report["serialization_replay"] is True
    assert report["holdout_claim"]["status"] == "NEW"
    assert report["holdout_claim"]["ledger_namespace"] == "deep_challenger_gru"
    assert report["dataset_sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert report["rows_sha256_basis"] == "source_bytes_and_row_construction"
    assert report["rows_sha256"] != report["dataset_sha256"]
    assert report["execution_authorized"] is False
    assert report["production_decision_authorized"] is False
    assert report["auto_promote"] is False
    significance = report["significance"]
    assert significance["minimum_lag"] == report["sequence_length"] - 1
    assert significance["vs_logit"]["lag"] >= significance["minimum_lag"]
    assert significance["vs_null"]["lag"] >= significance["minimum_lag"]
    assert (tmp_path / report["model_file"]).is_file()

    # Changing a holdout source row while keeping timestamps fixed must not be
    # treated as an identical-study replay for the same claimed interval.
    _write_source(source, 501, changed_at=450)
    claimed["value"] = False
    changed = run.train_deep_gru_file(
        source, "minutes", "ohlc", "NQ", out=tmp_path / "changed.json",
        ledger=tmp_path / "ledger.sqlite3",
    )
    assert changed["status"] == "blocked"
    assert changed["holdout_claim"]["status"] == deep_challenger.ledger.REUSE


@pytest.mark.parametrize("bad_row", ["ohlc", "tide"])
def test_first_holdout_integrity_failure_occurs_after_claim(monkeypatch, tmp_path, bad_row):
    pytest.importorskip("torch")
    source = _write_source(tmp_path / f"{bad_row}.csv", 501)
    hold_start = walk_slices(499)[2][0]
    lines = source.read_text(encoding="utf-8").splitlines()
    if bad_row == "ohlc":
        cells = lines[hold_start + 1].split(",")
        cells[2] = str(float(cells[4]) - 2.0)  # high is below low and close
        lines[hold_start + 1] = ",".join(cells)
    else:
        header = lines[0].split(",") + ["TIDE Long", "TIDE Long"]
        rows = [header]
        for index, line in enumerate(lines[1:]):
            cells = line.split(",") + ["7", "8" if index == hold_start else "7"]
            rows.append(cells)
        lines = [",".join(row) for row in rows]
    source.write_text("\n".join(lines) + "\n", encoding="utf-8")

    claimed = {"value": False}
    original_inspect = deep_challenger.inspect_ohlc
    source_bytes = source.read_bytes()

    def guarded_inspect(path, *, raw_bytes=None, **kwargs):
        if raw_bytes == source_bytes and not claimed["value"]:
            raise AssertionError("full terminal source parsed before the ledger claim")
        return original_inspect(path, raw_bytes=raw_bytes, **kwargs)

    monkeypatch.setattr(deep_challenger, "inspect_ohlc", guarded_inspect)
    original_claim = deep_challenger.ledger.claim_holdout

    def record_claim(*args, **kwargs):
        status = original_claim(*args, **kwargs)
        claimed["value"] = True
        return status

    monkeypatch.setattr(deep_challenger.ledger, "claim_holdout", record_claim)
    for key, value in {"epochs": 1, "patience": 1, "hidden_size": 4, "layers": 1,
                       "dropout": 0.0, "batch_size": 64}.items():
        monkeypatch.setitem(deep_challenger._MODEL, key, value)

    report = run.train_deep_gru_file(
        source, "minutes", "ohlc", "NQ", out=tmp_path / "blocked.json",
        ledger=tmp_path / "ledger.sqlite3",
    )
    assert claimed["value"] is True
    assert report["status"] == "blocked"
    assert report["holdout_claim"]["status"] == deep_challenger.ledger.NEW
    assert "full source differs" in report["reason"]
