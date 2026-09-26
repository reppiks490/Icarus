# Dependency-Ordered Implementation Sequence

## Phase 1 — SOURCE + DATA kernel

Suggested ownership:

```
icarus_engine/evidence/
    timestamps.py
    identity.py
    integrity.py
```

Deliver canonical timestamp parser, evidence schema, provider/source state, instrument/chart identity, row integrity and DatasetManifest.

Do not change Pulse.

## Phase 2 — TIME kernel

Deliver source-event/received/available times, feature availability, event schedule/result availability, label availability, purged splits, irregular-bar unresolved state and staleness authority cap.

## Phase 3 — Baselines

Deliver null baseline, clean logistic probabilities, logloss, Brier, calibration diagnostics and exact experiment binding.

## Phase 4 — XGB Slot 1

Only after phases 1-3 pass. Implement frozen XGB contract, validation-only early stopping, pre-holdout calibration, serialization verification and exact artifact identity. No hyperparameter search initially.

## Phase 5 — Artifact verifier

Replace existence-only gates with semantic verification.

## Phase 6 — Candidate lead/lag

Replace same-interval predictive qualification with strict future lead and nested candidate selection.

## Phase 7 — Economics

Frozen decision policy and execution-stress frontier.

## Phase 8 — Robustness

Regime, transfer, fragility, OOD, calibration drift, corruption, ablation and tail-risk harness.

## Phase 9 — Integration/simplification

Delete or demote complexity that fails incremental-value tests.

## Merge discipline

- implementation commits separate from contract docs
- preserve exact hashes/experiment identities
- never turn diagnostics into authority without their gate
- never reuse viewed holdout as unseen evidence
