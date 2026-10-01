"""Deterministic causal evidence graph projection for ICARUS.

The graph is derived from already-recorded Brain events and settled Performance
Proof statistics. It does not invent evidence, mutate research state, promote a
candidate, or authorize production/execution.
"""
from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from typing import Any, Iterable, Mapping

_SHA40 = re.compile(r"^[0-9a-f]{40}$")


def _text(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _node_id(kind: str, key: str) -> str:
    digest = hashlib.sha256(f"{kind}\0{key}".encode("utf-8")).hexdigest()
    return f"{kind}:{digest[:24]}"


def _source_revision(event: Mapping[str, Any]) -> tuple[str, str] | None:
    repo = _text(event.get("source_repo"))
    commit = _text(event.get("source_commit")).lower()
    if not repo or not _SHA40.fullmatch(commit):
        return None
    return repo, commit


def build_evidence_graph(
    events: Iterable[Mapping[str, Any]],
    proof_snapshot: Mapping[str, Any] | None = None,
    *,
    max_events: int = 1000,
) -> dict[str, Any]:
    """Project immutable observations into a compact evidence/provenance graph."""
    if isinstance(max_events, bool) or not isinstance(max_events, int) or not 1 <= max_events <= 10000:
        raise ValueError("max_events must be an integer within [1,10000]")

    rows = [x for x in events if isinstance(x, Mapping)][-max_events:]
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[tuple[str, str, str], dict[str, Any]] = {}
    evidence_events: dict[str, set[str]] = defaultdict(set)
    evidence_sources: dict[str, set[str]] = defaultdict(set)
    candidate_rows: dict[str, dict[str, Any]] = {}

    def add_node(node_id: str, kind: str, label: str, **extra: Any) -> None:
        current = nodes.get(node_id)
        payload = {"id": node_id, "kind": kind, "label": label}
        payload.update(extra)
        if current is None:
            nodes[node_id] = payload
        else:
            for key, value in extra.items():
                if key not in current or current[key] in (None, "", [], {}):
                    current[key] = value

    def add_edge(source: str, relation: str, target: str, **extra: Any) -> None:
        key = (source, relation, target)
        if key not in edges:
            payload = {"source": source, "relation": relation, "target": target}
            payload.update(extra)
            edges[key] = payload

    for event in rows:
        event_id = _text(event.get("id"))
        if not event_id:
            continue
        event_node = f"event:{event_id}"
        kind = _text(event.get("kind")).lower() or "event"
        subject = _text(event.get("subject"))
        status = _text(event.get("status")).lower()
        recorded_at = _text(event.get("recorded_at"))
        add_node(
            event_node,
            "event",
            _text(event.get("summary")) or event_id,
            event_kind=kind,
            status=status,
            recorded_at=recorded_at,
        )

        source = _source_revision(event)
        source_node = None
        if source:
            repo, commit = source
            source_key = f"{repo}@{commit}"
            source_node = _node_id("source", source_key)
            add_node(source_node, "source_revision", source_key, repository=repo, commit=commit)
            add_edge(event_node, "SOURCED_FROM", source_node)

        if subject:
            subject_node = _node_id("subject", subject.lower())
            add_node(subject_node, "subject", subject)
            add_edge(event_node, "ASSERTS", subject_node)

        candidate_id = _text(event.get("candidate_id"))
        if candidate_id:
            candidate_node = _node_id("candidate", candidate_id)
            add_node(candidate_node, "candidate", candidate_id)
            add_edge(event_node, "UPDATES_CANDIDATE", candidate_node)
            row = candidate_rows.setdefault(candidate_id, {
                "candidate_id": candidate_id,
                "event_ids": set(),
                "source_revisions": set(),
                "evidence_ids": set(),
                "regimes": set(),
                "verified_gates": set(),
                "latest_stage": "",
                "latest_status": "",
                "latest_recorded_at": "",
            })
            row["event_ids"].add(event_id)
            if source:
                row["source_revisions"].add(f"{source[0]}@{source[1]}")
            if recorded_at >= row["latest_recorded_at"]:
                row["latest_recorded_at"] = recorded_at
                row["latest_stage"] = _text(event.get("stage"))
                row["latest_status"] = status

            regimes = event.get("regimes")
            if isinstance(regimes, list):
                for raw in regimes:
                    regime = _text(raw)
                    if not regime:
                        continue
                    regime_node = _node_id("regime", regime.lower())
                    add_node(regime_node, "regime", regime)
                    add_edge(candidate_node, "VALID_FOR_REGIME", regime_node)
                    row["regimes"].add(regime)

            validation = event.get("validation")
            if isinstance(validation, Mapping):
                for gate, value in validation.items():
                    if value is not True:
                        continue
                    gate_name = _text(gate)
                    if not gate_name:
                        continue
                    gate_node = _node_id("gate", gate_name)
                    add_node(gate_node, "validation_gate", gate_name)
                    add_edge(candidate_node, "VERIFIED_GATE", gate_node)
                    row["verified_gates"].add(gate_name)

        evidence = event.get("evidence")
        if isinstance(evidence, list):
            for raw in evidence:
                item = _text(raw)
                if not item:
                    continue
                evidence_node = _node_id("evidence", item.lower())
                add_node(evidence_node, "evidence", item)
                add_edge(event_node, "CITES", evidence_node)
                evidence_events[evidence_node].add(event_id)
                if source_node:
                    evidence_sources[evidence_node].add(source_node)
                if candidate_id:
                    candidate_rows[candidate_id]["evidence_ids"].add(evidence_node)
                    add_edge(_node_id("candidate", candidate_id), "SUPPORTED_BY", evidence_node)

    proof = proof_snapshot if isinstance(proof_snapshot, Mapping) else {}
    proof_rows = proof.get("candidate_statistics")
    if isinstance(proof_rows, list):
        for stat in proof_rows:
            if not isinstance(stat, Mapping):
                continue
            candidate_id = _text(stat.get("candidate_id"))
            asset = _text(stat.get("asset")).upper()
            regime = _text(stat.get("regime"))
            definition = _text(stat.get("success_definition"))
            horizon = stat.get("horizon_seconds")
            if not candidate_id or not asset or not regime or not definition or isinstance(horizon, bool) or not isinstance(horizon, int):
                continue
            candidate_node = _node_id("candidate", candidate_id)
            add_node(candidate_node, "candidate", candidate_id)
            scope_key = f"{asset}|{regime}|{definition}|{horizon}"
            scope_node = _node_id("proof_scope", scope_key)
            add_node(
                scope_node,
                "proof_scope",
                f"{asset} / {regime} / {horizon}s",
                asset=asset,
                regime=regime,
                horizon_seconds=horizon,
                success_definition=definition,
                settled=stat.get("settled"),
                successes=stat.get("successes"),
                success_rate=stat.get("success_rate"),
                brier_score=stat.get("brier_score"),
                outcome_coverage=stat.get("outcome_coverage"),
                closed_regime_sample=stat.get("closed_regime_sample") is True,
            )
            add_edge(candidate_node, "MEASURED_IN", scope_node)

    duplicate_nodes = {
        node_id for node_id, event_ids in evidence_events.items()
        if len(event_ids) > 1
    }
    independently_corroborated = {
        node_id for node_id, source_ids in evidence_sources.items()
        if len(source_ids) > 1
    }

    candidate_summary = []
    for candidate_id, row in sorted(candidate_rows.items()):
        candidate_summary.append({
            "candidate_id": candidate_id,
            "event_count": len(row["event_ids"]),
            "source_revision_count": len(row["source_revisions"]),
            "evidence_count": len(row["evidence_ids"]),
            "regimes": sorted(row["regimes"]),
            "verified_gates": sorted(row["verified_gates"]),
            "latest_stage": row["latest_stage"],
            "latest_status": row["latest_status"],
            "latest_recorded_at": row["latest_recorded_at"],
        })

    evidence_summary = []
    for node_id in sorted(evidence_events):
        node = nodes[node_id]
        evidence_summary.append({
            "evidence_id": node_id,
            "label": node["label"],
            "event_count": len(evidence_events[node_id]),
            "source_revision_count": len(evidence_sources[node_id]),
            "duplicate_reference": node_id in duplicate_nodes,
            "independently_corroborated": node_id in independently_corroborated,
        })

    ordered_nodes = [nodes[k] for k in sorted(nodes)]
    ordered_edges = [edges[k] for k in sorted(edges)]
    return {
        "schema_version": "icarus-evidence-graph-v1",
        "metrics": {
            "event_count": sum(1 for x in ordered_nodes if x["kind"] == "event"),
            "node_count": len(ordered_nodes),
            "edge_count": len(ordered_edges),
            "candidate_count": sum(1 for x in ordered_nodes if x["kind"] == "candidate"),
            "source_revision_count": sum(1 for x in ordered_nodes if x["kind"] == "source_revision"),
            "evidence_count": sum(1 for x in ordered_nodes if x["kind"] == "evidence"),
            "duplicate_evidence_count": len(duplicate_nodes),
            "independently_corroborated_evidence_count": len(independently_corroborated),
        },
        "nodes": ordered_nodes,
        "edges": ordered_edges,
        "candidates": candidate_summary,
        "evidence": evidence_summary,
        "execution_authorized": False,
        "production_decision_authorized": False,
        "rule": "Graph edges describe recorded evidence/provenance relationships only; repeated evidence is not counted as independent corroboration unless it comes from distinct exact source revisions.",
    }
