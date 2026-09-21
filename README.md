# Icarus

<!-- Grok (xAI) — 2026-09-20. Whole file. This repo had no README. Engine/strategy remain Astra's. -->

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

## Plant (local infrastructure)

Grok (xAI) — 2026-09-20. A data directory + process supervisor so Brain B stays up. **Not Docker, not a CME feed.** The engine binds `127.0.0.1` (DNS-rebinding). Health is `GET /healthz` on loopback.

**Windows (do this):** clone the repo, double-click [`start-plant.bat`](start-plant.bat). Full dummy list: [SETUP.md](SETUP.md).

```
icarus-plant setup --open                 # numbered steps + open history/drop/
icarus-plant init                         # history/drop, run/, logs/ under $ICARUS_HOME or cwd
# drop Supercharts CSVs into history/drop/  (each dump MERGES into history/NQ_1m.csv)
icarus-plant start --assets NQ --offline  # FileFeed only; Yahoo is not contacted
icarus-plant status
icarus-plant stop
```

`--offline` sets `ICARUS_FEED=file`: live poll reads `history/{SYM}_*m.csv` (mtime-reload as drop ingest rewrites them). Roll is forced `none` so FileFeed volumes cannot fake a CME 1! roll. 1-minute exports are required for live FileFeed; a 20m dump still warms the strategy but is not split into invented minutes.

Optional systemd unit: [deploy/icarus-plant.service](deploy/icarus-plant.service). Edit paths; do not expose port 8791.

## Requirements

- Python 3.10+
- Engine / plant: stdlib only (no API keys)
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
icarus-engine run --assets NQ --feed file   # HistoryHub; same as plant --offline
```

Default chart session is **RTH** (09:30–16:15 ET, 20m at `:10/:30/:50`, last bar a 5-minute stub). Yahoo 1-minute history is ~30 days and ~10 minutes delayed. Empty minutes are not invented. `$ICARUS_HOME` is the data dir (history, journal, presets) when the plant sets it.

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

Paid next (Alpaca paper, TradersPost / PickMyTrade futures, Plus CSV, ML boundary): [PAID_NEXT.md](PAID_NEXT.md). Dummy command list: [COMMANDS.md](COMMANDS.md).

Hands: **Astra** (engine, Pine port, emulator, bridge, tests) · **Grok (xAI)** (free-gap ingest/doctor/CI/hygiene + local plant — see [GROK.md](GROK.md)).
