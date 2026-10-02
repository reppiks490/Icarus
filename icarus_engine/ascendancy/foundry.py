"""ASCENDANCY Candidate Foundry.

The Foundry is the research intake boundary for hypotheses originating from
native ICARUS failures, foreign lenses, public research, generated mathematics,
architecture mutations, or human proposals.  Every candidate is falsifiable,
resource-bounded, provenance-bound, and research-only.

The Foundry deliberately cannot grant QUALIFIED_SHADOW.  That authority remains
with ICARUS protected candidate qualification.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "icarus-ascendancy-candidate-v1"
FOUNDRY_SCHEMA_VERSION = "icarus-ascendancy-foundry-v1"

ORIGINS = {
    "native_residual",
    "native_subsystem",
    "foreign_lens",
    "public_research",
    "generated_math",
    "architecture_mutation",
    "dreamstate",
    "human",
    "hybrid",
}
EVIDENCE_CLASSES = {"observed", "derived", "reconstructed", "inferred", "unavailable"}
STAGES = (
    "PROPOSED",
    "INCUBATING",
    "TESTING",
    "VALIDATED_RESEARCH",
    "QUALIFIED_SHADOW",
    "REJECTED",
    "RETIRED",
)
_PROGRESS = {
    "PROPOSED": 0,
    "INCUBATING": 1,
    "TESTING": 2,
    "VALIDATED_RESEARCH": 3,
}
_TERMINAL = {"QUALIFIED_SHADOW", "REJECTED", "RETIRED"}
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA64 = re.compile(r"^[0-9a-f]{64}$")
_LOCK = threading.RLock()


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


def _json(value: Any, name: str, max_bytes: int = 131072) -> Any:
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as ex:
        raise ValueError(f"{name} must be finite JSON") from ex
    if len(raw.encode("utf-8")) > max_bytes:
        raise ValueError(f"{name} exceeds {max_bytes} bytes")
    return value


def _canonical(value: Any, name: str = "value") -> str:
    _json(value, name)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value, "hash input").encode("utf-8")).hexdigest()


def _git_sha(value: Any) -> str:
    out = _text(value, "source_commit", 40).lower()
    if not _SHA40.fullmatch(out):
        raise ValueError("source_commit must be an exact 40-character Git SHA")
    return out


def _hash_id(value: Any, name: str) -> str:
    out = _text(value, name, 64).lower()
    if not _SHA64.fullmatch(out):
        raise ValueError(f"{name} must be a 64-character hash")
    return out


def _positive_int(value: Any, name: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if value < 1 or value > maximum:
        raise ValueError(f"{name} must be between 1 and {maximum}")
    return value


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be finite")
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"{name} must be finite")
    return out


def _normalize_evaluation_contract(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("evaluation_contract must be an object")
    raw_objectives = value.get("objectives")
    if not isinstance(raw_objectives, Sequence) or isinstance(raw_objectives, (str, bytes)) or not raw_objectives:
        raise ValueError("evaluation_contract requires objectives")
    objectives: list[dict[str, str]] = []
    names: set[str] = set()
    for raw in raw_objectives:
        if not isinstance(raw, Mapping):
            raise ValueError("evaluation objective must be an object")
        name = _text(raw.get("name"), "objective name", 96)
        direction = _text(raw.get("direction"), "objective direction", 8).lower()
        if direction not in {"max", "min"}:
            raise ValueError("objective direction must be max or min")
        if name in names:
            raise ValueError("duplicate evaluation objective")
        names.add(name)
        objectives.append({"name": name, "direction": direction})
    objectives.sort(key=lambda row: row["name"])

    raw_keys = value.get("descriptor_keys") or []
    if not isinstance(raw_keys, Sequence) or isinstance(raw_keys, (str, bytes)):
        raise ValueError("descriptor_keys must be a list")
    descriptor_keys = sorted({_text(x, "descriptor key", 96) for x in raw_keys})
    if value.get("protected_holdout_required") is not True:
        raise ValueError("evaluation_contract must require a protected holdout")

    contract = {
        "objectives": objectives,
        "descriptor_keys": descriptor_keys,
        "protected_holdout_required": True,
    }
    contract["contract_hash"] = _hash(contract)
    return contract


def _normalize_budget(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("resource_budget must be an object")
    max_evaluations = _positive_int(value.get("max_evaluations"), "max_evaluations", 10_000_000)
    max_wall_seconds = _positive_int(value.get("max_wall_seconds"), "max_wall_seconds", 31_536_000)
    max_cost_units = _finite(value.get("max_cost_units"), "max_cost_units")
    if max_cost_units < 0.0 or max_cost_units > 1_000_000_000.0:
        raise ValueError("max_cost_units is outside the supported range")
    return {
        "max_evaluations": max_evaluations,
        "max_wall_seconds": max_wall_seconds,
        "max_cost_units": max_cost_units,
    }


def _normalize_observation(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("required observation must be an object")
    name = _text(value.get("name"), "observation name", 160)
    if value.get("evidence_class") is None:
        raise ValueError("required observation evidence_class is required")
    evidence_class = _text(value.get("evidence_class"), "evidence_class", 40).lower()
    if evidence_class not in EVIDENCE_CLASSES:
        raise ValueError("unsupported evidence_class")
    row: dict[str, Any] = {
        "name": name,
        "evidence_class": evidence_class,
        "usable_for_confirmation": evidence_class != "unavailable",
    }
    if value.get("provider") is not None:
        row["provider"] = _text(value.get("provider"), "observation provider", 160)
    if value.get("details") is not None:
        row["details"] = _json(
            dict(value["details"]) if isinstance(value["details"], Mapping) else value["details"],
            "observation details",
            32768,
        )
    return row


def normalize_candidate(body: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(body, Mapping):
        raise ValueError("candidate must be an object")
    if body.get("execution_authorized") not in (None, False):
        raise ValueError("candidate authority escalation is forbidden")
    if body.get("production_decision_authorized") not in (None, False):
        raise ValueError("candidate authority escalation is forbidden")
    if body.get("broker_authority") not in (None, False):
        raise ValueError("candidate authority escalation is forbidden")

    origin = _text(body.get("origin"), "origin", 64).lower()
    if origin not in ORIGINS:
        raise ValueError("unsupported candidate origin")

    source_repo = _text(body.get("source_repo"), "source_repo", 180)
    source_commit = _git_sha(body.get("source_commit"))
    title = _text(body.get("title"), "title", 240)
    hypothesis = _text(body.get("hypothesis"), "hypothesis", 4000)

    mechanism = body.get("mechanism")
    if not isinstance(mechanism, Mapping) or not mechanism:
        raise ValueError("mechanism must be a non-empty object")
    mechanism = dict(mechanism)
    _json(mechanism, "mechanism", 65536)

    expected_advantage = body.get("expected_advantage")
    if not isinstance(expected_advantage, Mapping) or not expected_advantage:
        raise ValueError("expected_advantage must be a non-empty object")
    expected_advantage = dict(expected_advantage)
    _json(expected_advantage, "expected_advantage", 32768)

    raw_obs = body.get("required_observations")
    if not isinstance(raw_obs, Sequence) or isinstance(raw_obs, (str, bytes)) or not raw_obs:
        raise ValueError("candidate requires required_observations")
    observations = [_normalize_observation(x) for x in raw_obs]
    names = [row["name"] for row in observations]
    if len(names) != len(set(names)):
        raise ValueError("duplicate required observation")
    observations.sort(key=lambda row: row["name"])

    raw_falsifiers = body.get("falsifiers")
    if not isinstance(raw_falsifiers, Sequence) or isinstance(raw_falsifiers, (str, bytes)) or not raw_falsifiers:
        raise ValueError("candidate requires at least one falsifier")
    falsifiers = sorted({_text(x, "falsifier", 1000) for x in raw_falsifiers})

    raw_parent_candidates = body.get("parent_candidate_ids") or []
    if not isinstance(raw_parent_candidates, Sequence) or isinstance(raw_parent_candidates, (str, bytes)):
        raise ValueError("parent_candidate_ids must be a list")
    parent_candidate_ids = sorted({_hash_id(x, "parent_candidate_id") for x in raw_parent_candidates})

    raw_parent_genomes = body.get("parent_genome_ids") or []
    if not isinstance(raw_parent_genomes, Sequence) or isinstance(raw_parent_genomes, (str, bytes)):
        raise ValueError("parent_genome_ids must be a list")
    parent_genome_ids = sorted({_hash_id(x, "parent_genome_id") for x in raw_parent_genomes})

    evaluation_contract = _normalize_evaluation_contract(body.get("evaluation_contract"))
    resource_budget = _normalize_budget(body.get("resource_budget"))

    metadata_value = body.get("metadata") or {}
    if not isinstance(metadata_value, Mapping):
        raise ValueError("metadata must be an object")
    metadata = dict(metadata_value)
    _json(metadata, "metadata", 65536)

    semantic: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "origin": origin,
        "source_repo": source_repo,
        "source_commit": source_commit,
        "title": title,
        "hypothesis": hypothesis,
        "mechanism": mechanism,
        "expected_advantage": expected_advantage,
        "required_observations": observations,
        "falsifiers": falsifiers,
        "parent_candidate_ids": parent_candidate_ids,
        "parent_genome_ids": parent_genome_ids,
        "evaluation_contract": evaluation_contract,
        "resource_budget": resource_budget,
        "metadata": metadata,
        "stage": "PROPOSED",
        "execution_authorized": False,
        "production_decision_authorized": False,
        "broker_authority": False,
    }
    semantic["candidate_id"] = _hash(semantic)
    return semantic


class CandidateFoundry:
    """Durable, research-only candidate intake and lifecycle store."""

    def __init__(self, base_dir: str | os.PathLike[str]):
        self.base_dir = Path(base_dir)
        self.path = self.base_dir / "research" / "ascendancy_candidates.sqlite3"
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
                CREATE TABLE IF NOT EXISTS candidates (
                    candidate_id TEXT PRIMARY KEY,
                    origin TEXT NOT NULL,
                    source_repo TEXT NOT NULL,
                    source_commit TEXT NOT NULL,
                    evaluation_contract_hash TEXT NOT NULL,
                    semantic_json TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS lineage (
                    parent_candidate_id TEXT NOT NULL,
                    child_candidate_id TEXT NOT NULL,
                    PRIMARY KEY(parent_candidate_id, child_candidate_id)
                );
                CREATE INDEX IF NOT EXISTS idx_asc_foundry_child
                    ON lineage(child_candidate_id);

                CREATE TABLE IF NOT EXISTS lifecycle_events (
                    event_id TEXT PRIMARY KEY,
                    candidate_id TEXT NOT NULL,
                    from_stage TEXT,
                    to_stage TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_asc_foundry_events
                    ON lifecycle_events(candidate_id, recorded_at);
                """
            )

    def close(self) -> None:
        return None

    @staticmethod
    def _decode(row: sqlite3.Row) -> dict[str, Any]:
        try:
            semantic = json.loads(row["semantic_json"])
        except (TypeError, json.JSONDecodeError) as ex:
            raise RuntimeError("candidate foundry semantic corruption") from ex
        if not isinstance(semantic, dict):
            raise RuntimeError("candidate foundry semantic corruption")
        out = dict(semantic)
        out["stage"] = str(row["stage"])
        out["registered_at"] = str(row["created_at"])
        out["updated_at"] = str(row["updated_at"])
        return out

    def _row(self, candidate_id: str) -> sqlite3.Row:
        cid = _hash_id(candidate_id, "candidate_id")
        with self._connect() as con:
            row = con.execute(
                "SELECT * FROM candidates WHERE candidate_id=?",
                (cid,),
            ).fetchone()
        if row is None:
            raise ValueError("unknown candidate_id")
        return row

    def register(self, body: Mapping[str, Any]) -> dict[str, Any]:
        candidate = normalize_candidate(body)
        cid = candidate["candidate_id"]
        raw = _canonical(candidate, "candidate")
        parents = candidate["parent_candidate_ids"]
        now = _utc_now()

        with _LOCK, self._connect() as con:
            row = con.execute(
                "SELECT * FROM candidates WHERE candidate_id=?",
                (cid,),
            ).fetchone()
            if row is not None:
                if str(row["semantic_json"]) != raw:
                    raise RuntimeError("candidate identity integrity failure")
                existing = {
                    str(x["parent_candidate_id"])
                    for x in con.execute(
                        "SELECT parent_candidate_id FROM lineage WHERE child_candidate_id=?",
                        (cid,),
                    ).fetchall()
                }
                if existing != set(parents):
                    raise RuntimeError("candidate lineage integrity failure")
                return {
                    "idempotent": True,
                    "candidate": self._decode(row),
                    "execution_authorized": False,
                    "production_decision_authorized": False,
                }

            con.execute(
                """INSERT INTO candidates(
                    candidate_id,origin,source_repo,source_commit,
                    evaluation_contract_hash,semantic_json,stage,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?)""",
                (
                    cid,
                    candidate["origin"],
                    candidate["source_repo"],
                    candidate["source_commit"],
                    candidate["evaluation_contract"]["contract_hash"],
                    raw,
                    "PROPOSED",
                    now,
                    now,
                ),
            )
            for parent in parents:
                con.execute(
                    "INSERT INTO lineage(parent_candidate_id,child_candidate_id) VALUES(?,?)",
                    (parent, cid),
                )
            event = {
                "candidate_id": cid,
                "from_stage": None,
                "to_stage": "PROPOSED",
                "reason": "registered",
            }
            con.execute(
                """INSERT INTO lifecycle_events(
                    event_id,candidate_id,from_stage,to_stage,reason,recorded_at
                ) VALUES(?,?,?,?,?,?)""",
                (_hash(event), cid, None, "PROPOSED", "registered", now),
            )
            row = con.execute(
                "SELECT * FROM candidates WHERE candidate_id=?",
                (cid,),
            ).fetchone()

        if row is None:
            raise RuntimeError("candidate registration did not persist")
        return {
            "idempotent": False,
            "candidate": self._decode(row),
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    def advance(self, candidate_id: str, stage: str, reason: str) -> dict[str, Any]:
        cid = _hash_id(candidate_id, "candidate_id")
        target = _text(stage, "stage", 64).upper()
        reason = _text(reason, "reason", 2000)
        if target not in STAGES:
            raise ValueError("unsupported candidate stage")
        if target in _TERMINAL:
            raise ValueError(
                "terminal candidate stages are reserved for explicit reject/retire or protected qualification authority"
            )

        now = _utc_now()
        with _LOCK, self._connect() as con:
            row = con.execute(
                "SELECT * FROM candidates WHERE candidate_id=?",
                (cid,),
            ).fetchone()
            if row is None:
                raise ValueError("unknown candidate_id")
            current = str(row["stage"]).upper()
            if current in _TERMINAL:
                raise ValueError("terminal candidate cannot advance")
            if target == current:
                return {
                    **self._decode(row),
                    "idempotent": True,
                }
            if target not in _PROGRESS or current not in _PROGRESS:
                raise ValueError("unsupported candidate progression")
            if _PROGRESS[target] <= _PROGRESS[current]:
                raise ValueError("backward candidate stage transition is forbidden")
            if _PROGRESS[target] != _PROGRESS[current] + 1:
                raise ValueError("candidate stage progression cannot skip validation stages")

            con.execute(
                "UPDATE candidates SET stage=?,updated_at=? WHERE candidate_id=?",
                (target, now, cid),
            )
            event = {
                "candidate_id": cid,
                "from_stage": current,
                "to_stage": target,
                "reason": reason,
            }
            con.execute(
                """INSERT INTO lifecycle_events(
                    event_id,candidate_id,from_stage,to_stage,reason,recorded_at
                ) VALUES(?,?,?,?,?,?)""",
                (_hash(event), cid, current, target, reason, now),
            )
            row = con.execute(
                "SELECT * FROM candidates WHERE candidate_id=?",
                (cid,),
            ).fetchone()
        if row is None:
            raise RuntimeError("candidate stage update did not persist")
        return self._decode(row)

    def _terminal(self, candidate_id: str, stage: str, reason: str) -> dict[str, Any]:
        cid = _hash_id(candidate_id, "candidate_id")
        reason = _text(reason, "reason", 2000)
        if stage not in {"REJECTED", "RETIRED"}:
            raise ValueError("unsupported terminal stage")
        now = _utc_now()
        with _LOCK, self._connect() as con:
            row = con.execute(
                "SELECT * FROM candidates WHERE candidate_id=?",
                (cid,),
            ).fetchone()
            if row is None:
                raise ValueError("unknown candidate_id")
            current = str(row["stage"]).upper()
            if current == stage:
                return self._decode(row)
            if current in _TERMINAL:
                raise ValueError("terminal candidate cannot change terminal state")
            con.execute(
                "UPDATE candidates SET stage=?,updated_at=? WHERE candidate_id=?",
                (stage, now, cid),
            )
            event = {
                "candidate_id": cid,
                "from_stage": current,
                "to_stage": stage,
                "reason": reason,
            }
            con.execute(
                """INSERT INTO lifecycle_events(
                    event_id,candidate_id,from_stage,to_stage,reason,recorded_at
                ) VALUES(?,?,?,?,?,?)""",
                (_hash(event), cid, current, stage, reason, now),
            )
            row = con.execute(
                "SELECT * FROM candidates WHERE candidate_id=?",
                (cid,),
            ).fetchone()
        if row is None:
            raise RuntimeError("candidate terminal update did not persist")
        return self._decode(row)

    def reject(self, candidate_id: str, reason: str) -> dict[str, Any]:
        return self._terminal(candidate_id, "REJECTED", reason)

    def retire(self, candidate_id: str, reason: str) -> dict[str, Any]:
        return self._terminal(candidate_id, "RETIRED", reason)

    def snapshot(self) -> dict[str, Any]:
        with _LOCK, self._connect() as con:
            candidates = con.execute(
                "SELECT * FROM candidates ORDER BY created_at,candidate_id"
            ).fetchall()
            lineage = con.execute(
                """SELECT parent_candidate_id,child_candidate_id
                   FROM lineage
                   ORDER BY parent_candidate_id,child_candidate_id"""
            ).fetchall()
            events = con.execute(
                """SELECT event_id,candidate_id,from_stage,to_stage,reason,recorded_at
                   FROM lifecycle_events
                   ORDER BY recorded_at,event_id"""
            ).fetchall()

        decoded = [self._decode(row) for row in candidates]
        stage_counts: dict[str, int] = {}
        for row in decoded:
            stage_counts[row["stage"]] = stage_counts.get(row["stage"], 0) + 1

        return {
            "schema_version": FOUNDRY_SCHEMA_VERSION,
            "journal_mode": self.journal_mode,
            "candidate_count": len(decoded),
            "stage_counts": dict(sorted(stage_counts.items())),
            "candidates": decoded,
            "lineage": [
                {
                    "parent_candidate_id": str(row["parent_candidate_id"]),
                    "child_candidate_id": str(row["child_candidate_id"]),
                }
                for row in lineage
            ],
            "lifecycle_events": [
                {
                    "event_id": str(row["event_id"]),
                    "candidate_id": str(row["candidate_id"]),
                    "from_stage": row["from_stage"],
                    "to_stage": str(row["to_stage"]),
                    "reason": str(row["reason"]),
                    "recorded_at": str(row["recorded_at"]),
                }
                for row in events
            ],
            "contracts": {
                "falsifiers_required_before_testing": True,
                "unavailable_observations_cannot_confirm": True,
                "qualified_shadow_reserved_for_protected_qualification": True,
                "terminal_history_preserved": True,
            },
            "execution_authorized": False,
            "production_decision_authorized": False,
        }
