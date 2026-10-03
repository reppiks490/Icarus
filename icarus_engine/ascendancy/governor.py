"""ASCENDANCY autonomous evolution governor.

The governor is a research scheduler, not an evaluator and not a trading
authority.  It turns the current ASCENDANCY state into a deterministic,
resource-bounded queue of next research actions while preserving diversity,
unknown-unknown exploration, stepping stones, and federated context.

It never fabricates evaluator receipts, PASS/FAIL outcomes, protected holdout
identities, qualification, production decisions, or execution authority.
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

SCHEMA_VERSION = "icarus-ascendancy-governor-v1"
PLAN_SCHEMA_VERSION = "icarus-ascendancy-governor-plan-v1"
_LOCK = threading.RLock()

_STAGE_COST_UNITS = {
    "CONTRACT_VALIDATION": 0.25,
    "SMOKE_NULLS": 0.50,
    "LOW_FIDELITY_REPLAY": 1.00,
    "ABLATION": 2.00,
    "WALK_FORWARD": 2.50,
    "OOS": 4.00,
    "PROTECTED_HOLDOUT": 6.00,
    "CONDITIONAL_CONTRIBUTION": 4.00,
    "ROBUSTNESS": 5.00,
    "QUALIFICATION_PREFLIGHT": 1.50,
}

# These are scheduling priors only.  They are not evidence of edge, quality,
# expected return, or probability of success.
_STAGE_INFORMATION_PRIOR = {
    "CONTRACT_VALIDATION": 0.50,
    "SMOKE_NULLS": 0.80,
    "LOW_FIDELITY_REPLAY": 1.20,
    "ABLATION": 2.20,
    "WALK_FORWARD": 2.40,
    "OOS": 3.20,
    "PROTECTED_HOLDOUT": 4.00,
    "CONDITIONAL_CONTRIBUTION": 3.80,
    "ROBUSTNESS": 4.20,
    "QUALIFICATION_PREFLIGHT": 1.50,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical(value: Any, name: str = "value", max_bytes: int = 2_000_000) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as ex:
        raise ValueError(f"{name} must be finite JSON") from ex
    if len(raw.encode("utf-8")) > max_bytes:
        raise ValueError(f"{name} exceeds {max_bytes} bytes")
    return raw


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value, "hash input").encode("utf-8")).hexdigest()


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be finite")
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"{name} must be finite")
    return out


def _positive_int(value: Any, name: str, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    if value < 1 or value > maximum:
        raise ValueError(f"{name} must be between 1 and {maximum}")
    return value


def _bool(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be Boolean")
    return value


def _normalize_policy(value: Mapping[str, Any] | None) -> dict[str, Any]:
    raw = dict(value or {})
    if raw.get("execution_authorized") not in (None, False):
        raise ValueError("governor policy authority escalation is forbidden")
    if raw.get("production_decision_authorized") not in (None, False):
        raise ValueError("governor policy authority escalation is forbidden")
    if raw.get("can_mint_qualification") not in (None, False):
        raise ValueError("governor policy cannot mint qualification")

    max_actions = _positive_int(
        raw.get("max_actions_per_cycle", 8),
        "max_actions_per_cycle",
        100,
    )
    max_cost = _finite(raw.get("max_estimated_cost_units", 20.0), "max_estimated_cost_units")
    if max_cost <= 0.0 or max_cost > 1_000_000.0:
        raise ValueError("max_estimated_cost_units is outside the supported range")

    exploration = _finite(raw.get("exploration_fraction", 0.35), "exploration_fraction")
    if exploration < 0.0 or exploration > 1.0:
        raise ValueError("exploration_fraction must be between 0 and 1")

    return {
        "max_actions_per_cycle": max_actions,
        "max_estimated_cost_units": max_cost,
        "exploration_fraction": exploration,
        "max_actions_per_niche": _positive_int(
            raw.get("max_actions_per_niche", 1),
            "max_actions_per_niche",
            100,
        ),
        "allow_protected_holdout_request": _bool(
            raw.get("allow_protected_holdout_request", True),
            "allow_protected_holdout_request",
        ),
        "allow_federated_context_mining": _bool(
            raw.get("allow_federated_context_mining", True),
            "allow_federated_context_mining",
        ),
        "execution_authorized": False,
        "production_decision_authorized": False,
        "can_mint_qualification": False,
    }


def _candidate_niche(candidate: Mapping[str, Any] | None) -> str:
    if not isinstance(candidate, Mapping):
        return "unmapped:unmapped"
    origin = str(candidate.get("origin") or "unknown").strip().lower()
    mechanism = candidate.get("mechanism")
    mech = (
        str(mechanism.get("type") or "unknown").strip().lower()
        if isinstance(mechanism, Mapping)
        else "unknown"
    )
    return f"{origin}:{mech}"


def _action(
    *,
    kind: str,
    subject_id: str,
    lane: str,
    niche_key: str,
    cost: float,
    priority: float,
    reason: str,
    details: Mapping[str, Any] | None = None,
    requires_external_evidence: bool,
) -> dict[str, Any]:
    semantic: dict[str, Any] = {
        "kind": str(kind),
        "subject_id": str(subject_id),
        "lane": str(lane),
        "niche_key": str(niche_key),
        "estimated_cost_units": float(cost),
        "priority_score": float(priority),
        "priority_basis": "scheduler_heuristic_not_edge_score",
        "reason": str(reason),
        "details": dict(details or {}),
        "requires_external_evidence": bool(requires_external_evidence),
        "execution_authorized": False,
        "production_decision_authorized": False,
    }
    semantic["action_id"] = _hash(semantic)
    return semantic


def _priority(stage: str) -> float:
    cost = _STAGE_COST_UNITS[stage]
    return _STAGE_INFORMATION_PRIOR[stage] / cost


def _frontier_parent(frontier: Mapping[str, Any]) -> tuple[str | None, str]:
    contracts = frontier.get("contracts")
    if isinstance(contracts, Sequence) and not isinstance(contracts, (str, bytes)):
        for group in sorted(
            (x for x in contracts if isinstance(x, Mapping)),
            key=lambda x: str(x.get("evaluation_contract_hash") or ""),
        ):
            ids = [
                str(x) for x in (group.get("pareto_genome_ids") or [])
                if isinstance(x, str) and x
            ]
            if ids:
                return sorted(ids)[0], "pareto_frontier"

    stones = frontier.get("stepping_stones")
    if isinstance(stones, Sequence) and not isinstance(stones, (str, bytes)):
        informative = [
            str(row.get("genome_id"))
            for row in stones
            if isinstance(row, Mapping)
            and row.get("informative_even_if_dominated") is True
            and row.get("genome_id")
        ]
        if informative:
            return sorted(informative)[0], "stepping_stone"
    return None, "none"


def _candidate_actions(state: Mapping[str, Any], policy: Mapping[str, Any]) -> list[dict[str, Any]]:
    foundry = state.get("foundry") if isinstance(state.get("foundry"), Mapping) else {}
    evaluator = state.get("evaluator") if isinstance(state.get("evaluator"), Mapping) else {}
    inventions = state.get("inventions") if isinstance(state.get("inventions"), Mapping) else {}
    unknowns = state.get("unknowns") if isinstance(state.get("unknowns"), Mapping) else {}
    frontier = state.get("frontier") if isinstance(state.get("frontier"), Mapping) else {}
    federation = state.get("federation") if isinstance(state.get("federation"), Mapping) else {}

    foundry_rows = [
        row for row in (foundry.get("candidates") or [])
        if isinstance(row, Mapping) and row.get("candidate_id")
    ]
    foundry_by_id = {str(row["candidate_id"]): row for row in foundry_rows}

    evaluator_rows = [
        row for row in (evaluator.get("candidates") or [])
        if isinstance(row, Mapping) and row.get("candidate_id")
    ]
    evaluator_by_id = {str(row["candidate_id"]): row for row in evaluator_rows}

    actions: list[dict[str, Any]] = []

    for cid in sorted(evaluator_by_id):
        row = evaluator_by_id[cid]
        foundry_row = foundry_by_id.get(cid)
        niche = _candidate_niche(foundry_row)
        state_name = str(row.get("state") or "").upper()
        next_stage = str(row.get("next_stage") or "").upper()

        if state_name == "READY_FOR_PROTECTED_QUALIFICATION":
            actions.append(_action(
                kind="SUBMIT_FOR_INDEPENDENT_QUALIFICATION",
                subject_id=cid,
                lane="exploit",
                niche_key=niche,
                cost=0.10,
                priority=20.0,
                reason="Evaluator cascade is complete; only the independent protected qualification authority may decide the next state.",
                details={
                    "governor_can_qualify": False,
                    "requires_external_authority": "protected_candidate_qualification",
                },
                requires_external_evidence=True,
            ))
            actions[-1]["governor_can_qualify"] = False
            actions[-1]["requires_external_authority"] = "protected_candidate_qualification"
            continue

        if state_name == "HALTED_FAILED":
            actions.append(_action(
                kind="REJECT_FAILED_CANDIDATE",
                subject_id=cid,
                lane="governance",
                niche_key=niche,
                cost=0.05,
                priority=12.0,
                reason="Evaluator recorded a terminal failure; Foundry lifecycle should preserve the failed lineage instead of spending more evaluation budget.",
                details={"evaluator_state": state_name},
                requires_external_evidence=False,
            ))
            continue

        if state_name != "EVALUATING" or not next_stage:
            continue
        if next_stage not in _STAGE_COST_UNITS:
            continue

        cost = _STAGE_COST_UNITS[next_stage]
        remaining = row.get("resource_remaining")
        remaining_cost = (
            float(remaining.get("cost_units", 0.0))
            if isinstance(remaining, Mapping)
            and isinstance(remaining.get("cost_units"), (int, float))
            and not isinstance(remaining.get("cost_units"), bool)
            else 0.0
        )
        if remaining_cost + 1e-12 < cost:
            actions.append(_action(
                kind="REVIEW_RESOURCE_EXHAUSTION",
                subject_id=cid,
                lane="governance",
                niche_key=niche,
                cost=0.05,
                priority=15.0,
                reason=f"Next evaluator stage {next_stage} exceeds remaining candidate research budget.",
                details={
                    "next_stage": next_stage,
                    "stage_cost_units": cost,
                    "remaining_cost_units": remaining_cost,
                },
                requires_external_evidence=False,
            ))
            continue

        if next_stage == "PROTECTED_HOLDOUT":
            if not policy["allow_protected_holdout_request"]:
                continue
            action = _action(
                kind="REQUEST_PROTECTED_HOLDOUT",
                subject_id=cid,
                lane="exploit",
                niche_key=niche,
                cost=cost,
                priority=25.0,
                reason="Candidate reached protected holdout; governor may request an externally named holdout but cannot invent or expose one itself.",
                details={
                    "stage": next_stage,
                    "requires_named_holdout": True,
                },
                requires_external_evidence=True,
            )
            action["requires_named_holdout"] = True
            actions.append(action)
        else:
            actions.append(_action(
                kind="RUN_EVALUATOR_STAGE",
                subject_id=cid,
                lane="exploit",
                niche_key=niche,
                cost=cost,
                priority=_priority(next_stage),
                reason=f"Candidate is waiting on evaluator stage {next_stage}; schedule evidence production under the immutable evaluator contract.",
                details={"stage": next_stage},
                requires_external_evidence=True,
            ))

    # Foundry candidates not yet known to the evaluator are enrolled rather
    # than treated as if evaluation had already begun.
    for cid in sorted(foundry_by_id):
        if cid in evaluator_by_id:
            continue
        row = foundry_by_id[cid]
        stage = str(row.get("stage") or "").upper()
        niche = _candidate_niche(row)
        if stage in {"INCUBATING", "TESTING", "VALIDATED_RESEARCH"}:
            actions.append(_action(
                kind="REGISTER_WITH_EVALUATOR",
                subject_id=cid,
                lane="exploit",
                niche_key=niche,
                cost=0.10,
                priority=9.0,
                reason=f"Foundry candidate is {stage} but absent from the staged evaluator cascade.",
                details={"foundry_stage": stage},
                requires_external_evidence=False,
            ))
        elif stage == "PROPOSED":
            actions.append(_action(
                kind="INCUBATE_CANDIDATE",
                subject_id=cid,
                lane="explore",
                niche_key=niche,
                cost=0.20,
                priority=2.0,
                reason="New Foundry proposal needs mechanism/provenance review before evaluator enrollment.",
                details={"foundry_stage": stage},
                requires_external_evidence=False,
            ))

    # Replicated unexplained phenomena become research questions, never causes.
    phenomena = [
        row for row in (unknowns.get("phenomena") or [])
        if isinstance(row, Mapping) and row.get("phenomenon_signature")
    ]
    for row in sorted(phenomena, key=lambda x: str(x.get("phenomenon_signature"))):
        status = str(row.get("status") or "").upper()
        candidate_ids = [str(x) for x in (row.get("candidate_ids") or []) if x]
        if status not in {"STRUCTURED_CANDIDATE", "REPLICATED"} or candidate_ids:
            continue
        replication = int(row.get("independent_episode_count") or 0)
        magnitude_value = row.get("mean_residual_magnitude")
        magnitude = (
            max(0.0, min(10.0, float(magnitude_value)))
            if isinstance(magnitude_value, (int, float)) and not isinstance(magnitude_value, bool)
            else 0.0
        )
        priority = 2.5 + min(replication, 10) * 0.15 + magnitude * 0.05
        signature = str(row["phenomenon_signature"])
        actions.append(_action(
            kind="GENERATE_UNKNOWN_HYPOTHESES",
            subject_id=signature,
            lane="explore",
            niche_key=f"unknown:{signature[:12]}",
            cost=1.00,
            priority=priority,
            reason="Unexplained residual has independent replication and no linked Foundry candidate; generate falsifiable explanations without assigning cause.",
            details={
                "unknown_status": status,
                "independent_episode_count": replication,
                "failed_explanations": list(row.get("failed_explanations") or []),
                "cause_must_remain_null": True,
            },
            requires_external_evidence=False,
        ))

    used_blueprints = {
        str((row.get("metadata") or {}).get("blueprint_id"))
        for row in foundry_rows
        if isinstance(row.get("metadata"), Mapping)
        and (row.get("metadata") or {}).get("blueprint_id")
    }
    blueprints = [
        row for row in (inventions.get("blueprints") or [])
        if isinstance(row, Mapping) and row.get("blueprint_id")
    ]
    for row in sorted(blueprints, key=lambda x: str(x.get("blueprint_id"))):
        bid = str(row["blueprint_id"])
        if bid in used_blueprints or str(row.get("status") or "") != "UNTESTED_HYPOTHESIS":
            continue
        estimated = row.get("estimated_cost_units")
        raw_cost = (
            float(estimated)
            if isinstance(estimated, (int, float)) and not isinstance(estimated, bool)
            else 1.0
        )
        admission_cost = max(0.10, min(0.75, raw_cost * 0.10))
        actions.append(_action(
            kind="PROMOTE_BLUEPRINT_TO_FOUNDRY",
            subject_id=bid,
            lane="explore",
            niche_key=f"invention:{bid[:12]}",
            cost=admission_cost,
            priority=3.0 / max(0.25, raw_cost),
            reason="Untested invention blueprint has not entered the Candidate Foundry; admit it as a falsifiable proposal, not as established edge.",
            details={
                "blueprint_status": "UNTESTED_HYPOTHESIS",
                "edge_claim_established": False,
            },
            requires_external_evidence=False,
        ))

    parent, parent_kind = _frontier_parent(frontier)
    if parent:
        contract_count = len([
            x for x in (frontier.get("contracts") or []) if isinstance(x, Mapping)
        ])
        niche_count = sum(
            len(x.get("niches") or [])
            for x in (frontier.get("contracts") or [])
            if isinstance(x, Mapping)
        )
        actions.append(_action(
            kind="SPAWN_GENOME_DESCENDANT",
            subject_id=parent,
            lane="explore",
            niche_key=f"architecture:{parent_kind}",
            cost=1.50,
            priority=1.25 + (0.25 if niche_count <= max(1, contract_count) else 0.0),
            reason="Preserve open-ended architecture search by generating a bounded descendant from a frontier or informative stepping-stone parent.",
            details={
                "parent_kind": parent_kind,
                "current_contract_count": contract_count,
                "current_niche_count": niche_count,
                "mutation_must_be_falsifiable": True,
            },
            requires_external_evidence=False,
        ))

    if (
        policy["allow_federated_context_mining"]
        and str(federation.get("status") or "").lower() == "green"
        and str(federation.get("historical_context_status") or "").lower() == "green"
        and int(federation.get("historical_candidate_evidence_count") or 0) == 0
    ):
        sources = [
            row for row in (federation.get("historical_context_sources") or [])
            if isinstance(row, Mapping)
            and row.get("id")
            and row.get("research_context_eligible") is True
            and row.get("candidate_evidence_eligible") is False
        ]
        for row in sorted(sources, key=lambda x: str(x.get("id"))):
            sid = str(row["id"])
            actions.append(_action(
                kind="MINE_FEDERATED_CONTEXT",
                subject_id=sid,
                lane="explore",
                niche_key=f"federation:{sid}",
                cost=0.50,
                priority=1.75,
                reason="Verified Icarus-engine historical context may seed new research questions but cannot count as candidate evidence or bypass normal gates.",
                details={
                    "evidence_status": row.get("evidence_status"),
                    "blob_sha": row.get("blob_sha"),
                    "candidate_evidence_eligible": False,
                    "requires_foundry_and_evaluator": True,
                },
                requires_external_evidence=False,
            ))
            actions[-1]["candidate_evidence_eligible"] = False
            actions[-1]["requires_foundry_and_evaluator"] = True

    return actions


def _sorted_actions(actions: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        (dict(x) for x in actions),
        key=lambda x: (
            -float(x["priority_score"]),
            float(x["estimated_cost_units"]),
            str(x["kind"]),
            str(x["subject_id"]),
            str(x["action_id"]),
        ),
    )


def _take_actions(
    candidates: Sequence[Mapping[str, Any]],
    *,
    slots: int,
    remaining_cost: float,
    niche_counts: dict[str, int],
    max_per_niche: int,
) -> tuple[list[dict[str, Any]], float]:
    selected: list[dict[str, Any]] = []
    if slots <= 0 or remaining_cost <= 0:
        return selected, remaining_cost
    for action in _sorted_actions(candidates):
        if len(selected) >= slots:
            break
        niche = str(action["niche_key"])
        if niche_counts.get(niche, 0) >= max_per_niche:
            continue
        cost = float(action["estimated_cost_units"])
        if cost > remaining_cost + 1e-12:
            continue
        selected.append(action)
        niche_counts[niche] = niche_counts.get(niche, 0) + 1
        remaining_cost -= cost
    return selected, remaining_cost


def build_governor_plan(
    state: Mapping[str, Any],
    policy: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build one deterministic, resource-bounded ASCENDANCY research plan."""
    if not isinstance(state, Mapping):
        raise ValueError("governor state must be an object")
    _canonical(state, "governor state")
    normalized_policy = _normalize_policy(policy)

    candidates = _candidate_actions(state, normalized_policy)
    exploration = [x for x in candidates if x["lane"] == "explore"]
    non_exploration = [x for x in candidates if x["lane"] != "explore"]

    max_actions = int(normalized_policy["max_actions_per_cycle"])
    reserve = min(
        len(exploration),
        int(math.ceil(max_actions * float(normalized_policy["exploration_fraction"]))),
    )
    remaining_cost = float(normalized_policy["max_estimated_cost_units"])
    niche_counts: dict[str, int] = {}

    selected_explore, remaining_cost = _take_actions(
        exploration,
        slots=reserve,
        remaining_cost=remaining_cost,
        niche_counts=niche_counts,
        max_per_niche=int(normalized_policy["max_actions_per_niche"]),
    )
    selected = list(selected_explore)

    remaining_slots = max_actions - len(selected)
    selected_main, remaining_cost = _take_actions(
        non_exploration,
        slots=remaining_slots,
        remaining_cost=remaining_cost,
        niche_counts=niche_counts,
        max_per_niche=int(normalized_policy["max_actions_per_niche"]),
    )
    selected.extend(selected_main)

    # If the exploit/governance pool cannot fill the cycle, spend remaining
    # slots on still-diverse exploration before considering duplicate niches.
    remaining_slots = max_actions - len(selected)
    already = {x["action_id"] for x in selected}
    if remaining_slots > 0:
        extra_explore = [x for x in exploration if x["action_id"] not in already]
        more, remaining_cost = _take_actions(
            extra_explore,
            slots=remaining_slots,
            remaining_cost=remaining_cost,
            niche_counts=niche_counts,
            max_per_niche=int(normalized_policy["max_actions_per_niche"]),
        )
        selected.extend(more)

    selected = _sorted_actions(selected)
    total_cost = sum(float(x["estimated_cost_units"]) for x in selected)
    fingerprint = _hash({
        "state": state,
        "policy": normalized_policy,
    })
    semantic = {
        "schema_version": PLAN_SCHEMA_VERSION,
        "input_fingerprint": fingerprint,
        "policy": normalized_policy,
        "candidate_action_count": len(candidates),
        "action_count": len(selected),
        "selected_exploration_actions": sum(1 for x in selected if x["lane"] == "explore"),
        "selected_exploitation_actions": sum(1 for x in selected if x["lane"] == "exploit"),
        "selected_governance_actions": sum(1 for x in selected if x["lane"] == "governance"),
        "estimated_cost_units": total_cost,
        "actions": selected,
        "can_mint_evaluator_receipts": False,
        "can_mint_qualification": False,
        "execution_authorized": False,
        "production_decision_authorized": False,
        "truth_contract": {
            "governor_is_scheduler_not_evaluator": True,
            "governor_never_fabricates_evaluation_outcomes": True,
            "governor_never_invents_protected_holdout_identity": True,
            "governor_never_mints_qualification": True,
            "priority_score_is_scheduler_heuristic_not_edge_score": True,
            "diversity_preserved_before_second_pass": True,
            "federated_context_is_not_candidate_evidence": True,
            "unknown_cause_remains_null_until_separately_validated": True,
            "resource_budget_applies_before_action_selection": True,
        },
    }
    semantic["plan_id"] = _hash(semantic)
    return semantic


class EvolutionGovernor:
    """Durable append-only archive of deterministic governor cycles."""

    def __init__(self, base_dir: str | os.PathLike[str]):
        self.base_dir = Path(base_dir)
        self.path = self.base_dir / "research" / "ascendancy_governor.sqlite3"
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
                CREATE TABLE IF NOT EXISTS cycles (
                    plan_id TEXT PRIMARY KEY,
                    input_fingerprint TEXT NOT NULL,
                    action_count INTEGER NOT NULL,
                    estimated_cost_units REAL NOT NULL,
                    plan_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_asc_governor_recorded
                    ON cycles(recorded_at, plan_id);
                """
            )

    def close(self) -> None:
        return None

    def plan(
        self,
        state: Mapping[str, Any],
        policy: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        plan = build_governor_plan(state, policy)
        raw = _canonical(plan, "governor plan")
        now = _utc_now()
        with _LOCK, self._connect() as con:
            existing = con.execute(
                "SELECT plan_json,recorded_at FROM cycles WHERE plan_id=?",
                (plan["plan_id"],),
            ).fetchone()
            if existing is not None:
                if str(existing["plan_json"]) != raw:
                    raise RuntimeError("governor plan identity integrity failure")
                return {
                    "idempotent": True,
                    "plan": plan,
                    "recorded_at": str(existing["recorded_at"]),
                    "execution_authorized": False,
                    "production_decision_authorized": False,
                }
            con.execute(
                """INSERT INTO cycles(
                    plan_id,input_fingerprint,action_count,estimated_cost_units,
                    plan_json,recorded_at
                ) VALUES(?,?,?,?,?,?)""",
                (
                    plan["plan_id"],
                    plan["input_fingerprint"],
                    plan["action_count"],
                    plan["estimated_cost_units"],
                    raw,
                    now,
                ),
            )
        return {
            "idempotent": False,
            "plan": plan,
            "recorded_at": now,
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    def snapshot(self) -> dict[str, Any]:
        with _LOCK, self._connect() as con:
            rows = con.execute(
                "SELECT plan_id,plan_json,recorded_at FROM cycles ORDER BY recorded_at,plan_id"
            ).fetchall()
        plans: list[dict[str, Any]] = []
        for row in rows:
            try:
                plan = json.loads(row["plan_json"])
            except (TypeError, json.JSONDecodeError) as ex:
                raise RuntimeError("governor cycle storage corruption") from ex
            if not isinstance(plan, dict):
                raise RuntimeError("governor cycle storage corruption")
            plan["recorded_at"] = str(row["recorded_at"])
            plans.append(plan)
        latest = plans[-1] if plans else None
        return {
            "schema_version": SCHEMA_VERSION,
            "journal_mode": self.journal_mode,
            "cycle_count": len(plans),
            "latest_plan_id": latest.get("plan_id") if latest else None,
            "latest_plan": latest,
            "plans": plans,
            "truth_contract": {
                "cycles_are_append_only": True,
                "exact_state_policy_retries_are_idempotent": True,
                "governor_is_scheduler_not_evaluator": True,
                "governor_cannot_mint_qualification": True,
            },
            "execution_authorized": False,
            "production_decision_authorized": False,
        }
