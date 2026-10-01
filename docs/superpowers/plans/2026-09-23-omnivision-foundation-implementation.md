# OMNIVISION Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first end-to-end OMNIVISION research path from an authorized cross-domain event through immutable advisory evidence, point-in-time world-state projection, falsifiable hypothesis generation, novelty screening, falsification/walk-forward validation, and a research-only integration candidate.

**Architecture:** Preserve `AdvisoryLedger` as the immutable evidence authority, add a narrow cross-domain `world_state` event contract, and project accepted ledger events into the existing deterministic `WorldStateGraph`. New hypothesis, novelty, and falsification modules remain pure/stateless where possible so they can be tested independently; final candidate construction consumes only hash-bound evidence and validation outputs and always emits `execution_authorized=false`.

**Tech Stack:** Python 3.10+ stdlib, sqlite3, dataclasses, hashlib/json/statistics/math, pytest. No new runtime dependency.

**Spec:** `docs/superpowers/specs/2026-09-23-omnivision-federated-research-mesh-design.md`

## Global Constraints

- `execution_authorized=false` remains invariant.
- No Pulse rewrite.
- No sandbox escape, credential discovery, access-control bypass, stealth persistence, scraping prohibited sources, or unauthorized access.
- Inputs are public, licensed, user-authorized, or connected sources only.
- Observed, derived, inferred, and unknown states remain distinct.
- Inference never upgrades itself into an observation.
- No synthesized ticks, fills, publication times, or other fabricated evidence.
- Existing owner-hard rules in `ASTRA_DO_NOT.md` remain authoritative.
- Engine/runtime code remains Python stdlib-only.
- Every historical decision uses first-available/receipt time, never event time alone.
- Every task follows TDD and commits only after its scoped tests pass.

## Review Focus

1. **Unknown publication time:** first-observed evidence must use receipt time as availability and retain the `publication_time_unknown` quality flag; it must never invent a publication timestamp.
2. **Ledger revision drift:** a later source revision must invalidate a stale projected observation/hypothesis when reconstructed as-of a later time, while historical as-of replay retains the older revision.
3. **Cross-source disagreement:** contradictory evidence must survive projection as separate observations and lower confidence or create a contradiction; no source is silently selected as truth.
4. **Duplicate/near-duplicate research feature:** novelty screening must reject exact duplicates and highly redundant candidates before holdout/falsification budget is spent.
5. **Validation leakage:** placebo/walk-forward evaluation must never let a fold consume rows whose `available_at` is after that fold's decision cutoff, and a failed holdout may not trigger a second candidate on the same interval.

---

## File Map

**Create**
- `icarus_engine/omnivision/__init__.py` — package exports only.
- `icarus_engine/omnivision/contracts.py` — strict canonical cross-domain event/observation contract and conversions.
- `icarus_engine/omnivision/ledger_bridge.py` — read-only projection from accepted `AdvisoryLedger` events into `Observation`.
- `icarus_engine/omnivision/hypotheses.py` — immutable hypothesis schema and deterministic forge from gaps/contradictions.
- `icarus_engine/omnivision/novelty.py` — bounded redundancy screening.
- `icarus_engine/omnivision/falsification.py` — timestamp-safe placebo and walk-forward evaluation primitives.
- `icarus_engine/omnivision/candidates.py` — research-only candidate artifact builder.
- `tests_engine/test_omnivision_contracts.py`
- `tests_engine/test_omnivision_bridge.py`
- `tests_engine/test_omnivision_hypotheses.py`
- `tests_engine/test_omnivision_novelty.py`
- `tests_engine/test_omnivision_falsification.py`
- `tests_engine/test_omnivision_candidates.py`
- `tests_engine/test_omnivision_integration.py`

**Modify**
- `icarus_engine/advisory.py` — accept one new `event_type="world_state"` with strict domain/entity metadata while preserving all existing validation.
- `tests_engine/test_advisory.py` — regression tests for new event type plus unchanged rejection behavior.
- `.icarus_loop/state.json` — checkpoint exact task/test results after implementation batches.

**Do not modify**
- `icarus_engine/strategy/pulse.py`
- broker/bridge execution paths
- live strategy inputs

---

### Task 1: Canonical Cross-Domain Observation Contract

**Files:**
- Create: `icarus_engine/omnivision/__init__.py`
- Create: `icarus_engine/omnivision/contracts.py`
- Create: `tests_engine/test_omnivision_contracts.py`

**Interfaces:**
- Consumes: validated primitive Python values only.
- Produces:
  - `WorldEvent(source: str, source_event_id: str, revision_id: str, source_url: str, domain: str, entity: str, asset_ids: tuple[str, ...], observed_at: str, published_at: str | None, values: Mapping[str, float], units: Mapping[str, str], confidence: float, timing_basis: str, quality_flags: tuple[str, ...] = ())`
  - `WorldEvent.to_advisory_event(schema_version: int = 1) -> dict`
  - `observation_from_event(event: Mapping, variable: str) -> Observation`

- [ ] **Step 1: Write failing contract tests**

```python
from icarus_engine.omnivision.contracts import WorldEvent, observation_from_event

def test_world_event_preserves_domain_entity_and_availability():
    event = WorldEvent(
        source="noaa", source_event_id="wx-1", revision_id="v1",
        source_url="https://www.noaa.gov/example",
        domain="weather", entity="US_MIDWEST", asset_ids=("GC",),
        observed_at="2026-09-23T12:00:00Z",
        published_at="2026-09-23T12:05:00Z",
        values={"temperature_anomaly": 1.25},
        units={"temperature_anomaly": "celsius"},
        confidence=0.9, timing_basis="published",
    )
    payload = event.to_advisory_event()
    assert payload["event_type"] == "world_state"
    assert payload["domain"] == "weather"
    assert payload["entity"] == "US_MIDWEST"
    assert payload["confidence"] == 0.9

def test_first_observed_does_not_invent_publication_time():
    event = WorldEvent(
        source="ais", source_event_id="port-1", revision_id="v1",
        source_url="https://ais.example/event",
        domain="logistics", entity="PORT_X", asset_ids=("NQ",),
        observed_at="2026-09-23T12:00:00Z", published_at=None,
        values={"congestion_z": 2.0}, units={"congestion_z": "zscore"},
        confidence=0.7, timing_basis="first_observed",
        quality_flags=("publication_time_unknown",),
    )
    assert event.to_advisory_event()["published_at"] is None
```

Also test: empty domain/entity, confidence outside `[0,1]`, mismatched `values/units`, non-finite numeric values, unsupported timing basis.

- [ ] **Step 2: Run tests and confirm RED**

Run:
```bash
python -m pytest tests_engine/test_omnivision_contracts.py -q
```

Expected: collection/import failure because `icarus_engine.omnivision.contracts` does not exist.

- [ ] **Step 3: Implement the strict contract**

Implement `WorldEvent` as a frozen dataclass. `to_advisory_event()` must emit exactly:

```python
{
    "schema_version": 1,
    "source": self.source,
    "source_event_id": self.source_event_id,
    "revision_id": self.revision_id,
    "source_url": self.source_url,
    "event_type": "world_state",
    "asset_ids": list(self.asset_ids),
    "instrument_id": self.entity,
    "observed_at": self.observed_at,
    "published_at": self.published_at,
    "values": dict(self.values),
    "units": dict(self.units),
    "timing_basis": self.timing_basis,
    "quality_flags": list(self.quality_flags),
    "domain": self.domain,
    "entity": self.entity,
    "confidence": self.confidence,
}
```

`observation_from_event()` must reject non-`world_state` input and use:
- `observed_at` as `Observation.observed_at`
- `published_at` when present, otherwise `received_at`, as `Observation.available_at`
- `source_url` as provenance
- event confidence unchanged
- one observation per named numeric variable

Use only timezone-aware ISO-8601 parsing.

- [ ] **Step 4: Run scoped tests and confirm GREEN**

```bash
python -m pytest tests_engine/test_omnivision_contracts.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add icarus_engine/omnivision tests_engine/test_omnivision_contracts.py
git commit -m "Codex: add OMNIVISION world-event contract"
```

---

### Task 2: Preserve AdvisoryLedger Invariants for World-State Evidence

**Files:**
- Modify: `icarus_engine/advisory.py` in `AdvisoryLedger._event`, `_observation_age`
- Modify: `tests_engine/test_advisory.py`
- Create: `icarus_engine/omnivision/ledger_bridge.py`
- Create: `tests_engine/test_omnivision_bridge.py`

**Interfaces:**
- Consumes: `WorldEvent.to_advisory_event()` payloads and existing `AdvisoryLedger`.
- Produces:
  - `ledger_observations(ledger: AdvisoryLedger, asset: str, as_of: str) -> tuple[Observation, ...]`
  - no write path besides existing `AdvisoryLedger.ingest_event()`

- [ ] **Step 1: Add failing AdvisoryLedger tests**

Add tests proving:
- `event_type="world_state"` requires `domain`, `entity`, and numeric `confidence` in `[0,1]`.
- existing `cot/macro/news/correlation/company` payloads still reject unexpected `domain/entity/confidence`.
- source URL allowlist, HTTPS-only behavior, asset registry, revision identity, signed replay protection, and future-time rejection remain unchanged.
- `timing_basis="first_observed"` still stores `published_at=None` and uses receipt time for historical availability.

Example:

```python
def test_world_state_event_keeps_existing_allowlist_and_time_guards(ledger):
    payload = event(
        event_type="world_state",
        report_family=None,
        domain="weather",
        entity="US_MIDWEST",
        confidence=0.8,
        values={"heat_z": 1.5},
        units={"heat_z": "zscore"},
    )
    payload.pop("report_family", None)
    saved = ledger.ingest_event(payload, now=NOW)
    assert saved["domain"] == "weather"
    assert saved["entity"] == "US_MIDWEST"
    assert saved["confidence"] == 0.8
```

- [ ] **Step 2: Run advisory tests and confirm RED**

```bash
python -m pytest tests_engine/test_advisory.py -q
```

Expected: new world-state tests fail with `unsupported event type` or unexpected fields.

- [ ] **Step 3: Extend `AdvisoryLedger._event` narrowly**

Change allowed event types to:

```python
("cot", "macro", "news", "correlation", "company", "world_state")
```

For `world_state` only:
- permit optional-field set additions `domain`, `entity`, `confidence`
- require all three after parsing
- validate `domain` and `entity` with `_identity`
- validate confidence as finite non-boolean number in `[0,1]`
- require at least one numeric value
- preserve all common URL, source, asset, revision, timing, freshness, and quality-flag checks
- do not alter database schema
- do not make these fields valid for legacy event types

Extend observation-age mapping only if required by a specific domain policy; otherwise retain the normal event TTL in this phase.

- [ ] **Step 4: Write bridge tests**

```python
from icarus_engine.omnivision.ledger_bridge import ledger_observations

def test_bridge_projects_only_evidence_available_as_of(ledger):
    old = ledger.ingest_event(world_event(revision_id="v1", published_at=iso(NOW - 20)), now=NOW - 10)
    ledger.ingest_event(world_event(revision_id="v2", published_at=iso(NOW + 5)), now=NOW + 6)
    rows = ledger_observations(ledger, "NQ", iso(NOW))
    assert {r.provenance for r in rows} == {old["source_url"]}

def test_bridge_preserves_cross_source_contradiction(ledger):
    ledger.ingest_event(world_event(source="a", value=1.0), now=NOW)
    ledger.ingest_event(world_event(source="b", value=-1.0), now=NOW)
    rows = ledger_observations(ledger, "NQ", iso(NOW))
    assert sorted(r.value for r in rows) == [-1.0, 1.0]
```

- [ ] **Step 5: Implement read-only bridge**

`ledger_observations()` calls `ledger.events_as_of(asset, as_of)`, filters `event_type=="world_state"`, and expands each event's numeric `values` via `observation_from_event`. It must never open the SQLite file directly or bypass ledger revision/freshness semantics.

- [ ] **Step 6: Run scoped regression tests**

```bash
python -m pytest tests_engine/test_advisory.py tests_engine/test_omnivision_contracts.py tests_engine/test_omnivision_bridge.py -q
```

Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add icarus_engine/advisory.py icarus_engine/omnivision/ledger_bridge.py tests_engine/test_advisory.py tests_engine/test_omnivision_bridge.py
git commit -m "Codex: bridge immutable advisory evidence into OMNIVISION"
```

---

### Task 3: Machine-Readable Falsifiable Hypotheses

**Files:**
- Create: `icarus_engine/omnivision/hypotheses.py`
- Create: `tests_engine/test_omnivision_hypotheses.py`

**Interfaces:**
- Consumes: `WorldStateGraph.gap_map()` output plus asset/regime context.
- Produces:
  - frozen `Hypothesis` dataclass
  - `forge_hypotheses(gap_map: Mapping, *, asset: str, decision_at: int) -> tuple[Hypothesis, ...]`

`Hypothesis` fields:
```python
hypothesis_id: str
kind: str                   # "latent_gap" | "contradiction"
asset: str
target: str
mechanism: str
expected_lag_seconds: int
horizon_seconds: int
required_variables: tuple[str, ...]
evidence_ids: tuple[str, ...]
falsification_rules: tuple[str, ...]
eligible_regimes: tuple[str, ...]
decision_at: int
execution_authorized: bool = False
```

- [ ] **Step 1: Write failing hypothesis tests**

```python
def test_gap_forge_is_deterministic_and_hash_bound():
    gap = {
        "latent": {
            "inflation_pressure": {
                "status": "latent_estimate", "estimate": 1.2, "confidence": 0.6,
                "evidence_ids": ["a" * 64], "mechanisms": ["freight-to-goods"],
            }
        },
        "unresolved": [],
        "contradictions": [],
        "execution_authorized": False,
    }
    left = forge_hypotheses(gap, asset="NQ", decision_at=100)
    right = forge_hypotheses(gap, asset="NQ", decision_at=100)
    assert left == right
    assert left[0].hypothesis_id == right[0].hypothesis_id
    assert left[0].execution_authorized is False

def test_unresolved_gap_without_evidence_does_not_become_hypothesis():
    gap = {"latent": {}, "unresolved": ["mystery"], "contradictions": [], "execution_authorized": False}
    assert forge_hypotheses(gap, asset="NQ", decision_at=100) == ()
```

Add a contradiction test requiring both evidence IDs in the resulting hypothesis.

- [ ] **Step 2: Run tests and confirm RED**

```bash
python -m pytest tests_engine/test_omnivision_hypotheses.py -q
```

- [ ] **Step 3: Implement deterministic forge**

Rules for this phase:
- one `latent_gap` hypothesis per latent target with non-empty evidence and mechanism
- one `contradiction` hypothesis per contradiction record
- unresolved gaps produce acquisition priorities later, not hypotheses
- IDs are SHA-256 of canonical JSON excluding `hypothesis_id`
- default falsification rules:
  - latent: `("placebo_shift_must_not_match", "walk_forward_must_hold")`
  - contradiction: `("source_disagreement_must_resolve_or_predict_distinct_outcomes",)`
- no LLM or network calls in the forge

- [ ] **Step 4: Run tests and confirm GREEN**

```bash
python -m pytest tests_engine/test_omnivision_hypotheses.py -q
```

- [ ] **Step 5: Commit**

```bash
git add icarus_engine/omnivision/hypotheses.py tests_engine/test_omnivision_hypotheses.py
git commit -m "Codex: add falsifiable OMNIVISION hypothesis forge"
```

---

### Task 4: Bounded Novelty/Redundancy Screening

**Files:**
- Create: `icarus_engine/omnivision/novelty.py`
- Create: `tests_engine/test_omnivision_novelty.py`

**Interfaces:**
- Consumes timestamp-aligned numeric candidate series and existing feature series.
- Produces:
  - `screen_novelty(candidate: Sequence[tuple[int, float]], existing: Mapping[str, Sequence[tuple[int, float]]], *, max_abs_correlation: float = 0.95, min_pairs: int = 20) -> dict`

Return shape:
```python
{
    "status": "novel" | "redundant" | "insufficient_data",
    "max_abs_correlation": float | None,
    "closest_feature": str | None,
    "pairs": int,
    "reason": str,
}
```

- [ ] **Step 1: Write failing novelty tests**

```python
def test_exact_duplicate_is_redundant():
    series = [(i, float(i)) for i in range(30)]
    out = screen_novelty(series, {"existing": series})
    assert out["status"] == "redundant"
    assert out["closest_feature"] == "existing"

def test_distinct_orthogonal_pattern_can_pass():
    candidate = [(i, float(i % 2)) for i in range(40)]
    existing = [(i, float((i // 2) % 2)) for i in range(40)]
    out = screen_novelty(candidate, {"existing": existing}, max_abs_correlation=0.95)
    assert out["status"] == "novel"

def test_alignment_never_fills_missing_rows():
    candidate = [(i, float(i)) for i in range(30)]
    existing = [(100 + i, float(i)) for i in range(30)]
    assert screen_novelty(candidate, {"x": existing})["status"] == "insufficient_data"
```

- [ ] **Step 2: Run tests and confirm RED**

```bash
python -m pytest tests_engine/test_omnivision_novelty.py -q
```

- [ ] **Step 3: Implement minimal novelty screen**

Use exact timestamp intersection only; do not interpolate or forward-fill. Compute Pearson correlation with stdlib math/statistics. Reject:
- exact same aligned values
- absolute correlation `>= max_abs_correlation`

Return insufficient data when no existing feature has `min_pairs` aligned observations.

This phase deliberately does not add mutual information; correlation screening satisfies the architecture's minimum novelty gate without adding a dependency or pretending a broader statistical guarantee.

- [ ] **Step 4: Run tests and confirm GREEN**

```bash
python -m pytest tests_engine/test_omnivision_novelty.py -q
```

- [ ] **Step 5: Commit**

```bash
git add icarus_engine/omnivision/novelty.py tests_engine/test_omnivision_novelty.py
git commit -m "Codex: add bounded OMNIVISION novelty screening"
```

---

### Task 5: Timestamp-Safe Placebo and Walk-Forward Falsification

**Files:**
- Create: `icarus_engine/omnivision/falsification.py`
- Create: `tests_engine/test_omnivision_falsification.py`

**Interfaces:**
- Consumes point-in-time rows:
  - feature rows `(observed_at: int, available_at: int, value: float)`
  - outcome rows `(observed_at: int, available_at: int, value: float)`
- Produces:
  - `aligned_pairs(feature_rows, outcome_rows, *, decision_cutoff: int, lag_seconds: int) -> list[tuple[float, float]]`
  - `placebo_shift_test(feature_rows: Sequence[tuple[int, int, float]], outcome_rows: Sequence[tuple[int, int, float]], *, decision_cutoff: int, lag_seconds: int, placebo_shift_seconds: int, min_pairs: int = 20) -> dict`
  - `walk_forward_correlation(feature_rows: Sequence[tuple[int, int, float]], outcome_rows: Sequence[tuple[int, int, float]], *, cutoffs: Sequence[int], lag_seconds: int, min_pairs: int = 20) -> dict`

- [ ] **Step 1: Write failing leakage tests**

```python
def test_alignment_rejects_future_available_feature():
    features = [(10, 50, 1.0), (20, 20, 2.0)]
    outcomes = [(30, 30, 3.0), (40, 40, 4.0)]
    pairs = aligned_pairs(features, outcomes, decision_cutoff=40, lag_seconds=20)
    assert pairs == [(2.0, 4.0)]

def test_placebo_that_matches_real_signal_fails_falsification():
    features = [(i, i, float(i)) for i in range(1, 80)]
    outcomes = [(i + 1, i + 1, float(i)) for i in range(1, 80)]
    out = placebo_shift_test(
        features, outcomes, decision_cutoff=80, lag_seconds=1,
        placebo_shift_seconds=0, min_pairs=20,
    )
    assert out["passed"] is False
```

Add:
- duplicate observation/revision ambiguity rejects instead of choosing one
- folds use only rows available at each cutoff
- empty/constant series return explicit insufficient status
- future outcome availability cannot affect an earlier fold

- [ ] **Step 2: Run tests and confirm RED**

```bash
python -m pytest tests_engine/test_omnivision_falsification.py -q
```

- [ ] **Step 3: Implement aligned pairing**

For each feature observation at `t`, target outcome observation is exactly `t + lag_seconds`. Include the pair only when both records' `available_at <= decision_cutoff`. Reject duplicate `observed_at` rows rather than guessing revisions.

- [ ] **Step 4: Implement placebo test**

Compute absolute correlation for:
- real alignment at `lag_seconds`
- placebo alignment at `lag_seconds + placebo_shift_seconds`

Return:

```python
{
    "status": "complete",
    "real_abs_correlation": 0.42,
    "placebo_abs_correlation": 0.11,
    "pairs": 48,
    "passed": True,
}
```

Pass only when:
- both have enough pairs
- real absolute correlation is strictly greater than placebo
- real correlation is finite/non-constant

- [ ] **Step 5: Implement walk-forward correlation**

Evaluate each cutoff independently with `aligned_pairs`. Return per-fold evidence plus:
- `folds_total`
- `folds_qualified`
- median signed correlation
- `stable_sign` true only when every qualified fold has the same nonzero sign
- `passed` true only when at least three folds qualify and `stable_sign` is true

This is a falsification primitive, not a profitability claim.

- [ ] **Step 6: Run tests and confirm GREEN**

```bash
python -m pytest tests_engine/test_omnivision_falsification.py -q
```

- [ ] **Step 7: Commit**

```bash
git add icarus_engine/omnivision/falsification.py tests_engine/test_omnivision_falsification.py
git commit -m "Codex: add point-in-time OMNIVISION falsification"
```

---

### Task 6: Research-Only Candidate Builder

**Files:**
- Create: `icarus_engine/omnivision/candidates.py`
- Create: `tests_engine/test_omnivision_candidates.py`

**Interfaces:**
- Consumes:
  - `Hypothesis`
  - novelty result
  - placebo result
  - walk-forward result
  - evidence IDs
  - dataset hash
- Produces:
  - `build_candidate(*, hypothesis: Hypothesis, novelty: Mapping, placebo: Mapping, walk_forward: Mapping, dataset_hash: str, known_failure_modes: Sequence[str], rollback_conditions: Sequence[str]) -> dict`

Required artifact fields:
```python
{
    "schema_version": 1,
    "artifact_type": "omnivision_research_candidate",
    "candidate_hash": "b" * 64,
    "hypothesis": {"hypothesis_id": "c" * 64, "asset": "NQ", "kind": "latent_gap"},
    "evidence_ids": ["d" * 64],
    "dataset_hash": "a" * 64,
    "validation": {
        "novelty": {"status": "novel"},
        "placebo": {"status": "complete", "passed": True},
        "walk_forward": {"passed": True},
    },
    "known_failure_modes": ["source_revision"],
    "rollback_conditions": ["walk_forward_sign_breaks"],
    "integration_ready": True,
    "execution_authorized": False,
}
```

- [ ] **Step 1: Write failing promotion tests**

```python
def test_candidate_never_authorizes_execution():
    artifact = build_candidate(
        hypothesis=qualified_hypothesis(),
        novelty={"status": "novel"},
        placebo={"status": "complete", "passed": True},
        walk_forward={"passed": True},
        dataset_hash="a" * 64,
        known_failure_modes=("source_stale",),
        rollback_conditions=("walk_forward_sign_breaks",),
    )
    assert artifact["integration_ready"] is True
    assert artifact["execution_authorized"] is False

def test_any_failed_gate_blocks_integration_readiness():
    artifact = build_candidate(
        hypothesis=qualified_hypothesis(),
        novelty={"status": "redundant"},
        placebo={"status": "complete", "passed": True},
        walk_forward={"passed": True},
        dataset_hash="a" * 64,
        known_failure_modes=("source_stale",),
        rollback_conditions=("walk_forward_sign_breaks",),
    )
    assert artifact["integration_ready"] is False
```

Also test:
- invalid SHA-256 dataset hash rejected
- missing failure modes/rollback conditions rejected
- candidate hash changes when any evidence/validation component changes
- a caller-supplied `execution_authorized=True` is impossible because the API does not accept that parameter

- [ ] **Step 2: Run tests and confirm RED**

```bash
python -m pytest tests_engine/test_omnivision_candidates.py -q
```

- [ ] **Step 3: Implement deterministic candidate builder**

`integration_ready` is true only when:
- novelty status is `novel`
- placebo status is `complete` and `passed is True`
- walk-forward `passed is True`
- hypothesis has at least one evidence ID
- failure modes and rollback conditions are non-empty

The hash is SHA-256 of canonical JSON excluding `candidate_hash`.

- [ ] **Step 4: Run tests and confirm GREEN**

```bash
python -m pytest tests_engine/test_omnivision_candidates.py -q
```

- [ ] **Step 5: Commit**

```bash
git add icarus_engine/omnivision/candidates.py tests_engine/test_omnivision_candidates.py
git commit -m "Codex: add OMNIVISION research candidate artifact"
```

---

### Task 7: End-to-End Evidence → Candidate Integration Test

**Files:**
- Create: `tests_engine/test_omnivision_integration.py`
- Modify only if the test exposes a real integration defect:
  - `icarus_engine/omnivision/contracts.py`
  - `icarus_engine/omnivision/ledger_bridge.py`
  - `icarus_engine/omnivision/hypotheses.py`
  - `icarus_engine/omnivision/novelty.py`
  - `icarus_engine/omnivision/falsification.py`
  - `icarus_engine/omnivision/candidates.py`

**Interfaces:**
- Consumes all prior task interfaces.
- Produces proof that one approved synthetic world-state event can traverse the entire research path without execution authority.

- [ ] **Step 1: Write end-to-end test**

Use two allowlisted synthetic HTTPS sources and deterministic synthetic time series.

Test flow:

```python
ledger.ingest_event(WorldEvent(
    source="source_a", source_event_id="event-1", revision_id="v1",
    source_url="https://source-a.example/event-1",
    domain="logistics", entity="PORT_X", asset_ids=("NQ",),
    observed_at=iso(NOW - 20), published_at=iso(NOW - 10),
    values={"shipping_stress": 2.0}, units={"shipping_stress": "zscore"},
    confidence=0.9, timing_basis="published",
).to_advisory_event(), now=NOW)
observations = ledger_observations(ledger, "NQ", iso(NOW))
graph = WorldStateGraph(observations, transmissions)
gap = graph.gap_map(["inflation_pressure"], NOW_INT)
hypothesis = forge_hypotheses(gap, asset="NQ", decision_at=NOW_INT)[0]
novelty = screen_novelty(candidate_series, existing_features)
placebo = placebo_shift_test(feature_rows, outcome_rows, decision_cutoff=NOW_INT, lag_seconds=1, placebo_shift_seconds=10, min_pairs=20)
walk = walk_forward_correlation(feature_rows, outcome_rows, cutoffs=(40, 60, 80), lag_seconds=1, min_pairs=20)
artifact = build_candidate(
    hypothesis=hypothesis,
    novelty=novelty,
    placebo=placebo,
    walk_forward=walk,
    dataset_hash="a" * 64,
    known_failure_modes=("source_revision", "regime_break",),
    rollback_conditions=("source_invalidated", "walk_forward_sign_breaks",),
)
assert artifact["artifact_type"] == "omnivision_research_candidate"
assert artifact["execution_authorized"] is False
```

Also assert:
- a future-published revision is invisible at the historical decision timestamp
- a contradictory second source appears in `graph.contradictions()`
- no file under strategy/Pulse or bridge execution configuration is touched by the integration API

- [ ] **Step 2: Run integration test and confirm RED/GREEN as appropriate**

```bash
python -m pytest tests_engine/test_omnivision_integration.py -q
```

If it fails, repair only the owning module and rerun its scoped test plus integration test.

- [ ] **Step 3: Run complete OMNIVISION + regression test set**

```bash
python -m pytest   tests_engine/test_world_state.py   tests_engine/test_omnivision_contracts.py   tests_engine/test_omnivision_bridge.py   tests_engine/test_omnivision_hypotheses.py   tests_engine/test_omnivision_novelty.py   tests_engine/test_omnivision_falsification.py   tests_engine/test_omnivision_candidates.py   tests_engine/test_omnivision_integration.py   tests_engine/test_advisory.py   tests_engine/test_research.py -q
```

Expected: all pass.

- [ ] **Step 4: Run full engine test suite**

```bash
python -m pytest tests_engine -q
```

Expected: all pass. If an unrelated pre-existing failure occurs, capture its exact test/error in `.icarus_loop/state.json`; do not weaken or skip the test to get green.

- [ ] **Step 5: Check forbidden execution surface remains untouched**

```bash
git diff main...HEAD -- icarus_engine/strategy/pulse.py icarus_bridge
```

Expected: no diff.

- [ ] **Step 6: Commit integration proof**

```bash
git add tests_engine/test_omnivision_integration.py
git commit -m "Codex: prove OMNIVISION research path end to end"
```

---

### Task 8: Durable GitHub Checkpoint and Review Evidence

**Files:**
- Modify: `.icarus_loop/state.json`

**Interfaces:**
- Consumes: exact commit SHAs and observed test/CI results from Tasks 1-7.
- Produces: resumable delta-only checkpoint for the next loop cycle.

- [ ] **Step 1: Record exact plugin contribution for each implementation cycle**

For every cycle checkpoint append:

```json
{
  "plugins": [
    {"name": "superpowers/test-driven-development", "contribution": "enforced red-green implementation order"},
    {"name": "astral-orchestrator", "contribution": "routed bounded implementation/review work"},
    {"name": "akinator/everything", "contribution": "kept repository knowledge and implementation evidence synchronized"},
    {"name": "baton-pass", "contribution": "maintained delta-only resumable checkpoint state"}
  ]
}
```

Only record a plugin as used when it was actually activated in that cycle.

- [ ] **Step 2: Record verification truthfully**

Use only:
- `passed`
- `passed outside sandbox`
- `not run — <reason>`
- `expected to pass, unverified`

Store:
- scoped test commands/results
- full suite command/result
- CI run ID/result if a workflow exists
- latest implementation commit
- unresolved failures
- next bounded objective

- [ ] **Step 3: Update delta pointer**

Set `last_processed_commit` to the exact final implementation commit so the next loop retrieves only subsequent changes plus unresolved findings.

- [ ] **Step 4: Commit checkpoint**

```bash
git add .icarus_loop/state.json
git commit -m "Codex: checkpoint OMNIVISION foundation verification"
```

---

## Plan Self-Review

### Spec coverage

- Authorized cross-domain source contract: Tasks 1-2.
- Immutable AdvisoryLedger integration: Task 2.
- Deterministic world-state inference: existing `world_state.py` exercised by Tasks 2, 3, 7.
- Machine-readable falsifiable hypotheses: Task 3.
- Novelty screening: Task 4.
- At least one falsification path: Task 5 placebo.
- Walk-forward validation path: Task 5.
- Failure/contradiction preservation: Tasks 2, 3, 7.
- Research-only candidate: Task 6.
- End-to-end evidence path: Task 7.
- Exact verification and resumability: Task 8.
- No execution authority/Pulse rewrite: Global Constraints and Tasks 6-7.

### Type consistency

- `WorldEvent.to_advisory_event() -> dict` is the sole new write payload entering AdvisoryLedger.
- `ledger_observations() -> tuple[Observation, ...]` feeds existing `WorldStateGraph`.
- `forge_hypotheses() -> tuple[Hypothesis, ...]` consumes graph gap output.
- `screen_novelty() -> dict`, `placebo_shift_test() -> dict`, and `walk_forward_correlation() -> dict` feed `build_candidate()`.
- `build_candidate() -> dict` is terminal research output only.

### Scope boundary

This plan intentionally stops before:
- real NOAA/AIS/grid/news adapters
- automatic network acquisition
- mutual-information/conditional-information estimators
- regime model training
- multi-agent research scheduling
- live/shadow strategy consumption

Those belong in later plans after this foundation is verified.
