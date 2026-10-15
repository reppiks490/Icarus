# ICARUS broker and proprietary-firm integration contract

**Date:** 2026-10-15
**Owner:** Codex (BKR specification)
**Status:** Provider-neutral contract; the incoming worker's target firms, platforms, and file reservations are not yet available.

## Purpose

Integrate the named broker platforms and proprietary-trading accounts into ICARUS through one explicit, testable order/account contract. Keep market-data providers, execution brokers, and proprietary-firm programs as separate concepts. A data provider does not become an execution venue because it supplies quotes; a prop firm is not an API adapter unless it directly operates the order API.

## Current repository baseline

The checked Icarus main branch has:

- `icarus_bridge.brokers.Broker`, a Python protocol for account, clock, quote, position, open orders, cancel, market/stop/bracket orders, stop replace, close, fill waits, and recent fills;
- `AlpacaBroker`, with an equity-only Alpaca API client and paper/live parameter; repository docs state that Alpaca does not route CME futures and uses QQQ/TQQQ as an equity proxy for NQ;
- `ShadowBroker`, an in-memory unit-test/dry-run adapter;
- `webhook.build_broker`, which selects Shadow for shadow mode and otherwise constructs Alpaca directly;
- bridge execution modes `shadow`, `mirror`, and `bracket`; the engine journals broker orders and compares TradingView alerts to paper fills;
- a separate `icarus_futures.VenueAdapter` protocol, `SimVenue`, fault-injection tests, and a journaled futures order state machine. The venue module says no real broker adapter ships until the owner chooses a futures broker; the LIVE mode separately requires a LIVE venue and a production-governance record.

No other named real broker or proprietary-firm adapter was found in the current Icarus main tree during this audit. The user reports that another AI has been working on additional providers. Its provider/account list, branch, and reserved paths are therefore a prerequisite to choosing concrete adapter implementations, but not to this contract.

## Three independent records

Maintain separate, versioned records for:

1. **Instrument:** canonical symbol/venue, asset class, tick/lot/contract value, calendar/session, and exact broker symbol mapping.
2. **Broker connection:** API/platform, account identity, available market/order capabilities, paper/demo/live environment, session/auth health, limits, and reconciliation status.
3. **Proprietary account policy:** firm/program, evaluation or funded status, maximum contracts, allowed instruments, session/day reset timezone, daily loss rule, trailing/static drawdown semantics, payout/consistency rules, and authoritative source/verified effective date.

One broker connection can serve several firms/accounts; one firm can expose multiple broker platforms. The implementation must model this relationship explicitly instead of copying connector code per firm.

## Capability discovery

Each adapter publishes its tested capabilities per account and instrument class:

- markets and exact symbol mappings;
- order types, time-in-force, extended-hours rules, reduce-only/close behavior, bracket semantics, and whether amend/replace is native or cancel-and-replace;
- fractional or integer quantity constraints, minimum notional, tick/price rounding, short-sale and borrow constraints;
- account/clock/positions/open-orders/fill APIs and event/update transport;
- authentication refresh, rate limits, maintenance windows, sandbox/demo availability, and reconnect behavior;
- idempotent client-order identifiers, partial fill reporting, cancel acknowledgement, and history retention;
- supported execution environments (simulated, paper, evaluation, funded, live) as distinct labels.

An unsupported capability is returned as unsupported. The adapter must not silently coerce a bracket into a market order, a fractional lot into an integer lot, a futures symbol into an ETF proxy, or a requested stop amend into an untracked second order.

## Broker adapter contract

The existing `Broker` protocol is a starting point, not proof that every platform has equivalent behavior. Before adding adapters, agree a versioned superset contract covering:

- typed account, position, order, fill, clock, health, error, and capability records;
- a stable client-order idempotency key distinct from broker order IDs;
- explicit quantity units and signed position semantics;
- durable order lifecycle: `new -> submitted/accepted -> partial -> filled/canceled/rejected/expired/unknown`, with broker timestamps and normalized reason codes;
- reconciliation readback after submit, timeout, restart, reconnect, and ambiguous cancel/replace; unknown outcomes are reconciled before any retry;
- adapter-defined tick/lot validation and native symbol resolution;
- safe error classification (transient, auth, entitlement, invalid order, risk reject, venue closed, unknown) without secrets in logs;
- account-scoped submit/cancel/close methods and no global/default account selection hidden in an adapter.

The engine routes a strategy intent through this sequence:

`Pulse intent -> asset/venue mapping -> account-specific risk policy -> adapter capability/preflight -> idempotent broker request -> broker event/readback -> immutable journal and fill-reality comparison`.

The state readback is the source of truth for broker position and fill, not the strategy's expected state. A fill mismatch, stale quote, lost connection, unknown order status, policy breach, or mapping ambiguity rejects new orders for the affected account until reconciliation completes. Other accounts remain isolated.

## Proprietary-firm policy adapter

A prop-firm integration is a policy profile layered on a verified broker/platform connection unless that firm documents and operates a separate API. Each profile requires:

- exact program/account type and official rule source;
- loss/drawdown calculation (intraday or end-of-day, realized vs unrealized, static vs trailing, high-water mark timing);
- daily reset timezone and holiday behavior;
- contract limits by product, scaling steps, position aggregation, and overnight/news restrictions;
- evaluation/funded transition, fees, payout/consistency rules if relevant;
- effective date and rule version, plus explicit unsupported/unknown fields.

No marketing summary or remembered rule may be converted into a risk gate. A policy profile is `UNVERIFIED` until source text and executable rule tests agree. An unknown rule blocks that account's new strategy orders while leaving read-only monitoring available.

## Risk and runtime boundaries

- Risk checks run per account and per venue before submission; account-level aggregate exposure is also reconciled across symbols.
- Strategy quantities are converted using the exact instrument's units and contract specifications. ETF proxies remain explicitly labelled proxies.
- Daily loss, drawdown, max contracts, order count, and allowed-hours controls are declarative and versioned; a breach records the offending inputs and blocks affected orders.
- Restart/reconnect first reads account, positions, and orders. It does not resubmit an order because an in-memory state was lost.
- Connector health, broker authorization, execution environment, and strategy qualification are separate fields. A successful API handshake does not qualify Pulse; a qualified strategy does not silently switch an account from paper to live.

The adapter suite can be implemented and tested against fakes and official demo/paper environments independently of any live-account arming. Each target platform must have an owner-configured credential source and explicit account/environment mapping before a real integration receipt can say `CONNECTED`.

## Security and data handling

- Credentials remain in the user's local secret store or the platform's approved secret service, never code, fixtures, logs, PR descriptions, or screenshots.
- Config/status endpoints expose only present/missing, account alias, environment, and health; never return tokens, account secrets, or full account numbers.
- No connector may elevate `execution_authorized`, `production_decision_authorized`, or a champion state.
- Provider terms govern retained market data and execution records; licensed raw payloads remain outside the public repository.

## Verification gates

For each target broker/platform:

1. Unit tests cover API request mapping, precision, error classification, partial fills, cancel/replace semantics, idempotency, and credential redaction.
2. Shared adapter contract tests run over the fake adapter and every concrete adapter.
3. Reconciliation tests inject timeout-after-submit, duplicate events, restart, reconnect, stale reads, and out-of-order updates.
4. Official sandbox or demo integration validates actual product/market scope, symbol mappings, supported order types, and account environment. No real trade is required to test a sandbox connection.
5. Risk-profile tests cover every explicit prop-firm rule at just-below/at/just-above thresholds, session reset boundaries, DST transitions, and evaluation-to-funded changes.
6. Readback reports distinguish `CODED`, `MOCK_TESTED`, `SANDBOX_VERIFIED`, `ACCOUNT_CONNECTED`, and `FORWARD_PAPER_OBSERVED` for each platform/account. Never collapse these levels into “fully integrated.”

## Parallel worker handoff required

Before concrete adapters are implemented, the incoming agent should publish:

- the exact target list of brokers, execution platforms, prop firms, program/account types, and supported instrument classes;
- its branch/PR and exact reserved files;
- vendor official API/product documentation and account/region eligibility;
- for every firm, whether the connector is direct or is actually a broker platform account;
- work already completed, tests run, sandbox availability, and known rule/entitlement gaps.

Codex will then take the non-overlapping adapter or policy layers agreed against that list. This document reserves only itself; it does not transfer or claim the existing broker, executor, config, or UI files.
