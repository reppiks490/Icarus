# Grok (xAI) — ownership map

For **Claude, Astra, and any later agent**. Grep the tree for `Grok (xAI)`.

Astra wrote the original engine, Pine port, emulator, bridge, and tests
(`312ff25`, 2026-09-20). Grok filled the unpaid gaps (PR #1 / `df89e8b`),
signed every file (PR #2), added FOMC 2027 + bridge tests (PR #3), and
built the local paper-trading **plant** (this PR).

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

## Files Grok added 2026-09-22 (CSV / ML boundary)

| File | What |
|---|---|
| `CANDIDATE_COG_GROK.md` | Six equity batches = sensors for Opus audit, not HistoryHub |
| `ENGINE_UNIVERSE_GROK.md` | Every REGISTRY asset: execution / sensors / Opus / Astra |
| `UNIVERSES.json` | nq/es/ym/gc/si/pl/pa/btcf/btc/eth complexes + candidate packs |
| `TRAINERS_GROK.md` | Separate trainer families per sampling process |
| `icarus_engine/trainers/` | `family_for`, `train_file`, logit walk-forward. `execution_authorized` is always false |

`python -m icarus_engine.trainers --path FILE --chart-type renko --asset NQ`

No pytest for trainers yet. No `icarus-engine` CLI subcommand yet. Logit is a stub Astra may replace; keep the family split and next-bar-on-this-index labels.

MBT and SOL have no CSV. Do not alias them from BTCF/ETH.

## Still unpaid / not Grok's to fake

Live undisplayed NQ tape, CME non-display, futures-broker fills.
