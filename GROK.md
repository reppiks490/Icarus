# Grok (xAI) — ownership map

For **Claude, Astra, and any later agent**. Grep the tree for `Grok (xAI)`.

Astra wrote the original engine, Pine port, emulator, bridge, and tests
(`312ff25`, 2026-09-20). Grok filled unpaid gaps, the plant, and the 2026-09-22 CSV/ML boundary.

Do **not** undo these constraints without the owner asking:

- Do not scrape TradingView.
- Do not invent ticks, queue, or spread.
- A TradingView CME pack is **display**. It does not feed this Python process.
- Do not add Databento without keys.
- Alpaca `NQ1! → QQQ` is a percent-mapped equity proxy, not an NQ fill.
- Do not Docker the engine as the primary deploy: it binds `127.0.0.1` against DNS rebinding.
- Do not drop `BATS_*` candidate CSVs into HistoryHub. `ingest-drop` quarantines them to `history/drop/candidates/`.
- Do not concatenate Renko/range/tick rows into the clock trainer.
- Do not rewrite `strategy/pulse.py` or `emulator.py` to hook trainers.

Full never-list: `ASTRA_DO_NOT.md`.
Plant/feed file list: commit `90ea0e7` GROK.md table.

## 2026-09-22 CSV / ML boundary

| File | What |
|---|---|
| `ASTRA_DO_NOT.md` | What Astra/Opus must not do |
| `CANDIDATE_COG_GROK.md` | Six equity batches = sensors |
| `ENGINE_UNIVERSE_GROK.md` | Every REGISTRY asset sockets |
| `UNIVERSES.json` | complexes + candidate packs |
| `TRAINERS_GROK.md` | Family split |
| `icarus_engine/trainers/` | `train_file` / scaled logit. `execution_authorized` always false |
| `tests_engine/test_trainers.py` | Family map, skip, synthetic fit |
| `tests_engine/test_drop_candidates.py` | BATS must not become NQ/AAPL history |
| `icarus_plant/drop.py` | Candidate quarantine |

```
icarus-train --path FILE --chart-type renko --asset NQ --out run/trainers/NQ_renko.json
python -m icarus_engine.trainers --path FILE --chart-type minutes --asset ES
```

`icarus-engine` CLI is Astra's. Train is a separate console script.
Logit is still a stub. MBT/SOL have no CSV — do not alias.

## Still unpaid / not Grok's to fake

Live undisplayed NQ tape, CME non-display, futures-broker fills.
