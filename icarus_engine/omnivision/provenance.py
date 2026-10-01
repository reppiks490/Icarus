"""Explicit deterministic provenance graph for OMNIVISION research artifacts."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re
from collections import deque

_HASH = re.compile(r"^[0-9a-f]{64}$")
NODE_KINDS = frozenset({
    "source_capability", "raw_evidence", "normalized_observation", "derived_feature",
    "latent_estimate", "dataset_snapshot", "hypothesis", "trial",
    "validation_result", "candidate", "integration_decision",
})
EDGE_KINDS = frozenset({
    "produced_by", "normalized_from", "derived_from", "contradicts", "supersedes",
    "tests", "falsifies", "supports", "duplicates", "depends_on", "invalidates",
})
DEPENDENCY_EDGES = frozenset({
    "produced_by", "normalized_from", "derived_from", "tests", "supports", "depends_on",
})


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


def _metadata(value) -> tuple[tuple[str, str], ...]:
    if type(value) is not tuple:
        raise ValueError("metadata must be a tuple")
    keys = []
    for item in value:
        if type(item) is not tuple or len(item) != 2:
            raise ValueError("metadata entries must be (key, value) tuples")
        key, val = item
        _text(key, "metadata key"); _text(val, "metadata value")
        keys.append(key)
    if len(set(keys)) != len(keys):
        raise ValueError("metadata keys must be unique")
    return value


@dataclass(frozen=True)
class ProvenanceNode:
    node_id: str
    kind: str
    external_id: str
    as_of: int
    content_hash: str
    metadata: tuple[tuple[str, str], ...]

    def __post_init__(self):
        _hash(self.node_id, "node_id")
        if self.kind not in NODE_KINDS:
            raise ValueError("unsupported node kind")
        _text(self.external_id, "external_id")
        _time(self.as_of, "as_of")
        _hash(self.content_hash, "content_hash")
        _metadata(self.metadata)
        if self.node_id != _digest({k: v for k, v in asdict(self).items() if k != "node_id"}):
            raise ValueError("node_id does not match node content")

    @classmethod
    def build(cls, *, kind: str, external_id: str, as_of: int, content_hash: str,
              metadata: tuple[tuple[str, str], ...]) -> "ProvenanceNode":
        body = dict(kind=kind, external_id=external_id, as_of=as_of,
                    content_hash=content_hash, metadata=metadata)
        return cls(node_id=_digest(body), **body)


@dataclass(frozen=True)
class ProvenanceEdge:
    edge_id: str
    kind: str
    source_node_id: str
    target_node_id: str
    run_id: str
    created_at: int
    transform_id: str
    evidence_hashes: tuple[str, ...]
    code_hash: str | None = None
    config_hash: str | None = None

    def __post_init__(self):
        _hash(self.edge_id, "edge_id")
        if self.kind not in EDGE_KINDS:
            raise ValueError("unsupported edge kind")
        _hash(self.source_node_id, "source_node_id")
        _hash(self.target_node_id, "target_node_id")
        if self.source_node_id == self.target_node_id:
            raise ValueError("self edges are not allowed")
        _text(self.run_id, "run_id")
        _time(self.created_at, "created_at")
        _text(self.transform_id, "transform_id")
        if type(self.evidence_hashes) is not tuple or not self.evidence_hashes:
            raise ValueError("evidence_hashes must be a non-empty tuple")
        if len(set(self.evidence_hashes)) != len(self.evidence_hashes):
            raise ValueError("evidence_hashes must be unique")
        for value in self.evidence_hashes:
            _hash(value, "evidence_hash")
        if self.code_hash is not None:
            _hash(self.code_hash, "code_hash")
        if self.config_hash is not None:
            _hash(self.config_hash, "config_hash")
        if self.edge_id != _digest({k: v for k, v in asdict(self).items() if k != "edge_id"}):
            raise ValueError("edge_id does not match edge content")

    @classmethod
    def build(cls, *, kind: str, source_node_id: str, target_node_id: str,
              run_id: str, created_at: int, transform_id: str,
              evidence_hashes: tuple[str, ...], code_hash: str | None = None,
              config_hash: str | None = None) -> "ProvenanceEdge":
        body = dict(
            kind=kind, source_node_id=source_node_id, target_node_id=target_node_id,
            run_id=run_id, created_at=created_at, transform_id=transform_id,
            evidence_hashes=evidence_hashes, code_hash=code_hash, config_hash=config_hash,
        )
        return cls(edge_id=_digest(body), **body)


class ProvenanceDAG:
    def __init__(self):
        self.nodes: dict[str, ProvenanceNode] = {}
        self.edges: dict[str, ProvenanceEdge] = {}
        self._out: dict[str, set[str]] = {}
        self._in: dict[str, set[str]] = {}
        self._dep_out: dict[str, set[str]] = {}
        self._dep_in: dict[str, set[str]] = {}

    def add_node(self, node: ProvenanceNode) -> None:
        if not isinstance(node, ProvenanceNode):
            raise TypeError("node must be ProvenanceNode")
        ProvenanceNode(**asdict(node))
        existing = self.nodes.get(node.node_id)
        if existing is not None and existing != node:
            raise ValueError("node_id collision")
        self.nodes[node.node_id] = node

    def _reachable(self, start: str, target: str) -> bool:
        queue = deque([start]); seen = {start}
        while queue:
            current = queue.popleft()
            if current == target:
                return True
            for nxt in sorted(self._dep_out.get(current, ())):
                if nxt not in seen:
                    seen.add(nxt); queue.append(nxt)
        return False

    def add_edge(self, edge: ProvenanceEdge) -> None:
        if not isinstance(edge, ProvenanceEdge):
            raise TypeError("edge must be ProvenanceEdge")
        ProvenanceEdge(**asdict(edge))
        if edge.source_node_id not in self.nodes or edge.target_node_id not in self.nodes:
            raise ValueError("edge endpoints must already exist")
        existing = self.edges.get(edge.edge_id)
        if existing is not None:
            if existing == edge:
                return
            raise ValueError("edge_id collision")
        if edge.kind in DEPENDENCY_EDGES and self._reachable(edge.target_node_id, edge.source_node_id):
            raise ValueError("dependency edge would create a cycle")
        self.edges[edge.edge_id] = edge
        self._out.setdefault(edge.source_node_id, set()).add(edge.target_node_id)
        self._in.setdefault(edge.target_node_id, set()).add(edge.source_node_id)
        if edge.kind in DEPENDENCY_EDGES:
            self._dep_out.setdefault(edge.source_node_id, set()).add(edge.target_node_id)
            self._dep_in.setdefault(edge.target_node_id, set()).add(edge.source_node_id)

    def _walk(self, start: str, adjacency: dict[str, set[str]]) -> dict[str, int]:
        if start not in self.nodes:
            raise KeyError(start)
        distance = {start: 0}; queue = deque([start])
        while queue:
            current = queue.popleft()
            for nxt in sorted(adjacency.get(current, ())):
                if nxt not in distance:
                    distance[nxt] = distance[current] + 1
                    queue.append(nxt)
        distance.pop(start, None)
        return distance

    def ancestors(self, node_id: str) -> tuple[str, ...]:
        distance = self._walk(node_id, self._dep_in)
        return tuple(sorted(distance, key=lambda item: (-distance[item], item)))

    def descendants(self, node_id: str) -> tuple[str, ...]:
        distance = self._walk(node_id, self._dep_out)
        return tuple(sorted(distance, key=lambda item: (distance[item], item)))

    def shared_ancestors(self, node_ids: tuple[str, ...]) -> tuple[str, ...]:
        if type(node_ids) is not tuple or len(node_ids) < 2:
            raise ValueError("node_ids must contain at least two nodes")
        sets = [set(self.ancestors(node_id)) for node_id in node_ids]
        return tuple(sorted(set.intersection(*sets)))

    def invalidation_closure(self, node_id: str) -> tuple[str, ...]:
        return (node_id, *self.descendants(node_id))

    def snapshot_hash(self) -> str:
        body = {
            "nodes": [asdict(self.nodes[key]) for key in sorted(self.nodes)],
            "edges": [asdict(self.edges[key]) for key in sorted(self.edges)],
        }
        return _digest(body)
