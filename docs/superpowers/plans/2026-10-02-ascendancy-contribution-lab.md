# ASCENDANCY Conditional Contribution Lab

**Goal:** Measure whether a contributor adds predictive information conditional on an explicit ICARUS baseline, without conflating standalone performance, structural novelty, or correlation with incremental edge.

## Estimator

Use paired predictive log-score gain:

- binary targets: realized-class log probability under augmented model minus baseline model;
- continuous targets: Gaussian predictive log-density under augmented model minus baseline model.

Aggregate only over independent episodes sharing the exact:

- contributor;
- evaluation contract;
- conditioning set;
- baseline/augmented model identity;
- target kind/key;
- horizon;
- context.

The result is an **incremental predictive-information estimator**, not exact conditional mutual information and not causal proof.

## Truth rules

- exact_conditional_mutual_information=false;
- standalone_performance_is_not_incremental_information=true;
- contracts/contexts/horizons/conditioning sets are never pooled;
- independent episode identity prevents duplicate sample inflation;
- continuous-target Gaussian density is an explicit assumption;
- insufficient samples remain INSUFFICIENT_EVIDENCE;
- research-only: no execution or production-decision authority.

## Delivery

1. RED/GREEN core ContributionLab tests.
2. Explicit Windows CI coverage.
3. Authenticated read/write research API with candidate provenance binding.
4. Adaptive Brain registration under DAEDALUS.
5. ASCENDANCY dashboard Information Contribution Matrix.
6. Full Linux + Windows verification.
