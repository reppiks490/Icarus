# Icarus goal (durable) — Grok (xAI) 2026-09-22

This file **is** the goal. Delete the live Ultraglobal.
Astra first read: **`ASTRA_ORDER.md`** then **`MODELS_GROK.md`**.
Also: `ASTRA_DO_NOT.md`, `EVENTS_GROK.md`.

## One sentence
Hybrid AI×ML brains swap candidates per asset per timeframe on owner CSV + dated events. Losers go to a separate brain. Execution stays REGISTRY minus MBT/SOL/ETHUSD. Candidates never become the tape.

## Astra sequence
1. Build `MODELS_GROK.md` (XGBoost primary, logit baseline) for NQ ES YM GC SI PL PA BTCF BTC × family.
2. Write `run/trainers/{SYM}_{family}_xgb.json`. Keep logit baseline.
3. **Then** candidate audit. If that XGB file is missing, stop.

## Brains
A Pulse (do not rewrite) · B HistoryHub · C audit after XGB · D trainers first · E losers after trades · F FOMC+owner events · G flow socket only.

## Credit paste
Follow GOAL.md, ASTRA_ORDER.md, MODELS_GROK.md. Obey ASTRA_DO_NOT.md. Do not rebuild Pulse.
