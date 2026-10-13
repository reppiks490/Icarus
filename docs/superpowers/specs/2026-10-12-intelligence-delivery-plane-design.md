# ICARUS Durable Intelligence Delivery Plane — Phase 2 Design

Date: 2026-10-12
Status: Approved architecture, written-spec review pending
Depends on: PR #334 / Intelligence Fabric Phase 1
Base head: `01d29ce037698d930e8511a7e748b7132f187248`

## 1. Purpose

Phase 2 turns the Phase 1 Intelligence Fabric from a durable causal journal into an operational delivery plane for human and machine consumers.

The system must let ICARUS agents, research services, risk processes, observability tools, and later interactive clients consume the same canonical intelligence events with durable progress, crash-safe redelivery, explicit acknowledgements, and measurable lag. It must do this without becoming a trade-authorization path, without duplicating the existing Engine scheduler `agent_fabric`, and without binding ICARUS to a specific network broker before the delivery contract is stable.

Success means an intelligence event can be published once into the canonical Phase 1 journal and independently consumed by multiple named consumers, with each consumer able to resume from durable state after interruption and with every delivery transition auditable.

## 2. Non-goals and hard boundaries

Phase 2 does not:

- authorize orders, production decisions, or broker actions;
- edit or own `brain.py`, `brain_sync.py`, UI/aesthetic paths, provider collectors, workflows/schedulers, credentials, or Atlas registry paths;
- adopt or mutate scheduler automation IDs or state from `Icarus-engine/automation_intelligence/agent_fabric`;
- create a second canonical event store;
- make acknowledgement mean agreement with an intelligence claim;
- use consumer lag, delivery count, acknowledgement state, or retry count as trading confidence;
- require Kafka, NATS, Redis, or another external broker in Phase 2;
- introduce paid infrastructure or credentials.

The Phase 1 SQLite intelligence journal remains the source of truth. Phase 2 adds delivery state and projections only.

## 3. Architectural approach

Recommended approach: a transport-independent durable delivery layer backed by the same SQLite database as the Phase 1 journal.

The delivery plane operates over journal sequence numbers, never over wall-clock polling alone. Consumers register durable subscriptions. A subscription defines what events are eligible; a consumer state records what has been delivered, leased, acknowledged, negatively acknowledged, or made eligible for retry.

The first implementation is local and synchronous at the storage API boundary. Network transports are adapters layered on top later. This deliberately separates delivery semantics from delivery transport.

### Why not a single cursor per agent

A single cursor is too weak once a consumer can fail after receipt but before processing. Advancing the cursor on delivery risks loss; advancing only after work risks uncontrolled duplicates. The delivery plane therefore distinguishes eligibility, lease, delivery attempt, and acknowledgement.

### Why not Kafka/NATS now

A broker can provide transport and distribution, but it cannot define ICARUS-specific semantics such as authority isolation, causal event identity, replay contract, consumer state, lease expiry, and audit receipts. Those semantics must be stable first. The design keeps a broker adapter possible later without changing producers or canonical event identity.

## 4. Core concepts

### 4.1 Subscription

A durable named filter over Phase 1 events.

Minimum fields:

- `subscription_id`
- `consumer_group`
- `mode`: `broadcast` or `competing`
- optional filters: channel, event types, assets, tags, source, minimum severity
- `created_at`
- `enabled`

Filters reuse Phase 1 semantics; they do not re-score intelligence.

### 4.2 Consumer identity

A stable machine-readable identity such as `risk-monitor`, `fve-research-agent`, or `owner-console`.

A consumer may reconnect under the same identity and resume its durable state. Consumer identity is separate from event `source` identity.

### 4.3 Delivery

A delivery is a claim on one eligible journal sequence for one subscription/consumer target.

A delivery has:

- immutable journal `sequence` and `event_id`;
- monotonically increasing `attempt` for that target;
- `leased_at` and `lease_expires_at`;
- delivery status;
- acknowledgement metadata when terminal;
- no execution authority.

### 4.4 Acknowledgement

`ACK` means only: the consumer successfully processed the intelligence event under its own contract.

`NACK` means processing failed or should be retried.

Neither state means the content is true, endorsed, calibrated, or authorized for trading.

### 4.5 Lease

A bounded ownership window for an unacknowledged delivery. If a worker disappears, the lease expires and the event becomes eligible for redelivery.

Leases prevent simultaneous duplicate processing in competing-consumer mode without allowing permanent event loss.

## 5. Delivery modes

### 5.1 Broadcast

Every subscribed consumer identity receives each matching event independently.

Use cases:

- human console + risk monitor both need the same risk event;
- multiple independent models should inspect the same anomaly;
- audit/observability consumers require complete copies.

Each consumer has independent acknowledgement and lag state.

### 5.2 Competing consumer group

Exactly one active member of a consumer group leases a matching event at a time. If the lease expires or the member NACKs, another member may receive it.

Use cases:

- replicated workers performing the same expensive research task;
- horizontally scaled enrichment services where duplicate concurrent work is wasteful.

The system provides at-least-once processing semantics, not an unverifiable exactly-once claim. Idempotent event identity remains the protection against duplicate side effects.

## 6. Durable state model

Phase 2 adds tables alongside the Phase 1 journal. Suggested logical schema:

### `fabric_subscriptions`

Stores durable subscription definitions and normalized filter JSON.

### `fabric_consumers`

Stores registered consumer identities and status metadata. Registration is descriptive; it does not grant execution authority.

### `fabric_deliveries`

One durable delivery state row per event target. It binds:

- subscription
- consumer or competing group target
- journal sequence
- event ID
- attempt count
- lease state
- ACK/NACK terminal state
- timestamps

A uniqueness constraint prevents duplicate logical delivery rows for the same subscription target and event.

### `fabric_delivery_receipts`

Append-only state-transition receipts. Each receipt records the prior state, new state, attempt, consumer identity, journal identity, and timestamp. Receipts are audit evidence; mutable delivery state is the fast projection.

The append-only receipt log is required so a later overwrite of projection state cannot erase delivery history.

## 7. State machine

Allowed logical states:

`PENDING -> LEASED -> ACKED`

`PENDING -> LEASED -> NACKED -> PENDING`

`PENDING -> LEASED -> LEASE_EXPIRED -> PENDING`

No direct `PENDING -> ACKED` transition is allowed.

`ACKED` is terminal for that logical delivery target.

Lease ownership is validated on ACK/NACK. A stale worker cannot acknowledge a delivery after its lease has expired and been reassigned.

Every state transition is transactional with its receipt append.

## 8. Claiming and ordering semantics

Eligibility is determined by journal sequence plus subscription filter.

Default ordering is ascending journal sequence. This preserves the Phase 1 append order and gives reproducible replay.

The API claims at most a bounded batch. Claiming occurs inside a transaction so two workers cannot successfully lease the same competing-group delivery at the same time.

Phase 2 will not claim total event-time ordering across providers. Phase 1 already preserves `observed_at` and `received_at`; delivery order follows durable journal sequence.

## 9. Resume and replay

A consumer does not rely on an in-memory cursor.

After restart, it asks for its next eligible unacknowledged delivery. ACKed rows remain excluded. Expired leases are recoverable. NACKed deliveries become retryable according to deterministic retry rules.

Historical replay may create a new explicitly named subscription beginning at a requested journal sequence. Rewinding an existing live subscription is not silently allowed because it would obscure whether duplicate deliveries were intentional.

## 10. Retry and poison-event handling

Retries are bounded and observable.

Phase 2 should support:

- deterministic attempt counter;
- optional fixed retry delay in the core implementation;
- maximum attempts per subscription;
- `DEAD_LETTERED` terminal state only after the configured attempt ceiling;
- manual or explicit API requeue from dead-letter state, producing a new receipt.

Dead-lettering means delivery failure, not invalid market intelligence. It must not alter Phase 1 event history or source confidence.

## 11. Backpressure and lag

The delivery plane exposes operational metrics without using them as alpha inputs by default:

- pending delivery count;
- oldest pending journal sequence;
- current journal tail sequence;
- sequence lag;
- oldest pending age based on `received_at`;
- active leases;
- expired leases;
- ACK/NACK counts;
- retry and dead-letter counts.

The core API accepts bounded batch sizes. Consumers pull/claim work at their own sustainable rate.

No automatic dropping of low-priority events is permitted in Phase 2. If a consumer is slow, lag grows visibly rather than silently discarding history.

## 12. Authority and safety contract

Every delivery API response carries or inherits:

- `execution_authorized=false`
- `production_decision_authorized=false`

Registration, leasing, ACK, NACK, replay, dead-lettering, or group membership can never mutate those flags.

If a stored event violates the Phase 1 authority contract, delivery fails closed rather than projecting it downstream.

Phase 2 does not expose brokerage methods and does not call execution modules.

## 13. Public API shape

The exact Python names may change during the implementation plan, but the contract should include operations equivalent to:

- register/update a subscription definition;
- register a consumer identity;
- claim next/batch deliveries;
- ACK a leased delivery using lease identity/version;
- NACK a leased delivery with bounded error metadata;
- recover expired leases;
- inspect consumer/subscription lag;
- list delivery receipts;
- create explicit historical replay subscription;
- inspect dead-lettered deliveries;
- explicitly requeue dead-lettered delivery.

All identifiers and text fields receive strict length/type validation consistent with Phase 1.

## 14. Transactionality and concurrency

SQLite remains the Phase 2 storage implementation.

Requirements:

- WAL may be enabled for file-backed deployments where compatible;
- a bounded busy timeout is configured rather than immediate failure under brief writer contention;
- claiming is transactional;
- state transition and receipt append are atomic;
- ACK/NACK validates current lease token/version;
- uniqueness constraints enforce logical idempotency;
- foreign keys remain enabled;
- failures roll back without half-applied projection/receipt state.

The implementation must not claim distributed consensus. Multi-host SQLite use remains out of scope. A future broker/database adapter can implement the same delivery contract when ICARUS requires multi-host scale.

## 15. Transport adapters — future-compatible, not Phase 2 core

The storage contract must be usable behind future adapters:

- WebSocket for interactive consoles;
- SSE for one-way live monitoring;
- NATS or Kafka for high-throughput multi-process/multi-host transport;
- local in-process polling for research agents;
- mobile notification gateways for selected escalations.

Adapters must never become canonical storage. If an adapter disconnects, recovery comes from durable delivery state and the Phase 1 journal.

## 16. Relationship to Engine scheduler `agent_fabric`

The Engine `automation_intelligence/agent_fabric` owns scheduler-to-persistence bindings for its original automation lanes. Phase 2 does not alter that namespace, automation IDs, cadence, heartbeat, startup/finalization, or persistence protocol.

A scheduler lane may later become a consumer of the Intelligence Delivery Plane through an explicit adapter, but that is a separate integration task with its own ownership and review gate.

## 17. Testing strategy

Implementation will use TDD.

Required test classes:

1. subscription validation and canonical filter identity;
2. broadcast delivery to independent consumers;
3. competing-group single active lease;
4. ACK removes future eligibility only for the correct target;
5. NACK returns event to retry eligibility;
6. lease expiry enables safe redelivery;
7. stale lease ACK/NACK rejection;
8. crash/reopen durability using file-backed SQLite;
9. transaction rollback leaves no orphan state/receipt;
10. duplicate claim race protection using independent SQLite connections where practical;
11. bounded retries and dead-letter transition;
12. explicit dead-letter requeue receipt;
13. lag metrics correctness;
14. replay subscription begins at requested sequence without mutating live state;
15. authority flags remain false across every API;
16. Phase 1 event bytes/event IDs remain unchanged;
17. malformed stored/delivery state fails closed;
18. full existing `tests_engine` suite remains green on Linux and the existing Windows regression matrix remains green.

## 18. Proposed implementation boundaries

New backend-only files are preferred to reduce ownership collision:

- `icarus_engine/intelligence_delivery.py`
- `tests_engine/test_intelligence_delivery.py`
- optional dedicated fixture file only if needed

Phase 1 `icarus_engine/intelligence_fabric.py` may receive narrowly scoped extension points only if the implementation plan proves they are necessary. No Phase 1 schema/identity behavior may be changed casually.

No server/UI/network adapter is part of this implementation slice.

## 19. Acceptance criteria

Phase 2 is complete only when:

- multiple broadcast consumers independently receive and ACK the same Phase 1 event;
- a competing group never has two valid simultaneous leases for the same logical delivery;
- interruption before ACK causes safe redelivery after lease expiry;
- interruption after durable ACK does not redeliver that target;
- stale acknowledgements are rejected;
- delivery state and audit receipts survive process restart;
- lag/backlog is measurable without dropping events;
- authority remains false through every path;
- no scheduler/UI/Brain ownership path is modified;
- focused tests pass;
- full repository CI passes at the exact implementation head;
- independent review completes before merge.

## 20. Explicit future phases

Not part of Phase 2 implementation, but enabled by this contract:

- Phase 3: authenticated live transport adapters and machine-to-machine streaming;
- Phase 4: semantic research request/response workflows, incident rooms, escalation policy, and human read/ack state;
- Phase 5: immersive ICARUS UI projection and mobile surfaces;
- Phase 6: optional distributed broker/database backends after measured local limits justify them.

These later phases must preserve the canonical event and delivery contracts rather than replacing them with UI- or broker-specific state.
