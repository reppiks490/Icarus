# TRAINER-CALIBRATION-001 — resolve calibration/evaluation split before XGB implementation

Pinned ICARUS revision: `007e70189945b8e112904cf92b2b1a12e43792d6`.

## Frozen-contract conflict

`SPEC.md` currently requires:
- time-ordered 60% train / 20% valid / 20% holdout;
- valid used for early stopping;
- holdout log-loss and sign accuracy reported;
- isotonic calibration fitted on holdout after the booster is frozen.

Isotonic calibration is itself a fitted transformation. Fitting it on the same holdout whose metrics are reported consumes that holdout for model calibration. The reported calibrated metrics are therefore not an untouched final holdout estimate.

## Why this must be solved before implementation

The current XGB slot at the pinned revision is not yet a complete implemented trainer. This is the cheapest point to resolve the protocol without invalidating an existing history of model results.

## Design options requiring owner approval

Do not silently alter the frozen spec. Select one explicit protocol, for example:

- **three-way plus calibration split:** train / early-stop-valid / calibration / final-test in strict time order;
- **nested time-series calibration:** obtain out-of-fold/rolling calibration predictions inside the pre-test period, then preserve the final holdout;
- another temporally valid protocol that retains an untouched final evaluation partition.

Whichever protocol is approved must define:
- exact chronological boundaries;
- minimum sample requirements;
- behavior when calibration data is insufficient;
- whether reported log-loss/accuracy are raw, calibrated, or both;
- artifact schema changes/versioning;
- multiple-testing/attempt ledger semantics;
- no shuffle and no future information.

## Admission test

A candidate XGB result cannot claim an untouched final holdout if any transformation used to generate its reported predictions was fitted on that same holdout.

## Current status

SPECIFICATION CONFLICT / DESIGN_AWAITING_APPROVAL. No trainer behavior is changed in this handoff.
