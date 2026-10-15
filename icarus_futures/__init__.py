# CL (Claude, Anthropic) — 2026-10-04 — icarus_futures: futures-native execution core and portfolio risk governor
"""Broker-agnostic CME futures execution for ICARUS.

* contracts  — contract specs, continuous identities (NQ1!, MNQ1!, ...) and roll resolution
* orders     — deterministic intents, the order state machine, fills, races, ambiguity
* journal    — crash-safe append-only hash-chained event journal (restart without replay)
* risk       — portfolio risk governor that vetoes intents BEFORE any venue sees them
* venue      — the venue adapter protocol and deterministic simulated venue
* ibkr_paper — fixed-account IBKR PAPER adapter and optional loopback TWS transport
* engine     — the coordinator: mode identity, risk-before-venue, reconciliation, pause/flatten

The IBKR TWS transport requires the optional ``ibkr`` extra and an explicitly connected
local PAPER session. It accepts only loopback paper ports and ``DU...`` accounts; no
live route ships here. Live mode refuses to submit unless a separate production
governance record authorizes it (none ships here), so execution_authorized stays False.
"""
EXECUTION_AUTHORIZED = False
PRODUCTION_DECISION_AUTHORIZED = False
LANE = "CL"
