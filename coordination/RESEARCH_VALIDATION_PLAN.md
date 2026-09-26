# ICARUS Research & Validation Plan

## Goal

Create a research system that can become substantially more sophisticated without allowing overfitting, data leakage, provider disagreement, duplicated features, or weak tests to masquerade as production confidence.

## 1. Temporal integrity

Every observation used in historical research should distinguish:

- event time,
- observed time,
- provider publication time,
- ingestion time,
- availability-to-strategy time,
- decision time.

A feature is temporally valid only if all information required to construct it was available at or before the historical decision point.

### Required probes

- one-bar shift tests,
- one-timestamp shift tests,
- release-latency injection,
- session-boundary perturbation,
- post-close/pre-open availability checks,
- contract-roll boundary checks,
- revision/republication checks for macro/fundamental data.

## 2. Data sufficiency

Research must explicitly record coverage:

- sample count,
- unique sessions,
- unique regimes,
- missingness,
- stale intervals,
- source gaps,
- contract/roll coverage,
- train/validation/holdout windows,
- excluded intervals and reasons.

Insufficient data yields a lower authority state, not an optimistic extrapolation.

## 3. Ablation

Required research instrumentation should support:

### Leave-one-vote-out

Disable one contribution while leaving all other logic unchanged.

### Leave-one-family-out

Disable an entire correlated signal family.

### Bonus/weight isolation

Observe family bonuses and adaptive weights independently so the system can detect multiple reward for correlated evidence.

### Composite isolation

A composite must be removable as its own channel even when built from lower-level features.

## 4. Redundancy

Before a new feature receives production authority, evaluate whether it adds information beyond existing channels.

Useful diagnostics include:

- conditional correlation,
- mutual information,
- incremental out-of-sample contribution,
- leave-one-feature-out delta,
- family-level ablation,
- regime-conditioned contribution,
- partial dependence / monotonicity checks where appropriate.

High complexity with negligible incremental information should favor simplification.

## 5. Estimator validity

For trained or calibrated estimators record:

- training window,
- validation window,
- holdout window,
- target definition,
- leakage controls,
- feature availability timing,
- class/target balance,
- calibration method,
- calibration drift,
- retraining trigger,
- random seeds,
- library versions,
- serialized model hash,
- feature schema hash.

## 6. Stress and falsification

Every material trading/model claim should face plausible failure scenarios.

Minimum families:

- increased commission,
- increased slippage,
- delayed fills,
- spread expansion,
- missing bars,
- duplicated bars,
- stale provider data,
- provider outage,
- timestamp skew,
- session truncation,
- volatility shock,
- regime inversion,
- parameter perturbation,
- reduced liquidity,
- rolling-contract transition.

A claim that only survives the exact historical configuration is not robust.

## 7. Test-oracle independence

Passing tests is not enough if the tests merely mirror implementation.

Use at least one of:

- property-based invariant,
- independent reference calculation,
- mutation test,
- fault injection,
- adversarial fixture,
- manually derived micro-case with documented provenance,
- cross-provider compatibility check where providers are genuinely independent.

## 8. Mutation plan

Examples of plausible wrong implementations that the suite should catch:

- flip a long/short comparison,
- shift a feature one bar into the future,
- change an RTH boundary,
- reverse a weight sign,
- fail to reset state at a session boundary,
- accept stale provider data,
- duplicate one vote,
- omit a risk gate,
- alter a contract multiplier,
- bypass idempotency,
- ignore a repository/config hash mismatch.

## 9. Holdout discipline

Holdout data must not choose:

- feature masks,
- ablation masks,
- thresholds,
- hyperparameters,
- weighting schemes,
- regime definitions,
- entry/exit heuristics.

If a holdout influences selection, it is no longer a holdout and must be relabeled.

## 10. Production-parity requirement for diagnostics

When research instrumentation is disabled:

- entries must be identical,
- exits must be identical,
- vote thresholds must be identical,
- sizing must be identical,
- alert/order intent must be identical,
- session behavior must be identical.

Any deviation means the instrumentation changed production behavior and must be reviewed as new functionality.

## 11. Empirical evidence restrictions

Do not count as empirical market evidence:

- invented bars,
- synthetic fills presented as observed fills,
- silently interpolated missing minutes,
- reconstructed microstructure without a licensed/observed source,
- post-hoc labels leaking future state.

Synthetic/adversarial data may be used for testing, but must remain clearly labeled as synthetic test material.

## 12. Release evidence package

A candidate change should carry:

- exact revision,
- exact config digest,
- raw evidence IDs,
- research attempt IDs,
- temporal-integrity result,
- data-sufficiency result,
- estimator-validity result,
- ablation-readiness result,
- redundancy result,
- stress/falsification result,
- oracle-independence result,
- focused test evidence,
- full-suite evidence,
- rollback path,
- unresolved risks.

Only then should independent Stage 5 assurance consider integration readiness.
