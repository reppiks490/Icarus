# Frozen spec — Grok (xAI) 2026-09-22

Code copy: `icarus_engine/spec.py`. If this file and that file disagree, **spec.py wins**.
Astra/Opus do not invent extra slots, features, or symbols.

## Universe
Trade: NQ ES YM GC SI PL PA BTCF BTC.
Ignore: MBT SOL ETH ETHUSD.
Families: clock_minutes hours seconds daily weekly, renko, range, tick.
Skip a missing CSV. Do not synthesize bars.

## Label
`y ∈ {+1, −1}` = sign of next bar close−close on **this file's index**.
Drop flat bars. Tide / MP / candidate close are never labels.

## Features (required, this order)
`ret_1, ret_3, body, range, close_loc, tide, run, fomc, any_macro`
Optional if the join exists: `cpi, nfp, earnings, vix_z, tnx_z, dxy_z`.
Events: `ts_event <= ts_bar` only.

## Split
Time order. 60% train / 20% valid / 20% holdout. No shuffle.
Valid is for early stop only. Report holdout logloss + sign accuracy.
`execution_authorized` is always false.

## Slot 1 XGB (required before swap)
```
objective binary:logistic
tree_method hist
max_depth 4
eta 0.05
subsample 0.8
colsample_bytree 0.8
min_child_weight 8
lambda 1.0
n_estimators 400
early_stopping_rounds 40
eval_metric logloss
seed 7
```
Calibrate **isotonic on holdout only** after the booster is frozen.
Write `run/trainers/{SYM}_{family}_xgb.json` with keys:
`slot, symbol, family, n_train, n_valid, n_hold, holdout_acc, holdout_logloss, features, params, execution_authorized=false`.
Also keep `run/trainers/{SYM}_{family}_logit.json`.

## Slot 2 ranker (after slot 1 exists)
Inputs per candidate: `sign_agree, tide_agree, macro_agree, overlap` from `score_pair`.
Target: 1 if next execution bar agrees with candidate sign.
Artifact: `run/trainers/{FUT}_{family}_rank.json`.

## Slot 3 regime
Fit only if a vol/RATE series exists for that symbol. Else write `status: skipped`.
Do not block slot 1.

## Slot 4 fail
Fit only if `losers_from_journal` returns `n_losers >= 30`. Else skipped.

## Swap (not Pulse)
Astra writes `run/audit/{CAND}__vs__{FUT}_{family}.json`.
`swap_recommend` is true iff all of:
- `run/trainers/{FUT}_{family}_xgb.json` exists
- overlap ≥ 200
- sign_agree ≥ 0.55
`execution_authorized` stays false. Nobody calls `pulse.py`.

## Unzip
`python -m icarus_engine.unzip_batches --fetch`
Six zips only: Csv first 60, First 60 half, Csv 2nd 60, 2nd 60 half, Csv last 57, Last 57 half.

## Git
`MODEL_HANDOFF.md`. Prefix `Astra:` / `Opus:` / `Grok (xAI):`.
