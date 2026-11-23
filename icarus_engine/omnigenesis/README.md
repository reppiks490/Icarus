# ICARUS OMNIGENESIS ∞ — Research-only Mathematical Intelligence

This package is an implemented, intentionally constrained scientific microkernel.
It is not an autonomous profitable trading system, AI agent colony, production
execution controller, or verified financial forecaster.

## Delivered Python capabilities

- Exact next-prime and first-observed-event arithmetic.
- Strict as-of timestamps, immutable record identity, source Git revision.
- Single-feature finite hypothesis discovery with purged chronological splits.
- SQLite-ledgered study outcomes with immutable content-derived identifiers.
- Typed finite-state machine compiler, deterministic replay, prefix causality.
- Symbolic detection of overlapping numeric transition guards with counterexamples.
- Seeded price/time-priority synthetic order-book matching with self-match guard.
- Exact-tick historical OHLC upper/lower first-passage, explicit ambiguous and
  censored outcomes, and incomplete-horizon rejection.
- Bounded, dependency-ordered, non-executing research capability proposals.
- Unified content-addressed summaries of model studies, proofs, event-time
  labels, synthetic exchange experiments and capability plans.
- Native ICARUS read-only API, desktop cinematic research tab and secure mobile
  gateway read surface. Standalone HTML visualization for offline viewing.
- Focused tests in tests_engine/test_omnigenesis*.py and dedicated Actions CI.

## Run from canonical repository root

    python -m pytest tests_engine/test_omnigenesis*.py -q
    python -m icarus_engine.omnigenesis prime 100
    python -m icarus_engine.omnigenesis run dataset.json --root .
    python -m icarus_engine.omnigenesis status --root .
    python -m icarus_engine.omnigenesis synthetic-book --seed 17 --steps 300 --root .
    python -m icarus_engine.omnigenesis formal machine.json --root .
    python -m icarus_engine.omnigenesis automaton machine.json observations.json
    python -m icarus_engine.omnigenesis first-passage tape.json --up-ticks 8 --down-ticks 6 --horizon 10 --root .
    python -m icarus_engine.omnigenesis propose capability.json
    python -m icarus_engine.omnigenesis plan proposals.json --seconds 1000 --dollars 0 --root .
    python -m icarus_engine.omnigenesis dashboard --root . --output research/omnigenesis.html

No CLI command automatically trains, deploys, schedules, purchases data or
modifies paper/live trading. Offline evaluation uses explicit input files.

## Historical research dataset contract

JSON must contain exactly these top-level keys:

    {
      "dataset_id": "NQ-verified-run-id",
      "source_commit": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "records": [...]
    }

Each of the 30–50000 records must contain exactly:

    {
      "record_id": "event-0001",
      "asset": "NQ",
      "decision_at": "2026-01-01T14:00:00Z",
      "observed_at": "2026-01-01T13:59:59Z",
      "received_at": "2026-01-01T14:00:00Z",
      "label_resolved_at": "2026-01-01T14:05:00Z",
      "feature": 0.25,
      "outcome": true,
      "source_record_id": "verified-source-record-0001"
    }

This is a ONE-ASSET, ONE-FEATURE experimental grammar. Outcome is a historically
resolved boolean; unlabeled, ambiguous and censored observations MUST NOT be
arbitrarily converted into false. Observational and label clocks must be
verified upstream. This version does NOT prove data-provider completeness or
correctness just because it accepts a syntactically valid source identifier.

Output EXPLO​RATORY (without the optional invisible separator) is only an
exploratory held-out improvement and never qualification. Data snooping,
transaction costs, multiple-testing penalties, OOD, and cross-market
validation remain external DAEDALUS/ASCENDANCY obligations.

## First-passage tape JSON

    {
      "asset": "NQ",
      "source_commit": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "bars": [
        {
          "record_id": "bar_001",
          "observed_at": "2026-01-01T14:00:00Z",
          "received_at": "2026-01-01T14:00:01Z",
          "open_ticks": 25000,
          "high_ticks": 25004,
          "low_ticks": 24996,
          "close_ticks": 25002
        }
      ]
    }

The actual tape requires at least five bars. All prices must be positive
integer tick indices. Outcomes are UPPER, LOWER, AMBIGUOUS_BOTH or CENSORED.
An incomplete future window is PENDING (excluded). These are retrospective
labels, not forecasted trades, not actual fills and not a synthetic oracle.

## Typed machine JSON

    {
      "name": "sweep_reclaim",
      "states": ["WAIT", "SWEEP", "DONE"],
      "initial": "WAIT",
      "terminal_states": ["DONE"],
      "transitions": [
        {"from": "WAIT", "to": "SWEEP", "feature": "sweep",
         "op": "gte", "threshold": 1.0},
        {"from": "SWEEP", "to": "DONE", "feature": "reclaim",
         "op": "gte", "threshold": 0.7}
      ]
    }

Replay inputs are bounded arrays of as-of observations, each with exactly
record_id, observed_at, received_at, decision_at and a finite numeric
features object. Simultaneously satisfiable guards fail compilation. A
formal certificate proves only structural properties of this typed program,
not that real markets will ever enter its terminal state.

## Research integration and UI

An authenticated GET /api/omnigenesis returns a read-only, bounded derived
snapshot. The existing desktop dashboard has an OMNIGENESIS tab with a
cinematic geometry scene and data-backed study/artifact nodes. The session-
secured mobile gateway forwards GET /v1/omnigenesis, but does NOT install
a new phone application or expose the engine port publicly.

The CLI dashboard command creates an HTML offline snapshot (not live data).
Animation is visual presentation only and never an assertion of autonomous
agent activity. Empty ledger means zero research records.

For architecture, ownership, remaining research and release gates see:
docs/icarus/OMNIGENESIS.md.

## Strict prohibitions

No eval or arbitrary generated code, live order APIs, broker tokens, trade
state writes, paid vendor requests, production model promotion, self-deploy,
indefinite autonomous tasks, hidden future inputs or fabricated causal proof.

## Phase 17–18 ICARUS × UMBRA hybrid research — current draft

Phase 17 provides local, read-only, normalized JSONL intake and precise checksum/declared futures-roll and timestamp audits. It does **not** authenticate the claimed vendor, validate actual market-data rights, reconstruct official MBO or produce market signals. UMBRA's separate v5 source is accepted only as a schema-checked synthetic paired-worldline report. Phase 18 provides an **explicitly invoked**, typed, dependency-checked, research-only task DAG with deterministic chained receipts and fail-closed task statuses. Derived summaries may be appended to the existing immutable SQLite research ledger and consequently viewed in the existing authenticated OMNIGENESIS tab without a new write endpoint.

    python -m icarus_engine.omnigenesis market-intake path/to/local_tape.jsonl path/to/manifest.json
    python -m icarus_engine.omnigenesis audit-umbra path/to/paired.json --claimed-source-commit aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
    python -m icarus_engine.omnigenesis workflow path/to/workflow.json
    python -m icarus_engine.omnigenesis workflow path/to/workflow.json --execute --root . --output research/new_workflow_receipt.json

All paths above are illustrative. No licensed market tape, vendor attestation, live feed, broker order, or actual UMBRA engine replay was performed. Workflow compute budgets are estimates rather than preemptive CPU enforcement. A PASS receipt is not APEX/DAEDALUS approval, empirical causality or profit evidence. Do not present the current local executor as permanently running agents. Source, schemas, nonclaims and release gates: docs/icarus/OMNIGENESIS_SOVEREIGN_HYBRID.md.
