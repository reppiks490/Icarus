# CL (Claude, Anthropic) — 2026-10-04 — icarus_futures: futures-native execution core and portfolio risk governor
"""Broker-agnostic CME futures execution for ICARUS.

* contracts  — contract specs, continuous identities (NQ1!, MNQ1!, ...) and roll resolution
* orders     — deterministic intents, the order state machine, fills, races, ambiguity
* journal    — crash-safe append-only hash-chained event journal (restart without replay)
* risk       — portfolio risk governor that vetoes intents BEFORE any venue sees them
* venue      — the venue adapter protocol and a deterministic simulated venue (paper/sim/tests)
* engine     — the coordinator: mode identity, risk-before-venue, reconciliation, pause/flatten

No real broker adapter ships here: the owner has not chosen a futures broker, and
fabricating one is forbidden. Live mode refuses to submit unless a separate production
governance record authorizes it (it does not exist), so execution_authorized stays False.
"""
EXECUTION_AUTHORIZED = False
PRODUCTION_DECISION_AUTHORIZED = False
LANE = "CL"
