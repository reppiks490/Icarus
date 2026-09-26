# ICARUS Empirical Qualification

## Mission

This directory contains the complete handoff for the ICARUS empirical research / qualification lane built in ChatGPT.

The lane exists to prevent ICARUS from becoming a large sophisticated system whose conclusions are invalidated by bad timestamps, leakage, selection bias, provider ambiguity, weak baselines, optimistic execution assumptions, or untracked research trials.

## Non-negotiables

- `execution_authorized=false`
- no Pulse rewrite
- no synthetic bars presented as empirical market evidence
- no invented Icarus trainer slots/features
- deterministic canonical serialization
- strict time-order validation
- fail-closed qualification
- immutable/tamper-evident audit semantics
- deterministic replay
- uncertainty cannot increase authority
- stale/unknown critical data cannot silently qualify
- no model authority without incremental OOS value net of cost
- no disappearing failed experiments
- no silent provider fallback that changes data semantics
- no exact-timeframe collapse into coarse family identity

## Ownership boundary

This lane owns:

- source/provider qualification
- dataset identity and row integrity
- timestamp normalization
- information availability semantics
- event timing
- purged temporal splits
- null/logistic baseline
- XGB Slot-1 qualification contract
- artifact semantic binding
- candidate lead/lag qualification
- multiple-testing controls
- calibration/OOD/uncertainty qualification
- economic stress qualification
- robustness / transfer / ablation / tail-risk qualification

This lane does **not** own Pulse strategy rewrite, live order routing, broker credentials, user-facing UI, unrelated infrastructure, marketing, or media generation.

## Current conclusion

The qualification architecture is sufficiently specified to stop broad feature brainstorming.

The next work should be dependency-ordered implementation:

`SOURCE+DATA -> TIME -> BASELINE -> XGB -> ARTIFACT VERIFIER -> CANDIDATE LEAD/LAG -> ECONOMICS -> ROBUSTNESS`

See `CURRENT_STATE.md` and `IMPLEMENTATION_SEQUENCE.md`.
