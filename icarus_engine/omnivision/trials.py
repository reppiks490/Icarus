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
