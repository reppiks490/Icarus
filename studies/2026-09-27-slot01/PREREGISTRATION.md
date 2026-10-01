# Pre-registration — Slot 0/1 study on the owner's TradingView exports (2026-09-27)

Written and committed by Claude (Opus 5.5) **before any holdout below was scored**. The study runs once
(`run_study.py --run` refuses to overwrite its results). Nothing here authorizes trading:
`execution_authorized=false` throughout.

## Question
For each traded symbol and trainer family, does the frozen Slot 1 XGB (`spec.XGB_CLASSIFIER`, unchanged) predict
the sign of the next bar's close-to-close move on the terminal 20% holdout better than
1. a converged ridge logistic on the same nine `FEATURE_KEYS` (`logit.fit_newton`, fitted on train only), and
2. the train-slice base rate (null)?

## Data (fixed by rule, not by looking at results)
- Source: `C:\Users\tripl\Downloads\Csv\Csv` (the owner's 144-file TradingView archive, delayed `_DL_` feeds),
  classified in `icarus-bridge/research/tv-exports/classification.json` (2026-09-21).
- Symbols: `spec.TRADED` present in the archive: NQ ES YM GC SI PL PA (no BTC/BTCF files exist).
- Chart types: candles (1m, 1h, 4h, 1D) and Range bars. Kagi, point-and-figure, line-break and unclassified
  irregular series have no trainer family and are excluded.
- A file is eligible if it has at least its family's `min_rows`. One file per (symbol, family): most rows; a tie
  goes to the first file name. Every file passes the DATA gate or is reported as blocked, never trained.

| symbol | family | chart | rows | file |
|---|---|---|---|---|
| ES | clock_daily | 1D | 300 | `CME_MINI_DL_ES1!, 1D` |
| ES | clock_hours | 4h | 1175 | `CME_MINI_DL_ES1!, 4` |
| ES | clock_minutes | 1m | 1782 | `CME_MINI_DL_ES1!, 1 5` |
| ES | range | range | 1122 | `CME_MINI_DL_ES1!, 1 6` |
| GC | clock_hours | 1h | 741 | `COMEX_DL_GC1!, 60` |
| GC | clock_minutes | 1m | 1782 | `COMEX_DL_GC1!, 1 4` |
| GC | range | range | 1139 | `COMEX_DL_GC1!, 1 5` |
| NQ | clock_daily | 1D | 300 | `CME_MINI_DL_NQ1!, 1D` |
| NQ | clock_hours | 4h | 1187 | `CME_MINI_DL_NQ1!, 3` |
| NQ | clock_minutes | 1m | 1782 | `CME_MINI_DL_NQ1!, 1 4` |
| NQ | range | range | 1110 | `CME_MINI_DL_NQ1!, 1 5` |
| PA | clock_hours | 4h | 1170 | `NYMEX_DL_PA1!, 2` |
| PA | clock_minutes | 1m | 2183 | `NYMEX_DL_PA1!, 1 3` |
| PA | range | range | 852 | `NYMEX_DL_PA1!, 1 5` |
| PL | clock_hours | 4h | 1175 | `NYMEX_DL_PL1!, 3` |
| PL | clock_minutes | 1m | 2189 | `NYMEX_DL_PL1!, 1 3` |
| PL | range | range | 1139 | `NYMEX_DL_PL1!, 1 5` |
| SI | clock_hours | 4h | 1175 | `COMEX_DL_SI1!, 3` |
| SI | clock_minutes | 1m | 1777 | `COMEX_DL_SI1!, 1 4` |
| YM | clock_daily | 1D | 300 | `CBOT_MINI_DL_YM1!, 1D` |
| YM | clock_hours | 4h | 1175 | `CBOT_MINI_DL_YM1!, 4` |
| YM | clock_minutes | 1m | 1768 | `CBOT_MINI_DL_YM1!, 1 4` |
| YM | range | range | 1139 | `CBOT_MINI_DL_YM1!, 1 5` |

16 files are excluded for too few rows (listed in `results.json`).

## Protocol
- Split: time order, 60/20/20 with a one-row embargo at each edge; no shuffle. Validation is used only for
  early stopping. The terminal holdout is scored once, raw.
- Every holdout is claimed in the ledger `C:\Users\tripl\icarus-studies\holdout_ledger.sqlite3` **before** it
  is scored. Any later study on these files must use that ledger; a changed study on the same intervals is
  blocked there.
- Artifacts are validated with `qualify_xgb`, replayed from the rows.
- Slot 0 (the original 120-step logistic) is reported descriptively only.

## Endpoints
1. **Primary, per study:** `incremental_value_status` (PASS iff raw XGB holdout log loss < the converged logistic's
   AND < the null's).
2. **Primary, across studies:** paired per-row holdout log-loss difference XGB − logistic. One-sided test (XGB
   better) with a normal approximation, then **Benjamini-Hochberg at q = 0.10** over every fitted study. A study
   "shows incremental value" only if it is PASS **and** survives BH.
3. **Secondary, descriptive:** raw holdout sign accuracy with a Wilson 95% interval; Slot 0 holdout accuracy.

## What a result can and cannot mean
- A surviving study is a statistical statement about next-bar sign probabilities on one delayed export over its
  last 20% of rows (about 6 hours for 1-minute files, about 7 weeks for 4-hour files, 60 sessions for daily).
  It is **not** a trading edge, a profitability estimate, or a reason to change any preset or input.
- Nothing is re-run with different parameters on these holdouts. A follow-up needs new, later data.
- If nothing survives, that is the result and is reported as such.

## Code
Branch `opus/study-slot01`, the commit that adds this file; `repo_revision` is recorded in `results.json`.
