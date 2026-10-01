# ICARUS Subsystem Rotation Findings

## Status vocabulary

- **VERIFIED BOUNDARY** — responsibility/interface supported by canonical pinned evidence.
- **PARTIAL** — supported by a sibling snapshot but current implementation not directly available.
- **UNVERIFIED** — canonical role/implementation not established; fail closed.
- **OPEN DEFECT** — evidence-backed technical defect; not yet implemented/retested here.

---

## 1. NEXUS

Status: **UNVERIFIED**

Accessible ICARUS repositories did not establish a canonical NEXUS implementation or ownership contract. No responsibility was inferred from the name.

### Artifact: NEXUS subsystem admission invariant

```text
A named subsystem MUST NOT participate in ICARUS integration until evidence
establishes all of:

1. canonical implementation location + immutable revision
2. responsibility statement
3. owned input/output contracts
4. sibling ownership exclusions
5. event-time / observation-time semantics
6. provenance requirements
7. deterministic replay behavior
8. uncertainty/failure semantics
9. execution_authorized == false
10. regression tests proving the preceding properties

Missing/ambiguous evidence => subsystem_state = UNVERIFIED
UNVERIFIED => no authority, no inferred adapters, no synthetic substitute,
              no silent qualification.
```

Proof obligation: locate canonical NEXUS implementation/architecture evidence and validate the above contract.

---

## 2. AION

Status: **VERIFIED BOUNDARY / OPEN DEFECT**

Canonical evidence:
- `reppiks490/aion-parallax-research`
- `12a7cb8ef99e84ce50b766db0aea1592b3906f80`

Canonical responsibility from AION docs:

> AION owns the shared time/identity/replay evidence contract.

AION is research/shadow only and does not own execution. It preserves event/publish/availability/ingestion clocks, revisions, source identity, as-of replay, forecasts, settlements, and evidence-tier firewalls.

### Open defect: gap history is replay-significant but not cryptographically authenticated

`source_gap_history` affects `gaps_asof()`, which affects replay book validity and therefore frame hashes. Yet `verify_chain()` authenticates source manifests and event rows, not gap-history transitions.

AION's own independent review marked this issue open.

### Artifact: AION-GAP-INTEGRITY-v1

```text
Every source_gap_history transition that can influence an as-of frame MUST
participate in deterministic integrity verification.

For transition i:

canonical_gap_i = {
    source_id,
    available_ns,
    state,
    previous_sequence,
    observed_sequence
}

gap_hash_i = SHA256(canonical({
    previous: gap_hash_(i-1),
    transition: canonical_gap_i
}))

Requirements:
1. gap transitions remain append-only.
2. ordering deterministic by ledger position.
3. verify_chain() recomputes every gap transition hash.
4. any row mutation, deletion, insertion/reordering, or indexed-value mismatch MUST fail verification.
5. gaps_asof() may only consume transitions belonging to verified ledger.
6. frozen replay retains gap_ledger_cutoff semantics.
7. integrity failure must fail closed, not degrade into partial quality and continue.
8. execution_authorized remains false.
```

Required regressions:

```python
def test_gap_history_tamper_breaks_integrity_verification():
    # seq=1 then seq=3 => persisted gap
    # verify_chain succeeds before tampering
    # mutate a stored gap transition outside normal append-only triggers
    # REQUIRED: verify_chain raises integrity error
    ...
```

Also mutate a historical `recovered` transition when the current active gap table is empty.

---

## 3. ARGUS

Status: **PARTIAL / LIVE IMPLEMENTATION UNAVAILABLE**

AION saved code-atlas evidence describes ARGUS as the owner of authenticated/validated microstructure semantics, while AION supplies ordered evidence/provenance. The current ARGUS working tree was not accessible.

### Boundary defect discovered in AION federation

AION currently exports:

```python
"source_hashes": frame["evidence_hashes"]
```

but `frame["evidence_hashes"]` contains event hashes, not source-manifest hashes.

That conflates event identity with source identity exactly at the ARGUS provenance boundary.

### Artifact: ARGUS-PROVENANCE-ADMISSION-v1

```text
ARGUS MUST NOT interpret legacy aion-evidence-v1 source_hashes
as source-manifest identity.

Admissible microstructure packets must separate:

event_hashes:
    immutable hashes of frame observations

source_manifests:
    source_id
    source_manifest_hash
    raw_source_sha256
    provider/origin
    representation_id
    instrument identity
    max_evidence_tier
    sequence_policy
    adapter_id/version
    semantic_review_status

microstructure_state:
    latest_sequence
    gap_state
    recovery_state
    freshness_state
    correction_policy

Unknown/legacy provenance semantics => reject/fail closed.
Candle/proxy evidence cannot become TRUE_TRADE/TRUE_DEPTH.
Synthetic evidence remains research-only.
execution_authorized must remain false.
```

Proof obligation: recover/pin the current ARGUS repo and implement/retest ingress rejection for ambiguous provenance and unreviewed venue semantics.

---

## 4. ATHENA

Status: **PARTIAL / LIVE IMPLEMENTATION UNAVAILABLE**

AION saved code-atlas evidence establishes ATHENA's boundary as inferred world state, uncertainty, advisory routing, risk, and abstention. AION supplies reproducible evidence; ATHENA does not own source reconstruction or order execution.

### Boundary defect: flow aggregation erases uncertainty-relevant lineage

AION observations carry:
- `source_id`
- `event_ns`
- `available_ns`
- `ingested_ns`
- `event_hash`
- `evidence_tier`
- `quality_flags`

But derived `flow[ticker]` aggregates collapse trades into buy/sell/unknown/delta/count and discard the individual contributor lineage before export to ATHENA.

Therefore ATHENA cannot fully distinguish equal numerical aggregates with different source quality/latency/provenance.

### Artifact: ATHENA-UNCERTAINTY-LINEAGE-v1

```text
Any AION-derived state supplied to ATHENA MUST retain enough contributor
lineage for ATHENA to make uncertainty and abstention decisions without
reconstructing hidden source state.

For every aggregated signal retain:

aggregate:
    symbol
    buy
    sell
    unknown
    delta
    observation_count

contributors[]:
    source_id
    event_hash
    event_ns
    available_ns
    evidence_tier
    quality_flags

Rules:
1. aggregation must not erase provenance relevant to uncertainty.
2. incomplete lineage can never produce more authority than complete lineage.
3. missing/stale/conflicting/synthetic/degraded evidence may raise uncertainty or force abstention; it may never lower uncertainty.
4. missing_true_trades=false means only eligible trade evidence exists; it does not mean complete market coverage.
5. unknown aggressor volume stays explicit.
6. synthetic/scenario evidence cannot increase empirical confidence.
7. legacy untraceable aggregates are supervisory-uncertain by construction.
8. no order authority is granted.
```

Proof obligation: recover/pin ATHENA and prove degraded or lineage-incomplete evidence never decreases uncertainty or increases advisory authority.

---

## 5. DAEDALUS

Status: **VERIFIED BOUNDARY / OPEN DEFECT**

Canonical evidence:
- `reppiks490/daedalus-research-os`
- `74ad94149b02ddd3f69d535ee5fdc00c1fdbe096`

DAEDALUS owns research discovery, causal feature construction, development-vs-protected evidence separation, holdout budget/ledger, adversarial validation, promotion gates, experiment memory, and research-only candidate export.

Repository checkpoint at the pinned commit records 59 tests and static audit results. Those are repository-recorded results; this ChatGPT pass did not rerun them.

### Open defect: protected holdout identity is tied to full-file SHA, not stable source lineage

The ledger key uses:
- `source_sha256`
- `protocol_hash`
- `holdout_start`
- `holdout_end`

If a logical source is appended/corrected, the full-file SHA changes. A descendant snapshot can therefore be treated as a new source even though part of its history overlaps a previously exposed protected tail.

Because current feature loading uses snapshot-local row positions, a previously protected historical interval can silently move into later development evidence.

### Artifact: DAEDALUS-PROTECTED-LINEAGE-v4

```text
Every protected exposure MUST be associated with both:

1. stable logical source lineage
2. immutable dataset snapshot

Required identifiers:
source_lineage_id
snapshot_sha256
protocol_hash
holdout_start_position
holdout_end_position
snapshot_row_count
lineage_relation
execution_authorized = false

lineage_relation:
    SAME_SNAPSHOT
    APPEND_ONLY_DESCENDANT
    MUTATED_OR_REORDERED
    UNKNOWN

Invariant:
Previously exposed protected observations MUST NEVER silently enter
development evidence for a descendant snapshot of the same logical source.
```

Required regressions:

```python
def test_appended_snapshot_cannot_recycle_old_holdout_into_development():
    ...
```

```python
def test_mutated_descendant_requires_reviewed_lineage_mapping():
    ...
```

For append-only descendants, ancestry must be verified rather than inferred by filename/path. Mutated/reordered/unknown ancestry fails closed pending reviewed mapping.

---

## 6. ORACLE

Status: **UNVERIFIED**

No canonical ORACLE repository, handoff, code-atlas entry, or ownership statement was found in accessible repository/library evidence. Responsibility must not be inferred from the name.

### Artifact: ORACLE-CANONICAL-ADMISSION-v1

```text
ORACLE MUST remain integration-ineligible until a canonical evidence bundle
establishes:

1. canonical_repository
2. immutable_revision
3. responsibility_statement
4. owned_input_contracts
5. owned_output_contracts
6. sibling_exclusion_boundaries
7. temporal_semantics
8. provenance_semantics
9. uncertainty/failure semantics
10. deterministic_replay contract
11. execution_authorized = false
12. regression tests

Missing responsibility or ownership proof => no inferred function/adapters.
Ambiguous schema/version => reject integration.
Unknown uncertainty => authority cannot increase.
ORACLE_STATE != VERIFIED => cannot affect qualification/execution/routing authority.
```

Proof obligation: locate authoritative ORACLE evidence before any implementation/integration work.

---

# Cross-subsystem rule

A subsystem being named in a diagram, prompt, chat, or configuration is **not** evidence that its implementation/contract exists.

For all six systems:

```text
MISSING OR AMBIGUOUS CANONICAL EVIDENCE
=> UNVERIFIED
=> NO AUTHORITY
=> NO INFERRED ADAPTER
=> NO SILENT FALLBACK
=> NO MATURITY PROMOTION
```

This rule is intentional. It prevents the integration layer from manufacturing system boundaries that repository evidence does not support.
