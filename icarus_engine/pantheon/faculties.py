"""Independent PANTHEON faculties.

These are deliberately diagnostic heuristics, not calibrated probabilities.
Each output declares its semantics and abstains when the required evidence is
missing.  Disagreement is preserved instead of averaged away.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

from .contracts import authority_block, digest, finite, signed_unit, unit

def _base(name: str, status: str = "active") -> dict[str, Any]:
    return {
        "faculty": name,
        "status": status,
        "authority": authority_block(),
    }

def nullspace(signals: Mapping[str, Any]) -> dict[str, Any]:
    out = _base("NULLSPACE")
    if "expected_response" not in signals or "observed_response" not in signals:
        return {**out, "status": "abstain", "reason": "expected_response and observed_response required"}
    expected = finite(signals["expected_response"], "expected_response")
    observed = finite(signals["observed_response"], "observed_response")
    absorber = unit(signals.get("absorber_strength"), "absorber_strength")
    validity = unit(signals.get("relationship_validity"), "relationship_validity", 1.0)
    lag = unit(signals.get("lag_score"), "lag_score")
    diversion = unit(signals.get("diversion_score"), "diversion_score")
    debt = expected - observed
    scale = max(abs(expected), 1e-9)
    debt_norm = min(1.0, abs(debt) / scale) if abs(expected) > 1e-9 else min(1.0, abs(debt))
    if validity < 0.35:
        route = "forgiveness_candidate"
    elif absorber >= 0.65:
        route = "absorbed"
    elif diversion >= 0.65:
        route = "diverted"
    elif lag >= 0.65:
        route = "delayed"
    else:
        route = "unresolved"
    elasticity = None if abs(expected) <= 1e-12 else observed / expected
    return {
        **out,
        "causal_debt": debt,
        "debt_magnitude": abs(debt),
        "debt_normalized": debt_norm,
        "response_elasticity": elasticity,
        "absorber_strength": absorber,
        "relationship_validity": validity,
        "routing_state": route,
        "semantics": "causal-debt diagnostic; not a promise that price must repay the debt",
    }

def godel(signals: Mapping[str, Any]) -> dict[str, Any]:
    out = _base("GODEL")
    raw = signals.get("world_scores")
    if not isinstance(raw, Mapping) or len(raw) < 2:
        return {**out, "status": "abstain", "reason": "at least two world_scores required", "identifiability": 0.0}
    vals = []
    worlds = {}
    for key, value in raw.items():
        v = max(0.0, finite(value, f"world_scores.{key}"))
        worlds[str(key)] = v
        vals.append(v)
    total = sum(vals)
    if total <= 0:
        return {**out, "status": "abstain", "reason": "world_scores have no positive mass", "identifiability": 0.0}
    probs = [v / total for v in vals]
    entropy = -sum(p * math.log(p) for p in probs if p > 0)
    max_entropy = math.log(len(probs))
    normalized_entropy = entropy / max_entropy if max_entropy else 0.0
    ident = max(0.0, min(1.0, 1.0 - normalized_entropy))
    diagnostics = signals.get("diagnostic_values")
    next_obs = None
    if isinstance(diagnostics, Mapping) and diagnostics:
        scored = []
        for key, value in diagnostics.items():
            scored.append((unit(value, f"diagnostic_values.{key}"), str(key)))
        scored.sort(reverse=True)
        next_obs = scored[0][1]
    ordered = sorted(((v / total, k) for k, v in worlds.items()), reverse=True)
    return {
        **out,
        "identifiability": ident,
        "ambiguity": 1.0 - ident,
        "worlds": [{"world": k, "relative_support": v} for v, k in ordered],
        "most_valuable_next_observation": next_obs,
        "semantics": "relative world indistinguishability heuristic; not calibrated posterior probability",
    }

def ananke(signals: Mapping[str, Any]) -> dict[str, Any]:
    out = _base("ANANKE")
    if "transition_cost_up" not in signals or "transition_cost_down" not in signals:
        return {**out, "status": "abstain", "reason": "transition_cost_up/down required"}
    up = max(0.0, finite(signals["transition_cost_up"], "transition_cost_up"))
    down = max(0.0, finite(signals["transition_cost_down"], "transition_cost_down"))
    reach_up = math.exp(-up)
    reach_down = math.exp(-down)
    asym = reach_up - reach_down
    freedom = (reach_up + reach_down) / 2.0
    if abs(asym) < 0.10:
        least = "symmetric"
    else:
        least = "up" if asym > 0 else "down"
    horizon = None
    if max(up, down) >= 2.5:
        horizon = "down" if down > up else "up"
    return {
        **out,
        "structural_cost": {"up": up, "down": down},
        "reachability_score": {"up": reach_up, "down": reach_down},
        "freedom": freedom,
        "asymmetry": asym,
        "least_cost_direction": least,
        "causal_event_horizon_side": horizon,
        "semantics": "structural transition score; exp(-cost) is not a forecast probability",
    }

def nemesis(signals: Mapping[str, Any]) -> dict[str, Any]:
    out = _base("NEMESIS")
    margin = unit(signals.get("perturbation_margin"), "perturbation_margin")
    data_sens = unit(signals.get("data_sensitivity"), "data_sensitivity")
    exec_sens = unit(signals.get("execution_sensitivity"), "execution_sensitivity")
    fragility = unit(signals.get("thesis_fragility"), "thesis_fragility")
    if not any(k in signals for k in ("perturbation_margin", "data_sensitivity", "execution_sensitivity", "thesis_fragility")):
        return {**out, "status": "abstain", "reason": "adversarial sensitivity evidence required", "survival_score": 0.0}
    survival = min(margin, 1.0 - data_sens, 1.0 - exec_sens, 1.0 - fragility)
    failure_axis = max(
        (("data", data_sens), ("execution", exec_sens), ("thesis", fragility), ("margin_shortfall", 1.0 - margin)),
        key=lambda x: x[1],
    )[0]
    return {
        **out,
        "survival_score": max(0.0, survival),
        "minimum_failure_distance": margin,
        "dominant_failure_axis": failure_axis,
        "sensitivities": {"data": data_sens, "execution": exec_sens, "thesis": fragility},
        "semantics": "bounded adversarial robustness heuristic; not a guarantee of survival",
    }

def ex_nihilo(signals: Mapping[str, Any], observation_id: str) -> dict[str, Any]:
    out = _base("EX_NIHILO")
    novelty = unit(signals.get("novelty"), "novelty")
    rep_error = unit(signals.get("representation_error"), "representation_error")
    invariance = unit(signals.get("cross_regime_invariance"), "cross_regime_invariance")
    score = 0.45 * novelty + 0.45 * rep_error + 0.10 * invariance
    candidate = score >= 0.72 and novelty >= 0.55 and rep_error >= 0.55
    return {
        **out,
        "ontology_surprise": score,
        "new_phenomenon_candidate": candidate,
        "phenomenon_id": ("x-" + digest(observation_id, "ontology")[:16]) if candidate else None,
        "required_next_stage": "shadow_hypothesis_falsification" if candidate else "none",
        "semantics": "representation inadequacy detector; candidate concepts have zero authority until independently validated",
    }

def mint(signals: Mapping[str, Any]) -> dict[str, Any]:
    out = _base("MINT")
    raw = signals.get("candidate_expressions")
    if not isinstance(raw, list) or not raw:
        return {**out, "status": "abstain", "reason": "candidate_expressions required", "candidates": [], "best_candidate": None}
    candidates = []
    for i, item in enumerate(raw[:64]):
        if not isinstance(item, Mapping):
            continue
        name = str(item.get("name") or f"candidate_{i}")[:96]
        gross = finite(item.get("expected_gross", 0.0), f"candidate_expressions[{i}].expected_gross")
        costs = max(0.0, finite(item.get("costs", 0.0), f"candidate_expressions[{i}].costs"))
        risk = max(1e-9, abs(finite(item.get("risk_capital", 1.0), f"candidate_expressions[{i}].risk_capital")))
        duration = max(1.0, finite(item.get("duration_seconds", 1.0), f"candidate_expressions[{i}].duration_seconds"))
        capacity = unit(item.get("capacity_remaining", 1.0), f"candidate_expressions[{i}].capacity_remaining", 1.0)
        net = gross - costs
        density = (net / (risk * duration)) * capacity
        candidates.append({
            "name": name,
            "expected_net": net,
            "costs": costs,
            "risk_capital": risk,
            "duration_seconds": duration,
            "capacity_remaining": capacity,
            "profit_density": density,
        })
    candidates.sort(key=lambda x: (x["expected_net"] > 0, x["profit_density"], x["expected_net"]), reverse=True)
    best = candidates[0] if candidates and candidates[0]["expected_net"] > 0 else None
    return {
        **out,
        "candidates": candidates,
        "best_candidate": best,
        "proposal_only": True,
        "semantics": "expression-ranking heuristic before risk-kernel review; never an order instruction",
    }

def archon(signals: Mapping[str, Any], godel_state: Mapping[str, Any]) -> dict[str, Any]:
    out = _base("ARCHON")
    scores = signals.get("engine_scores")
    reliabilities = signals.get("engine_reliability")
    if not isinstance(scores, Mapping) or not scores:
        return {**out, "status": "abstain", "reason": "engine_scores required", "leases": [], "contradiction": 0.0}
    rel = reliabilities if isinstance(reliabilities, Mapping) else {}
    data_quality = unit(signals.get("data_quality"), "data_quality", 0.5)
    uncertainty = unit(godel_state.get("ambiguity"), "godel.ambiguity", 1.0)
    rows = []
    vals = []
    for name, value in scores.items():
        score = signed_unit(value, f"engine_scores.{name}")
        reliability = unit(rel.get(name), f"engine_reliability.{name}", 0.5)
        attention = reliability * data_quality * (1.0 - 0.5 * uncertainty)
        rows.append({"engine": str(name), "score": score, "reliability": reliability, "attention_weight": attention})
        vals.append(score)
    rows.sort(key=lambda x: x["attention_weight"], reverse=True)
    contradiction = (max(vals) - min(vals)) / 2.0 if len(vals) > 1 else 0.0
    ttl = max(1, min(300, int(finite(signals.get("lease_ttl_seconds", 30), "lease_ttl_seconds"))))
    leases = [{
        "engine": row["engine"],
        "scope": "research_attention",
        "ttl_seconds": ttl,
        "revocable": True,
        "execution_authorized": False,
        "production_decision_authorized": False,
    } for row in rows[:3] if row["attention_weight"] > 0]
    return {
        **out,
        "engine_states": rows,
        "contradiction": contradiction,
        "leases": leases,
        "consensus_forced": False,
        "semantics": "temporary research-attention leases; disagreement is retained and no lease grants trading authority",
    }

def socrates(states: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    out = _base("SOCRATES")
    uncertainty = unit(states.get("godel", {}).get("ambiguity"), "godel.ambiguity")
    debt = unit(states.get("nullspace", {}).get("debt_normalized"), "nullspace.debt_normalized")
    novelty = unit(states.get("ex_nihilo", {}).get("ontology_surprise"), "ex_nihilo.ontology_surprise")
    contradiction = unit(states.get("archon", {}).get("contradiction"), "archon.contradiction")
    options = [
        (uncertainty, "Which observation most efficiently separates the competing market worlds?"),
        (debt, "Where did the missing reaction route: delay, absorption, diversion, or causal-model failure?"),
        (novelty, "Does the current residual require a new concept, or can an existing concept explain it out of sample?"),
        (contradiction, "Which engine disagreement is mechanism-specific rather than mere noise or horizon mismatch?"),
    ]
    strength, question = max(options, key=lambda x: x[0])
    return {
        **out,
        "question": question if strength >= 0.25 else None,
        "question_priority": strength,
        "experiment_required": strength >= 0.25,
        "semantics": "question generator only; experiments must pass independent validation before affecting production",
    }

def evaluate_faculties(signals: Mapping[str, Any], observation_id: str) -> dict[str, Any]:
    ns = nullspace(signals)
    gd = godel(signals)
    ak = ananke(signals)
    nm = nemesis(signals)
    xn = ex_nihilo(signals, observation_id)
    mt = mint(signals)
    ar = archon(signals, gd)
    states = {
        "nullspace": ns,
        "godel": gd,
        "ananke": ak,
        "nemesis": nm,
        "ex_nihilo": xn,
        "mint": mt,
        "archon": ar,
    }
    states["socrates"] = socrates(states)
    return states
