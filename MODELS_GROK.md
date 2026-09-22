# Models Astra must build — Grok (xAI) 2026-09-22

The file `icarus_engine/trainers/logit.py` is a **baseline stub only**.
Owner wants **advanced, task-specific models**. Primary booster: **XGBoost**
(current XGBoost, histogram / approx tree method — not a toy stump).
Do not ship one global net. Do not mix families.

Build these **before** candidate audit (`ASTRA_ORDER.md`).

## Required per traded symbol × family

Traded: NQ ES YM GC SI PL PA BTCF BTC. Ignore MBT SOL ETHUSD.
Families: clock_minutes, clock_hours, clock_seconds, clock_daily, clock_weekly, renko, range, tick.
Skip a cell if that CSV does not exist. Do not invent rows.

| Slot | Model | Why this task |
|---|---|---|
| 0 baseline | scaled L2 logit (already here) | Sanity / coefficient read |
| 1 primary | **XGBoost classifier** on next-bar sign | Tabular OHLC + Tide + FOMC/macro flags |
| 2 rank | XGBoost ranker *or* second XGB on P(agree) | Candidate swap: score names vs execution |
| 3 regime | gradient-boosted trees or HMM on RATE/FDI/vol | Do not trade the same weights in every vol state |
| 4 fail | XGB / logistic on journal losers | Brain E — after trades exist |
| 5 calibrate | Platt or isotonic on **holdout only** | Raw XGB margin is not a probability |

That is the “XGBoost + the other advanced models” set. Not five random architectures.

## Features (do not throw the kitchen at it)

Allowed on a family row: ret_1, ret_3, body, range, close_loc, tide, run, fomc, any_macro, cpi/nfp/earnings if dated events exist, vix_z/tnx_z/dxy_z when those CSVs as-of join.
Forbidden as labels: Tide, MP POC/VAH/VAL, candidate close.
Label: next bar **on this family's index** only.

## Fit rules

- Walk-forward on that file's own order. No shuffle.
- No future print: event flags use `ts <= bar.ts`.
- Early stop on valid slice. Report holdout logloss + sign acc.
- `execution_authorized` stays false.
- Save `run/trainers/{SYM}_{family}_xgb.json` (or joblib) **and** keep the logit file as baseline.
- Candidate audit may run only if the **primary XGB** for that execution family exists.

## Do not

- One XGB on concatenated 1m+renko+AAPL.
- Deep nets first. These series are short and event-sparse; trees first.
- Claim holdout acc is edge.
- Rewrite Pulse to call XGB.
