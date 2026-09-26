# ICARUS Master Integration Index — 2026-09-24

This is the compact canonical handoff for the work completed across the ICARUS GitHub/control-plane, OMNIVISION, market-data provenance, subsystem-boundary, and provider-admission lanes on 2026-09-23/24.

The repository remains the source of truth. This document points to immutable revisions and verified evidence; it does not convert chat summaries into implementation authority.

## Authority split

- repository_write_authorized: true for this handoff/update
- live_trading_execution_authorized: false
- broker/order authority: false
- research promotion authority: fail-closed
- Pulse rewrite: prohibited
- synthetic bars as empirical evidence: prohibited
- invented trainer slots/features: prohibited

Engineering write permission MUST NOT be interpreted as live-trading permission.

## Canonical ICARUS baseline

Default branch:
- repo: `reppiks490/Icarus`
- branch: `main`
- immutable revision: `007e70189945b8e112904cf92b2b1a12e43792d6`

Main is intentionally not treated as equivalent to later stacked research/control branches.

## Current integration branches

### PR #17 — durable handoff/control-plane evidence
- branch: `chatgpt/icarus-control-plane-handoff-20260924`
- prior head: `c1c331a7a743bcad3dc1e7128eb5cb6f61ac8225`
- purpose: durable subsystem/control-plane handoff
- state: documentation/evidence package
- base: `main`

### PR #18 — repo-verifiable S1->S5 receipt chain
- branch: `chatgpt/icarus-control-plane-runtime-20260924`
- head: `76569e1962e721b0f4dc973df21358f40c31ce81`
- purpose: deterministic control-receipt verification and fail-closed policy-chain validation
- state: implemented on stacked branch
- IMPORTANT: CI was made green by moving global `--root` before the plant subcommand. That is a verified workaround, not proof that the documented public form `icarus-plant setup --root DIR` was repaired.

### PR #19 — point-in-time market-data vintage preservation
- branch: `chatgpt/icarus-data-vintage-20260924`
- head: `e05c122f7a8e5501d98251c7449cbe7ce3ec6dda`
- verified Actions run: `36065964176` = success
- purpose: preserve observations/revisions before canonical CSV history mutation
- state: implemented + green on stacked branch
- residual hardening: append-only SQLite semantics are not yet a cryptographic verification chain; deterministic authenticated-head verification and full as-of reconstruction remain future proof obligations.

### OMNIVISION v2
- branch: `codex/exotic-research-loop`
- current head observed: `9f3c792d44fd9142e0b98676224dfe50d740db3b`
- head message: `Codex: plan OMNIVISION v2 Stage 1 control plane`
- Stage-0 verified commit/run evidence:
  - Actions `36071102061` — OMNIVISION Stage 0 — success
  - Actions `36071102460` — native tests — success
  - both ran at `511814e1d4f4a2527abaa3b6e3472a66df666281`
- Stage 0 status: VERIFIED GO on its stated temporal/boundary scope
- Stage 1 status: PLANNED, NOT YET IMPLEMENTED
- Stage 1 plan: `docs/superpowers/plans/2026-09-24-omnivision-v2-stage1-control-plane.md`
- Stage 1 scope: source capability registry + provenance DAG + search-aware trial ledger + governed evidence gateway

## Sibling repositories

### AION
- repo: `reppiks490/aion-parallax-research`
- pinned/current head observed: `12a7cb8ef99e84ce50b766db0aea1592b3906f80`
- open proof obligation: replay-significant `source_gap_history` is not authenticated by the main integrity chain.

### DAEDALUS
- repo: `reppiks490/daedalus-research-os`
- pinned/current head observed: `74ad94149b02ddd3f69d535ee5fdc00c1fdbe096`
- open proof obligation: protected-holdout exposure identity is snapshot-SHA keyed without a proven stable logical-source lineage across append-only descendants.

### ARGUS / ATHENA / NEXUS / ORACLE
No installed canonical repository was found for these names during the latest repository discovery pass.
They remain fail-closed for integration authority until canonical repository + immutable revision + ownership/contracts are established.

## Highest-value verified findings

1. **CLI contract anti-gaming issue**
   - CI can pass using `icarus-plant --root DIR setup`.
   - Repository documentation still advertises `icarus-plant setup --root DIR`.
   - No verified regression proves the documented argument order.
   - Classification: WORKAROUND_VERIFIED / CONTRACT_DEFECT_OPEN.

2. **Disconnected multi-automation control plane**
   - independent S1..S5 automations did not have guaranteed authoritative same-cycle handoff transport.
   - durable design: one sequential S1->S5 cycle with one policy epoch, one pinned snapshot, one evidence chain.

3. **Point-in-time market-data provenance**
   - PR #19 now records observations/revisions before canonical-history merge.
   - first captured observation is not falsely labelled vendor-original publication.
   - provenance failure blocks canonical overwrite.

4. **OMNIVISION temporal integrity**
   - Stage 0 now carries executable tests for non-reused walk-forward folds and decision-time availability boundaries.
   - Stage 1 must build source capability/version state, explicit provenance DAG, and complete search/trial accounting before provider breadth expands.

5. **Provider capability is state, not installation**
   - installed connector != reachable connector != entitled data != authoritative evidence.
   - provider availability must be represented explicitly and historically.

6. **Evidence independence**
   - two vendors relaying the same upstream source are derived/duplicate evidence, not independent confirmation.

7. **Research authority**
   - descriptive correlation != strategy.
   - backtest != proof.
   - holdout/calibration contamination blocks promotion.
   - uncertainty may never increase authority.

## Reported prior-loop work not yet reconciled as canonical merged implementation

The overnight conversations also reported AEGIS hardening batches, isolated integrity tests, and broader subsystem research. Those reports are useful evidence leads but MUST NOT be called merged/current until their canonical repository locations and revisions are pinned and revalidated.

## Read next

1. `INTEGRATION_MANIFEST.json`
2. `CONNECTION_CONTRACTS.md`
3. `EVIDENCE_FINDINGS_LEDGER.md`
4. `PROVIDER_CAPABILITY_SNAPSHOT.json`
5. `NEXT_CONNECTION_SEQUENCE.md`
6. `HANDOFF_STATE.json`
7. `UNIFIED_CYCLE_RUNBOOK.md`
8. `SUBSYSTEM_ROTATION_FINDINGS.md`

## Integration rule

A component may connect only when:
- canonical implementation location is known,
- immutable revision is pinned,
- owned inputs/outputs are explicit,
- timing and provenance semantics are explicit,
- uncertainty/failure semantics are explicit,
- deterministic replay expectations are stated where applicable,
- required tests pass,
- no open load-bearing conflict invalidates the boundary,
- live trading authority remains false unless separately and explicitly changed.
