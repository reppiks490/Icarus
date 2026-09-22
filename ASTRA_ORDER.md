# Astra order of work — Grok (xAI) 2026-09-22

Handoff law: **`MODEL_HANDOFF.md`**. Pull first. Push before you stop.
Owner rule: unzip six batches → XGB → candidates.

## Sequence (hard)

0. `git pull --ff-only`. Unzip: `python -m icarus_engine.unzip_batches --fetch`
   Do not ingest BATS into HistoryHub.
1. Read `GOAL.md`, `ASTRA_DO_NOT.md`, `MODELS_GROK.md`, `TRAINERS_GROK.md`, `EVENTS_GROK.md`.
2. Build XGBoost per `MODELS_GROK.md` on NQ ES YM GC SI PL PA BTCF BTC only.
3. Write `run/trainers/{SYM}_{family}_xgb.json`.
4. Only then `python -m icarus_engine.audit … --require-xgb`.
5. Never hook XGB into Pulse/emulator.
6. `git add` / `git commit -m "Astra: …"` / `git push`. Append `HANDOFF_LOG.md`.
