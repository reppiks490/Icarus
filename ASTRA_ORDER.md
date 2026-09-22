# Astra order of work — Grok (xAI) 2026-09-22

Owner rule: **build the ML that serves this stack before you run candidates.**
Model spec: **`MODELS_GROK.md`**. Primary model is **XGBoost**, not the logit stub.

## Sequence (hard)

1. **Read** `GOAL.md`, `ASTRA_DO_NOT.md`, `MODELS_GROK.md`, `TRAINERS_GROK.md`, `EVENTS_GROK.md`.
2. **Build** the models in `MODELS_GROK.md`:
   - Slot 0 logit baseline (already in tree).
   - Slot 1 **XGBoost** next-bar sign per traded symbol × family.
   - Slot 2 candidate ranker.
   - Slot 3 regime model.
   - Slot 5 calibration on holdout.
   - Slot 4 failure model only after journal losers exist.
   - Ignore `MBT`, `SOL`, `ETH`/`ETHUSD`.
   - `execution_authorized` stays false. Do not rewrite Pulse.
3. **Write** `run/trainers/{SYM}_{family}_xgb.json` (and keep logit baseline).
4. **Only then** candidate audit. If the XGB for that execution family is missing: **stop.**
5. Never hook XGB into `pulse.py` / `emulator.py`.

Opus may inspect CSVs. An Opus draft is not Astra's candidate pass.
