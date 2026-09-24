# OMNIVISION v2 Stage 1 Control Plane Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Stage 1 epistemic control plane that version-governs every source capability, preserves end-to-end provenance as an immutable DAG, records every meaningful research attempt in a search-aware trial ledger, and admits evidence only through a relevance- and capability-aware gateway.

**Architecture:** Stage 1 adds three tightly coupled but separately testable control-plane subsystems around the already-verified OMNIVISION foundation: immutable source capability versions, an append-only provenance DAG, and an append-only trial ledger. A governed evidence gateway composes them with the existing `AdvisoryLedger` without adding any provider adapter or live execution authority. The existing evidence ledger remains the immutable raw evidence store; the new control database records governance facts and lineage, and a governed projection refuses to treat an event as accepted OMNIVISION evidence unless its admission/provenance proof exists.

**Tech Stack:** Python 3.10+ standard library, dataclasses, SQLite, SHA-256 canonical JSON identities, pytest, existing `AdvisoryLedger`, existing OMNIVISION contracts, existing `research.py` holdout ledger. No new runtime dependency.

**Spec:** `docs/superpowers/specs/2026-09-24-omnivision-epistemic-control-plane-v2-design.md`

## Global Constraints

- `execution_authorized=false` remains invariant for every OMNIVISION artifact and Stage 1 record.
- No Pulse rewrite.
- No external provider adapter is implemented or wired in Stage 1.
- No autonomous credential acquisition, secret storage, sandbox escape, access-control bypass, stealth persistence, unauthorized access, or prohibited scraping.
- No fabricated observations, publication times, receipt times, revisions, source availability, source independence, trial outcomes, or lineage.
- Inputs must be public, licensed, connected, or explicitly user-authorized before a capability can become admissible.
- Reachability is not relevance; a syntactically valid source may still be inadmissible.
- Source outage, quota exhaustion, rate limiting, entitlement failure, and source-policy blocking remain distinct states.
- A later source-health state never rewrites a historical capability state or previously accepted observation.
- Opinion, media, attention, analyst rank, and aggregate research products never silently become primary factual world state.
- Two vendors that share an upstream source do not count as independent confirmations.
- Current data is never backfilled into a historical decision timestamp unless availability is proven.
- The existing `AdvisoryLedger` remains immutable evidence storage and source/URL/timing enforcement; Stage 1 does not weaken it.
- The existing `research.py` holdout ledger remains the authority for holdout consumption; a new dataset hash or Stage 1 trial ID cannot mint a fresh holdout.
- Stage 1 records search history; it does not yet implement Deflated Sharpe Ratio, PBO, FDR, calibration, regime intelligence, causal identification, source adapters, or proof-carrying candidate promotion.
- Owner-hard repository rules remain authoritative.
- TDD is mandatory: each behavior-changing task begins with a test that fails for the intended reason.
- No test may be weakened, deleted, skipped, or xfailed merely to obtain green.
- Final completion requires fresh GitHub Actions evidence from the native Linux/Windows workflow and the OMNIVISION Python 3.10–3.13 matrix.

## Review Focus

1. **Historical capability integrity:** a source can become rate-limited, blocked, stale, or disabled later without retroactively changing the capability state visible at an earlier decision timestamp.
2. **Semantic firewall:** a schema-valid event from an `analyst_opinion`, `media`, `aggregator`, or `negative_control` capability cannot enter the factual `world_state` path merely because its payload resembles a `WorldEvent`.
3. **Shared-upstream duplication:** two vendors declaring the same upstream source identity must be recognized as non-independent; adding the second vendor cannot create a false independence count.
4. **Lineage completeness and invalidation:** every governed observation must trace back through a capability version and raw evidence node, and invalidating a load-bearing ancestor must make every downstream dependent discoverable without deleting history.
5. **Search-history honesty:** failed, rejected, deferred, cancelled, and successful trials all count within their hypothesis family; dataset/config changes cannot erase earlier attempts or bypass the existing holdout-consumption rule.

---

## Stage 1 File Map

**Create**
- `icarus_engine/omnivision/identity.py` — dependency-light canonical JSON/hash helpers and shared bounded identity validators for Stage 1 records.
- `icarus_engine/omnivision/capabilities.py` — immutable `SourceCapability`, strict vocabularies, expiry/review semantics, purpose/role firewall, upstream independence helpers.
- `icarus_engine/omnivision/provenance.py` — immutable `ProvenanceNode`, `ProvenanceEdge`, allowed node/edge classes, deterministic IDs.
- `icarus_engine/omnivision/trials.py` — immutable `TrialRecord`, split definitions, trial/family/search metadata, terminal-state rules.
- `icarus_engine/omnivision/control_store.py` — append-only SQLite storage for capability versions, provenance nodes/edges, admissions, invalidations, and trials; as-of queries and recursive traversal.
- `icarus_engine/omnivision/gateway.py` — governed `EvidenceGateway` that checks capability/relevance/timing, delegates raw evidence ingestion to `AdvisoryLedger`, writes admission/provenance, and provides governed projection.
- `tests_engine/test_omnivision_capabilities.py`
- `tests_engine/test_omnivision_provenance.py`
- `tests_engine/test_omnivision_trials.py`
- `tests_engine/test_omnivision_gateway.py`
- `tests_engine/test_omnivision_stage1_integration.py`
- `docs/audits/2026-09-24-omnivision-v2-stage1-audit.md` — created during execution, finalized only after runtime verification.

**Modify**
- `icarus_engine/omnivision/__init__.py` — export only stable Stage 1 public contracts.
- `.github/workflows/omnivision-stage0.yml` — retain the verified matrix but add Stage 1 test modules to the focused regression command; workflow name may remain unchanged to preserve run continuity.
- `.icarus_loop/state.json` — Stage 1 implementation checkpoint only after final runtime verification.

**Read / integrate without ownership transfer**
- `icarus_engine/advisory.py` — raw immutable evidence ledger; Stage 1 uses its public methods and does not reach into private SQLite tables.
- `icarus_engine/research.py` — existing holdout consumption remains authoritative.
- `icarus_engine/world_state.py` — governed projection returns existing `Observation` objects.
- `icarus_engine/omnivision/contracts.py` — existing `WorldEvent` and `observation_from_event`.
- `icarus_engine/omnivision/ledger_bridge.py` — remains available as a low-level foundation bridge; Stage 1 adds a governed path rather than silently changing its semantics.
- `icarus_engine/omnivision/candidates.py` — no Stage 1 promotion rewrite; proof-carrying candidate enforcement is Stage 6.

**Forbidden Stage 1 changes**
- `icarus_engine/strategy/pulse.py`
- broker/order submission modules
- live bridge execution configuration
- provider credentials or environment secret handling
- Stage 2+ calibration/regime/causal/adapter/governor implementations

## Knowledge Delta by Path

### Batch A — deterministic identities + capability governance
- Code: `identity.py`, `capabilities.py`, capability portion of `control_store.py`.
- Tests: `test_omnivision_capabilities.py`.
- Documentation: Stage 1 audit records exact capability-state semantics and negative-control firewall.
- Rules: no new global owner rule; this batch operationalizes already-approved v2 source-admission rules.
- Context/memory: `.icarus_loop/state.json` changes only at final Stage 1 checkpoint.

### Batch B — provenance DAG
- Code: `provenance.py`, provenance/invalidation portion of `control_store.py`.
- Tests: `test_omnivision_provenance.py`.
- Documentation: Stage 1 audit records lineage/invalidation invariants.
- Rules: no new external adapter policy.
- Context/memory: no separate memory artifact; GitHub code/tests/audit are authoritative.

### Batch C — search-aware trial accounting
- Code: `trials.py`, trial portion of `control_store.py`.
- Tests: `test_omnivision_trials.py` plus existing `test_research.py` regressions.
- Documentation: Stage 1 audit explicitly distinguishes trial accounting from the existing holdout authorization ledger.
- Rules: dataset hashes remain evidence, never fresh-holdout authorization keys.

### Batch D — governed evidence gateway
- Code: `gateway.py`, stable exports in `__init__.py`.
- Tests: `test_omnivision_gateway.py`, `test_omnivision_stage1_integration.py`.
- Documentation: Stage 1 audit records partial-write/reconciliation semantics.
- Rules: a raw ledger event without a completed Stage 1 admission record is not a governed OMNIVISION observation.

### Batch E — verification and checkpoint
- Code: CI focused test list only.
- Tests: all `tests_engine`.
- Documentation: completed Stage 1 audit.
- Context/memory: `.icarus_loop/state.json` records exact run IDs, commit, findings, residual Stage 2+ work, and next allowed action.

## Locked Stage 1 Interfaces

The following names and shapes are fixed by this plan so tasks can be executed independently without inventing neighboring APIs.

### Canonical identity

```python
# icarus_engine/omnivision/identity.py
def canonical_json(value) -> str: ...
def canonical_hash(value) -> str: ...
def identity(value: str, name: str) -> str: ...
def sha256_hex(value: str, name: str) -> str: ...
```

These helpers are Stage 1-local. They do not refactor `advisory.py`, `world_state.py`, or existing foundation modules during this stage.

### Source capability

```python
@dataclass(frozen=True)
class SourceCapability:
    source_id: str
    provider: str
    domain_classes: tuple[str, ...]
    access_class: str
    epistemic_role: str
    auth_mode: str
    entitlement_state: str
    health_state: str
    rate_limit_state: str
    cost_class: str
    reliability_evidence: tuple[str, ...]
    timing_semantics: str
    revision_semantics: str
    freshness_policy: str
    observed_at: int
    available_at: int
    valid_until: int | None
    review_after: int | None
    allowed_assets: tuple[str, ...]
    allowed_entities: tuple[str, ...]
    forbidden_uses: tuple[str, ...]
    upstream_source_ids: tuple[str, ...]

    @property
    def version_id(self) -> str: ...
```

Strict vocabularies:

```python
ACCESS_CLASSES = {"public", "licensed", "connected", "user_authorized"}
EPISTEMIC_ROLES = {
    "primary_observation",
    "aggregator",
    "analyst_opinion",
    "media",
    "derived_market_data",
    "negative_control",
}
HEALTH_STATES = {
    "healthy",
    "degraded",
    "rate_limited",
    "quota_exhausted",
    "blocked_by_source_policy",
    "entitlement_missing",
    "schema_changed",
    "stale",
    "disabled",
}
ENTITLEMENT_STATES = {"not_required", "active", "missing", "expired", "unknown"}
RATE_LIMIT_STATES = {"normal", "near_limit", "rate_limited", "quota_exhausted", "unknown"}
COST_CLASSES = {"zero", "low", "medium", "high", "metered", "unknown"}
PURPOSES = {
    "factual_world_state",
    "aggregated_research",
    "opinion_signal",
    "media_signal",
    "negative_control",
}
```

Purpose/role admission matrix:

```python
ROLE_PURPOSES = {
    "primary_observation": {"factual_world_state"},
    "derived_market_data": {"factual_world_state"},
    "aggregator": {"aggregated_research"},
    "analyst_opinion": {"opinion_signal"},
    "media": {"media_signal"},
    "negative_control": {"negative_control"},
}
```

No role is silently coerced into another role.

### Provenance

```python
@dataclass(frozen=True)
class ProvenanceNode:
    node_type: str
    external_id: str
    body_hash: str
    as_of: int
    run_id: str
    metadata: Mapping[str, object]

    @property
    def node_id(self) -> str: ...

@dataclass(frozen=True)
class ProvenanceEdge:
    edge_type: str
    source_node_id: str
    target_node_id: str
    run_id: str
    as_of: int
    transformation_id: str
    evidence_hashes: tuple[str, ...]
    code_hash: str | None
    config_hash: str | None

    @property
    def edge_id(self) -> str: ...
```

Node types exactly:
`SourceCapability`, `RawEvidence`, `NormalizedObservation`, `DerivedFeature`, `LatentEstimate`, `DatasetSnapshot`, `Hypothesis`, `Trial`, `ValidationResult`, `Candidate`, `IntegrationDecision`.

Edge types exactly:
`produced_by`, `normalized_from`, `derived_from`, `contradicts`, `supersedes`, `tests`, `falsifies`, `supports`, `duplicates`, `depends_on`, `invalidates`.

### Trial accounting

```python
@dataclass(frozen=True)
class TrialRecord:
    trial_id: str
    hypothesis_id: str
    hypothesis_family_id: str
    parent_trial_ids: tuple[str, ...]
    generation_method: str
    feature_config: Mapping[str, object]
    dataset_snapshot_hashes: tuple[str, ...]
    train_start: int
    train_end: int
    validation_start: int
    validation_end: int
    holdout_start: int | None
    holdout_end: int | None
    code_hash: str
    config_hash: str
    decision_at: int
    evaluation_metrics: Mapping[str, object]
    cost_assumptions: Mapping[str, object]
    result_status: str
    rejection_reason: str | None
    multiple_testing_family_id: str
    holdout_claim_ref: str | None
```

Terminal result statuses:
`complete`, `rejected`, `deferred`, `failed`, `cancelled`.

A `TrialRecord` records history; it never authorizes holdout use and never grants execution.

### Control store

```python
class ControlPlaneStore:
    def __init__(self, path): ...
    def put_capability(self, capability: SourceCapability) -> str: ...
    def capability_as_of(self, source_id: str, as_of: int) -> SourceCapability | None: ...
    def capability_versions(self, source_id: str) -> tuple[SourceCapability, ...]: ...

    def put_node(self, node: ProvenanceNode) -> str: ...
    def put_edge(self, edge: ProvenanceEdge) -> str: ...
    def node(self, node_id: str) -> ProvenanceNode | None: ...
    def ancestors(self, node_id: str) -> tuple[str, ...]: ...
    def descendants(self, node_id: str) -> tuple[str, ...]: ...
    def invalidate(self, node_id: str, *, reason: str, run_id: str, as_of: int) -> tuple[str, ...]: ...
    def invalidated(self, node_id: str, as_of: int) -> bool: ...

    def put_trial(self, trial: TrialRecord) -> str: ...
    def trial(self, trial_id: str) -> TrialRecord | None: ...
    def trials_for_family(self, family_id: str) -> tuple[TrialRecord, ...]: ...
    def trial_family_count(self, family_id: str) -> int: ...

    def put_admission(self, *, event_id: str, capability_version_id: str,
                      raw_node_id: str, run_id: str, admitted_at: int,
                      purpose: str) -> str: ...
    def admission_for_event(self, event_id: str, *, as_of: int) -> Mapping[str, object] | None: ...
```

### Governed gateway

```python
class EvidenceGateway:
    def __init__(self, ledger: AdvisoryLedger, control: ControlPlaneStore): ...

    def admit_world_event(
        self,
        capability: SourceCapability,
        event: WorldEvent,
        *,
        purpose: str,
        now: int | float | None = None,
        run_id: str,
    ) -> Mapping[str, object]: ...

    def governed_observations(
        self,
        asset: str,
        as_of: str,
    ) -> tuple[Observation, ...]: ...
```

The gateway is local and deterministic. It does not call a provider.

---

### Task 1: Shared Identity and Immutable Capability Contract

**Files:**
- Create: `icarus_engine/omnivision/identity.py`
- Create: `icarus_engine/omnivision/capabilities.py`
- Create: `tests_engine/test_omnivision_capabilities.py`
- Modify: `icarus_engine/omnivision/__init__.py`

**Interfaces:**
- Consumes: Python primitive values only.
- Produces: `SourceCapability`, `capability_is_current()`, `capability_allows()`, `independence_key()`, and Stage 1 canonical identity helpers used by Tasks 2–7.

- [ ] **Step 1: Write canonical-identity tests**

Add tests:

```python
from icarus_engine.omnivision.identity import canonical_hash, canonical_json


def test_canonical_hash_is_order_independent_for_json_objects():
    left = {"b": 2, "a": 1}
    right = {"a": 1, "b": 2}
    assert canonical_json(left) == canonical_json(right)
    assert canonical_hash(left) == canonical_hash(right)


def test_canonical_json_rejects_nonfinite_numbers():
    import math
    import pytest

    with pytest.raises(ValueError, match="finite"):
        canonical_json({"x": math.inf})
```

Use bounded JSON validation equivalent in safety to existing repository canonicalization: finite numbers, string keys, bounded nesting/collection sizes, deterministic ASCII JSON, no NaN.

- [ ] **Step 2: Write capability-vocabulary and deterministic-version tests**

Use a helper fixture:

```python
def healthy_source(**overrides):
    values = dict(
        source_id="twelve_data",
        provider="TwelveData",
        domain_classes=("market_quote",),
        access_class="connected",
        epistemic_role="derived_market_data",
        auth_mode="connector",
        entitlement_state="active",
        health_state="healthy",
        rate_limit_state="normal",
        cost_class="metered",
        reliability_evidence=("design-cycle-2026-09-24",),
        timing_semantics="provider_timestamp_plus_receipt",
        revision_semantics="snapshot_replaced_by_newer_snapshot",
        freshness_policy="max_age_60s",
        observed_at=100,
        available_at=101,
        valid_until=1000,
        review_after=500,
        allowed_assets=("NQ",),
        allowed_entities=("QQQ",),
        forbidden_uses=("live_order_execution",),
        upstream_source_ids=("nasdaq_venue_data",),
    )
    values.update(overrides)
    return SourceCapability(**values)
```

Tests:

```python
def test_capability_version_is_deterministic_and_changes_with_state():
    first = healthy_source()
    same = healthy_source()
    later = healthy_source(
        health_state="rate_limited",
        rate_limit_state="rate_limited",
        observed_at=200,
        available_at=201,
    )
    assert first.version_id == same.version_id
    assert first.version_id != later.version_id
```

- [ ] **Step 3: Write strict state/access/role tests**

Parametrize invalid:
- access class `"private_unknown"`;
- role `"fact"`;
- health `"error"`;
- entitlement `"maybe"`;
- rate limit `"throttledish"`;
- cost class `"free-ish"`;
- `available_at < observed_at`;
- duplicate assets/entities/upstream IDs;
- empty domain classes;
- `review_after < available_at`;
- `valid_until <= available_at`.

Each must raise `ValueError` before storage.

- [ ] **Step 4: Write purpose firewall tests**

```python
import pytest
from icarus_engine.omnivision.capabilities import capability_allows


def test_opinion_cannot_be_admitted_as_factual_world_state():
    capability = healthy_source(epistemic_role="analyst_opinion")
    assert capability_allows(
        capability,
        purpose="opinion_signal",
        asset="NQ",
        entity="QQQ",
        domain="market_quote",
        as_of=200,
    )
    with pytest.raises(ValueError, match="epistemic role"):
        capability_allows(
            capability,
            purpose="factual_world_state",
            asset="NQ",
            entity="QQQ",
            domain="market_quote",
            as_of=200,
        )
```

Add equivalent rejection tests for `media`, `aggregator`, and `negative_control` in the factual path.

- [ ] **Step 5: Write current/expired/health behavior tests**

```python
def test_capability_must_be_known_current_and_healthy_enough_for_admission():
    capability = healthy_source()
    assert capability_allows(
        capability,
        purpose="factual_world_state",
        asset="NQ",
        entity="QQQ",
        domain="market_quote",
        as_of=200,
    )

    with pytest.raises(ValueError, match="expired"):
        capability_allows(
            capability,
            purpose="factual_world_state",
            asset="NQ",
            entity="QQQ",
            domain="market_quote",
            as_of=1001,
        )
```

Admission-blocking health states:
`rate_limited`, `quota_exhausted`, `blocked_by_source_policy`, `entitlement_missing`, `schema_changed`, `stale`, `disabled`.

`degraded` remains admissible only when entitlement/rate state and freshness are otherwise valid; its degraded state remains in provenance.

- [ ] **Step 6: Write upstream-independence tests**

```python
from icarus_engine.omnivision.capabilities import independence_key


def test_shared_upstream_sources_are_not_independent():
    left = healthy_source(
        source_id="vendor_a",
        upstream_source_ids=("exchange_x",),
    )
    right = healthy_source(
        source_id="vendor_b",
        upstream_source_ids=("exchange_x",),
    )
    assert independence_key(left) == independence_key(right)
```

For multiple upstream IDs, the helper must return a sorted tuple, never a count. Empty upstream IDs fall back to a source-specific key and must carry a quality flag in future adapter work; Stage 1 does not infer shared ancestry when it is unknown.

- [ ] **Step 7: Implement the minimal contracts**

Implementation requirements:
- frozen dataclass;
- all tuple fields must be actual tuples;
- tuple values non-empty where required and unique;
- all timestamps exact non-negative integers;
- `version_id = canonical_hash(asdict(self))`;
- `capability_allows` validates purpose, role, allowed asset/entity/domain, health, entitlement, rate limit, expiry/review state, and forbidden use;
- `capability_allows` returns `True` only after every gate passes;
- it raises descriptive `ValueError` on closed gates.

- [ ] **Step 8: Run scoped tests**

```bash
python -m pytest tests_engine/test_omnivision_capabilities.py -q
```

Expected: PASS.

- [ ] **Step 9: Run foundation regressions**

```bash
python -m pytest   tests_engine/test_omnivision_contracts.py   tests_engine/test_omnivision_stage0_temporal.py   tests_engine/test_omnivision_stage0_boundaries.py   -q
```

Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add   icarus_engine/omnivision/identity.py   icarus_engine/omnivision/capabilities.py   icarus_engine/omnivision/__init__.py   tests_engine/test_omnivision_capabilities.py
git commit -m "Codex: add OMNIVISION source capability contract"
```

---

### Task 2: Append-Only Capability Version Store and Historical State

**Files:**
- Create: `icarus_engine/omnivision/control_store.py`
- Modify: `tests_engine/test_omnivision_capabilities.py`

**Interfaces:**
- Consumes: `SourceCapability`.
- Produces: `ControlPlaneStore.put_capability()`, `capability_as_of()`, `capability_versions()`.
- Later tasks add tables/methods to this same focused store without changing capability semantics.

- [ ] **Step 1: Write immutable-version persistence tests**

```python
from icarus_engine.omnivision.control_store import ControlPlaneStore


def test_capability_versions_are_append_only_and_asof(tmp_path):
    store = ControlPlaneStore(tmp_path / "control.sqlite3")
    healthy = healthy_source(observed_at=100, available_at=101)
    limited = healthy_source(
        health_state="rate_limited",
        rate_limit_state="rate_limited",
        observed_at=200,
        available_at=201,
    )

    assert store.put_capability(healthy) == healthy.version_id
    assert store.put_capability(limited) == limited.version_id

    assert store.capability_as_of("twelve_data", 150).version_id == healthy.version_id
    assert store.capability_as_of("twelve_data", 250).version_id == limited.version_id
    assert [c.version_id for c in store.capability_versions("twelve_data")] == [
        healthy.version_id,
        limited.version_id,
    ]
```

- [ ] **Step 2: Write no-retroactive-outage test**

```python
def test_later_outage_does_not_rewrite_past_capability(tmp_path):
    store = ControlPlaneStore(tmp_path / "control.sqlite3")
    healthy = healthy_source(observed_at=100, available_at=100)
    blocked = healthy_source(
        health_state="blocked_by_source_policy",
        observed_at=300,
        available_at=300,
    )
    store.put_capability(healthy)
    store.put_capability(blocked)

    assert store.capability_as_of("twelve_data", 200).health_state == "healthy"
    assert store.capability_as_of("twelve_data", 400).health_state == "blocked_by_source_policy"
```

- [ ] **Step 3: Write future-knowledge rejection test**

A capability version with `available_at=500` must not appear in `capability_as_of(source_id, 499)`, even if its `observed_at` is earlier.

- [ ] **Step 4: Write same-version idempotence / conflicting-ID tests**

- inserting the exact same `version_id` and canonical body twice is idempotent;
- no SQL `UPDATE` or `DELETE` operation may be exposed;
- SQLite triggers reject direct updates/deletes to capability rows;
- a body digest mismatch raises `ValueError`.

- [ ] **Step 5: Implement initial SQLite schema**

Use:

```sql
CREATE TABLE IF NOT EXISTS capability_versions (
    version_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    available_at INTEGER NOT NULL,
    body TEXT NOT NULL,
    digest TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS capability_source_asof
ON capability_versions(source_id, available_at, rowid);
```

If SQLite rejects indexing `rowid` in this environment, index only `(source_id, available_at)`; do not change query semantics.

Create immutable triggers:

```sql
CREATE TRIGGER IF NOT EXISTS capability_versions_no_update
BEFORE UPDATE ON capability_versions
BEGIN SELECT RAISE(ABORT, 'capability_versions is immutable'); END;

CREATE TRIGGER IF NOT EXISTS capability_versions_no_delete
BEFORE DELETE ON capability_versions
BEGIN SELECT RAISE(ABORT, 'capability_versions is immutable'); END;
```

All deserialized bodies must be reconstructed through `SourceCapability(**body)` and re-hashed before returning.

- [ ] **Step 6: Run scoped tests**

```bash
python -m pytest tests_engine/test_omnivision_capabilities.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add   icarus_engine/omnivision/control_store.py   tests_engine/test_omnivision_capabilities.py
git commit -m "Codex: persist versioned OMNIVISION source capabilities"
```

---

### Task 3: Provenance DAG Contracts, Traversal, Duplication, and Invalidation

**Files:**
- Create: `icarus_engine/omnivision/provenance.py`
- Create: `tests_engine/test_omnivision_provenance.py`
- Modify: `icarus_engine/omnivision/control_store.py`
- Modify: `icarus_engine/omnivision/__init__.py`

**Interfaces:**
- Consumes: deterministic external IDs and hashes from evidence/capability/trial layers.
- Produces: immutable `ProvenanceNode`, `ProvenanceEdge`, node/edge persistence, ancestors, descendants, duplicate relationships, and append-only recursive invalidation closure.

- [ ] **Step 1: Write deterministic node/edge tests**

```python
def test_provenance_node_and_edge_ids_are_deterministic():
    node = ProvenanceNode(
        node_type="RawEvidence",
        external_id="a" * 64,
        body_hash="b" * 64,
        as_of=100,
        run_id="run-1",
        metadata={"source_id": "provider"},
    )
    assert node.node_id == ProvenanceNode(**asdict(node)).node_id

    edge = ProvenanceEdge(
        edge_type="produced_by",
        source_node_id=node.node_id,
        target_node_id="c" * 64,
        run_id="run-1",
        as_of=100,
        transformation_id="gateway-v1",
        evidence_hashes=("a" * 64,),
        code_hash=None,
        config_hash=None,
    )
    assert edge.edge_id == ProvenanceEdge(**asdict(edge)).edge_id
```

- [ ] **Step 2: Write strict type vocabulary tests**

Reject unknown node types and edge types. Reject:
- self-edge;
- malformed SHA-256 node IDs;
- duplicate evidence hashes;
- negative/non-integer `as_of`;
- empty run/transformation IDs;
- malformed optional code/config hashes.

- [ ] **Step 3: Write DAG integrity and cycle tests**

```python
def test_provenance_store_rejects_cycle(tmp_path):
    store = ControlPlaneStore(tmp_path / "control.sqlite3")
    a = put_node(store, "RawEvidence", "raw")
    b = put_node(store, "NormalizedObservation", "normalized")

    store.put_edge(edge("normalized_from", a, b))
    with pytest.raises(ValueError, match="cycle"):
        store.put_edge(edge("depends_on", b, a))
```

Direction convention is fixed:

```text
source_node_id -> target_node_id
ancestor/input  -> dependent/output
```

Therefore `ancestors(target)` walks incoming edges and `descendants(source)` walks outgoing edges.

- [ ] **Step 4: Write exact backwards/forwards tracing tests**

Build:
`SourceCapability -> RawEvidence -> NormalizedObservation -> Hypothesis -> Trial`.

Assert:
- ancestors of Trial return all four prior nodes exactly once;
- descendants of SourceCapability include every downstream node;
- traversal ordering is deterministic by `(distance, node_id)`.

- [ ] **Step 5: Write shared-upstream duplicate-edge test**

For two RawEvidence nodes originating from capabilities with the same `independence_key`, persist an explicit `duplicates` edge between their raw nodes. Assert traversal exposes it but does not merge/delete either node.

Stage 1 records the relationship; confidence adjustment remains Stage 2.

- [ ] **Step 6: Write recursive invalidation test**

```python
def test_invalidation_is_append_only_and_reaches_dependents(tmp_path):
    store = populated_dag(tmp_path)
    affected = store.invalidate(
        RAW_NODE_ID,
        reason="source revision invalidated load-bearing evidence",
        run_id="audit-1",
        as_of=500,
    )
    assert affected == tuple(sorted({RAW_NODE_ID, OBS_NODE_ID, HYP_NODE_ID, TRIAL_NODE_ID}))
    assert not store.invalidated(TRIAL_NODE_ID, 499)
    assert store.invalidated(TRIAL_NODE_ID, 500)
```

Invalidation does not mutate/delete nodes or edges. It appends immutable invalidation rows for the root and every current descendant.

- [ ] **Step 7: Implement provenance schema**

Required tables:

```sql
CREATE TABLE IF NOT EXISTS provenance_nodes (
    node_id TEXT PRIMARY KEY,
    node_type TEXT NOT NULL,
    as_of INTEGER NOT NULL,
    body TEXT NOT NULL,
    digest TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS provenance_edges (
    edge_id TEXT PRIMARY KEY,
    source_node_id TEXT NOT NULL,
    target_node_id TEXT NOT NULL,
    edge_type TEXT NOT NULL,
    as_of INTEGER NOT NULL,
    body TEXT NOT NULL,
    digest TEXT NOT NULL,
    FOREIGN KEY(source_node_id) REFERENCES provenance_nodes(node_id),
    FOREIGN KEY(target_node_id) REFERENCES provenance_nodes(node_id)
);

CREATE TABLE IF NOT EXISTS provenance_invalidations (
    invalidation_id TEXT PRIMARY KEY,
    node_id TEXT NOT NULL,
    root_node_id TEXT NOT NULL,
    as_of INTEGER NOT NULL,
    reason TEXT NOT NULL,
    run_id TEXT NOT NULL,
    body TEXT NOT NULL,
    digest TEXT NOT NULL,
    FOREIGN KEY(node_id) REFERENCES provenance_nodes(node_id)
);
```

Enable `PRAGMA foreign_keys=ON` on every connection.

Add immutable update/delete triggers to all three tables.

Cycle detection must run before edge insert by checking whether `target_node_id` can already reach `source_node_id`.

- [ ] **Step 8: Run scoped tests**

```bash
python -m pytest tests_engine/test_omnivision_provenance.py -q
```

Expected: PASS.

- [ ] **Step 9: Run existing provenance regressions**

```bash
python -m pytest   tests_engine/test_world_state.py   tests_engine/test_omnivision_bridge.py   tests_engine/test_omnivision_integration.py   tests_engine/test_advisory.py   -q
```

Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add   icarus_engine/omnivision/provenance.py   icarus_engine/omnivision/control_store.py   icarus_engine/omnivision/__init__.py   tests_engine/test_omnivision_provenance.py
git commit -m "Codex: add OMNIVISION provenance DAG and invalidation"
```

---

### Task 4: Search-Aware Trial Contracts and Family Accounting

**Files:**
- Create: `icarus_engine/omnivision/trials.py`
- Create: `tests_engine/test_omnivision_trials.py`
- Modify: `icarus_engine/omnivision/control_store.py`
- Modify: `icarus_engine/omnivision/__init__.py`

**Interfaces:**
- Consumes: immutable hypothesis IDs, dataset snapshot hashes, split boundaries, result summaries, and optional reference to an existing holdout claim.
- Produces: immutable `TrialRecord`, append-only trial persistence, family counts, parent lineage, and exact search history.
- Does **not** consume or authorize holdout intervals itself.

- [ ] **Step 1: Write trial validation tests**

A valid fixture:

```python
def trial(**overrides):
    values = dict(
        trial_id="trial-001",
        hypothesis_id="a" * 64,
        hypothesis_family_id="family-shipping-inflation",
        parent_trial_ids=(),
        generation_method="grid",
        feature_config={"lookback": 20},
        dataset_snapshot_hashes=("b" * 64,),
        train_start=100,
        train_end=199,
        validation_start=200,
        validation_end=299,
        holdout_start=300,
        holdout_end=399,
        code_hash="c" * 64,
        config_hash="d" * 64,
        decision_at=400,
        evaluation_metrics={"validation_score": 0.1},
        cost_assumptions={"commission": 2.0, "slippage_ticks": 1},
        result_status="rejected",
        rejection_reason="validation hurdle failed",
        multiple_testing_family_id="mtf-shipping-inflation",
        holdout_claim_ref=None,
    )
    values.update(overrides)
    return TrialRecord(**values)
```

Reject:
- overlapping/non-ordered train/validation/holdout intervals;
- malformed hashes;
- empty family/generation IDs;
- invalid result status;
- terminal rejected/failed/deferred trial with no reason;
- `complete` with a nonempty rejection reason;
- duplicate dataset hashes or parent IDs;
- self-parent;
- decision before the end of every evaluated interval;
- non-finite metric/cost JSON.

- [ ] **Step 2: Write all-outcomes-count test**

```python
def test_family_count_includes_failures_rejections_deferrals_and_success(tmp_path):
    store = ControlPlaneStore(tmp_path / "control.sqlite3")
    statuses = ["failed", "rejected", "deferred", "cancelled", "complete"]

    for index, status in enumerate(statuses):
        store.put_trial(trial(
            trial_id=f"trial-{index}",
            result_status=status,
            rejection_reason=None if status == "complete" else f"{status} reason",
        ))

    assert store.trial_family_count("family-shipping-inflation") == 5
    assert [t.result_status for t in store.trials_for_family("family-shipping-inflation")] == statuses
```

Sort trials by insertion/decision order plus trial ID deterministically.

- [ ] **Step 3: Write immutable trial-ID conflict test**

- exact same `trial_id` + body is idempotent;
- same `trial_id` with changed body raises;
- no update/delete APIs;
- direct SQL updates/deletes blocked by triggers.

- [ ] **Step 4: Write parent-lineage/cycle tests**

A child may name only existing parent trials in the same hypothesis family. Reject:
- missing parent;
- parent from another family;
- parent graph cycle.

- [ ] **Step 5: Write dataset-hash-does-not-reset-family test**

Two trials with different dataset snapshot hashes but the same hypothesis family and multiple-testing family must produce family count 2, not 1.

- [ ] **Step 6: Write holdout-authority separation test**

```python
def test_trial_store_does_not_authorize_holdout_reuse(tmp_path):
    store = ControlPlaneStore(tmp_path / "control.sqlite3")
    store.put_trial(trial(trial_id="trial-a", dataset_snapshot_hashes=("a" * 64,)))
    store.put_trial(trial(trial_id="trial-b", dataset_snapshot_hashes=("b" * 64,)))

    assert not hasattr(store, "claim_holdout")
```

The authoritative behavior remains tested in existing `tests_engine/test_research.py::test_selection_does_not_inspect_other_candidates_holdouts` and `test_old_validation_cannot_be_relabelled_as_holdout`.

- [ ] **Step 7: Implement trial persistence schema**

```sql
CREATE TABLE IF NOT EXISTS research_trials (
    trial_id TEXT PRIMARY KEY,
    family_id TEXT NOT NULL,
    multiple_testing_family_id TEXT NOT NULL,
    decision_at INTEGER NOT NULL,
    status TEXT NOT NULL,
    body TEXT NOT NULL,
    digest TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS research_trials_family
ON research_trials(family_id, decision_at, trial_id);
```

Add immutable update/delete triggers.

Store canonical body and digest; reconstruct and validate on read.

- [ ] **Step 8: Run trial and holdout regressions**

```bash
python -m pytest   tests_engine/test_omnivision_trials.py   tests_engine/test_research.py   -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add   icarus_engine/omnivision/trials.py   icarus_engine/omnivision/control_store.py   icarus_engine/omnivision/__init__.py   tests_engine/test_omnivision_trials.py
git commit -m "Codex: add search-aware OMNIVISION trial ledger"
```

---

### Task 5: Explicit Search-Result Recording Adapter Without Holdout Reauthorization

**Files:**
- Modify: `icarus_engine/omnivision/trials.py`
- Modify: `tests_engine/test_omnivision_trials.py`
- Read regression: `icarus_engine/research.py`, `tests_engine/test_research.py`

**Interfaces:**
- Consumes: one completed or interrupted `research.run_search()` output plus immutable hypothesis/family/code/config/dataset identities supplied by the caller.
- Produces: one `TrialRecord` per attempted parameter combination and terminal search outcome metadata.
- Does not call `_claim_holdout` or create holdout state.

Add:

```python
def trial_records_from_search(
    search_result: Mapping[str, object],
    *,
    hypothesis_id: str,
    hypothesis_family_id: str,
    multiple_testing_family_id: str,
    code_hash: str,
    config_hash: str,
) -> tuple[TrialRecord, ...]:
    ...
```

- [ ] **Step 1: Write failed-search preservation test**

Construct a minimal search-result mapping with:
- manifest windows/dataset hash;
- two attempted trials;
- one eligible false, one eligible true;
- terminal `status="complete"`;
- selected inputs.

Assert two TrialRecords are returned. The losing trial is not omitted.

- [ ] **Step 2: Write truncated/cancelled search preservation test**

For `status="cancelled"` and `search_truncated=True`, return every already-attempted trial and mark their result status consistently from recorded evidence; never fabricate unattempted combinations.

- [ ] **Step 3: Write no-holdout-minting test**

The adapter may copy the manifest's holdout interval and a caller-provided existing `holdout_claim_ref` only if present in the result evidence. It must not open the holdout ledger, call a private research helper, or synthesize a claim from dataset hash.

AST-test `trials.py` to reject references to `_claim_holdout`.

- [ ] **Step 4: Implement deterministic trial IDs**

For imported search trials, derive:

```python
trial_id = canonical_hash({
    "study_hash": search_result["study_hash"],
    "hypothesis_id": hypothesis_id,
    "hypothesis_family_id": hypothesis_family_id,
    "trial_index": index,
    "inputs": attempted_trial["inputs"],
})
```

The same frozen search result imports idempotently.

- [ ] **Step 5: Run scoped and research regressions**

```bash
python -m pytest   tests_engine/test_omnivision_trials.py   tests_engine/test_research.py   -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add   icarus_engine/omnivision/trials.py   tests_engine/test_omnivision_trials.py
git commit -m "Codex: bind research search history into OMNIVISION trials"
```

---

### Task 6: Governed Evidence Gateway and Admission Records

**Files:**
- Create: `icarus_engine/omnivision/gateway.py`
- Create: `tests_engine/test_omnivision_gateway.py`
- Modify: `icarus_engine/omnivision/control_store.py`
- Modify: `icarus_engine/omnivision/__init__.py`

**Interfaces:**
- Consumes: current `SourceCapability`, `WorldEvent`, `AdvisoryLedger`, `ControlPlaneStore`.
- Produces: immutable admission record, SourceCapability/RawEvidence provenance nodes and `produced_by` edge, plus governed observation projection.
- No network/provider call.

- [ ] **Step 1: Write happy-path admission test**

```python
def test_governed_world_event_requires_capability_and_provenance(tmp_path):
    ledger = AdvisoryLedger(
        tmp_path / "evidence.sqlite3",
        {"provider": ["provider.example"]},
    )
    control = ControlPlaneStore(tmp_path / "control.sqlite3")
    capability = factual_capability(source_id="provider")
    control.put_capability(capability)
    gateway = EvidenceGateway(ledger, control)

    admission = gateway.admit_world_event(
        capability,
        world_event(source="provider"),
        purpose="factual_world_state",
        now=200,
        run_id="ingest-run-1",
    )

    assert admission["event_id"]
    assert admission["capability_version_id"] == capability.version_id
    assert control.admission_for_event(admission["event_id"], as_of=200)
    observations = gateway.governed_observations("NQ", iso(200))
    assert observations
    assert {row.evidence_id for row in observations} == {admission["event_id"]}
```

- [ ] **Step 2: Write stale/unhealthy capability rejection tests**

Reject before `AdvisoryLedger.ingest_event` when capability at the decision time is:
- expired;
- review-overdue when policy requires review;
- disabled;
- blocked by source policy;
- entitlement missing;
- quota exhausted;
- rate limited;
- schema changed;
- stale.

After rejection, ledger event count remains unchanged.

- [ ] **Step 3: Write source/version binding test**

The supplied capability must equal `control.capability_as_of(capability.source_id, now)` by `version_id`. A historical or superseded capability object cannot be used for current admission.

- [ ] **Step 4: Write semantic firewall negative-control tests**

A valid `WorldEvent` from:
- `analyst_opinion`,
- `media`,
- `aggregator`,
- `negative_control`
must be rejected from `purpose="factual_world_state"` before raw evidence ingestion.

This is the executable analogue of the Cheat Database design-cycle negative control.

- [ ] **Step 5: Write partial-write safety test**

Simulate control-store admission/provenance failure after `AdvisoryLedger` accepts raw evidence.

Expected:
- raw ledger evidence may exist because the stores are intentionally isolated;
- `governed_observations()` excludes it because no complete admission record exists;
- retrying the exact deterministic event and control write may complete idempotently;
- no ungoverned event becomes visible through the governed path.

Do not implement a distributed transaction.

- [ ] **Step 6: Write admission provenance test**

For one admitted event, require:
- one SourceCapability node referencing `capability.version_id`;
- one RawEvidence node referencing ledger `event_id`;
- one `produced_by` edge SourceCapability -> RawEvidence;
- admission row binding event, capability version, raw node, run ID, purpose, admitted-at;
- every body/digest revalidates on read.

- [ ] **Step 7: Implement admission schema**

```sql
CREATE TABLE IF NOT EXISTS evidence_admissions (
    admission_id TEXT PRIMARY KEY,
    event_id TEXT NOT NULL UNIQUE,
    capability_version_id TEXT NOT NULL,
    raw_node_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    admitted_at INTEGER NOT NULL,
    purpose TEXT NOT NULL,
    body TEXT NOT NULL,
    digest TEXT NOT NULL
);
```

Add immutable update/delete triggers.

`admission_id = canonical_hash(canonical admission body)`.

- [ ] **Step 8: Implement gateway order**

The order is fixed:

```text
1. validate types
2. resolve current capability from ControlPlaneStore as-of now
3. require exact version match
4. capability_allows(... purpose="factual_world_state" ...)
5. ingest immutable raw evidence through AdvisoryLedger
6. create/put SourceCapability provenance node
7. create/put RawEvidence provenance node
8. put produced_by edge
9. put immutable admission record last
10. return admission
```

The admission record is the commit marker. Governed projection ignores raw events without it.

- [ ] **Step 9: Implement governed projection**

`governed_observations(asset, as_of)`:
- gets `AdvisoryLedger.events_as_of(asset, as_of)`;
- keeps only `world_state` events;
- requires an admission visible as-of the same cutoff;
- requires the associated capability version itself was available by admission time;
- rejects/skips an event if its raw provenance node is invalidated as-of the cutoff;
- calls existing `observation_from_event` for each value;
- preserves ledger event ID as evidence ID;
- deterministic sort identical to `ledger_observations`.

Historical health changes after admission do not erase a past accepted event. Explicit provenance invalidation does.

- [ ] **Step 10: Run gateway/advisory/temporal tests**

```bash
python -m pytest   tests_engine/test_omnivision_gateway.py   tests_engine/test_omnivision_capabilities.py   tests_engine/test_omnivision_provenance.py   tests_engine/test_omnivision_stage0_temporal.py   tests_engine/test_advisory.py   -q
```

Expected: PASS.

- [ ] **Step 11: Commit**

```bash
git add   icarus_engine/omnivision/gateway.py   icarus_engine/omnivision/control_store.py   icarus_engine/omnivision/__init__.py   tests_engine/test_omnivision_gateway.py
git commit -m "Codex: add governed OMNIVISION evidence gateway"
```

---

### Task 7: End-to-End Stage 1 Lineage, Duplicate-Source, and Search-History Proof

**Files:**
- Create: `tests_engine/test_omnivision_stage1_integration.py`
- Modify only if a RED test proves a defect: Stage 1 modules from Tasks 1–6.
- Do not modify provider adapters because none exist in Stage 1.

**Interfaces:**
- Consumes: `SourceCapability`, `ControlPlaneStore`, `EvidenceGateway`, existing world-state/hypothesis/falsification modules, `TrialRecord`.
- Produces: executable proof that the three Stage 1 control-plane subsystems compose without granting execution.

- [ ] **Step 1: Write factual governed path integration**

Build:

```text
SourceCapability
 -> EvidenceGateway
 -> AdvisoryLedger RawEvidence
 -> governed Observation
 -> WorldStateGraph
 -> Hypothesis
 -> TrialRecord
 -> Provenance Trial node
```

Assertions:
- one exact capability version;
- one exact raw event ID;
- evidence ID survives into hypothesis;
- trial names the hypothesis/family and dataset snapshot;
- ancestors of Trial reach RawEvidence and SourceCapability;
- every relevant timestamp is <= trial decision time;
- no returned artifact exposes `execution_authorized=True`.

- [ ] **Step 2: Write shared-upstream vendor integration**

Create vendor A and vendor B with different `source_id` but identical `upstream_source_ids=("exchange_x",)`.

Admit separate raw events. Add explicit `duplicates` lineage edge.

Assert:
- raw events remain separate immutable evidence;
- `independence_key(A) == independence_key(B)`;
- an independence-count helper returns one group, not two;
- no Stage 1 function claims confidence doubled.

Add:

```python
def independent_source_groups(capabilities: Sequence[SourceCapability]) -> tuple[tuple[str, ...], ...]:
    ...
```

to `capabilities.py` only if this integration test first demonstrates the need. The helper groups source IDs by exact upstream-independence key; it does not score confidence.

- [ ] **Step 3: Write irrelevant source integration**

Create a `negative_control` capability representing a reachable but semantically unrelated provider. Attempt to send a valid numeric WorldEvent through `factual_world_state`.

Assert:
- gateway rejects;
- no event inserted;
- no RawEvidence provenance node;
- no admission.

- [ ] **Step 4: Write invalidation propagation integration**

After creating SourceCapability -> RawEvidence -> NormalizedObservation -> Hypothesis -> Trial lineage, invalidate RawEvidence at time 800.

Assert:
- Trial is not invalidated at 799;
- Trial is invalidated at 800;
- governed historical observation remains visible at cutoff 700;
- governed projection at cutoff 800 excludes the invalidated raw evidence.

- [ ] **Step 5: Write family-history persistence integration**

Insert five trials in one family across two dataset hashes and mixed statuses. Assert:
- family count is five;
- all five remain readable;
- invalidating one evidence ancestor does not delete trial history;
- a later trial adds a sixth record rather than replacing one.

- [ ] **Step 6: Run all Stage 1 focused tests**

```bash
python -m pytest   tests_engine/test_omnivision_capabilities.py   tests_engine/test_omnivision_provenance.py   tests_engine/test_omnivision_trials.py   tests_engine/test_omnivision_gateway.py   tests_engine/test_omnivision_stage1_integration.py   -q
```

Expected: PASS.

- [ ] **Step 7: Run foundation compatibility tests**

```bash
python -m pytest   tests_engine/test_world_state.py   tests_engine/test_omnivision_contracts.py   tests_engine/test_omnivision_bridge.py   tests_engine/test_omnivision_hypotheses.py   tests_engine/test_omnivision_novelty.py   tests_engine/test_omnivision_falsification.py   tests_engine/test_omnivision_candidates.py   tests_engine/test_omnivision_integration.py   tests_engine/test_omnivision_stage0_temporal.py   tests_engine/test_omnivision_stage0_boundaries.py   tests_engine/test_advisory.py   tests_engine/test_research.py   -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add   icarus_engine/omnivision   tests_engine/test_omnivision_stage1_integration.py
git commit -m "Codex: prove OMNIVISION Stage 1 control-plane integration"
```

---

### Task 8: Extend CI, Run Stage 1 Extreme Audit, and Fix Only Proven Defects

**Files:**
- Modify: `.github/workflows/omnivision-stage0.yml`
- Create: `docs/audits/2026-09-24-omnivision-v2-stage1-audit.md`
- Modify only if tests prove defects: Stage 1 modules/tests.

**Interfaces:**
- Consumes: complete Stage 1 implementation.
- Produces: executable cross-version evidence and 16-lane audit verdict.

- [ ] **Step 1: Add Stage 1 files to the focused CI command**

Append:
- `tests_engine/test_omnivision_capabilities.py`
- `tests_engine/test_omnivision_provenance.py`
- `tests_engine/test_omnivision_trials.py`
- `tests_engine/test_omnivision_gateway.py`
- `tests_engine/test_omnivision_stage1_integration.py`

Do not remove any Stage 0 focused file.

- [ ] **Step 2: Compile**

```bash
python -m compileall -q icarus_engine tests_engine
```

Expected: exit 0.

- [ ] **Step 3: Run full suite locally or in the execution surface**

```bash
python -m pytest tests_engine -q
```

Expected: exit 0.

- [ ] **Step 4: Push and inspect both GitHub workflows**

Required:
- OMNIVISION matrix success on Python 3.10, 3.11, 3.12, 3.13;
- native Linux success;
- native Windows success.

If any job fails, use Superpowers systematic-debugging:
1. isolate symptom;
2. prove root cause with a focused failing test where possible;
3. apply minimal fix;
4. rerun scoped test;
5. rerun final gate once.

- [ ] **Step 5: Run duration visibility**

The Python 3.11 OMNIVISION matrix already runs:

```bash
python -m pytest tests_engine -q --durations=20
```

Record whether any new Stage 1 test enters the slowest 20. A Stage 1 test slower than 2 seconds is a review trigger, not an automatic failure; investigate query complexity and fixture size.

- [ ] **Step 6: Run the 16-lane Stage 1 audit**

Use the same lanes as Stage 0:

1. architecture/interface
2. security/trust boundary
3. point-in-time/temporal leakage
4. provenance/revision
5. statistical/search bias
6. calibration/uncertainty
7. causal claims
8. contradiction handling
9. source-health/quota behavior
10. negative-control/relevance
11. adversarial robustness
12. test quality/mutation resistance
13. performance/complexity
14. backwards compatibility
15. execution separation
16. documentation/resumability

Stage 1 expected non-blocking residuals:
- calibration/uncertainty -> Stage 2;
- stronger multiple-testing statistics -> Stage 3;
- regime/causal validation -> Stage 4;
- real source adapters -> Stage 5;
- proof-carrying candidate governor -> Stage 6.

No Stage 1 lane may call those implemented.

- [ ] **Step 7: Audit SQL and dependency boundaries**

Confirm:
- no Stage 1 table has a mutable update/delete API;
- immutability triggers exist;
- foreign keys on provenance edges;
- no raw provider network library imported into Stage 1 modules;
- no order/broker/Pulse imports;
- no secret value fields;
- no dynamic code execution;
- all JSON deserialization revalidates through dataclass contracts.

- [ ] **Step 8: Audit complexity**

Document:
- capability as-of query index;
- trial-family query index;
- DAG traversal worst-case behavior;
- invalidation closure behavior.

For Stage 1 dataset sizes, iterative graph traversal is acceptable if bounded by visited-node deduplication. Add an explicit `max_nodes=100000` traversal safety cap if implementation otherwise allows unbounded graph traversal; exceeding it must raise rather than silently truncate.

- [ ] **Step 9: Commit audit evidence**

```bash
git add   .github/workflows/omnivision-stage0.yml   docs/audits/2026-09-24-omnivision-v2-stage1-audit.md
git commit -m "Codex: audit OMNIVISION v2 Stage 1 control plane"
```

---

### Task 9: Final Stage 1 Gate and Durable Checkpoint

**Files:**
- Modify: `docs/audits/2026-09-24-omnivision-v2-stage1-audit.md`
- Modify: `.icarus_loop/state.json`

**Interfaces:**
- Consumes: final CI run IDs, audit findings, exact implementation head.
- Produces: binary Stage 1 GO/NO_GO and the only durable authorization to begin Stage 2 planning.

- [ ] **Step 1: Require all Stage 1 acceptance gates**

Stage 1 is `GO` only if all are true:

- capability versions are immutable and queryable as-of;
- historical source health is not retroactively rewritten;
- access/role/health/quota/entitlement states are distinct;
- semantic firewall blocks opinion/media/aggregator/negative-control from factual world-state admission;
- common upstream lineage is explicit and does not count as independent;
- governed evidence has exact capability + raw-evidence provenance;
- DAG is acyclic and traceable backward/forward;
- invalidation recursively reaches current dependents without deleting history;
- every stored trial belongs to a hypothesis family and multiple-testing family;
- all attempted terminal statuses remain counted;
- dataset changes do not erase family search history;
- Stage 1 cannot authorize/reuse holdout intervals;
- governed projection excludes unadmitted or invalidated raw evidence;
- no Stage 1 path authorizes execution;
- focused and full suites pass;
- Python 3.10–3.13 matrix passes;
- native Linux and Windows workflows pass;
- no blocking 16-lane audit finding remains.

Otherwise Stage 1 is `NO_GO`.

- [ ] **Step 2: Write exact final audit fields**

The final audit ends with observed values for:

```markdown
## Stage 1 Final Verdict

Verdict: GO or NO_GO
Implementation head: exact git commit SHA verified by CI
OMNIVISION matrix run: exact run ID and four job conclusions
Native workflow run: exact run ID and Linux/Windows job conclusions
Compile: exact command and result
Focused tests: exact command/result
Full tests: exact command/result
Performance: exact slowest-test evidence
Review: SHIP_STAGE1_GO, FIX_FIRST, or RETHINK
Blocking findings: none or exact finding IDs
Residual Stage 2+ requirements: exact list
Execution authorized: false
Next permitted action: write Stage 2 plan or continue Stage 1 remediation
```

No symbolic placeholder survives the committed audit.

- [ ] **Step 3: Update loop state**

For `GO`:

```json
{
  "active_build": {
    "phase": "v2_stage1_verified",
    "status": "ready_for_stage2_plan"
  }
}
```

For `NO_GO`:

```json
{
  "active_build": {
    "phase": "v2_stage1_remediation",
    "status": "blocked"
  }
}
```

Record:
- implementation head;
- exact CI run IDs;
- audit finding IDs;
- source-capability schema version;
- provenance/trial schema versions;
- plugin activations actually used during execution;
- residual Stage 2+ work;
- `execution_authorized=false`.

- [ ] **Step 4: Set delta pointer**

`last_processed_commit` must point to the exact final implementation/audit commit that exists before the state-checkpoint commit.

- [ ] **Step 5: Commit checkpoint**

```bash
git add   docs/audits/2026-09-24-omnivision-v2-stage1-audit.md   .icarus_loop/state.json
git commit -m "Codex: checkpoint OMNIVISION v2 Stage 1 verdict"
```

- [ ] **Step 6: Stop**

If `GO`, the next cycle may write the Stage 2 plan for confidence decomposition, calibration, abstention, and staleness.

Do not implement Stage 2 in this plan.

---

## Stage 1 Stable Finding IDs

Use these IDs in the audit/state:

- `S1-CAP-001` — capability version/as-of integrity
- `S1-CAP-002` — health/entitlement/rate-limit state conflation
- `S1-REL-001` — semantic relevance firewall failure
- `S1-DUP-001` — shared-upstream source counted as independent
- `S1-PROV-001` — missing or inconsistent provenance edge/node
- `S1-PROV-002` — lineage cycle or traversal defect
- `S1-INV-001` — invalidation propagation defect
- `S1-TRIAL-001` — missing search attempt/family accounting
- `S1-TRIAL-002` — trial path attempts to reauthorize holdout
- `S1-GATE-001` — raw evidence visible without completed admission
- `S1-TIME-001` — future capability/evidence knowledge leak
- `S1-BOUNDARY-001` — execution/network/secret boundary violation
- `S1-PERF-001` — material control-plane performance regression
- `S1-DOC-001` — resumability/audit gap

## Provider Admission Boundary

The user's available provider/plugin set is intentionally **not** wired in Stage 1.

After Stage 1 `GO`, each future Stage 5 adapter must receive a concrete `SourceCapability` record before its data can enter the governed evidence path. The existing design-cycle observations for StackerScan, U.S. Gold Bureau, Bybit, Twelve Data, FMP, Massive, Bigdata.com, The Fly, Zacks, DataBlue, Blockscout, Scite, treg, Stock Market Summary, and the Cheat Database negative control are capability-design evidence only.

Stage 1 may use provider names in fixtures, but tests must be local and deterministic. No test may require network access, credentials, a paid entitlement, or a live provider response.

## Execution / Review Policy

The user selected the highest-scrutiny route.

During implementation:

1. activate the required plugin stack at the start of every cycle;
2. use Superpowers TDD for every behavioral task;
3. use systematic-debugging on every unexpected failure;
4. use a fresh reviewer/worker when the harness exposes lifecycle tooling;
5. if no lifecycle tool exists, record that limitation and use the strongest native fallback without fabricating a reviewer;
6. run scoped tests after each task;
7. push only after the task's local/scoped evidence is clean;
8. use GitHub Actions as executable cross-version evidence;
9. use verification-before-completion before any `GO` claim;
10. persist exact findings, run IDs, commits, and residuals to GitHub.

## Plan Self-Review

### 1. Spec coverage

- Source Capability Registry: Tasks 1–2.
- Capability health/auth/quota/relevance distinctions: Tasks 1–2 and 6.
- Relevance firewall: Tasks 1 and 6.
- Duplicate vendor/upstream independence: Tasks 1, 3, and 7.
- Provenance DAG node/edge taxonomy: Task 3.
- Exact backward/forward lineage: Task 3 and Task 7.
- Recursive invalidation: Task 3 and Task 7.
- Search-Aware Trial Ledger: Tasks 4–5.
- Failed/rejected/deferred trial preservation: Task 4.
- Existing holdout anti-reuse compatibility: Tasks 4–5.
- Governed canonical evidence path: Task 6.
- Point-in-time admission/projection: Task 6 and Task 7.
- Stage 1 integration proof: Task 7.
- 16-lane audit and multi-version CI: Task 8.
- GitHub resumability and binary verdict: Task 9.
- Execution separation: global constraints, Task 6, Task 8, Task 9.
- No provider breadth before governance: provider admission boundary + forbidden changes.

Deferred intentionally because the approved evolution sequence assigns them later:
- confidence decomposition/calibration/abstention/staleness -> Stage 2;
- stronger novelty, negative-knowledge cemetery, statistical multiple-testing corrections -> Stage 3;
- regime/changepoint/causal validation -> Stage 4;
- real provider/domain adapters -> Stage 5;
- proof-carrying candidate and Integration Governor -> Stage 6.

### 2. Placeholder scan

This plan contains no `TBD`, `TODO`, `FIXME`, “implement later,” generic “add error handling,” “write tests for the above,” or “similar to Task” instructions.

The final audit section describes explicit fields to fill from observed runtime evidence; symbolic angle-bracket placeholders are not used.

### 3. Type consistency

- Stage 1 identities are SHA-256 strings only where a hash is explicitly required.
- `SourceCapability.version_id` is deterministic from the frozen body.
- capability as-of returns `SourceCapability | None`.
- provenance traversal returns tuples of node IDs.
- invalidation returns the exact affected node-ID tuple and never mutates nodes.
- trials use immutable `TrialRecord` and remain separate from holdout authorization.
- gateway returns a mapping admission record and governed projection returns existing `Observation` objects.
- the governed path preserves ledger event IDs as canonical evidence IDs.

### 4. Review Focus coverage

1. Historical capability integrity -> Task 2 no-retroactive-outage and future-knowledge tests.
2. Semantic firewall -> Task 1 role-purpose tests and Task 6 gateway negative controls.
3. Shared-upstream duplication -> Task 1 independence test, Task 3 duplicates edge, Task 7 integration.
4. Lineage completeness/invalidation -> Task 3 graph tests, Task 6 admission proof, Task 7 recursive integration.
5. Search-history honesty -> Task 4 family/status tests, Task 5 search-result adapter, existing research holdout regressions.

### 5. Stage boundary check

No task creates a real external adapter, calls a market/news/crypto/provider API, stores a credential, changes Pulse, changes order execution, implements calibrated uncertainty, performs causal identification, or promotes a candidate into live execution.

### Final plan ruling

Stage 1 is deliberately a **control-plane expansion**, not a source-breadth expansion. It makes later breadth safer by forcing every future provider, observation, transformation, and research attempt to carry explicit capability state, semantic role, lineage, timing, and search history before ICARUS can claim it as governed knowledge.
