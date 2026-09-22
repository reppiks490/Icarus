# Astra / Opus — do not — Grok (xAI) 2026-09-22

First: `ASTRA_ORDER.md` + `MODELS_GROK.md`. Owner did not authorize Never.

## Never
- Rewrite `icarus_engine/strategy/pulse.py` or `emulator.py` to hook trainers, XGB, or candidates.
- Scrape TradingView. Ingest only files the owner exported.
- Invent ticks, queue, or spread.
- Treat QQQ as NQ. Treat AAPL/MSFT as NQ fills. Treat Coinbase spot as CME BTCF P&L.
- Drop `BATS_*`, `LSE_DLY_MAG7`, `BCBA_DLY_TSMC` into `history/drop/` as NQ/ES/YM.
- Concatenate Renko, range, or tick rows into `history/{SYM}_1m.csv` or `clock_minutes` training.
- Merge `60` with `61`. Treat `1M` as 1-minute. Treat `30S` as tick.
- Average holdout_acc across families and call it a model.
- Set `execution_authorized` true.
- Bind 0.0.0.0. Add XAI_API_KEY to the plant. Docker as the primary deploy.
- Trade, start, train, or alias `MBT`, `SOL`, or `ETH`/`ETHUSD`.
- Run Astra candidate **swap** before `run/trainers/{SYM}_{family}_xgb.json` exists.
- Label SI/PL/PA from GC Pulse. Label stocks from NQ Pulse.
- Use Tide as labels. Use empty MP columns as profile charts.
- Replace HistoryHub with candidate CSVs.

## May
- `pip install -e ".[ml]"` and implement XGBoost per `MODELS_GROK.md`.
- Keep the logit as baseline.
- Opus may inspect the six zips. That is not a swap.
- Astra audit with `--require-xgb` after artifacts exist.
- Export TPO/footprint later. Do not export MBT/SOL/ETHUSD.

```
pip install -e ".[ml]"
python -m icarus_engine.trainers --path FILE --chart-type minutes --asset NQ --out run/trainers/NQ_clock_minutes.json
python -m icarus_engine.audit --exec history/NQ_1m.csv --cand FILE --future NQ --asset AAPL --require-xgb
```
