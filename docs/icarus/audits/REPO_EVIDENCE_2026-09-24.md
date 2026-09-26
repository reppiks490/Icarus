# ICARUS Direct Repository Evidence — 2026-09-24

Baseline inspected: `reppiks490/Icarus@007e70189945b8e112904cf92b2b1a12e43792d6`

This document separates verified code facts from research interpretation.

## 1. XGBoost5 lineage
Verified in `icarus_engine/strategy/pulse.py`:
- XGBoost5 uses normalized ADX, Hurst, inverse FDI, supply/demand distance,
  cycle state, and `rate_regime`.
- It uses fixed hand-built transforms/weights and a sigmoid.
- It is therefore a `DERIVED_COMPOSITE`, not an independently trained XGBoost model.

Verified in `icarus_engine/trainers/xgb_slot.py`:
- the trainable XGB slot imports xgboost and raises `NotImplementedError`.

Verified in `icarus_engine/trainers/run.py` and `logit.py`:
- the active baseline trainer is logistic regression.

Consequence: XGBoost5 cannot be counted as statistically independent confirmation
on top of its own source indicators.

## 2. Active trainer feature lineage
`icarus_engine/spec.py` defines active `FEATURE_KEYS`:
`ret_1, ret_3, body, range, close_loc, tide, run, fomc, any_macro`.

Optional keys include `cpi, nfp, earnings, vix_z, tnx_z, dxy_z`, but
`trainers/dataset.py` constructs active training `x` from `FEATURE_KEYS`.
Therefore the optional market variables are not active baseline trainer features
at the pinned revision.

## 3. Correlation module
`icarus_engine/correlations.py` and `research.return_correlation` explicitly treat
the calculation as point-in-time association, not causality or predictive lead.
The code excludes forming bars and preserves receipt-time constraints.

The semantic boundary is good and should be preserved:
correlation != independence != lead/lag != directional alpha.

## 4. Event/calendar defects
Verified defects in the current event research path:

### EVT-WINDOW-001
Documented intended event window and implemented asymmetric predicate are reversed.
Current predicate effectively covers a longer pre-event than post-event interval
relative to the stated design.

### EVT-TIME-002
Fixed UTC release hours are unsafe for U.S. macro events whose official time is
defined in Eastern Time across DST.

### EVT-REDUNDANCY-003
The current trainer event path seeds only FOMC, while both `fomc` and `any_macro`
are active features. Under that path the two columns collapse to the same source.

### EVT-SCOPE-004
Event records carry scope/asset information, but current event selection does not
fully enforce it.

### EVT-SURPRISE-005
Realized `actual_minus_consensus` values can be present in a window that reaches
pre-event bars. The current logistic trainer does not consume `surprise_abs`, so
this is an interface leakage risk rather than a claim of current-model contamination.

Safer semantics already exist in `icarus_engine/advisory.py`, including
publication/receipt ordering and asset scoping. S4 should reuse those principles.

## 5. Futures curve / roll gap
`icarus_engine/contracts.py` explicit roll logic covers the equity-index roots
NQ/ES/YM.

`icarus_engine/assets.py` defines GC/SI/PL/PA with `roll="none"` and front/continuous
Yahoo symbols.

Consequence: a genuine metals term-structure research subsystem must use explicit
maturities. Existing continuous/front symbols cannot supply a curve.

## 6. Current risk posture
None of the findings above authorize production trading changes.
`execution_authorized=false`.
