"""ASCENDANCY mechanism extraction from paired research experiments.

This module decomposes candidate performance through explicitly paired
perturbations. It can identify direct-looking, interaction-dependent, harmful,
or unresolved contributions, but it never claims structural causality solely
from ablation statistics and never grants trading authority.
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

SCHEMA_VERSION = "icarus-ascendancy-mechanism-experiment-v1"
LAB_SCHEMA_VERSION = "icarus-ascendancy-mechanism-lab-v1"

KINDS = {
    "ablation",
    "interaction_ablation",
    "timing_ablation",
    "cost_perturbation",
    "latency_perturbation",
    "regime_isolation",
    "representation_swap",
}
DIRECTIONS = {"max", "min"}
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA64 = re.compile(r"^[0-9a-f]{64}$")
_LOCK = threading.RLock()
_MIN_SUPPORT_N = 5


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


def normalize_experiment(body: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and canonicalize one paired mechanism experiment."""
    if not isinstance(body, Mapping):
        raise ValueError("mechanism experiment must be an object")
    if body.get("execution_authorized") not in (None, False):
        raise ValueError("mechanism experiment cannot grant execution authority")
    if body.get("production_decision_authorized") not in (None, False):
        raise ValueError("mechanism experiment cannot grant production authority")

    candidate_id = _sha(body.get("candidate_id"), "candidate_id", 64)
    source_repo = _text(body.get("source_repo"), "source_repo", 180)
    source_commit = _sha(body.get("source_commit"), "source_commit", 40)
    contract = _sha(body.get("evaluation_contract_hash"), "evaluation_contract_hash", 64)
    mechanism_key = _text(body.get("mechanism_key"), "mechanism_key", 180)
    kind = _text(body.get("experiment_kind"), "experiment_kind", 64).lower()
    if kind not in KINDS:
        raise ValueError("unsupported experiment_kind")
    target_metric = _text(body.get("target_metric"), "target_metric", 120)
    direction = _text(body.get("direction"), "direction", 8).lower()
    if direction not in DIRECTIONS:
        raise ValueError("direction must be max or min")

    baseline = _finite(body.get("baseline_value"), "baseline_value")
    perturbed = _finite(body.get("perturbed_value"), "perturbed_value")
    effect = baseline - perturbed if direction == "max" else perturbed - baseline

    context_value = body.get("context")
    if not isinstance(context_value, Mapping):
        raise ValueError("context must be an object")
    context = dict(context_value)
    _canonical(context, "context", 32768)
    context_hash = _hash(context)

    episode_id = _text(body.get("episode_id"), "episode_id", 180)
    raw_related = body.get("related_mechanisms") or []
    if not isinstance(raw_related, Sequence) or isinstance(raw_related, (str, bytes)):
        raise ValueError("related_mechanisms must be a list")
    related = sorted({_text(x, "related mechanism", 180) for x in raw_related})

    raw_evidence = body.get("evidence")
    if not isinstance(raw_evidence, Sequence) or isinstance(raw_evidence, (str, bytes)) or not raw_evidence:
        raise ValueError("mechanism experiment evidence is required")
    evidence = sorted({_text(x, "evidence item", 700) for x in raw_evidence})
    if len(evidence) > 64:
        raise ValueError("too many evidence items")

    observed_at = _observed_at(body.get("observed_at"))

    row: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "candidate_id": candidate_id,
        "source_repo": source_repo,
        "source_commit": source_commit,
        "evaluation_contract_hash": contract,
        "mechanism_key": mechanism_key,
        "experiment_kind": kind,
        "target_metric": target_metric,
        "direction": direction,
        "baseline_value": baseline,
        "perturbed_value": perturbed,
        "effect": effect,
        "context": context,
        "context_hash": context_hash,
        "episode_id": episode_id,
        "related_mechanisms": related,
        "evidence": evidence,
        "observed_at": observed_at,
        "causal_proof": False,
        "execution_authorized": False,
        "production_decision_authorized": False,
    }
    row["experiment_id"] = _hash(row)
    return row


def _summary(values: Sequence[float]) -> dict[str, Any]:
    vals = [float(v) for v in values]
    if not vals:
        return {
            "n": 0,
            "mean_effect": None,
            "median_effect": None,
            "ci95_low": None,
            "ci95_high": None,
            "sign_agreement": None,
            "negative_sign_agreement": None,
            "status": "UNMEASURED",
        }
    n = len(vals)
    mean = statistics.fmean(vals)
    median = statistics.median(vals)
    positive = sum(1 for v in vals if v > 0.0) / n
    negative = sum(1 for v in vals if v < 0.0) / n

    if n >= 2:
        sd = statistics.stdev(vals)
        se = sd / math.sqrt(n)
        low = mean - (1.96 * se)
        high = mean + (1.96 * se)
    else:
        low = None
        high = None

    if n < _MIN_SUPPORT_N:
        status = "INSUFFICIENT_EVIDENCE"
    elif low is not None and low > 0.0 and positive >= 0.8:
        status = "SUPPORTED_POSITIVE"
    elif high is not None and high < 0.0 and negative >= 0.8:
        status = "SUPPORTED_NEGATIVE"
    else:
        status = "UNRESOLVED"

    return {
        "n": n,
        "mean_effect": mean,
        "median_effect": median,
        "ci95_low": low,
        "ci95_high": high,
        "sign_agreement": positive,
        "negative_sign_agreement": negative,
        "status": status,
    }


class MechanismLab:
    """Append-only research store for paired mechanism experiments."""

    def __init__(self, base_dir: str | os.PathLike[str]):
        self.base_dir = Path(base_dir)
        self.path = self.base_dir / "research" / "ascendancy_mechanisms.sqlite3"
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
                CREATE TABLE IF NOT EXISTS experiments (
                    experiment_id TEXT PRIMARY KEY,
                    candidate_id TEXT NOT NULL,
                    source_repo TEXT NOT NULL,
                    source_commit TEXT NOT NULL,
                    evaluation_contract_hash TEXT NOT NULL,
                    mechanism_key TEXT NOT NULL,
                    experiment_kind TEXT NOT NULL,
                    target_metric TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    context_hash TEXT NOT NULL,
                    episode_id TEXT NOT NULL,
                    effect REAL NOT NULL,
                    semantic_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_asc_mech_candidate
                    ON experiments(candidate_id, mechanism_key, recorded_at);
                CREATE INDEX IF NOT EXISTS idx_asc_mech_contract
                    ON experiments(evaluation_contract_hash, context_hash, mechanism_key);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_asc_mech_independent_episode
                    ON experiments(
                        candidate_id,
                        evaluation_contract_hash,
                        context_hash,
                        mechanism_key,
                        experiment_kind,
                        target_metric,
                        direction,
                        episode_id
                    );
                """
            )

    def close(self) -> None:
        return None

    def record(self, body: Mapping[str, Any]) -> dict[str, Any]:
        row = normalize_experiment(body)
        raw = _canonical(row, "mechanism experiment")
        now = _utc_now()

        with _LOCK, self._connect() as con:
            existing = con.execute(
                "SELECT semantic_json FROM experiments WHERE experiment_id=?",
                (row["experiment_id"],),
            ).fetchone()
            if existing is not None:
                if str(existing["semantic_json"]) != raw:
                    raise RuntimeError("mechanism experiment identity integrity failure")
                return {
                    "idempotent": True,
                    "experiment": row,
                    "execution_authorized": False,
                    "production_decision_authorized": False,
                }

            episode_collision = con.execute(
                """SELECT experiment_id,semantic_json FROM experiments
                   WHERE candidate_id=?
                     AND evaluation_contract_hash=?
                     AND context_hash=?
                     AND mechanism_key=?
                     AND experiment_kind=?
                     AND target_metric=?
                     AND direction=?
                     AND episode_id=?""",
                (
                    row["candidate_id"],
                    row["evaluation_contract_hash"],
                    row["context_hash"],
                    row["mechanism_key"],
                    row["experiment_kind"],
                    row["target_metric"],
                    row["direction"],
                    row["episode_id"],
                ),
            ).fetchone()
            if episode_collision is not None:
                raise ValueError(
                    "independent episode already recorded for this mechanism/contract/context group"
                )

            con.execute(
                """INSERT INTO experiments(
                    experiment_id,candidate_id,source_repo,source_commit,
                    evaluation_contract_hash,mechanism_key,experiment_kind,
                    target_metric,direction,context_hash,episode_id,effect,
                    semantic_json,recorded_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    row["experiment_id"],
                    row["candidate_id"],
                    row["source_repo"],
                    row["source_commit"],
                    row["evaluation_contract_hash"],
                    row["mechanism_key"],
                    row["experiment_kind"],
                    row["target_metric"],
                    row["direction"],
                    row["context_hash"],
                    row["episode_id"],
                    row["effect"],
                    raw,
                    now,
                ),
            )

        return {
            "idempotent": False,
            "experiment": row,
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict[str, Any]:
        try:
            value = json.loads(row["semantic_json"])
        except (TypeError, json.JSONDecodeError) as ex:
            raise RuntimeError("mechanism lab semantic corruption") from ex
        if not isinstance(value, dict):
            raise RuntimeError("mechanism lab semantic corruption")
        value["recorded_at"] = str(row["recorded_at"])
        return value

    def snapshot(self, candidate_id: str | None = None) -> dict[str, Any]:
        params: tuple[Any, ...] = ()
        where = ""
        if candidate_id is not None:
            cid = _sha(candidate_id, "candidate_id", 64)
            where = " WHERE candidate_id=?"
            params = (cid,)

        with _LOCK, self._connect() as con:
            rows = con.execute(
                "SELECT * FROM experiments" + where + " ORDER BY observed_at,experiment_id",
                params,
            ).fetchall()
        experiments = [self._decode(row) for row in rows]

        grouped: dict[
            tuple[str, str, str, str, str, str, str],
            dict[str, Any],
        ] = {}
        for row in experiments:
            key = (
                row["candidate_id"],
                row["mechanism_key"],
                row["experiment_kind"],
                row["evaluation_contract_hash"],
                row["context_hash"],
                row["target_metric"],
                row["direction"],
            )
            group = grouped.setdefault(
                key,
                {
                    "candidate_id": row["candidate_id"],
                    "mechanism_key": row["mechanism_key"],
                    "experiment_kind": row["experiment_kind"],
                    "evaluation_contract_hash": row["evaluation_contract_hash"],
                    "context_hash": row["context_hash"],
                    "context": row["context"],
                    "target_metric": row["target_metric"],
                    "direction": row["direction"],
                    "effects": [],
                    "episode_ids": [],
                    "related_mechanisms": set(),
                },
            )
            group["effects"].append(float(row["effect"]))
            group["episode_ids"].append(str(row["episode_id"]))
            group["related_mechanisms"].update(row.get("related_mechanisms") or [])

        group_rows: list[dict[str, Any]] = []
        for group in grouped.values():
            stats = _summary(group["effects"])
            group_rows.append({
                **{
                    k: v
                    for k, v in group.items()
                    if k not in {"effects", "related_mechanisms"}
                },
                "related_mechanisms": sorted(group["related_mechanisms"]),
                **stats,
                "causal_proof": False,
            })
        group_rows.sort(
            key=lambda x: (
                x["candidate_id"],
                x["mechanism_key"],
                x["evaluation_contract_hash"],
                x["context_hash"],
                x["experiment_kind"],
                x["target_metric"],
            )
        )

        by_mechanism: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        for group in group_rows:
            by_mechanism[(group["candidate_id"], group["mechanism_key"])].append(group)

        mechanisms: list[dict[str, Any]] = []
        for (cid, mechanism_key), groups in sorted(by_mechanism.items()):
            direct_supported = any(
                g["experiment_kind"] == "ablation" and g["status"] == "SUPPORTED_POSITIVE"
                for g in groups
            )
            interaction_supported = any(
                g["experiment_kind"] == "interaction_ablation"
                and g["status"] == "SUPPORTED_POSITIVE"
                for g in groups
            )
            direct_harmful = any(
                g["experiment_kind"] == "ablation" and g["status"] == "SUPPORTED_NEGATIVE"
                for g in groups
            )

            if direct_supported:
                classification = "DIRECT_CONTRIBUTOR"
            elif interaction_supported:
                classification = "INTERACTION_DEPENDENT"
            elif direct_harmful:
                classification = "HARMFUL_LOOKING"
            else:
                classification = "UNRESOLVED"

            related = sorted({
                name
                for g in groups
                for name in g.get("related_mechanisms", [])
            })
            mechanisms.append({
                "candidate_id": cid,
                "mechanism_key": mechanism_key,
                "classification": classification,
                "related_mechanisms": related,
                "group_count": len(groups),
                "groups": groups,
                "causal_proof": False,
            })

        return {
            "schema_version": LAB_SCHEMA_VERSION,
            "experiment_count": len(experiments),
            "mechanism_count": len(mechanisms),
            "experiments": experiments,
            "mechanisms": mechanisms,
            "truth_contract": {
                "paired_effect_definition": (
                    "positive effect means baseline/full candidate performed better than the paired perturbation "
                    "after respecting the target metric direction"
                ),
                "minimum_support_n": _MIN_SUPPORT_N,
                "ci95_is_normal_approximation": True,
                "mechanism_attribution_is_not_causal_proof": True,
                "contracts_and_contexts_are_never_pooled": True,
                "independent_episode_identity_prevents_duplicate_counting": True,
                "interaction_support_can_be_reported_without_claiming_direct_effect": True,
            },
            "execution_authorized": False,
            "production_decision_authorized": False,
        }
