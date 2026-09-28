# Results — Slot 0/1 study (2026-09-27)

Protocol: [PREREGISTRATION.md](PREREGISTRATION.md), committed and pushed (657f9ab) before the run. One run, code at
`657f9ab619f7`. All 23 selected files passed the DATA gate clean and were fitted; every holdout is claimed in
`C:\Users\tripl\icarus-studies\holdout_ledger.sqlite3`. Raw numbers: [results.json](results.json).

## Pre-registered verdict
A study shows incremental value only if it is PASS (raw XGB log loss below the converged logistic's and the
null's) **and** survives Benjamini-Hochberg at q = 0.10 on the paired per-row test against the logistic.

**Two of 23 qualify: GC clock_hours (1h) and YM clock_hours (4h). Neither is a usable edge.**
- **GC 1h** is the only study that beats both baselines by a visible margin (0.678 vs 0.709 logistic, 0.692 null).
  Its holdout sign accuracy is 0.541 with a Wilson 95% interval of [0.460, 0.619], which includes 0.5.
- **YM 4h** beats the logistic but ties the null (0.69253 vs 0.69257).
- ES 4h survives the correction against the logistic but loses to the null, so it fails the gate.

## Table
Log loss on the terminal holdout (lower is better). d = mean per-row log loss, XGB minus logistic; p is one-sided.

| sym | family | n hold | XGB | logistic | null | gate | d | p | BH q=.10 | accuracy [Wilson 95%] |
|---|---|---|---|---|---|---|---|---|---|---|
| ES | clock_daily | 60 | 0.6949 | 0.7015 | 0.6957 | PASS | -0.0066 | 0.380 | no | 0.483 [0.362, 0.607] |
| ES | clock_hours | 234 | 0.6972 | 0.7182 | 0.6925 | FAIL | -0.0210 | 0.001 | yes | 0.500 [0.436, 0.564] |
| ES | clock_minutes | 299 | 0.6916 | 0.6926 | 0.6940 | PASS | -0.0010 | 0.416 | no | 0.502 [0.445, 0.558] |
| ES | range | 225 | 0.5319 | 0.5264 | 0.6618 | FAIL | +0.0055 | 0.765 | no | 0.778 [0.719, 0.827] |
| GC | clock_hours | 148 | 0.6783 | 0.7091 | 0.6920 | PASS | -0.0308 | 0.013 | yes | 0.541 [0.460, 0.619] |
| GC | clock_minutes | 343 | 0.6928 | 0.6962 | 0.6932 | PASS | -0.0035 | 0.020 | no | 0.536 [0.484, 0.589] |
| GC | range | 228 | 0.5796 | 0.5962 | 0.6976 | PASS | -0.0166 | 0.133 | no | 0.737 [0.676, 0.790] |
| NQ | clock_daily | 60 | 0.6966 | 0.7261 | 0.6972 | PASS | -0.0296 | 0.197 | no | 0.467 [0.346, 0.591] |
| NQ | clock_hours | 238 | 0.7179 | 0.6988 | 0.6921 | FAIL | +0.0192 | 0.912 | no | 0.508 [0.445, 0.571] |
| NQ | clock_minutes | 349 | 0.6987 | 0.6943 | 0.6930 | FAIL | +0.0044 | 0.879 | no | 0.484 [0.432, 0.537] |
| NQ | range | 222 | 0.4973 | 0.5091 | 0.6461 | PASS | -0.0118 | 0.039 | no | 0.788 [0.730, 0.837] |
| PA | clock_hours | 230 | 0.6952 | 0.6977 | 0.6920 | FAIL | -0.0025 | 0.303 | no | 0.470 [0.406, 0.534] |
| PA | clock_minutes | 342 | 0.6934 | 0.6855 | 0.6929 | FAIL | +0.0079 | 0.993 | no | 0.477 [0.424, 0.530] |
| PA | range | 171 | 0.7087 | 0.6957 | 0.6974 | FAIL | +0.0130 | 0.910 | no | 0.632 [0.557, 0.700] |
| PL | clock_hours | 234 | 0.6979 | 0.6952 | 0.6929 | FAIL | +0.0027 | 0.675 | no | 0.479 [0.415, 0.542] |
| PL | clock_minutes | 414 | 0.6947 | 0.6946 | 0.6931 | FAIL | +0.0002 | 0.519 | no | 0.495 [0.447, 0.543] |
| PL | range | 228 | 0.5775 | 0.5751 | 0.6935 | FAIL | +0.0023 | 0.619 | no | 0.750 [0.690, 0.802] |
| SI | clock_hours | 234 | 0.6930 | 0.6930 | 0.6938 | FAIL | +0.0001 | 0.507 | no | 0.513 [0.449, 0.576] |
| SI | clock_minutes | 332 | 0.6992 | 0.6930 | 0.6947 | FAIL | +0.0062 | 0.885 | no | 0.491 [0.438, 0.545] |
| YM | clock_daily | 60 | 0.7199 | 0.7001 | 0.6936 | FAIL | +0.0198 | 0.766 | no | 0.583 [0.457, 0.699] |
| YM | clock_hours | 234 | 0.6925 | 0.7115 | 0.6926 | PASS | -0.0190 | 0.005 | yes | 0.517 [0.453, 0.580] |
| YM | clock_minutes | 325 | 0.6919 | 0.6896 | 0.6930 | FAIL | +0.0022 | 0.764 | no | 0.511 [0.457, 0.565] |
| YM | range | 228 | 0.5835 | 0.5684 | 0.7012 | FAIL | +0.0152 | 0.976 | no | 0.759 [0.699, 0.810] |

## Reading it honestly
- **Clock charts (1m, 1h/4h, daily):** next-bar sign is essentially unpredictable from these nine features. Most
  log losses sit at 0.69, about ln 2, and the converged logistic is often *worse than a constant*. So "XGB beats the
  logistic" usually means the logistic generalises badly, not that XGB found something. The null comparison is
  what keeps the gate honest.
- **Range bars:** every model reaches 0.63-0.79 accuracy; the logistic's sign accuracy is identical to XGB's in all six files. That is how range bars are
  built: a bar completes only after a full range move, so bar-to-bar direction persists by construction. It is
  not a tradeable forecast, and XGB adds nothing over the logistic there (only GC and NQ range beat it, and
  neither survives the correction).
- **Sample sizes:** 60 holdout sessions for daily files, 148-238 bars for hourly files, and a few hours for
  1-minute files. Nothing here supports a claim about profitability, and no preset or input should change
  because of it.
- **Next step, per the protocol:** these holdouts are spent. A follow-up needs later data: the 20-minute RTH
  candle exports the engine actually trades, scrolled back as far as the plan allows.

`execution_authorized=false`.
