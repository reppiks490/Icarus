"""Durable PANTHEON / AETHER research kernel."""
from __future__ import annotations

import json
import math
import os
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
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
    finite,
    iso_aware,
    json_canonical,
    mapping,
    signed_unit,
    text,
    unit,
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
                CREATE TABLE IF NOT EXISTS agent_claims (
                    claim_id TEXT PRIMARY KEY,
                    observation_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(observation_id, agent_id)
                );
                CREATE TABLE IF NOT EXISTS claim_outcomes (
                    outcome_id TEXT PRIMARY KEY,
                    claim_id TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    utility REAL NOT NULL,
                    confidence REAL NOT NULL,
                    evidence_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS species (
                    species_id TEXT PRIMARY KEY,
                    asset TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    origin_claim_id TEXT NOT NULL,
                    parent_species_id TEXT,
                    generation INTEGER NOT NULL,
                    stage TEXT NOT NULL,
                    fitness_credit REAL NOT NULL,
                    evidence_count INTEGER NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
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
                CREATE INDEX IF NOT EXISTS idx_pantheon_agent_claim_obs ON agent_claims(observation_id, role);
                CREATE INDEX IF NOT EXISTS idx_pantheon_outcome_claim ON claim_outcomes(claim_id, observed_at);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_pantheon_outcome_claim_time ON claim_outcomes(claim_id, observed_at);
                CREATE INDEX IF NOT EXISTS idx_pantheon_species_asset ON species(asset, stage, fitness_credit);
                CREATE INDEX IF NOT EXISTS idx_pantheon_cells_energy ON sentinel_cells(last_energy, updated_at);
                """
            )
            columns = {row["name"] for row in con.execute("PRAGMA table_info(sentinel_cells)").fetchall()}
            if "last_observed_at" not in columns:
                con.execute("ALTER TABLE sentinel_cells ADD COLUMN last_observed_at TEXT NOT NULL DEFAULT ''")
            con.execute(
                """UPDATE sentinel_cells
                   SET last_observed_at=COALESCE(
                       (SELECT observed_at FROM observations
                        WHERE observation_id=sentinel_cells.last_observation_id),
                       last_observed_at
                   )
                   WHERE last_observed_at=''"""
            )

            legacy_claims = con.execute(
                """SELECT c.claim_id,c.kind,c.payload_json,c.created_at,o.asset
                   FROM claims c
                   JOIN observations o ON o.observation_id=c.observation_id
                   WHERE c.kind IN ('ontology_candidate','monetization_candidate','mutation_candidate')
                   ORDER BY c.created_at,c.rowid"""
            ).fetchall()
            for claim in legacy_claims:
                present = con.execute(
                    "SELECT species_id FROM species WHERE origin_claim_id=? LIMIT 1",
                    (claim["claim_id"],),
                ).fetchone()
                if present is not None:
                    continue
                payload = json.loads(claim["payload_json"])
                parent_species_id = payload.get("parent_species_id") if isinstance(payload, Mapping) else None
                generation = 0
                if parent_species_id:
                    parent = con.execute(
                        "SELECT generation FROM species WHERE species_id=?",
                        (str(parent_species_id),),
                    ).fetchone()
                    generation = (int(parent["generation"]) + 1) if parent is not None else 1
                species_id = "species-" + digest(claim["claim_id"], claim["asset"])[:18]
                con.execute(
                    """INSERT OR IGNORE INTO species(
                        species_id,asset,kind,origin_claim_id,parent_species_id,generation,
                        stage,fitness_credit,evidence_count,payload_json,created_at,updated_at
                    ) VALUES(?,?,?,?,?,?,'hypothesis',0.0,0,?,?,?)""",
                    (
                        species_id,
                        claim["asset"],
                        claim["kind"],
                        claim["claim_id"],
                        str(parent_species_id) if parent_species_id else None,
                        generation,
                        claim["payload_json"],
                        claim["created_at"],
                        claim["created_at"],
                    ),
                )

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
        claim_outcomes = payload.get("claim_outcomes", [])
        if claim_outcomes is None:
            claim_outcomes = []
        if not isinstance(claim_outcomes, list) or len(claim_outcomes) > 32:
            raise ValueError("claim_outcomes must be a list with at most 32 items")
        clean_outcomes = []
        for i, row in enumerate(claim_outcomes):
            if not isinstance(row, Mapping):
                raise ValueError(f"claim_outcomes[{i}] must be an object")
            clean_outcomes.append(dict(row))
        normalized = {
            "schema_version": OBSERVATION_SCHEMA,
            "observed_at": observed_at,
            "asset": asset,
            "horizon_ms": horizon,
            "source_commit": source_commit,
            "signals": signals,
            "evidence": evidence,
            "subsystem_outputs": source_outputs,
            "claim_outcomes": clean_outcomes,
        }
        identity_payload = {
            "schema_version": OBSERVATION_SCHEMA,
            "observed_at": observed_at,
            "asset": asset,
            "horizon_ms": horizon,
            "source_commit": source_commit,
            "signals": signals,
            "evidence": evidence,
        }
        raw = json_canonical(identity_payload, "observation identity", 262144)
        identity = digest(raw)
        observation_id = str(payload.get("observation_id") or ("pan-" + identity[:24]))
        observation_id = text(observation_id, "observation_id", 96)
        return normalized, identity, observation_id

    def _attach_ecology_outcomes(self, result: dict[str, Any], normalized: Mapping[str, Any]) -> dict[str, Any]:
        result["ecology_outcomes"] = [
            self.record_claim_outcome({
                **row,
                "observed_at": row.get("observed_at") or normalized["observed_at"],
                "_source_observation_id": result.get("observation_id"),
            })
            for row in normalized.get("claim_outcomes", [])
        ]
        return result

    def record_observation(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        normalized, identity, observation_id = self._normalize(payload)
        with _LOCK, self._connect() as con:
            existing = con.execute("SELECT * FROM observations WHERE observation_id=?", (observation_id,)).fetchone()
            if existing:
                if existing["identity_hash"] != identity:
                    raise ValueError("observation_id already exists with different immutable identity")
                return self._attach_ecology_outcomes(self.observation(observation_id), normalized)

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
                "ambient_subsystem_context_excluded_from_immutable_identity": True,
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
            # Recheck under the insertion lock. Evaluation happens outside the lock,
            # so another request may have committed the same immutable observation.
            existing = con.execute("SELECT identity_hash FROM observations WHERE observation_id=?", (observation_id,)).fetchone()
            if existing:
                if existing["identity_hash"] != identity:
                    raise ValueError("observation_id already exists with different immutable identity")
                return self._attach_ecology_outcomes(self.observation(observation_id), normalized)
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
                claim_payload_json = json_canonical(claim["payload"], "claim", 65536)
                con.execute(
                    "INSERT OR IGNORE INTO claims(claim_id,observation_id,kind,stage,payload_json,created_at) VALUES(?,?,?,?,?,?)",
                    (
                        claim["claim_id"],
                        observation_id,
                        claim["kind"],
                        claim["stage"],
                        claim_payload_json,
                        now,
                    ),
                )
                species_id = "species-" + digest(claim["claim_id"], normalized["asset"])[:18]
                con.execute(
                    """INSERT OR IGNORE INTO species(
                        species_id,asset,kind,origin_claim_id,parent_species_id,generation,
                        stage,fitness_credit,evidence_count,payload_json,created_at,updated_at
                    ) VALUES(?,?,?,?,NULL,0,'hypothesis',0.0,0,?,?,?)""",
                    (
                        species_id,
                        normalized["asset"],
                        claim["kind"],
                        claim["claim_id"],
                        claim_payload_json,
                        now,
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
        return self._attach_ecology_outcomes(self.observation(observation_id), normalized)

    def record_agent_claim(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Commit one blind-first-pass claim from a spawned AETHER research agent."""
        if not isinstance(payload, Mapping):
            raise ValueError("agent claim must be an object")
        observation_id = text(payload.get("observation_id"), "observation_id", 96)
        agent_id = text(payload.get("agent_id"), "agent_id", 96)
        if payload.get("peer_context_used", False) is not False:
            raise ValueError("blind first-pass AETHER claims cannot use peer context")
        claim = mapping(payload.get("claim", {}), "claim")
        thesis = text(claim.get("thesis"), "claim.thesis", 1200)
        direction = text(claim.get("direction", "unknown"), "claim.direction", 16).lower()
        if direction not in {"long", "short", "flat", "unknown"}:
            raise ValueError("claim.direction must be long, short, flat or unknown")
        if "confidence" not in claim:
            raise ValueError("claim.confidence is required")
        confidence = unit(claim.get("confidence"), "claim.confidence")
        falsifier = text(claim.get("falsifier", ""), "claim.falsifier", 1200, required=False)
        evidence = claim.get("evidence", [])
        if isinstance(evidence, str):
            evidence = [evidence]
        if not isinstance(evidence, list) or not evidence or len(evidence) > 24:
            raise ValueError("claim.evidence must contain 1-24 items")
        normalized_evidence = [text(x, "claim.evidence item", 700) for x in evidence]

        observation = self.observation(observation_id)
        agents = observation.get("analysis", {}).get("aether", {}).get("agents", [])
        agent = next((row for row in agents if isinstance(row, Mapping) and row.get("agent_id") == agent_id), None)
        if agent is None:
            raise ValueError("agent_id is not an active AETHER agent for this observation")
        role = text(agent.get("role"), "agent.role", 64)
        if agent.get("falsifier_required") and not falsifier:
            raise ValueError(f"falsifier is required for AETHER role {role}")
        normalized = {
            "thesis": thesis,
            "direction": direction,
            "confidence": confidence,
            "falsifier": falsifier,
            "evidence": normalized_evidence,
            "peer_context_used": False,
            "information_partition": agent.get("information_partition"),
            "independence_round": agent.get("independence_round"),
        }
        raw = json_canonical(normalized, "agent claim", 65536)
        claim_id = "aethc-" + digest(observation_id, agent_id)[:20]
        now = _utc_now()
        with _LOCK, self._connect() as con:
            existing = con.execute(
                "SELECT * FROM agent_claims WHERE observation_id=? AND agent_id=?",
                (observation_id, agent_id),
            ).fetchone()
            if existing:
                if existing["payload_json"] != raw or existing["role"] != role:
                    raise ValueError("AETHER agent first-pass claim is immutable")
                return self.observation(observation_id)
            con.execute(
                "INSERT INTO agent_claims(claim_id,observation_id,agent_id,role,payload_json,created_at) VALUES(?,?,?,?,?,?)",
                (claim_id, observation_id, agent_id, role, raw, now),
            )
        return self.observation(observation_id)

    def _agent_claim_state(self, observation_id: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        with _LOCK, self._connect() as con:
            rows = con.execute(
                "SELECT * FROM agent_claims WHERE observation_id=? ORDER BY rowid",
                (observation_id,),
            ).fetchall()
            observation_row = con.execute(
                "SELECT analysis_json FROM observations WHERE observation_id=?",
                (observation_id,),
            ).fetchone()
        claims = [
            {
                "claim_id": row["claim_id"],
                "agent_id": row["agent_id"],
                "role": row["role"],
                "claim": json.loads(row["payload_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]
        analysis = json.loads(observation_row["analysis_json"]) if observation_row else {}
        expected_agents = analysis.get("aether", {}).get("agents", [])
        expected_agents = [row for row in expected_agents if isinstance(row, Mapping) and row.get("agent_id")]
        expected_ids = {str(row["agent_id"]) for row in expected_agents}
        expected_roles = {str(row.get("role") or "") for row in expected_agents}
        submitted_ids = {row["agent_id"] for row in claims}
        mandatory = {"falsifier", "alternative_cause", "provenance_guard", "risk_guard"}
        present_roles = {row["role"] for row in claims}
        missing_mandatory = sorted(mandatory - present_roles)
        missing_agent_ids = sorted(expected_ids - submitted_ids)
        mandatory_complete = not missing_mandatory
        all_spawned_complete = bool(expected_ids) and not missing_agent_ids
        directional = [row["claim"].get("direction") for row in claims if row["claim"].get("direction") in {"long", "short", "flat"}]
        counts = {name: directional.count(name) for name in ("long", "short", "flat")}
        disagreement = None
        if directional:
            disagreement = 1.0 - (max(counts.values()) / len(directional))
        confidence_values = [float(row["claim"].get("confidence", 0.0)) for row in claims]
        return claims, {
            "ready_for_deliberation": all_spawned_complete,
            "mandatory_roles": sorted(mandatory),
            "expected_roles": sorted(role for role in expected_roles if role),
            "expected_agent_claims": len(expected_ids),
            "missing_mandatory_roles": missing_mandatory,
            "missing_agent_ids": missing_agent_ids,
            "mandatory_roles_complete": mandatory_complete,
            "submitted_claims": len(claims),
            "direction_counts": counts,
            "disagreement_index": disagreement,
            "mean_stated_confidence": (sum(confidence_values) / len(confidence_values)) if confidence_values else None,
            "blind_first_pass_complete": all_spawned_complete,
            "peer_conclusions_hidden_during_first_pass": True,
            "claim_bodies_visible": all_spawned_complete,
            "consensus_forced": False,
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    def record_claim_outcome(self, body: Mapping[str, Any]) -> dict[str, Any]:
        """Record one immutable observed claim result and update research fitness."""
        if not isinstance(body, Mapping):
            raise ValueError("claim outcome must be an object")
        claim_id = text(body.get("claim_id"), "claim_id", 96)
        observed_at = iso_aware(body.get("observed_at"))
        utility = signed_unit(body.get("utility"), "utility")
        if "confidence" not in body:
            raise ValueError("confidence is required")
        confidence = unit(body.get("confidence"), "confidence")
        source_observation_id = body.get("_source_observation_id")
        if source_observation_id is not None:
            source_observation_id = text(source_observation_id, "_source_observation_id", 96)
        evidence = body.get("evidence", [])
        if isinstance(evidence, str):
            evidence = [evidence]
        if not isinstance(evidence, list) or not evidence or len(evidence) > 64:
            raise ValueError("evidence must contain 1-64 items")
        evidence = [text(item, "evidence item", 700) for item in evidence]
        evidence_json = json_canonical(evidence, "evidence", 65536)
        semantic = json_canonical(
            {
                "claim_id": claim_id,
                "observed_at": observed_at,
                "utility": utility,
                "confidence": confidence,
                "evidence": evidence,
            },
            "claim outcome",
            131072,
        )
        outcome_id = "out-" + digest(semantic)[:24]
        now = _utc_now()

        with _LOCK, self._connect() as con:
            claim = con.execute(
                """SELECT c.*,o.observed_at AS claim_observed_at,
                          o.horizon_ms AS claim_horizon_ms,o.asset AS claim_asset
                   FROM claims c JOIN observations o ON o.observation_id=c.observation_id
                   WHERE c.claim_id=?""",
                (claim_id,),
            ).fetchone()
            if claim is None:
                raise ValueError("unknown PANTHEON claim")
            source_observation = None
            if source_observation_id is not None:
                source_observation = con.execute(
                    "SELECT observation_id,observed_at,asset FROM observations WHERE observation_id=?",
                    (source_observation_id,),
                ).fetchone()
                if source_observation is None:
                    raise ValueError("unknown source observation for claim outcome")
            claim_time = datetime.fromisoformat(str(claim["claim_observed_at"]).replace("Z", "+00:00"))
            claim_payload = json.loads(claim["payload_json"])
            mutation_trigger = claim_payload.get("mutation_trigger") if isinstance(claim_payload, Mapping) else None
            if isinstance(mutation_trigger, Mapping) and mutation_trigger.get("observed_at"):
                mutation_time = datetime.fromisoformat(str(mutation_trigger["observed_at"]).replace("Z", "+00:00"))
                if mutation_time > claim_time:
                    claim_time = mutation_time
            outcome_time = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
            if source_observation is not None:
                source_time = datetime.fromisoformat(str(source_observation["observed_at"]).replace("Z", "+00:00"))
                if str(source_observation["asset"]) != str(claim["claim_asset"]):
                    raise ValueError("claim outcome source asset must match claim asset")
                if outcome_time != source_time:
                    raise ValueError("claim outcome time must match its source observation time")
            maturity_time = claim_time + timedelta(milliseconds=int(claim["claim_horizon_ms"]))
            if outcome_time < maturity_time:
                raise ValueError("claim outcome cannot precede claim horizon maturity")
            prior_time = con.execute(
                "SELECT * FROM claim_outcomes WHERE claim_id=? AND observed_at=?",
                (claim_id, observed_at),
            ).fetchone()
            if prior_time is not None and (
                abs(float(prior_time["utility"]) - utility) > 1e-12
                or abs(float(prior_time["confidence"]) - confidence) > 1e-12
                or prior_time["evidence_json"] != evidence_json
            ):
                raise ValueError("claim outcome is immutable for claim_id + observed_at")
            prior = con.execute("SELECT * FROM claim_outcomes WHERE outcome_id=?", (outcome_id,)).fetchone()
            if prior is None and prior_time is None:
                con.execute(
                    """INSERT INTO claim_outcomes(
                        outcome_id,claim_id,observed_at,utility,confidence,evidence_json,created_at
                    ) VALUES(?,?,?,?,?,?,?)""",
                    (outcome_id, claim_id, observed_at, utility, confidence, evidence_json, now),
                )

            outcomes = con.execute(
                "SELECT utility,confidence FROM claim_outcomes WHERE claim_id=? ORDER BY observed_at",
                (claim_id,),
            ).fetchall()
            positive_weight = sum(float(row["confidence"]) for row in outcomes)
            if positive_weight > 1e-12:
                fitness = sum(float(row["utility"]) * float(row["confidence"]) for row in outcomes) / positive_weight
            else:
                fitness = 0.0
            n = len(outcomes)
            if n >= 3 and fitness <= -0.20:
                stage = "retired"
            elif n >= 3 and fitness >= 0.20:
                stage = "surviving_shadow"
            elif n >= 2:
                stage = "contested"
            else:
                stage = "hypothesis"

            species = con.execute(
                "SELECT * FROM species WHERE origin_claim_id=? ORDER BY generation LIMIT 1",
                (claim_id,),
            ).fetchone()
            child_id = None
            if species is not None:
                con.execute(
                    "UPDATE species SET stage=?,fitness_credit=?,evidence_count=?,updated_at=? WHERE species_id=?",
                    (stage, fitness, n, now, species["species_id"]),
                )
                child = con.execute(
                    "SELECT species_id FROM species WHERE parent_species_id=? ORDER BY generation LIMIT 1",
                    (species["species_id"],),
                ).fetchone()
                if (
                    child is None
                    and stage == "surviving_shadow"
                    and fitness >= 0.50
                    and int(species["generation"]) < 3
                ):
                    child_id = "species-" + digest(species["species_id"], "mutant", str(n))[:18]
                    child_claim_id = "mut-" + digest(child_id, claim_id)[:20]
                    child_payload = {
                        "parent_species_id": species["species_id"],
                        "parent_claim_id": claim_id,
                        "mutation_trigger": {
                            "fitness_credit": fitness,
                            "evidence_count": n,
                            "observed_at": observed_at,
                        },
                        "stage": "research_variant",
                        "automatic_production_authority": False,
                    }
                    con.execute(
                        """INSERT OR IGNORE INTO claims(
                            claim_id,observation_id,kind,stage,payload_json,created_at
                        ) VALUES(?,?,?,?,?,?)""",
                        (
                            child_claim_id,
                            source_observation_id or claim["observation_id"],
                            "mutation_candidate",
                            "hypothesis",
                            json_canonical(child_payload, "mutant claim", 65536),
                            now,
                        ),
                    )
                    con.execute(
                        """INSERT OR IGNORE INTO species(
                            species_id,asset,kind,origin_claim_id,parent_species_id,generation,
                            stage,fitness_credit,evidence_count,payload_json,created_at,updated_at
                        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            child_id,
                            species["asset"],
                            "mutation_candidate",
                            child_claim_id,
                            species["species_id"],
                            int(species["generation"]) + 1,
                            "hypothesis",
                            0.0,
                            0,
                            json_canonical(child_payload, "species payload", 65536),
                            now,
                            now,
                        ),
                    )

        return {
            "outcome_id": outcome_id,
            "claim_id": claim_id,
            "observed_at": observed_at,
            "utility": utility,
            "confidence": confidence,
            "fitness_credit": fitness,
            "evidence_count": n,
            "species_stage": stage,
            "offspring_species_id": child_id,
            "authority": authority_block(),
        }

    def _ecology_snapshot(self, limit: int = 100) -> dict[str, Any]:
        with _LOCK, self._connect() as con:
            rows = con.execute(
                "SELECT * FROM species ORDER BY fitness_credit DESC,evidence_count DESC,updated_at DESC LIMIT ?",
                (max(1, min(250, int(limit))),),
            ).fetchall()
            outcome_count = con.execute("SELECT COUNT(*) AS n FROM claim_outcomes").fetchone()["n"]

        species = []
        for row in rows:
            payload = json.loads(row["payload_json"])
            alpha_mass = max(0.0, float(row["fitness_credit"])) * (1.0 + math.log1p(int(row["evidence_count"])))
            species.append(
                {
                    "species_id": row["species_id"],
                    "asset": row["asset"],
                    "kind": row["kind"],
                    "origin_claim_id": row["origin_claim_id"],
                    "parent_species_id": row["parent_species_id"],
                    "generation": row["generation"],
                    "stage": row["stage"],
                    "fitness_credit": row["fitness_credit"],
                    "evidence_count": row["evidence_count"],
                    "alpha_mass": alpha_mass,
                    "payload": payload,
                    "updated_at": row["updated_at"],
                }
            )

        interactions = []
        for i, left in enumerate(species):
            if left["stage"] == "retired":
                continue
            for right in species[i + 1:]:
                if right["stage"] == "retired" or left["asset"] != right["asset"]:
                    continue
                if left["kind"] == right["kind"] and abs(left["fitness_credit"] - right["fitness_credit"]) >= 0.35:
                    predator, prey = (left, right) if left["fitness_credit"] > right["fitness_credit"] else (right, left)
                    interactions.append(
                        {
                            "type": "predation",
                            "predator": predator["species_id"],
                            "prey": prey["species_id"],
                            "asset": left["asset"],
                            "basis": "same-kind research fitness separation",
                        }
                    )
                elif left["kind"] != right["kind"] and left["fitness_credit"] >= 0.20 and right["fitness_credit"] >= 0.20:
                    interactions.append(
                        {
                            "type": "symbiosis",
                            "species": [left["species_id"], right["species_id"]],
                            "asset": left["asset"],
                            "basis": "independent positive research fitness across distinct claim kinds",
                        }
                    )
                if len(interactions) >= 64:
                    break
            if len(interactions) >= 64:
                break

        active_species = [row for row in species if row["stage"] != "retired"]
        retired_species = [row for row in species if row["stage"] == "retired"]
        for parasite in retired_species:
            hosts = [
                host for host in active_species
                if host["asset"] == parasite["asset"] and host["fitness_credit"] >= 0.20
            ]
            if hosts:
                host = max(hosts, key=lambda row: row["fitness_credit"])
                interactions.append({
                    "type": "parasitic_drag",
                    "parasite": parasite["species_id"],
                    "host": host["species_id"],
                    "asset": parasite["asset"],
                    "basis": "retired negative-fitness research species previously competed for the same asset attention",
                })
                if len(interactions) >= 64:
                    break

        alpha_food_web = sorted(
            [row for row in species if row["stage"] != "retired" and row["alpha_mass"] > 0],
            key=lambda row: (row["alpha_mass"], row["fitness_credit"], row["evidence_count"]),
            reverse=True,
        )[:20]
        genesis = [
            {
                "species_id": row["species_id"],
                "asset": row["asset"],
                "origin_claim_id": row["origin_claim_id"],
                "reason": "repeated ontology candidate survived observed shadow outcomes",
                "recommended_action": "open bounded independent engine-design study",
                "automatic_engine_creation": False,
            }
            for row in species
            if row["kind"] == "ontology_candidate"
            and row["stage"] == "surviving_shadow"
            and row["evidence_count"] >= 3
        ][:12]
        extinct = [row for row in species if row["stage"] == "retired"]

        return {
            "species": species,
            "species_count": len(species),
            "claim_outcome_count": int(outcome_count),
            "interactions": interactions,
            "alpha_food_web": alpha_food_web,
            "extinct_species": extinct,
            "cognitive_genesis_candidates": genesis,
            "contracts": {
                "speciation_requires_observed_positive_fitness": True,
                "extinction_requires_repeated_negative_observed_fitness": True,
                "predation_and_symbiosis_are_research_relationships_only": True,
                "cognitive_genesis_never_auto_creates_production_code": True,
            },
            "authority": authority_block(),
        }

    def observation(self, observation_id: str) -> dict[str, Any]:
        with _LOCK, self._connect() as con:
            row = con.execute("SELECT * FROM observations WHERE observation_id=?", (observation_id,)).fetchone()
            if not row:
                raise ValueError("unknown PANTHEON observation")
            claim_rows = con.execute("SELECT * FROM claims WHERE observation_id=? ORDER BY rowid", (observation_id,)).fetchall()
        agent_claims, deliberation = self._agent_claim_state(observation_id)
        visible_agent_claims = agent_claims if deliberation["claim_bodies_visible"] else [
            {
                "claim_id": item["claim_id"],
                "agent_id": item["agent_id"],
                "role": item["role"],
                "committed": True,
                "claim": None,
                "created_at": item["created_at"],
            }
            for item in agent_claims
        ]
        return {
            "observation_id": row["observation_id"],
            "observed_at": row["observed_at"],
            "asset": row["asset"],
            "horizon_ms": row["horizon_ms"],
            "source_commit": row["source_commit"],
            "input": json.loads(row["payload_json"]),
            "analysis": json.loads(row["analysis_json"]),
            "agent_claims": visible_agent_claims,
            "deliberation": deliberation,
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
                "SELECT COUNT(*) AS observations,(SELECT COUNT(*) FROM claims) AS claims,(SELECT COUNT(*) FROM agent_claims) AS agent_claims,(SELECT COUNT(*) FROM sentinel_cells) AS cells FROM observations"
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
        ecology = self._ecology_snapshot(limit=100)
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
            "counts": {"observations": counts["observations"], "claims": counts["claims"], "agent_claims": counts["agent_claims"], "sentinel_cells": counts["cells"]},
            "sentinel_cells": cells,
            "engine_catalog": catalog,
            "faculty_names": list(FACULTIES),
            "ecology": ecology,
            "latest": latest,
            "observations": observations,
            "authority": authority_block(),
            "truth_contract": {
                "research_shadow_only": True,
                "no_direct_agent_trading": True,
                "no_forced_consensus": True,
                "oracle_parallax_dreamstate_ownership_preserved": True,
                "risk_kernel_remains_external_hard_gate": True,
                "aether_evolution_requires_observed_claim_outcomes": True,
                "cognitive_genesis_never_auto_creates_production_code": True,
            },
        }
