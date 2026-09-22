# Astra order — Grok (xAI) 2026-09-22

Schwab = Market Data only. Not the executing broker.

1. git pull --ff-only
2. python -m icarus_engine.unzip_batches --fetch
3. If secrets/schwab_token.json exists: python -m icarus_plant.schwab_poll --once
   Else skip Schwab and log it. Do not paste secrets.
4. Fit XGB on owner CSVs for NQ ES YM GC SI PL PA BTCF BTC. Then audit --require-xgb
5. git commit -m "Astra: …" && git push && HANDOFF_LOG.md
