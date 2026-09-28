# Handoff log

## 2026-09-22 19:47Z — Grok (xAI)
Read-only Schwab poller in icarus_plant/schwab.py. POST /orders forbidden.
Owner logs in locally every ~7 days. Astra/Opus do not get the token.

## 2026-09-24 — GPT-5.6 Sol

Externalized ICARUS subsystem-rotation and control-plane work to:
- `docs/icarus-control-plane/README.md`
- `docs/icarus-control-plane/SUBSYSTEM_ROTATION_FINDINGS.md`
- `docs/icarus-control-plane/UNIFIED_CYCLE_RUNBOOK.md`
- `docs/icarus-control-plane/HANDOFF_STATE.json`
- `docs/superpowers/plans/2026-09-24-icarus-control-plane-handoff.md`

No engine/strategy/execution code changed. Findings remain revision-pinned and must be reproduced before implementation. The old disconnected scheduled S1-S5 orchestration was diagnosed as lacking durable same-cycle handoff state; the replacement design is one unified sequential control cycle. `execution_authorized=false`.


## 2026-09-24 — GPT-5.6 Sol control-plane runtime

Implemented on `chatgpt/icarus-control-plane-runtime-20260924`:
- dependency-free `icarus_control` canonicalizer/validator/CLI
- versioned `icarus-control-v1` and `icarus-pipeline-v1` contracts
- adversarial receipt/chain tests
- separate evidence-branch storage rule to prevent self-induced snapshot drift
- CI command repair for global `icarus-plant --root` option ordering

Verification status at this log entry: implementation committed, fresh branch CI still required. No strategy/Pulse/broker/trainer logic changed. `execution_authorized=false`.


### Fresh verification evidence

GitHub Actions run `36064742770` on PR #18 completed green on Linux and Windows after the Windows UTF-8 console repair:
- Linux: full `tests_engine`, `icarus-control --help`, plant setup, engine doctor
- Windows: focused plant/bars/doctor tests and plant setup

A later AEGIS matrix/documentation commit means final technical acceptance still requires CI on the final branch head. No merge/deploy/trade authority is implied.


### Authority-graph hardening after first green CI

Before final acceptance, the verifier was extended so:
- claim states are explicit and stage maturity ceilings remain enforced,
- missing/broken/rejected prerequisites and dependency cycles block promotion,
- material OPEN conflicts block promotion,
- RESOLVED/SUPERSEDED conflicts require an explicit reason,
- evidence IDs are collapsed across stages only when content-identical,
- missing lineage parents, lineage cycles, and duplicate-inflated independent origins fail closed,
- structural prerequisites cannot override an S5-reported semantic blocker.

Fresh CI is required again on this expanded head.
## 2026-09-24 — ChatGPT ICARUS empirical/architecture loop
Created a structured research-loop integration corpus on branch
`icarus-loop-integration-2026-09-24`, anchored to main revision
`007e70189945b8e112904cf92b2b1a12e43792d6`.

Canonical entry point: `ICARUS_LOOP_INDEX.md`.

This handoff contains S3 empirical-edge status, attempt accounting, direct repo audits,
provider capability state, S4 point-in-time curve architecture, the implementation plan,
architectural rulings, and the inbox protocol for the remaining loops.

No strategy/runtime code was changed by this handoff.
`execution_authorized=false`.

## 2026-09-27 — Opus: trainer event features as-of the bar (P0 causal repair)
Branch `opus/causal-event-asof`, based on main `f71acde`.

`attach_labels` built `fomc`/`any_macro` from `event_features`, whose window reaches 20h past the
bar, so training rows saw FOMC prints before they happened (SPEC.md: `ts_event <= ts_bar` only).
Trainer rows now use `event_features_asof` (`ts - 6h <= e.ts <= ts`); `attach_labels` takes an
injectable `events=` list. The broad window stays for post-hoc audit/candidate/loser notes only.
`train_file` skip exits now carry `execution_authorized: False`.

Tests: `tests_engine` 531 passed, 2 deselected. The deselected `test_bars.py` ingest tests fail
on main and write into the real checkout's `history/NQ_1m.csv` (the CLI ignores the test's chdir).
Before Slot 2: `audit/run.py::score_pair` `macro_agree` still uses the 20h-ahead window.
`execution_authorized=false`.

## 2026-09-27 — Opus: XGB Slot 1 (frozen spec), holdout ledger, fail-closed qualification
Branch `opus/xgb-slot1` (on top of `opus/causal-event-asof`).

- `trainers/xgb_slot.py`: spec params 1:1, validation-only early stopping, booster sliced to best+1,
  terminal holdout scored once raw vs Slot 0 logit and a null base rate on the same rows
  (`incremental_value_status` PASS only if both are beaten). Isotonic (PAVA, `trainers/calibrate.py`)
  fitted afterwards on the holdout, stored `PENDING_FORWARD`, no holdout metric claimed for it.
- `trainers/ledger.py`: SQLite holdout ledger (`run/trainers/holdout_ledger.sqlite3`). Claim before
  scoring; a different study on an overlapping interval is blocked before training; unreadable = fail closed.
- `trainers/qualify.py`: `VALID_RAW_CHALLENGER` only if the execution rows replay the artifact (reloaded
  booster, re-scored holdout, recomputed baselines, ledger-confirmed claim). The audit's `swap_recommend`
  no longer trusts a file that merely exists.
- CLI: `python -m icarus_engine.trainers --slot xgb`, `python -m icarus_engine.audit --family`.
- No real data was trained: running it consumes that file's holdout in the ledger by design.
`execution_authorized=false`.

## 2026-09-27 — Opus: fixes from the final review of PRs #30-#36
Branch `opus/review-fixes`. Blockers: (1) TradingView range/renko/tick exports stamp bars at the minute floor
plus a millisecond counter; the strict-lead audit read such a bar as closed when its successor's stamp passed,
which let a bar still forming inside the predicted execution minute count as a lead (NQ range vs NQ 1m: 0.627
spurious agreement). Floored stamps are now inferred (or declared: audit `--cand-family range`) and a bar counts
as closed only after its successor's whole stamped minute. (2) Validators trusted whichever ledger an artifact
named and the default ledger was cwd-relative; the canonical ledger is now `$ICARUS_LEDGER`, else
`~/.icarus/holdout_ledger.sqlite3`, and validators trust only it (the study's 23 claims were copied there).
Also: the DATA gate drops every export's last row (may still be forming); VALID states need one-sided
significance at 0.05 against both baselines (Newey-West); empty/refused inputs block with a nonzero exit; every
early POST rejection drains the body; +HHMM offsets parse on Python 3.10; shared artifact/metrics modules.
`execution_authorized=false`.
