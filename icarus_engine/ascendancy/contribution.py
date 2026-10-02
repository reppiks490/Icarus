"""ASCENDANCY conditional contribution measurement.

The Contribution Lab measures *paired predictive log-score gain* from adding a
contributor to a declared conditioning set.  Positive mean gain indicates the
augmented predictor assigned higher probability density to realized outcomes
than the baseline predictor, conditional on the declared comparison context.

This is a practical incremental predictive-information estimator.  It is not an
exact conditional mutual-information estimator and does not by itself prove
causality or authorize trading.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import statistics
import threading
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "icarus-ascendancy-contribution-observation-v1"
LAB_SCHEMA_VERSION = "icarus-ascendancy-contribution-lab-v1"

CONTRIBUTOR_KINDS = {
    "candidate",
    "native_subsystem",
    "foreign_lens",
    "generated",
    "hybrid",
    "architecture",
}
TARGET_KINDS = {"binary", "continuous"}
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA64 = re.compile(r"^[0-9a-f]{64}$")
_LOCK = threading.RLock()
_EPS = 1e-9
_MIN_SUPPORT_N = 8


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _text(value: Any, name: str, limit: int = 1000) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    out = value.strip()
    if not out:
        raise ValueError(f"{name} is required")
    if len(out) > limit:
        raise ValueError(f"{name} exceeds {limit} characters")
    return out


def _canonical(value: Any, name: str = "value", max_bytes: int = 131072) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as ex:
        raise ValueError(f"{name} must be finite JSON") from ex
    if len(raw.encode("utf-8")) > max_bytes:
        raise ValueError(f"{name} exceeds {max_bytes} bytes")
    return raw


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value, "hash input").encode("utf-8")).hexdigest()


def _sha(value: Any, name: str, size: int) -> str:
    out = _text(value, name, size).lower()
    pattern = _SHA40 if size == 40 else _SHA64
    if not pattern.fullmatch(out):
        if size == 40:
            raise ValueError(f"{name} must be an exact 40-character Git SHA")
        raise ValueError(f"{name} must be a {size}-character hash")
    return out


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be finite")
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"{name} must be finite")
    return out


def _positive_int(value: Any, name: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if value < 1 or value > maximum:
        raise ValueError(f"{name} must be between 1 and {maximum}")
    return value


def _observed_at(value: Any) -> str:
    raw = _text(value, "observed_at", 80)
    probe = raw[:-1] + "+00:00" if raw.endswith("Z") else raw
    try:
        dt = datetime.fromisoformat(probe)
    except ValueError as ex:
        raise ValueError("observed_at must be ISO-8601") from ex
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("observed_at must include a timezone")
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _binary_log_score(y: int, probability: float) -> float:
    if probability < 0.0 or probability > 1.0:
        raise ValueError("probability must be between 0 and 1")
    p = min(1.0 - _EPS, max(_EPS, probability))
    return math.log(p if y == 1 else 1.0 - p)


def _gaussian_log_density(y: float, mean: float, sigma: float) -> float:
    if sigma <= 0.0:
        raise ValueError("sigma must be positive")
    return (
        -0.5 * math.log(2.0 * math.pi)
        - math.log(sigma)
        - ((y - mean) ** 2) / (2.0 * sigma ** 2)
    )


def _prediction_gain(
    target_kind: str,
    baseline_prediction: Mapping[str, Any],
    augmented_prediction: Mapping[str, Any],
    observed_outcome: Any,
) -> tuple[dict[str, float], dict[str, float], float]:
    if target_kind == "binary":
        if observed_outcome not in (0, 1):
            raise ValueError("binary observed_outcome must be 0 or 1")
        bp = _finite(baseline_prediction.get("probability"), "baseline probability")
        ap = _finite(augmented_prediction.get("probability"), "augmented probability")
        if not 0.0 <= bp <= 1.0:
            raise ValueError("baseline probability must be between 0 and 1")
        if not 0.0 <= ap <= 1.0:
            raise ValueError("augmented probability must be between 0 and 1")
        baseline = {"probability": bp}
        augmented = {"probability": ap}
        gain = _binary_log_score(int(observed_outcome), ap) - _binary_log_score(int(observed_outcome), bp)
        return baseline, augmented, gain

    if target_kind == "continuous":
        y = _finite(observed_outcome, "observed_outcome")
        bm = _finite(baseline_prediction.get("mean"), "baseline mean")
        bs = _finite(baseline_prediction.get("sigma"), "baseline sigma")
        am = _finite(augmented_prediction.get("mean"), "augmented mean")
        a_s = _finite(augmented_prediction.get("sigma"), "augmented sigma")
        if bs <= 0.0:
            raise ValueError("baseline sigma must be positive")
        if a_s <= 0.0:
            raise ValueError("augmented sigma must be positive")
        baseline = {"mean": bm, "sigma": bs}
        augmented = {"mean": am, "sigma": a_s}
        gain = _gaussian_log_density(y, am, a_s) - _gaussian_log_density(y, bm, bs)
        return baseline, augmented, gain

    raise ValueError("unsupported target_kind")


def normalize_contribution_observation(body: Mapping[str, Any]) -> dict[str, Any]:
    """Validate one causally comparable paired prediction observation."""
    if not isinstance(body, Mapping):
        raise ValueError("contribution observation must be an object")
    if body.get("execution_authorized") not in (None, False):
        raise ValueError("contribution observation cannot grant execution authority")
    if body.get("production_decision_authorized") not in (None, False):
        raise ValueError("contribution observation cannot grant production authority")

    contributor_id = _sha(body.get("contributor_id"), "contributor_id", 64)
    contributor_kind = _text(body.get("contributor_kind"), "contributor_kind", 64).lower()
    if contributor_kind not in CONTRIBUTOR_KINDS:
        raise ValueError("unsupported contributor_kind")

    source_repo = _text(body.get("source_repo"), "source_repo", 180)
    source_commit = _sha(body.get("source_commit"), "source_commit", 40)
    contract = _sha(body.get("evaluation_contract_hash"), "evaluation_contract_hash", 64)

    raw_conditioning = body.get("conditioning_set")
    if (
        not isinstance(raw_conditioning, Sequence)
        or isinstance(raw_conditioning, (str, bytes))
        or not raw_conditioning
    ):
        raise ValueError("conditioning_set must be a non-empty list")
    conditioning_set = sorted({_text(x, "conditioning_set member", 160) for x in raw_conditioning})
    conditioning_set_hash = _hash(conditioning_set)

    baseline_model_id = _text(body.get("baseline_model_id"), "baseline_model_id", 240)
    augmented_model_id = _text(body.get("augmented_model_id"), "augmented_model_id", 240)

    target_kind = _text(body.get("target_kind"), "target_kind", 32).lower()
    if target_kind not in TARGET_KINDS:
        raise ValueError("unsupported target_kind")
    target_key = _text(body.get("target_key"), "target_key", 160)
    horizon_seconds = _positive_int(body.get("horizon_seconds"), "horizon_seconds", 31_536_000)

    bp_raw = body.get("baseline_prediction")
    ap_raw = body.get("augmented_prediction")
    if not isinstance(bp_raw, Mapping) or not isinstance(ap_raw, Mapping):
        raise ValueError("baseline_prediction and augmented_prediction must be objects")
    baseline_prediction, augmented_prediction, gain = _prediction_gain(
        target_kind,
        bp_raw,
        ap_raw,
        body.get("observed_outcome"),
    )
    if not math.isfinite(gain):
        raise ValueError("information gain must be finite")

    if target_kind == "binary":
        observed_outcome: int | float = int(body.get("observed_outcome"))
    else:
        observed_outcome = _finite(body.get("observed_outcome"), "observed_outcome")

    context_value = body.get("context")
    if not isinstance(context_value, Mapping):
        raise ValueError("context must be an object")
    context = dict(context_value)
    _canonical(context, "context", 32768)
    context_hash = _hash(context)

    episode_id = _text(body.get("episode_id"), "episode_id", 180)
    raw_evidence = body.get("evidence")
    if (
        not isinstance(raw_evidence, Sequence)
        or isinstance(raw_evidence, (str, bytes))
        or not raw_evidence
    ):
        raise ValueError("contribution evidence is required")
    evidence = sorted({_text(x, "evidence item", 700) for x in raw_evidence})
    observed_at = _observed_at(body.get("observed_at"))

    row: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "contributor_id": contributor_id,
        "contributor_kind": contributor_kind,
        "source_repo": source_repo,
        "source_commit": source_commit,
        "evaluation_contract_hash": contract,
        "conditioning_set": conditioning_set,
        "conditioning_set_hash": conditioning_set_hash,
        "baseline_model_id": baseline_model_id,
        "augmented_model_id": augmented_model_id,
        "target_kind": target_kind,
        "target_key": target_key,
        "horizon_seconds": horizon_seconds,
        "baseline_prediction": baseline_prediction,
        "augmented_prediction": augmented_prediction,
        "observed_outcome": observed_outcome,
        "information_gain_nats": gain,
        "context": context,
        "context_hash": context_hash,
        "episode_id": episode_id,
        "evidence": evidence,
        "observed_at": observed_at,
        "estimator": "paired_predictive_log_score_gain",
        "exact_conditional_mutual_information": False,
        "causal_proof": False,
        "execution_authorized": False,
        "production_decision_authorized": False,
    }
    row["observation_id"] = _hash(row)
    return row


def _summary(values: Sequence[float]) -> dict[str, Any]:
    vals = [float(x) for x in values]
    if not vals:
        return {
            "n": 0,
            "mean_information_gain_nats": None,
            "median_information_gain_nats": None,
            "bits_per_observation": None,
            "ci95_low": None,
            "ci95_high": None,
            "positive_fraction": None,
            "classification": "UNMEASURED",
        }

    n = len(vals)
    mean = statistics.fmean(vals)
    median = statistics.median(vals)
    positive = sum(1 for x in vals if x > 0.0) / n

    if n >= 2:
        sd = statistics.stdev(vals)
        se = sd / math.sqrt(n)
        low = mean - (1.96 * se)
        high = mean + (1.96 * se)
    else:
        low = None
        high = None

    if n < _MIN_SUPPORT_N:
        classification = "INSUFFICIENT_EVIDENCE"
    elif low is not None and low > 0.0 and positive >= 0.65:
        classification = "SUPPORTED_INCREMENTAL"
    elif high is not None and high < 0.0 and positive <= 0.35:
        classification = "SUPPORTED_HARMFUL_OR_REDUNDANT"
    else:
        classification = "UNRESOLVED"

    return {
        "n": n,
        "mean_information_gain_nats": mean,
        "median_information_gain_nats": median,
        "bits_per_observation": mean / math.log(2.0),
        "ci95_low": low,
        "ci95_high": high,
        "positive_fraction": positive,
        "classification": classification,
    }


class ContributionLab:
    """Append-only conditional contribution ledger."""

    def __init__(self, base_dir: str | os.PathLike[str]):
        self.base_dir = Path(base_dir)
        self.path = self.base_dir / "research" / "ascendancy_contribution.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.path), timeout=15)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        return con

    @property
    def journal_mode(self) -> str:
        with self._connect() as con:
            return str(con.execute("PRAGMA journal_mode").fetchone()[0]).lower()

    def _init(self) -> None:
        with _LOCK, self._connect() as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS observations (
                    observation_id TEXT PRIMARY KEY,
                    contributor_id TEXT NOT NULL,
                    contributor_kind TEXT NOT NULL,
                    source_repo TEXT NOT NULL,
                    source_commit TEXT NOT NULL,
                    evaluation_contract_hash TEXT NOT NULL,
                    conditioning_set_hash TEXT NOT NULL,
                    baseline_model_id TEXT NOT NULL,
                    augmented_model_id TEXT NOT NULL,
                    target_kind TEXT NOT NULL,
                    target_key TEXT NOT NULL,
                    horizon_seconds INTEGER NOT NULL,
                    context_hash TEXT NOT NULL,
                    episode_id TEXT NOT NULL,
                    information_gain_nats REAL NOT NULL,
                    observed_at TEXT NOT NULL,
                    semantic_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_asc_contribution_contributor
                    ON observations(contributor_id, observed_at);
                CREATE INDEX IF NOT EXISTS idx_asc_contribution_contract
                    ON observations(
                        evaluation_contract_hash,
                        conditioning_set_hash,
                        context_hash,
                        target_key,
                        horizon_seconds
                    );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_asc_contribution_episode
                    ON observations(
                        contributor_id,
                        evaluation_contract_hash,
                        conditioning_set_hash,
                        baseline_model_id,
                        augmented_model_id,
                        target_kind,
                        target_key,
                        horizon_seconds,
                        context_hash,
                        episode_id
                    );
                """
            )

    def close(self) -> None:
        return None

    def record(self, body: Mapping[str, Any]) -> dict[str, Any]:
        row = normalize_contribution_observation(body)
        raw = _canonical(row, "contribution observation")
        now = _utc_now()

        with _LOCK, self._connect() as con:
            existing = con.execute(
                "SELECT semantic_json FROM observations WHERE observation_id=?",
                (row["observation_id"],),
            ).fetchone()
            if existing is not None:
                if str(existing["semantic_json"]) != raw:
                    raise RuntimeError("contribution observation identity integrity failure")
                return {
                    "idempotent": True,
                    "observation": row,
                    "execution_authorized": False,
                    "production_decision_authorized": False,
                }

            collision = con.execute(
                """SELECT observation_id FROM observations
                   WHERE contributor_id=?
                     AND evaluation_contract_hash=?
                     AND conditioning_set_hash=?
                     AND baseline_model_id=?
                     AND augmented_model_id=?
                     AND target_kind=?
                     AND target_key=?
                     AND horizon_seconds=?
                     AND context_hash=?
                     AND episode_id=?""",
                (
                    row["contributor_id"],
                    row["evaluation_contract_hash"],
                    row["conditioning_set_hash"],
                    row["baseline_model_id"],
                    row["augmented_model_id"],
                    row["target_kind"],
                    row["target_key"],
                    row["horizon_seconds"],
                    row["context_hash"],
                    row["episode_id"],
                ),
            ).fetchone()
            if collision is not None:
                raise ValueError(
                    "independent episode already recorded for this contribution comparison"
                )

            con.execute(
                """INSERT INTO observations(
                    observation_id,contributor_id,contributor_kind,source_repo,
                    source_commit,evaluation_contract_hash,conditioning_set_hash,
                    baseline_model_id,augmented_model_id,target_kind,target_key,
                    horizon_seconds,context_hash,episode_id,information_gain_nats,
                    observed_at,semantic_json,recorded_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    row["observation_id"],
                    row["contributor_id"],
                    row["contributor_kind"],
                    row["source_repo"],
                    row["source_commit"],
                    row["evaluation_contract_hash"],
                    row["conditioning_set_hash"],
                    row["baseline_model_id"],
                    row["augmented_model_id"],
                    row["target_kind"],
                    row["target_key"],
                    row["horizon_seconds"],
                    row["context_hash"],
                    row["episode_id"],
                    row["information_gain_nats"],
                    row["observed_at"],
                    raw,
                    now,
                ),
            )

        return {
            "idempotent": False,
            "observation": row,
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict[str, Any]:
        try:
            value = json.loads(row["semantic_json"])
        except (TypeError, json.JSONDecodeError) as ex:
            raise RuntimeError("contribution lab semantic corruption") from ex
        if not isinstance(value, dict):
            raise RuntimeError("contribution lab semantic corruption")
        value["recorded_at"] = str(row["recorded_at"])
        return value

    def snapshot(self, contributor_id: str | None = None) -> dict[str, Any]:
        where = ""
        params: tuple[Any, ...] = ()
        if contributor_id is not None:
            cid = _sha(contributor_id, "contributor_id", 64)
            where = " WHERE contributor_id=?"
            params = (cid,)

        with _LOCK, self._connect() as con:
            rows = con.execute(
                "SELECT * FROM observations" + where + " ORDER BY observed_at,observation_id",
                params,
            ).fetchall()
        observations = [self._decode(row) for row in rows]

        grouped: dict[tuple[Any, ...], dict[str, Any]] = {}
        for row in observations:
            key = (
                row["contributor_id"],
                row["evaluation_contract_hash"],
                row["conditioning_set_hash"],
                row["baseline_model_id"],
                row["augmented_model_id"],
                row["target_kind"],
                row["target_key"],
                row["horizon_seconds"],
                row["context_hash"],
            )
            group = grouped.setdefault(
                key,
                {
                    "contributor_id": row["contributor_id"],
                    "contributor_kind": row["contributor_kind"],
                    "evaluation_contract_hash": row["evaluation_contract_hash"],
                    "conditioning_set": row["conditioning_set"],
                    "conditioning_set_hash": row["conditioning_set_hash"],
                    "baseline_model_id": row["baseline_model_id"],
                    "augmented_model_id": row["augmented_model_id"],
                    "target_kind": row["target_kind"],
                    "target_key": row["target_key"],
                    "horizon_seconds": row["horizon_seconds"],
                    "context": row["context"],
                    "context_hash": row["context_hash"],
                    "values": [],
                    "episode_ids": [],
                },
            )
            group["values"].append(float(row["information_gain_nats"]))
            group["episode_ids"].append(str(row["episode_id"]))

        groups: list[dict[str, Any]] = []
        for group in grouped.values():
            stats = _summary(group["values"])
            groups.append({
                **{k: v for k, v in group.items() if k != "values"},
                **stats,
                "estimator": "paired_predictive_log_score_gain",
                "exact_conditional_mutual_information": False,
                "causal_proof": False,
            })
        groups.sort(
            key=lambda x: (
                x["contributor_id"],
                x["evaluation_contract_hash"],
                x["conditioning_set_hash"],
                x["context_hash"],
                x["target_key"],
                x["horizon_seconds"],
            )
        )

        return {
            "schema_version": LAB_SCHEMA_VERSION,
            "observation_count": len(observations),
            "group_count": len(groups),
            "observations": observations,
            "groups": groups,
            "truth_contract": {
                "estimator": "paired_predictive_log_score_gain",
                "exact_conditional_mutual_information": False,
                "standalone_performance_is_not_incremental_information": True,
                "positive_gain_means_augmented_predictor_scored_realized_outcomes_better": True,
                "contracts_contexts_horizons_and_conditioning_sets_are_never_pooled": True,
                "independent_episode_identity_prevents_duplicate_counting": True,
                "gaussian_density_is_an_assumption_for_continuous_targets": True,
                "contribution_is_not_causal_proof": True,
                "minimum_support_n": _MIN_SUPPORT_N,
            },
            "execution_authorized": False,
            "production_decision_authorized": False,
        }
