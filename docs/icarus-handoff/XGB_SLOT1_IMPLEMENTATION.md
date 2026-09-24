# XGB Slot 1 — Empirical-Integrity Implementation Plan

## Current repository state

Baseline revision: `007e70189945b8e112904cf92b2b1a12e43792d6`

Observed:
- `icarus_engine/trainers/xgb_slot.py` remains an explicit `NotImplementedError` path.
- The repository policy requires XGB Slot 1 before swap/promotion.
- Current audit logic over-trusts the existence of an XGB artifact file.
- Slot 0 logistic remains the incumbent baseline.

## Critical sequencing rule

**Do not train XGB until causal trainer-event leakage is repaired.**

Current trainer labeling/features call the broader event-window feature path. That path can include events with timestamps after the current bar, which conflicts with the frozen requirement `ts_event <= ts_bar only` for model features.

A stronger learner would amplify leakage rather than improve truth.

## Phase 0 — Causal event repair

Add a trainer-only as-of/causal event feature path:
- model features may use only events whose timestamp is at or before the bar,
- future scheduled events must not set trainer event flags,
- future realized surprise values must never enter trainer features,
- preserve broader post-hoc audit/event-window behavior where that behavior is intentionally non-causal for analysis.

Required tests:
- future FOMC/event not visible to trainer feature row,
- future surprise value not visible,
- exact-time and past events still behave correctly,
- post-hoc audit window behavior remains unchanged.

## Phase 1 — Explicit execution lock on every trainer exit

Every trainer outcome must explicitly emit:
`execution_authorized=false`

This applies to:
- trained,
- skipped,
- blocked,
- insufficient rows,
- missing dependency,
- malformed input,
- any other early return.

Do not rely on the field merely being absent.

## Phase 2 — Preserve frozen 60/20/20 contract

Do not silently rewrite the repository's frozen split.

Use:
- 60% training,
- 20% validation,
- 20% terminal holdout,
- chronological ordering,
- no shuffle.

For XGB:
- training partition fits the booster,
- validation partition is used for early stopping,
- terminal holdout is scored exactly once for raw model authority.

## Phase 3 — Calibration semantics

Repository materials call for isotonic calibration on the holdout. That creates an important authority distinction:

1. Score raw XGB on the untouched terminal holdout first.
2. Only after raw scoring, calibration may be fitted as required by the frozen spec.
3. Any calibrator fitted on the terminal holdout is **provisional** and has:
   `CALIBRATION_VALIDATION_STATUS=PENDING_FORWARD`
4. Do not report calibration-fit performance on the same data as independent OOS evidence.
5. Calibrated probabilities gain authority only after genuinely fresh forward data validates them.

A small deterministic internal PAVA isotonic implementation is a candidate to avoid unnecessary dependency expansion, but this remains a design choice until implemented/tested.

## Phase 4 — Holdout-consumption ledger

Add a durable research ledger (SQLite is the current design candidate) keyed by terminal interval and study identity.

Minimum identity:
- symbol,
- family,
- terminal start/end,
- dataset/content digest,
- feature-order digest,
- parameter/config digest,
- repository revision,
- artifact schema,
- study digest.

Semantics:
- same interval + same study -> REPLAY
- same interval + materially changed study after observation -> BLOCKED_HOLDOUT_REUSE
- genuinely new terminal interval -> NEW

The goal is to prevent “unseen holdout” status from being reset by parameter changes.

## Phase 5 — XGB artifact schema

A qualifying artifact should bind at least:
- artifact schema version,
- slot,
- symbol,
- family,
- dataset/content SHA-256,
- study SHA-256,
- repository revision,
- exact ordered feature keys,
- XGB parameters,
- random seed,
- split policy and row counts,
- validation/early-stopping provenance,
- best iteration / best score when available,
- raw terminal holdout accuracy,
- raw terminal holdout log loss,
- calibration method/status/rows,
- calibrated state marked provisional until forward validation,
- baseline terminal metrics,
- incremental delta versus Slot 0,
- holdout claim status,
- terminal boundaries,
- `holdout_touched_before_final=false`,
- `execution_authorized=false`,
- `accuracy_guaranteed=false`.

NaN/Infinity is forbidden.

## Phase 6 — Baseline promotion gate

A trained XGB model does not automatically gain authority.

Compare XGB and Slot 0 on the same untouched raw terminal holdout.

Primary comparison should include probability log loss. Additional metrics may be reported but must not silently replace the primary acceptance rule.

Suggested state:
- `incremental_value_status=PASS|FAIL|UNVERIFIED`

If XGB does not improve untouched-OOS probability quality versus the baseline, keep the artifact but do not strengthen swap/promotion authority.

## Phase 7 — Harden audit qualification

Replace “XGB file exists” semantics with structural validation.

Validator should reject/block:
- malformed JSON,
- wrong symbol,
- wrong family,
- wrong feature order,
- unexpected params,
- invalid/non-finite metrics,
- missing provenance,
- dataset/content mismatch where the audit can verify expected identity,
- terminal-holdout reuse violation,
- execution authority anything other than false,
- failed/unverified incremental-value gate when promotion depends on it.

Audit CLI should pass enough dataset identity to the validator to prove the artifact belongs to the execution dataset, rather than trusting a stored hash that cannot be checked.

## Phase 8 — RED -> GREEN test matrix

Minimum RED tests:
- causal event feature blocks future timestamp,
- causal event feature blocks future surprise,
- exact/past event remains valid,
- every trainer exit explicitly locks execution,
- XGB dependency missing -> fail closed,
- XGB fit does not consume terminal holdout,
- early stopping uses validation only,
- raw terminal scoring happens before calibration,
- holdout ledger exact replay allowed,
- changed study on same holdout blocked,
- artifact contains dataset/study/revision identities,
- malformed artifact rejected,
- wrong symbol/family rejected,
- execution-authorized artifact rejected,
- dataset mismatch rejected,
- holdout reuse rejected,
- incremental OOS value required,
- valid qualified artifact may unlock only the intended audit state.

Then run:
- focused trainer tests,
- focused audit tests,
- event tests,
- full `tests_engine`,
- independent verification review.

## Non-goals

- no Pulse rewrite,
- no new unauthorized feature universe,
- no automatic trading,
- no execution-authority change,
- no parameter optimization against terminal holdout,
- no acceptance-criterion changes merely to improve measured performance.
