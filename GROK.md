# Grok (xAI) — ownership map

For **Claude, Astra, and any later agent**. Grep the tree for `Grok (xAI)`.

Astra wrote the original engine, Pine port, emulator, bridge, and tests
(`312ff25`, 2026-09-20). Grok filled unpaid gaps (feeds/bars, plant, doctor,
FOMC list, start scripts) and the 2026-09-22 CSV/ML boundary.

Do **not** undo these without the owner asking:

- Do not scrape TradingView.
- Do not invent ticks, queue, or spread.
- A TradingView CME pack is **display**. It does not feed this Python process.
- Do not add Databento without keys.
- Alpaca `NQ1! → QQQ` is a percent-mapped equity proxy, not an NQ fill.
- Do not Docker the engine as the primary deploy: it binds `127.0.0.1`.
- Do not drop `BATS_*` into HistoryHub.
- Do not concatenate Renko/range/tick into the clock trainer.
- Do not rewrite `strategy/pulse.py` or `emulator.py` to hook trainers.

Full never-list: `ASTRA_DO_NOT.md`.

## Plant / feed files Grok owns (pre-CSV work)

`icarus_engine/feeds/bars.py`, `icarus_plant/` (drop, layout, supervisor, cli, downloads),
`start-plant.*`, `start-engine-background.*`, `COMMANDS.md`, `SETUP.md`, `PAID_NEXT.md`,
`ASTRA_HANDOFF.md`, `tests_engine/test_plant.py`, `tests_engine/test_bars.py`,
`tests_engine/test_fomc.py`, FOMC dates inside `strategy/inputs.py`.

Older line-by-line table: commit `90ea0e7` `GROK.md`.

## 2026-09-22 CSV / ML boundary (Grok)

| File | What |
|---|---|
| `GOAL.md` | Durable goal — delete Ultraglobal |
| `ASTRA_DO_NOT.md` | What Astra/Opus must not do |
| `EVENTS_GROK.md` | Event socket |
| `CANDIDATE_COG_GROK.md` | Six equity batches = sensors |
| `ENGINE_UNIVERSE_GROK.md` | Every REGISTRY asset |
| `UNIVERSES.json` | complexes + candidate packs |
| `TRAINERS_GROK.md` | Family split |
| `icarus_engine/trainers/` | `icarus-train`. Labels on own index |
| `icarus_engine/events/` | FOMC from `Inputs().fomc_dates` + owner CSV |
| `icarus_engine/audit/` | Candidate vs execution JSON |
| `icarus_engine/failure/` | Journal losers, any pnl table or CSV |
| `icarus_plant/drop.py` | BATS → `history/drop/candidates/` |
| `tests_engine/test_trainers.py` | families, sort, fit |
| `tests_engine/test_events.py` | seed == engine FOMC list |
| `tests_engine/test_drop_candidates.py` | BATS not NQ |
| `tests_engine/test_audit.py` | score_pair + losers |

```
icarus-train --path FILE --chart-type renko_brick_100 --asset NQ --out run/trainers/NQ_renko.json
python -m icarus_engine.audit --exec history/NQ_1m.csv --cand FILE --future NQ --asset AAPL --out run/audit/AAPL.json
```

Logit is a stub. `execution_authorized` is always false. MBT/SOL have no CSV — do not alias.

## Still unpaid / not Grok's to fake

Live undisplayed NQ tape, CME non-display, futures-broker fills, bookmap, news wire.
