# ICARUS Assurance / Prior-Work Archive

This directory is the durable repository index for the ICARUS/AEGIS work consolidated from prior ChatGPT research, red-team, handoff and verification sessions.

## Start here

1. [AEGIS Assurance Baseline v1](AEGIS_ASSURANCE_BASELINE_V1.md) — frozen Findings 001–030 and the transition from discovery to implementation assurance.
2. [Control-Plane Implementation Map](CONTROL_PLANE_IMPLEMENTATION_MAP.md) — highest-priority executable architecture for durable S1–S5 policy/snapshot/handoff/evidence/oracle receipts.
3. [Related Build Registry](RELATED_BUILD_REGISTRY.md) — pinned repository/branch identities observed during consolidation.
4. [Transfer Change Record](CHANGE_RECORD_2026-09-24.md) — provenance and evidentiary boundary for this archive.\n5. [Source Manifest](SOURCE_MANIFEST.md) — source file identities, transfer modes, and binary/text limitations.

## Preserved source artifacts

- [Full AEGIS dossier](archive/ICARUS_AEGIS_FULL_DOSSIER.txt)
- [Full AEGIS masterbuild handoff](archive/ICARUS_AEGIS_MASTERBUILD_FULL_HANDOFF.md)
- [Complete S3 Agent Reach handoff](archive/ICARUS_S3_COMPLETE_HANDOFF.txt)
- [Unified 5-stage control-cycle handoff](archive/ICARUS_Unified_Control_Cycle_Master_Handoff_20260924-07.txt)
- [AEGIS worklog / Findings 019–030 / Stage-5 assurance](archive/ICARUS_AEGIS_WORKLOG.md)
- [Stage-5 machine-readable receipt](archive/stage5_final_receipt.json)

## Epistemic boundary

Git storage does not promote a claim. Archived statements marked proposed, specified, blocked, unverified, reported, or not-run retain those meanings. Fresh repository code, pinned revisions, independently defensible tests and valid provenance remain required for implementation/release claims.

## Non-negotiable constraints carried forward

- `execution_authorized=false`
- no synthetic bars represented as empirical evidence
- no invented trainer slots/features
- no Pulse rewrite
- fail-closed qualification
- deterministic canonical serialization/replay where applicable
- tamper-evident provenance/audit
- strict temporal integrity
- uncertainty cannot increase authority
- technical acceptance never implies permission to merge, deploy, trade or publish

## Active direction

The red-team discovery loop is frozen at AEGIS Findings 001–030. The active loop is implementation assurance:

`implement → attack → regress → qualify → map evidence → repeat`

Priority zero is the durable S1–S5 control-plane substrate. Do not resume open-ended finding generation unless implementation work exposes a genuinely new failure class.

## Stale when

Update this index when a linked artifact moves, a newer assurance baseline supersedes v1, or the canonical control-plane implementation lands.
