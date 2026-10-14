# ICARUS Intelligence Fabric Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a durable, versioned, append-only ICARUS intelligence event fabric that provides machine-readable threads, indexed query, consumer replay, deterministic attention ranking, and a lossless bridge from normalized Unified Intelligence claims without granting execution authority.

**Architecture:** Add one focused stdlib-only backend module. `IntelligenceEvent` validates/canonicalizes immutable envelopes; `IntelligenceFabric` journals them transactionally in SQLite and exposes read/query/replay/thread/inbox projections. Unified Intelligence claims are bridged into events without re-scoring or re-validating predictive merit.

**Tech Stack:** Python 3.10+, stdlib `dataclasses`, `datetime`, `hashlib`, `json`, `math`, `sqlite3`; pytest.

**Spec:** `docs/superpowers/specs/2026-10-12-intelligence-fabric-design.md`

## Global Constraints

- `execution_authorized` is always `false`.
- `production_decision_authorized` is always `false`.
- No provider calls, external services, new dependencies, spend, credentials, workflow/schedule changes or execution activation.
- Phase 1 edits only the two new backend/test files plus this design/plan documentation.
- Do not edit UI/aesthetics, Brain, brain_sync, server, Atlas registry, provider/collector or broker paths.
- Events are append-only: no public update/delete event method.
- Replay sequence is local journal order, never market-event order.

## Review Focus

- Naive or timezone-free timestamps must fail closed rather than silently localize.
- JSON containing NaN/Infinity or payloads over 32,768 UTF-8 bytes must fail closed.
- Re-publishing an identical event after closing/reopening a file-backed journal must preserve the same ID and sequence rather than duplicate it.
- Inbox expiration affects attention projection only; replay/history must still return expired events.
- Unified Intelligence source confidence must not alter attention rank or be represented as validated trading edge.

---

### Task 1: Durable intelligence fabric contract and journal

**Files:**
- Create: `icarus_engine/intelligence_fabric.py`
- Create: `tests_engine/test_intelligence_fabric.py`

**Interfaces:**
- Consumes: normalized Unified Intelligence claim mappings shaped like `IntelligenceClaim.normalized()`.
- Produces: `IntelligenceEvent`, `IntelligenceFabric`, `event_from_intelligence_claim`.

- [ ] **Step 1: Write failing contract tests**

Create tests that assert:

- `IntelligenceEvent(...).normalized()` returns schema `icarus-intelligence-fabric-v1`, canonical UTC timestamps and both authority flags false.
- malformed timestamps, `received_at < observed_at`, unsupported event types/source kinds, non-finite urgency/confidence/payload and out-of-range severity/urgency/confidence fail with `ValueError`.
- payloads larger than 32,768 bytes and more than 64 assets/tags/causation/evidence IDs fail closed.
- two semantically identical events normalize identically and compute the same deterministic event ID.
- source confidence does not change attention score when severity/urgency/type are equal.

- [ ] **Step 2: Run tests and verify RED**

Run: `pytest -q tests_engine/test_intelligence_fabric.py`

Expected: FAIL because `icarus_engine.intelligence_fabric` does not exist.

- [ ] **Step 3: Implement the event contract**

Create `icarus_engine/intelligence_fabric.py` with:

- `SCHEMA_VERSION = "icarus-intelligence-fabric-v1"`.
- `IntelligenceEvent` frozen dataclass with fields: `event_type`, `source`, `source_kind`, `channel`, `thread_key`, `title`, `body`, `observed_at`, `received_at`, `severity=0`, `urgency=0.0`, `confidence=None`, `expires_at=None`, `assets=()`, `correlation_id=None`, `causation_ids=()`, `evidence_ids=()`, `tags=()`, `payload={}`.
- `IntelligenceEvent.normalized() -> dict[str, Any]`.
- `IntelligenceEvent.event_id() -> str` as SHA-256 over canonical normalized JSON.
- `attention_score(event: IntelligenceEvent | Mapping[str, Any]) -> float` using `min(100, severity*12 + urgency*30 + type_bonus)` with bonuses risk=10, anomaly=6, alert=4, decision_request=4, else 0.

Validation limits from the spec are exact: title 240 chars, body 4,000 chars, source 160, source_kind 40, channel 80, thread_key/correlation/evidence/causation item 240, asset/tag 80, max 64 items in each repeated collection, payload max 32,768 UTF-8 bytes. Severity is integer 0–5 excluding bool. Urgency/confidence are finite floats in 0–1 excluding bool. Timestamp inputs must be strings with explicit timezone and normalize to UTC `Z`.

- [ ] **Step 4: Run contract tests and verify GREEN**

Run: `pytest -q tests_engine/test_intelligence_fabric.py`

Expected: contract-focused tests pass.

- [ ] **Step 5: Add failing journal/replay/query tests**

Add tests asserting:

- `IntelligenceFabric(":memory:")` publishes atomically and returns `sequence`, `event_id`, `idempotent`, `attention_score` and both authority flags false.
- duplicate publish returns the original sequence with `idempotent=true` and does not increase replay count.
- file-backed close/reopen preserves events, replay sequence and idempotency.
- `replay(after_sequence=N)` returns strictly later events in ascending sequence order.
- `get(event_id)` returns the canonical stored event.
- `query` filters by channel, thread, any requested asset, any requested tag, any requested event type, minimum severity, source and received-time boundaries.
- `thread(thread_key)` is an ascending sequence projection.
- `inbox(as_of=...)` sorts by attention score descending and excludes expired events only from the inbox; replay still includes them.
- query/replay limits reject bool, zero, negative and values over 1,000.

- [ ] **Step 6: Run journal tests and verify RED**

Run: `pytest -q tests_engine/test_intelligence_fabric.py`

Expected: FAIL because `IntelligenceFabric` behavior is not implemented yet.

- [ ] **Step 7: Implement the append-only SQLite journal**

Implement:

- `IntelligenceFabric(path_or_connection: str | sqlite3.Connection = ":memory:")`.
- Tables `fabric_events`, `fabric_assets`, `fabric_tags`, `fabric_causes` and indexes required by the spec.
- `publish(event: IntelligenceEvent | Mapping[str, Any]) -> dict[str, Any]`.
- `get(event_id: str) -> dict[str, Any] | None`.
- `replay(*, after_sequence: int = 0, limit: int = 100) -> list[dict[str, Any]]`.
- `query(*, channel=None, thread_key=None, assets=None, event_types=None, min_severity=None, source=None, tags=None, after=None, before=None, limit=100) -> list[dict[str, Any]]` where assets/tags/event types use OR-within-filter semantics and different filter categories combine with AND.
- `thread(thread_key: str, *, limit: int = 100) -> list[dict[str, Any]]`.
- `inbox(*, as_of: str, channel=None, assets=None, limit: int = 100) -> list[dict[str, Any]]` ordered by stored attention score DESC, received time DESC, sequence DESC, with `expires_at <= as_of` excluded only from this projection.
- `close()` and context-manager methods.

No update/delete event API.

- [ ] **Step 8: Run journal tests and verify GREEN**

Run: `pytest -q tests_engine/test_intelligence_fabric.py`

Expected: all event+journal tests pass.

- [ ] **Step 9: Add failing Unified Intelligence bridge tests**

Add tests asserting `event_from_intelligence_claim(claim, claim_id="claim-1")`:

- emits `event_type="claim"`, `channel="intelligence"`;
- preserves source/source_kind/observed/received/confidence;
- stores stance, semantic key, regime, horizon, lineage and original authority flags in payload/evidence metadata;
- produces a deterministic thread key from semantic key/regime/horizon;
- keeps `execution_authorized=false` and `production_decision_authorized=false` regardless of input flags;
- does not make confidence part of attention scoring;
- fails closed if required normalized-claim fields are missing or malformed.

- [ ] **Step 10: Run bridge tests and verify RED**

Run: `pytest -q tests_engine/test_intelligence_fabric.py`

Expected: FAIL because the bridge does not exist yet.

- [ ] **Step 11: Implement the Unified Intelligence bridge**

Implement `event_from_intelligence_claim(claim: Mapping[str, Any], claim_id: str | None = None) -> IntelligenceEvent`. It validates required claim fields, hashes the semantic group into a bounded deterministic thread key, copies source identity/timestamps/confidence, adds claim lineage plus optional claim ID to evidence IDs, and stores the complete finite normalized claim under `payload["unified_intelligence_claim"]`. It does not call providers, re-score stance, calibrate confidence, fuse claims or grant execution authority.

- [ ] **Step 12: Verify focused and repository suites**

Run focused: `pytest -q tests_engine/test_intelligence_fabric.py`

Expected: PASS with zero failures/skips.

Run repository: `pytest -q`

Expected: zero failures. If unrelated pre-existing failures appear, record each by name; do not conceal them.

- [ ] **Step 13: Commit/publish branch and open PR**

Commit the two code/test files and the design/plan docs on `chatgpt/beyond-ib-intelligence-fabric-20261012`. Open a PR to `main`, request Claude review through the coordination inbox, and do not merge the code without that review/evidence gate.
