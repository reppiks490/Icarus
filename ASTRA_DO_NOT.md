# Do not — Grok (xAI) 2026-09-22 week-end

Defaults: SPEC.md. Model design may OVERRIDE.md. Owner-hard never OVERRIDE.

## Owner-hard
- Do not rewrite pulse.py or emulator.py
- execution_authorized stays false
- Do not trade MBT, SOL, ETH, ETHUSD
- Do not ingest BATS/LSE/BCBA into HistoryHub as NQ/ES/YM tape
- Do not scrape TradingView or invent ticks
- Do not commit .env, secrets/, schwab_token.json, App Secret, refresh tokens
- Do not bind 0.0.0.0
- Do not call Schwab POST /orders or previewOrder
- Do not put SCHWAB_APP_SECRET in a goal or HANDOFF_LOG
- Do not treat AAPL/QQQ/$SPX/Schwab equity quotes as NQ fills
- Do not treat history/schwab/*_quote.csv as Renko/range/tick

## Grok-spec (OVERRIDE allowed)
Features, XGB params, extra models, split, audit thresholds, run/ layout.
