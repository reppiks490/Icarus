# Icarus

Paper engine + TradingView-alert bridge for **THE PULSE OF ICARUS**.

Two brains. They do not share a tape.

| | Who sees the market | What it trades |
|---|---|---|
| **A — live signals** | TradingView Pine on `CME_MINI:NQ1!` | Alpaca paper **QQQ** via `icarus-bridge` (percent-mapped, not a futures fill) |
| **B — this Python engine** | Yahoo `NQ=F` **or** a chart export you already own | Internal emulator (CME contract specs, RTH 20m, HA tick-quantize) |

A TradingView CME subscription does **not** stream into Brain B. CME forbids redistributing that feed. The legal free way to warm the engine on the same bars the chart used:

```
TradingView Supercharts → ⋯ → Export chart data
icarus-engine ingest-bars ~/Downloads/NQ1!.csv --symbol NQ --tz America/New_York
icarus-engine doctor
icarus-engine backtest --assets NQ
```

That writes `history/NQ_1m.csv` (preferred) or `history/NQ_20m.csv`. Warm-up uses it instead of delayed Yahoo. Details: [DATA.md](DATA.md). Documented Pine departures: [PARITY.md](PARITY.md).

## Requirements

- Python 3.10+
- Engine: stdlib only (no API keys)
- Bridge extras: `pip install -e '.[bridge]'` (fastapi, uvicorn, httpx, plus `alpaca-py` if you talk to Alpaca)
- Tests: `pip install -e '.[dev]'` then `python -m pytest tests_engine -q`

## Engine

```
icarus-engine assets
icarus-engine ingest-bars FILE --symbol NQ
icarus-engine doctor
icarus-engine backtest --assets NQ --tf 20
icarus-engine parity --asset NQ --tv-csv "List of Trades.csv"
icarus-engine import-tv strategy-report.xlsx --name NQ-20m-mine
icarus-engine run --assets NQ --tf 20
```

Default chart session is **RTH** (09:30–16:15 ET, 20m at `:10/:30/:50`, last bar a 5-minute stub). Yahoo 1-minute history is ~30 days and ~10 minutes delayed. Empty minutes are not invented.

## Bridge (TV alerts → Alpaca paper)

```
cp icarus_bridge/.env.example .env   # set WEBHOOK_SECRET, ADMIN_TOKEN, Alpaca paper keys
icarus-bridge doctor
icarus-bridge serve --tunnel ngrok
```

Paste `pine/ALERT_TEMPLATE.json` into the strategy alert. `NQ1!` → `QQQ` is the default map. That is an equity proxy, not CME.

## What this repo will not do for free

- Scrape TradingView or invent ticks / queue / spread
- Stream a CME display license into Python (non-display / Databento is the paid path)
- Fill NQ at a futures broker from Alpaca
