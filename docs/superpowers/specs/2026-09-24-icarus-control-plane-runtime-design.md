# ICARUS Repo-Native Control-Plane Runtime — Design

## Status

Approved implementation direction for the 2026-09-24 control-plane hardening cycle.

This design implements **evidence verification**, not a scheduler and not a trading subsystem.

## Goal

Make S1->S5 handoffs durable, deterministic, independently checkable, and fail-closed without moving the code revision being verified.

The tool must make it possible for Stage 5 to distinguish:

- a complete, exact-policy, exact-snapshot chain,
- a mixed-policy chain,
- a mixed-revision chain,
- a broken/tampered digest chain,
- an incomplete chain,
- an S4 handoff whose test oracle provenance is insufficient.

It must never turn technical chain validity into trading, merge, deployment, publication, or model-promotion authority.

## Non-goals

- No background scheduler.
- No agent orchestration runtime.
- No broker integration.
- No Pulse or emulator rewrite.
- No new trainer slots or model features.
- No synthetic market observations.
- No automatic claim promotion.
- No secrets, credentials, or GitHub-token handling.
- No claim that the format is SLSA/in-toto compliant.

## Architecture

### Code subject and evidence history are separate

A cycle pins the code subject once:

```text
repo_baseline_revision=<immutable git commit>
repo_snapshot_set=<all materially used repositories + immutable revisions>
```

S2-S5 must consume that same subject. Stage receipts MUST NOT be committed onto the code branch being verified because doing so would move its branch head and create self-induced snapshot drift.

Recommended evidence storage:

```text
branch: control-evidence
path: control/receipts/<CYCLE_ID>/S1.json ... S5.json
```

The evidence branch is append-only by convention and independent of the code subject. Git history provides an outer history; the receipt digest chain provides an inner deterministic chain.

### Receipt envelope

Every receipt contains:

- `handoff_schema_version = icarus-pipeline-v1`
- `pipeline_policy_version = icarus-control-v1`
- `pipeline_policy_epoch`
- `cycle_id`
- `execution_instance_id`
- `stage`
- `producer`
- `repo_baseline_revision`
- `repo_snapshot_set`
- `policy_contract_digest`
- `handoff_schema_digest`
- `prior_stage_digest`
- `claims`
- `dependencies`
- `conflicts`
- `evidence_lineage`
- `execution_authorized = false`
- `receipt_digest`

S4 additionally carries:

- `test_oracle_origin`
- `test_oracle_derived_from`
- `oracle_independence_status`
- `golden_vector_provenance`
- `negative_controls`
- `mutation_or_fault_injection_plan`

S5 may carry release-assurance fields, but the validator never infers substantive correctness merely because those fields are present.

### Canonicalization

The v1 canonical form is UTF-8 JSON with:

- recursively sorted object keys,
- array order preserved,
- compact separators,
- no NaN or Infinity,
- no implicit datetime/decimal coercion.

A receipt digest is SHA-256 over the entire receipt after removing only `receipt_digest`.

### Chain rules

S1:
- `prior_stage_digest = null`.

S2-S5:
- `prior_stage_digest` equals the immediately preceding receipt's verified digest.

All stages:
- exact same `cycle_id`,
- exact same `pipeline_policy_epoch`,
- exact policy/schema versions and contract digests,
- exact same `repo_baseline_revision`,
- canonically equivalent `repo_snapshot_set`,
- `execution_authorized == false`,
- stage order exactly S1,S2,S3,S4,S5.

Unknown stages, future enum values, absent mandatory fields, non-finite numbers, digest mismatch, or semantic ambiguity fail closed.

### Output semantics

The validator emits structural states such as:

- `VALID`
- `INCOMPLETE`
- `MIXED_POLICY`
- `MIXED_REVISION`
- `INVALID`

It may state `promotion_path_valid=true` only for the **structural path**. That does not mean any trading/model claim is true or verified for integration.

## CLI

```text
icarus-control digest FILE
icarus-control validate-receipt FILE --policy POLICY --schema SCHEMA
icarus-control validate-cycle DIR --policy POLICY --schema SCHEMA
```

The CLI is read-only with respect to repository/trading state. It does not create or mutate receipts.

## Failure semantics

Any uncertainty that affects chain authority preserves or reduces authority.

Examples:

- missing predecessor -> INCOMPLETE
- different policy/epoch -> MIXED_POLICY
- different baseline/snapshot -> MIXED_REVISION
- bad digest -> INVALID
- S4 oracle metadata absent -> INVALID
- S4 oracle status TAUTOLOGICAL/INVALID -> structurally present but promotion path blocked
- unknown status -> fail closed

## Security / integrity boundary

The digest chain detects post-creation mutation when a trusted digest is available. It is not a signature and does not identify a human cryptographically.

Future strengthening may add GitHub artifact attestations or Sigstore signatures, but v1 remains dependency-free and must not pretend unsigned hashes are signatures.

## Tests

Independent/property-oriented checks include:

1. deterministic canonical serialization;
2. NaN/Infinity rejection;
3. semantic mutation changes digest;
4. digest-field self-exclusion is the only exclusion;
5. exact policy/schema enforcement;
6. execution_authorized cannot be true or absent;
7. stage-order and predecessor-link validation;
8. missing predecessor fails closed;
9. mixed policy/epoch detected;
10. mixed baseline/snapshot detected;
11. S4 oracle provenance required;
12. TAUTOLOGICAL/INVALID oracle blocks structural promotion;
13. receipt tamper breaks digest;
14. valid S1->S5 chain passes structural validation.

## Operational rule

A green `icarus-control validate-cycle` is evidence that the handoff chain is structurally coherent. It is never authorization to merge, deploy, publish, trade, or increase model authority.
