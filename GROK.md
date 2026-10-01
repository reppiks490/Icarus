# Grok (xAI) — ownership map

Grep `Grok (xAI)`. Owner-hard list: `ASTRA_DO_NOT.md`. Astra/Opus may beat Grok spec: `OVERRIDE.md`.
Every model logs to `HANDOFF_LOG.md` via `icarus_engine.model_log.log_action`.

## Read first
SPEC.md, OVERRIDE.md, MODEL_HANDOFF.md, ASTRA_ORDER.md / OPUS_ORDER.md, GOAL.md.

## Grok 2026-09-22 surface
GOAL.md ASTRA_DO_NOT.md ASTRA_ORDER.md OPUS_ORDER.md OVERRIDE.md MODEL_HANDOFF.md HANDOFF_LOG.md
SPEC.md MODELS_GROK.md EVENTS_GROK.md CANDIDATE_COG_GROK.md ENGINE_UNIVERSE_GROK.md CSV_ACCESS_GROK.md TRAINERS_GROK.md
UNIVERSES.json
icarus_engine/spec.py ignore_trade.py csv_access.py unzip_batches.py model_log.py
icarus_engine/trainers/ (families dataset logit xgb_slot run)
icarus_engine/events/ icarus_engine/audit/ icarus_engine/failure/
icarus_plant/drop.py layout.py
tests_engine/test_spec.py test_trainers.py test_events.py test_drop_candidates.py test_audit.py test_ignore_trade.py test_csv_access.py test_model_log.py

Logit = slot 0. XGB slot 1 = Astra (`xgb_slot.py`). execution_authorized false.
MBT/SOL/ETHUSD ignored. BATS not HistoryHub.

## Still not Grok's to fake
Live NQ tape, broker fills, bookmap, news wire.
