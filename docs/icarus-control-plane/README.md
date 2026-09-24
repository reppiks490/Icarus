# ICARUS Control-Plane Handoff — 2026-09-24

> Durable GitHub handoff for ICARUS engineering/research-control work. Repository evidence outranks chat summaries.

## Start here

1. [MASTER_INTEGRATION_INDEX.md](MASTER_INTEGRATION_INDEX.md) — current canonical map of what is built, verified, planned, blocked, and where it lives.
2. [INTEGRATION_MANIFEST.json](INTEGRATION_MANIFEST.json) — machine-readable pinned revisions, verified runs, open defects and connection state.
3. [CONNECTION_CONTRACTS.md](CONNECTION_CONTRACTS.md) — minimum subsystem/provider handshake.
4. [EVIDENCE_FINDINGS_LEDGER.md](EVIDENCE_FINDINGS_LEDGER.md) — verified findings vs reported/unreconciled work.
5. [PROVIDER_CAPABILITY_SNAPSHOT.json](PROVIDER_CAPABILITY_SNAPSHOT.json) — current provider admission/health observations.
6. [NEXT_CONNECTION_SEQUENCE.md](NEXT_CONNECTION_SEQUENCE.md) — exact recommended order for connecting the remaining system.
7. [HANDOFF_STATE.json](HANDOFF_STATE.json) — compact continuation state.
8. [SUBSYSTEM_ROTATION_FINDINGS.md](SUBSYSTEM_ROTATION_FINDINGS.md) — NEXUS/AION/ARGUS/ATHENA/DAEDALUS/ORACLE boundary evidence.
9. [UNIFIED_CYCLE_RUNBOOK.md](UNIFIED_CYCLE_RUNBOOK.md) — repaired S1->S5 orchestration model.

## Governing principle

GitHub is the persistent source of truth, engineering memory, validation layer, provenance layer, research checkpoint registry and multi-agent coordination fabric.

Do not optimize for the appearance of complexity. Complexity must reduce failure, compute, tokens, manual work, recovery time, research error or agent confusion—or measurably improve correctness, observability, reproducibility, research quality, reuse or extensibility.

## Authority boundary

Repository writes are authorized for this handoff update.

Live trading/order authority remains **false**.

No documentation, test, PR, checkpoint or research maturity state may silently grant broker/order execution.

## Current high-level state

- PR #17: durable handoff package
- PR #18: repo-verifiable control receipt chain; CI global-root workaround verified; documented subcommand-root contract still open
- PR #19: point-in-time market-data vintage layer implemented and green; stronger cryptographic verification still pending
- OMNIVISION Stage 0: verified GO on temporal/boundary scope
- OMNIVISION Stage 1: planned, not implemented
- AION: canonical repo pinned; gap-history integrity defect open
- DAEDALUS: canonical repo pinned; protected-evidence source-lineage defect open
- ARGUS/ATHENA/NEXUS/ORACLE: canonical repositories not established in latest discovery; fail closed
- provider capability architecture: specified from live admission evidence; adapter breadth deferred until Stage 1 governance exists

## Continuation discipline

Before changing a component:
1. pin current revision,
2. check ownership,
3. reproduce the defect/invariant,
4. write the independent failing test first for behavior changes,
5. implement the smallest fix,
6. run focused + full applicable verification,
7. update compact state/evidence,
8. preserve trading execution authority as false.

Do not weaken provenance, causality, holdout, uncertainty or execution-separation gates merely to obtain green.
