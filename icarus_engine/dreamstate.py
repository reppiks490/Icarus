"""DREAMSTATE policy incubator fed by PARALLAX counterfactual evidence.

DREAMSTATE turns repeated, statistically conservative PARALLAX regret patterns into
versioned research hypotheses. Candidates remain shadow-only until every protected
validation gate is explicitly satisfied. Even then the terminal stage is
qualified_shadow; this module has no production or broker authority.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .parallax import ParallaxStore

SCHEMA_VERSION = "icarus-dreamstate-v1"
REQUIRED_GATES = (
    "causal_time",
    "provenance",
    "oos",
    "protected_holdout",
    "multiple_testing",
    "costs_slippage_latency",
    "ablation",
    "calibration",
    "ood_drift",
    "deterministic_replay",
    "independent_verification",
)
_ALLOWED_STAGES = {"proposed", "study", "validated", "qualified_shadow", "rejected", "retired"}
_LOCK = threading.RLock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _text(value: Any, field: str, limit: int, required: bool = True) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    value = value.strip()
    if required and not value:
        raise ValueError(f"{field} is required")
    if len(value) > limit:
        raise ValueError(f"{field} exceeds {limit} characters")
    return value


def _json(value: Any, field: str, max_bytes: int = 131072) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as ex:
        raise ValueError(f"{field} must be finite JSON") from ex
    if len(raw.encode("utf-8")) > max_bytes:
        raise ValueError(f"{field} exceeds {max_bytes} bytes")
    return raw


def _git_sha(value: Any) -> str:
    value = _text(value, "source_commit", 40).lower()
    if len(value) != 40 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("source_commit must be an exact 40-character Git SHA")
    return value


class DreamstateLab:
    """Durable counterfactual-to-hypothesis incubator with protected gates."""

    def __init__(self, base_dir: str | os.PathLike[str], parallax: ParallaxStore | None = None):
        self.base_dir = Path(base_dir)
        self.path = self.base_dir / "research" / "dreamstate.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.parallax = parallax or ParallaxStore(base_dir)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.path), timeout=15)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        return con

    def _init(self) -> None:
        with _LOCK, self._connect() as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS candidates (
                    candidate_id TEXT PRIMARY KEY,
                    family_id TEXT NOT NULL,
                    trial_index INTEGER NOT NULL,
                    asset TEXT NOT NULL,
                    regime TEXT NOT NULL,
                    hypothesis TEXT NOT NULL,
                    mutation_json TEXT NOT NULL,
                    source_commit TEXT NOT NULL,
                    source_signal_json TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    validation_json TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    parent_candidate_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_dreamstate_family ON candidates(family_id, trial_index);
                CREATE INDEX IF NOT EXISTS idx_dreamstate_stage ON candidates(stage, updated_at);
                """
            )

    @staticmethod
    def _mutation(signal: Mapping[str, Any]) -> tuple[dict[str, Any], str] | None:
        label = str(signal.get("branch_label") or "").lower()
        kind = str(signal.get("kind") or "").lower()
        if kind == "opposite":
            return None
        if kind == "delay" and label.startswith("delay_"):
            value = int(label.rsplit("_", 1)[1])
            return (
                {"op": "set_execution_delay_bars", "value": value, "scope": "research_candidate"},
                f"Test whether delaying entry by {value} bars reduces paired counterfactual regret in this regime.",
            )
        if kind == "stop" and label.startswith("stop_"):
            value = float(label.rsplit("_", 1)[1])
            return (
                {"op": "scale_stop_distance", "value": value, "scope": "research_candidate"},
                f"Test a {value:.2f}x stop-distance policy against the immutable baseline.",
            )
        if kind == "size" and label.startswith("size_"):
            value = float(label.rsplit("_", 1)[1])
            return (
                {"op": "scale_position_size", "value": value, "scope": "research_candidate", "risk_authority": False},
                f"Test {value:.2f}x sizing only under independent risk-normalized evaluation.",
            )
        if kind == "skip" or label == "skip":
            return (
                {"op": "learn_abstention_gate", "scope": "research_candidate", "requires_context_clustering": True},
                "Test a causal abstention gate for contexts where skipping repeatedly outperformed the baseline.",
            )
        if kind == "ablation" or label.startswith("without_"):
            subsystem = label.removeprefix("without_")
            return (
                {"op": "review_subsystem_weight", "subsystem": subsystem, "scope": "research_candidate", "automatic_removal": False},
                f"Test whether {subsystem} should be gated or reweighted; never remove it solely from paired ablation evidence.",
            )
        return None

    def refresh(self, min_samples: int = 5) -> dict[str, Any]:
        min_samples = max(3, min(1000, int(min_samples)))
        signals = self.parallax.mutation_signals(min_samples=min_samples)
        created: list[str] = []
        with _LOCK, self._connect() as con:
            for signal in signals:
                proposal = self._mutation(signal)
                if proposal is None:
                    continue
                mutation, hypothesis = proposal
                asset = _text(signal.get("asset"), "asset", 32).upper()
                regime = _text(signal.get("regime"), "regime", 120)
                source_commit = _git_sha(signal.get("source_commit"))
                family_id = "dsf-" + _sha(asset + "|" + regime + "|" + str(mutation.get("op")) + "|" + str(mutation.get("subsystem", "")))[:20]
                signal_json = _json(dict(signal), "source_signal", 32768)
                mutation_json = _json(mutation, "mutation", 32768)
                candidate_id = "ds-" + _sha(family_id + "|" + signal_json + "|" + mutation_json)[:24]
                if con.execute("SELECT 1 FROM candidates WHERE candidate_id=?", (candidate_id,)).fetchone():
                    continue
                trial_index = 1 + int(con.execute("SELECT COUNT(*) FROM candidates WHERE family_id=?", (family_id,)).fetchone()[0])
                validation = {gate: None for gate in REQUIRED_GATES}
                now = _utc_now()
                con.execute(
                    """INSERT INTO candidates(candidate_id,family_id,trial_index,asset,regime,hypothesis,mutation_json,
                       source_commit,source_signal_json,stage,validation_json,evidence_json,parent_candidate_id,created_at,updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        candidate_id, family_id, trial_index, asset, regime, hypothesis, mutation_json,
                        source_commit, signal_json, "proposed", _json(validation, "validation"),
                        "[]", None, now, now,
                    ),
                )
                created.append(candidate_id)
        out = self.snapshot()
        out["refresh"] = {"created": created, "signal_count": len(signals), "min_samples": min_samples}
        return out

    def evaluate(self, candidate_id: str, payload: Mapping[str, Any]) -> dict[str, Any]:
        candidate_id = _text(candidate_id, "candidate_id", 96)
        if not isinstance(payload, Mapping):
            raise ValueError("evaluation must be an object")
        updates = payload.get("validation", {})
        if not isinstance(updates, Mapping) or not updates:
            raise ValueError("validation must be a non-empty object")
        unknown = set(updates) - set(REQUIRED_GATES)
        if unknown:
            raise ValueError("unsupported validation gates: " + ", ".join(sorted(unknown)))
        evidence = payload.get("evidence", [])
        if isinstance(evidence, str):
            evidence = [evidence]
        if not isinstance(evidence, list) or len(evidence) > 64:
            raise ValueError("evidence must be a list with at most 64 items")
        evidence = [_text(x, "evidence item", 700) for x in evidence]

        with _LOCK, self._connect() as con:
            row = con.execute("SELECT * FROM candidates WHERE candidate_id=?", (candidate_id,)).fetchone()
            if not row:
                raise ValueError("unknown DREAMSTATE candidate")
            if row["stage"] in {"rejected", "retired"}:
                raise ValueError("terminal DREAMSTATE candidate cannot be requalified")
            validation = json.loads(row["validation_json"])
            for gate, value in updates.items():
                if value is not None and type(value) is not bool:
                    raise ValueError(f"validation.{gate} must be boolean or null")
                previous = validation.get(gate)
                if previous is False and value is not False:
                    raise ValueError(f"failed gate {gate} is immutable; create a new candidate revision")
                validation[gate] = value
            prior_evidence = json.loads(row["evidence_json"])
            merged_evidence = list(dict.fromkeys((prior_evidence + evidence)[-128:]))

            if any(value is False for value in validation.values()):
                stage = "rejected"
            elif all(value is True for value in validation.values()):
                stage = "qualified_shadow"
            elif all(validation.get(g) is True for g in ("causal_time", "provenance", "oos", "protected_holdout")):
                stage = "validated"
            else:
                stage = "study"

            con.execute(
                "UPDATE candidates SET stage=?,validation_json=?,evidence_json=?,updated_at=? WHERE candidate_id=?",
                (stage, _json(validation, "validation"), _json(merged_evidence, "evidence"), _utc_now(), candidate_id),
            )
        return self.candidate(candidate_id)

    def retire(self, candidate_id: str, reason: str) -> dict[str, Any]:
        candidate_id = _text(candidate_id, "candidate_id", 96)
        reason = _text(reason, "reason", 700)
        with _LOCK, self._connect() as con:
            row = con.execute("SELECT * FROM candidates WHERE candidate_id=?", (candidate_id,)).fetchone()
            if not row:
                raise ValueError("unknown DREAMSTATE candidate")
            evidence = json.loads(row["evidence_json"])
            evidence = list(dict.fromkeys((evidence + ["retired: " + reason])[-128:]))
            con.execute(
                "UPDATE candidates SET stage='retired',evidence_json=?,updated_at=? WHERE candidate_id=?",
                (_json(evidence, "evidence"), _utc_now(), candidate_id),
            )
        return self.candidate(candidate_id)

    def candidate(self, candidate_id: str) -> dict[str, Any]:
        with _LOCK, self._connect() as con:
            row = con.execute("SELECT * FROM candidates WHERE candidate_id=?", (candidate_id,)).fetchone()
        if not row:
            raise ValueError("unknown DREAMSTATE candidate")
        return {
            "candidate_id": row["candidate_id"], "family_id": row["family_id"], "trial_index": row["trial_index"],
            "asset": row["asset"], "regime": row["regime"], "hypothesis": row["hypothesis"],
            "mutation": json.loads(row["mutation_json"]), "source_commit": row["source_commit"],
            "source_signal": json.loads(row["source_signal_json"]), "stage": row["stage"],
            "validation": json.loads(row["validation_json"]), "evidence": json.loads(row["evidence_json"]),
            "parent_candidate_id": row["parent_candidate_id"], "created_at": row["created_at"], "updated_at": row["updated_at"],
            "execution_authorized": False, "production_decision_authorized": False,
        }

    def snapshot(self, limit: int = 200) -> dict[str, Any]:
        with _LOCK, self._connect() as con:
            rows = con.execute("SELECT candidate_id FROM candidates ORDER BY updated_at DESC LIMIT ?", (max(1, min(1000, int(limit))),)).fetchall()
            stage_rows = con.execute("SELECT stage,COUNT(*) AS n FROM candidates GROUP BY stage").fetchall()
        candidates = [self.candidate(row["candidate_id"]) for row in rows]
        stages = {stage: 0 for stage in sorted(_ALLOWED_STAGES)}
        stages.update({row["stage"]: row["n"] for row in stage_rows})
        return {
            "schema_version": SCHEMA_VERSION,
            "stages": stages,
            "candidates": candidates,
            "required_gates": list(REQUIRED_GATES),
            "authority": {
                "maximum_stage": "qualified_shadow",
                "automatic_production_promotion": False,
                "execution_authorized": False,
                "production_decision_authorized": False,
            },
            "truth_contract": {
                "counterfactual_signal_is_hypothesis_generation_only": True,
                "multiple_testing_gate_required": True,
                "independent_verification_required": True,
                "failed_gate_requires_new_candidate_revision": True,
            },
        }
