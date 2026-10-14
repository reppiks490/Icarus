# ICARUS Live Intelligence Gateway — Phase 3 Design

Date: 2026-10-13
Status: written specification after conversational design approval; implementation not started
Depends on:
- Phase 1 Intelligence Fabric (`icarus_engine/intelligence_fabric.py`)
- Phase 2 Intelligence Delivery Plane (`icarus_engine/intelligence_delivery.py`)

## 1. Purpose

Phase 3 makes the durable Intelligence Delivery Plane reachable by live clients without weakening its provenance, lease, retry, dead-letter, replay, or authority semantics.

The gateway is a transport/authentication layer only. It is not a second event store, second delivery state machine, chat system, execution path, or intelligence source.

Success means ICARUS agents, operator clients, browser clients, and future mobile clients can consume already-deliverable intelligence in real time and durably ACK/NACK it through Phase 2.

## 2. Non-negotiable invariants

1. Phase 1 remains the canonical intelligence journal.
2. Phase 2 remains the canonical delivery state machine.
3. The gateway never mutates Phase 1 events or invents delivery state.
4. The gateway never advances a durable cursor independently of Phase 2.
5. `execution_authorized=false` always.
6. `production_decision_authorized=false` always.
7. ACK means only “this intelligence delivery was processed before lease expiry.” It is never trade approval.
8. NACK means only “this delivery was not successfully processed.” Retry/dead-letter behavior stays in Phase 2.
9. The gateway is loopback-only by default.
10. Phase 3 generates/persists no new long-lived credential.
11. No broker/order/position/strategy activation, scheduler, workflow, Brain, Atlas, provider, UI, or Field Agent behavior is modified.
12. `icarus_engine/server.py` is not edited.
13. `icarus_engine/agent.py` is not edited.
14. No Kafka/NATS/Redis/RabbitMQ or other external broker is introduced.

## 3. Existing Phase 2 contract reused unchanged

The gateway delegates to Phase 2’s existing public primitives:

- registered consumers and group membership
- immutable subscription revisions
- `claim(subscription_id, revision, consumer_id, as_of=..., lease_seconds=..., limit=...)`
- `ack(delivery_id, consumer_id, lease_token, as_of=...)`
- `nack(delivery_id, consumer_id, lease_token, as_of=..., reason=...)`
- `recover_expired(as_of=..., limit=...)`
- replay subscriptions
- metrics
- append-only receipts

Phase 3 must not reproduce Phase 2 SQL/state transitions.

## 4. Selected architecture

Create a standalone ASGI gateway:

- production module: `icarus_engine/intelligence_gateway.py`
- primary tests: `tests_engine/test_intelligence_gateway.py`
- security/protocol tests: `tests_engine/test_intelligence_gateway_security.py`

FastAPI/Uvicorn remain optional dependencies from the repository’s existing `bridge` extra. Importing the core package must not require FastAPI unless the gateway is imported/launched.

The gateway owns only:

- authentication
- ephemeral sessions/tickets
- protocol framing
- WebSocket transport
- SSE transport
- authenticated ACK/NACK/metrics HTTP endpoints
- backpressure
- heartbeat/liveness
- gateway-local observability

It does not own event identity, subscription state, delivery identity, leases, retries, dead letters, replay state, persistent cursors, or execution authority.

## 5. Process boundary

The gateway is a separate process from the existing `ThreadingHTTPServer` dashboard/API server.

```text
Phase 1 IntelligenceFabric
          |
          v
shared file-backed SQLite journal/delivery DB
          ^
          |
Phase 2 IntelligenceDeliveryPlane
          ^
          |
Phase 3 IntelligenceGateway ASGI
          |
     WS / SSE / HTTP
          |
clients / agents / future UI-mobile
```

Production launch requires a file-backed database path. No in-memory production launch.

## 6. SQLite concurrency boundary

`IntelligenceDeliveryPlane` owns a normal SQLite connection with SQLite thread affinity. Therefore Phase 3 must **not** create one Phase 2 instance on the ASGI event-loop thread and then call it from arbitrary threadpool workers.

Selected design: a dedicated bounded `DeliveryExecutor` worker owns one `IntelligenceDeliveryPlane` instance and its SQLite connection. ASGI coroutines submit typed Phase 2 operations to that worker and await results.

Requirements:

- the worker creates and closes the Phase 2 connection on its own thread
- Phase 2 calls never run on the ASGI event-loop thread
- the submission queue is bounded
- queue saturation fails/retries safely; it never grows without bound
- operations preserve Phase 2 transactional semantics
- multiple gateway **processes** may each own their own DeliveryExecutor/SQLite connection; WAL/busy-timeout and Phase 2 transactions remain authoritative across processes

A future connection pool is out of scope.

## 7. Bind, Host, Origin, and exposure policy

Default host: `127.0.0.1`.

A non-loopback bind (`0.0.0.0`, LAN address, non-loopback IPv6, public/container interface) fails closed unless an explicit `allow_remote=True`-style launch option is supplied.

Remote enablement only changes bind permission. It does not imply TLS, public-Internet safety, reverse-proxy correctness, or multi-tenant RBAC.

### Host validation

Default accepted HTTP/WebSocket Host values are limited to loopback forms such as:

- `127.0.0.1`
- `localhost`
- `[::1]`

Unexpected Host values fail closed by default to reduce DNS-rebinding exposure. Remote deployments must explicitly configure allowed hosts.

### Origin validation

Browser WebSocket requests include `Origin`. By default, any non-empty Origin is rejected unless explicitly present in a configured allowlist. Non-browser clients without Origin remain permitted after token authentication.

This protects the loopback gateway from cross-site WebSocket hijacking. Phase 3 does not enable permissive CORS.

## 8. Authentication

### 8.1 Long-lived bearer

The process receives one operator-supplied bearer token at startup. Phase 3 does not generate, rotate, persist, log, or discover it.

Authenticated HTTP endpoints require:

```http
Authorization: Bearer <token>
```

Comparison uses constant-time comparison. Missing/invalid credentials return generic `401` without revealing object existence.

### 8.2 WebSocket authentication

A WebSocket may be accepted at the transport layer, but it receives no intelligence and performs no claim until the first valid authentication frame arrives within a fixed timeout.

```json
{
  "type": "authenticate",
  "protocol": "icarus-intelligence-gateway-v1",
  "token": "...",
  "subscription_id": "...",
  "revision": 1,
  "consumer_id": "...",
  "lease_seconds": 30,
  "max_inflight": 16
}
```

The token is never echoed and never appears in logs, receipts, metrics, or error frames.

### 8.3 SSE authentication ticket

Native browser `EventSource` cannot reliably provide an Authorization header. The gateway therefore uses a short-lived one-time stream ticket rather than putting the long-lived bearer token in the URL.

Authenticated creation:

```http
POST /v1/intelligence/tickets
Authorization: Bearer <token>
```

The request identifies subscription/revision/consumer plus requested lease duration and in-flight window.

Ticket properties:

- cryptographically random opaque value
- maximum 30-second lifetime before first use
- one successful use only
- process-local memory only
- atomic consume
- no durable persistence
- no execution authority

Stream:

`GET /v1/intelligence/stream?ticket=<opaque-ticket>`

Before capacity checks the ticket store purges expired tickets. If still full, creation fails closed; it does not evict a valid unused ticket.

Process restart invalidates unused tickets only. Phase 2 durable state is unaffected.

## 9. Protocol version

`icarus-intelligence-gateway-v1`

Unsupported versions are rejected before any Phase 2 claim.

This version is independent from `icarus-intelligence-fabric-v1` and Phase 2’s internal schema so transport evolution cannot alter immutable event IDs.

## 10. Consumer identity and authorization

Gateway connection does **not** auto-register consumers or grant group membership.

A consumer must already exist in Phase 2. Competing subscriptions additionally require active Phase 2 group membership.

Possession of the transport bearer therefore cannot manufacture new durable consumer identities.

Phase 4 will define agent identity/provisioning separately.

## 11. Ephemeral session model

A successful WebSocket authentication or consumed SSE ticket creates one session with:

- `session_id` — cryptographically random process-local ID
- `transport` — `websocket` or `sse`
- `subscription_id`
- `revision`
- `consumer_id`
- `connected_at`
- `last_client_activity_at`
- `last_server_activity_at`
- `lease_seconds`
- `max_inflight`
- `inflight_delivery_ids`
- `closed`

Session state is never durable.

Multiple sessions for the same Phase 2 consumer are permitted. Phase 2 leases remain the authority preventing the same delivery from being leased twice simultaneously.

On reconnect a new session is created; no gateway cursor is restored.

## 12. Session-scoped control rule

A gateway session may ACK/NACK only a `delivery_id` currently present in **that session’s** `inflight_delivery_ids`.

This is an additional transport-scope check before Phase 2 validation. It prevents one concurrent session for the same consumer from controlling another session’s lease.

Phase 2 still performs the authoritative consumer/lease-token/expiry validation.

## 13. WebSocket endpoint

`WS /v1/intelligence/ws`

Successful authentication returns:

```json
{
  "type": "hello",
  "protocol": "icarus-intelligence-gateway-v1",
  "session_id": "...",
  "subscription_id": "...",
  "revision": 1,
  "consumer_id": "...",
  "heartbeat_seconds": 10,
  "lease_seconds": 30,
  "max_inflight": 16,
  "server_time": "...Z",
  "execution_authorized": false,
  "production_decision_authorized": false
}
```

Then the bounded claim/send loop begins.

## 14. WebSocket server frames

### Delivery

```json
{
  "type": "delivery",
  "session_id": "...",
  "delivery_id": "...",
  "event_id": "...",
  "journal_sequence": 42,
  "attempt": 1,
  "lease_token": "...",
  "lease_expires_at": "...Z",
  "event": {"...": "canonical Phase 1 envelope"},
  "execution_authorized": false,
  "production_decision_authorized": false
}
```

The lease token is a short-lived delivery capability required by Phase 2 ACK/NACK. It is never logged.

### ACK result

```json
{
  "type": "ack_result",
  "request_id": "...",
  "delivery_id": "...",
  "state": "ACKED",
  "server_time": "...Z",
  "execution_authorized": false,
  "production_decision_authorized": false
}
```

### NACK result

Same shape with `type=nack_result` and Phase 2’s resulting `PENDING` or `DEAD_LETTERED` state.

### Heartbeat

```json
{
  "type": "heartbeat",
  "session_id": "...",
  "server_time": "...Z",
  "inflight": 3,
  "max_inflight": 16,
  "sequence_lag": 7,
  "execution_authorized": false,
  "production_decision_authorized": false
}
```

### Flow

```json
{
  "type": "flow",
  "paused": true,
  "reason": "inflight_window_full",
  "inflight": 16,
  "max_inflight": 16,
  "execution_authorized": false,
  "production_decision_authorized": false
}
```

### Error

```json
{
  "type": "error",
  "request_id": "optional",
  "code": "LEASE_EXPIRED",
  "message": "delivery lease is no longer valid",
  "retryable": true,
  "execution_authorized": false,
  "production_decision_authorized": false
}
```

No stack traces, SQL, file paths, bearer values, tickets, lease tokens, or unrelated object-existence details may appear in external errors.

## 15. WebSocket client frames

After authentication v1 accepts only:

### ACK

```json
{
  "type": "ack",
  "request_id": "...",
  "delivery_id": "...",
  "lease_token": "..."
}
```

### NACK

```json
{
  "type": "nack",
  "request_id": "...",
  "delivery_id": "...",
  "lease_token": "...",
  "reason": {"code": "consumer_processing_failed"}
}
```

### Ping

```json
{"type":"ping","request_id":"..."}
```

Arbitrary publication, subscription creation, group mutation, replay creation, dead-letter requeue, execution commands, and free-form agent messaging are rejected.

## 16. Control-request idempotency semantics

Phase 2 ACK/NACK is lease-state based, not request-ID idempotent. Phase 3 must not pretend otherwise.

`request_id` is correlation only.

If a durable ACK/NACK commits but the network response is lost, the client must reconnect/reconcile through Phase 2 state rather than blindly replay the old control frame. A repeated stale ACK/NACK may correctly return `DELIVERY_STATE_INVALID`, `LEASE_EXPIRED`, or equivalent.

Adding durable operation IDs/idempotent control receipts would change the delivery contract and is deferred.

## 17. SSE endpoint

`GET /v1/intelligence/stream?ticket=<one-time-ticket>`

Content type: `text/event-stream`.

Event names:

- `hello`
- `delivery`
- `heartbeat`
- `flow`
- `error`

Payload fields mirror WebSocket server frames.

## 18. SSE HTTP ACK/NACK

Endpoints:

- `POST /v1/intelligence/ack`
- `POST /v1/intelligence/nack`

Both require the long-lived bearer token **and** an active SSE `session_id`.

ACK:

```json
{
  "session_id": "...",
  "consumer_id": "...",
  "delivery_id": "...",
  "lease_token": "..."
}
```

NACK:

```json
{
  "session_id": "...",
  "consumer_id": "...",
  "delivery_id": "...",
  "lease_token": "...",
  "reason": {"code": "consumer_processing_failed"}
}
```

Before calling Phase 2 the gateway verifies:

- session exists and is open
- session transport is SSE
- session consumer matches `consumer_id`
- `delivery_id` is in that session’s in-flight set

After successful Phase 2 ACK/NACK, the gateway removes the delivery from that session’s in-flight set immediately, releasing backpressure capacity.

There is no separate HTTP ACK ledger.

## 19. Claim/send loop and backpressure

For each active session:

1. `available = max_inflight - current_inflight`.
2. If `available <= 0`, do not call Phase 2 `claim`.
3. Otherwise call Phase 2 `claim` with `limit <= available`.
4. Emit each returned delivery once for that lease issuance on that session.
5. Add its `delivery_id` to the session in-flight set.
6. Remove it only after successful ACK/NACK, observed expiry recovery, or session teardown.
7. Teardown never ACKs/NACKs outstanding deliveries.
8. Phase 2 expiry/retry/dead-letter logic decides later disposition.

Hard protocol bounds:

- `max_inflight`: 1..256
- `lease_seconds`: 5..300

Out-of-range values are rejected before claim.

There is no unbounded application delivery queue. The DeliveryExecutor request queue is also bounded.

An idle poll delay is required; no CPU-spin claim loop.

## 20. Lease-expiry recovery

A bounded periodic gateway task submits `recover_expired(as_of=..., limit=...)` through the DeliveryExecutor.

Recovered delivery IDs are reconciled out of all local in-flight sets that contain them.

The gateway never extends leases. Lease renewal is deferred.

Multiple gateway processes may run recovery because Phase 2 uses transactional state as authority.

## 21. Heartbeats/liveness

Default heartbeat: 10 seconds.

The server sends heartbeats when idle. WebSocket `ping` receives a heartbeat/pong-equivalent with server time.

A bounded client-inactivity timeout may close a WebSocket. Closure changes no durable delivery state.

SSE emits heartbeat events/comments to keep idle streams visibly alive.

## 22. Resume semantics

There is no gateway cursor and no client-supplied “last seen sequence” authority.

Reconnect:

1. establish a new authenticated session
2. use the same immutable subscription/revision/consumer
3. ask Phase 2 for claimable work
4. Phase 2 decides pending/leased/ACKed/retry/dead-letter state

This prevents split-brain cursor state.

## 23. Time semantics

All gateway-generated times are UTC ISO-8601 with timezone, normalized to `Z`.

Every Phase 2 call receives gateway server UTC as `as_of`.

Client timestamps may be diagnostic only. They never decide lease validity, ACK/NACK validity, retry eligibility, or recovery.

## 24. Error mapping

Minimum stable external codes:

- `AUTH_FAILED`
- `HOST_REJECTED`
- `ORIGIN_REJECTED`
- `PROTOCOL_UNSUPPORTED`
- `INVALID_FRAME`
- `INVALID_REQUEST`
- `SESSION_INVALID`
- `DELIVERY_NOT_IN_SESSION`
- `UNKNOWN_CONSUMER`
- `SUBSCRIPTION_UNAVAILABLE`
- `CONSUMER_NOT_AUTHORIZED_FOR_SUBSCRIPTION`
- `LEASE_EXPIRED`
- `LEASE_TOKEN_INVALID`
- `DELIVERY_STATE_INVALID`
- `GATEWAY_BUSY`
- `DELIVERY_STORE_UNAVAILABLE`
- `INTERNAL_ERROR`

Gateway prevalidation should generate stable codes where possible. Raw Phase 2 exception strings must not be exposed directly if doing so leaks internal details.

## 25. Observability

### Unauthenticated health

`GET /healthz`

Returns only process health, protocol version, uptime, and coarse delivery-store reachability. No consumer/subscription/delivery data.

### Authenticated metrics

`GET /v1/intelligence/metrics?subscription_id=...&revision=...`

Delegates durable metrics to Phase 2 and may add explicitly ephemeral gateway metrics:

- active sessions
- WebSocket sessions
- SSE sessions
- local in-flight count
- unused ticket count
- authentication failures
- Host/Origin rejections
- protocol errors
- DeliveryExecutor queue depth/saturation count

Ephemeral counters reset on restart.

## 26. Logging/redaction

Logs may contain session ID, consumer ID, subscription/revision, delivery ID, event ID, lifecycle state, and protocol error code.

Logs must never contain:

- bearer token
- one-time ticket
- lease token
- full event payload by default
- raw NACK reason by default

A tested redaction helper is required.

## 27. Resource limits

Required limits:

- authentication/control JSON: <=32 KiB
- WebSocket text frame: <=64 KiB
- NACK reason remains under Phase 2’s <=32 KiB finite-JSON contract
- active unused tickets: <=1024
- active sessions: finite/configurable, default 256
- DeliveryExecutor queue: finite/configurable

Oversized input is rejected before durable operations.

## 28. Failure behavior

### Store unavailable at startup

Fail startup. Do not expose a gateway that cannot durably control delivery.

### Store fails during operation

- stop claiming
- return retryable sanitized errors where possible
- never synthesize ACK/NACK success
- close affected sessions if safe continuation cannot be guaranteed

### Client disconnect

- drop ephemeral session state
- do not ACK/NACK outstanding delivery
- Phase 2 lease expiry governs retry

### Gateway crash/restart

- sessions/tickets disappear
- Phase 1 and Phase 2 durable state survives
- expired leases recover after restart

### Phase 1 integrity failure

Phase 2 already fails closed during claim. Gateway sends no forged replacement event.

## 29. Transport equivalence

Transport choice must not change durable semantics.

Under equivalent initial durable state (tested independently, not by racing two transports for the same live lease), WebSocket and SSE must expose the same Phase 2 delivery/event identity and authority metadata.

Both transports:

- use Phase 2 claim
- require the active Phase 2 lease token for control
- use the same retry/dead-letter budget
- resume from Phase 2 state

Only framing/control transport differs.

## 30. Test contract

Implementation is TDD-first.

### Security/authentication

- HTTP bearer success/failure
- constant-time token comparison helper
- Host rejection before sensitive routing
- WebSocket Origin rejection by default
- configured Origin allowlist success
- no intelligence before WebSocket auth
- auth timeout closes without claim
- token/ticket/lease-token redaction
- one-time ticket expiry/reuse rejection
- bounded ticket store and purge-before-capacity behavior
- remote bind rejected by default
- unsupported protocol rejected before claim

### Session/control scoping

- consumer is not auto-registered
- ACK/NACK only for that session’s in-flight delivery
- one session cannot control another session’s lease even with the same consumer ID
- SSE HTTP ACK/NACK requires active matching SSE session
- successful SSE ACK/NACK immediately frees its in-flight slot

### Delivery semantics

- delivery frame comes directly from Phase 2 claim result
- ACK calls Phase 2 with exact consumer/delivery/token
- NACK calls Phase 2 with exact consumer/delivery/token/reason
- failed Phase 2 operation never returns protocol success
- disconnect never auto-ACKs
- reconnect resumes from Phase 2 durable state
- broadcast and competing authorization stay enforced by Phase 2

### Backpressure/executor

- no claim when in-flight is full
- claim limit never exceeds free slots
- no unbounded session delivery queue
- DeliveryExecutor queue is bounded
- Phase 2 connection is created/used/closed on its owning worker thread
- ASGI event loop is not blocked by synchronous Phase 2 calls

### Lease/recovery

- expired lease cannot ACK
- recovery returns to Phase 2 retry/dead-letter flow
- recovered deliveries leave session-local in-flight sets

### Transport equivalence

- independently seeded WS and SSE cases expose matching delivery/event identity
- all applicable protocol outputs preserve both false authority flags

### Failure/hardening

- DB startup failure prevents launch
- runtime DB failure does not synthesize success
- malformed/oversized frames rejected
- NaN/Infinity rejected where applicable
- external errors contain no stack/SQL/path/secret leakage
- lost ACK response semantics are documented/tested as non-idempotent correlation behavior

### Regression

- all Phase 1 Intelligence Fabric tests green
- all Phase 2 Delivery Plane tests green
- full Linux `tests_engine` green
- Windows regression matrix green

## 31. Planned file boundaries

Expected implementation scope after plan approval:

- `icarus_engine/intelligence_gateway.py`
- `tests_engine/test_intelligence_gateway.py`
- `tests_engine/test_intelligence_gateway_security.py`
- optional narrowly scoped gateway launcher/CLI test if the plan proves one is needed

Explicitly excluded:

- `icarus_engine/server.py`
- `icarus_engine/dashboard.html`
- `icarus_engine/*-ui.js`
- `icarus_engine/agent.py`
- `icarus_engine/brain.py`
- `icarus_engine/brain_sync.py`
- workflows/schedules
- providers/collectors
- broker/execution modules
- Atlas `research_allocation/**`

Any `pyproject.toml` launcher/entry-point edit must be separately explicit in the implementation plan; it is not implicitly approved here.

## 32. Deferred to Phase 4+

Not part of Phase 3:

- agent identity provisioning/signatures
- human/agent rooms
- presence/typing
- free-form chat
- structured request/response conversations
- delegation/capability advertisement
- agent-to-agent tasks
- inbound arbitrary intelligence publication
- UI/mobile implementation or push
- TLS termination/public Internet exposure
- multi-tenant RBAC
- lease renewal
- Kafka/NATS adapters
- durable ACK/NACK operation idempotency keys

Phase 4 will define structured machine/human exchange as canonical Phase 1 events, routed by Phase 2 and carried over Phase 3. It must not bypass these layers.

## 33. Acceptance criteria

Phase 3 is complete only when:

1. A pre-registered consumer receives a real Phase 1 event through Phase 2 over WebSocket.
2. Equivalent delivery is streamable over SSE.
3. ACK/NACK is performed by Phase 2 only.
4. Session control cannot operate on another session’s in-flight lease.
5. Disconnect/restart loses no durable position.
6. Backpressure and executor queues are bounded.
7. Authentication gates all sensitive delivery/control operations.
8. SSE tickets keep the long-lived bearer out of stream URLs.
9. Host/Origin protections are fail-closed by default.
10. Non-loopback bind fails closed by default.
11. Applicable outputs preserve both false authority flags.
12. No Phase 1 event identity changes.
13. No Phase 2 delivery semantics changes.
14. Existing server, Field Agent, UI, Brain, scheduler, provider, workflow, broker, and execution behavior remain unchanged.
15. Focused Phase 3 tests pass.
16. Phase 1 and Phase 2 regressions pass.
17. Exact-head Linux and Windows CI pass.
18. Independent review completes before merge.
