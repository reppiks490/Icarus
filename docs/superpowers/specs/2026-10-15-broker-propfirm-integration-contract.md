# ICARUS broker and proprietary-firm integration contract

**Date:** 2026-10-15
**Owner:** Codex (BKR specification)
**Status:** Provider-neutral contract. This specification is not proof that every broker, platform, or prop-firm program is integrated.

## Purpose

Integrate named broker platforms and proprietary-trading accounts into ICARUS through explicit, testable order/account contracts. Keep market-data providers, execution brokers, and proprietary-firm programs separate. A data provider does not become an execution venue because it supplies quotes; a prop firm is not an API adapter unless it directly operates the order API.

## Current repository baseline (verified after PR #372)

The current `main` branch has:

- `icarus_bridge.brokers.Broker`, an equity/crypto bridge protocol; `AlpacaBroker` is an equity adapter, and `ShadowBroker` is in-memory simulation. Bridge mode selection and its account model are separate from the futures venue.
- `icarus_futures.VenueAdapter` and `SimVenue`, a deterministic futures simulation venue with fault-injection support.
- `icarus_futures.ibkr_paper.IbkrPaperVenue` and `IbkrTwsPaperGateway` from merged PR #372. The adapter accepts explicit reviewed mappings for exact dated CME futures, requires an explicit managed `DU...` paper account, restricts the optional TWS/IB Gateway transport to loopback and standard paper ports, and has no live route. It uses IBKR `orderRef` to identify/reconcile client orders and returns an ambiguous timeout rather than retrying an uncertain submit.
- Unit and contract tests for mapping validation, precision, account isolation, order references, callback/readback normalization, and failure handling.

PR #372 reports 16 focused tests, build, diff, and exact-head Linux/Windows checks passed. A local TWS gateway/paper account was unavailable, so no `SANDBOX_VERIFIED`, `ACCOUNT_CONNECTED`, or `FORWARD_PAPER_OBSERVED` claim is made.

No verified concrete Tradovate, TradeLocker, or proprietary-firm program adapter is established by this baseline. Confirm owner-selected providers, supported products, account type, official documentation, and reservations before adding one. Do not infer a firm policy from its broker platform.

## Three independent records

Maintain separate, versioned records for:

1. **Instrument:** canonical symbol/venue, asset class, tick/lot/contract value, calendar/session, and exact broker symbol mapping.
2. **Broker connection:** API/platform, account identity, available market/order capabilities, paper/demo/live environment, session/auth health, limits, and reconciliation status.
3. **Proprietary account policy:** firm/program, evaluation or funded status, maximum contracts, allowed instruments, session/day reset timezone, daily loss rule, trailing/static drawdown semantics, payout/consistency rules, and authoritative source/verified effective date.

One broker connection can serve several firms/accounts; one firm can expose multiple broker platforms. Model that relationship explicitly instead of copying connector code per firm.

## Capability discovery

Each adapter publishes tested capabilities per account and instrument class:

- markets and exact symbol mappings;
- order types, time-in-force, extended-hours rules, reduce-only/close behavior, bracket semantics, and whether amend/replace is native or cancel-and-replace;
- fractional or integer quantity constraints, minimum notional, tick/price rounding, short-sale and borrow constraints;
- account/clock/positions/open-orders/fill APIs and event/update transport;
- authentication refresh, rate limits, maintenance windows, sandbox/demo availability, and reconnect behavior;
- idempotent client-order identifiers, partial fill reporting, cancel acknowledgement, and history retention;
- supported execution environments (simulated, paper, evaluation, funded, live) as distinct labels.

Unsupported capabilities must be returned as unsupported. Never silently coerce a bracket into a market order, a fractional lot into an integer lot, a futures symbol into an ETF proxy, or a requested stop amend into an untracked second order.

## Broker adapter contract

The existing bridge `Broker` and futures `VenueAdapter` protocols are separate interfaces, not interchangeable adapters. Before adding a new broker, agree a versioned superset contract covering:

- typed account, position, order, fill, clock, health, error, and capability records;
- a stable client-order idempotency key distinct from broker order IDs;
- explicit quantity units and signed position semantics;
- durable order lifecycle: `new -> submitted/accepted -> partial -> filled/canceled/rejected/expired/unknown`, with broker timestamps and normalized reason codes;
- reconciliation readback after submit, timeout, restart, reconnect, and ambiguous cancel/replace; unknown outcomes must be reconciled before any retry;
- adapter-defined tick/lot validation and native symbol resolution;
- safe error classification (transient, auth, entitlement, invalid order, risk reject, venue closed, unknown) without secrets in logs;
- account-scoped submit/cancel/close methods and no hidden global/default account selection.

The shipped IBKR futures paper adapter is a concrete implementation of the futures `VenueAdapter` for its reviewed mappings, not proof that the general broker contract or every product is covered. Its optional loopback transport and fake-gateway tests establish `CODED` and `MOCK_TESTED` only; the owner-reported absence of a local gateway leaves account and forward-paper verification open.

The engine should route strategy intent through:

`Pulse intent -> asset/venue mapping -> account-specific risk policy -> adapter capability/preflight -> idempotent broker request -> broker event/readback -> immutable journal and fill-reality comparison`.

Broker readback remains the source of truth for position and fill, not expected strategy state. A fill mismatch, stale quote, lost connection, unknown order status, policy breach, or mapping ambiguity rejects new orders for the affected account until reconciliation completes. Other accounts remain isolated.

## Proprietary-firm policy adapter

A prop-firm integration is a policy profile layered on a verified broker/platform connection unless that firm documents and operates a separate API. Each profile requires:

- exact program/account type and official rule source;
- loss/drawdown calculation (intraday or end-of-day, realized vs unrealized, static vs trailing, high-water mark timing);
- daily reset timezone and holiday behavior;
- contract limits by product, scaling steps, position aggregation, and overnight/news restrictions;
- evaluation/funded transition, fees, payout/consistency rules if relevant;
- effective date and rule version, plus explicit unsupported/unknown fields.

No marketing summary or remembered rule may become a risk gate. A policy profile is `UNVERIFIED` until source text and executable rule tests agree. An unknown rule blocks that account's new strategy orders while leaving read-only monitoring available.

## Risk and runtime boundaries

- Risk checks run per account and per venue before submission; account-level aggregate exposure is also reconciled across symbols.
- Strategy quantities are converted using exact instrument units and contract specifications. ETF proxies remain explicitly labelled proxies.
- Daily loss, drawdown, max contracts, order count, and allowed-hours controls are declarative and versioned; a breach records the offending inputs and blocks affected orders.
- Restart/reconnect first reads account, positions, and orders. It does not resubmit an order because in-memory state was lost.
- Connector health, broker authorization, execution environment, and strategy qualification are separate fields. A successful API handshake does not qualify Pulse; a qualified strategy does not silently switch an account from paper to live.

New adapters can be implemented against fakes and official demo/paper environments without live arming. Each target platform needs an owner-configured credential source and explicit account/environment mapping before any real integration receipt says `CONNECTED`.

## Security and data handling

- Credentials remain in the user's local secret store or platform's approved secret service, never code, fixtures, logs, PR descriptions, or screenshots.
- Config/status endpoints expose only present/missing, account alias, environment, and health; never tokens, account secrets, or full account numbers.
- No connector may elevate `execution_authorized`, `production_decision_authorized`, or champion state.
- Provider terms govern retained market data and execution records; licensed raw payloads remain outside the public repository.

## Verification gates

For each target broker/platform:

1. Unit tests cover API request mapping, precision, error classification, partial fills, cancel/replace semantics, idempotency, and credential redaction.
2. Shared adapter contract tests run over the fake adapter and every concrete adapter.
3. Reconciliation tests inject timeout-after-submit, duplicate events, restart, reconnect, stale reads, and out-of-order updates.
4. Official sandbox/demo integration validates actual product/market scope, symbol mappings, supported order types, and account environment. No real trade is required.
5. Risk-profile tests cover every explicit prop-firm rule at just-below/at/just-above thresholds, session reset boundaries, DST transitions, and evaluation-to-funded changes.
6. Readback reports distinguish `CODED`, `MOCK_TESTED`, `SANDBOX_VERIFIED`, `ACCOUNT_CONNECTED`, and `FORWARD_PAPER_OBSERVED`. Never collapse them into “fully integrated.”

## Coordination and handoff

Before a concrete adapter is implemented, publish:

- target brokers, execution platforms, prop firms, program/account types, and supported instrument classes;
- active branch/PR and exact reserved files;
- official vendor product/API documentation and account/region eligibility;
- whether a connector is direct or a broker-platform connection used by a firm;
- completed work, tests, sandbox availability, and known rule/entitlement gaps.

This specification reserves only itself. It does not reserve or authorize changes to an active broker adapter, account mapping, execution router, risk policy, credentials, or UI.
