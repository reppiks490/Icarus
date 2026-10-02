"""Quality-diversity search frontier for ASCENDANCY architecture genomes.

This module never converts novelty into trading authority.  It compares only
evaluations produced under the same immutable evaluation contract, keeps the
latest evaluation per genome/contract to avoid cherry-picking, and preserves
lineage/stepping-stone context separately from the active Pareto frontier.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import defaultdict, deque
from datetime import datetime
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "icarus-ascendancy-frontier-v1"
_TERMINAL_STATES = {"RETIRED", "REJECTED"}


def _canonical(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as ex:
        raise ValueError("frontier values must be finite JSON") from ex


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _text(value: Any, name: str, limit: int = 256) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    out = value.strip()
    if not out:
        raise ValueError(f"{name} is required")
    if len(out) > limit:
        raise ValueError(f"{name} exceeds {limit} characters")
    return out


def _finite_metrics(metrics: Mapping[str, Any]) -> dict[str, float]:
    if not isinstance(metrics, Mapping):
        raise ValueError("metrics must be an object")
    out: dict[str, float] = {}
    for key, value in metrics.items():
        name = _text(key, "metric name", 96)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"metric {name} must be finite")
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"metric {name} must be finite")
        out[name] = number
    return dict(sorted(out.items()))


def _objectives(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or not value:
        raise ValueError("evaluation contract requires objectives")
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, Mapping):
            raise ValueError("objective must be an object")
        name = _text(item.get("name"), "objective name", 96)
        direction = _text(item.get("direction"), "objective direction", 8).lower()
        if direction not in {"max", "min"}:
            raise ValueError("objective direction must be max or min")
        if name in seen:
            raise ValueError("duplicate objective")
        seen.add(name)
        out.append({"name": name, "direction": direction})
    return sorted(out, key=lambda row: row["name"])


def dominates(
    left_metrics: Mapping[str, Any],
    right_metrics: Mapping[str, Any],
    objectives: Sequence[Mapping[str, Any]],
) -> bool:
    """Return True only when left is no worse everywhere and better somewhere."""
    left = _finite_metrics(left_metrics)
    right = _finite_metrics(right_metrics)
    specs = _objectives(objectives)
    expected = {row["name"] for row in specs}
    if set(left) != expected or set(right) != expected:
        raise ValueError("dominance comparison requires exact objective metrics")

    strictly_better = False
    for spec in specs:
        name = spec["name"]
        lv = left[name]
        rv = right[name]
        if spec["direction"] == "max":
            if lv < rv:
                return False
            if lv > rv:
                strictly_better = True
        else:
            if lv > rv:
                return False
            if lv < rv:
                strictly_better = True
    return strictly_better


def niche_id(
    evaluation_contract_hash: str,
    descriptors: Mapping[str, Any],
    descriptor_keys: Sequence[str],
) -> str:
    contract_hash = _text(evaluation_contract_hash, "evaluation_contract_hash", 64).lower()
    if len(contract_hash) != 64 or any(c not in "0123456789abcdef" for c in contract_hash):
        raise ValueError("evaluation_contract_hash must be a 64-character hash")
    if not isinstance(descriptors, Mapping):
        raise ValueError("descriptors must be an object")
    keys = sorted({_text(key, "descriptor key", 96) for key in descriptor_keys})
    if set(descriptors) != set(keys):
        raise ValueError("descriptor values must match the evaluation contract exactly")
    values = {key: descriptors[key] for key in keys}
    _canonical(values)
    return _hash({
        "evaluation_contract_hash": contract_hash,
        "descriptors": values,
    })


def _observed_sort_key(value: Any) -> tuple[float, str]:
    text = _text(value, "observed_at", 80)
    probe = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        dt = datetime.fromisoformat(probe)
    except ValueError as ex:
        raise ValueError("observed_at must be ISO-8601") from ex
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("observed_at must include a timezone")
    return (dt.timestamp(), text)


def _descriptor_distance(left: Mapping[str, Any], right: Mapping[str, Any], keys: Sequence[str]) -> float:
    if not keys:
        return 0.0
    different = sum(1 for key in keys if _canonical(left[key]) != _canonical(right[key]))
    return different / len(keys)


def _novelty_scores(candidates: list[dict[str, Any]], descriptor_keys: list[str]) -> dict[str, float]:
    if len(candidates) <= 1:
        return {str(row["genome_id"]): 0.0 for row in candidates}
    out: dict[str, float] = {}
    for row in candidates:
        distances = sorted(
            _descriptor_distance(row["descriptors"], other["descriptors"], descriptor_keys)
            for other in candidates
            if other["genome_id"] != row["genome_id"]
        )
        k = min(5, len(distances))
        out[str(row["genome_id"])] = sum(distances[:k]) / k if k else 0.0
    return out


def _descendants(lineage: Sequence[Mapping[str, Any]]) -> dict[str, list[str]]:
    children: dict[str, set[str]] = defaultdict(set)
    nodes: set[str] = set()
    for edge in lineage:
        if not isinstance(edge, Mapping):
            continue
        parent = str(edge.get("parent_genome_id") or "").strip()
        child = str(edge.get("child_genome_id") or "").strip()
        if not parent or not child or parent == child:
            continue
        children[parent].add(child)
        nodes.add(parent)
        nodes.add(child)

    out: dict[str, list[str]] = {}
    for root in sorted(nodes):
        seen: set[str] = set()
        queue: deque[str] = deque(sorted(children.get(root, set())))
        while queue:
            current = queue.popleft()
            if current in seen:
                continue
            seen.add(current)
            for nxt in sorted(children.get(current, set())):
                if nxt not in seen:
                    queue.append(nxt)
        if seen:
            out[root] = sorted(seen)
    return out


def build_frontier(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Build contract-separated Pareto and quality-diversity projections."""
    if not isinstance(snapshot, Mapping):
        raise ValueError("archive snapshot must be an object")
    if snapshot.get("execution_authorized") not in (None, False):
        raise ValueError("archive snapshot cannot authorize execution")
    if snapshot.get("production_decision_authorized") not in (None, False):
        raise ValueError("archive snapshot cannot authorize production decisions")

    raw_genomes = snapshot.get("genomes") or []
    raw_evaluations = snapshot.get("evaluations") or []
    lineage = snapshot.get("lineage") or []
    if not isinstance(raw_genomes, Sequence) or isinstance(raw_genomes, (str, bytes)):
        raise ValueError("genomes must be a list")
    if not isinstance(raw_evaluations, Sequence) or isinstance(raw_evaluations, (str, bytes)):
        raise ValueError("evaluations must be a list")

    genomes: dict[str, dict[str, Any]] = {}
    contracts: dict[str, dict[str, Any]] = {}
    for raw in raw_genomes:
        if not isinstance(raw, Mapping):
            raise ValueError("genome row must be an object")
        gid = _text(raw.get("genome_id"), "genome_id", 64).lower()
        if gid in genomes:
            raise ValueError("duplicate genome_id in snapshot")
        contract = raw.get("evaluation_contract")
        if not isinstance(contract, Mapping):
            raise ValueError("genome evaluation contract missing")
        contract_hash = _text(contract.get("contract_hash"), "evaluation contract hash", 64).lower()
        objectives = _objectives(contract.get("objectives"))
        raw_keys = contract.get("descriptor_keys") or []
        if not isinstance(raw_keys, Sequence) or isinstance(raw_keys, (str, bytes)):
            raise ValueError("descriptor_keys must be a list")
        descriptor_keys = sorted({_text(x, "descriptor key", 96) for x in raw_keys})
        canonical_contract = {
            "objectives": objectives,
            "descriptor_keys": descriptor_keys,
            "protected_holdout_required": bool(contract.get("protected_holdout_required")),
            "contract_hash": contract_hash,
        }
        if contract_hash in contracts:
            existing = contracts[contract_hash]
            if (
                existing["objectives"] != objectives
                or existing["descriptor_keys"] != descriptor_keys
                or existing["protected_holdout_required"] != canonical_contract["protected_holdout_required"]
            ):
                raise ValueError("evaluation contract hash collision or integrity mismatch")
        else:
            contracts[contract_hash] = canonical_contract
        genomes[gid] = dict(raw)

    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for raw in raw_evaluations:
        if not isinstance(raw, Mapping):
            raise ValueError("evaluation row must be an object")
        gid = _text(raw.get("genome_id"), "evaluation genome_id", 64).lower()
        if gid not in genomes:
            raise ValueError("evaluation references unknown genome")
        genome_contract = str(genomes[gid]["evaluation_contract"]["contract_hash"])
        eval_contract = _text(raw.get("evaluation_contract_hash"), "evaluation contract hash", 64).lower()
        if eval_contract != genome_contract:
            raise ValueError("evaluation contract does not match genome contract")
        contract = contracts[eval_contract]
        metrics = _finite_metrics(raw.get("metrics"))
        expected_metrics = {row["name"] for row in contract["objectives"]}
        if set(metrics) != expected_metrics:
            raise ValueError("evaluation metrics do not match objective contract")
        descriptors_raw = raw.get("descriptors")
        if not isinstance(descriptors_raw, Mapping):
            raise ValueError("evaluation descriptors must be an object")
        descriptors = dict(descriptors_raw)
        if set(descriptors) != set(contract["descriptor_keys"]):
            raise ValueError("evaluation descriptors do not match descriptor contract")
        _canonical(descriptors)

        evaluation_id = _text(raw.get("evaluation_id"), "evaluation_id", 128)
        observed_at = _text(raw.get("observed_at"), "observed_at", 80)
        observed_key = _observed_sort_key(observed_at)
        candidate = {
            "evaluation_id": evaluation_id,
            "genome_id": gid,
            "evaluation_contract_hash": eval_contract,
            "metrics": metrics,
            "descriptors": descriptors,
            "observed_at": observed_at,
            "status": str(raw.get("status") or "UNMEASURED"),
            "genome_state": str(genomes[gid].get("state") or "REGISTERED_RESEARCH").upper(),
            "niche_id": niche_id(eval_contract, descriptors, contract["descriptor_keys"]),
        }
        key = (eval_contract, gid)
        previous = latest.get(key)
        if previous is None:
            latest[key] = candidate
        else:
            previous_key = _observed_sort_key(previous["observed_at"])
            if observed_key > previous_key or (
                observed_key == previous_key and evaluation_id > previous["evaluation_id"]
            ):
                latest[key] = candidate

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for (contract_hash, _), candidate in latest.items():
        grouped[contract_hash].append(candidate)

    contract_rows: list[dict[str, Any]] = []
    global_active_frontier: set[str] = set()
    dominated_all: set[str] = set()

    for contract_hash in sorted(grouped):
        contract = contracts[contract_hash]
        candidates = sorted(grouped[contract_hash], key=lambda row: row["genome_id"])
        novelty = _novelty_scores(candidates, contract["descriptor_keys"])
        for row in candidates:
            row["novelty_score"] = novelty[row["genome_id"]]

        active = [row for row in candidates if row["genome_state"] not in _TERMINAL_STATES]
        pareto: list[dict[str, Any]] = []
        for candidate in active:
            if not any(
                other["genome_id"] != candidate["genome_id"]
                and dominates(other["metrics"], candidate["metrics"], contract["objectives"])
                for other in active
            ):
                pareto.append(candidate)
        pareto_ids = sorted(row["genome_id"] for row in pareto)
        pareto_set = set(pareto_ids)
        dominated_ids = sorted(row["genome_id"] for row in active if row["genome_id"] not in pareto_set)
        global_active_frontier.update(pareto_ids)
        dominated_all.update(dominated_ids)

        niche_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in active:
            niche_groups[row["niche_id"]].append(row)
        niches: list[dict[str, Any]] = []
        for nid in sorted(niche_groups):
            rows = niche_groups[nid]
            local_elites: list[dict[str, Any]] = []
            for candidate in rows:
                if not any(
                    other["genome_id"] != candidate["genome_id"]
                    and dominates(other["metrics"], candidate["metrics"], contract["objectives"])
                    for other in rows
                ):
                    local_elites.append(candidate)
            exemplar = rows[0]
            niches.append({
                "niche_id": nid,
                "descriptor_values": {
                    key: exemplar["descriptors"][key]
                    for key in contract["descriptor_keys"]
                },
                "candidate_count": len(rows),
                "elite_genome_ids": sorted(row["genome_id"] for row in local_elites),
            })

        contract_rows.append({
            "evaluation_contract_hash": contract_hash,
            "objectives": contract["objectives"],
            "descriptor_keys": contract["descriptor_keys"],
            "candidate_count": len(candidates),
            "active_candidate_count": len(active),
            "pareto_count": len(pareto_ids),
            "pareto_genome_ids": pareto_ids,
            "dominated_genome_ids": dominated_ids,
            "candidates": candidates,
            "niches": niches,
        })

    descendants = _descendants(lineage if isinstance(lineage, Sequence) else [])
    stepping_stones: list[dict[str, Any]] = []
    for gid in sorted(descendants):
        if gid not in genomes:
            continue
        descendant_ids = [x for x in descendants[gid] if x in genomes]
        if not descendant_ids:
            continue
        stepping_stones.append({
            "genome_id": gid,
            "state": str(genomes[gid].get("state") or "REGISTERED_RESEARCH").upper(),
            "descendant_genome_ids": descendant_ids,
            "active_frontier_descendant_ids": sorted(
                x for x in descendant_ids if x in global_active_frontier
            ),
            "informative_even_if_dominated": gid in dominated_all
                or str(genomes[gid].get("state") or "").upper() in _TERMINAL_STATES,
        })

    return {
        "schema_version": SCHEMA_VERSION,
        "selection_policy": "latest_evaluation_per_genome_per_contract",
        "comparison_rule": "never compare metrics across distinct evaluation_contract_hash values",
        "diversity_rule": "exact descriptor niches preserve local nondominated elites; novelty is descriptive, not predictive proof",
        "contract_count": len(contract_rows),
        "contracts": contract_rows,
        "stepping_stones": stepping_stones,
        "execution_authorized": False,
        "production_decision_authorized": False,
    }
