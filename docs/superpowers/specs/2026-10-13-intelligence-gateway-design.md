# ICARUS Live Intelligence Gateway — Phase 3 Design

Date: 2026-10-13
Status: proposed written specification after conversational design approval
Depends on:
- Phase 1 Intelligence Fabric (`icarus_engine/intelligence_fabric.py`)
- Phase 2 Intelligence Delivery Plane (`icarus_engine/intelligence_delivery.py`)

## 1. Purpose

Phase 3 makes the durable Intelligence Delivery Plane reachable by live clients without weakening its delivery, provenance, retry, lease, or authority semantics.

The gateway is a transport and authentication layer only. It must not become a second event store, a second delivery state machine, a chat system, an execution path, or a source of market intelligence.

The intended result is a low-latency network surface through which ICARUS agents, operator clients, browser clients, and future mobile clients can consume already-authorized-for-delivery intelligence in real time and acknowledge processing durably through Phase 2.

## 2. Non-negotiable invariants

1. Phase 1 remains the canonical intelligence journal.
2. Phase 2 remains the canonical delivery state machine.
3. The gateway never mutates Phase 1 events.
4. The gateway never invents delivery state.
5. The gateway never advances a durable cursor independently of Phase 2 ACK state.
6. `execution_authorized` is always `false`.
7. `production_decision_authorized` is always `false`.
8. An ACK means only “this intelligence delivery was processed by this consumer before lease expiry.” It is never trade approval.
9. A NACK means only “this delivery was not successfully processed.” Retry/dead-letter behavior remains Phase 2’s responsibility.
10. The gateway is loopback-only by default.
11. No new long-lived credential is generated or persisted by Phase 3.
12. No broker, order, position, strategy activation, scheduler, workflow, Brain, Atlas, provider, UI, or Field Agent behavior is modified by this phase.
13. `icarus_engine/server.py` is not edited by Phase 3.
14. `icarus_engine/agent.py` / the existing Field Agent contract is not edited by Phase 3.
15. No Kafka, NATS, Redis, RabbitMQ, or other external broker is introduced.

## 3. Existing contract reused unchanged

Phase 2 already provides the authoritative primitives the gateway must call:

- consumer registration
- group membership
- immutable subscription revisions
- `claim(subscription_id, revision, consumer_id, as_of=..., lease_seconds=..., limit=...)`
- `ack(delivery_id, consumer_id, lease_token, as_of=...)`
- `nack(delivery_id, consumer_id, lease_token, as_of=..., reason=...)`
- lease-expiry recovery
- dead-letter handling
- replay subscriptions
- metrics
- append-only receipts

Phase 3 must call those APIs rather than reproduce their SQL/state transitions.

## 4. Selected architecture

Create a standalone ASGI gateway module:

- intended production module: `icarus_engine/intelligence_gateway.py`
- intended primary tests: `tests_engine/test_intelligence_gateway.py`
- intended security/protocol tests: `tests_engine/test_intelligence_gateway_security.py`

The gateway exposes a FastAPI application but FastAPI/Uvicorn remain optional runtime dependencies under the repository’s existing `bridge` extra. Core package imports must not require FastAPI unless the gateway module is imported or launched.

The gateway owns only:

- authentication
- ephemeral connection/session state
- protocol framing
- WebSocket transport
- SSE transport
- small authenticated HTTP control endpoints
- bounded in-flight windows
- heartbeat/liveness
- gateway-local observability

It does not own:

- event identity
- subscriptions
- delivery identity
- lease identity
- retries
- dead-letter policy
- replay semantics
- persistent cursors
- execution authority

## 5. Process boundary

The gateway is a separate process from the existing standard-library `ThreadingHTTPServer` dashboard/API server.

Default launch model:

```text
ICARUS runtime / IntelligenceFabric / IntelligenceDeliveryPlane
                         |
                         | shared durable SQLite path
                         v
               IntelligenceGateway ASGI process
                         |
                 WebSocket / SSE / HTTP
                         |
          agents / operator / future UI/mobile
```

The gateway opens the same file-backed SQLite database through its own `IntelligenceDeliveryPlane` instance. Phase 2’s WAL and busy-timeout behavior remains authoritative for contention.

The gateway must not use an in-memory database in production launch mode.

## 6. Bind and exposure policy

Default host: `127.0.0.1`.

Default port: implementation-configurable; the design does not require reuse of the existing engine server port.

A non-loopback bind (`0.0.0.0`, LAN address, IPv6 non-loopback, container-public interface) must fail closed unless an explicit `allow_remote=True` or equivalent launch flag is supplied.

Remote enablement in Phase 3 only changes bind permission. It does not create TLS, reverse-proxy, public-Internet, or multi-tenant guarantees. Those remain deployment responsibilities and are outside this phase.

## 7. Authentication model

### 7.1 Long-lived token

The process receives one operator-supplied bearer token at startup. Phase 3 does not generate, rotate, persist, or discover it.

HTTP control endpoints require:

```http
Authorization: Bearer <token>
```

Comparison must use constant-time comparison.

Missing or invalid bearer credentials return `401` and must not reveal whether a subscription/consumer/delivery exists.

### 7.2 WebSocket authentication

A WebSocket connection is accepted at the transport level but must remain unauthenticated and receive no intelligence until the client sends an authentication frame within a short fixed timeout.

Client first frame:

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

The token is never echoed back and must not appear in gateway logs, receipts, error bodies, metrics, or delivery frames.

Authentication failure closes the socket with an application-defined policy-violation close code after a generic error frame.

### 7.3 SSE authentication

Native browser `EventSource` cannot reliably set an Authorization header. Therefore the gateway uses a short-lived one-time stream ticket rather than putting the long-lived bearer token in the URL.

Authenticated ticket creation:

```http
POST /v1/intelligence/tickets
Authorization: Bearer <token>
```

Request body identifies `subscription_id`, `revision`, `consumer_id`, requested lease duration, and in-flight window.

The response returns a cryptographically random opaque ticket with:

- maximum lifetime: 30 seconds before first use
- one successful use only
- process-local memory only
- no durable persistence
- no execution authority

The client then opens:

```text
GET /v1/intelligence/stream?ticket=<opaque-ticket>
```

The ticket must be consumed atomically. Reuse, expiry, or unknown tickets return a generic authentication failure.

A process restart invalidates unused tickets. Durable delivery position is unaffected because Phase 2 remains canonical.

## 8. Protocol version

Gateway protocol version:

`icarus-intelligence-gateway-v1`

The server rejects unsupported protocol versions before leasing any event.

Protocol versioning is independent from:

- `icarus-intelligence-fabric-v1`
- the Phase 2 internal delivery schema

This allows transport evolution without changing immutable Phase 1 event IDs.

## 9. Session model

A successful authenticated WebSocket or consumed SSE ticket creates one ephemeral gateway session.

Session fields:

- `session_id`: cryptographically random, process-local identifier
- `transport`: `websocket` or `sse`
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

Session state is not durable. Losing a session must never lose a durable event or ACK because all durable state lives in Phase 2.

A reconnect creates a new session ID and resumes by asking Phase 2 for claimable work for the same immutable subscription revision and consumer.

## 10. Consumer identity

The gateway does not auto-register arbitrary consumer IDs as a side effect of connecting.

A consumer must already exist in Phase 2. For a competing subscription, the consumer must already have active membership in the target group.

This avoids turning possession of a transport token into permission to manufacture new durable consumer identities.

Future Phase 4 agent identity and provisioning rules remain separate.

## 11. WebSocket endpoint

Endpoint:

`WS /v1/intelligence/ws`

After successful authentication the server sends:

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

The server then enters a bounded claim/send loop.

## 12. WebSocket server frames

### 12.1 Delivery

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

The lease token is required because Phase 2 validates ACK/NACK against the active lease. It is scoped to the delivery and expires with the lease.

### 12.2 ACK result

```json
{
  "type": "ack_result",
  "request_id": "client-generated-id",
  "delivery_id": "...",
  "state": "ACKED",
  "server_time": "...Z",
  "execution_authorized": false,
  "production_decision_authorized": false
}
```

### 12.3 NACK result

Equivalent shape with `type=nack_result` and the Phase 2 resulting state (`PENDING` or `DEAD_LETTERED`).

### 12.4 Heartbeat

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

### 12.5 Flow state

The server may emit:

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

### 12.6 Error

```json
{
  "type": "error",
  "request_id": "optional-client-request-id",
  "code": "LEASE_EXPIRED",
  "message": "delivery lease is no longer valid",
  "retryable": true,
  "execution_authorized": false,
  "production_decision_authorized": false
}
```

Errors must not include stack traces, SQL, file paths, bearer tokens, ticket values, or unrelated delivery/subscription existence information.

## 13. WebSocket client frames

After authentication only these client frame types are accepted in Phase 3:

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
{
  "type": "ping",
  "request_id": "..."
}
```

Arbitrary event publication, subscription creation, group mutation, replay creation, dead-letter requeue, execution commands, and free-form agent messaging are rejected in Phase 3.

## 14. SSE endpoint

Endpoint:

`GET /v1/intelligence/stream?ticket=<one-time-ticket>`

Content type:

`text/event-stream`

SSE event names:

- `hello`
- `delivery`
- `heartbeat`
- `flow`
- `error`

SSE delivery payloads use the same JSON fields as WebSocket server frames.

SSE itself is server-to-client only. Durable completion uses authenticated HTTP control calls.

## 15. SSE / HTTP ACK and NACK

Endpoints:

- `POST /v1/intelligence/ack`
- `POST /v1/intelligence/nack`

Both require the long-lived bearer token.

ACK request:

```json
{
  "consumer_id": "...",
  "delivery_id": "...",
  "lease_token": "..."
}
```

NACK request:

```json
{
  "consumer_id": "...",
  "delivery_id": "...",
  "lease_token": "...",
  "reason": {"code": "consumer_processing_failed"}
}
```

The HTTP layer calls Phase 2 directly and returns the Phase 2 resulting state plus the two false authority flags.

The gateway must not maintain a separate HTTP ACK ledger.

## 16. Claim and send loop

For each active session:

1. Calculate `available = max_inflight - current_inflight`.
2. If `available <= 0`, do not call Phase 2 `claim`.
3. Otherwise call Phase 2 `claim` with `limit <= available`.
4. Emit each returned delivery exactly once for that lease issuance on that session.
5. Add its `delivery_id` to the session-local in-flight set.
6. Remove it from the in-flight set only after:
   - successful ACK,
   - successful NACK,
   - observed lease expiry/recovery,
   - or session teardown.
7. Session teardown does not ACK or NACK outstanding deliveries.
8. Expired outstanding leases are recovered by Phase 2 and later redelivered according to its retry budget.

The gateway must not repeatedly call `claim` in a CPU-spin loop when no work exists. An idle poll delay is required.

## 17. Lease-expiry recovery

The gateway may run a bounded periodic recovery loop that calls Phase 2 `recover_expired(as_of=..., limit=...)`.

Recovery must be safe with multiple gateway processes because Phase 2 owns transactional state transitions.

Gateway session state must reconcile recovered delivery IDs out of local in-flight sets when observed.

The gateway never extends a lease. A client that requires more processing time must use a future protocol revision; lease renewal is explicitly deferred.

## 18. Backpressure

Defaults are implementation choices within these hard bounds:

- `max_inflight` minimum: 1
- `max_inflight` maximum: 256
- `lease_seconds` minimum: 5
- `lease_seconds` maximum: 300

The server clamps or rejects out-of-range client requests before any claim.

There is no unbounded application queue between Phase 2 and the network socket.

A slow client therefore consumes only its finite Phase 2 leases and then stops receiving more work until capacity returns.

## 19. Heartbeats and liveness

Default heartbeat cadence: 10 seconds.

The server sends heartbeats even when no deliveries are available.

WebSocket clients may send `ping`; the server responds with a heartbeat or pong-equivalent frame containing server time.

A WebSocket client that sends no valid frame for a bounded liveness timeout may be disconnected. Disconnect does not mutate durable delivery state.

SSE liveness is represented by periodic heartbeat events/comment frames so intermediaries do not treat an idle stream as dead.

## 20. Resume semantics

There is no separate gateway cursor.

Reconnect behavior:

1. authenticate a new session
2. use the same immutable `subscription_id`, `revision`, and `consumer_id`
3. ask Phase 2 for claimable deliveries
4. Phase 2 decides what is pending, already ACKed, still leased, retry-eligible, or dead-lettered

This prevents split-brain cursor state.

A client must never supply “last seen sequence” as authority to skip Phase 2 work.

## 21. Time semantics

All gateway-generated timestamps are UTC ISO-8601 with timezone and `Z` normalization.

For every call into Phase 2, the gateway supplies its current server UTC time as `as_of`.

Client timestamps may be accepted for diagnostics only and must never replace server time for lease validity, ACK/NACK validation, retry timing, or recovery.

## 22. Error mapping

Phase 2 validation failures are translated into stable protocol error codes.

Minimum codes:

- `AUTH_FAILED`
- `PROTOCOL_UNSUPPORTED`
- `INVALID_FRAME`
- `INVALID_REQUEST`
- `UNKNOWN_CONSUMER`
- `SUBSCRIPTION_UNAVAILABLE`
- `CONSUMER_NOT_AUTHORIZED_FOR_SUBSCRIPTION`
- `LEASE_EXPIRED`
- `LEASE_TOKEN_INVALID`
- `DELIVERY_STATE_INVALID`
- `INTERNAL_ERROR`

The external message is deliberately less specific than internal exceptions when specificity could leak object existence across consumers.

## 23. Gateway-local observability

Read-only health endpoint:

`GET /healthz`

It reports only process health, protocol version, uptime, and whether the delivery database can be opened/read.

Authenticated metrics endpoint:

`GET /v1/intelligence/metrics?subscription_id=...&revision=...`

It delegates durable metrics to Phase 2 and may add gateway-local fields:

- active session count
- WebSocket session count
- SSE session count
- session-local in-flight total
- ticket count
- authentication failure count
- protocol error count

Gateway-local counters reset on process restart and must be labelled as ephemeral.

## 24. Logging and secrets

Logs may include:

- session ID
- consumer ID
- subscription ID/revision
- delivery ID
- event ID
- connection lifecycle
- protocol error code

Logs must never include:

- bearer token
- one-time ticket
- lease token
- full event payload by default
- raw NACK reason by default

The implementation must provide a redaction helper covered by tests.

## 25. Resource limits

Hard request/frame limits are required.

Recommended specification limits:

- authentication/control JSON body: <= 32 KiB
- WebSocket text frame: <= 64 KiB
- NACK reason: remains bounded by Phase 2’s 32 KiB finite-JSON contract
- maximum active one-time tickets: 1024
- maximum active sessions: configurable, finite, default 256

Oversized input fails before parsing into durable operations.

## 26. Failure behavior

### Delivery DB unavailable at startup

Fail startup; do not expose a gateway that cannot durably ACK/NACK.

### DB becomes unavailable during operation

- stop claiming new deliveries
- return retryable transport errors where possible
- do not synthesize ACK/NACK success
- preserve existing socket process state only long enough to report failure/close

### Client disconnect

- close session state
- do not ACK/NACK outstanding deliveries
- allow Phase 2 lease expiry/recovery to determine retry

### Gateway crash/restart

- ephemeral sessions/tickets are lost
- Phase 1 events remain intact
- Phase 2 delivery/lease state remains intact
- expired leases are recovered after restart

### Malformed Phase 1 event

Phase 2 already fails closed during `claim`; the gateway propagates a generic integrity/internal error and sends no forged replacement event.

## 27. Concurrency model

The ASGI layer is asynchronous, but SQLite/Phase 2 calls are synchronous.

The implementation must not block the event loop with long-running claim/recovery loops. Durable calls should execute through a bounded worker/thread mechanism or equivalent FastAPI/Starlette concurrency primitive.

Per-session send ordering must preserve the order returned by Phase 2 for a claim batch.

ACK/NACK for separate deliveries may execute concurrently, but Phase 2 transactional locking remains authoritative.

## 28. SSE and WebSocket equivalence

Transport choice must not change durable semantics.

Given the same subscription revision and consumer:

- both transports use Phase 2 claim
- both expose the same delivery IDs/event IDs
- both require the same active lease token for ACK/NACK
- both are subject to the same retry/dead-letter budget
- both resume from Phase 2 state after reconnect

Only framing and ACK transport differ.

## 29. Testing contract

Implementation will be TDD-first.

Required test categories:

### Authentication/security

- HTTP bearer success/failure
- constant-time comparison helper behavior
- WebSocket sends no intelligence before authentication
- WebSocket auth timeout closes without claiming
- long-lived token never appears in frames/log strings
- one-time SSE tickets expire
- tickets are one-use
- ticket store is bounded
- remote bind rejected by default
- unsupported protocol rejected before claim

### Delivery semantics

- delivery frame is derived from Phase 2 claim result
- ACK calls Phase 2 ACK with exact consumer/delivery/lease token
- NACK calls Phase 2 NACK with exact fields
- failed ACK/NACK never returns success
- disconnect never auto-ACKs
- reconnect resumes from Phase 2 state
- broadcast ownership remains enforced
- competing membership remains enforced

### Backpressure

- no claim when in-flight window is full
- claim limit never exceeds free slots
- slow consumer cannot cause unbounded queue growth
- ACK/NACK frees one in-flight slot

### Lease/recovery

- expired lease cannot ACK through gateway
- recovery returns delivery to Phase 2 retry/dead-letter flow
- session-local in-flight is reconciled after recovery

### Transport equivalence

- WebSocket and SSE produce equivalent delivery identity/event identity
- authority flags remain false on all protocol responses

### Failure/hardening

- DB startup failure prevents launch
- runtime DB error does not synthesize delivery success
- malformed frames are bounded and rejected
- oversized frames/bodies rejected
- NaN/Infinity JSON rejected where applicable
- no stack traces/secrets in external errors

### Regression

- all Phase 1 Intelligence Fabric tests remain green
- all Phase 2 Intelligence Delivery Plane tests remain green
- full `tests_engine` Linux CI remains green
- Windows regression matrix remains green

## 30. Planned file boundaries

Expected Phase 3 implementation scope after plan approval:

- `icarus_engine/intelligence_gateway.py`
- `tests_engine/test_intelligence_gateway.py`
- `tests_engine/test_intelligence_gateway_security.py`
- optional narrowly-scoped gateway launcher/CLI test file if implementation requires one

The following remain explicitly excluded unless a later approved spec changes ownership:

- `icarus_engine/server.py`
- `icarus_engine/dashboard.html`
- `icarus_engine/*-ui.js`
- `icarus_engine/agent.py`
- `icarus_engine/brain.py`
- `icarus_engine/brain_sync.py`
- workflows/schedules
- provider/collector modules
- broker/execution modules
- Atlas `research_allocation/**`

If a launcher requires changing `pyproject.toml`, that change must be called out explicitly in the implementation plan; it is not implicitly approved by this spec.

## 31. Deferred to Phase 4 or later

Not part of Phase 3:

- agent identity provisioning
- agent cryptographic identity/signatures
- human/agent rooms
- presence
- typing state
- free-form chat
- request/response conversations
- delegation
- agent capability advertisements
- agent-to-agent tasks
- inbound arbitrary intelligence publication
- UI implementation
- mobile push notifications
- TLS termination
- public Internet exposure
- multi-tenant RBAC
- lease renewal
- Kafka/NATS transport adapters

Phase 4 will define structured machine/human intelligence exchange as canonical Phase 1 events delivered through Phase 2 and carried over Phase 3. It must not bypass these layers.

## 32. Acceptance criteria

Phase 3 is complete only when all of the following are true:

1. A pre-registered consumer can receive a real Phase 1 event through Phase 2 over WebSocket.
2. The same class of delivery can be streamed over SSE.
3. ACK/NACK transitions are performed by Phase 2, not duplicated by the gateway.
4. Disconnect/restart does not lose durable delivery position.
5. Backpressure prevents unbounded claim/send growth.
6. Authentication gates all delivery and control operations.
7. One-time SSE tickets do not expose the long-lived token in stream URLs.
8. Non-loopback binding fails closed by default.
9. Every external response preserves both false authority flags where authority metadata is applicable.
10. No Phase 1 event identity changes.
11. No Phase 2 delivery semantics change.
12. No existing `server.py`, Field Agent, UI, Brain, scheduler, provider, workflow, broker, or execution behavior changes.
13. Focused Phase 3 tests pass.
14. Phase 1 and Phase 2 regression tests pass.
15. Exact-head Linux and Windows repository CI pass.
16. Independent review completes before merge.
