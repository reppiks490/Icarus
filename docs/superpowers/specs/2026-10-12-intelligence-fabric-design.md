# ICARUS Intelligence Fabric — Design

## Purpose

Build a machine-native communications and intelligence substrate for ICARUS that goes materially beyond a human chat product such as Instant Bloomberg. The fabric is not a chat clone. It is an append-only, provenance-preserving event plane in which humans, agents, research systems, market-data analyzers, risk systems and the existing Unified Intelligence Spine can exchange structured information without conflating communication with trading authority.

Phase 1 is backend-only and research/shadow-only. It does not activate execution, modify broker paths, add spend, create new schedules, call providers, or touch the UI lane.

## Existing foundation

ICARUS already has `icarus_engine.unified_intelligence`: a causal composition boundary for heterogeneous cognition that preserves source identity, evidence ancestry, disagreement and shared-lineage discounts. It deliberately cannot authorize production decisions or broker actions. The new fabric must compose that contract rather than replace it.

`icarus_engine.intelligence_feed` already projects canonical forecasts into the Unified Intelligence Spine while preserving durable first-receipt time. Phase 1 therefore focuses on the missing transport/history/attention layer: durable events, threads, replay and query.

## Options considered

### 1. Chat-first Bloomberg clone

Create rooms, DMs and messages first, then bolt machine metadata onto them.

Rejected. It makes human prose the canonical representation and forces agents to reverse-engineer state from conversation. It would reproduce Instant Bloomberg rather than exceed it.

### 2. External broker first (Kafka, NATS, Redis Streams)

Start with a distributed message bus and build ICARUS semantics on top.

Deferred. It is scalable, but introduces services, dependencies and operational burden before the event contract is stable. It also conflicts with the Phase-1 no-spend/no-new-credential constraint.

### 3. Embedded append-only intelligence fabric

Use a strict versioned event envelope plus an embedded SQLite journal, with query/thread/replay APIs and a bridge from normalized Unified Intelligence claims. Make transports pluggable later.

Selected. SQLite gives durable local ordering, transactions, indexed query, no new service and no new dependency. The contract can later be carried over WebSocket/SSE/NATS/Kafka without changing producers.

## Core architecture

### Intelligence event

The canonical unit is an immutable `IntelligenceEvent`, not a chat message. Every event contains:

- `event_type`: one of `claim`, `alert`, `anomaly`, `research`, `risk`, `system`, `human_note`, `agent_note`, `decision_request`, `decision_response`.
- `source` and `source_kind`: identity of the human/agent/system that emitted it.
- `channel`: coarse routing domain such as `market`, `risk`, `research`, `ops`, `system`, or a caller-defined bounded name.
- `thread_key`: stable semantic conversation key. Threads are projections over events rather than mutable containers.
- `assets`: zero or more canonical asset identifiers.
- `title` and `body`: concise human-readable projection.
- `severity`: integer 0–5 describing operational importance, not trade conviction.
- `urgency`: float 0–1 describing how soon the event deserves attention.
- `confidence`: optional float 0–1 preserving source-reported confidence without treating it as validated predictive probability.
- `observed_at` and `received_at`: timezone-aware ISO-8601 timestamps with `received_at >= observed_at`.
- `expires_at`: optional attention-expiry timestamp; expiration never deletes history.
- `correlation_id`: optional cross-event/workflow correlation token.
- `causation_ids`: event IDs that caused or directly motivated this event.
- `evidence_ids`: immutable external evidence/claim/receipt identifiers.
- `tags`: bounded routing/filter labels.
- `payload`: finite JSON metadata, size-bounded.

Normalization always adds `schema_version`, `execution_authorized=false` and `production_decision_authorized=false`.

`event_id` is the SHA-256 of the canonical normalized envelope. The same logical event is therefore idempotent without trusting caller-generated IDs.

### Durable journal

`IntelligenceFabric` owns an SQLite connection or path. It creates an append-only schema:

- `fabric_events`: monotonic local sequence, event ID, indexed routing columns, canonical JSON envelope.
- `fabric_assets`: event-to-asset index.
- `fabric_tags`: event-to-tag index.
- `fabric_causes`: child-to-parent event-edge index.

The public API exposes append/read/query/replay only. There is no update or delete event method.

An append transaction stores the event and indexes atomically. Re-appending the identical event returns the existing sequence with `idempotent=true`.

### Replay and consumer cursor

Every accepted event gets a monotonically increasing local `sequence`. `replay(after_sequence=N, limit=M)` returns events strictly after N in ascending sequence order. This is the Phase-1 consumer contract for crash recovery and future streaming transports.

Sequence is local journal order, not market event time. Causal/event time remains explicit in `observed_at`/`received_at`.

### Semantic threads

`thread(thread_key)` is an ordered query over immutable events. This permits human and machine participants to share one timeline while keeping structured event semantics intact.

A thread can contain claims, anomalies, risk notes, human notes and decision requests/responses. The fabric never infers that a response authorizes execution.

### Attention projection

The fabric computes `attention_score` only to rank what deserves inspection. It is explicitly not a trading score or edge estimate.

Phase-1 score is deterministic and bounded 0–100:

`severity * 12 + urgency * 30 + type_bonus`, capped at 100.

Type bonus: risk=10, anomaly=6, alert=4, decision_request=4, all others=0.

Confidence is deliberately excluded from attention ranking so uncertain severe risks are not suppressed and source confidence is not misrepresented as truth.

`inbox(as_of=..., ...)` filters out events whose `expires_at` is before `as_of` from the attention view, but history/replay continues to return them.

### Unified Intelligence bridge

`event_from_intelligence_claim(claim, claim_id=None)` accepts a normalized Unified Intelligence claim mapping and produces a `claim` event.

It preserves source, source kind, causal timestamps, semantic key, regime/horizon, evidence lineage, stance/confidence and execution-denial flags in the event payload. Its thread key is deterministic from `semantic_key`, `regime` and `horizon_seconds`.

The bridge does not re-score, calibrate, fuse or validate the claim. Those remain responsibilities of the Unified Intelligence Spine and protected downstream validation.

## Safety and integrity constraints

1. No Phase-1 event can grant execution or production-decision authority.
2. No hidden conversion of severity/urgency/attention into a trade signal.
3. Received time cannot precede observed time; malformed/nonfinite JSON fails closed.
4. Events are immutable and idempotent; no update/delete API is exposed.
5. Replay order is explicit local receipt order; it is never presented as market-time ordering.
6. Payload/title/body/tags/assets are bounded to prevent accidental unbounded journal growth.
7. The bridge preserves source identity and ancestry and does not call source confidence calibrated unless the source already proves that separately.
8. Phase 1 adds no external service, dependency, provider call, workflow, schedule, spend or credential.
9. Phase 1 does not touch UI, Brain, brain_sync, server, Atlas registry paths or broker execution.

## Phase-1 public API

- `IntelligenceEvent(...).normalized() -> dict[str, Any]`
- `IntelligenceFabric(path_or_connection=":memory:")`
- `IntelligenceFabric.publish(event) -> dict[str, Any]`
- `IntelligenceFabric.get(event_id) -> dict[str, Any] | None`
- `IntelligenceFabric.replay(after_sequence=0, limit=100) -> list[dict[str, Any]]`
- `IntelligenceFabric.query(...) -> list[dict[str, Any]]`
- `IntelligenceFabric.thread(thread_key, limit=...) -> list[dict[str, Any]]`
- `IntelligenceFabric.inbox(as_of, limit=..., ...) -> list[dict[str, Any]]`
- `event_from_intelligence_claim(claim, claim_id=None) -> IntelligenceEvent`

Returned event rows contain the durable local `sequence`, canonical `event_id`, normalized event envelope and `attention_score`.

## Deliberately deferred

After Phase 1 is independently reviewed and merged, later phases can add: authenticated WebSocket/SSE delivery, consumer acknowledgements/checkpoints, RBAC/room privacy, full-text search, agent presence, cross-host transport adapters, notification policies, source-reliability weighting, cryptographic signing, UI projections and mobile push. None of those should change the Phase-1 event identity or replay contract.
