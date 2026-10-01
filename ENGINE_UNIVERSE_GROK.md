# Engine universe cog — Grok (xAI) — 2026-09-22

Execution tape ≠ sensors ≠ labels. Not NQ-only.

## Owner ignore — do not trade, do not start, do not train

`MBT`, `SOL`, `ETH` / `ETHUSD` **do not show up in the engine** and are **not to be traded**.
`icarus_engine.ignore_trade.DO_NOT_TRADE`. Do not alias them off BTC/BTCF. Do not drop CSVs for them.

## Registry that is in play

| Symbol | Kind | Status |
|---|---|---|
| NQ ES YM | index futures | trade |
| GC SI PL PA | metals | trade |
| BTCF | CME BTC fut | trade |
| BTC | Coinbase BTC spot | trade |
| MBT | micro BTC | **ignored** |
| SOL | Solana | **ignored** |
| ETH / ETHUSD | Coinbase ETH | **ignored** (index_ethusd may exist as a file; it is not an ETH fill) |

## Four sockets per *traded* symbol

1. execution `history/{SYM}_{tf}.csv`
2. sensors (cash, CFD, vol, DXY, TNX, peers, candidates)
3. Opus audit: clock-join sensors onto execution
4. Astra labels: Pulse/emulator on **that** symbol only

Index / metals / BTCF+BTC as before. QQQ is not NQ. ES ≠ NQ. YM ticks are not NQ ticks.
Do not label SI from GC Pulse.

Grok (xAI). Do not rewrite Pulse. Do not scrape TV.
