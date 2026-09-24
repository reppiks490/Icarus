# ICARUS Master Handoff — 2026-09-24

This directory is the durable handoff for the current ICARUS research/control architecture and the next implementation lane.

## Canonical baseline

- Repository: `reppiks490/Icarus`
- Pinned baseline at handoff creation: `007e70189945b8e112904cf92b2b1a12e43792d6`
- Branch containing this handoff: `icarus-handoff-2026-09-24`
- Trading execution authority: **disabled**
- `execution_authorized=false`
- No Pulse rewrite.
- No invented trainer slots or features.
- No synthetic bars as empirical evidence.
- No merge, deploy, trade, or publish permission is implied by this documentation.

## What this handoff contains

1. [Architecture](ARCHITECTURE.md) — system layers, invariants, maturity ladder, evidence/control fabric.
2. [Control plane](CONTROL_PLANE.md) — Unified Control Cycle, safeguards, migration from legacy loops.
3. [XGB Slot 1 plan](XGB_SLOT1_IMPLEMENTATION.md) — implementation-ready challenger-model plan.
4. [Findings and defects](FINDINGS_AND_DEFECTS.md) — verified/observed defects, methodology conflicts, provider facts.
5. [Onboarding](ONBOARDING.md) — how engineering, empirical research, verification, and observability agents should connect.
6. [Automation status](AUTOMATION_STATUS.json) — active/disabled automation inventory.
7. [Manifest](MANIFEST.json) — machine-readable artifact/status/blocker/next-action index.

## Current priority

**Freeze further architecture expansion and implement the empirical-integrity lane.**

The highest-value sequence is:

1. Repair causal event-feature leakage in trainer-only paths.
2. Make every trainer exit explicitly preserve `execution_authorized=false`.
3. Implement real XGB Slot 1 using the frozen repository contract.
4. Add terminal-holdout consumption protection.
5. Add deterministic model/study/data provenance.
6. Harden XGB artifact qualification in audit.
7. Require incremental out-of-sample value versus Slot 0 before promotion.
8. Run targeted tests, full `tests_engine`, and an independent verification pass.

## Status vocabulary

- **VERIFIED** — directly supported by repository/tool evidence.
- **OBSERVED** — directly seen, but not necessarily fully validated.
- **SPECIFIED** — implementation/design contract exists.
- **BLOCKED** — cannot safely advance without missing evidence/capability.
- **UNVERIFIED** — plausible or designed, but not demonstrated.
- **REJECTED** — deliberately excluded after evidence/relevance check.

## Important distinction

ICARUS architecture maturity is ahead of implementation maturity. The control/evidence system is substantial; XGB Slot 1, holdout ledger, generalized evidence adapters, and hardened artifact validation still require landed code and fresh tests.
