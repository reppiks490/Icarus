"""AETHER: bounded, ephemeral research swarm over PANTHEON state.

The swarm is intentionally unable to trade.  It allocates research attention to
high-energy regions and emits falsifiable roles with immutable provenance.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

from .contracts import authority_block, digest, unit

_MANDATORY_INDEPENDENT_ROLES = (
    "falsifier",
    "alternative_cause",
    "provenance_guard",
    "risk_guard",
)
_OPTIONAL_ROLES = (
    "monetization",
    "historical_analogue",
    "cross_asset",
    "execution_risk",
    "edge_half_life",
    "information_gain",
    "ontology_scout",
    "redundancy_hunter",
)
_ROLE_PARTITIONS = {
    "falsifier": "adversarial",
    "alternative_cause": "mechanism",
    "provenance_guard": "provenance",
    "risk_guard": "risk",
    "monetization": "economics",
    "historical_analogue": "history",
    "cross_asset": "cross_asset",
    "execution_risk": "execution",
    "edge_half_life": "decay",
    "information_gain": "epistemic",
    "ontology_scout": "novelty",
    "redundancy_hunter": "ablation",
}

class AetherSwarm:
    def __init__(self, threshold: float = 0.58, max_agents: int = 12):
        self.threshold = max(0.0, min(1.0, float(threshold)))
        self.max_agents = max(1, min(32, int(max_agents)))

    def evaluate(
        self,
        observation_id: str,
        asset: str,
        horizon_ms: int,
        signals: Mapping[str, Any],
        faculties: Mapping[str, Mapping[str, Any]],
    ) -> dict[str, Any]:
        best = faculties.get("mint", {}).get("best_candidate")
        if isinstance(best, Mapping):
            ev = max(0.0, float(best.get("expected_net") or 0.0))
            profit = math.tanh(ev / 1000.0)
        else:
            profit = unit(signals.get("profit_potential"), "profit_potential")
        contradiction = unit(faculties.get("archon", {}).get("contradiction"), "archon.contradiction")
        novelty = unit(faculties.get("ex_nihilo", {}).get("ontology_surprise"), "ex_nihilo.ontology_surprise")
        causal = unit(faculties.get("nullspace", {}).get("debt_normalized"), "nullspace.debt_normalized")
        uncertainty = unit(faculties.get("godel", {}).get("ambiguity"), "godel.ambiguity", 1.0)
        risk = unit(signals.get("risk"), "risk")
        data_quality = unit(signals.get("data_quality"), "data_quality", 0.5)
        raw_energy = (
            0.27 * profit
            + 0.20 * contradiction
            + 0.16 * novelty
            + 0.20 * causal
            + 0.17 * uncertainty
        )
        energy = max(0.0, min(1.0, raw_energy * (1.0 - 0.45 * risk) * (0.50 + 0.50 * data_quality)))
        active = energy >= self.threshold and data_quality >= 0.35
        agents = []
        if active:
            count = min(self.max_agents, max(4, 4 + int(round(energy * 8))))
            ttl = max(1, min(180, int(max(1, horizon_ms) / 1000) * 2))
            roles = list(_MANDATORY_INDEPENDENT_ROLES)
            roles.extend(_OPTIONAL_ROLES[: max(0, count - len(roles))])
            for role in roles[:count]:
                aid = "aeth-" + digest(observation_id, role)[:18]
                agents.append({
                    "agent_id": aid,
                    "role": role,
                    "claim_scope": f"{asset}:{horizon_ms}ms",
                    "falsifier_required": role not in {"provenance_guard", "risk_guard"},
                    "information_partition": _ROLE_PARTITIONS[role],
                    "independence_round": "blind_first_pass",
                    "peer_context_authorized": False,
                    "ttl_seconds": ttl,
                    "ephemeral": True,
                    "capital_authority": "NONE",
                    "execution_authorized": False,
                    "production_decision_authorized": False,
                    "lineage": {"observation_id": observation_id, "generation": 0},
                })
        species = []
        ontology = faculties.get("ex_nihilo", {})
        if active and ontology.get("new_phenomenon_candidate"):
            species.append({
                "species_id": "species-" + digest(str(ontology.get("phenomenon_id")), asset)[:16],
                "origin": ontology.get("phenomenon_id"),
                "stage": "hypothesis",
                "fitness_credit": 0.0,
                "production_authority": False,
            })
        return {
            "status": "active" if active else "quiet",
            "field": {
                "profit": profit,
                "contradiction": contradiction,
                "novelty": novelty,
                "causal_debt": causal,
                "uncertainty": uncertainty,
                "risk": risk,
                "data_quality": data_quality,
                "energy": energy,
                "activation_threshold": self.threshold,
            },
            "agents": agents,
            "species_candidates": species,
            "cognitive_mass": len(agents),
            "authority": authority_block(),
            "diversity_contract": {
                "blind_first_pass": True,
                "peer_conclusions_hidden_until_commitment": True,
                "minimum_independent_roles": 4 if active else 0,
                "mandatory_roles": list(_MANDATORY_INDEPENDENT_ROLES) if active else [],
                "forced_consensus": False,
            },
            "truth_contract": {
                "agents_are_ephemeral_research_workers": True,
                "claims_not_agents_are_durable_units": True,
                "consensus_is_not_forced": True,
                "risk_kernel_bypass": False,
            },
        }
