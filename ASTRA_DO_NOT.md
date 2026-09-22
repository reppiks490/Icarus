# Do not — Grok (xAI) 2026-09-22

Owner-hard:
- No Pulse rewrite. execution_authorized false.
- No MBT/SOL/ETHUSD. No BATS as HistoryHub tape.
- No scrape TV. No invent ticks. No 0.0.0.0. No secrets in git.
- Schwab: GET quotes / price history only. Never POST /orders or previewOrder.
- Schwab quotes are not NQ fills and not Renko/range labels.
- Do not treat Schwab as the executing broker.

Allowed: run schwab_poll --once when the local token file already exists.
