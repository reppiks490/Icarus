# Schwab data feed — not the executing broker

Owner uses another broker to trade. Schwab here = Market Data.

Astra and Opus **are authorized** to run:
`python -m icarus_plant.schwab_poll --once`
when `$ICARUS_HOME/secrets/schwab_token.json` is already on the plant.

They are **not** authorized to:
- POST /orders or previewOrder
- Put SCHWAB_APP_SECRET or the token in git or a goal
- Use equity quotes as futures fills

Owner still does the ~7 day browser login on the PC (`--auth-url` then `--exchange-code`). After that the poller and --once calls are data-only.

Symbols: set SCHWAB_SYMBOLS=/NQ,/ES,/YM,/GC on the PC.
