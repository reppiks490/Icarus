"""ASCENDANCY architecture-genome contracts and deterministic research compiler.

The genome makes ICARUS research topology explicit and reproducible.  Compiling
one creates a *research plan*, not an executable production strategy.  No path
in this module grants broker or production-decision authority.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
from collections import defaultdict
from typing import Any, Iterable, Mapping, Sequence

SCHEMA_VERSION = "icarus-ascendancy-genome-v1"
COMPILED_SCHEMA_VERSION = "icarus-ascendancy-compiled-genome-v1"

NODE_KINDS = {"native", "foreign_lens", "generated", "hybrid"}
LATENCY_TIERS = {"hot", "near", "online", "research", "retrain"}
OBJECTIVE_DIRECTIONS = {"max", "min"}
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA64 = re.compile(r"^[0-9a-f]{64}$")


def _text(value: Any, name: str, limit: int = 240) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    out = value.strip()
    if not out:
        raise ValueError(f"{name} is required")
    if len(out) > limit:
        raise ValueError(f"{name} exceeds {limit} characters")
    return out


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"{name} must be a finite number")
    return out


def _positive_int(value: Any, name: str, *, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if value < 1 or value > maximum:
        raise ValueError(f"{name} must be between 1 and {maximum}")
    return value


def _json_value(value: Any, name: str, *, max_bytes: int = 65536) -> Any:
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as ex:
        raise ValueError(f"{name} must be finite JSON") from ex
    if len(raw.encode("utf-8")) > max_bytes:
        raise ValueError(f"{name} exceeds {max_bytes} bytes")
    return value


def _hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _source_commit(value: Any) -> str:
    out = _text(value, "source_commit", 40).lower()
    if not _SHA40.fullmatch(out):
        raise ValueError("source_commit must be an exact 40-character Git SHA")
    return out


def _parent_id(value: Any) -> str:
    out = _text(value, "parent_genome_id", 64).lower()
    if not _SHA64.fullmatch(out):
        raise ValueError("parent_genome_id must be a 64-character genome hash")
    return out


def _normalize_node(item: Any) -> dict[str, Any]:
    if not isinstance(item, Mapping):
        raise ValueError("genome node must be an object")
    node_id = _text(item.get("id"), "node id", 96)
    subsystem = _text(item.get("subsystem"), "node subsystem", 160)
    kind = _text(item.get("kind"), "node kind", 40).lower()
    tier = _text(item.get("tier"), "node tier", 40).lower()
    if kind not in NODE_KINDS:
        raise ValueError(f"unsupported node kind: {kind}")
    if tier not in LATENCY_TIERS:
        raise ValueError(f"unsupported node tier: {tier}")

    config = dict(item.get("config") or {})
    _json_value(config, "node config", max_bytes=32768)
    row: dict[str, Any] = {
        "id": node_id,
        "subsystem": subsystem,
        "kind": kind,
        "tier": tier,
        "config": config,
    }
    if kind == "native":
        row["isolated"] = bool(item.get("isolated", False))
        if item.get("adapter_id") is not None:
            row["adapter_id"] = _text(item.get("adapter_id"), "adapter_id", 160)
    else:
        adapter = item.get("adapter_id")
        if not adapter:
            raise ValueError(f"{kind} node requires an explicit adapter_id")
        if item.get("isolated") is not True:
            raise ValueError(f"{kind} node adapter must be isolated")
        row["adapter_id"] = _text(adapter, "adapter_id", 160)
        row["isolated"] = True
    return row


def _normalize_edge(item: Any, node_ids: set[str]) -> dict[str, str]:
    if not isinstance(item, Mapping):
        raise ValueError("genome edge must be an object")
    source = _text(item.get("source"), "edge source", 96)
    target = _text(item.get("target"), "edge target", 96)
    relation = _text(item.get("relation"), "edge relation", 96)
    if source not in node_ids or target not in node_ids:
        raise ValueError("genome edge references an unknown node")
    if source == target:
        raise ValueError("genome self loop is not allowed")
    return {"source": source, "target": target, "relation": relation}


def _normalize_evaluation_contract(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("evaluation_contract must be an object")
    raw_objectives = value.get("objectives")
    if not isinstance(raw_objectives, Sequence) or isinstance(raw_objectives, (str, bytes)) or not raw_objectives:
        raise ValueError("evaluation_contract requires objectives")
    if len(raw_objectives) > 32:
        raise ValueError("evaluation_contract has too many objectives")

    objectives: list[dict[str, str]] = []
    names: set[str] = set()
    for raw in raw_objectives:
        if not isinstance(raw, Mapping):
            raise ValueError("evaluation objective must be an object")
        name = _text(raw.get("name"), "objective name", 96)
        direction = _text(raw.get("direction"), "objective direction", 8).lower()
        if direction not in OBJECTIVE_DIRECTIONS:
            raise ValueError("objective direction must be max or min")
        if name in names:
            raise ValueError("duplicate evaluation objective")
        names.add(name)
        objectives.append({"name": name, "direction": direction})
    objectives.sort(key=lambda row: row["name"])

    raw_descriptors = value.get("descriptor_keys") or []
    if not isinstance(raw_descriptors, Sequence) or isinstance(raw_descriptors, (str, bytes)):
        raise ValueError("descriptor_keys must be a list")
    descriptors = sorted({_text(x, "descriptor key", 96) for x in raw_descriptors})
    if len(descriptors) > 32:
        raise ValueError("too many descriptor_keys")
    if value.get("protected_holdout_required") is not True:
        raise ValueError("evaluation_contract must require a protected holdout")

    contract = {
        "objectives": objectives,
        "descriptor_keys": descriptors,
        "protected_holdout_required": True,
    }
    contract["contract_hash"] = _hash(contract)
    return contract


def _normalize_budget(value: Any) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError("resource_budget must be an object")
    evaluations = _positive_int(value.get("max_evaluations"), "max_evaluations", maximum=10_000_000)
    wall = _positive_int(value.get("max_wall_seconds"), "max_wall_seconds", maximum=31_536_000)
    cost = _finite(value.get("max_cost_units"), "max_cost_units")
    if cost < 0.0 or cost > 1_000_000_000.0:
        raise ValueError("max_cost_units is outside the supported range")
    return {
        "max_evaluations": evaluations,
        "max_wall_seconds": wall,
        "max_cost_units": cost,
    }


def normalize_genome(body: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and canonicalize one architecture genome.

    List ordering that has no graph semantics is canonicalized so the same
    architecture receives the same content identity.
    """
    if not isinstance(body, Mapping):
        raise ValueError("genome must be an object")

    source_repo = _text(body.get("source_repo"), "source_repo", 180)
    source_commit = _source_commit(body.get("source_commit"))

    raw_parents = body.get("parent_genome_ids") or []
    if not isinstance(raw_parents, Sequence) or isinstance(raw_parents, (str, bytes)):
        raise ValueError("parent_genome_ids must be a list")
    parents = sorted({_parent_id(x) for x in raw_parents})
    if len(parents) > 64:
        raise ValueError("too many parent_genome_ids")

    raw_nodes = body.get("nodes")
    if not isinstance(raw_nodes, Sequence) or isinstance(raw_nodes, (str, bytes)) or not raw_nodes:
        raise ValueError("genome requires at least one node")
    if len(raw_nodes) > 256:
        raise ValueError("genome has too many nodes")
    nodes = [_normalize_node(x) for x in raw_nodes]
    node_ids = [row["id"] for row in nodes]
    if len(node_ids) != len(set(node_ids)):
        raise ValueError("duplicate genome node id")
    nodes.sort(key=lambda row: row["id"])
    node_id_set = set(node_ids)

    raw_edges = body.get("edges") or []
    if not isinstance(raw_edges, Sequence) or isinstance(raw_edges, (str, bytes)):
        raise ValueError("edges must be a list")
    if len(raw_edges) > 2048:
        raise ValueError("genome has too many edges")
    edges = [_normalize_edge(x, node_id_set) for x in raw_edges]
    edge_keys = [(x["source"], x["target"], x["relation"]) for x in edges]
    if len(edge_keys) != len(set(edge_keys)):
        raise ValueError("duplicate genome edge")
    edges.sort(key=lambda row: (row["source"], row["target"], row["relation"]))

    mutation_value = body.get("mutation")
    if not isinstance(mutation_value, Mapping):
        raise ValueError("mutation must be an object")
    mutation = {
        "operator": _text(mutation_value.get("operator"), "mutation operator", 96),
        "target": _text(mutation_value.get("target"), "mutation target", 160),
        "rationale": _text(mutation_value.get("rationale"), "mutation rationale", 1000),
    }
    extras = mutation_value.get("details")
    if extras is not None:
        mutation["details"] = _json_value(dict(extras) if isinstance(extras, Mapping) else extras, "mutation details")

    raw_falsifiers = body.get("falsifiers")
    if not isinstance(raw_falsifiers, Sequence) or isinstance(raw_falsifiers, (str, bytes)) or not raw_falsifiers:
        raise ValueError("genome requires at least one falsifier")
    falsifiers = sorted({_text(x, "falsifier", 600) for x in raw_falsifiers})
    if len(falsifiers) > 64:
        raise ValueError("too many falsifiers")

    resource_budget = _normalize_budget(body.get("resource_budget"))
    evaluation_contract = _normalize_evaluation_contract(body.get("evaluation_contract"))

    normalized: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "source_repo": source_repo,
        "source_commit": source_commit,
        "parent_genome_ids": parents,
        "nodes": nodes,
        "edges": edges,
        "mutation": mutation,
        "falsifiers": falsifiers,
        "resource_budget": resource_budget,
        "evaluation_contract": evaluation_contract,
        "execution_authorized": False,
        "production_decision_authorized": False,
    }
    normalized["genome_id"] = _hash(normalized)
    return normalized


def genome_id(body: Mapping[str, Any]) -> str:
    return str(normalize_genome(body)["genome_id"])


def _topological_layers(nodes: Sequence[Mapping[str, Any]], edges: Sequence[Mapping[str, Any]]) -> list[list[str]]:
    ids = [str(row["id"]) for row in nodes]
    adjacency: dict[str, set[str]] = {node_id: set() for node_id in ids}
    indegree: dict[str, int] = {node_id: 0 for node_id in ids}
    for edge in edges:
        source = str(edge["source"])
        target = str(edge["target"])
        if target not in adjacency[source]:
            adjacency[source].add(target)
            indegree[target] += 1

    layers: list[list[str]] = []
    remaining = set(ids)
    while remaining:
        layer = sorted(node_id for node_id in remaining if indegree[node_id] == 0)
        if not layer:
            raise ValueError("genome graph contains a cycle")
        layers.append(layer)
        for source in layer:
            remaining.remove(source)
            for target in sorted(adjacency[source]):
                indegree[target] -= 1
    return layers


def compile_genome(
    body: Mapping[str, Any],
    *,
    available_native_subsystems: Iterable[str],
) -> dict[str, Any]:
    """Compile a genome into a deterministic, non-executing research plan."""
    genome = normalize_genome(body)
    available = {str(x).strip() for x in available_native_subsystems if str(x).strip()}
    for node in genome["nodes"]:
        if node["kind"] == "native" and node["subsystem"] not in available:
            raise ValueError(f"unknown native subsystem: {node['subsystem']}")

    layers = _topological_layers(genome["nodes"], genome["edges"])
    plan = {
        "schema_version": COMPILED_SCHEMA_VERSION,
        "genome_id": genome["genome_id"],
        "source_repo": genome["source_repo"],
        "source_commit": genome["source_commit"],
        "layers": layers,
        "node_count": len(genome["nodes"]),
        "edge_count": len(genome["edges"]),
        "resource_budget": genome["resource_budget"],
        "evaluation_contract_hash": genome["evaluation_contract"]["contract_hash"],
        "production_bindings": [],
        "status": "COMPILED_RESEARCH_ONLY",
        "execution_authorized": False,
        "production_decision_authorized": False,
    }
    plan["runtime_hash"] = _hash(plan)
    return plan
