# Opus order of work — Grok (xAI) 2026-09-22

Same handoff as Astra: **`MODEL_HANDOFF.md`**. Push every change.
Opus **inspects** and drafts. Astra owns XGB + official candidate swap.

## Sequence

1. `git pull --ff-only`. Read `MODEL_HANDOFF.md`, `ASTRA_DO_NOT.md`, `CANDIDATE_COG_GROK.md`.
2. If unzipped CSVs missing: you may run `python -m icarus_engine.unzip_batches --fetch`. Do not ingest BATS into HistoryHub.
3. Inspect candidate vs execution joins. Write draft JSON under `run/audit/opus/`.
4. Do **not** call it a swap. Do **not** set `execution_authorized` true.
5. Do **not** replace `logit.py` with XGB unless Astra has not started and the owner names you. Default: leave slot 1 to Astra.
6. Commit `Opus:` + push + `HANDOFF_LOG.md` before you stop.

Never rewrite Pulse. Never trade MBT/SOL/ETHUSD.
