# Astra order of work — Grok (xAI) 2026-09-22

Owner rule: **build the ML that serves this stack before you run candidates.**
Do not skip to audit because Opus can already score a CSV pair.

## Sequence (hard)

1. **Read** `GOAL.md`, `ASTRA_DO_NOT.md`, `TRAINERS_GROK.md`, `EVENTS_GROK.md`.
2. **Build** the ML systems that benefit execution + candidate *later*:
   - Replace `icarus_engine/trainers/logit.py` (stub is not the system).
   - One trainer family per sampling process (`family_for`). Do not mix indexes.
   - Fit **traded** symbols only: NQ, ES, YM, GC, SI, PL, PA, BTCF, BTC.
   - Ignore `MBT`, `SOL`, `ETH`/`ETHUSD` (`ignore_trade.py`).
   - Keep next-bar-on-this-index labels. Keep `execution_authorized: false`.
   - Wire FOMC/`any_macro` already on the rows. Add owner `history/events/*.csv` when present.
3. **Write** models to `run/trainers/{SYM}_{family}.json` and prove holdout per family.
4. **Only then** run candidate audits (`python -m icarus_engine.audit …`) and decide swaps.
   Candidates are sensors. They are not HistoryHub and not fills.
5. Never rewrite Pulse or the emulator to “hook” a model.

## What “ML that benefits this” means

| System | Serves |
|---|---|
| Clock trainers | NQ/ES/YM/metals/BTCF/BTC time bars |
| Renko/range/tick trainers | Same symbols, own index |
| Event features | FOMC + owner prints on those trainers |
| Candidate scorer | Uses the **fitted** family model + sign/Tide/macro agree |
| Failure brain | Losers after the engine has trades, not before step 2 |

Opus may inspect CSVs. Astra does not treat an Opus draft as a finished candidate run.

If a candidate JSON exists and `run/trainers/` is empty: **stop. Build trainers first.**
