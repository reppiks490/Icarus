# Astra order of work — Grok (xAI) 2026-09-22

Handoff: `MODEL_HANDOFF.md`. Numbers: **`SPEC.md`** / `icarus_engine/spec.py`.

0. `git pull --ff-only`. `python -m icarus_engine.unzip_batches --fetch`
1. Read SPEC.md, ASTRA_DO_NOT.md, MODELS_GROK.md.
2. Fit slot 1 with **exact** `XGB_CLASSIFIER`. Features = `FEATURE_KEYS` only.
3. Write `run/trainers/{SYM}_{family}_xgb.json`.
4. Swap JSON only if SPEC swap rule holds. `--require-xgb`.
5. No Pulse hook. Commit `Astra:` + HANDOFF_LOG.md.
