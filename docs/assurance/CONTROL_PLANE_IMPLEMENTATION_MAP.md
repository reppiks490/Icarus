# ICARUS Control-Plane Implementation Map

Status: recommended next implementation slice. This is a design/implementation map, not a claim that the subsystem is already implemented.

## Why this is priority zero

Stage 5 repeatedly failed closed because S1–S4 did not expose a durable, machine-verifiable same-cycle handoff chain. The engine already contains useful primitives (strict canonical JSON/SHA-256 patterns, immutable ledger patterns, transactional journals, replay/fingerprint tests and explicit execution controls), so the fix should be a narrow assurance subsystem rather than a strategy/Pulse rewrite.

## Do not repurpose

- `state.json` — already assigned a different mathematical/trend-state role by repository instructions.
- `HANDOFF_LOG.md` — useful human history, but mutable prose is not the machine-authoritative receipt chain.
- `icarus_engine/strategy/pulse.py` — out of scope.
- trainer slots/features — do not invent or alter them for this work.

## Proposed repository seams

```text
icarus_engine/pipeline_control.py
tests_engine/test_pipeline_control.py
PIPELINE_POLICY.json
CONTROL_PLANE.md
icarus_engine/cli.py        # narrow verify/receipt entry points only
```

A dedicated control-plane branch/storage surface is preferred for receipts so the code snapshot pinned by S1 does not move merely because a stage writes its receipt.

## Required receipt envelope

Every S1–S5 receipt should bind:

- `handoff_schema_version = icarus-pipeline-v1`
- `pipeline_policy_version = icarus-control-v1`
- policy epoch / exact policy artifact identity
- cycle ID and execution-instance ID
- stage and ordinal
- producer identity
- produced-at timestamp
- repository identity
- immutable baseline revision
- snapshot-set identity/digest
- previous stage
- previous receipt digest
- stage payload
- receipt digest

S1 has no predecessor. S2→S1, S3→S2, S4→S3 and S5→S4 must hash-link.

## Domain-separated identity

Do not silently change existing repository hash semantics. Add a control-plane-specific domain-separated digest, conceptually:

```text
SHA256(
  "ICARUS-CONTROL-V1\0"
  + artifact_type
  + "\0"
  + canonical_json(payload)
)
```

This prevents semantically different artifact types from sharing a naked byte-hash identity.

## Stage payload graphs

Use explicit machine-readable collections for:

- claims
- dependencies
- conflicts
- evidence origins

Evidence origins must collapse summaries/agents/dashboards derived from the same decisive source into one independent origin.

S4 additionally carries:

- TEST_ORACLE_ORIGIN
- TEST_ORACLE_DERIVED_FROM
- ORACLE_INDEPENDENCE_STATUS
- GOLDEN_VECTOR_PROVENANCE
- NEGATIVE_CONTROLS
- MUTATION_OR_FAULT_INJECTION_PLAN

S5 alone may promote to VERIFIED_FOR_INTEGRATION.

## Fail-closed outcomes

- missing/different required policy epoch → `MIXED_POLICY`
- baseline/snapshot mismatch → `MIXED_REVISION`
- broken predecessor digest/schema/producer/chronology → invalid handoff chain
- missing stage → incomplete liveness/completeness
- identical repeated stage receipt → duplicate suppressed
- different second receipt for same cycle/stage → competing-authority failure, never overwrite
- dependency cycle → promotion blocked
- rejected/insufficient prerequisite → descendants transitively blocked
- TAUTOLOGICAL/INVALID material oracle → full promotion impossible
- UNKNOWN material oracle → full promotion impossible
- unauthorized prior promotion → AUTHORITY_VIOLATION

## Minimum adversarial verification suite

- key-order permutation preserves canonical digest
- one-value mutation changes digest
- predecessor-digest mutation breaks chain
- wrong policy epoch yields MIXED_POLICY
- wrong baseline yields MIXED_REVISION
- stage chronology violation rejected
- duplicate identical receipt suppressed
- competing different receipt rejected/flagged
- duplicate evidence reports retain one independent origin
- dependency cycle blocks promotion
- rejected prerequisite blocks descendants
- tautological oracle cannot reach VERIFIED_FOR_INTEGRATION
- unknown oracle cannot reach full promotion
- unauthorized promotion produces authority violation
- deleted/missing receipt breaks completeness
- unknown schema/enum fails closed

At least one deliberate plausible mutation/fault must be shown to be detected before the oracle is treated as independently useful.

## Existing primitives to reuse

The current repository already demonstrates:
- bounded canonical JSON + SHA-256 in `icarus_engine/advisory.py`
- immutable SQLite trigger patterns in `AdvisoryLedger`
- transactional/WAL workflow semantics in orchestration/research components
- replay/fingerprint tests in `tests_engine/`
- explicit `execution_authorized=false` safety boundaries

Reuse these patterns where compatible; do not create parallel semantics without need.

## Acceptance boundary

Technical acceptance of this subsystem does not authorize merge, deployment, publication or trading. `execution_authorized=false` remains unchanged.

## Stale when

This map becomes stale when a canonical pipeline-control implementation lands or when the repository adopts a different versioned control-plane architecture with equivalent or stronger guarantees.
