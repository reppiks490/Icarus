# ICARUS Cross-Loop Convergence Record — TEMPLATE

> Copy this file to a dated convergence record after all intended loop handoffs have arrived.

## Control header

```
CONVERGENCE_ID=
CREATED_AT=
BASELINE_MAIN_REVISION=
INTEGRATION_BRANCH=
PIPELINE_POLICY_VERSION=icarus-control-v1
PIPELINE_SCHEMA=icarus-pipeline-v1
EXECUTION_AUTHORIZED=false
```

## Source handoffs consumed

| Handoff | Source loop | Producer | Pinned revision | Status |
|---|---|---|---|---|
| | | | | |

## Claim reconciliation

| Canonical claim ID | Incoming claim | Source | Disposition | Evidence origin | Notes |
|---|---|---|---|---|---|
| | | | | | |

Allowed disposition:
`COMPATIBLE, DUPLICATE, DERIVED_DUPLICATE, REVISION_CONFLICT, CONFIG_CONFLICT,
EVIDENCE_CONFLICT, STALE, UNVERIFIED, BLOCKED`.

## Attempt-ledger delta

List every newly discovered attempt, including failures and discarded variants.

```
ATTEMPTS_BEFORE=
ATTEMPTS_ADDED=
ATTEMPTS_AFTER=
MULTIPLE_TESTING_STATUS=
```

## Duplicate suppression

Document duplicate/derived claims that were collapsed and the shared underlying evidence origin.

## Revision conflicts

For each revision conflict:
- source revision;
- canonical revision;
- files/interfaces affected;
- whether the claim remains comparable;
- required re-verification.

## Configuration conflicts

For each config conflict:
- symbol/market;
- timeframe;
- session;
- feature/parameter set;
- cost model;
- execution assumptions;
- disposition.

## Evidence conflicts

State both sides. Do not resolve a conflict by majority vote. Identify which evidence is primary,
point-in-time, reproducible, or stale.

## Canonical S3 registry delta

### Promotions
None unless every material promotion gate is satisfied.

### Demotions
Record any maturity lost because of conflicts, source revision, temporal leakage, or redundancy.

### New hypotheses

### Newly rejected claims

## S4 architecture delta

Record whether incoming loops:
- add a prerequisite;
- invalidate a current assumption;
- duplicate an existing subsystem;
- expose a safer existing interface;
- create a new blocker;
- justify no change.

## Current blockers after convergence

- DATA_SUFFICIENCY_STATUS=
- ESTIMATOR_VALIDITY_STATUS=
- ABLATION_READINESS_STATUS=
- REDUNDANCY_STATUS=
- MULTIPLE_TESTING_STATUS=
- TEMPORAL_INTEGRITY_STATUS=
- PROVENANCE_STATUS=

## Result

```
PIPELINE_DISPOSITION=
NET_NEW_DELTA=
STATE_CHANGE_CLASS=
ESCALATION_REQUIRED=
REQUEST_TO_NEXT_STAGE=
NEXT_EXPECTED_STAGE=
EXECUTION_AUTHORIZED=false
```

## Resume instruction

State the single smallest decisive next action. Do not restart already completed research families
unless the convergence record identifies a concrete reason.
