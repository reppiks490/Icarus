# ICARUS Control-Plane Handoff — 2026-09-24

> Prepared by GPT-5.6 Sol from the read-only subsystem-rotation/control-plane work completed on 2026-09-23/24.
>
> This package records evidence and continuation instructions. It does **not** authorize live trading, repository-wide rewrites, model promotion, or execution.

## Purpose

This directory externalizes the durable state from the ChatGPT ICARUS subsystem-rotation work so the next implementation/research agent does not need the original conversation.

The work covered:

- round-robin subsystem review: `NEXUS -> AION -> ARGUS -> ATHENA -> DAEDALUS -> ORACLE`
- evidence-backed ownership/interface reconciliation
- fail-closed subsystem admission rules when canonical evidence is missing
- AION replay/provenance defects
- ARGUS ingress provenance requirements
- ATHENA uncertainty-lineage requirements
- DAEDALUS protected-evidence lineage risk
- ORACLE canonical-identity blocker
- diagnosis of the failed multi-automation control-plane handoff
- replacement design: one unified hourly S1->S5 control cycle with an in-run shared policy epoch and pinned snapshot

## Non-negotiable constraints

These constraints were preserved throughout the work and must remain preserved:

- `execution_authorized=false`
- no synthetic bars represented as empirical market evidence
- no invented trainer slots/features
- no Pulse rewrite
- fail-closed qualification
- deterministic canonical serialization/replay where applicable
- strict event/availability-time integrity
- immutable/tamper-evident provenance/audit where required
- uncertainty may never increase authority
- repository evidence outranks summaries/handoffs
- do not infer subsystem responsibility from its name

## Current canonical repo snapshot used for ICARUS

At the final control-plane diagnosis, the visible `reppiks490/Icarus` default branch head was:

```
007e70189945b8e112904cf92b2b1a12e43792d6
```

This handoff branch was created from that commit. Do not silently treat later code as equivalent evidence; revalidate affected findings if `main` has advanced.

## External sibling evidence used

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
2. [UNIFIED_CYCLE_RUNBOOK.md](UNIFIED_CYCLE_RUNBOOK.md) — repaired S1->S5 scheduler/control-plane design.
3. [HANDOFF_STATE.json](HANDOFF_STATE.json) — machine-readable continuation state.
4. [../superpowers/plans/2026-09-24-icarus-control-plane-handoff.md](../superpowers/plans/2026-09-24-icarus-control-plane-handoff.md) — implementation plan for turning the findings into repository changes safely.

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
6. run focused + full applicable verification,
7. preserve `execution_authorized=false`,
8. update this handoff with the new evidence revision and test output.

Do not weaken a safety/provenance/holdout gate just to make a test or candidate pass.


## Repo-native receipt verifier

The runtime branch adds a dependency-free verifier package, `icarus_control`, with the console command:

```text
icarus-control digest FILE
icarus-control validate-receipt FILE
icarus-control validate-cycle DIRECTORY
```

This verifier is intentionally narrower than the scheduler. It validates deterministic receipt canonicalization, SHA-256 receipt links, exact policy/schema identity, same-cycle policy epoch, pinned repository snapshots, stage order, maturity ceilings, evidence-lineage structure, S4 oracle provenance fields, and the invariant `execution_authorized=false`.

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
