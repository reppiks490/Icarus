# Grok (xAI) — ownership map

For **Claude, Astra, and any later agent**. Grep the tree for `Grok (xAI)`.

Astra wrote the original engine, Pine port, emulator, bridge, and tests
(`312ff25`, 2026-09-20). Grok filled the unpaid gaps (PR #1 / `df89e8b`),
signed every file (PR #2), added FOMC 2027 + bridge tests (PR #3), and
built the local paper-trading **plant**.

Do **not** undo these constraints without the owner asking:

- Do not scrape TradingView.
- Do not invent ticks, queue, or spread.
- A TradingView CME pack is **display**. It does not feed this Python process.
- Do not add Databento without keys.
- Alpaca `NQ1! → QQQ` is a percent-mapped equity proxy, not an NQ fill.
- Do not Docker the engine as the primary deploy: it binds `127.0.0.1` against DNS rebinding.
- Do not drop `BATS_*` candidate CSVs into `history/drop/`.
- Do not concatenate Renko/range/tick rows into the clock trainer.
- Do not rewrite `strategy/pulse.py` or `emulator.py` to hook trainers.

## Files Grok added (whole file)

See git history for the plant/feed/doctor list (bars.py, icarus_plant, ASTRA_HANDOFF, PARITY, presets, tests_engine).

## 2026-09-22 CSV / ML boundary (this look)

| File | What |
|---|---|
| `CANDIDATE_COG_GROK.md` | Six equity batches = Opus sensors, not HistoryHub |
| `ENGINE_UNIVERSE_GROK.md` | Every REGISTRY asset sockets |
| `UNIVERSES.json` | complexes + candidate packs |
| `TRAINERS_GROK.md` | Family split |
| `icarus_engine/trainers/` | `train_file` / logit. `execution_authorized` always false |

`python -m icarus_engine.trainers --path FILE --chart-type renko --asset NQ`

No pytest for trainers yet. No `icarus-engine train` subcommand yet. Logit is a stub; keep family split and next-bar-on-this-index labels. MBT/SOL have no CSV — do not alias.

## Still unpaid / not Grok's to fake

Live undisplayed NQ tape, CME non-display, futures-broker fills.
