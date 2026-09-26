# AEGIS Assurance Baseline v1 — Findings 001–030

Status: frozen red-team discovery baseline for implementation/verification work.

This document consolidates the failure classes discovered across the AEGIS red-team loop. It is an assurance specification, not proof that every control is implemented. Detailed Findings 019–030 are preserved in `archive/ICARUS_AEGIS_WORKLOG.md`; the broader architecture and kernel plan are preserved in the dossier/masterbuild handoff.

## Immutable constraints

- `execution_authorized=false`
- no synthetic bars represented as empirical evidence
- no invented ICARUS trainer slots/features
- no Pulse rewrite
- fail-closed qualification
- deterministic canonical serialization/replay where applicable
- tamper-evident provenance/audit
- strict temporal integrity
- uncertainty cannot increase authority
- complexity cannot gain authority without incremental out-of-sample information net of cost

## Findings

### 001 — Information-Time Leakage
Event time alone is insufficient. Preserve publication, first-observed/ingest, revision, and knowledge cutoffs. Mutating future information must not change a prior decision.

### 002 — Correlated Expert Evidence
Multiple experts sharing decisive ancestry are not independent votes. Maintain lineage/dependency graphs and dependency-adjusted confidence. Cloning an expert cannot increase authority.

### 003 — Calibration Operational Mismatch
Calibration is scoped by regime, horizon, instrument, configuration, and vintage. Stale/OOD/unknown calibration fails closed rather than inheriting authority.

### 004 — Execution-Cost Blindness
A predictive signal is not a realizable edge. Qualification requires cost/latency/fill/impact assumptions and stress; ambiguous intrabar execution remains unknown rather than invented.

### 005 — Fault Propagation / Semantic Integrity
Derived evidence inherits ancestor validity/provenance. Invalid or unknown ancestors cannot be laundered into valid descendants.

### 006 — Replay Nondeterminism
Replay identity binds numeric contracts, ordering, randomness, caches, environment and dependency manifests. Equivalent replay should be byte/semantics deterministic within its declared contract.

### 007 — Audit Completeness / Alternate-History Resistance
Audit must expose omissions, forks and substitutions through chained/checkpointed commitments and manifest binding. A valid local record cannot silently support an alternate global history.

### 008 — Adaptation Governance
Adaptation follows shift detection → degraded/OOD → proposal → shadow → independent qualification → promotion. A newly adapted model does not inherit predecessor authority automatically.

### 009 — Research-Process Overfitting
Distinguish model OOS, research OOS, and untouched lockbox evidence. Repeated exposure converts a holdout into selection data.

### 010 — Common Drivers / False Influence Graph
Association, conditional prediction and causal interpretation are distinct. Influence graphs require latent/common-driver controls and scope-qualified claims.

### 011 — Schema-Valid Semantic Split-Brain
Syntactic validity is insufficient. Explicitly distinguish NONE, UNKNOWN, REJECTED and ABSTAINED; confidence must bind a specific claim, horizon and context.

### 012 — Fail-Closed Composition
Mandatory dependencies are explicit. Missing evidence cannot be hidden by survivor renormalization, fallback defaults, or optionalization of mandatory gates.

### 013 — Evidence Double Spending
Evidence lineage is transitive. Transforms, summaries, dashboards, agents and derived metrics do not create new independent evidence origins.

### 014 — Label / Target Integrity
Targets have immutable contracts covering horizon, ambiguity, censoring, overlap, roll/revision and knowledge time. Synthetic/invented paths cannot stand in for empirical labels.

### 015 — Objective / Proxy Gaming
Optimization targets are versioned contracts with hard constraints. No universal super-score may trade away safety/integrity semantics for aggregate performance.

### 016 — Population / Selection Integrity
Qualification declares the eligible population and flow of exclusions/missing cases. Survivor populations cannot silently replace the intended population.

### 017 — Policy-Induced Data
Observation, selection and labeling policies are part of provenance. A policy-created information deficit may raise research priority, but never epistemic authority.

### 018 — Market-Time / Calendar Integrity
Bind canonical economic time, exchange session, trading date, timezone/calendar version, holidays/early closes and roll identity. Clock/session ambiguity fails closed.

### 019 — Numerical Stability / Threshold Topology
Reproducibility is not robustness. Empirical thresholds expose margin/uncertainty/sensitivity; hard safety boundaries remain absolute. Near-boundary uncertainty cannot increase authority.

### 020 — Checkpoint / Recovery Equivalence
Restart/recovery must be observationally equivalent to uninterrupted execution. Qualification-relevant state, causal cutoffs, pending joins and dependency state must survive or fail closed.

### 021 — Provenance Identity Collision / Artifact Substitution
Hashes authenticate semantic objects, not naked bytes. Identity binds artifact type/role, canonicalization version, contracts and behaviorally relevant dependencies.

### 022 — Configuration Authority / Control Plane
Anything capable of changing authority is itself authority-bearing. Mandatory gates and immutable invariants cannot be downgraded by ordinary runtime configuration.

### 023 — Validator Monoculture / Correlated Test Oracles
Test count is not oracle independence. Track shared code/data/fixtures/assumptions; use independent invariants, negative/property tests, known-good vectors and mutation/fault injection.

### 024 — Specification Drift / Requirement Erosion
Trace critical requirements through architecture → implementation → validation → active runtime path. Orphaned or weakened requirements block qualification.

### 025 — Resource Exhaustion / Graceful Degradation
Loss of compute, storage, validators, audit capacity or data may reduce throughput/availability, but cannot increase authority or silently relax mandatory semantics.

### 026 — Multi-Timeframe Aggregation Leakage
Higher-timeframe features may summarize only information available by the decision cutoff. PARTIAL and FINAL bars have distinct semantics; future confirmation cannot leak backward.

### 027 — Market-Data Revision / Vendor-Correction Integrity
Point-in-time and final-revised datasets are distinct. Corrections/backfills/revisions enter only when first observable and retain explicit vintage provenance.

### 028 — Feature Availability / Computational-Latency Leakage
Evidence is usable only if the required computation can finish before the decision deadline. Readiness propagates across the dependency critical path and includes tail/stress latency.

### 029 — Training-Serving Skew
Qualification binds model + feature implementation + preprocessing + ordering + units + data vintage/source + runtime semantics. Matching column names are not parity.

### 030 — Multiple Comparisons / Research Selection Multiplicity
Qualify the search process that found the winner. Preserve candidate-family exposure, failed candidates and adaptive search history; renamed/redundant candidates do not reset multiplicity.

## Loop transition

The discovery loop is frozen here because additional theoretical findings have diminishing expected value. The active loop is now implementation assurance:

`implement → attack → regress → qualify → map evidence → repeat`

New theoretical findings should be added only when an implementation defect exposes a genuinely new failure class.

## Stale when

Review this baseline when a finding is formally superseded by a versioned assurance policy or when implementation evidence demonstrates that a failure class must be split/merged.
