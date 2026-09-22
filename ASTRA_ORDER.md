# Astra order — Grok (xAI) 2026-09-22

Owner: Schwab is **data only**. Trading is another broker. You MAY pull Schwab quotes.

1. git pull --ff-only. Read ASTRA_DO_NOT.md SPEC.md SCHWAB_GROK.md.
2. unzip_batches --fetch. BATS → candidates only.
3. If $ICARUS_HOME/secrets/schwab_token.json exists:
   `python -m icarus_plant.schwab_poll --once`
   Use history/schwab/execution/*_quote.csv as **clock last-print** features only.
   If the token file is missing, skip Schwab and note it in HANDOFF_LOG. Do not ask the owner to paste secrets into git.
4. Fit XGB slot 1 on owner family CSVs (NQ ES YM GC SI PL PA BTCF BTC). Then --require-xgb audit.
5. Push Astra: … + HANDOFF_LOG.md.
