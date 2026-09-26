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

AION:
- repo: `reppiks490/aion-parallax-research`
- pinned evidence head: `12a7cb8ef99e84ce50b766db0aea1592b3906f80`

DAEDALUS:
- repo: `reppiks490/daedalus-research-os`
- pinned evidence head: `74ad94149b02ddd3f69d535ee5fdc00c1fdbe096`

ARGUS / ATHENA:
- live canonical repositories were not visible through the connected account during the audit.
- saved ownership snapshots were available through AION's code-atlas documents only.
- therefore implementation-level claims for ARGUS/ATHENA remain partial until their current working trees are recovered.

NEXUS / ORACLE:
- no canonical implementation/ownership evidence was established in accessible repositories.
- they remain fail-closed / unverified.

## Read next

1. [SUBSYSTEM_ROTATION_FINDINGS.md](SUBSYSTEM_ROTATION_FINDINGS.md) — evidence and artifacts for each subsystem.
2. [AEGIS_IMPLEMENTATION_MATRIX.md](AEGIS_IMPLEMENTATION_MATRIX.md) — Findings 019–030 mapped to exact current controls and next regressions.
3. [UNIFIED_CYCLE_RUNBOOK.md](UNIFIED_CYCLE_RUNBOOK.md) — repaired S1->S5 scheduler/control-plane design.
4. [HANDOFF_STATE.json](HANDOFF_STATE.json) — machine-readable continuation state.
5. [../superpowers/plans/2026-09-24-icarus-control-plane-handoff.md](../superpowers/plans/2026-09-24-icarus-control-plane-handoff.md) — implementation plan for turning the findings into repository changes safely.

## What was intentionally NOT done

- No ICARUS trading code was modified.
- No AION or DAEDALUS repository was modified.
- No broker/execution permission was changed.
- No subsystem was declared production-ready.
- No new model edge was declared empirically validated.
- No automated scheduler state was committed into this repository as if it were a repo-native daemon.

The hourly unified cycle referenced in this package is a ChatGPT automation/control-plane concept external to this repository. Treat repository docs as the durable specification and evidence record, not proof that the external automation is currently running.

## Continuation rule

Before implementing any finding:

1. pin the current repo revision,
2. compare it with the evidence revision recorded here,
3. reproduce the defect/invariant on that compatible revision,
4. write the independent failing regression test first,
5. implement the smallest fix only after the behavior is proven,
Before changing a component:
1. pin current revision,
2. check ownership,
3. reproduce the defect/invariant,
4. write the independent failing test first for behavior changes,
5. implement the smallest fix,
6. run focused + full applicable verification,
7. update compact state/evidence,
8. preserve trading execution authority as false.

Do not weaken a safety/provenance/holdout gate just to make a test or candidate pass.


## Repo-native receipt verifier

The runtime branch adds a dependency-free verifier package, `icarus_control`, with the console command:

```text
icarus-control digest FILE
icarus-control validate-receipt FILE
icarus-control validate-cycle DIRECTORY
```

This verifier is intentionally narrower than the scheduler. It validates deterministic receipt canonicalization, SHA-256 receipt links, exact policy/schema identity, same-cycle policy epoch, pinned repository snapshots, stage order, maturity ceilings, claim dependency closure, material conflict state, evidence-lineage DAG structure, S4 oracle provenance fields, and the invariant `execution_authorized=false`.

A successful validator result is only structural evidence. It does not prove a trading/model claim and does not authorize merge, deployment, publication, or trading.

### Evidence storage rule

Do not commit S1-S5 receipts onto the code branch whose revision they attest.

Recommended layout:

```text
code subject: main (or another pinned immutable commit)
evidence branch: control-evidence
control/receipts/<CYCLE_ID>/S1.json
control/receipts/<CYCLE_ID>/S2.json
control/receipts/<CYCLE_ID>/S3.json
control/receipts/<CYCLE_ID>/S4.json
control/receipts/<CYCLE_ID>/S5.json
```

This prevents the act of recording evidence from moving the code revision under verification.

The versioned contracts are:
- `contracts/icarus-control-v1.json`
- `contracts/icarus-pipeline-v1.json`
Do not weaken provenance, causality, holdout, uncertainty or execution-separation gates merely to obtain green.
