# Futures-native execution core and portfolio risk governor (`icarus_futures/`)

CL (Claude, Anthropic) — 2026-10-04. Status: **BUILT, unit-VERIFIED (22 tests), not broker-connected, not PAPER-TESTED against a real venue, not PRODUCTION-AUTHORIZED.**

## Why it exists

`icarus_bridge` executes through Alpaca (ETF proxy shares) or an in-memory shadow broker. Neither is CME futures execution, and proxy fills must never be shown as futures fills. This package is the broker-agnostic futures layer the bridge can migrate onto once the owner picks a futures broker (none is chosen; none is faked here).

## Pieces

| Module | What it guarantees |
|---|---|
| `contracts.py` | Contract economics for NQ/MNQ, ES/MES, YM/MYM, RTY/M2K, GC/MGC, SI/SIL (tick, point value, notional, full-size equivalent, cluster). Continuous identities (`NQ1!`, `CME_MINI:MNQ1!`) resolve to dated contracts with CME's published roll rule (equity: the Monday before the 3rd Friday; expiry moves to the prior business day on an exchange holiday, e.g. June 2026; metals: first notice − 2 business days). Expiring codes are rejected as user-facing symbols. |
| `orders.py` | Deterministic client intent ids (hash of the intent) → duplicate requests never reach a venue twice. States PENDING_SUBMIT → SUBMITTED → WORKING → PARTIALLY_FILLED → FILLED, PENDING_CANCEL/REPLACE, CANCELLED, REJECTED (classified: margin, price band, closed, invalid, position limit, rate limit, busy), EXPIRED, AMBIGUOUS. Fill during cancel wins; late cancel acks are ignored; duplicate fills are ignored; overfills go AMBIGUOUS; OCO siblings cancel. |
| `journal.py` | Append-only, fsynced, SHA-256 hash-chained journal. A torn last line (crash mid-write) is tolerated; any other corruption fails closed. |
| `risk.py` | Portfolio governor evaluated before any venue call: per-asset full-size-equivalent limits (MNQ = 0.1 NQ), cluster notional (NQ/ES/YM/RTY together; metals together), gross notional, daily / rolling / drawdown loss limits, global pause, broker mismatch, ambiguous orders, stale data, volatility shock, event blackout, session window. Every veto carries reason codes. Reducing exposure is always allowed; reduce-only intents can never add or flip. |
| `venue.py` | `VenueAdapter` protocol plus a deterministic `SimVenue` with fault injection (lost ack, duplicate fill, reject, partial fill, disconnect). |
| `engine.py` | Duplicate suppression → governor → journal → venue. Timeouts and disconnects make orders AMBIGUOUS (never auto-retried). Restart rebuilds from the journal without resubmitting; live orders at the crash block new risk until `reconcile()` compares the book with the venue's open orders and positions. `flatten_all()` cancels working orders and exits with reduce-only market intents. Modes SIM / PAPER / SHADOW / LIVE are explicit; LIVE needs a LIVE venue and `config/production_governance.json` with `production_authorized: true` (absent → construction raises). `snapshot()` is the UI contract (`icarus_futures.snapshot/1`: health GREEN / DEGRADED / BLOCKED, ui_state PAPER / SHADOW / LIVE, orders by state, positions, alarms, vetoes). |

## What is still owed

- **BLOCKED_EXTERNAL:** the futures broker/API choice (e.g. a CME-capable broker API); its adapter must implement `VenueAdapter` and pass the same chaos tests against its paper environment.
- Extend `EXPIRY_HOLIDAYS` from CME's holiday calendar (only Juneteenth 2026 is encoded and verified).
- Wiring `icarus_bridge` and the ICARUS UI to `snapshot()` (UI lane), and feeding live marks / data age / volatility ratios from the Databento path into `PortfolioState`.
