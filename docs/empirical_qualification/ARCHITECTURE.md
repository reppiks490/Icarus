# Architecture

## Qualification spine

SOURCE -> DATA -> TIME -> BASELINE -> XGB -> ECONOMICS -> ROBUSTNESS

A downstream component cannot override a failed upstream gate.

### SOURCE
Owns provider identity/state, evidence schema, instrument identity, source-event/received/available timestamps, payload hash, freshness and semantic fallback labeling.

### DATA
Owns canonical timestamp normalization, exact chart identity, OHLC validation, duplicate/conflict handling, source-order evidence, canonical row hash and DatasetManifest.

### TIME
Owns feature availability, decision time, label availability, event schedule/result timing, staleness, temporal purging and strict candidate lead/lag.

Core invariant: `max(feature_available_times) <= decision_time < label_available_time`.

### BASELINE
Owns null model, clean logistic, train-only preprocessing and reproducible OOS probability metrics.

### XGB
Owns frozen initial spec, validation-only early stopping, pre-holdout calibration, paired incremental-value test, serialization/reload equivalence and semantic artifact identity.

### ECONOMICS
Owns frozen decision rule, modeled costs/slippage/latency, fill assumptions, path sensitivity and capacity limits.

### ROBUSTNESS
Owns regime cells, transfer, fragility, OOD, selective prediction, calibration drift, corruption, ablation, trial ledger and tails.

## Authority principle

Worse evidence, more staleness, more disagreement or more uncertainty can only maintain or reduce authority.

No uncertainty mechanism may increase authority.
