# DIVINE PROVIDENCE: THE HEART OF ICARUS

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

`--offline` sets `ICARUS_FEED=file`: live poll reads `history/{SYM}_*m.csv` (mtime-reload as drop ingest rewrites them). Futures remain continuous-only; ICARUS never selects or asks you to maintain a month-coded expiry contract. 1-minute exports are required for live FileFeed; a 20m dump still warms the strategy but is not split into invented minutes.

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
icarus-control validate-cycle control/receipts/20260924-16  # handoff structure only
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


## Control-plane assurance

`icarus-control` is a read-only verifier for ICARUS S1->S5 evidence receipts. It validates the versioned control policy, handoff schema, pinned repository subject, digest links, evidence-lineage structure, and oracle metadata.

It does **not** run the scheduler, change strategy state, authorize execution, or prove a trading claim. See `docs/icarus-control-plane/README.md`.
## ICARUS research-loop integration

The empirical/architecture loop corpus is staged through
[ICARUS_LOOP_INDEX.md](ICARUS_LOOP_INDEX.md).

That index is the canonical entry point for the progressive S3 edge registry and
attempt ledger, direct repository audits, provider capability state, S4 architecture
specifications and plans, the current loop handoff, and the inbox protocol for the
remaining loops.

These artifacts are research/design evidence only unless a later stage explicitly
proves and authorizes runtime integration. Current handoff state preserves
`execution_authorized=false`.


## Continuous learning fabric

ICARUS continuously joins historical replay, matured forecasts, source-quality evidence, and realized trade outcomes into a durable research-only learning ledger. It includes chronological shadow calibration, exact-revision/label scoping, overlap purging, tie-preserving adaptive calibration error, log loss and Brier skill diagnostics, refresh batching, calibrator drift retirement, and source-bound realized-P&L provenance. Runtime closure evidence is classified as `RUNTIME_CLOSURE_CONFIG`; verified historical report linkage is `HISTORICAL_ARTIFACT_CONFIG`; everything else remains `UNSCOPED`. Historical artifacts can never satisfy runtime-closure proof, and historical RTH/ETH identity is preserved only when explicitly declared by intake metadata rather than inferred from timestamps or filenames.

Architecture, data lanes, calibration safeguards, APIs/MCP/UI, and authority boundaries: [docs/icarus/CONTINUOUS_LEARNING.md](docs/icarus/CONTINUOUS_LEARNING.md).

The learning plane does not authorize execution or automatic production promotion.



## APEX Ω world-intelligence layer

APEX Ω is the research/shadow world-dynamics layer that federates ICARUS evidence, participant/force reconstruction, causal/cascade hypotheses, economic world state, unknown-force analysis, model health, and independent conscience checks. It is explicitly non-executing and preserves `execution_authorized=false` and `production_decision_authorized=false`.

Installed architecture, API/MCP/UI surfaces, persistence, truth semantics, and verification contract: [docs/icarus/APEX_OMEGA.md](docs/icarus/APEX_OMEGA.md).

## Assurance archive

Prior ICARUS/AEGIS research, red-team findings, handoffs, Stage-5 verification material, related-build registry, and the implementation-assurance control-plane map are consolidated at [ASSURANCE_INDEX.md](ASSURANCE_INDEX.md).

The archive is evidence/context, not execution authorization or proof of implementation. `execution_authorized=false` remains unchanged.
