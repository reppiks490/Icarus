# Model handoff — Grok (xAI) 2026-09-22

Owner rule: **nothing stays only on one model's disk.**
Every Astra or Opus change is committed and pushed so the next model (Astra, Opus, or Grok) can continue from GitHub.
Grok's job on each wake: read new commits, fix contradictions, update these instruction files.

Repo: `reppiks490/Icarus` branch `main`. CSV zips stay in `reppiks490/multi-level-csv`.

## Astra and Opus — every session

1. `git pull --ff-only` first. Do not reset --hard over someone else's work unless the owner says so.
2. Read `ASTRA_ORDER.md` or `OPUS_ORDER.md`, `ASTRA_DO_NOT.md`, `MODEL_HANDOFF.md`.
3. Do the work.
4. **Commit + push before you stop**, even if unfinished. Small commits, often.
5. Append `HANDOFF_LOG.md` with: who, time UTC, files, what works, what is blocked, next command.

Commit message prefix:
- `Astra:` …
- `Opus:` …
Do not use `Grok (xAI):` — that prefix is Grok only.

Never commit: secrets, `.env`, `XAI_API_KEY`, broker keys, unzipped multi-MB CSVs, `history/*.csv` tapes, `__pycache__`, `.venv`.
Do commit: code, tests, trainer **reports** under `run/trainers/*.json` if small, audit JSON, docs, `HANDOFF_LOG.md`.

If push fails, write `HANDOFF_LOG.md` locally and tell the owner. Do not keep a private fork as the source of truth.

## Grok — every session

1. `git log` since last `Grok (xAI):` commit.
2. Diff Astra/Opus files against `ASTRA_DO_NOT.md` (Pulse rewrite, BATS ingest, MBT/SOL/ETHUSD, execution_authorized).
3. Update instruction md if they drifted. Fix only broken contracts; do not wipe their trainers.
4. Push `Grok (xAI):` commits. Append `HANDOFF_LOG.md`.

Grok does not auto-run while this chat is closed. Owner starts Grok or a scheduled Grok job after Astra/Opus push.

## Next model paste

```
Pull Icarus main. Read MODEL_HANDOFF.md, ASTRA_DO_NOT.md, then your ORDER file.
git pull --ff-only. Do the next unfinished step. Commit and push before you stop. Append HANDOFF_LOG.md.
Do not rewrite Pulse. Do not trade MBT/SOL/ETHUSD.
```
