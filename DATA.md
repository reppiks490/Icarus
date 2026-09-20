# Data: what is free, what is not

<!-- Grok (xAI) — 2026-09-20. Whole file. Two-brain data map. A TV CME pack does not feed Brain B. -->

Icarus has **two brains**. They do not share a tape.

| Brain | Who sees the market | Free path | Paid path |
|---|---|---|---|
| **A — live signals** | TradingView Pine (`CME_MINI:NQ1!`) | Delayed TV (10 min) | [TV CME pack](https://www.tradingview.com/cme/) ~$10/mo **display** |
| **B — this Python engine** | `feeds/` (Yahoo `NQ=F` / Coinbase) | Yahoo (delayed ~10 min, 1m history ~30 days) **or a chart export you already own** | Databento Standard ~$199/mo |

A TradingView CME subscription **does not** stream into this process. CME forbids redistributing that feed. The legal free way to get the *same bars the chart used* is:

```
TradingView Supercharts → ⋯ → Export chart data
icarus-engine ingest-bars ~/Downloads/NQ1!.csv --symbol NQ --tz America/New_York
```

That writes `history/NQ_1m.csv` (or `NQ_20m.csv`). On the next `run` / `backtest` / `parity`, warm-up prefers that file over Yahoo.

## File names

| File | Meaning |
|---|---|
| `history/NQ_1m.csv` | Best. Engine aggregates 20m / HTF / LTF itself |
| `history/NQ_20m.csv` | Chart-TF export. HTF chains are built from 20m bars (worse than 1m) |
| Yahoo fallback | Used when neither file exists, and for the 1-minute tail after the last exported bar |

Canonical columns: `ts,open,high,low,close,volume` with `ts` = UTC epoch **open**. `ingest-bars` converts TradingView's formats.

## What this does **not** fix

- Live delay after the export ends (Yahoo tail is still ~10 min late)
- Tick path / queue / spread (do not invent ticks)
- `NQ=F` vs `NQ1!` roll window, unless the export **is** `NQ1!`
- Alpaca QQQ fills (bridge, not engine)

## Next paid step (not this PR)

Databento `GLBX.MDP3` Standard (~$199/mo, personal, live + history) implements the same `candles/recent_ex/ticker` interface as Yahoo. Plug it in; do not scrape TradingView.
