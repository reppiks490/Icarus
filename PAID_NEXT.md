# Save spot — paid path (do this when you have the money)

<!-- Grok (xAI) — 2026-09-20. Whole file. Not a live runbook for tonight. Brain B is already up on Yahoo. -->

This is the list you asked to freeze. Call it later. It is **not** a promise that Alpaca, TradersPost, or PickMyTrade stream CME into the Python engine. They do not.

Tonight’s plant (`http://127.0.0.1:8791/`) is **Brain B**: Yahoo `NQ=F`, local paper emulator, RTH 20m. Leave that PowerShell open.

We are **not scalpers**. Session is RTH (09:30–16:15 ET). Sunday Globex is not a trade.

---

## 0. What is already done (free)

- Repo: `C:\Users\tripl\Icarus` on `main`
- Plant runs: `py -3 -m icarus_plant start --assets NQ` (Yahoo, **no** `--offline`)
- Dashboard on the **PC**: `http://127.0.0.1:8791/` token `icarus`
- Local paper journal: `icarus_engine.db` — Icarus’s book, not a broker statement
- Export that book: `py -3 -m icarus_engine.cli paper-export` → `paper-trades.csv`
- CSV export is **Plus**, not Essential (that was wrong earlier)

---

## 1. Alpaca — Brain A, equity proxy (QQQ), not NQ

Icarus-bridge turns **TradingView Pine alerts** into **Alpaca paper QQQ**. Percent-mapped. **Not a futures fill.** The 8791 dashboard does not see these orders.

### Cost (order of magnitude — check live)

- Alpaca paper: free
- Alpaca live: free API, you fund the account (do **not** do live until paper is boring)
- TradingView: paid plan for **webhook** alerts (Essential or above as of 2026 docs)
- ngrok: free tier is enough to start
- `alpaca-py` + `pip install -e ".[bridge]"`: free

### Steps (PC, **second** PowerShell — keep Brain B running)

1. [Alpaca paper](https://app.alpaca.markets/) → API keys. Paper only.
2. ```
   cd C:\Users\tripl\Icarus
   py -3 -m pip install -e ".[bridge]"
   py -3 -m pip install alpaca-py
   copy icarus_bridge\.env.example .env
   notepad .env
   ```
3. Fill:
   ```
   ALPACA_API_KEY=...
   ALPACA_SECRET_KEY=...
   ALPACA_PAPER=true
   HOST=127.0.0.1
   PORT=8787
   WEBHOOK_SECRET=<long random>
   ADMIN_TOKEN=<other long random>
   EXECUTION_MODE=mirror
   ```
   Never `ALPACA_PAPER=false` until you mean it. Never leave `replace-me`.
4. `py -3 -m icarus_bridge doctor`
5. Install [ngrok](https://ngrok.com/download). Then:
   `py -3 -m icarus_bridge serve --tunnel ngrok`
6. TradingView strategy alert on THE PULSE OF ICARUS:
   - Webhook URL = the printed `https://…/webhook`
   - Body = `pine/ALERT_TEMPLATE.json` with `YOUR_WEBHOOK_SECRET` replaced
7. Optional dry run: `py -3 -m icarus_bridge test-alert --side long`

| URL | Brain |
|---|---|
| `http://127.0.0.1:8791/` | B — Yahoo NQ engine |
| `http://127.0.0.1:8787/` | A — Alpaca QQQ from Pine |

Traceable **on Alpaca paper statements**. Still not CME.

---

## 2. TradersPost and/or PickMyTrade — actual futures (NQ / MNQ)

These are **cloud webhook routers**. They are **not** Icarus plugins. They do **not** feed Brain B. Pine stays the brain. The router places the order at a **futures** broker.

```
TradingView alert (PULSE)
    → webhook (HTTPS)
        → TradersPost  OR  PickMyTrade
            → Tradovate / Rithmic / IB / TradeStation / prop (ProjectX, etc.)
                → CME NQ or MNQ
```

**Do not** point the same alert at Icarus-bridge **and** TradersPost. One destination.

### Which one

| | TradersPost | PickMyTrade |
|---|---|---|
| Job | Webhook → many brokers (stocks, futures, crypto) | Strong on **futures** + prop |
| Futures brokers | Tradovate, TradeStation, others | Tradovate, Rithmic, IB, TradeStation, ProjectX/TopstepX |
| Icarus code change | None. Paste **their** webhook + JSON, not `ALERT_TEMPLATE.json` | Same |
| `NQ1!` | They map continuous → front month on **their** roll calendar (can differ from TV). Prefer explicit contract (`NQZ2026`) if they say so | They generate the JSON; symbol is usually `NQ1!` / `MNQ1!` as you configure |
| PC must stay on | No (cloud) | No (cloud) |

Check current prices on their sites. Class of cost: roughly tens of USD per month **plus** a futures account (margin, exchange data fees). Not “free with Essential.”

### TradersPost (when paid)

1. Account at [traderspost.io](https://traderspost.io/). Paper first if they offer it.
2. **Connection:** Tradovate (or TradeStation) **paper/sim**, not live.
3. Enable **futures** in account settings.
4. Create a **Strategy** (asset class = futures, allowed tickers NQ/MNQ).
5. Create a **Subscription** (size in **contracts**, not QQQ shares).
6. Copy the strategy webhook URL (`https://webhooks.traderspost.io/trading/webhook/…`).
7. TradingView alert → that URL. JSON from [their signal reference](https://docs.traderspost.io/docs/core-concepts/webhooks), not Icarus’s template. Example shape: `ticker` + `action`. For futures they warn: `NQ1!` roll may not match TV — use the contract they document.
8. Confirm a **sim** fill in Tradovate **before** any live account or prop.

### PickMyTrade (when paid)

1. Account at [pickmytrade.trade](https://pickmytrade.trade/) / [pickmytrade.io](https://pickmytrade.io/). Trial if offered.
2. Connect Tradovate (simplest retail) or Rithmic/ProjectX if that is the prop.
3. Inside PickMyTrade: generate **alert message + webhook URL** (they write the JSON).
4. TradingView: paste **their** message, **their** webhook. Do not use `pine/ALERT_TEMPLATE.json`.
5. Size in **micros first (MNQ)** until the mapping is proven. We are not scalpers; leave their HFT/abuse settings off.
6. Sim/demo fill, then funded.

### What Icarus still is, after that

Brain B remains the **research / parity / paper** engine. Futures fills live in the **broker**. To compare: export the broker’s fill list and, when you have a Plus CSV, `icarus-engine parity`. Do not pretend the Yahoo dashboard is the futures blotter.

---

## 3. Collect CSV (when TradingView **Plus** or higher)

Essential **cannot** export Supercharts. Plus can.

1. Upgrade TV to Plus (or use a trial **only** if you accept their terms).
2. Supercharts: `CME_MINI:NQ1!`, **1 minute**, scroll **left**.
3. ⋯ → **Download chart data**. Typical name: `CME_MINI_NQ1!, 1.csv`.
4. Copy into `C:\Users\tripl\Icarus\history\drop` **or** leave in Downloads (plant pulls it).
5. Repeat over days. Dumps **merge** by timestamp into `history/NQ_1m.csv` (Plus’s bar window accumulates).
6. Then Brain B can run `--offline` on **your** NQ1! tape instead of delayed Yahoo `NQ=F`.
7. Still not a live CME stream. Last bar = last export. For live non-display tape later: Databento `GLBX.MDP3` (~$199/mo class) implementing the same `candles/recent_ex/ticker` interface — not scrape.

Do **not** use random GitHub “NQ_1m.csv” samples as the live book. Third-party, often tick-volume, stale, not `NQ1!`.

---

## 4. Continue work (queue — do not start until funded or you ask)

1. Alpaca paper (section 1) → one `test-alert` → then real Pine alerts on **paper QQQ**.
2. Plus CSV (section 3) → `history/NQ_1m.csv` → optional `--offline` plant.
3. TradersPost **or** PickMyTrade + Tradovate **sim** (section 2) → MNQ/NQ **contracts**.
4. Databento (or other **non-display** CME) wired as a feed class next to Yahoo — only with keys you own.
5. Futures **live** last. Never skip sim.

Icarus will **not**: scrape TradingView, invent ticks/queue/spread, treat Alpaca QQQ as an NQ fill, or bind the engine off loopback.

---

## Machine learning (honest)

**Can I touch it?** Yes. There is already adaptation code. It is **not** a neural net.

| Piece | What it actually is |
|---|---|
| `icarus_engine/research.py` | Bounded grid search. Train / validation / **locked holdout**. Candidates, never live orders |
| `icarus_engine/adaptation.py` | Opt-in paper scheduler (`enabled: false`). Walk-forward on existing inputs. `execution_authorized: False` |
| `icarus_engine/advisory.py` | Regime notes. Association ≠ prediction |
| PyTorch / sklearn / LSTM | **None in this repo** |

**Should we bolt on “true ML” for robustness?** Not as a price-predicting model. This system is a **20-minute RTH Heikin-Ashi pulse**, not a scalper. Fitting a network to 1-minute Yahoo noise would be the slop you told me not to ship.

Robustness that belongs here, if we extend later:

- Keep holdout **untouched**
- Regime / session / FOMC / holiday **gates** (already partly there)
- Walk-forward on **existing** Pulse inputs, not new predicted prices
- Position **size** and **skip** decisions, not entry-price oracles
- Never train on ticks we invented; never leak holdout; never auto-arm live from a trial

Astra owns `strategy/pulse.py`. I will not replace it with an LSTM.

---

Grok (xAI) — 2026-09-20.
