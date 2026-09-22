# Astra / Opus — do not — Grok (xAI) 2026-09-22

Read with ASTRA_HANDOFF.md and GROK.md. Owner did not authorize the list under Never.

## Never
- Rewrite `icarus_engine/strategy/pulse.py` or `emulator.py` to hook trainers or candidates.
- Scrape TradingView. Ingest only files the owner exported.
- Invent ticks, queue, spread, or MBT/SOL bars.
- Treat QQQ as NQ. Treat AAPL/MSFT as NQ fills. Treat Coinbase spot as CME BTCF P&L.
- Drop `BATS_*`, `LSE_DLY_MAG7`, `BCBA_DLY_TSMC` into `history/drop/` or `ingest-bars` as NQ/ES/YM.
- Concatenate Renko, range, or tick rows into `history/{SYM}_1m.csv` or into `clock_minutes` training.
- Merge `60` with `61`. Treat `1M` as 1-minute. Treat `30S` as tick.
- Average holdout_acc across families and call it a model.
- Set `execution_authorized` true. Trainers never arm a broker.
- Bind 0.0.0.0. Add XAI_API_KEY to the plant. Docker as the primary deploy.
- Alias MBT from BTCF or SOL from ETH. Alias ETH execution from index_ethusd.
- Label SI/PL/PA from GC Pulse. Label stocks from NQ Pulse.
- Use Tide Long/Short as labels. They are features. Labels are emulator/Pulse on the execution symbol.
- Use empty MP POC/VAH/VAL as profile charts. Those columns are often NaN.
- Replace HistoryHub with candidate CSVs. Two brains: execution tape vs sensors.

## May
- Replace the logit in `icarus_engine/trainers/logit.py`. Keep the family split and next-bar-on-this-index labels.
- Extend `tests_engine/test_trainers.py`.
- Wire `icarus-engine train` later. Until then: `python -m icarus_engine.trainers`.
- Run Opus candidate audit off the six zips in `multi-level-csv` without plant ingest.
- Export MBT, SOL, Coinbase ETHUSD, TPO/footprint later as new families. Do not fake them.

## Train command
```
python -m icarus_engine.trainers --path FILE --chart-type minutes|hours|seconds|daily|weekly|renko|range|tick --asset NQ --out run/trainers/NQ_clock.json
```
`execution_authorized` in the JSON is always false.
