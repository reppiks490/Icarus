# Schwab read-only plant — Grok (xAI) 2026-09-22

Safeguard: **GET quotes only**. `POST /orders` and preview are hard-refused in `icarus_plant/schwab.py`.
Tokens live in `$ICARUS_HOME/secrets/schwab_token.json` (gitignored).
Astra/Opus do **not** receive App Secret or the token file.
You re-login in a browser about every **7 days**.

## You do this on the PC

1. App on developer.schwab.com — enable **Market Data Production**. Trading product optional; poller will not place orders even if it is on.
2. Callback URL exactly `https://127.0.0.1` (or whatever you set in `SCHWAB_REDIRECT`).
3. In the same PowerShell:
```
set SCHWAB_APP_KEY=...
set SCHWAB_APP_SECRET=...
set SCHWAB_REDIRECT=https://127.0.0.1
set SCHWAB_SYMBOLS=/NQ,/ES,/YM,/GC
python -m icarus_plant.schwab_poll --auth-url
```
4. Open that URL, log into **schwab.com**, approve. Copy `code=` from the address bar (seconds count).
5. `python -m icarus_plant.schwab_poll --exchange-code PASTE_CODE`
6. Loop: `python -m icarus_plant.schwab_poll --seconds 15`
7. Files: `history/schwab/execution/NQ_quote.csv` (slash stripped).

Trainers still prefer your Tide/Renko CSVs. This feed is **clock last prints** for gap-fill / live last.

`execution_authorized` stays false.
