"""Evidence ancestry and effective-independence accounting for APEX Ω."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class _Node:
    evidence_id: str
    dependencies: tuple[str, ...]
    root_key: str


class EvidenceAncestry:
    def __init__(self) -> None:
        self._nodes: dict[str, _Node] = {}

    @staticmethod
    def _text(value: Any, field: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} must be a non-empty string")
        return value.strip()

    @classmethod
    def _root_key(cls, evidence: Mapping[str, Any], evidence_id: str) -> str:
        source = evidence.get("source")
        if not isinstance(source, Mapping):
            return f"evidence:{evidence_id}"
        record = str(source.get("source_record_id") or "").strip()
        if not record:
            return f"evidence:{evidence_id}"
        subsystem = str(source.get("subsystem") or "").strip()
        repo = str(source.get("source_repo") or "").strip()
        commit = str(source.get("source_commit") or "").strip()
        return f"source:{subsystem}|{repo}|{commit}|{record}"

    def add(self, evidence: Mapping[str, Any]) -> None:
        if not isinstance(evidence, Mapping):
            raise ValueError("evidence must be an object")
        eid = self._text(evidence.get("evidence_id"), "evidence_id")
        raw_deps = evidence.get("dependencies", [])
        if not isinstance(raw_deps, list):
            raise ValueError("dependencies must be a list")
        deps = tuple(self._text(dep, "dependency") for dep in raw_deps)
        if len(set(deps)) != len(deps):
            raise ValueError("dependencies must be unique")
        node = _Node(eid, deps, self._root_key(evidence, eid))
        prior = self._nodes.get(eid)
        if prior is not None and prior != node:
            raise ValueError("evidence ancestry identity collision")
        self._nodes[eid] = node

    def _cycle_nodes(self, start: str) -> set[str]:
        visited: set[str] = set()
        active: list[str] = []
        active_set: set[str] = set()
        cycles: set[str] = set()
        def visit(eid: str) -> None:
            if eid in active_set:
                idx = active.index(eid)
                cycles.update(active[idx:])
                return
            if eid in visited:
                return
            visited.add(eid)
            node = self._nodes.get(eid)
            if node is None:
                return
            active.append(eid)
            active_set.add(eid)
            for dep in node.dependencies:
                visit(dep)
            active.pop()
            active_set.remove(eid)
        visit(start)
        return cycles

    def detect_cycle(self, evidence_id: str) -> bool:
        return bool(self._cycle_nodes(self._text(evidence_id, "evidence_id")))

    def _collect(self, start: str) -> tuple[set[str], set[str], set[str]]:
        roots: set[str] = set()
        missing: set[str] = set()
        cycles = self._cycle_nodes(start)
        if cycles:
            return roots, missing, cycles
        visited: set[str] = set()
        def walk(eid: str) -> None:
            if eid in visited:
                return
            visited.add(eid)
            node = self._nodes.get(eid)
            if node is None:
                missing.add(eid)
                return
            if not node.dependencies:
                roots.add(node.root_key)
                return
            for dep in node.dependencies:
                walk(dep)
        walk(start)
        return roots, missing, cycles

    def roots(self, evidence_id: str) -> frozenset[str]:
        eid = self._text(evidence_id, "evidence_id")
        roots, missing, cycles = self._collect(eid)
        if cycles:
            raise ValueError("evidence ancestry cycle detected")
        if missing:
            raise ValueError("missing evidence dependency: " + ", ".join(sorted(missing)))
        return frozenset(roots)

    def effective_support(self, evidence_ids: Sequence[str]) -> dict[str, Any]:
        if isinstance(evidence_ids, (str, bytes)):
            raise ValueError("evidence_ids must be a sequence of ids")
        requested = [self._text(eid, "evidence_id") for eid in evidence_ids]
        nominal = len(requested)
        all_roots: set[str] = set()
        missing: set[str] = set()
        cycles: set[str] = set()
        for eid in requested:
            roots, miss, cyc = self._collect(eid)
            all_roots.update(roots)
            missing.update(miss)
            cycles.update(cyc)
        effective = len(all_roots)
        overlap = 0.0 if nominal == 0 else max(0.0, min(1.0, 1.0 - (effective / nominal)))
        semantic_duplicate_count = max(0, nominal - len(all_roots)) if not missing and not cycles else 0
        return {
            "nominal_support": nominal,
            "effective_independent_families": effective,
            "overlap_ratio": overlap,
            "semantic_duplicate_count": semantic_duplicate_count,
            "root_ids": sorted(all_roots),
            "missing_dependencies": sorted(missing),
            "cycle_evidence_ids": sorted(cycles),
            "integrity_ok": not missing and not cycles,
        }
