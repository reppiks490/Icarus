# ICARUS Architecture

## 1. System intent

ICARUS is evolving from a trading-strategy repository into a quantitative research, evidence-governance, model-validation, and release-qualification platform.

The core question is no longer only “did a backtest make money?” It is:

> Is the claimed signal real, temporally valid, independently supported, reproducible, incrementally useful, robust to falsification, and safe to promote?

## 2. Core layers

### Data / evidence layer
- Canonical repository snapshot and revision identity.
- Dataset/content identity.
- Source timestamps and semantic identity.
- Independence classification: PRIMARY, INDEPENDENT_REPLICATION, DERIVED, DUPLICATE, UNKNOWN.
- Duplicate-collapse and derivation lineage.
- Provider outages/entitlement failures degrade only that source.

### Research layer
- Stable claim IDs, evidence IDs, and research-attempt IDs.
- Attempt ledger that retains failures and rejected variants.
- Multiple-testing status.
- Mechanism, observability, data sufficiency, estimator validity.
- Redundancy and incremental-information analysis.
- Walk-forward/OOS/holdout stress.
- Failure regimes and falsification attempts.

### Model layer
- Slot 0 remains the incumbent logistic baseline.
- XGB Slot 1 is the next challenger model.
- Challenger promotion requires incremental untouched-OOS value over the incumbent.
- Model existence is not model authority.

### Control layer
- Immutable snapshot pinning.
- Maturity ladder and authority boundaries.
- Claim dependency graph and transitive invalidation.
- Conflict arbitration and explicit supersession.
- Policy version pinning.
- Cross-cycle continuity validation.
- Single-flight/overlap suppression.
- Cycle-time budget.
- Anti-stagnation/progress fingerprint.
- Adaptive work budget.
- Fail-closed behavior.

### Verification layer
- Independent test-oracle requirements.
- Negative/adversarial cases.
- Property/metamorphic checks where appropriate.
- Golden-vector provenance when available.
- Mutation/fault-injection plan where useful.
- Passing tests are not decisive if they only restate implementation assumptions.

### Observability layer
Planned/allowed surfaces should expose:
- claim maturity,
- evidence origin and independence,
- dataset/repository/config identity,
- model lineage,
- source freshness,
- conflict sets,
- dependency invalidations,
- calibration state,
- terminal-holdout consumption state,
- verification/oracle state.

Observability may use design/media tooling, but those tools do not become empirical evidence.

## 3. Hard invariants

These are owner-hard unless explicitly changed by the owner:

- `execution_authorized=false`
- no synthetic bars as empirical market evidence
- no invented trainer slots/features
- no Pulse rewrite
- strict temporal integrity
- deterministic replay/serialization where applicable
- tamper-evident provenance/audit
- fail-closed qualification
- uncertainty cannot increase authority
- no fabricated plugin, worker, test, evidence, repository, persistence, lock, or execution activity
- technical acceptance never implies merge/deploy/trade/publish permission

## 4. Claim maturity ladder

`OBSERVED -> HYPOTHESIS -> SPECIFIED -> EMPIRICALLY_SUPPORTED -> IMPLEMENTATION_READY -> VERIFIED_FOR_INTEGRATION`

Terminal states/side states:
- `BLOCKED`
- `REJECTED`

Authority boundaries:
- Evidence convergence may not promote above OBSERVED.
- Structural/subsystem analysis may promote only to HYPOTHESIS/SPECIFIED.
- Empirical research alone may promote only to EMPIRICALLY_SUPPORTED.
- Repair/architecture work may produce IMPLEMENTATION_READY only for approved/canonical behavior.
- Only independent verification may grant VERIFIED_FOR_INTEGRATION.

## 5. Evidence rules

- Same underlying commit/test/backtest/result counts once.
- Multiple agent summaries of the same origin are not independent corroboration.
- Derived composites are not independent evidence merely because their transform is nonlinear.
- Conflicts are not resolved by vote, repetition, confidence wording, averaging incompatible results, or recency alone.
- Supersession requires compatible scope, equal/newer canonical revision/config, and equal-or-stronger validation.
- Broken prerequisites invalidate dependent authority transitively.

## 6. External evidence adapters

Future adapters should be typed and provenance-preserving:
- macro/rates,
- DXY,
- volatility,
- metals,
- equities,
- crypto,
- on-chain.

Every observation should carry at least:
- provider,
- instrument/semantic identity,
- timestamp,
- freshness,
- unit,
- revision/config if applicable,
- independence origin,
- failure/entitlement status.

External feeds are optional evidence channels, not automatic features and never execution authority.
