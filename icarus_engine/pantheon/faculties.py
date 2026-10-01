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
    debt_change_rate = finite(signals.get("debt_change_rate", 0.0), "debt_change_rate")
    migration_target = signals.get("debt_migration_target")
    migration_target = str(migration_target)[:96] if migration_target not in (None, "") else None
    if validity >= 0.65 and debt_norm >= 0.85 and route == "unresolved":
        debt_state = "insolvency_candidate"
    elif debt_norm >= 0.65 and abs(debt_change_rate) >= 0.50:
        debt_state = "cliff"
    elif migration_target and diversion >= 0.50:
        debt_state = "migrating"
    elif route in {"absorbed", "delayed", "diverted"}:
        debt_state = route
    else:
        debt_state = "open"
    return {
        **out,
        "causal_debt": debt,
        "debt_magnitude": abs(debt),
        "debt_normalized": debt_norm,
        "response_elasticity": elasticity,
        "debt_direction": "positive" if debt > 0 else "negative" if debt < 0 else "flat",
        "repayment_pressure": debt_norm * validity * (1.0 - absorber) * (1.0 - diversion),
        "debt_change_rate": debt_change_rate,
        "debt_state": debt_state,
        "migration_target": migration_target,
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
    effective_world_count = math.exp(entropy)
    resolution_gap = ordered[0][0] - ordered[1][0] if len(ordered) > 1 else ordered[0][0]
    diagnostics_ranked = []
    if isinstance(diagnostics, Mapping):
        diagnostics_ranked = [
            {"observation": str(key), "separation_value": unit(value, f"diagnostic_values.{key}")}
            for key, value in diagnostics.items()
        ]
        diagnostics_ranked.sort(key=lambda row: row["separation_value"], reverse=True)
    return {
        **out,
        "identifiability": ident,
        "ambiguity": 1.0 - ident,
        "effective_world_count": effective_world_count,
        "resolution_gap": resolution_gap,
        "epistemic_blindspot": ident < 0.25,
        "worlds": [{"world": k, "relative_support": v} for v, k in ordered],
        "most_valuable_next_observation": next_obs,
        "ranked_discriminating_observations": diagnostics_ranked[:8],
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
    world_raw = signals.get("world_reachability")
    cross_world = None
    if isinstance(world_raw, Mapping) and world_raw:
        parsed_worlds = []
        for name, row in world_raw.items():
            if not isinstance(row, Mapping):
                continue
            parsed_worlds.append({
                "world": str(name)[:96],
                "up": unit(row.get("up"), f"world_reachability.{name}.up"),
                "down": unit(row.get("down"), f"world_reachability.{name}.down"),
            })
        if parsed_worlds:
            cross_world = {
                "worlds": parsed_worlds,
                "intersection": {
                    "up": min(row["up"] for row in parsed_worlds),
                    "down": min(row["down"] for row in parsed_worlds),
                },
            }
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
        "constraint_pressure": 1.0 - freedom,
        "reachable_space_collapse": 1.0 - freedom,
        "asymmetry": asym,
        "least_cost_direction": least,
        "causal_event_horizon_side": horizon,
        "cross_world_reachability": cross_world,
        "semantics": "structural transition score; exp(-cost) and cross-world intersections are not forecast probabilities",
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
    decay_rate = max(0.0, finite(signals.get("edge_decay_rate_per_second", 0.0), "edge_decay_rate_per_second"))
    explicit_half_life = signals.get("edge_half_life_seconds")
    if explicit_half_life is not None:
        half_life = max(0.0, finite(explicit_half_life, "edge_half_life_seconds"))
        half_life_source = "supplied"
    elif decay_rate > 0:
        half_life = math.log(2.0) / decay_rate
        half_life_source = "derived_from_decay_rate"
    else:
        half_life = None
        half_life_source = "unmeasured"
    subsystem_raw = signals.get("subsystem_survival")
    subsystem_survival = []
    if isinstance(subsystem_raw, Mapping):
        for name, value in subsystem_raw.items():
            subsystem_survival.append({
                "subsystem": str(name)[:96],
                "survival": unit(value, f"subsystem_survival.{name}"),
            })
        subsystem_survival.sort(key=lambda row: row["survival"])
    curriculum = [
        {"target": "data_sensitivity", "severity": data_sens},
        {"target": "execution_sensitivity", "severity": exec_sens},
        {"target": "thesis_fragility", "severity": fragility},
        {"target": "margin_shortfall", "severity": 1.0 - margin},
    ]
    curriculum.extend({
        "target": "ablate:" + row["subsystem"],
        "severity": 1.0 - row["survival"],
    } for row in subsystem_survival)
    curriculum.sort(key=lambda row: row["severity"], reverse=True)
    return {
        **out,
        "survival_score": max(0.0, survival),
        "minimum_failure_distance": margin,
        "dominant_failure_axis": failure_axis,
        "edge_half_life_seconds": half_life,
        "edge_half_life_source": half_life_source,
        "sensitivities": {"data": data_sens, "execution": exec_sens, "thesis": fragility},
        "robustness_vector": {
            "perturbation_margin": margin,
            "data_resilience": 1.0 - data_sens,
            "execution_resilience": 1.0 - exec_sens,
            "thesis_resilience": 1.0 - fragility,
        },
        "subsystem_ablation_survival": subsystem_survival,
        "dreamstate_curriculum": curriculum[:12],
        "semantics": "bounded adversarial robustness heuristic; curriculum items are falsification targets, not a guarantee of survival",
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
        "falsification_questions": [
            "Does the residual survive out-of-sample and regime holdouts?",
            "Can an existing feature family explain the residual after ablation?",
            "Does the phenomenon survive costs, latency and source substitution?",
        ] if candidate else [],
        "retirement_condition": "retire ontology species after repeated negative observed shadow fitness",
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
        stress_mult = max(1.0, finite(item.get("cost_stress_multiplier", 1.5), f"candidate_expressions[{i}].cost_stress_multiplier"))
        stress_net = gross - costs * stress_mult
        density = (net / (risk * duration)) * capacity
        stress_density = (stress_net / (risk * duration)) * capacity
        decay_half_life = item.get("edge_half_life_seconds")
        decay_half_life = None if decay_half_life is None else max(0.0, finite(decay_half_life, f"candidate_expressions[{i}].edge_half_life_seconds"))
        crowding = unit(item.get("crowding", 0.0), f"candidate_expressions[{i}].crowding")
        metabolism = {
            "gross_alpha_intake": gross,
            "cost_burn": costs,
            "stress_cost_burn": costs * stress_mult,
            "net_conversion": net,
            "stress_net_conversion": stress_net,
            "capacity_remaining": capacity,
            "crowding": crowding,
            "edge_half_life_seconds": decay_half_life,
        }
        candidates.append({
            "name": name,
            "expected_net": net,
            "costs": costs,
            "risk_capital": risk,
            "duration_seconds": duration,
            "capacity_remaining": capacity,
            "profit_density": density,
            "stress_cost_multiplier": stress_mult,
            "stress_expected_net": stress_net,
            "stress_profit_density": stress_density,
            "robust_positive": net > 0 and stress_net > 0,
            "alpha_metabolism": metabolism,
        })
    candidates.sort(
        key=lambda x: (x["robust_positive"], x["expected_net"] > 0, x["stress_profit_density"], x["profit_density"], x["expected_net"]),
        reverse=True,
    )
    best = candidates[0] if candidates and candidates[0]["expected_net"] > 0 else None
    robust = [row for row in candidates if row["robust_positive"]]
    profit_chain = []
    cumulative_stress_net = 0.0
    for row in robust[:8]:
        cumulative_stress_net += row["stress_expected_net"]
        profit_chain.append({
            "expression": row["name"],
            "stress_expected_net": row["stress_expected_net"],
            "capacity_remaining": row["capacity_remaining"],
            "cumulative_research_net": cumulative_stress_net,
        })
    return {
        **out,
        "candidates": candidates,
        "best_candidate": best,
        "profit_surface": {
            "robust_positive_count": len(robust),
            "candidate_count": len(candidates),
            "best_stress_profit_density": robust[0]["stress_profit_density"] if robust else None,
        },
        "profit_chain": profit_chain,
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
    total_attention = sum(row["attention_weight"] for row in rows)
    attention_concentration = (
        max((row["attention_weight"] for row in rows), default=0.0) / total_attention
        if total_attention > 0 else 0.0
    )
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
        "attention_concentration": attention_concentration,
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
    ranked = sorted(options, key=lambda x: x[0], reverse=True)
    hypothesis_templates = [
        (uncertainty, "Competing market worlds remain observationally aliased.", "Acquire the highest-separation GÖDEL observation and require posterior world separation."),
        (debt, "The expected reaction has been absorbed, delayed, diverted, or the causal relation failed.", "Trace NULLSPACE routing and reject the claim if relationship validity collapses."),
        (novelty, "Current residual structure is not represented by the existing ontology.", "Run EX NIHILO ablation/OOS tests before admitting a new concept."),
        (contradiction, "Engine disagreement reflects a mechanism or horizon mismatch rather than noise.", "Partition ARCHON conflict by horizon/mechanism and test each branch independently."),
    ]
    hypotheses = [
        {"priority": score, "hypothesis": hypothesis, "falsifier": falsifier}
        for score, hypothesis, falsifier in sorted(hypothesis_templates, key=lambda x: x[0], reverse=True)
        if score >= 0.10
    ]
    strength, question = ranked[0]
    return {
        **out,
        "question": question if strength >= 0.25 else None,
        "question_priority": strength,
        "question_queue": [
            {"priority": score, "question": item}
            for score, item in ranked if score >= 0.10
        ],
        "hypothesis_queue": hypotheses,
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
