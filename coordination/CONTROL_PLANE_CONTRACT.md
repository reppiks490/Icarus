# ICARUS Control-Plane Contract

## Canonical versions

`PIPELINE_POLICY_VERSION = "icarus-control-v1"`

`HANDOFF_SCHEMA_VERSION = "icarus-pipeline-v1"`

Mixed-policy or silently translated legacy semantics are non-authoritative.

## Stage-4 intake requirements

Stage 4 must consume a same-cycle authoritative S1/S2/S3 chain or an authoritative S3 handoff that preserves the required lineage.

Minimum checks:

- matching policy version and policy epoch,
- matching/pinned repository revision,
- matching configuration digest where applicable,
- valid evidence lineage,
- valid claim/dependency/conflict state,
- data sufficiency status,
- estimator validity status,
- ablation readiness status,
- redundancy status,
- factual-provenance gate,
- stress/falsification gate,
- concrete implementation, repair, or diagnostic request.

Missing, stale, duplicate, mixed-policy, cross-revision, materially conflicted, estimator-invalid, or stress-missing input cannot support implementation-ready promotion.

## Repository snapshot rule

A stage must not silently rebase mid-cycle.

If repository drift is detected:

- explicitly revalidate against the new revision, or
- emit `RESTART_CYCLE_REQUIRED`.

## Claim and evidence identity

Preserve stable IDs across stages:

- `CLAIM_ID`
- `EVIDENCE_ID`
- `RESEARCH_ATTEMPT_ID`
- dependency lineage
- conflict lineage

Derived summaries are not automatically independent observations.

## Mandatory status vocabulary

### Implementation

- `REPAIRED`
- `IMPLEMENTED_APPROVED`
- `DESIGN_AWAITING_APPROVAL`
- `SPEC_ONLY`
- `BLOCKED`
- `NO_CHANGE`

### Oracle independence

- `INDEPENDENT`
- `PARTIALLY_INDEPENDENT`
- `TAUTOLOGICAL`
- `UNKNOWN`

### Pipeline disposition examples

- `CONTINUE`
- `SHORT_CIRCUIT_NO_CHANGE`
- `RESTART_CYCLE_REQUIRED`

## Test-oracle requirements

Every material implementation package should record:

- `TEST_ORACLE_ORIGIN`
- `TEST_ORACLE_DERIVED_FROM`
- `ORACLE_INDEPENDENCE_STATUS`
- `GOLDEN_VECTOR_PROVENANCE`
- `NEGATIVE_CONTROLS`
- `MUTATION_OR_FAULT_INJECTION_PLAN`

At least one material behavior test class must be capable of catching a plausible incorrect implementation.

Never invent golden expected values.

## Defect route

For a verified defect whose intended behavior is already canonical:

1. establish root cause,
2. define defect boundary and severity,
3. capture canonical intended behavior,
4. add minimal failing regression test,
5. verify RED,
6. implement smallest fix,
7. verify focused GREEN,
8. run applicable full suite,
9. record pre-existing unrelated failures separately,
10. prepare for independent verification.

Do not change acceptance criteria or expected values merely to obtain GREEN.

## New-behavior route

For genuinely new behavior:

- prepare the smallest design,
- document mechanism and ownership,
- define interfaces and data flow,
- define temporal semantics,
- define execution assumptions,
- define risk controls and failure modes,
- define test oracle,
- define migration and rollback,
- define non-goals,
- explain why it does not duplicate existing ICARUS logic.

New behavior remains `DESIGN_AWAITING_APPROVAL` unless the exact design was already authorized.

## Ablation gate

If `ABLATION_READINESS_STATUS` is `PARTIAL` or `BLOCKED`:

- do not rewrite trading logic,
- design research-only instrumentation,
- preserve identical production defaults,
- expose pre-threshold vote/feature states,
- preserve reproducibility hashes,
- keep holdout isolated from mask selection.

## Pulse-specific research constraints

The working research taxonomy supplied for the Pulse architecture includes eight base votes:

- MTF
- RSI/Fisher
- VWAP
- candle conviction
- volume surge
- regime acceleration
- CCI
- XGBoost5

Known independently toggleable research surfaces previously identified include:

- Kalman
- PMA
- PE
- Cyber Cycle

Until canonical repository evidence proves otherwise, treat `XGBoost5` as a `DERIVED_COMPOSITE` when it is composed from existing ADX/Hurst/FDI/zone/cycle/regime/direction features rather than an independently trained estimator.

Family bonuses and adaptive weighting must be independently observable to test correlated multiple-reward effects.

## Acceptance invariants for research instrumentation

- defaults preserve identical entries/exits/vote thresholds,
- disabling one research vote changes only that channel contribution,
- diagnostics introduce no lookahead,
- masks/config enter reproducibility hashes,
- holdout is not used to choose masks,
- unapproved research surfaces cannot remotely alter production/trading execution.

## Promotion rule

Stage 4 may promote only to `IMPLEMENTATION_READY` and only when required evidence, dependency, conflict, temporal, estimator, oracle, and stress gates are satisfied.

Stage 4 never emits `VERIFIED_FOR_INTEGRATION`.

## Handoff-out minimums

Every S4 handoff should include:

- cycle/run identity,
- repository snapshot/revision,
- policy version/epoch,
- evidence IDs,
- claim IDs,
- dependency/conflict state,
- files changed,
- tests added,
- RED evidence,
- GREEN evidence,
- full-suite evidence,
- failures/pre-existing failures,
- test-oracle fields,
- data sufficiency status,
- estimator validity status,
- ablation readiness status,
- redundancy status,
- implementation status,
- rollback plan,
- residual risks,
- `NEXT_EXPECTED_STAGE = "VERIFICATION_RELEASE_ASSURANCE"`.

## Safety invariants

- no synthetic bars as empirical evidence,
- no invented trainer slots or features,
- no silent Pulse rewrite,
- deterministic replay,
- tamper-evident provenance,
- strict temporal integrity,
- uncertainty cannot increase authority,
- no merge/deploy/trade/publish without separate authorization.
