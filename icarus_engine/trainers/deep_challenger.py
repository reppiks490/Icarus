from __future__ import annotations

import math
import platform
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from icarus_engine.spec import FEATURE_KEYS, LABEL, WALK

from . import ledger, logit
from .artifact import canon, code_digest, lock, sha, write_json_atomic
from .calibrate import isotonic_apply, isotonic_fit
from .dataset import walk_slices
from .metrics import incremental_status, logloss, sign_accuracy, significance
from .sequence import causal_sequence_rows, fit_standardizer, standardize_sequence

SCHEMA = "icarus.research.deep_challenger.gru/1"
LEDGER_NAMESPACE = "deep_challenger_gru"
CODE_FILES = (
    "spec.py",
    "events/calendar.py",
    "evidence/timestamps.py",
    "trainers/dataset.py",
    "trainers/sequence.py",
    "trainers/logit.py",
    "trainers/calibrate.py",
    "trainers/metrics.py",
    "trainers/deep_challenger.py",
)
_MODEL = {
    "kind": "gru",
    "sequence_length": 16,
    "hidden_size": 16,
    "layers": 2,
    "dropout": 0.10,
    "epochs": 60,
    "patience": 8,
    "min_delta": 1e-6,
    "batch_size": 128,
    "learning_rate": 1e-3,
    "weight_decay": 1e-4,
    "seed": 7,
    "device": "cpu",
}


def _locked(report: dict[str, Any]) -> dict[str, Any]:
    report = lock(report)
    report["production_decision_authorized"] = False
    report["auto_promote"] = False
    return report


def contract() -> dict[str, Any]:
    """Immutable research contract; deliberately not an ICARUS trainer slot."""
    return _locked(
        {
            "schema": SCHEMA,
            "lane": "deep_learning_challenger",
            "model": _MODEL["kind"],
            "features": list(FEATURE_KEYS),
            "sequence_length": _MODEL["sequence_length"],
            "architecture": {
                "hidden_size": _MODEL["hidden_size"],
                "layers": _MODEL["layers"],
                "dropout": _MODEL["dropout"],
            },
            "training": {
                "epochs": _MODEL["epochs"],
                "patience": _MODEL["patience"],
                "batch_size": _MODEL["batch_size"],
                "learning_rate": _MODEL["learning_rate"],
                "weight_decay": _MODEL["weight_decay"],
                "seed": _MODEL["seed"],
                "device": _MODEL["device"],
                "shuffle": False,
            },
            "split": dict(WALK),
            "calibration": "isotonic_on_validation_only",
            "existing_trainer_slots_modified": False,
        }
    )


def _load_torch():
    try:
        import torch
    except ImportError:
        return None, "PyTorch is not installed; install the optional deep-learning extra with pip install 'icarus[deep]'"
    return torch, None


def code_sha256() -> str:
    return code_digest(CODE_FILES)


def study_sha256() -> str:
    return sha(
        canon(
            {
                "schema": SCHEMA,
                "features": list(FEATURE_KEYS),
                "model": dict(_MODEL),
                "walk": dict(WALK),
                "label": LABEL,
                "code": code_sha256(),
            }
        )
    )


def _split_bounds(rows: Sequence[Mapping[str, Any]], train, valid, hold) -> dict[str, float]:
    return {
        "train_end_ts": float(rows[train[1] - 1]["ts"]),
        "valid_start_ts": float(rows[valid[0]]["ts"]),
        "valid_end_ts": float(rows[valid[1] - 1]["ts"]),
        "hold_start_ts": float(rows[hold[0]]["ts"]),
        "hold_end_ts": float(rows[hold[1] - 1]["ts"]),
    }


def _tensorize(torch, sequences, standardizer):
    nested = []
    ys = []
    for seq in sequences:
        normalized = standardize_sequence(seq["steps"], standardizer)
        nested.append([[step[key] for key in FEATURE_KEYS] for step in normalized])
        ys.append(1.0 if seq["y"] > 0 else 0.0)
    x = torch.tensor(nested, dtype=torch.float32, device="cpu")
    y = torch.tensor(ys, dtype=torch.float32, device="cpu")
    return x, y


def _make_model(torch):
    class SequenceGRU(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.gru = torch.nn.GRU(
                input_size=len(FEATURE_KEYS),
                hidden_size=_MODEL["hidden_size"],
                num_layers=_MODEL["layers"],
                dropout=_MODEL["dropout"] if _MODEL["layers"] > 1 else 0.0,
                batch_first=True,
            )
            self.head = torch.nn.Linear(_MODEL["hidden_size"], 1)

        def forward(self, x):
            out, _ = self.gru(x)
            return self.head(out[:, -1, :]).squeeze(-1)

    return SequenceGRU()


def _configure_determinism(torch):
    torch.manual_seed(_MODEL["seed"])
    try:
        torch.set_num_threads(1)
    except RuntimeError:
        pass
    try:
        torch.set_num_interop_threads(1)
    except (AttributeError, RuntimeError):
        pass
    try:
        torch.use_deterministic_algorithms(True)
    except AttributeError:
        pass


def _predict(torch, model, x) -> list[float]:
    model.eval()
    with torch.no_grad():
        probs = torch.sigmoid(model(x)).detach().cpu().tolist()
    return [min(max(float(value), 1e-12), 1.0 - 1e-12) for value in probs]


def _train_model(torch, train_x, train_y, valid_x, valid_signs):
    _configure_determinism(torch)
    model = _make_model(torch)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=_MODEL["learning_rate"],
        weight_decay=_MODEL["weight_decay"],
    )
    criterion = torch.nn.BCEWithLogitsLoss()
    best_loss = math.inf
    best_epoch = -1
    best_state = None
    stale = 0
    history: list[dict[str, float | int]] = []
    batch_size = _MODEL["batch_size"]

    for epoch in range(_MODEL["epochs"]):
        model.train()
        total_loss = 0.0
        total_rows = 0
        for start in range(0, len(train_x), batch_size):
            stop = min(start + batch_size, len(train_x))
            xb = train_x[start:stop]
            yb = train_y[start:stop]
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(xb), yb)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=5.0)
            optimizer.step()
            rows = stop - start
            total_loss += float(loss.detach().cpu()) * rows
            total_rows += rows

        valid_probs = _predict(torch, model, valid_x)
        valid_loss = logloss(valid_probs, valid_signs)
        history.append(
            {
                "epoch": epoch,
                "train_bce": total_loss / max(total_rows, 1),
                "valid_logloss": valid_loss,
            }
        )
        if valid_loss < best_loss - _MODEL["min_delta"]:
            best_loss = valid_loss
            best_epoch = epoch
            best_state = {name: tensor.detach().cpu().clone() for name, tensor in model.state_dict().items()}
            stale = 0
        else:
            stale += 1
            if stale >= _MODEL["patience"]:
                break

    if best_state is None:
        raise ValueError("GRU training produced no finite validation state")
    model.load_state_dict(best_state)
    return model, best_epoch, best_loss, history


def _state_payload(model) -> dict[str, Any]:
    return {
        name: {"shape": list(tensor.shape), "values": tensor.detach().cpu().tolist()}
        for name, tensor in sorted(model.state_dict().items())
    }


def _load_state(torch, model, payload: Mapping[str, Any]) -> None:
    current = model.state_dict()
    restored = {}
    for name, target in current.items():
        item = payload.get(name)
        if not isinstance(item, Mapping):
            raise ValueError(f"model state missing {name}")
        shape = list(item.get("shape") or ())
        if shape != list(target.shape):
            raise ValueError(f"model state shape mismatch for {name}")
        tensor = torch.tensor(item.get("values"), dtype=target.dtype, device="cpu")
        restored[name] = tensor.reshape(target.shape)
    model.load_state_dict(restored, strict=True)


def _write_model(out_path: Path, model, standardizer, calibration, study: str):
    payload = {
        "schema": SCHEMA,
        "lane": "deep_learning_challenger",
        "model": "gru",
        "study_sha256": study,
        "contract": contract(),
        "standardizer": standardizer,
        "calibration": calibration,
        "state_dict": _state_payload(model),
    }
    model_sha = sha(canon(payload))
    model_path = out_path.with_name(f"{out_path.stem}.{model_sha[:16]}.model.json")
    write_json_atomic(model_path, payload)
    return model_path, model_sha, payload


def train(
    labeled: Sequence[Mapping[str, Any]],
    symbol: str,
    family: str,
    out_path,
    ledger_path=None,
    dataset_sha256=None,
    extra=None,
):
    symbol = str(symbol or "").upper()
    head = {
        "lane": "deep_learning_challenger",
        "model": "gru",
        "schema": SCHEMA,
        "symbol": symbol,
        "family": family,
        **(extra or {}),
    }

    # Dataset/split preflight happens before importing the optional deep-learning backend.
    try:
        train_slice, valid_slice, hold_slice = walk_slices(len(labeled))
    except ValueError as exc:
        return _locked({**head, "status": "skipped", "reason": str(exc)})

    sequence_length = _MODEL["sequence_length"]
    try:
        train_rows = labeled[train_slice[0]:train_slice[1]]
        standardizer = fit_standardizer(train_rows)
        train_seq = causal_sequence_rows(
            labeled, start=train_slice[0], stop=train_slice[1], sequence_length=sequence_length
        )
        valid_seq = causal_sequence_rows(
            labeled, start=valid_slice[0], stop=valid_slice[1], sequence_length=sequence_length
        )
    except (KeyError, TypeError, ValueError) as exc:
        return _locked({**head, "status": "blocked", "reason": f"sequence preflight failed: {exc}"})

    hold_sequence_count = max(0, hold_slice[1] - max(hold_slice[0], sequence_length - 1))
    if len(train_seq) < 20 or len(valid_seq) < 10 or hold_sequence_count < 10:
        return _locked(
            {
                **head,
                "status": "skipped",
                "reason": f"sequence rows too small: train={len(train_seq)} valid={len(valid_seq)} holdout={hold_sequence_count}",
            }
        )

    torch, backend_error = _load_torch()
    if torch is None:
        return _locked({**head, "status": "blocked", "reason": backend_error})

    if not isinstance(dataset_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", dataset_sha256):
        return _locked(
            {**head, "status": "blocked", "reason": "an immutable lowercase SHA-256 source digest is required"}
        )

    try:
        train_x, train_y = _tensorize(torch, train_seq, standardizer)
        valid_x, _ = _tensorize(torch, valid_seq, standardizer)
        valid_signs = [seq["y"] for seq in valid_seq]
        model, best_epoch, best_valid_loss, history = _train_model(
            torch, train_x, train_y, valid_x, valid_signs
        )
        raw_valid = _predict(torch, model, valid_x)
        calibration = isotonic_fit(raw_valid, valid_signs)
    except (RuntimeError, ValueError) as exc:
        return _locked({**head, "status": "blocked", "reason": f"GRU training failed: {exc}"})

    study = study_sha256()
    # The immutable raw-source digest identifies the complete input without
    # materializing protected holdout labels before the ledger claim.
    rsha = dataset_sha256
    bounds = _split_bounds(labeled, train_slice, valid_slice, hold_slice)
    ledger_path = Path(ledger_path) if ledger_path else ledger.canonical()
    claim = ledger.claim_holdout(
        ledger_path,
        symbol,
        family,
        bounds["hold_start_ts"],
        bounds["hold_end_ts"],
        rsha,
        study,
        hold_sequence_count,
        slot=LEDGER_NAMESPACE,
    )
    claim_record = {
        "status": claim,
        "hold_start_ts": bounds["hold_start_ts"],
        "hold_end_ts": bounds["hold_end_ts"],
        "rows_sha256_basis": "raw_source_bytes",
        "ledger": str(ledger_path.resolve()),
        "ledger_namespace": LEDGER_NAMESPACE,
    }
    if claim not in ledger.SCORED:
        return _locked(
            {
                **head,
                "status": "blocked",
                "reason": f"holdout claim {claim}",
                "holdout_claim": claim_record,
                "study_sha256": study,
                "rows_sha256": rsha,
            }
        )

    # The terminal holdout is first materialized here, after its claim and after
    # architecture selection, early stopping, standardization, and calibration
    # are frozen. In particular, sequence construction and tensorization read
    # holdout labels, so neither may happen in the pre-claim training phase.
    try:
        hold_seq = causal_sequence_rows(
            labeled, start=hold_slice[0], stop=hold_slice[1], sequence_length=sequence_length
        )
        hold_x, _ = _tensorize(torch, hold_seq, standardizer)
    except (KeyError, TypeError, ValueError, RuntimeError) as exc:
        return _locked(
            {
                **head,
                "status": "blocked",
                "reason": f"holdout materialization failed after claim: {exc}",
                "holdout_claim": claim_record,
                "dataset_sha256": dataset_sha256,
                "study_sha256": study,
            }
        )
    raw_hold = _predict(torch, model, hold_x)
    calibrated_hold = [isotonic_apply(calibration, p) for p in raw_hold]
    hold_rows = [labeled[seq["end_index"]] for seq in hold_seq]
    hold_signs = [row["y"] for row in hold_rows]

    base_rate = sum(1 for row in train_rows if row["y"] > 0) / len(train_rows)
    baseline_model = logit.fit_newton(train_rows)
    baseline_probs = [logit.predict_sign(baseline_model, row)[1] for row in hold_rows]
    baseline_ll = logloss(baseline_probs, hold_signs)
    null_ll = logloss([base_rate] * len(hold_signs), hold_signs)
    raw_ll = logloss(raw_hold, hold_signs)
    calibrated_ll = logloss(calibrated_hold, hold_signs)

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    calibration_record = {
        "method": "isotonic",
        "fitted_on": "validation_only",
        "rows": len(valid_seq),
        "x": calibration["x"],
        "y": calibration["y"],
    }
    model_path, model_sha, payload = _write_model(
        out_path, model, standardizer, calibration_record, study
    )

    replay_model = _make_model(torch)
    _load_state(torch, replay_model, payload["state_dict"])
    replay_raw = _predict(torch, replay_model, hold_x)
    replay_ok = replay_raw == raw_hold

    report = _locked(
        {
            **head,
            "status": "fitted",
            "features": list(FEATURE_KEYS),
            "sequence_length": sequence_length,
            "n_train": len(train_seq),
            "n_valid": len(valid_seq),
            "n_hold": len(hold_seq),
            "best_epoch": best_epoch,
            "best_valid_logloss": best_valid_loss,
            "training_history": history,
            "split": {"policy": dict(WALK), **bounds},
            "standardizer": standardizer,
            "calibration": calibration_record,
            "holdout_raw": {
                "logloss": raw_ll,
                "accuracy": sign_accuracy(raw_hold, hold_signs),
            },
            "holdout_calibrated": {
                "logloss": calibrated_ll,
                "accuracy": sign_accuracy(calibrated_hold, hold_signs),
            },
            "baseline": {
                "null_p": base_rate,
                "null_logloss": null_ll,
                "logit_logloss": baseline_ll,
                "logit_acc": logit.accuracy(baseline_model, hold_rows),
            },
            "incremental_value_status": incremental_status(calibrated_ll, baseline_ll, null_ll),
            "significance": significance(calibrated_hold, baseline_probs, base_rate, hold_signs, "logit"),
            "holdout_claim": claim_record,
            "holdout_touched_before_final": False,
            "model_file": model_path.name,
            "model_sha256": model_sha,
            "serialization_replay": replay_ok,
            "dataset_sha256": dataset_sha256,
            "rows_sha256": rsha,
            "rows_sha256_basis": "raw_source_bytes",
            "study_sha256": study,
            "code_sha256": code_sha256(),
            "torch_version": getattr(torch, "__version__", "unknown"),
            "python_version": platform.python_version(),
            "device": "cpu",
            "deterministic_algorithms": True,
            "promotion_note": (
                "External research challenger only. PASS means incremental terminal-holdout value versus the "
                "logistic/null baselines for this study; it does not modify frozen trainer slots, authorize "
                "production, or authorize execution."
            ),
        }
    )
    write_json_atomic(out_path, report)
    return report
