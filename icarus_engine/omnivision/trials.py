"""Immutable search-aware research trial contracts for OMNIVISION."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import re

_HASH = re.compile(r"^[0-9a-f]{64}$")
TRIAL_STATUSES = frozenset({
    "planned", "running", "passed", "rejected", "failed", "duplicate", "deferred", "invalidated",
})
_COMPLETED_STATUSES = frozenset({"passed", "rejected", "failed", "duplicate", "invalidated"})
_REASON_REQUIRED = frozenset({"rejected", "failed", "duplicate", "invalidated"})


def _canon(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


def _hash(value, name: str) -> str:
    if type(value) is not str or not _HASH.fullmatch(value):
        raise ValueError(f"{name} must be lowercase SHA-256")
    return value


def _text(value, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def _time(value, name: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _hash_tuple(value, name: str, *, required: bool) -> tuple[str, ...]:
    if type(value) is not tuple or (required and not value):
        raise ValueError(f"{name} must be a {'non-empty ' if required else ''}tuple")
    if len(set(value)) != len(value):
        raise ValueError(f"{name} must be unique")
    for item in value:
        _hash(item, f"{name} entry")
    return value


def _text_tuple(value, name: str, *, required: bool) -> tuple[str, ...]:
    if type(value) is not tuple or (required and not value):
        raise ValueError(f"{name} must be a {'non-empty ' if required else ''}tuple")
    if len(set(value)) != len(value):
        raise ValueError(f"{name} must be unique")
    for item in value:
        _text(item, f"{name} entry")
    return value


def _numeric_pairs(value, name: str) -> tuple[tuple[str, float], ...]:
    if type(value) is not tuple:
        raise ValueError(f"{name} must be a tuple")
    keys = []
    for item in value:
        if type(item) is not tuple or len(item) != 2:
            raise ValueError(f"{name} entries must be (name, value) tuples")
        key, number = item
        _text(key, f"{name} key")
        if isinstance(number, bool) or type(number) not in (int, float) or not math.isfinite(number):
            raise ValueError(f"{name} values must be finite numbers")
        keys.append(key)
    if len(set(keys)) != len(keys):
        raise ValueError(f"{name} keys must be unique")
    return value


@dataclass(frozen=True)
class TrialRecord:
    trial_id: str
    hypothesis_id: str
    hypothesis_family_id: str
    parent_trial_ids: tuple[str, ...]
    generation_method: str
    feature_config_hash: str
    dataset_snapshot_hashes: tuple[str, ...]
    train_start: int
    train_end: int
    validation_start: int
    validation_end: int
    holdout_start: int
    holdout_end: int
    code_hash: str
    config_hash: str
    decision_at: int
    metrics: tuple[tuple[str, float], ...]
    cost_assumptions: tuple[tuple[str, float], ...]
    status: str
    rejection_reason: str | None
    family_memberships: tuple[str, ...]
    execution_authorized: bool = False

    def __post_init__(self):
        _hash(self.trial_id, "trial_id")
        _hash(self.hypothesis_id, "hypothesis_id")
        _hash(self.hypothesis_family_id, "hypothesis_family_id")
        _hash_tuple(self.parent_trial_ids, "parent_trial_ids", required=False)
        if self.trial_id in self.parent_trial_ids:
            raise ValueError("trial cannot be its own parent")
        _text(self.generation_method, "generation_method")
        _hash(self.feature_config_hash, "feature_config_hash")
        _hash_tuple(self.dataset_snapshot_hashes, "dataset_snapshot_hashes", required=True)
        for name in (
            "train_start", "train_end", "validation_start", "validation_end",
            "holdout_start", "holdout_end", "decision_at",
        ):
            _time(getattr(self, name), name)
        if not (
            self.train_start < self.train_end <= self.validation_start
            < self.validation_end <= self.holdout_start < self.holdout_end
        ):
            raise ValueError("train/validation/holdout boundaries must be ordered and non-overlapping")
        _hash(self.code_hash, "code_hash")
        _hash(self.config_hash, "config_hash")
        _numeric_pairs(self.metrics, "metrics")
        _numeric_pairs(self.cost_assumptions, "cost_assumptions")
        if self.status not in TRIAL_STATUSES:
            raise ValueError("unsupported trial status")
        if self.status in _COMPLETED_STATUSES and self.decision_at < self.holdout_end:
            raise ValueError("completed trial decision_at cannot precede holdout_end")
        if self.status in _REASON_REQUIRED:
            _text(self.rejection_reason, "rejection_reason")
        elif self.rejection_reason is not None:
            _text(self.rejection_reason, "rejection_reason")
        _text_tuple(self.family_memberships, "family_memberships", required=True)
        if self.execution_authorized is not False:
            raise ValueError("trials never authorize execution")
        body = {k: v for k, v in asdict(self).items() if k != "trial_id"}
        if self.trial_id != _digest(body):
            raise ValueError("trial_id does not match trial content")

    @classmethod
    def build(cls, **values) -> "TrialRecord":
        if "trial_id" in values:
            raise ValueError("trial_id is computed by TrialRecord.build")
        values.setdefault("execution_authorized", False)
        return cls(trial_id=_digest(values), **values)


from pathlib import Path
import sqlite3


def _trial_from_json(payload_json: str) -> TrialRecord:
    values = json.loads(payload_json)
    for name in ("parent_trial_ids", "dataset_snapshot_hashes", "family_memberships"):
        values[name] = tuple(values[name])
    for name in ("metrics", "cost_assumptions"):
        values[name] = tuple(tuple(item) for item in values[name])
    return TrialRecord(**values)


class TrialLedger:
    """Append-only record of every meaningful OMNIVISION research attempt."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        with sqlite3.connect(self.path) as connection:
            connection.executescript("""
                CREATE TABLE IF NOT EXISTS omnivision_trials (
                    trial_id TEXT PRIMARY KEY,
                    hypothesis_id TEXT NOT NULL,
                    hypothesis_family_id TEXT NOT NULL,
                    decision_at INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    recorded_at INTEGER NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_omnivision_trial_family
                ON omnivision_trials(hypothesis_family_id, decision_at, trial_id);
                CREATE TRIGGER IF NOT EXISTS omnivision_trials_no_update
                BEFORE UPDATE ON omnivision_trials
                BEGIN
                    SELECT RAISE(ABORT, 'omnivision_trials is append-only');
                END;
                CREATE TRIGGER IF NOT EXISTS omnivision_trials_no_delete
                BEFORE DELETE ON omnivision_trials
                BEGIN
                    SELECT RAISE(ABORT, 'omnivision_trials is append-only');
                END;
            """)

    def record(self, trial: TrialRecord, *, recorded_at: int) -> str:
        if not isinstance(trial, TrialRecord):
            raise TypeError("trial must be TrialRecord")
        _time(recorded_at, "recorded_at")
        if recorded_at < trial.decision_at:
            raise ValueError("recorded_at cannot precede decision_at")
        payload = _canon(asdict(trial))
        with sqlite3.connect(self.path) as connection:
            existing = connection.execute(
                "SELECT payload_json FROM omnivision_trials WHERE trial_id=?",
                (trial.trial_id,),
            ).fetchone()
            if existing is not None:
                if existing[0] == payload:
                    return trial.trial_id
                raise ValueError("trial_id already exists with different payload")
            connection.execute(
                "INSERT INTO omnivision_trials "
                "(trial_id, hypothesis_id, hypothesis_family_id, decision_at, status, payload_json, recorded_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    trial.trial_id, trial.hypothesis_id, trial.hypothesis_family_id,
                    trial.decision_at, trial.status, payload, recorded_at,
                ),
            )
        return trial.trial_id

    def get(self, trial_id: str) -> TrialRecord | None:
        _hash(trial_id, "trial_id")
        with sqlite3.connect(self.path) as connection:
            row = connection.execute(
                "SELECT payload_json FROM omnivision_trials WHERE trial_id=?", (trial_id,)
            ).fetchone()
        return None if row is None else _trial_from_json(row[0])

    def family(self, hypothesis_family_id: str) -> tuple[TrialRecord, ...]:
        _hash(hypothesis_family_id, "hypothesis_family_id")
        with sqlite3.connect(self.path) as connection:
            rows = connection.execute(
                "SELECT payload_json FROM omnivision_trials WHERE hypothesis_family_id=? "
                "ORDER BY decision_at ASC, trial_id ASC",
                (hypothesis_family_id,),
            ).fetchall()
        return tuple(_trial_from_json(row[0]) for row in rows)

    def family_summary(self, hypothesis_family_id: str) -> dict:
        items = self.family(hypothesis_family_id)
        statuses = {name: 0 for name in ("passed", "rejected", "failed", "duplicate", "deferred", "invalidated")}
        for item in items:
            if item.status in statuses:
                statuses[item.status] += 1
        return {
            "hypothesis_family_id": hypothesis_family_id,
            "attempts_total": len(items),
            **statuses,
            "generation_methods": tuple(sorted({item.generation_method for item in items})),
            "dataset_snapshot_hashes": tuple(sorted({h for item in items for h in item.dataset_snapshot_hashes})),
        }

    def search_burden(self, hypothesis_family_id: str) -> dict:
        items = self.family(hypothesis_family_id)
        configs = {(item.feature_config_hash, item.config_hash) for item in items}
        datasets = {item.dataset_snapshot_hashes for item in items}
        evaluated = [item for item in items if item.status in {"passed", "rejected", "failed", "invalidated"}]
        correction_required = len(configs) > 1 or len(evaluated) > 1
        if not items:
            reason = "no_recorded_attempts"
        elif len(items) == 1:
            reason = "single_recorded_attempt"
        elif correction_required:
            reason = "multiple_search_paths"
        else:
            reason = "single_effective_evaluation"
        return {
            "attempts_total": len(items),
            "distinct_configs": len(configs),
            "distinct_datasets": len(datasets),
            "correction_required": correction_required,
            "reason": reason,
        }
