# ICARUS Coordination & Integration Layer

This directory is the canonical onboarding surface for external agents, research systems, provider adapters, and later verification/release agents that need to connect to ICARUS without silently changing trading behavior.

## Status

- Added as an **additive coordination layer**.
- No live strategy logic, execution routing, sizing, alert mapping, or market-data semantics are changed by these files.
- Production execution remains unauthorized by this package.
- Control-plane policy: `icarus-control-v1`.
- Handoff schema: `icarus-pipeline-v1`.

## Read order for every new agent

1. `CURRENT_FINDINGS.md` — repository facts directly verified during this integration pass.
2. `CONTROL_PLANE_CONTRACT.md` — authority, stage, promotion, failure, and handoff rules.
3. `ARCHITECTURE_CAPABILITY_FABRIC.md` — target layered architecture and subsystem ownership.
4. `RESEARCH_VALIDATION_PLAN.md` — temporal integrity, ablation, stress, oracle-independence, and falsification requirements.
5. `AGENT_CONNECTION_GUIDE.md` — onboarding and collaboration rules for additional agents.
6. `schemas/handoff.schema.json` — machine-readable stage handoff contract.
7. `schemas/state-index.schema.json` — proposed safe shape for a compact control-state index.
8. `manifests/provider-registry.yaml` — provider capabilities and authority boundaries.

## Core doctrine

ICARUS can expand aggressively in research breadth, provider coverage, diagnostics, modeling, observability, and verification **without allowing complexity to silently increase execution authority**.

External systems produce evidence, diagnostics, research artifacts, or candidate designs. They do not become trade-command authorities merely because they are available.

The architecture is therefore intentionally asymmetric:

```
provider mesh
   ↓
evidence + provenance
   ↓
research / diagnostics / stress / ablation
   ↓
candidate model or design
   ↓
S4 architecture / implementation gate
   ↓
S5 verification / release assurance
   ↓
explicitly authorized execution surface only
```

## Non-negotiable invariants

- No uncertainty may increase authority.
- Missing, stale, conflicting, untraceable, mixed-policy, or cross-revision evidence must preserve or reduce authority.
- No synthetic bars are treated as empirical evidence.
- No holdout data is used to select masks, thresholds, or models.
- No trading/model claim becomes authoritative solely because a provider or model emits it.
- No Stage 4 output self-certifies Stage 5 verification.
- No test is accepted merely because it reproduces implementation logic.
- No repo drift is silently ignored during a pipeline cycle.
- No production execution is implied by this coordination package.
