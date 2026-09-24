# OMNIVISION v2 Stage 1 Trust Substrate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the versioned Source Capability Registry, Semantic Relevance Firewall, Provenance DAG, and Search-Aware Trial Ledger that every future OMNIVISION source, hypothesis, validation run, and candidate must traverse before it can be treated as admissible research evidence.

**Architecture:** Stage 1 adds a dependency-light trust substrate beside the existing immutable `AdvisoryLedger`; it does not replace the ledger, world-state graph, or Stage 0 contracts. Capability state is append-only and queryable as-of time, semantic admission is deterministic and fail-closed, provenance is an explicit acyclic graph with backwards/forwards tracing, and research trials are append-only records that preserve the hidden search process instead of only the surviving result.

**Tech Stack:** Python 3.10+ standard library, dataclasses, hashlib/json canonicalization, sqlite3, pytest, existing GitHub Actions matrix. No new runtime dependency.

**Spec:** `docs/superpowers/specs/2026-09-24-omnivision-epistemic-control-plane-v2-design.md`

## Global Constraints

- `execution_authorized=false` remains invariant for OMNIVISION research artifacts.
- No Pulse rewrite.
- No autonomous credential acquisition.
- No sandbox escape, credential discovery, access-control bypass, stealth persistence, unauthorized access, or prohibited scraping.
- No fabricated observations, publication times, ticks, fills, revisions, or source availability.
- Inputs must be public, licensed, connected, or explicitly user-authorized.
- Observed, derived, latent/inferred, hypothesized, contradicted, stale, invalidated, and unknown states remain distinct.
- Inference never upgrades itself into an observation.
- Source opinion, attention, sentiment, analyst rank, and media tone are labeled as such and never silently converted into factual world state.
- Current data is never backfilled into a historical decision timestamp unless the source proves it was available then.
- Owner-hard repository rules remain authoritative.
- Stage 0 `GO` at verified implementation head `511814e1d4f4a2527abaa3b6e3472a66df666281` is the minimum baseline.
- Stage 1 does not implement live provider adapters, calibration, staleness decay, causal identification, regime models, or integration promotion.
- Capability records describe source behavior; they never assert that a source is correct merely because it is reachable.
- A source outage, quota limit, entitlement failure, or policy block is a capability-state observation, not evidence that the underlying world fact is false.
- No provider can bypass the registry because it is "trusted," authenticated, popular, low-latency, or already used elsewhere.
- No trial may disappear from family accounting because it failed, duplicated another trial, or was abandoned.
- All deterministic identities use canonical JSON with `sort_keys=True`, compact separators, `allow_nan=False`, and SHA-256.
- Every new SQLite table is append-only after insert except explicitly modeled invalidation/status-event tables; destructive update/delete triggers must reject mutation.
- No external provider call occurs inside Stage 1 product code or Stage 1 tests.

## Design Evidence Carried Into Stage 1

These are capability observations, not market signals:

- FMP returned dated Treasury curves for 2026-09-23 and 2026-09-24: source records need date/maturity semantics distinct from receipt time.
- Bybit public BTC spot returned price/change/volume with an explicit warning that data may be delayed/incomplete: public access and evidentiary confidence are separate fields.
- StackerScan returned XAU/XAG with a UTC `asOf` instant and market date: registry timing metadata must distinguish source update instant from session date.
- Massive documents futures session bars whose `window_start` may be the prior calendar day to the settlement/session date: adapter timing semantics cannot be globally inferred from a date label.
- Twelve Data reported authenticated state: authentication/entitlement is dynamic capability state, not a hard-coded provider property.
- Blockscout required a session unlock, exposed a finite free-session budget, and announced a future API-key requirement: capability versions need `review_after`/expiry plus auth/quota state.
- DataBlue exposes per-endpoint credit weights: expected acquisition cost belongs in capability metadata before research-budget allocation.
- Scite hit monthly quota exhaustion after earlier successful research use: `quota_exhausted` must remain distinct from low evidentiary quality.
- OpenLineage 1.53 models explicit run/job/dataset identities and exact lineage edges rather than inferring a Cartesian product; OMNIVISION follows the explicit-edge principle without adding an OpenLineage dependency.
- Deflated Sharpe Ratio literature treats selection bias and the number of attempted alternatives as part of the evidentiary burden; Stage 1 therefore records the complete trial family, including rejected trials.

## Review Focus

1. **Historical capability replay:** a source that is healthy today but was rate-limited at a past decision timestamp must replay as rate-limited at that timestamp.
2. **Common-upstream duplication:** two vendors that normalize the same upstream release must be traceable to a shared ancestor and must not count as independent evidence merely because source IDs differ.
3. **Semantic-role confusion:** analyst opinion, media attention, aggregator output, and negative controls must not pass a primary-observation requirement.
4. **Hidden search:** rejected/duplicate/failed trials remain in family counts and cannot be omitted from the search burden.
5. **Recursive invalidation:** invalidating a load-bearing raw-evidence/provenance node must make every dependent descendant discoverable without deleting history.

---

## Scope decomposition

Stage 1 is one cohesive **trust substrate** because its units form a strict sequence:

```text
SourceCapability version
        ↓
Semantic admission decision
        ↓
Evidence / transformation lineage
        ↓
Hypothesis + trial lineage
        ↓
Search-family accounting
```

Later stages consume these interfaces:

- Stage 2 — confidence decomposition, calibration, staleness, abstention;
- Stage 3 — negative knowledge and stronger novelty/search statistics;
- Stage 4 — regime/changepoint and causal validation;
- Stage 5 — authorized external adapters;
- Stage 6 — proof-carrying candidate + integration governor.

Stage 1 must not pre-implement those stages.

## File Map

**Create**
- `icarus_engine/omnivision/capabilities.py` — immutable source capability contract plus append-only SQLite capability registry and as-of replay.
- `icarus_engine/omnivision/admissibility.py` — deterministic semantic/relevance firewall.
- `icarus_engine/omnivision/provenance.py` — immutable provenance nodes/edges, DAG validation, ancestry/descendant tracing, shared-upstream and invalidation traversal.
- `icarus_engine/omnivision/trials.py` — immutable trial contract plus append-only SQLite trial ledger and family accounting.
- `tests_engine/test_omnivision_capabilities.py`
- `tests_engine/test_omnivision_admissibility.py`
- `tests_engine/test_omnivision_provenance.py`
- `tests_engine/test_omnivision_trials.py`
- `tests_engine/test_omnivision_stage1_integration.py`
- `docs/audits/2026-09-24-omnivision-v2-stage1-trust-substrate-audit.md`

**Modify**
- `icarus_engine/omnivision/__init__.py` — export only stable Stage 1 public types after their tests pass.
- `.github/workflows/omnivision-stage0.yml` — rename/generalize workflow display name and add Stage 1 focused tests while preserving the Python 3.10–3.13 full-suite matrix.
- `.icarus_loop/state.json` — exact plan/implementation/test/plugin/evidence checkpoint only after execution.

**Do not modify**
- `icarus_engine/strategy/pulse.py`
- `icarus_bridge/**`
- broker/order execution modules
- existing `AdvisoryLedger` mutation semantics unless a Stage 1 integration test proves a necessary compatibility defect
- `WorldStateGraph` inference mathematics
- existing candidate promotion semantics

## Stable Stage 1 vocabulary

### Access classes

```python
ACCESS_CLASSES = frozenset({
    "public",
    "licensed",
    "connected",
    "user_authorized",
})
```

### Epistemic roles

```python
EPISTEMIC_ROLES = frozenset({
    "primary_observation",
    "aggregator",
    "analyst_opinion",
    "media",
    "derived_market_data",
    "negative_control",
})
```

### Health states

```python
HEALTH_STATES = frozenset({
    "healthy",
    "degraded",
    "rate_limited",
    "quota_exhausted",
    "blocked_by_source_policy",
    "entitlement_missing",
    "schema_changed",
    "stale",
    "disabled",
})
```

### Provenance node kinds

```python
NODE_KINDS = frozenset({
    "source_capability",
    "raw_evidence",
    "normalized_observation",
    "derived_feature",
    "latent_estimate",
    "dataset_snapshot",
    "hypothesis",
    "trial",
    "validation_result",
    "candidate",
    "integration_decision",
})
```

### Provenance edge kinds

```python
EDGE_KINDS = frozenset({
    "produced_by",
    "normalized_from",
    "derived_from",
    "contradicts",
    "supersedes",
    "tests",
    "falsifies",
    "supports",
    "duplicates",
    "depends_on",
    "invalidates",
})
```

### Trial result statuses

```python
TRIAL_STATUSES = frozenset({
    "planned",
    "running",
    "passed",
    "rejected",
    "failed",
    "duplicate",
    "deferred",
    "invalidated",
})
```

---

### Task 1: Immutable Source Capability Contract

**Files:**
- Create: `icarus_engine/omnivision/capabilities.py`
- Test: `tests_engine/test_omnivision_capabilities.py`

**Interfaces:**
- Produces `SourceCapability`.
- Produces `source_capability_id(capability: SourceCapability) -> str`.
- Later tasks consume the exact field names below.

```python
@dataclass(frozen=True)
class SourceCapability:
    source_id: str
    provider: str
    version: int
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
    allowed_entities: tuple[str, ...]
    forbidden_uses: tuple[str, ...]
    valid_from: int
    valid_until: int | None = None
    review_after: int | None = None
    upstream_source_ids: tuple[str, ...] = ()
```

- [ ] **Step 1: Write contract validation tests**

Tests pin:
- version is positive integer;
- access/role/health values are from the stable vocabularies;
- all identity/text fields are non-empty bounded strings;
- tuples are tuples, deterministic, non-duplicated, and non-empty where required;
- `valid_until > valid_from` when present;
- `review_after >= valid_from` when present;
- a source cannot list itself in `upstream_source_ids`;
- `negative_control` cannot claim `primary_observation` semantics through a second field;
- deterministic capability ID changes when any epistemically material field changes.

Representative test:

```python
def test_capability_identity_changes_with_health_and_timing():
    healthy = capability(health_state="healthy")
    limited = capability(health_state="rate_limited")
    timing_changed = capability(timing_semantics="session_end_date")
    assert healthy.capability_id != limited.capability_id
    assert healthy.capability_id != timing_changed.capability_id
```

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests_engine/test_omnivision_capabilities.py -q
```

Expected: import/module failure because the contract does not exist.

- [ ] **Step 3: Implement canonical identity helpers and `SourceCapability`**

Use the repository's existing canonical JSON/SHA-256 pattern. Do not import a new serialization package.

Expose `capability_id` as a read-only property computed from every dataclass field.

- [ ] **Step 4: Run GREEN + existing contract regressions**

```bash
python -m pytest   tests_engine/test_omnivision_capabilities.py   tests_engine/test_omnivision_contracts.py   tests_engine/test_omnivision_stage0_boundaries.py   -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add icarus_engine/omnivision/capabilities.py tests_engine/test_omnivision_capabilities.py
git commit -m "Codex: add immutable OMNIVISION source capability contract"
```

---

### Task 2: Append-Only Capability Registry With Historical Replay

**Files:**
- Modify: `icarus_engine/omnivision/capabilities.py`
- Modify: `tests_engine/test_omnivision_capabilities.py`

**Interfaces:**
- Produces `SourceCapabilityRegistry(path: str | Path)`.
- Produces:
  - `register(capability: SourceCapability, *, recorded_at: int) -> str`
  - `as_of(source_id: str, decision_at: int) -> SourceCapability | None`
  - `history(source_id: str) -> tuple[SourceCapability, ...]`
  - `eligible(*, decision_at: int, domain: str | None = None) -> tuple[SourceCapability, ...]`

- [ ] **Step 1: Write RED tests for append-only and as-of behavior**

Required cases:
- healthy v1 at T100, rate-limited v2 at T200: `as_of(..., 150)` returns v1; T200 returns v2;
- future capability versions never leak backward;
- `valid_until` expires a capability;
- `review_after` does not auto-disable but is preserved for later policy;
- duplicate `capability_id` insert is idempotent only when payload is byte-equivalent;
- same `source_id/version` with different payload rejects;
- direct SQL UPDATE and DELETE reject via triggers;
- two registry instances opening the same SQLite file replay the same history.

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests_engine/test_omnivision_capabilities.py -q
```

Expected: failures for missing registry behavior.

- [ ] **Step 3: Implement SQLite schema**

Tables:

```sql
CREATE TABLE IF NOT EXISTS source_capabilities (
    capability_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    payload_json TEXT NOT NULL,
    valid_from INTEGER NOT NULL,
    valid_until INTEGER,
    recorded_at INTEGER NOT NULL,
    UNIQUE(source_id, version)
);

CREATE INDEX IF NOT EXISTS idx_source_capability_asof
ON source_capabilities(source_id, valid_from, version);
```

Add BEFORE UPDATE and BEFORE DELETE triggers that raise `ABORT`.

Do not persist credentials, tokens, API keys, session IDs, cookies, or secret material in capability payloads.

- [ ] **Step 4: Implement deterministic replay**

Selection rule at `decision_at`:
1. `valid_from <= decision_at`;
2. `valid_until IS NULL OR decision_at < valid_until`;
3. highest `version`;
4. no use of `recorded_at` to backdate knowability.

Reject registration when `recorded_at < valid_from` unless the record explicitly represents a policy schedule known in advance. Stage 1 has no scheduled-policy exception, so reject it.

- [ ] **Step 5: Run GREEN**

```bash
python -m pytest tests_engine/test_omnivision_capabilities.py -q
```

- [ ] **Step 6: Commit**

```bash
git add icarus_engine/omnivision/capabilities.py tests_engine/test_omnivision_capabilities.py
git commit -m "Codex: add historical OMNIVISION capability registry"
```

---

### Task 3: Semantic Relevance Firewall

**Files:**
- Create: `icarus_engine/omnivision/admissibility.py`
- Create: `tests_engine/test_omnivision_admissibility.py`

**Interfaces:**
- Consumes `SourceCapability`.
- Produces:

```python
@dataclass(frozen=True)
class AdmissionRequest:
    domain: str
    required_roles: tuple[str, ...]
    entity: str | None = None
    intended_use: str = "research_evidence"

@dataclass(frozen=True)
class AdmissionDecision:
    admitted: bool
    reason_code: str
    capability_id: str
    source_id: str
    decision_at: int

def evaluate_admission(
    capability: SourceCapability,
    request: AdmissionRequest,
    *,
    decision_at: int,
) -> AdmissionDecision:
    ...
```

Reason codes are stable strings:

```python
ADMISSION_REASONS = frozenset({
    "admitted",
    "capability_not_yet_valid",
    "capability_expired",
    "health_not_usable",
    "domain_mismatch",
    "role_mismatch",
    "entity_not_allowed",
    "forbidden_use",
    "negative_control",
})
```

- [ ] **Step 1: Write RED tests**

Pin:
- healthy public primary macro source admitted for matching macro request;
- `quota_exhausted`, `blocked_by_source_policy`, `entitlement_missing`, `schema_changed`, `stale`, `disabled` fail closed;
- `degraded` and `rate_limited` do not silently pass as healthy; Stage 1 returns `health_not_usable`;
- analyst opinion fails a primary-observation requirement;
- aggregator fails a primary-observation requirement unless request explicitly allows aggregator;
- media fails a primary-observation requirement;
- negative control always rejects under `research_evidence`;
- domain/entity/forbidden-use mismatches reject;
- no decision can be evaluated before `valid_from` or after `valid_until`.

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests_engine/test_omnivision_admissibility.py -q
```

- [ ] **Step 3: Implement minimal deterministic firewall**

No network calls, fuzzy NLP, embeddings, LLM calls, or provider-specific conditionals.

- [ ] **Step 4: Run GREEN**

```bash
python -m pytest   tests_engine/test_omnivision_admissibility.py   tests_engine/test_omnivision_capabilities.py   -q
```

- [ ] **Step 5: Commit**

```bash
git add icarus_engine/omnivision/admissibility.py tests_engine/test_omnivision_admissibility.py
git commit -m "Codex: add OMNIVISION semantic admission firewall"
```

---

### Task 4: Explicit Provenance DAG

**Files:**
- Create: `icarus_engine/omnivision/provenance.py`
- Create: `tests_engine/test_omnivision_provenance.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class ProvenanceNode:
    node_id: str
    kind: str
    external_id: str
    as_of: int
    content_hash: str
    metadata: tuple[tuple[str, str], ...]

@dataclass(frozen=True)
class ProvenanceEdge:
    edge_id: str
    kind: str
    source_node_id: str
    target_node_id: str
    run_id: str
    created_at: int
    transform_id: str
    evidence_hashes: tuple[str, ...]
    code_hash: str | None = None
    config_hash: str | None = None

class ProvenanceDAG:
    def add_node(self, node: ProvenanceNode) -> None: ...
    def add_edge(self, edge: ProvenanceEdge) -> None: ...
    def ancestors(self, node_id: str) -> tuple[str, ...]: ...
    def descendants(self, node_id: str) -> tuple[str, ...]: ...
    def shared_ancestors(self, node_ids: tuple[str, ...]) -> tuple[str, ...]: ...
    def invalidation_closure(self, node_id: str) -> tuple[str, ...]: ...
    def snapshot_hash(self) -> str: ...
```

- [ ] **Step 1: Write RED tests for node/edge validation**

Reject:
- unknown node/edge kinds;
- non-SHA content/evidence/code/config hashes;
- self edges;
- missing source/target nodes;
- duplicate edge IDs with different content;
- cycles through any dependency-carrying edge.

Contradiction edges may connect peer observations but still cannot create a directed dependency cycle.

- [ ] **Step 2: Write RED shared-upstream test**

```python
def test_two_vendors_with_one_upstream_are_not_independent():
    dag = graph_with(
        upstream_raw,
        vendor_a_normalized,
        vendor_b_normalized,
        edges=(
            edge(upstream_raw, vendor_a_normalized, "normalized_from"),
            edge(upstream_raw, vendor_b_normalized, "normalized_from"),
        ),
    )
    assert dag.shared_ancestors(
        (vendor_a_normalized.node_id, vendor_b_normalized.node_id)
    ) == (upstream_raw.node_id,)
```

- [ ] **Step 3: Write RED recursive invalidation test**

Raw evidence -> normalized observation -> derived feature -> hypothesis -> trial must all appear in `invalidation_closure(raw_id)`.

History is not deleted.

- [ ] **Step 4: Run RED**

```bash
python -m pytest tests_engine/test_omnivision_provenance.py -q
```

- [ ] **Step 5: Implement DAG**

Use adjacency dictionaries and deterministic sorted traversal. Stage 1 keeps the DAG in-memory as a deterministic value structure; persistence remains the immutable ledgers' responsibility until a later scale requirement proves a dedicated graph store necessary.

Dependency-carrying edge kinds for cycle detection:

```python
DEPENDENCY_EDGES = frozenset({
    "produced_by",
    "normalized_from",
    "derived_from",
    "tests",
    "supports",
    "depends_on",
})
```

`contradicts`, `supersedes`, `duplicates`, `falsifies`, and `invalidates` remain explicit semantic relationships but do not imply value derivation.

- [ ] **Step 6: Run GREEN**

```bash
python -m pytest tests_engine/test_omnivision_provenance.py -q
```

- [ ] **Step 7: Commit**

```bash
git add icarus_engine/omnivision/provenance.py tests_engine/test_omnivision_provenance.py
git commit -m "Codex: add explicit OMNIVISION provenance DAG"
```

---

### Task 5: Immutable Search-Aware Trial Contract

**Files:**
- Create: `icarus_engine/omnivision/trials.py`
- Create: `tests_engine/test_omnivision_trials.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class TrialRecord:
    trial_id: str
    hypothesis_id: str
    hypothesis_family_id: str
    parent_trial_ids: tuple[str, ...]
    generation_method: str
    feature_config_hash: str
    dataset_snapshot_hashes: tuple[str, ...]
    train_start: int
    train_end: int
    validation_start: int
    validation_end: int
    holdout_start: int
    holdout_end: int
    code_hash: str
    config_hash: str
    decision_at: int
    metrics: tuple[tuple[str, float], ...]
    cost_assumptions: tuple[tuple[str, float], ...]
    status: str
    rejection_reason: str | None
    family_memberships: tuple[str, ...]
    execution_authorized: bool = False
```

- [ ] **Step 1: Write RED validation tests**

Pin:
- all IDs/hashes lowercase SHA-256;
- train < validation < holdout boundaries with no overlap;
- `decision_at >= holdout_end` for a completed evaluation;
- metrics/cost values finite;
- status from stable vocabulary;
- rejected/failed/duplicate/invalidated records require `rejection_reason`;
- passed records may omit rejection reason;
- parent IDs unique and cannot contain own trial ID;
- `execution_authorized=True` rejects.

- [ ] **Step 2: Run RED**

```bash
python -m pytest tests_engine/test_omnivision_trials.py -q
```

- [ ] **Step 3: Implement immutable contract**

Identity is the canonical hash of every field except `trial_id`; constructor verifies the supplied `trial_id` equals the computed identity.

Provide:

```python
@classmethod
def build(cls, **values) -> "TrialRecord":
    ...
```

so callers do not manually compute the ID.

- [ ] **Step 4: Run GREEN**

```bash
python -m pytest tests_engine/test_omnivision_trials.py -q
```

- [ ] **Step 5: Commit**

```bash
git add icarus_engine/omnivision/trials.py tests_engine/test_omnivision_trials.py
git commit -m "Codex: add immutable OMNIVISION trial contract"
```

---

### Task 6: Append-Only Trial Ledger and Search-Family Accounting

**Files:**
- Modify: `icarus_engine/omnivision/trials.py`
- Modify: `tests_engine/test_omnivision_trials.py`

**Interfaces:**

```python
class TrialLedger:
    def __init__(self, path: str | Path): ...
    def record(self, trial: TrialRecord, *, recorded_at: int) -> str: ...
    def get(self, trial_id: str) -> TrialRecord | None: ...
    def family(self, hypothesis_family_id: str) -> tuple[TrialRecord, ...]: ...
    def family_summary(self, hypothesis_family_id: str) -> dict: ...
    def search_burden(self, hypothesis_family_id: str) -> dict: ...
```

`family_summary()` returns:

```python
{
    "hypothesis_family_id": "...",
    "attempts_total": 0,
    "passed": 0,
    "rejected": 0,
    "failed": 0,
    "duplicate": 0,
    "deferred": 0,
    "invalidated": 0,
    "generation_methods": (),
    "dataset_snapshot_hashes": (),
}
```

`search_burden()` returns metadata, not a p-value:

```python
{
    "attempts_total": 0,
    "distinct_configs": 0,
    "distinct_datasets": 0,
    "correction_required": False,
    "reason": "single_recorded_attempt",
}
```

`correction_required=True` whenever the family contains more than one distinct feature/config search or more than one non-duplicate evaluated attempt.

- [ ] **Step 1: Write RED hidden-search tests**

Record one passed, two rejected, one duplicate, and one failed trial in one family. Assert:
- `attempts_total == 5`;
- all statuses are counted;
- deleting or updating rows through SQL is rejected;
- `correction_required is True`;
- querying only passed trials cannot change family summary;
- a duplicate trial still contributes to attempted-search history but is separately counted.

- [ ] **Step 2: Write RED restart/determinism tests**

Two ledger instances over the same SQLite file return identical family order and summary.

Order trials by `decision_at`, then `trial_id`.

- [ ] **Step 3: Run RED**

```bash
python -m pytest tests_engine/test_omnivision_trials.py -q
```

- [ ] **Step 4: Implement append-only SQLite ledger**

Schema:

```sql
CREATE TABLE IF NOT EXISTS omnivision_trials (
    trial_id TEXT PRIMARY KEY,
    hypothesis_id TEXT NOT NULL,
    hypothesis_family_id TEXT NOT NULL,
    decision_at INTEGER NOT NULL,
    status TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    recorded_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_omnivision_trial_family
ON omnivision_trials(hypothesis_family_id, decision_at, trial_id);
```

Add mutation-blocking UPDATE/DELETE triggers.

Do not implement Deflated Sharpe Ratio, PBO, FDR, or a generic significance calculator in Stage 1. The ledger records the search burden those later methods require.

- [ ] **Step 5: Run GREEN**

```bash
python -m pytest tests_engine/test_omnivision_trials.py -q
```

- [ ] **Step 6: Commit**

```bash
git add icarus_engine/omnivision/trials.py tests_engine/test_omnivision_trials.py
git commit -m "Codex: preserve OMNIVISION hidden research search history"
```

---

### Task 7: End-to-End Trust-Substrate Integration

**Files:**
- Create: `tests_engine/test_omnivision_stage1_integration.py`
- Modify: `icarus_engine/omnivision/__init__.py`

**Interfaces:**
- Consumes Tasks 1–6.
- Produces one deterministic Stage 1 research-control flow without calling an external provider.

- [ ] **Step 1: Write RED integration fixture**

Synthetic flow:

1. register a healthy `primary_observation` source capability v1;
2. admit it for a matching macro hypothesis;
3. create provenance nodes for capability -> raw evidence -> normalized observation -> hypothesis -> trial;
4. record a rejected trial;
5. register capability v2 as `quota_exhausted`;
6. prove a historical T150 admission still sees v1 while T250 sees v2 and rejects;
7. record a second trial in the same family;
8. prove `search_burden()["correction_required"] is True`;
9. invalidate raw evidence and prove trial node is in the invalidation closure;
10. assert every research artifact still carries no execution authority.

- [ ] **Step 2: Add shared-upstream integration case**

Create two healthy aggregator/vendor capability records with the same `upstream_source_ids=("official-release",)`. Their normalized nodes must expose a shared upstream lineage node before any later system can call them independent confirmations.

- [ ] **Step 3: Add negative-control integration case**

A syntactically valid `negative_control` capability is registered successfully but `evaluate_admission(... intended_use="research_evidence")` rejects it.

This pins the distinction between registry reachability and semantic admissibility.

- [ ] **Step 4: Run RED**

```bash
python -m pytest tests_engine/test_omnivision_stage1_integration.py -q
```

Expected: failures until public exports and any missing cross-component glue are present.

- [ ] **Step 5: Export stable interfaces**

`icarus_engine/omnivision/__init__.py` exports:

```python
from .admissibility import AdmissionDecision, AdmissionRequest, evaluate_admission
from .capabilities import SourceCapability, SourceCapabilityRegistry
from .provenance import ProvenanceDAG, ProvenanceEdge, ProvenanceNode
from .trials import TrialLedger, TrialRecord
```

Do not export internal validators/constants unless another production module needs them.

- [ ] **Step 6: Run GREEN + Stage 0 regressions**

```bash
python -m pytest   tests_engine/test_omnivision_stage1_integration.py   tests_engine/test_omnivision_capabilities.py   tests_engine/test_omnivision_admissibility.py   tests_engine/test_omnivision_provenance.py   tests_engine/test_omnivision_trials.py   tests_engine/test_omnivision_integration.py   tests_engine/test_omnivision_stage0_temporal.py   tests_engine/test_omnivision_stage0_boundaries.py   -q
```

- [ ] **Step 7: Commit**

```bash
git add   icarus_engine/omnivision/__init__.py   tests_engine/test_omnivision_stage1_integration.py
git commit -m "Codex: integrate OMNIVISION Stage 1 trust substrate"
```

---

### Task 8: Strengthen CI Without Weakening Existing Gates

**Files:**
- Modify: `.github/workflows/omnivision-stage0.yml`

**Interfaces:**
- Keeps Python matrix `3.10, 3.11, 3.12, 3.13`.
- Keeps compile, focused foundation regressions, full `tests_engine`, and Python 3.11 durations.
- Adds Stage 1 tests to the focused regression command.
- Rename workflow display name only; keep path stable to preserve history.

- [ ] **Step 1: Update display name**

Change:

```yaml
name: OMNIVISION Stage 0
```

to:

```yaml
name: OMNIVISION Trust Substrate
```

- [ ] **Step 2: Add Stage 1 tests to focused regression step**

Add exactly:

```text
tests_engine/test_omnivision_capabilities.py
tests_engine/test_omnivision_admissibility.py
tests_engine/test_omnivision_provenance.py
tests_engine/test_omnivision_trials.py
tests_engine/test_omnivision_stage1_integration.py
```

Do not remove any Stage 0 or foundation test path.

- [ ] **Step 3: Commit and observe workflow**

```bash
git add .github/workflows/omnivision-stage0.yml
git commit -m "Codex: extend OMNIVISION CI through Stage 1"
```

Required evidence before Stage 1 can be called verified:
- Python 3.10 job success;
- Python 3.11 job success;
- Python 3.12 job success;
- Python 3.13 job success;
- full suite success in each matrix job;
- Python 3.11 duration step success;
- native repository Linux workflow success;
- native repository Windows workflow success when triggered by changed paths.

If the native workflow does not trigger because its path filter excludes Stage 1-only files, record that exact reason; do not claim it passed for the Stage 1 commit.

---

### Task 9: Stage 1 Extreme Audit and Checkpoint

**Files:**
- Create: `docs/audits/2026-09-24-omnivision-v2-stage1-trust-substrate-audit.md`
- Modify: `.icarus_loop/state.json`

**Interfaces:**
- Consumes all Stage 1 code/tests/CI evidence.
- Produces binary `GO_STAGE2_PLAN` or `NO_GO_STAGE1_REMEDIATION`.

- [ ] **Step 1: Audit capability semantics**

Document and test representative capability profiles without calling providers in product code:

```text
FMP-like dated macro source
Bybit-like public venue source
StackerScan-like source with source-update instant + market date
Massive-like futures source with session-date semantics
Twelve-Data-like authenticated source
Blockscout-like session/quota/auth-transition source
DataBlue-like metered source
Scite-like quota-exhausted research source
Cheat-Database-like negative control
```

These are synthetic profiles derived from observed capability classes, not hard-coded provider adapters.

- [ ] **Step 2: Audit the 18 trust lanes**

Use exact verdict vocabulary:
- `PASS`
- `FIXED_AND_PASS`
- `RESIDUAL_LATER_STAGE_REQUIRED`
- `BLOCKING_FAIL`
- `NOT_APPLICABLE_STAGE1`

Lanes:

1. contract validation
2. historical capability replay
3. auth/entitlement state
4. health/quota/rate-limit state
5. temporal semantics
6. semantic relevance
7. epistemic-role separation
8. provenance identity
9. shared-upstream duplication
10. recursive invalidation
11. DAG cycle resistance
12. trial immutability
13. hidden-search accounting
14. dataset/code/config lineage
15. restart determinism
16. execution separation
17. backwards compatibility
18. performance/resumability

- [ ] **Step 3: Run security/boundary scans**

Run:

```bash
python -m pytest tests_engine/test_omnivision_stage0_boundaries.py -q
git diff main...HEAD -- icarus_engine/strategy/pulse.py icarus_bridge
```

Expected:
- boundary test PASS;
- no Stage 1 mutation to forbidden execution paths.

- [ ] **Step 4: Run final full verification**

```bash
python -m compileall -q icarus_engine tests_engine
python -m pytest tests_engine -q
python -m pytest tests_engine -q --durations=20
```

Then inspect GitHub Actions matrix results for the final implementation head.

- [ ] **Step 5: Performance guard**

Record:
- total full-suite runtime;
- slowest 20 tests;
- whether any Stage 1 test enters slowest 20;
- capability registry replay time for 1,000 synthetic versions;
- trial family summary time for 10,000 synthetic trials;
- provenance traversal time for a deterministic 10,000-node sparse DAG.

Microbenchmarks must run in a test or audit script with fixed seed/data shape and report wall-clock observations as environment-specific measurements, not universal performance guarantees.

Do not add a performance dependency.

- [ ] **Step 6: Independent review**

If an actual reviewer lifecycle is available, use it. Otherwise record the capability limitation and perform the approved fallback:
- fresh whole-delta reread;
- compare against Stage 1 plan;
- inspect every changed production file;
- inspect every new test;
- inspect CI job states;
- classify findings Critical / Important / Minor;
- fix Critical/Important with RED -> GREEN before final verdict.

Do not claim an unavailable reviewer ran.

- [ ] **Step 7: Compute Stage 1 verdict**

`GO_STAGE2_PLAN` only when:
- all Stage 1 focused tests pass;
- full `tests_engine` passes;
- Python 3.10–3.13 matrix passes;
- no execution boundary regression exists;
- no hidden mutation path exists in capability/trial ledgers;
- historical capability replay is proven;
- shared-upstream lineage is proven;
- hidden-search accounting includes failed/rejected/duplicate trials;
- recursive invalidation is proven;
- no blocking audit finding remains.

Otherwise: `NO_GO_STAGE1_REMEDIATION`.

- [ ] **Step 8: Update durable state**

For GO:

```json
{
  "active_build": {
    "phase": "v2_stage1_verified",
    "status": "ready_for_stage2_plan"
  }
}
```

Persist:
- final implementation head;
- exact workflow run/job IDs;
- test commands/results;
- audit path;
- stable interface list;
- unresolved later-stage requirements;
- plugin/capability contributions actually used;
- provider capability probes as design evidence only;
- `execution_authorized=false`.

- [ ] **Step 9: Commit audit/checkpoint**

```bash
git add   docs/audits/2026-09-24-omnivision-v2-stage1-trust-substrate-audit.md   .icarus_loop/state.json
git commit -m "Codex: checkpoint OMNIVISION v2 Stage 1 trust substrate"
```

- [ ] **Step 10: Stop**

The next cycle may write the Stage 2 plan for decomposed confidence, empirical calibration, staleness/half-life, and abstention.

Do not implement Stage 2 inside this plan.

---

## Stage 1 Stable Finding IDs

- `S1-CAP-001` — capability version/as-of replay defect
- `S1-CAP-002` — auth/entitlement/health state collapse
- `S1-SEM-001` — semantic-role/relevance admission defect
- `S1-PROV-001` — missing/incorrect lineage edge
- `S1-PROV-002` — shared-upstream independence defect
- `S1-PROV-003` — cycle or invalidation traversal defect
- `S1-TRIAL-001` — mutable/omitted trial history
- `S1-TRIAL-002` — incorrect family/search-burden accounting
- `S1-BOUNDARY-001` — execution-authority or forbidden dependency regression
- `S1-PERF-001` — material trust-substrate performance regression
- `S1-DOC-001` — resumability/evidence gap

## Knowledge delta by path

### `icarus_engine/omnivision/capabilities.py`
Introduces the source-capability ontology and historical registry. It is the only Stage 1 module allowed to decide which capability version existed at a decision timestamp.

### `icarus_engine/omnivision/admissibility.py`
Introduces deterministic semantic admission. It never fetches data and never infers source truthfulness.

### `icarus_engine/omnivision/provenance.py`
Introduces explicit lineage and invalidation traversal. It does not replace immutable evidence storage.

### `icarus_engine/omnivision/trials.py`
Introduces immutable trial/search history. It records search burden but does not yet decide which multiple-testing statistic is valid.

### Tests
Pin historical replay, role separation, common upstream ancestry, recursive invalidation, hidden search, restart determinism, and execution separation.

### Audit/state
Carry exact evidence, CI IDs, rulings, provider-probe lessons, residual gaps, and the next legal stage.

## Execution policy

The user's standing preference is the higher-scrutiny route. The current harness exposes no independent worker/subagent lifecycle tool, so execution must use the most rigorous available native fallback unless a worker tool becomes available in a later cycle.

Required execution skills:
- `superpowers/using-superpowers`
- `superpowers/executing-plans` when no worker lifecycle exists
- `superpowers/test-driven-development`
- `superpowers/systematic-debugging` on every unexpected failure before proposing a fix
- `superpowers/requesting-code-review` before the final verdict
- `superpowers/verification-before-completion`
- Astral/Akinator/Baton Pass cycle discipline
- Capability Orchestrator for selecting only provider/research tools that materially improve evidence

Adaptive Codex Orchestrator is task-local only in this harness unless persistent orchestration state is explicitly exposed; do not claim a persistent Ultra mode or child worker that the host did not confirm.

## Plan Self-Review

### Spec coverage

- Source Capability Registry: Tasks 1–2.
- Relevance/semantic firewall: Task 3.
- Provenance DAG: Task 4.
- Search-Aware Trial Ledger: Tasks 5–6.
- Shared-upstream duplicate protection: Tasks 4 and 7.
- Hidden-search accounting: Tasks 5–7.
- Execution separation: Tasks 7–9.
- Source-health/quota/auth/cost semantics: Tasks 1–3 and Task 9 synthetic capability audit.
- Exact lineage and recursive invalidation: Tasks 4 and 7.
- Restart/determinism: Tasks 2, 6, 9.
- CI and extreme audit: Tasks 8–9.
- Calibration, staleness, negative-knowledge resurrection rules, stronger novelty, regimes, causal inference, live adapters, and proof-carrying integration remain deliberately deferred to their specified later stages.

### Placeholder scan

The plan contains no unresolved `TBD`, `TODO`, `FIXME`, generic error-handling instructions, or references to undefined production interfaces.

### Type consistency

- `SourceCapabilityRegistry.as_of()` returns `SourceCapability | None`.
- `evaluate_admission()` consumes exactly one `SourceCapability` and returns `AdmissionDecision`.
- `ProvenanceDAG` consumes immutable `ProvenanceNode`/`ProvenanceEdge` values and returns sorted ID tuples.
- `TrialLedger` consumes immutable `TrialRecord` values and returns deterministic records/summaries.
- No Stage 1 public API accepts or returns live broker/order objects.

### Review Focus coverage

1. Historical capability replay — Task 2.
2. Common-upstream duplication — Tasks 4 and 7.
3. Semantic-role confusion — Task 3.
4. Hidden search — Task 6.
5. Recursive invalidation — Tasks 4 and 7.

### Scope ruling

Stage 1 remains one plan because capability admission, lineage, and trial accounting form a single trust chain and are independently testable tasks inside that chain. Splitting them into separate specs would create artificial integration gaps without reducing implementation risk.

### Final plan ruling

Stage 1 expands ICARUS horizontally across future data domains by strengthening the epistemic boundary first. It intentionally adds **zero live data adapters**: the system learns how to classify, admit, trace, invalidate, and account for evidence before it is allowed to ingest more of it.
