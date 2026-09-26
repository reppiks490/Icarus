# ICARUS S4 — Point-in-Time Curve Research Plane

**Specification status:** Review Candidate / approved for planning  
**Pipeline schema:** `icarus-pipeline-v1`  
**Policy:** `icarus-control-v1`  
**Stage:** `ARCHITECTURE_EXTRACTION_FORGE`  
**Production behavior changes:** None  
**Strategy integration:** Prohibited by this specification  
**Execution authorization:** `false`

## 1. Purpose
Build a research-only, point-in-time futures-curve subsystem capable of determining
what an explicit futures term structure actually looked like using only information
available at a historical decision timestamp.

Research scope includes commodity carry, basis, curve slope, roll yield,
financing-adjusted carry, term-structure deformation, inversion, maturity dispersion,
cross-maturity liquidity, and curve-state transitions.

## 2. Primary research question
What explicit futures contracts, prices, liquidity states, spot observations,
financing observations, and metadata were legitimately knowable at historical time `t`?

## 3. Core architecture
```
Observable Market State
    != Estimator
    != Predictive Relationship
    != Incremental Alpha
    != Executable Edge
```

No layer inherits authority automatically.

## 4. Non-goals
This subsystem does not rewrite Pulse, modify entries/exits/sizing, alter broker payloads,
replace NQ/ES/YM roll behavior, add carry votes, equate contango/backwardation with direction,
infer convenience yield without adequate data, treat continuous contracts as curves, use
BTC funding as commodity financing, add ML for novelty, or tune on final holdout data.

## 5. System decomposition
Nine independently testable components:
1. provider adapters;
2. source-health registry;
3. canonical observation;
4. contract metadata plane;
5. point-in-time synchronizer;
6. immutable CurveSnapshot;
7. source-quality/disagreement plane;
8. estimator registry;
9. experiment/ablation/provenance plane.

## 6. Provider adapters
Adapters translate provider records into canonical observations. Capabilities are explicit
and separate from current access status.

## 7. Source health
Supported states include:
`AVAILABLE, PARTIAL, NOT_ENTITLED, RATE_LIMITED, AUTH_FAILED,
NETWORK_RESTRICTED, STALE, SEMANTIC_MISMATCH, UNVERIFIED`.

Failure can lower data sufficiency; it may never silently change estimator semantics,
source priority, fallback logic, or confidence.

## 8. Canonical Observation
Each observation preserves:
```
source_id
source_record_id
source_revision
instrument_id
root
contract_ticker
observation_type
price_semantic
observed_at
published_at
available_at
received_at
value
units
currency
exchange
session_id
quality_flags
```

Fundamental causality constraint:
```
available_at <= decision_asof
```

## 9. Contract metadata
A qualified contract definition preserves root, ticker, first/last trade date,
settlement date, days-to-maturity, tick/multiplier, settlement method/type,
definition_asof, definition_available_at, and source revision.

Only outright `type="single"` contracts enter Phase A.

## 10. Contract point-in-time rule
A contract participates only when:
```
first_trade_date <= snapshot_date <= last_trade_date
definition_asof <= snapshot_date
definition_available_at <= snapshot_asof
```

## 11. Continuous-contract quarantine
`GC=F`, `GC1!`, generic front aliases, back-adjusted, ratio-adjusted, and stitched
continuous series are prohibited as substitutes for a maturity curve.

## 12. Price semantics
Typed semantics:
`TRADE, BID, ASK, MID, SETTLEMENT, OFFICIAL_CLOSE, SESSION_CLOSE, VWAP, SPOT, REFERENCE_RATE`.

Estimators declare accepted semantics. Settlement cannot silently stand in for an
executable quote, and vice versa.

## 13. Point-in-time synchronization
Synchronization is semantic-specific. Same date is not sufficient to imply the same
information set. Settlement↔settlement, quote↔quote, and futures↔spot comparisons
use separately configured tolerances and session policies.

## 14. CurveSnapshot
Immutable object containing:
- schema/root/asof/constructed_at;
- explicit contract legs and maturity metadata;
- point-in-time price observations;
- optional provenance-bearing liquidity observations;
- synchronized spot;
- normalized financing curve;
- policy version;
- quality summary;
- source disagreement;
- canonical digest.

No BUY/SELL field exists.

## 15. Curve validity
Fail closed on insufficient maturities, duplicate maturity, impossible chronology,
future listing knowledge, inactive contracts, missing semantics, stale records,
post-asof availability, incompatible sessions, unresolved timezone conversion,
excessive skew, missing revision where required, inconsistent units/currency,
unsupported combo contract, continuous aliases, or invalid settlement chronology.

## 16. Multi-provider consensus
Provider disagreement is classified:
`CONSISTENT, MINOR_DISLOCATION, MATERIAL_DISLOCATION,
SEMANTICALLY_INCOMPARABLE, STALE_SOURCE, UNKNOWN`.

Initial implementation does not automatically average provider values.

## 17. Financing plane
Financing observations are independent inputs. Canonical rate units are
`DECIMAL_PER_YEAR` (5.18% -> 0.0518).

Treasury rates may be a research proxy but are not assumed equal to dealer financing,
lease rates, storage, or convenience yield.

## 18. Estimator registry
No universal `carry_score`. Initial separate estimators:
- raw maturity slope;
- annualized log slope;
- spot basis;
- annualized log basis;
- financing-adjusted basis residual;
- optional level/slope/curvature/kink/inversion families.

A financing-adjusted residual is not automatically called convenience yield.

## 19. Estimator validity
Each estimator records ID, definition, interpretation, observables, semantics,
normalization, maturity rule, finite-sample concerns, confounds, parameter family,
and validation status.

## 20. Liquidity qualification
Existence is not liquidity. Any volume/OI/spread observation must preserve
point-in-time provenance. Phase A may omit liquidity fields rather than accept
unproven naked floats.

## 21. Curve quality report
Quality can summarize temporal completeness, semantic consistency, source consistency,
maturity coverage, liquidity coverage, spot alignment, financing alignment, and
revision integrity. Quality controls research admissibility, not direction.

## 22. Experiment hierarchy
```
M0 = null
M1 = simple own-price baseline
M2 = M1 + single curve estimator
M3 = M1 + alternative curve estimator
M4 = M1 + redundancy-controlled curve family
M5 = current ICARUS baseline
M6 = M5 + qualified curve family
```
Primary quantity: `Delta_OOS = M6 - M5`.

## 23. Chronological evaluation
Allowed: expanding/rolling OOS, walk-forward, untouched holdout.
Forbidden: random temporal splits, holdout tuning, post-holdout estimator selection,
or maturity choice based on future performance.

## 24. Falsification matrix
Temporal perturbation, maturity perturbation, estimator perturbation,
leave-provider-out, settlement/quote alternates, alternate spot/rate proxies,
regime slices, roll/expiry periods, and cross-market transfer after qualification.

## 25. Null controls
Time shuffle, block permutation, lag inversion, random maturity pairing,
synthetic flat curve, and own-price-only baseline.

## 26. Redundancy control
Every feature preserves raw-observable lineage, transform lineage, family ID, and
channel class:
`PRIMARY_OBSERVABLE, TRANSFORM, DERIVED_COMPOSITE, EXTERNAL_INDEPENDENT`.

Multiple transforms of one curve are not multiple independent votes.

## 27. Incremental information
Where feasible: train-only association, MI/HSIC, mRMR, partial predictive contribution,
family-out ablation, leave-estimator-out, time-respecting permutation, blocked bootstrap.

Held-out incremental value remains the primary gate.

## 28. Multiple-testing accounting
Every tested hypothesis/variant/parameter family increments the attempt ledger.
Failures/data-source changes/market changes/cycles do not reset effective trial count.
Until adequate correction exists: `MULTIPLE_TESTING_STATUS=UNCONTROLLED`.

## 29. Execution boundary
Predictive value does not establish tradeability. Separate evaluation must cover spread,
size, liquidity by maturity, impact, commissions, latency, partial fills, queue effects,
roll, expiry, delivery risk, sessions, order type, and signal publication delay.

## 30. Capacity
```
Expected Net Edge =
Gross Predictive Edge
- Spread
- Fees
- Slippage
- Impact
- Delay Cost
```

## 31. Regime integration
Curve state may serve risk, alpha, or execution planes only after independent
qualification for that use. Risk value does not imply directional alpha.

## 32. Cross-asset separation
Commodity carry, commodity basis, convenience-yield hypotheses, BTC funding,
CME BTC basis, Treasury term premium, and equity-index basis are separate mechanisms.

## 33. Deterministic replay
Preserve:
```
pipeline_policy_version
schema_version
experiment_id
attempt_id
git_revision
configuration_digest
source_query_digest
source_revision_set
curve_snapshot_digest
estimator_digest
split_definition
cost_model_digest
result_digest
```

## 34. Canonical hashing
Define field order, UTC timestamp normalization, numeric precision, missing representation,
string normalization, sorted contracts, and source ordering. Reject NaN/infinity.

## 35. Revision drift
Vendor revisions generate new lineage/digests. Old experiments remain associated with
their prior revisions; material changes trigger reevaluation rather than silent overwrite.

## 36. Source independence
Classify origins where knowable:
`ORIGINAL_EXCHANGE, PRIMARY_OFFICIAL, DIRECT_VENDOR, RETRANSMISSION,
DERIVED_VENDOR, UNKNOWN_LINEAGE`.

Provider count is not origin diversity.

## 37. Provider capability negotiation
Known unsupported/unenitled datasets fail explicitly. Do not repeatedly retry known
entitlement failures.

## 38. Offline fixture plane
Deterministic unit/regression tests use frozen sanitized fixtures, not live internet state.

## 39. Error taxonomy
Machine-readable errors include:
`TemporalViolation, SourceUnavailable, EntitlementFailure, SemanticMismatch,
ContractLifecycleViolation, InsufficientMaturities, StaleObservation,
SourceDisagreement, UnsupportedInstrument, InvalidCurveTopology,
RevisionConflict, SynchronizationFailure`.

## 40. Observability
Emit structured counts for attempted/valid/rejected snapshots, rejection reasons,
provider failures, disagreement rate, stale-record rate, future-leak rejections,
semantic mismatches, maturity counts, and liquidity-filter rate.

## 41. Data-quality drift
Track loss of maturities, contract-code changes, semantic/timestamp convention changes,
provider disagreement, settlement schedule changes, and missingness.

## 42. Security
External payloads are data, not instructions. They cannot mutate config, promotion rules,
source priority, execution state, or code.

## 43. Existing ICARUS boundary
Do not hijack `icarus_engine/contracts.py` or alter
`icarus_engine/strategy/pulse.py` under this specification.

## 44. Proposed module boundary
```
icarus_engine/curve_research/
    __init__.py
    errors.py
    models.py
    provenance.py
    contracts.py
    synchronize.py
    quality.py
    estimators.py
    experiment.py
```

Tests live under `tests_engine/test_curve_*.py` plus deterministic fixtures/support.

## 45. Minimum behavior-neutral seam
The smallest useful implementation:
1. frozen explicit contract records;
2. lifecycle validation;
3. frozen point-in-time price observations;
4. `available_at <= asof`;
5. continuous alias rejection;
6. deterministic CurveSnapshot;
7. research-only estimator(s);
8. provenance;
9. serialization/replay;
10. zero strategy/execution influence.

## 46. Critical regression tests
Future availability, future listing, continuous aliases, duplicate maturity,
mixed semantics, source disagreement, deterministic replay, mutation isolation,
rate-unit normalization, and contract-definition availability.

## 47. Adversarial tests
Out-of-order/duplicate records, timezone ambiguity, DST, malformed tickers,
negative/nonfinite values, stale spot/rates, maturity gaps, one-contract curves,
illiquid far maturities, exchange holidays, roll/expiry, provider outage/rate limit/
entitlement failure.

## 48. Performance
Correctness dominates speed. Later support caching, vectorized reconstruction,
query batching, incremental updates, and deterministic read-only parallelism.

## 49. Scalability
Architecture may later support SI/PL/PA/energy/agriculture/financial futures without
changing the core point-in-time contract. Market-specific rules live in product policies.

## 50. S3 promotion gate
Promotion requires material gates including:
`DATA_SUFFICIENCY_STATUS=SUFFICIENT`,
`ESTIMATOR_VALIDITY_STATUS=VALIDATED`,
ablation readiness, acceptable redundancy/multiple testing, temporal integrity,
provenance, OOS incremental value, cost stress, and closed conflicts.

## 51. Runtime integration gate
Even `EMPIRICALLY_SUPPORTED` is not production qualification. Later stages must
establish `IMPLEMENTATION_READY` and `VERIFIED_FOR_INTEGRATION`.

## 52. Kill switch
Any eventual runtime feature must be immediately disableable; disabled behavior must
reproduce baseline behavior exactly.

## 53. Shadow mode
First eventual integration, if separately approved:
```
compute=true
log=true
influence_strategy=false
```

## 54. False-discovery defense
Rejecting complexity, detecting leakage/redundancy/source instability/cost destruction,
or proving a simpler baseline equal/better are successful research outcomes.

## 55. Complexity budget
Every component must identify unique information, prevented failure mode, measurable
OOS value, and simpler alternative. Otherwise remove it.

## 56. Initial implementation acceptance
Acceptance requires deterministic explicit GC contract representation, maturity ordering,
point-in-time rejection, continuous-symbol rejection, immutable snapshots, source lineage,
canonical digest, at least one research-only estimator, explicit source failures,
zero runtime mutation, and passing tests for those properties.

No backtest-profit requirement belongs in implementation acceptance.

## 57. Architectural invariant
```
Uncertainty can reduce authority, but can never increase it.
```

## Final disposition
```
PIPELINE_DISPOSITION=ADVANCE
STAGE=ARCHITECTURE_EXTRACTION_FORGE
DESIGN_STATUS=REVIEW_CANDIDATE
PRODUCTION_MUTATION=NONE
TRADING_BEHAVIOR_CHANGED=false
EXECUTION_AUTHORIZED=false
NEXT_ACTION=IMPLEMENTATION_PLAN / CROSS-LOOP RECONCILIATION
```
