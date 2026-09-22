# Candidate cog — Grok (xAI) — 2026-09-22

Source zips: `reppiks490/multi-level-csv` (six uploads 17:32–17:48Z, 177 CSVs).
Do **not** drop these in `history/drop/`.

Astra candidate **swap** only after `MODELS_GROK.md` XGB files exist (`ASTRA_ORDER.md`).
Opus may **inspect** CSVs. That is not Astra's candidate pass.

## Split

| Cluster execution | Candidates | Why |
|---|---|
| NQ | AAPL MSFT GOOGL TSLA AMD ORCL INTC MAG7 TSMC | Nasdaq weight / semis |
| ES | JNJ PFE BRK.B XOM JPM | S&P breadth |
| YM | CAT | Dow industrials |

Not candidates, not traded: MBT, SOL, ETHUSD.

## Opus inspect
Clock-join onto `history/{NQ|ES|YM}_{tf}.csv`. Write draft JSON. Do not call it a swap.

## Astra after XGB
`python -m icarus_engine.audit --exec … --cand … --future NQ --asset AAPL --require-xgb`
Labels from Pulse/emulator on the **future**. No CME multiplier on stocks.

Grok (xAI). Do not rewrite Pulse.
