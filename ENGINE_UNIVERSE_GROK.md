# Engine universe cog — Grok (xAI) — 2026-09-22

Same treatment as the six equity batches, applied to every symbol in `icarus_engine/assets.py` REGISTRY.
Execution tape ≠ sensors ≠ labels. Not NQ-only.

## Registry

| Symbol | Kind | CSV | Plant |
|---|---|---|---|
| NQ ES YM | index futures | yes | CME_MINI / CBOT_MINI |
| GC SI PL PA | metals | yes | COMEX / NYMEX |
| BTCF | CME BTC fut | yes | CME_BTC1! |
| MBT | micro BTC fut | **none** | skip |
| BTC | Coinbase spot | yes | COINBASE / BITSTAMP |
| ETH | Ether | index only | Coinbase dump missing |
| SOL | Solana | **none** | skip |

Do not invent MBT/SOL. Do not alias MBT←BTCF or SOL←ETH.

## Four sockets per traded symbol

1. execution `history/{SYM}_{tf}.csv`
2. sensors (cash, CFD, vol, DXY, TNX, peer futures, candidates)
3. Opus audit: clock-join sensors onto execution
4. Astra labels: Pulse/emulator on **that** symbol only

### Index futures
- NQ sensors: NDX, US100, VXN, TNX, DXY, MAG7 + nq_candidates. QQQ is not NQ.
- ES sensors: SPX, US500, VIX, TNX, DXY, YM, es_candidates. ES ≠ NQ.
- YM sensors: DJI, CAT, ES, DXY. YM tick 1.0 / $5. Not NQ ticks.

### Metals
- GC lead. Sensors SI PL PA + DXY + TNX. `correlations.py` already snapshots DX-Y.NYB.
- SI / PL / PA each keep their own emulator specs. Do not label SI from GC Pulse.
- Thin PA/PL: use preferred_depth.

### Crypto
- BTCF sensors: BTC spot, ETH, DXY. Session ETH. roll=none. Spot fill ≠ CME P&L.
- BTC spot sensors: BTCF, ETH, DXY.
- ETH: treat index_ethusd as sensor until Coinbase ETHUSD exists.
- MBT / SOL: Opus skip, Astra no-train.

## Astra
One model family per execution symbol. Walk-forward on that calendar (cme / metals / cme_crypto / crypto). Renko/range/tick out of the clock trainer.

Grok (xAI). Do not rewrite Pulse. Do not scrape TV.
