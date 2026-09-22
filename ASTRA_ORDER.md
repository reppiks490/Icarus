# Astra order of work — Grok (xAI) 2026-09-22

Owner rule: **unzip the six newest CSV batches, then build the ML, then candidates.**
Model spec: **`MODELS_GROK.md`**. Unzip: **`CSV_ACCESS_GROK.md`**.

## Sequence (hard)

0. **Unzip** the six batches from `reppiks490/multi-level-csv`:
   `python -m icarus_engine.unzip_batches --fetch`
   Owner could not reach these files. You do it. Do not ingest BATS into HistoryHub.
1. **Read** `GOAL.md`, `ASTRA_DO_NOT.md`, `MODELS_GROK.md`, `TRAINERS_GROK.md`, `EVENTS_GROK.md`.
2. **Build** XGBoost per `MODELS_GROK.md` on traded symbols only (not MBT/SOL/ETHUSD).
3. **Write** `run/trainers/{SYM}_{family}_xgb.json`.
4. **Only then** candidate audit with `--require-xgb`.
5. Never hook XGB into `pulse.py` / `emulator.py`.
