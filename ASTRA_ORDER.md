# Astra order — Grok (xAI) 2026-09-22 week-end

1. git pull --ff-only. Read ASTRA_DO_NOT.md, SPEC.md, MODELS_GROK.md, SCHWAB_GROK.md.
2. python -m icarus_engine.unzip_batches --fetch
   BATS → unzipped/candidates only. Not HistoryHub tape.
3. Fit slot 1 XGB per spec.py (or OVERRIDE + log). Symbols: NQ ES YM GC SI PL PA BTCF BTC.
   Skip MBT SOL ETHUSD. Skip missing CSVs.
4. Write run/trainers/{SYM}_{family}_xgb.json
5. Then python -m icarus_engine.audit … --require-xgb
6. Schwab quote CSVs under history/schwab/ are optional clock last-prints. Do not use them as labels instead of owner family CSVs. Do not OAuth.
7. git commit -m "Astra: …" && git push. Append HANDOFF_LOG.md.
8. Never Pulse. Never POST /orders.
