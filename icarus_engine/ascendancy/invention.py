"""Bounded typed invention engine for ICARUS ASCENDANCY.

The engine searches a finite grammar of research transformations and emits
reproducible *untested hypotheses*.  It does not execute generated code, claim
edge, grant trading authority, or bypass the Candidate Foundry / protected
qualification path.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sqlite3
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "icarus-ascendancy-invention-v1"
LAB_SCHEMA_VERSION = "icarus-ascendancy-invention-lab-v1"
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA64 = re.compile(r"^[0-9a-f]{64}$")
_LOCK = threading.RLock()

EVIDENCE_CLASSES = {"observed", "derived", "reconstructed", "inferred", "unavailable"}

_PRIMITIVES = (
    {
        "id": "information_clock",
        "family": "market_clock",
        "requires": ("price_series", "information_rate"),
        "produces": "market_clock",
        "cost_units": 1.0,
        "description": "Re-parameterize market evolution by accumulated information activity.",
    },
    {
        "id": "volatility_clock",
        "family": "market_clock",
        "requires": ("price_series", "volatility"),
        "produces": "market_clock",
        "cost_units": 1.0,
        "description": "Re-parameterize market evolution by realized-volatility activity.",
    },
    {
        "id": "phase_embedding",
        "family": "dynamical_systems",
        "requires": ("price_series", "market_clock"),
        "produces": "phase_state",
        "cost_units": 1.5,
        "description": "Embed price and a transformed market clock into a phase-state representation.",
    },
    {
        "id": "spectral_energy",
        "family": "signal_processing",
        "requires": ("returns",),
        "produces": "spectral_state",
        "cost_units": 1.5,
        "description": "Represent return dynamics by bounded spectral-energy structure.",
    },
    {
        "id": "wavelet_multiscale",
        "family": "signal_processing",
        "requires": ("returns",),
        "produces": "multiscale_state",
        "cost_units": 2.0,
        "description": "Represent return dynamics across localized time-frequency scales.",
    },
    {
        "id": "topological_persistence",
        "family": "topology",
        "requires": ("multiscale_state",),
        "produces": "topology_state",
        "cost_units": 2.0,
        "description": "Summarize persistent geometric structure in a multiscale state.",
    },
    {
        "id": "state_space_filter",
        "family": "state_space",
        "requires": ("returns", "volatility"),
        "produces": "latent_state",
        "cost_units": 2.0,
        "description": "Construct a bounded latent state from returns and volatility.",
    },
    {
        "id": "information_geometry",
        "family": "information_geometry",
        "requires": ("latent_state",),
        "produces": "geometry_state",
        "cost_units": 2.0,
        "description": "Measure local statistical-manifold displacement in latent state.",
    },
    {
        "id": "graph_coupling",
        "family": "graph_systems",
        "requires": ("returns", "cross_asset_returns"),
        "produces": "graph_state",
        "cost_units": 2.5,
        "description": "Represent dynamic cross-asset coupling as a graph state.",
    },
    {
        "id": "optimal_transport_shift",
        "family": "distribution_geometry",
        "requires": ("returns", "reference_distribution"),
        "produces": "transport_state",
        "cost_units": 2.5,
        "description": "Measure distributional displacement through optimal-transport geometry.",
    },
    {
        "id": "control_residual",
        "family": "control_theory",
        "requires": ("latent_state", "market_clock"),
        "produces": "control_residual_state",
        "cost_units": 2.5,
        "description": "Represent deviation from a bounded expected state-transition model.",
    },
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _text(value: Any, name: str, limit: int = 2000) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    out = value.strip()
    if not out:
        raise ValueError(f"{name} is required")
    if len(out) > limit:
        raise ValueError(f"{name} exceeds {limit} characters")
    return out


def _canonical(value: Any, name: str = "value", max_bytes: int = 262144) -> str:
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


def _bounded_int(value: Any, name: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if value < low or value > high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return value


def _normalize_contract(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("evaluation_contract must be an object")
    raw = value.get("objectives")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)) or not raw:
        raise ValueError("evaluation_contract requires objectives")
    objectives: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, Mapping):
            raise ValueError("evaluation objective must be an object")
        name = _text(item.get("name"), "objective name", 96)
        direction = _text(item.get("direction"), "objective direction", 8).lower()
        if direction not in {"max", "min"}:
            raise ValueError("objective direction must be max or min")
        if name in seen:
            raise ValueError("duplicate evaluation objective")
        seen.add(name)
        objectives.append({"name": name, "direction": direction})
    objectives.sort(key=lambda x: x["name"])
    keys = value.get("descriptor_keys") or []
    if not isinstance(keys, Sequence) or isinstance(keys, (str, bytes)):
        raise ValueError("descriptor_keys must be a list")
    descriptor_keys = sorted({_text(x, "descriptor key", 96) for x in keys})
    if value.get("protected_holdout_required") is not True:
        raise ValueError("evaluation_contract must require a protected holdout")
    out = {
        "objectives": objectives,
        "descriptor_keys": descriptor_keys,
        "protected_holdout_required": True,
    }
    out["contract_hash"] = _hash(out)
    return out


def _normalize_budget(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("resource_budget must be an object")
    max_evaluations = _bounded_int(value.get("max_evaluations"), "max_evaluations", 1, 10_000_000)
    max_wall_seconds = _bounded_int(value.get("max_wall_seconds"), "max_wall_seconds", 1, 31_536_000)
    max_cost_units = _finite(value.get("max_cost_units"), "max_cost_units")
    if max_cost_units < 0 or max_cost_units > 1_000_000_000:
        raise ValueError("max_cost_units is outside the supported range")
    return {
        "max_evaluations": max_evaluations,
        "max_wall_seconds": max_wall_seconds,
        "max_cost_units": max_cost_units,
    }


def primitive_catalog() -> list[dict[str, Any]]:
    """Return the typed primitive grammar with immutable research-only authority."""
    return [
        {
            **{
                "id": row["id"],
                "family": row["family"],
                "requires": list(row["requires"]),
                "produces": row["produces"],
                "cost_units": float(row["cost_units"]),
                "description": row["description"],
            },
            "execution_authorized": False,
            "production_decision_authorized": False,
        }
        for row in _PRIMITIVES
    ]


def _normalize_seed(body: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(body, Mapping):
        raise ValueError("invention seed must be an object")
    if body.get("execution_authorized") not in (None, False):
        raise ValueError("invention seed cannot grant execution authority")
    if body.get("production_decision_authorized") not in (None, False):
        raise ValueError("invention seed cannot grant production authority")

    source_repo = _text(body.get("source_repo"), "source_repo", 180)
    source_commit = _sha(body.get("source_commit"), "source_commit", 40)
    question = _text(body.get("research_question"), "research_question", 4000)
    target_outcome = _text(body.get("target_outcome"), "target_outcome", 160)

    raw_obs = body.get("observations")
    if not isinstance(raw_obs, Sequence) or isinstance(raw_obs, (str, bytes)) or not raw_obs:
        raise ValueError("observations must be a non-empty list")
    observations: list[dict[str, Any]] = []
    roles: set[str] = set()
    for item in raw_obs:
        if not isinstance(item, Mapping):
            raise ValueError("observation must be an object")
        role = _text(item.get("role"), "observation role", 120)
        name = _text(item.get("name"), "observation name", 160)
        evidence_class = _text(item.get("evidence_class"), "evidence_class", 40).lower()
        if evidence_class not in EVIDENCE_CLASSES:
            raise ValueError("unsupported evidence_class")
        if role in {x["role"] for x in observations}:
            raise ValueError("duplicate observation role")
        row = {
            "role": role,
            "name": name,
            "evidence_class": evidence_class,
            "usable_for_invention": evidence_class != "unavailable",
        }
        observations.append(row)
        if row["usable_for_invention"]:
            roles.add(role)
    observations.sort(key=lambda x: x["role"])

    raw_targets = body.get("target_roles")
    if not isinstance(raw_targets, Sequence) or isinstance(raw_targets, (str, bytes)) or not raw_targets:
        raise ValueError("target_roles must be a non-empty list")
    target_roles = sorted({_text(x, "target role", 120) for x in raw_targets})

    raw_parents = body.get("parent_candidate_ids") or []
    if not isinstance(raw_parents, Sequence) or isinstance(raw_parents, (str, bytes)):
        raise ValueError("parent_candidate_ids must be a list")
    parents = sorted({_sha(x, "parent_candidate_id", 64) for x in raw_parents})

    constraints = body.get("constraints")
    if not isinstance(constraints, Mapping):
        raise ValueError("constraints must be an object")
    max_depth = _bounded_int(constraints.get("max_depth"), "max_depth", 1, 5)
    max_candidates = _bounded_int(constraints.get("max_candidates"), "max_candidates", 1, 500)
    max_cost = _finite(constraints.get("max_cost_units"), "max_cost_units")
    if max_cost <= 0 or max_cost > 10_000:
        raise ValueError("max_cost_units is outside the supported range")

    context_value = body.get("context") or {}
    if not isinstance(context_value, Mapping):
        raise ValueError("context must be an object")
    context = dict(context_value)
    _canonical(context, "context", 65536)

    return {
        "schema_version": SCHEMA_VERSION,
        "source_repo": source_repo,
        "source_commit": source_commit,
        "research_question": question,
        "target_outcome": target_outcome,
        "observations": observations,
        "available_roles": sorted(roles),
        "target_roles": target_roles,
        "parent_candidate_ids": parents,
        "constraints": {
            "max_depth": max_depth,
            "max_candidates": max_candidates,
            "max_cost_units": max_cost,
        },
        "evaluation_contract": _normalize_contract(body.get("evaluation_contract")),
        "resource_budget": _normalize_budget(body.get("resource_budget")),
        "context": context,
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


def _blueprint(seed: Mapping[str, Any], chain: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    primitive_ids = [str(x["id"]) for x in chain]
    families = [str(x["family"]) for x in chain]
    cost = sum(float(x["cost_units"]) for x in chain)
    target_role = str(chain[-1]["produces"])
    hypothesis = (
        f"Test whether typed composition {' -> '.join(primitive_ids)} creates "
        f"{target_role} that adds {seed['target_outcome']} beyond the current ICARUS baseline."
    )
    falsifiers = [
        f"protected OOS {seed['target_outcome']} is nonpositive versus the frozen baseline",
        "conditional contribution beyond the current ICARUS representation is nonpositive",
        "the effect disappears under regime-stratified replay or is concentrated in an isolated parameter spike",
        "deterministic replay fails or required evidence is unavailable",
    ]
    semantic = {
        "schema_version": "icarus-ascendancy-invention-blueprint-v1",
        "source_repo": seed["source_repo"],
        "source_commit": seed["source_commit"],
        "research_question": seed["research_question"],
        "target_outcome": seed["target_outcome"],
        "target_role": target_role,
        "primitive_ids": primitive_ids,
        "primitive_families": families,
        "transformations": [
            {
                "id": row["id"],
                "family": row["family"],
                "requires": list(row["requires"]),
                "produces": row["produces"],
                "cost_units": float(row["cost_units"]),
            }
            for row in chain
        ],
        "depth": len(chain),
        "estimated_cost_units": cost,
        "observations": seed["observations"],
        "parent_candidate_ids": seed["parent_candidate_ids"],
        "evaluation_contract": seed["evaluation_contract"],
        "resource_budget": seed["resource_budget"],
        "context": seed["context"],
        "hypothesis": hypothesis,
        "falsifiers": falsifiers,
        "status": "UNTESTED_HYPOTHESIS",
        "edge_claim_established": False,
        "execution_authorized": False,
        "production_decision_authorized": False,
    }
    semantic["blueprint_id"] = _hash(semantic)
    return semantic


def generate_blueprints(body: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Enumerate deterministic typed compositions within a bounded search envelope."""
    seed = _normalize_seed(body)
    max_depth = int(seed["constraints"]["max_depth"])
    max_candidates = int(seed["constraints"]["max_candidates"])
    max_cost = float(seed["constraints"]["max_cost_units"])
    targets = set(seed["target_roles"])

    primitives = [dict(row) for row in _PRIMITIVES]
    start_roles = frozenset(seed["available_roles"])
    queue: deque[tuple[frozenset[str], tuple[str, ...], float]] = deque()
    queue.append((start_roles, tuple(), 0.0))
    primitive_by_id = {str(row["id"]): row for row in primitives}
    seen_states: set[tuple[frozenset[str], tuple[str, ...]]] = {(start_roles, tuple())}
    blueprints: list[dict[str, Any]] = []

    while queue and len(blueprints) < max_candidates:
        roles, chain_ids, cost = queue.popleft()
        if len(chain_ids) >= max_depth:
            continue
        used = set(chain_ids)
        for primitive in primitives:
            pid = str(primitive["id"])
            if pid in used:
                continue
            requires = set(primitive["requires"])
            output = str(primitive["produces"])
            if not requires.issubset(roles):
                continue
            if output in roles:
                continue
            new_cost = cost + float(primitive["cost_units"])
            if new_cost > max_cost:
                continue
            new_roles = frozenset(set(roles) | {output})
            new_chain = chain_ids + (pid,)
            state_key = (new_roles, new_chain)
            if state_key in seen_states:
                continue
            seen_states.add(state_key)
            chain = [primitive_by_id[x] for x in new_chain]
            if output in targets:
                blueprints.append(_blueprint(seed, chain))
                if len(blueprints) >= max_candidates:
                    break
            queue.append((new_roles, new_chain, new_cost))

    blueprints.sort(key=lambda row: (row["depth"], row["primitive_ids"], row["blueprint_id"]))
    return blueprints[:max_candidates]


def to_foundry_candidate(blueprint: Mapping[str, Any]) -> dict[str, Any]:
    """Convert one invention blueprint into a Candidate Foundry proposal."""
    if not isinstance(blueprint, Mapping):
        raise ValueError("blueprint must be an object")
    if blueprint.get("status") != "UNTESTED_HYPOTHESIS":
        raise ValueError("only untested invention blueprints can enter the Candidate Foundry")
    observations = [
        {
            "name": row["name"],
            "evidence_class": row["evidence_class"],
        }
        for row in blueprint.get("observations", [])
        if isinstance(row, Mapping)
    ]
    return {
        "origin": "generated_math",
        "source_repo": blueprint["source_repo"],
        "source_commit": blueprint["source_commit"],
        "title": f"Invention {str(blueprint['blueprint_id'])[:12]} · {blueprint['target_role']}",
        "hypothesis": blueprint["hypothesis"],
        "mechanism": {
            "type": "typed_composition",
            "primitive_ids": list(blueprint["primitive_ids"]),
            "primitive_families": list(blueprint["primitive_families"]),
            "target_role": blueprint["target_role"],
            "transformations": list(blueprint["transformations"]),
        },
        "expected_advantage": {
            "target": blueprint["target_outcome"],
            "direction": "increase",
            "scope": dict(blueprint.get("context") or {}),
        },
        "required_observations": observations,
        "falsifiers": list(blueprint["falsifiers"]),
        "parent_candidate_ids": list(blueprint.get("parent_candidate_ids") or []),
        "parent_genome_ids": [],
        "evaluation_contract": dict(blueprint["evaluation_contract"]),
        "resource_budget": dict(blueprint["resource_budget"]),
        "metadata": {
            "blueprint_id": blueprint["blueprint_id"],
            "research_question": blueprint["research_question"],
            "estimated_cost_units": blueprint["estimated_cost_units"],
            "invention_status": "UNTESTED_HYPOTHESIS",
            "edge_claim_established": False,
        },
        "execution_authorized": False,
        "production_decision_authorized": False,
        "broker_authority": False,
    }


class InventionLab:
    """Durable archive of generated invention blueprints."""

    def __init__(self, base_dir: str | os.PathLike[str]):
        self.base_dir = Path(base_dir)
        self.path = self.base_dir / "research" / "ascendancy_inventions.sqlite3"
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
                CREATE TABLE IF NOT EXISTS blueprints (
                    blueprint_id TEXT PRIMARY KEY,
                    source_repo TEXT NOT NULL,
                    source_commit TEXT NOT NULL,
                    target_role TEXT NOT NULL,
                    depth INTEGER NOT NULL,
                    estimated_cost_units REAL NOT NULL,
                    semantic_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_asc_invention_target
                    ON blueprints(target_role, depth, created_at);
                """
            )

    def close(self) -> None:
        return None

    def generate(self, seed: Mapping[str, Any]) -> dict[str, Any]:
        rows = generate_blueprints(seed)
        now = _utc_now()
        new_count = 0
        with _LOCK, self._connect() as con:
            for row in rows:
                cur = con.execute(
                    """INSERT OR IGNORE INTO blueprints(
                        blueprint_id,source_repo,source_commit,target_role,depth,
                        estimated_cost_units,semantic_json,created_at
                    ) VALUES(?,?,?,?,?,?,?,?)""",
                    (
                        row["blueprint_id"],
                        row["source_repo"],
                        row["source_commit"],
                        row["target_role"],
                        row["depth"],
                        row["estimated_cost_units"],
                        _canonical(row, "blueprint"),
                        now,
                    ),
                )
                new_count += max(0, int(cur.rowcount))
        return {
            "generated_count": len(rows),
            "new_count": new_count,
            "blueprints": rows,
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    def snapshot(self) -> dict[str, Any]:
        with _LOCK, self._connect() as con:
            rows = con.execute(
                "SELECT semantic_json,created_at FROM blueprints ORDER BY depth,blueprint_id"
            ).fetchall()
        blueprints: list[dict[str, Any]] = []
        for row in rows:
            try:
                item = json.loads(row["semantic_json"])
            except (TypeError, json.JSONDecodeError):
                continue
            if isinstance(item, dict):
                item["created_at"] = str(row["created_at"])
                blueprints.append(item)

        family_counts: dict[str, int] = {}
        for row in blueprints:
            for family in row.get("primitive_families", []):
                family_counts[str(family)] = family_counts.get(str(family), 0) + 1

        return {
            "schema_version": LAB_SCHEMA_VERSION,
            "blueprint_count": len(blueprints),
            "blueprints": blueprints,
            "primitive_catalog": primitive_catalog(),
            "family_counts": dict(sorted(family_counts.items())),
            "truth_contract": {
                "generated_blueprint_is_not_validated_edge": True,
                "unavailable_observations_cannot_seed_transformations": True,
                "search_is_bounded_by_depth_candidate_count_and_cost": True,
                "protected_holdout_is_required_before_foundry_validation": True,
                "arbitrary_source_code_execution": False,
            },
            "execution_authorized": False,
            "production_decision_authorized": False,
        }
