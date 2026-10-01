"""Durable PANTHEON / AETHER research kernel."""
from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .aether import AetherSwarm
from .contracts import (
    FACULTIES,
    OBSERVATION_SCHEMA,
    SCHEMA_VERSION,
    authority_block,
    digest,
    exact_git_sha,
    iso_aware,
    json_canonical,
    mapping,
    text,
)
from .faculties import evaluate_faculties
from .bridge import sibyl_evidence_candidates

_LOCK = threading.RLock()

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

class PantheonKernel:
    """Immutable observation ledger plus deterministic shadow analysis."""

    def __init__(self, base_dir: str | os.PathLike[str], *, swarm: AetherSwarm | None = None):
        self.base_dir = Path(base_dir)
        self.path = self.base_dir / "research" / "pantheon.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.swarm = swarm or AetherSwarm()
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
                CREATE TABLE IF NOT EXISTS observations (
                    observation_id TEXT PRIMARY KEY,
                    observed_at TEXT NOT NULL,
                    asset TEXT NOT NULL,
                    horizon_ms INTEGER NOT NULL,
                    source_commit TEXT NOT NULL,
                    identity_hash TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    analysis_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS claims (
                    claim_id TEXT PRIMARY KEY,
                    observation_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sentinel_cells (
                    cell_id TEXT PRIMARY KEY,
                    asset TEXT NOT NULL,
                    horizon_ms INTEGER NOT NULL,
                    last_observation_id TEXT NOT NULL,
                    last_observed_at TEXT NOT NULL,
                    last_energy REAL NOT NULL,
                    last_status TEXT NOT NULL,
                    observation_count INTEGER NOT NULL DEFAULT 1,
                    updated_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_pantheon_obs_asset ON observations(asset, observed_at);
                CREATE INDEX IF NOT EXISTS idx_pantheon_claim_obs ON claims(observation_id, kind);
                CREATE INDEX IF NOT EXISTS idx_pantheon_cells_energy ON sentinel_cells(last_energy, updated_at);
                """
            )
            columns = {row["name"] for row in con.execute("PRAGMA table_info(sentinel_cells)").fetchall()}
            if "last_observed_at" not in columns:
                con.execute("ALTER TABLE sentinel_cells ADD COLUMN last_observed_at TEXT NOT NULL DEFAULT ''")

    def _normalize(self, payload: Mapping[str, Any]) -> tuple[dict[str, Any], str, str]:
        if not isinstance(payload, Mapping):
            raise ValueError("observation must be an object")
        if payload.get("schema_version", OBSERVATION_SCHEMA) != OBSERVATION_SCHEMA:
            raise ValueError("unsupported PANTHEON observation schema")
        observed_at = iso_aware(payload.get("observed_at"))
        asset = text(payload.get("asset"), "asset", 32).upper()
        source_commit = exact_git_sha(payload.get("source_commit"))
        horizon = payload.get("horizon_ms", 1000)
        if type(horizon) is not int or not 1 <= horizon <= 86_400_000:
            raise ValueError("horizon_ms must be an integer from 1 to 86400000")
        signals = dict(mapping(payload.get("signals", {}), "signals"))
        if len(signals) > 256:
            raise ValueError("signals exceeds 256 fields")
        evidence = payload.get("evidence", [])
        if isinstance(evidence, str):
            evidence = [evidence]
        if not isinstance(evidence, list) or len(evidence) > 64:
            raise ValueError("evidence must be a list with at most 64 items")
        evidence = [text(x, "evidence item", 700) for x in evidence]
        source_outputs = payload.get("subsystem_outputs", {})
        source_outputs = dict(mapping(source_outputs, "subsystem_outputs"))
        if len(source_outputs) > 64:
            raise ValueError("subsystem_outputs exceeds 64 entries")
        normalized = {
            "schema_version": OBSERVATION_SCHEMA,
            "observed_at": observed_at,
            "asset": asset,
            "horizon_ms": horizon,
            "source_commit": source_commit,
            "signals": signals,
            "evidence": evidence,
            "subsystem_outputs": source_outputs,
        }
        raw = json_canonical(normalized, "observation", 262144)
        identity = digest(raw)
        observation_id = str(payload.get("observation_id") or ("pan-" + identity[:24]))
        observation_id = text(observation_id, "observation_id", 96)
        return normalized, identity, observation_id

    def record_observation(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        normalized, identity, observation_id = self._normalize(payload)
        with _LOCK, self._connect() as con:
            existing = con.execute("SELECT * FROM observations WHERE observation_id=?", (observation_id,)).fetchone()
            if existing:
                if existing["identity_hash"] != identity:
                    raise ValueError("observation_id already exists with different immutable identity")
                return self.observation(observation_id)

        faculties = evaluate_faculties(normalized["signals"], observation_id)
        aether = self.swarm.evaluate(
            observation_id,
            normalized["asset"],
            normalized["horizon_ms"],
            normalized["signals"],
            faculties,
        )
        analysis = {
            "faculties": faculties,
            "aether": aether,
            "external_subsystems": normalized["subsystem_outputs"],
            "exports": {
                "sibyl_evidence": sibyl_evidence_candidates(
                    observed_at=normalized["observed_at"],
                    asset=normalized["asset"],
                    horizon_ms=normalized["horizon_ms"],
                    source_commit=normalized["source_commit"],
                    faculties=faculties,
                    aether=aether,
                )
            },
            "authority": authority_block(),
            "truth_contract": {
                "heuristics_are_not_calibrated_probabilities": True,
                "engine_disagreement_is_preserved": True,
                "missing_inputs_produce_abstention": True,
                "new_concepts_begin_as_hypotheses": True,
                "execution_requires_separate_hard_risk_kernel": True,
            },
        }
        payload_json = json_canonical(normalized, "normalized observation", 262144)
        analysis_json = json_canonical(analysis, "pantheon analysis", 524288)
        now = _utc_now()
        claims = []
        exn = faculties.get("ex_nihilo", {})
        if exn.get("new_phenomenon_candidate"):
            claims.append({
                "claim_id": str(exn["phenomenon_id"]),
                "kind": "ontology_candidate",
                "stage": "hypothesis",
                "payload": {
                    "faculty": "EX_NIHILO",
                    "ontology_surprise": exn.get("ontology_surprise"),
                    "observation_id": observation_id,
                },
            })
        mint = faculties.get("mint", {})
        if mint.get("best_candidate"):
            claims.append({
                "claim_id": "edge-" + digest(observation_id, str(mint["best_candidate"].get("name")))[:20],
                "kind": "monetization_candidate",
                "stage": "shadow",
                "payload": {
                    "faculty": "MINT",
                    "candidate": mint["best_candidate"],
                    "observation_id": observation_id,
                },
            })
        with _LOCK, self._connect() as con:
            con.execute(
                """INSERT INTO observations(
                    observation_id,observed_at,asset,horizon_ms,source_commit,identity_hash,payload_json,analysis_json,created_at
                ) VALUES(?,?,?,?,?,?,?,?,?)""",
                (
                    observation_id,
                    normalized["observed_at"],
                    normalized["asset"],
                    normalized["horizon_ms"],
                    normalized["source_commit"],
                    identity,
                    payload_json,
                    analysis_json,
                    now,
                ),
            )
            for claim in claims:
                con.execute(
                    "INSERT OR IGNORE INTO claims(claim_id,observation_id,kind,stage,payload_json,created_at) VALUES(?,?,?,?,?,?)",
                    (
                        claim["claim_id"],
                        observation_id,
                        claim["kind"],
                        claim["stage"],
                        json_canonical(claim["payload"], "claim", 65536),
                        now,
                    ),
                )
            cell_id = "cell-" + digest(normalized["asset"], str(normalized["horizon_ms"]))[:18]
            con.execute(
                """INSERT INTO sentinel_cells(
                    cell_id,asset,horizon_ms,last_observation_id,last_observed_at,last_energy,last_status,observation_count,updated_at
                ) VALUES(?,?,?,?,?,?,?,1,?)
                ON CONFLICT(cell_id) DO UPDATE SET
                    last_observation_id=CASE
                        WHEN excluded.last_observed_at >= sentinel_cells.last_observed_at
                        THEN excluded.last_observation_id ELSE sentinel_cells.last_observation_id END,
                    last_observed_at=MAX(sentinel_cells.last_observed_at, excluded.last_observed_at),
                    last_energy=CASE
                        WHEN excluded.last_observed_at >= sentinel_cells.last_observed_at
                        THEN excluded.last_energy ELSE sentinel_cells.last_energy END,
                    last_status=CASE
                        WHEN excluded.last_observed_at >= sentinel_cells.last_observed_at
                        THEN excluded.last_status ELSE sentinel_cells.last_status END,
                    observation_count=sentinel_cells.observation_count+1,
                    updated_at=excluded.updated_at""",
                (
                    cell_id,
                    normalized["asset"],
                    normalized["horizon_ms"],
                    observation_id,
                    normalized["observed_at"],
                    float(aether["field"]["energy"]),
                    str(aether["status"]),
                    now,
                ),
            )
        return self.observation(observation_id)

    def observation(self, observation_id: str) -> dict[str, Any]:
        with _LOCK, self._connect() as con:
            row = con.execute("SELECT * FROM observations WHERE observation_id=?", (observation_id,)).fetchone()
            if not row:
                raise ValueError("unknown PANTHEON observation")
            claim_rows = con.execute("SELECT * FROM claims WHERE observation_id=? ORDER BY rowid", (observation_id,)).fetchall()
        return {
            "observation_id": row["observation_id"],
            "observed_at": row["observed_at"],
            "asset": row["asset"],
            "horizon_ms": row["horizon_ms"],
            "source_commit": row["source_commit"],
            "input": json.loads(row["payload_json"]),
            "analysis": json.loads(row["analysis_json"]),
            "claims": [
                {
                    "claim_id": r["claim_id"],
                    "kind": r["kind"],
                    "stage": r["stage"],
                    "payload": json.loads(r["payload_json"]),
                }
                for r in claim_rows
            ],
        }

    def snapshot(self, limit: int = 50) -> dict[str, Any]:
        limit = max(1, min(250, int(limit)))
        with _LOCK, self._connect() as con:
            rows = con.execute("SELECT observation_id FROM observations ORDER BY observed_at DESC LIMIT ?", (limit,)).fetchall()
            counts = con.execute(
                "SELECT COUNT(*) AS observations,(SELECT COUNT(*) FROM claims) AS claims,(SELECT COUNT(*) FROM sentinel_cells) AS cells FROM observations"
            ).fetchone()
            cell_rows = con.execute(
                "SELECT * FROM sentinel_cells ORDER BY last_energy DESC,updated_at DESC LIMIT 100"
            ).fetchall()
        observations = [self.observation(row["observation_id"]) for row in rows]
        cells = [
            {
                "cell_id": row["cell_id"],
                "asset": row["asset"],
                "horizon_ms": row["horizon_ms"],
                "last_observation_id": row["last_observation_id"],
                "last_observed_at": row["last_observed_at"],
                "energy": row["last_energy"],
                "status": row["last_status"],
                "observation_count": row["observation_count"],
                "updated_at": row["updated_at"],
            }
            for row in cell_rows
        ]
        latest = observations[0] if observations else None
        catalog = {
            "ORACLE": {"mode": "native subsystem via read-only adapter", "ownership": "preserved; not reimplemented here"},
            "PARALLAX": {"mode": "native subsystem", "ownership": "preserved"},
            "DREAMSTATE": {"mode": "native subsystem", "ownership": "preserved"},
            "NEMESIS": {"mode": "pantheon faculty"},
            "GODEL": {"mode": "pantheon faculty"},
            "SOCRATES": {"mode": "pantheon faculty"},
            "ANANKE": {"mode": "pantheon faculty"},
            "EX_NIHILO": {"mode": "pantheon faculty"},
            "MINT": {"mode": "pantheon faculty"},
            "NULLSPACE": {"mode": "pantheon faculty"},
            "ARCHON": {"mode": "pantheon faculty"},
            "AETHER": {"mode": "ephemeral swarm ecology"},
        }
        return {
            "schema_version": SCHEMA_VERSION,
            "counts": {"observations": counts["observations"], "claims": counts["claims"], "sentinel_cells": counts["cells"]},
            "sentinel_cells": cells,
            "engine_catalog": catalog,
            "faculty_names": list(FACULTIES),
            "latest": latest,
            "observations": observations,
            "authority": authority_block(),
            "truth_contract": {
                "research_shadow_only": True,
                "no_direct_agent_trading": True,
                "no_forced_consensus": True,
                "oracle_parallax_dreamstate_ownership_preserved": True,
                "risk_kernel_remains_external_hard_gate": True,
            },
        }
