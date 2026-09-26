# ICARUS Next Connection Sequence

This is the preferred integration order for future agents. Do not skip a gate because a later subsystem is more interesting.

## 0. Preserve current verified baselines
Pin:
- ICARUS main `007e70189945b8e112904cf92b2b1a12e43792d6`
- PR #18 head `76569e1962e721b0f4dc973df21358f40c31ce81`
- PR #19 head `e05c122f7a8e5501d98251c7449cbe7ce3ec6dda`
- OMNIVISION current planning head `9f3c792d44fd9142e0b98676224dfe50d740db3b`
- AION `12a7cb8ef99e84ce50b766db0aea1592b3906f80`
- DAEDALUS `74ad94149b02ddd3f69d535ee5fdc00c1fdbe096`

## 1. Repair the plant public CLI contract
TDD:
1. add failing regression for `plant_main(["setup","--root",...])`
2. support subcommand-local `--root` while retaining global-root compatibility
3. run focused plant tests
4. run Linux + Windows CI
5. keep doctor smoke gate

Do not merely keep the invocation-order workaround.

## 2. Execute OMNIVISION Stage 1
Use the existing plan:
`docs/superpowers/plans/2026-09-24-omnivision-v2-stage1-control-plane.md`

Order:
1. deterministic identity + SourceCapability
2. provenance DAG + recursive invalidation
3. search-aware TrialRecord/ledger
4. governed EvidenceGateway
5. Stage-1 integration tests + Python matrix + native CI
6. audit/checkpoint

No real provider adapter in Stage 1.

## 3. Strengthen market-data vintage provenance
Build on PR #19:
- authenticated hash chain/head
- tamper regression
- deterministic `as_of` reconstruction
- stable canonical-history linkage
- preserve first-captured-vs-original-publication distinction

## 4. Fix AION integrity in owning repo
- failing tamper test first
- authenticate gap-history transitions
- verify replay failure closes on mutation/deletion/reordering

## 5. Fix DAEDALUS lineage in owning repo
- stable source lineage ID
- snapshot ancestry relation
- append-only descendant regression
- mutated/reordered descendant fail-closed mapping
- no holdout recycling

## 6. Recover missing subsystem ownership
Search/recover canonical:
- ARGUS
- ATHENA
- NEXUS
- ORACLE

Do not create replacements until owner/canonical absence is proven and an explicit design decision authorizes replacement.

## 7. Connect providers only after Stage 1
Each adapter must satisfy SourceCapability + relevance + timing + revision + provenance + negative-control tests.

Initial preference:
- sources with strong point-in-time semantics,
- sources with unique information value,
- sources whose upstream identity is known,
- sources with reproducible historical access.

Avoid connector-count maximization.

## 8. Rebuild empirical qualification
Before performance promotion:
- clean calibration split
- untouched evaluation/holdout
- strict chronology
- purging/embargo where needed
- costs/slippage/latency
- search-space accounting
- multiple-testing controls
- walk-forward stability
- ablations
- reproducible artifact hashes

## 9. Then connect supervisory/research systems
Only after canonical contracts exist:
- AION time/replay evidence
- DAEDALUS research evidence
- ARGUS microstructure
- ATHENA uncertainty/advisory
- NEXUS/ORACLE roles once verified
- OMNIVISION governed research graph

## Stop rule
If the next action cannot improve correctness, observability, reproducibility, recoverability, research quality, token/compute efficiency, or reduce failure/manual work, stop with `NO_CHANGE_JUSTIFIED`.
