# ICARUS Integration Handoff

Generated for the 2026-09-24 18:00 America/Chicago control cycle and committed only to the integration branch.

## Purpose

This directory consolidates the verified repository findings, repair packets, subsystem boundary evidence, provenance, and connection contracts produced during the ICARUS control work. It is intentionally separated from production code so sibling systems can connect against explicit contracts without silently acquiring execution authority.

## Non-negotiable controls

- `execution_authorized=false`.
- No synthetic bars are admissible as empirical evidence.
- Do not invent trainer slots, features, symbols, workers, tests, evidence, repository state, locks, or persistence.
- Do not rewrite Pulse.
- Qualification and integration fail closed.
- Preserve deterministic/canonical serialization and replay where the underlying subsystem supports it.
- Preserve strict temporal/as-of integrity.
- Uncertainty cannot increase authority.
- A parser/unit/replay smoke test does not prove financial edge or deployment readiness.
- Technical acceptance does not imply permission to merge, deploy, trade, or publish.

## Package map

- `CONTROL_STATE_20260924-18.json` — compact authoritative handoff state.
- `SUBSYSTEM_CONNECTION_MAP.md` — pinned roles, boundaries, and connection readiness.
- `CONNECTION_MANIFEST.json` — machine-readable sibling connection registry.
- `VERIFIED_FINDINGS.md` — findings confirmed against pinned repository evidence.
- `repair/ICARUS-RISK-001_UNSUPPORTED_EVENT_FAIL_OPEN.md` — TDD repair packet for bridge event dispatch.
- `repair/AION-INTEGRITY-001_DURABLE_STATE_HASH_SCOPE.md` — integrity-scope repair/design packet.
- `repair/TRAINER-CALIBRATION-001_HOLDOUT_CONTAMINATION.md` — frozen-spec conflict packet.
- `repair/NEXUS-RELEASE-001_CORPUS_RESEAL.md` — NEXUS reconciliation/reseal packet.
- `PROVENANCE_LEDGER.json` — source commits/blobs and evidence lineage.
- `NEXT_ACTIONS.md` — ordered, bounded work queue.

## Authority boundary

The findings below are evidence-backed at the pinned revisions in the provenance ledger. Any newer branch/commit must be revalidated before promotion. Provisional handoff/library material is not promoted to canonical subsystem authority here.

## Current top priorities

1. Close ICARUS-RISK-001 with a failing regression test first, then the smallest fail-closed parser/dispatcher fix.
2. Define and independently verify AION tamper-evidence coverage for durable prediction/settlement/gap state without breaking replay.
3. Resolve the Slot-1 XGB calibration/evaluation split conflict before implementation.
4. Reconcile and reseal NEXUS against the current 659-member / 13,788,256-row corpus evidence before integration authority.
