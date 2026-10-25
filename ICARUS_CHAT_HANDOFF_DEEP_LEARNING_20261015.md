# ICARUS cross-chat handoff — deep-learning challenger

Date: 2026-10-15
Repository: `reppiks490/Icarus`
Branch: `feature/deep-learning-challenger-20261015`
Pull request: `#353` — Research-only deep learning challenger for ICARUS
Base: `main`

## Purpose

This file exists so any other ChatGPT/Codex/cloud workspace can recover **everything implemented by the chat that built the deep-learning challenger** without depending on that chat's temporary workspace.

The work is pushed to GitHub. There is no required local-only state for this implementation.

## Exact recovery commands

```bash
git fetch origin feature/deep-learning-challenger-20261015
git switch --create feature/deep-learning-challenger-20261015 --track origin/feature/deep-learning-challenger-20261015
```

If the branch already exists locally:

```bash
git fetch origin feature/deep-learning-challenger-20261015
git switch feature/deep-learning-challenger-20261015
git reset --hard origin/feature/deep-learning-challenger-20261015
```

To inspect without disturbing another workspace:

```bash
git fetch origin feature/deep-learning-challenger-20261015
git worktree add ../icarus-deep-learning origin/feature/deep-learning-challenger-20261015
```

## Scope of work implemented

This branch adds a **research-only deep-learning challenger lane** to Icarus. It does not replace or alter the frozen production trainer-slot architecture.

Implemented capabilities:

1. Causal sequence construction for temporal models. Sequence windows end at the decision row and cannot include future feature rows.
2. Training-only feature standardization. Validation and holdout data do not influence normalization statistics.
3. A deterministic PyTorch GRU challenger using CPU execution, fixed seed, deterministic algorithms, gradient clipping, AdamW, validation-only early stopping, and bounded probability output.
4. Validation-only isotonic probability calibration.
5. Canonical holdout-ledger protection before terminal-holdout scoring.
6. Comparison against the converged logistic baseline and constant-null baseline using the repository's existing log-loss, sign-accuracy, incremental-value, and paired Newey-West significance machinery.
7. Content-addressed JSON model serialization, reload, and exact prediction replay verification.
8. Explicit safety locks: `execution_authorized=false`, `production_decision_authorized=false`, `auto_promote=false`.
9. CLI support through `icarus-train --challenger gru ...` rather than inventing a new trainer slot.
10. Optional dependency group `deep = ["torch>=2.4,<3"]` in `pyproject.toml`.
11. Dedicated GitHub Actions workflow `deep-learning-contract.yml` that installs the real PyTorch backend and executes the challenger end to end.
12. Regression tests that assert the frozen slot map stays exactly logit/xgb/rank/regime/fail.

## Critical architecture decision

An early provisional version treated the GRU as a sixth trainer slot. That was intentionally corrected before handoff because Icarus's canonical model contracts freeze slots 0–4.

Final architecture:

- slot0 = logit
- slot1 = xgb
- slot2 = rank
- slot3 = regime
- slot4 = fail
- GRU = external `deep_learning_challenger` research lane, **not slot5**

The provisional `gru_slot.py` was removed. Do not recreate slot5 unless the frozen model specification is intentionally redesigned in a separate approved change.

## Files changed by PR #353

- `.github/workflows/deep-learning-contract.yml`
- `icarus_engine/trainers/__main__.py`
- `icarus_engine/trainers/deep_challenger.py`
- `icarus_engine/trainers/run.py`
- `icarus_engine/trainers/sequence.py`
- `pyproject.toml`
- `tests_engine/test_deep_learning_challenger.py`

This handoff file is an additional documentation-only commit on the same branch.

## Verification status at handoff

Verified against branch head immediately before this handoff commit:

- General `tests` workflow: **SUCCESS**
- `source-data-contract` workflow: **SUCCESS**
- `deep-learning-contract` workflow: **SUCCESS**

The dedicated deep-learning workflow installed the real optional PyTorch dependency and exercised the actual training/calibration/holdout/serialization/replay path.

After this documentation commit, GitHub may run workflows again. Re-check the newest branch head before merging.

## What this does NOT claim

This implementation proves that Icarus can train and evaluate a controlled deep-learning challenger. It does **not** yet prove that deep learning is better than the frozen XGB model in real trading performance.

Do not claim superiority until the challenger is tested on the canonical historical futures execution data with untouched out-of-sample periods and then survives Icarus's existing qualification/shadow gates.

The repository's `history/` tree does not currently carry the canonical execution CSV payloads in GitHub. The `multi-level-csv` repository contains many exports, but the newer equity-candidate batches are sensor data and must not be mislabeled as NQ execution history.

## Recommended continuation

1. Locate/materialize the canonical futures history used by Icarus, preserving symbol, chart family, timestamp semantics, and roll behavior.
2. Run the GRU challenger and frozen XGB on matching causal datasets and matching untouched evaluation periods.
3. Compare log loss, calibration, sign accuracy, regime stability, tail behavior, turnover/cost sensitivity, and significance.
4. Reject the GRU if it does not add stable incremental value.
5. If it does add value, keep it as a challenger/ensemble input first; do not grant execution authority directly.
6. Only after forward/shadow validation should any production integration be considered.

## Useful commands

Install deep research dependency:

```bash
pip install -e ".[dev,deep]"
```

Run the dedicated tests:

```bash
python -m pytest tests_engine/test_deep_learning_challenger.py -q
```

Example challenger invocation:

```bash
icarus-train \
  --challenger gru \
  --path /path/to/canonical.csv \
  --chart-type 1m \
  --asset NQ \
  --out run/trainers/NQ_clock_minutes_deep_gru.json
```

## Cross-chat instruction

If another chat says it cannot access the earlier workspace, direct it to this repository branch and this file. It should inspect PR #353 and continue from the branch rather than rebuilding the feature from memory.

Do not confuse this branch with any separate UI/portfolio-tab workspace. This handoff contains the work performed by the deep-learning chat only.


## Current-main integration — 2026-10-18

The integration branch is `codex/gru-trusted-source-current-main-20261017`, based on main `e4daa751c0090c2c5c3888ffd35237b97973f05f`. It preserves the complete published PR #387 head `d3ff4cd1de3856025813009319dd7960d1179866`, including PR #353 and the CSV parsing repairs from #399. Original branches remain preserved.

Independent review found two further compatibility/evidence defects, now repaired with six regressions: empty label history again returns an empty dataset and audit rejects it cleanly; model replay now reopens saved JSON, verifies its canonical digest and research contract, restores saved weights, standardizer and calibration, and blocks on missing/corrupt/mismatched saved output. The replay claim no longer depends on the in-memory serialization payload.

Verified locally on the integrated source:
- Complete `tests_engine` suite passed with three skips.
- Focused real PyTorch, review-fix, temporal-integrity, trainer and frozen-spec tests: 56 passed, no skips (CPU Torch 2.14.1+cpu).
- `uv build` produced the source distribution and wheel; `git diff --check` passed.
- The earlier seven A200 fixture failures were reproduced on clean main and resolved by separately reviewed/merged PR #447; runtime freshness gates were preserved.

Only synthetic data and temporary test ledgers were used. Frozen slots 0–4 and execution/production/auto-promotion prohibitions remain unchanged. These code checks do not establish GRU superiority to XGB or authorize a canonical-data holdout experiment. Fresh GitHub CI on the published integration commit remains the next merge gate.
