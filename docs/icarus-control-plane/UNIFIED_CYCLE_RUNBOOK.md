# ICARUS Unified 5-Stage Control Cycle

## Why this exists

The first scheduled design used five independent hourly automations:

- S1 Evidence Convergence
- S2 Subsystem Rotation
- S3 Empirical Research
- S4 Repair / Architecture Forge
- S5 Verification / Release Assurance

They were scheduled at different minute offsets and their prompts assumed the exact S1 handoff would be available to S2, then S2 to S3, etc.

That assumption was false: independent automation executions had no guaranteed durable authoritative handoff transport.

Result:

- S1 could run correctly.
- S2 could not recover the exact same-cycle `PIPELINE_POLICY_EPOCH`, pinned revision, claim/evidence/dependency/conflict ledger and digest.
- S2 correctly failed closed as `MIXED_POLICY / DEGRADED / MISSING_OR_INVALID`.
- This was an orchestration defect, not evidence that ICARUS strategy/engine code had failed.

The disconnected staged automations were disabled. The replacement is one hourly automation that executes S1->S5 sequentially in one run so the same-cycle state remains in memory.

## Required control fields

```text
PIPELINE_POLICY_VERSION=icarus-control-v1
HANDOFF_SCHEMA_VERSION=icarus-pipeline-v1
CYCLE_ID=<scheduled America/Chicago hour YYYYMMDD-HH>
PIPELINE_POLICY_EPOCH=CYCLE_ID
execution_authorized=false
```

## Frozen snapshot rule

S1 pins immutable revisions for every repository used materially in that cycle.

S2-S5 consume only those pinned revisions.

Never rebase the baseline mid-cycle.

If branch heads move during the cycle:

```text
REPO_DRIFT_STATUS=DRIFT_DETECTED
post-baseline code = CROSS_REVISION
same-cycle promotion authority = false unless explicitly revalidated
```

## Stage authority

| Stage | Function | Maximum maturity |
|---|---|---|
| S1 | Repository/evidence convergence | OBSERVED |
| S2 | Subsystem boundary/specification | SPECIFIED |
| S3 | Empirical research/falsification | EMPIRICALLY_SUPPORTED |
| S4 | Authorized repair or implementation-ready design | IMPLEMENTATION_READY |
| S5 | Independent integration/release assurance | VERIFIED_FOR_INTEGRATION |

No stage may skip the ladder.

## Deterministic subsystem rotation

External Baton/task state is not required to decide whose turn it is.

Fixed rotation:

```
NEXUS -> AION -> ARGUS -> ATHENA -> DAEDALUS -> ORACLE -> repeat
```

Epoch:

```
2026-09-24 07:00 America/Chicago = NEXUS
```

For hourly scheduled cycle `h`:

```text
rotation_index =
  whole scheduled hours since epoch modulo 6

0=NEXUS
1=AION
2=ARGUS
3=ATHENA
4=DAEDALUS
5=ORACLE
```

A repository-pinned owner-approved override may replace this pointer. Chat text alone may not.

## Evidence lineage

Every material evidence item should carry:

```text
EVIDENCE_ID
EVIDENCE_KIND
EVIDENCE_ORIGIN
EVIDENCE_REVISION_OR_CONFIG
DERIVED_FROM_EVIDENCE_IDS
EVIDENCE_INDEPENDENCE =
  PRIMARY | INDEPENDENT_REPLICATION | DERIVED | DUPLICATE | UNKNOWN
EVIDENCE_DEDUP_STATUS
```

The same underlying commit/test/backtest/result counts once even if many agents summarize it.

Independent replication requires a genuinely distinct measurement/test/source without the same decisive dependency.

## Claim/dependency authority

Stable claims carry:

```text
CLAIM_ID
owner
maturity
evidence IDs
dependencies
conflict sets
last decisive change
```

Broken/rejected/missing-provenance prerequisite:

```text
dependency = BROKEN/DEGRADED
child maturity = block/downgrade
```

Dependency cycles bar promotion.

## Conflict handling

Never resolve incompatible evidence by:

- majority vote
- number of agents
- repeated summaries
- confidence wording
- averaging incompatible measurements
- recency alone

Structural/interface conflicts require a canonical pinned contract or decisive test.

Supersession requires compatible scope plus equal/newer canonical revision/config and equal-or-stronger validation.

## Adaptive depth

Default:

```text
WORK_BUDGET_CLASS=MINIMAL
```

Escalate only when another check can change:

- maturity
- blocker
- ownership
- dependency/conflict state
- evidence independence
- empirical data sufficiency
- implementation readiness
- release verdict

Use DEEP only for concrete HIGH/CRITICAL unresolved problems where deeper inspection can alter an actionable decision.

## S3 empirical requirements

Do not turn named indicators or historical PnL into edge claims.

For serious claims record, where applicable:

- mechanism
- population/instrument/horizon
- who plausibly pays
- decay/crowding/failure regimes
- data sufficiency
- estimator validity
- multiple-testing state
- feature/signal dependency lineage
- redundancy/incremental information
- OOS/holdout/walk-forward evidence
- costs/slippage/latency/capacity assumptions
- contrary evidence
- ablation readiness

Derived composites are not independent evidence.

Synthetic scenarios are stress evidence, not empirical validation.

## S4 mutation authority

Repository mutation is allowed only when separately authorized.

If no write authorization exists:
- produce an extraction-ready repair/design package,
- do not edit strategy code.

Verified defects:
1. establish canonical intended behavior,
2. reproduce root cause,
3. write independent failing test first,
4. implement smallest fix,
5. focused test,
6. full applicable suite,
7. independent review when warranted.

New architecture/behavior requires design approval first.

## S5 release rule

Only S5 may say `VERIFIED_FOR_INTEGRATION`.

Required:
- exact same-policy chain,
- pinned consistent revision,
- valid dependency closure,
- no material open conflict,
- non-inflated evidence lineage,
- sufficiently independent test oracle,
- fresh applicable verification.

Technical acceptance does not authorize merge/deploy/trade/publish.

## Failure semantics

If S1 cannot pin the cycle snapshot/policy:

```text
RUN_STATUS=DEGRADED
CYCLE_OUTCOME=INCOMPLETE_PIPELINE
```

Stop rather than manufacture downstream authority.

If a subsystem is blocked, record the blocker and let the next hourly cycle rotate onward.

## Durable handoff transport and repo-native validation

The scheduler remains external. The repository now defines a separate, read-only verification tool for durable stage receipts.

```text
icarus-control validate-receipt S1.json
icarus-control validate-cycle control/receipts/<CYCLE_ID>/
```

Receipt contracts:
- `docs/icarus-control-plane/contracts/icarus-control-v1.json`
- `docs/icarus-control-plane/contracts/icarus-pipeline-v1.json`

The receipt chain is:

```text
S1 receipt_digest
   ↓ prior_stage_digest
S2 receipt_digest
   ↓
S3 receipt_digest
   ↓
S4 receipt_digest
   ↓
S5 receipt_digest
```

Every stage binds the same policy epoch, policy digest, schema digest, code baseline and snapshot set. S4 additionally carries oracle origin/derivation, oracle independence, golden-vector provenance, negative controls, and mutation/fault plan.

Receipts must live separately from the code subject they verify. Recommended storage is an append-only `control-evidence` branch under `control/receipts/<CYCLE_ID>/`. Never move the pinned code baseline merely to record a handoff.

The verifier is fail-closed and cannot schedule stages, invoke models, modify strategy state, arm a broker, or promote a scientific claim by itself.

## External automation note

The unified hourly stage runner remains external to this repository. The repo-native `icarus-control` tool verifies its durable receipts; it is not the scheduler.

If external scheduler state is lost, reconstruct the stage runner from this runbook and use the same versioned receipt contracts rather than restoring the old five disconnected automations.

## Recommended continuation

The first implementation work should **not** be broad strategy enhancement.

Highest-value current proof obligations:

1. AION gap-history integrity chain + tamper regression.
2. DAEDALUS stable source-lineage protected-holdout accounting.
3. ARGUS live repo recovery and provenance ingress contract.
4. ATHENA live repo recovery and uncertainty-lineage contract.
5. NEXUS canonical identity recovery.
6. ORACLE canonical identity recovery.

Do not implement sibling-owned behavior in ICARUS merely because another repository is unavailable.
