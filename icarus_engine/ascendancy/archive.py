"""Durable open-ended architecture archive for ICARUS ASCENDANCY.

The archive is research-only evolutionary memory.  It stores immutable genome
semantics, ancestry, compile receipts, evaluation receipts, and lifecycle
events.  Retirement never deletes lineage or evaluation evidence.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .genome import normalize_genome

SCHEMA_VERSION = "icarus-ascendancy-genome-archive-v1"
_LOCK = threading.RLock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical(value: Any, name: str, *, max_bytes: int = 262144) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as ex:
        raise ValueError(f"{name} must be finite JSON") from ex
    if len(raw.encode("utf-8")) > max_bytes:
        raise ValueError(f"{name} exceeds {max_bytes} bytes")
    return raw


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value, "hash input").encode("utf-8")).hexdigest()


def _text(value: Any, name: str, limit: int = 1000) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    out = value.strip()
    if not out:
        raise ValueError(f"{name} is required")
    if len(out) > limit:
        raise ValueError(f"{name} exceeds {limit} characters")
    return out


def _parse_time(value: Any, name: str) -> str:
    text = _text(value, name, 80)
    probe = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        dt = datetime.fromisoformat(probe)
    except ValueError as ex:
        raise ValueError(f"{name} must be ISO-8601") from ex
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f"{name} must include a timezone")
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _finite_metrics(value: Any) -> dict[str, float]:
    if not isinstance(value, Mapping):
        raise ValueError("metrics must be an object")
    out: dict[str, float] = {}
    for key, raw in value.items():
        name = _text(key, "metric name", 96)
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise ValueError(f"metric {name} must be finite")
        number = float(raw)
        if not math.isfinite(number):
            raise ValueError(f"metric {name} must be finite")
        out[name] = number
    return dict(sorted(out.items()))


def _authority() -> dict[str, bool]:
    return {
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


class GenomeArchive:
    """SQLite/WAL research archive with immutable ancestry and evaluations."""

    def __init__(self, base_dir: str | os.PathLike[str]):
        self.base_dir = Path(base_dir)
        self.path = self.base_dir / "research" / "ascendancy_genomes.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.path), timeout=15)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA foreign_keys=ON")
        return con

    @property
    def journal_mode(self) -> str:
        with self._connect() as con:
            return str(con.execute("PRAGMA journal_mode").fetchone()[0]).lower()

    def _init(self) -> None:
        with _LOCK, self._connect() as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS genomes (
                    genome_id TEXT PRIMARY KEY,
                    source_repo TEXT NOT NULL,
                    source_commit TEXT NOT NULL,
                    evaluation_contract_hash TEXT NOT NULL,
                    semantic_json TEXT NOT NULL,
                    state TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS lineage (
                    parent_genome_id TEXT NOT NULL,
                    child_genome_id TEXT NOT NULL,
                    PRIMARY KEY(parent_genome_id, child_genome_id)
                );
                CREATE INDEX IF NOT EXISTS idx_asc_lineage_child ON lineage(child_genome_id);

                CREATE TABLE IF NOT EXISTS compile_receipts (
                    compile_id TEXT PRIMARY KEY,
                    genome_id TEXT NOT NULL,
                    runtime_hash TEXT NOT NULL,
                    semantic_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_asc_compile_genome ON compile_receipts(genome_id, recorded_at);

                CREATE TABLE IF NOT EXISTS evaluations (
                    evaluation_id TEXT PRIMARY KEY,
                    genome_id TEXT NOT NULL,
                    evaluation_contract_hash TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    metrics_json TEXT NOT NULL,
                    descriptors_json TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    semantic_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_asc_eval_genome ON evaluations(genome_id, observed_at, evaluation_id);
                CREATE INDEX IF NOT EXISTS idx_asc_eval_contract ON evaluations(evaluation_contract_hash, observed_at);

                CREATE TABLE IF NOT EXISTS lifecycle_events (
                    event_id TEXT PRIMARY KEY,
                    genome_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_asc_lifecycle_genome ON lifecycle_events(genome_id, recorded_at);
                """
            )

    def close(self) -> None:
        # Connections are short-lived per operation; method exists for symmetric
        # lifecycle use and deterministic reopen tests.
        return None

    @staticmethod
    def _decode_genome(row: sqlite3.Row) -> dict[str, Any]:
        try:
            semantic = json.loads(row["semantic_json"])
        except (TypeError, json.JSONDecodeError) as ex:
            raise RuntimeError("genome archive semantic corruption") from ex
        if not isinstance(semantic, dict):
            raise RuntimeError("genome archive semantic corruption")
        out = dict(semantic)
        out["state"] = row["state"]
        out["registered_at"] = row["created_at"]
        out["updated_at"] = row["updated_at"]
        return out

    def _genome_row(self, genome_id: str) -> sqlite3.Row:
        gid = _text(genome_id, "genome_id", 64).lower()
        with self._connect() as con:
            row = con.execute("SELECT * FROM genomes WHERE genome_id=?", (gid,)).fetchone()
        if row is None:
            raise ValueError("unknown genome_id")
        return row

    def register(self, body: Mapping[str, Any]) -> dict[str, Any]:
        genome = normalize_genome(body)
        gid = str(genome["genome_id"])
        raw = _canonical(genome, "genome")
        parents = list(genome["parent_genome_ids"])
        now = _utc_now()

        with _LOCK, self._connect() as con:
            row = con.execute("SELECT * FROM genomes WHERE genome_id=?", (gid,)).fetchone()
            if row is not None:
                if str(row["semantic_json"]) != raw:
                    raise RuntimeError("genome identity integrity failure")
                existing_parents = {
                    str(x["parent_genome_id"])
                    for x in con.execute(
                        "SELECT parent_genome_id FROM lineage WHERE child_genome_id=?",
                        (gid,),
                    ).fetchall()
                }
                if existing_parents != set(parents):
                    raise RuntimeError("lineage integrity failure")
                return {
                    "idempotent": True,
                    "genome": self._decode_genome(row),
                    **_authority(),
                }

            con.execute(
                """INSERT INTO genomes(
                    genome_id,source_repo,source_commit,evaluation_contract_hash,
                    semantic_json,state,created_at,updated_at
                ) VALUES(?,?,?,?,?,?,?,?)""",
                (
                    gid,
                    genome["source_repo"],
                    genome["source_commit"],
                    genome["evaluation_contract"]["contract_hash"],
                    raw,
                    "REGISTERED_RESEARCH",
                    now,
                    now,
                ),
            )
            for parent in parents:
                con.execute(
                    "INSERT INTO lineage(parent_genome_id,child_genome_id) VALUES(?,?)",
                    (parent, gid),
                )
            event = {
                "genome_id": gid,
                "state": "REGISTERED_RESEARCH",
                "reason": "registered",
            }
            con.execute(
                "INSERT INTO lifecycle_events(event_id,genome_id,state,reason,recorded_at) VALUES(?,?,?,?,?)",
                (_hash(event), gid, event["state"], event["reason"], now),
            )
            row = con.execute("SELECT * FROM genomes WHERE genome_id=?", (gid,)).fetchone()
        if row is None:
            raise RuntimeError("genome registration did not persist")
        return {"idempotent": False, "genome": self._decode_genome(row), **_authority()}

    def record_compile(self, compiled: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(compiled, Mapping):
            raise ValueError("compiled genome receipt must be an object")
        body = dict(compiled)
        gid = _text(body.get("genome_id"), "genome_id", 64).lower()
        row = self._genome_row(gid)
        runtime_hash = _text(body.get("runtime_hash"), "runtime_hash", 64).lower()
        if len(runtime_hash) != 64 or any(c not in "0123456789abcdef" for c in runtime_hash):
            raise ValueError("runtime_hash must be a 64-character hash")
        if body.get("execution_authorized") is not False or body.get("production_decision_authorized") is not False:
            raise ValueError("compiled genome cannot authorize trading")
        if body.get("production_bindings") != []:
            raise ValueError("compiled genome must not contain production bindings")
        expected = _hash({k: v for k, v in body.items() if k != "runtime_hash"})
        if expected != runtime_hash:
            raise ValueError("compiled genome runtime_hash integrity failure")
        if body.get("evaluation_contract_hash") != row["evaluation_contract_hash"]:
            raise ValueError("compiled genome evaluation contract mismatch")

        raw = _canonical(body, "compiled genome")
        compile_id = _hash({"genome_id": gid, "runtime_hash": runtime_hash, "compiled": body})
        now = _utc_now()
        with _LOCK, self._connect() as con:
            cur = con.execute(
                """INSERT OR IGNORE INTO compile_receipts(
                    compile_id,genome_id,runtime_hash,semantic_json,recorded_at
                ) VALUES(?,?,?,?,?)""",
                (compile_id, gid, runtime_hash, raw, now),
            )
        receipt = dict(body)
        receipt["compile_id"] = compile_id
        receipt["recorded_at"] = now
        return {
            "idempotent": cur.rowcount == 0,
            "compile_receipt": receipt,
            **_authority(),
        }

    def record_evaluation(self, body: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(body, Mapping):
            raise ValueError("evaluation must be an object")
        gid = _text(body.get("genome_id"), "genome_id", 64).lower()
        row = self._genome_row(gid)
        genome = self._decode_genome(row)
        contract = genome.get("evaluation_contract")
        if not isinstance(contract, Mapping):
            raise RuntimeError("genome evaluation contract is corrupt")
        expected_contract = str(contract.get("contract_hash") or "")
        supplied_contract = _text(body.get("evaluation_contract_hash"), "evaluation_contract_hash", 64).lower()
        if supplied_contract != expected_contract:
            raise ValueError("evaluation contract mismatch")

        metrics = _finite_metrics(body.get("metrics"))
        objective_names = {
            str(x["name"])
            for x in contract.get("objectives", [])
            if isinstance(x, Mapping) and x.get("name")
        }
        if set(metrics) != objective_names:
            raise ValueError("evaluation must provide exact objective metrics")

        descriptors_value = body.get("descriptors")
        if not isinstance(descriptors_value, Mapping):
            raise ValueError("descriptors must be an object")
        descriptor_keys = {str(x) for x in contract.get("descriptor_keys", [])}
        descriptors = dict(descriptors_value)
        if set(descriptors) != descriptor_keys:
            raise ValueError("evaluation must provide every contract descriptor and no extras")
        _canonical(descriptors, "descriptors", max_bytes=32768)

        evidence_value = body.get("evidence")
        if not isinstance(evidence_value, Sequence) or isinstance(evidence_value, (str, bytes)):
            raise ValueError("evaluation evidence must be a list")
        evidence = sorted({_text(x, "evaluation evidence", 500) for x in evidence_value})
        if not evidence:
            raise ValueError("evaluation evidence is required")

        observed_at = _parse_time(body.get("observed_at"), "observed_at")
        status = _text(body.get("status"), "evaluation status", 96).upper()
        if body.get("execution_authorized") not in (None, False) or body.get("production_decision_authorized") not in (None, False):
            raise ValueError("evaluation cannot authorize trading")

        semantic = {
            "genome_id": gid,
            "evaluation_contract_hash": supplied_contract,
            "metrics": metrics,
            "descriptors": descriptors,
            "evidence": evidence,
            "observed_at": observed_at,
            "status": status,
            **_authority(),
        }
        evaluation_id = _hash(semantic)
        raw = _canonical(semantic, "evaluation")
        now = _utc_now()

        with _LOCK, self._connect() as con:
            cur = con.execute(
                """INSERT OR IGNORE INTO evaluations(
                    evaluation_id,genome_id,evaluation_contract_hash,observed_at,
                    metrics_json,descriptors_json,evidence_json,status,semantic_json,recorded_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?)""",
                (
                    evaluation_id,
                    gid,
                    supplied_contract,
                    observed_at,
                    _canonical(metrics, "metrics"),
                    _canonical(descriptors, "descriptors"),
                    _canonical(evidence, "evidence"),
                    status,
                    raw,
                    now,
                ),
            )
        out = dict(semantic)
        out["evaluation_id"] = evaluation_id
        out["recorded_at"] = now
        return {"idempotent": cur.rowcount == 0, "evaluation": out, **_authority()}

    def retire(self, genome_id: str, reason: str) -> dict[str, Any]:
        gid = _text(genome_id, "genome_id", 64).lower()
        reason = _text(reason, "retirement reason", 1000)
        now = _utc_now()
        with _LOCK, self._connect() as con:
            row = con.execute("SELECT * FROM genomes WHERE genome_id=?", (gid,)).fetchone()
            if row is None:
                raise ValueError("unknown genome_id")
            current = str(row["state"])
            if current == "RETIRED":
                return {"genome_id": gid, "state": "RETIRED", "idempotent": True, **_authority()}
            con.execute(
                "UPDATE genomes SET state='RETIRED',updated_at=? WHERE genome_id=?",
                (now, gid),
            )
            event = {"genome_id": gid, "state": "RETIRED", "reason": reason}
            con.execute(
                "INSERT INTO lifecycle_events(event_id,genome_id,state,reason,recorded_at) VALUES(?,?,?,?,?)",
                (_hash(event), gid, "RETIRED", reason, now),
            )
        return {"genome_id": gid, "state": "RETIRED", "idempotent": False, **_authority()}

    def snapshot(self) -> dict[str, Any]:
        with _LOCK, self._connect() as con:
            genome_rows = con.execute("SELECT * FROM genomes ORDER BY created_at,genome_id").fetchall()
            lineage_rows = con.execute(
                "SELECT parent_genome_id,child_genome_id FROM lineage ORDER BY parent_genome_id,child_genome_id"
            ).fetchall()
            compile_rows = con.execute(
                "SELECT semantic_json,compile_id,recorded_at FROM compile_receipts ORDER BY recorded_at,compile_id"
            ).fetchall()
            evaluation_rows = con.execute(
                "SELECT semantic_json,evaluation_id,recorded_at FROM evaluations ORDER BY observed_at,evaluation_id"
            ).fetchall()
            lifecycle_rows = con.execute(
                "SELECT event_id,genome_id,state,reason,recorded_at FROM lifecycle_events ORDER BY recorded_at,event_id"
            ).fetchall()

        genomes = [self._decode_genome(row) for row in genome_rows]
        lineage = [
            {
                "parent_genome_id": str(row["parent_genome_id"]),
                "child_genome_id": str(row["child_genome_id"]),
            }
            for row in lineage_rows
        ]

        compiles: list[dict[str, Any]] = []
        for row in compile_rows:
            try:
                item = json.loads(row["semantic_json"])
            except (TypeError, json.JSONDecodeError):
                continue
            if isinstance(item, dict):
                item["compile_id"] = row["compile_id"]
                item["recorded_at"] = row["recorded_at"]
                compiles.append(item)

        evaluations: list[dict[str, Any]] = []
        for row in evaluation_rows:
            try:
                item = json.loads(row["semantic_json"])
            except (TypeError, json.JSONDecodeError):
                continue
            if isinstance(item, dict):
                item["evaluation_id"] = row["evaluation_id"]
                item["recorded_at"] = row["recorded_at"]
                evaluations.append(item)

        lifecycle = [
            {
                "event_id": str(row["event_id"]),
                "genome_id": str(row["genome_id"]),
                "state": str(row["state"]),
                "reason": str(row["reason"]),
                "recorded_at": str(row["recorded_at"]),
            }
            for row in lifecycle_rows
        ]
        return {
            "schema_version": SCHEMA_VERSION,
            "journal_mode": self.journal_mode,
            "genome_count": len(genomes),
            "compile_count": len(compiles),
            "evaluation_count": len(evaluations),
            "retired_count": sum(1 for row in genomes if row["state"] == "RETIRED"),
            "genomes": genomes,
            "lineage": lineage,
            "compile_receipts": compiles,
            "evaluations": evaluations,
            "lifecycle_events": lifecycle,
            **_authority(),
        }
