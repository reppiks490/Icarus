# ICARUS APEX Ω Project E — Self / Science Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build APEX model credibility, reality-gap/self-state, conscience, active information value, scientific governance, and bounded self-evolution proposals.

**Architecture:** Project E models ICARUS's epistemic health without claiming consciousness. It can downgrade/quarantine research authority and propose experiments/evolutions, but cannot deploy production changes or rewrite governing constraints.

**Tech Stack:** Python 3.10+, standard library, Projects A-D, existing proof/latency evidence where available, pytest.

**Spec:** docs/superpowers/specs/2026-10-01-apex-omega-design.md

## Global Constraints

- Requires Projects A-D.
- No self-modifying production path.
- Model credibility influences research weighting only.
- Missing calibration/reality-gap data remains `UNMEASURED`.
- Conscience judges remain separate; no forced consensus.
- Scientific governor proposes research only.
- External/paid experiments are never executed automatically.
- Knowledge delta: extend `docs/icarus/APEX_OMEGA.md` with Project-E governance semantics.

## Review Focus

- Historically strong model with newly high reality gap must lose current credibility — Task 1.
- Missing prerequisite must degrade dependent capability transitively — Task 2.
- Conscience risk veto must survive even if truth/provenance judges pass — Task 3.
- Information-value ranking must not favor unavailable evidence merely because uncertainty is high — Task 4.
- Self-evolution proposal with high performance gain but forbidden authority escalation must be rejected — Task 5.

---

### Task 1: Credibility and reality-gap monitors

**Files:**
- Modify: `icarus_engine/apex/credibility.py`
- Create: `icarus_engine/apex/reality_gap.py`
- Create: `tests_engine/test_apex_reality_gap.py`

**Interfaces:**
- `reality_gap(*, predictions, observations, calibration_contract) -> dict[str, Any]`
- states `NORMAL|DRIFTING|DEGRADED|INVALID|QUARANTINED|UNMEASURED`.
- `credibility_score` consumes reality-gap state and cannot increase on degradation.

- [ ] RED tests for degradation, unmeasured state, regime mismatch, historical strength/current failure, and quarantine.
- [ ] Run RED.
- [ ] Implement.
- [ ] Run GREEN.
- [ ] Commit `feat(apex): monitor model reality gap`.

### Task 2: Self model and capability graph

**Files:**
- Create: `icarus_engine/apex/self_model.py`
- Create: `tests_engine/test_apex_self_model.py`

**Interfaces:**
- `class CapabilityGraph`
- `CapabilityGraph.register(capability: str, prerequisites: Sequence[str]) -> None`
- `CapabilityGraph.status(available: Mapping[str, bool]) -> dict[str, Any]`
- `self_model_snapshot(*, source_commit: str, capabilities, model_health, compute, latency) -> dict[str, Any]`

- [ ] RED tests for transitive prerequisite failure, cycle rejection, source revision binding, unmeasured latency, and false authority.
- [ ] Run RED.
- [ ] Implement.
- [ ] Run GREEN.
- [ ] Commit `feat(apex): model ICARUS capabilities`.

### Task 3: Synthetic conscience and contradiction detector

**Files:**
- Create: `icarus_engine/apex/conscience.py`
- Create: `tests_engine/test_apex_conscience.py`

**Interfaces:**
- `conscience_verdict(*, belief_packet, risk_context, capability_state, authority_context) -> dict[str, Any]`
- independent judges: Truth, Uncertainty, Risk, Consistency, Provenance, Authority.
- judge states: `PASS|WARN|OBJECT|VETO|UNMEASURED`.

- [ ] RED tests for risk veto survival, inferred-as-observed truth veto, internal liquidity contradiction, missing provenance, and research-only authority judge.
- [ ] Run RED.
- [ ] Implement independent judges; preserve all verdicts.
- [ ] Run GREEN.
- [ ] Commit `feat(apex): add synthetic conscience`.

### Task 4: Active information value and scientific governor

**Files:**
- Create: `icarus_engine/apex/information_gain.py`
- Create: `tests_engine/test_apex_information_gain.py`

**Interfaces:**
- `rank_observations(candidates, *, uncertainty_state, acquisition_costs, availability) -> list[dict[str, Any]]`
- `rank_experiments(hypotheses, experiments) -> list[dict[str, Any]]`

- [ ] RED tests for unavailable candidate exclusion, redundant-evidence penalty, cost penalty, discriminative hypothesis value, and deterministic ranking.
- [ ] Run RED.
- [ ] Implement bounded normalized ranking; never claim unmeasured entropy as measured.
- [ ] Run GREEN.
- [ ] Commit `feat(apex): prioritize information and experiments`.

### Task 5: Bounded self-evolution and complexity tax

**Files:**
- Create: `icarus_engine/apex/evolution.py`
- Create: `tests_engine/test_apex_evolution.py`

**Interfaces:**
- `evaluate_architecture_proposal(body: Mapping[str, Any]) -> dict[str, Any]`
- stages `proposed|sandbox|replay|adversarial|ablation|calibration|complexity_review|independent_review|human_review`.
- no API to apply a proposal.

- [ ] RED tests for authority escalation rejection, complexity-dominated proposal rejection, missing independent-information gain, reversible proposal, and no deployment method/export.
- [ ] Run RED.
- [ ] Implement evaluation only.
- [ ] Run GREEN.
- [ ] Update docs and commit `feat(apex): evaluate bounded self evolution`.

### Task 6: Project-E verification gate

- [ ] Run all Project-E tests — Expected PASS.
- [ ] Run Projects A-D tests — Expected PASS.
- [ ] Run `python -m pytest tests_engine/test_brain.py tests_engine/test_pantheon_aether.py -q` — Expected PASS.
- [ ] Search exports and HTTP/control registrations to confirm Project E exposes no direct deploy/promote/broker mutation path.
