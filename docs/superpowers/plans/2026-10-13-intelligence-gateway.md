# ICARUS Live Intelligence Gateway Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone authenticated ASGI gateway that carries Phase 2 durable intelligence deliveries over WebSocket and SSE without duplicating Phase 1 event state or Phase 2 delivery semantics.

**Architecture:** `icarus_engine/intelligence_gateway.py` is a thin transport/runtime layer over the existing `IntelligenceDeliveryPlane`. A dedicated worker thread owns the Phase 2 SQLite connection; ASGI code submits bounded typed operations to that worker. Ephemeral sessions and one-time SSE tickets exist only in gateway memory, while claim/ACK/NACK/retry/dead-letter/replay state remains entirely in Phase 2.

**Tech Stack:** Python 3.11; FastAPI/Starlette; Uvicorn-compatible ASGI; stdlib `asyncio`, `threading`, `queue`, `concurrent.futures`, `hmac`, `secrets`, `ipaddress`; existing SQLite-backed `IntelligenceDeliveryPlane`; pytest/httpx/FastAPI TestClient from the existing `bridge` extra.

**Spec:** `docs/superpowers/specs/2026-10-13-intelligence-gateway-design.md`

## Global Constraints

- Phase 1 remains the canonical intelligence journal.
- Phase 2 remains the canonical delivery state machine; Phase 3 must use its public methods and must not reproduce its SQL/state transitions.
- `execution_authorized=false` and `production_decision_authorized=false` on every applicable externally visible gateway object.
- ACK means only “processed before lease expiry”; it never authorizes execution.
- Default bind is loopback only; non-loopback bind fails closed unless explicitly enabled.
- Default unexpected Host values fail closed; non-empty WebSocket Origin fails closed unless allowlisted.
- No new long-lived credential is generated, persisted, logged, or discovered.
- No Kafka, NATS, Redis, RabbitMQ, external broker, paid service, new credential, scheduler, workflow, provider, Brain, Atlas, broker/execution, UI, `server.py`, or Field Agent change.
- Production gateway startup requires a file-backed SQLite path.
- FastAPI/Uvicorn stay in the repository’s existing `bridge` optional dependency set. Do not change `pyproject.toml` or `.github/workflows/test.yml`; current Linux and Windows test workflows already install `bridge`.
- One `DeliveryExecutor` worker thread creates, owns, uses, and closes one `IntelligenceDeliveryPlane`/SQLite connection. Do not call that connection from arbitrary ASGI threadpool workers.
- DeliveryExecutor request queue, active sessions, ticket store, per-session in-flight set, request bodies, and frames are all bounded.
- Gateway session state and tickets are ephemeral; no gateway cursor or ACK ledger is durable.
- Session-scoped ACK/NACK must verify `delivery_id` is in that exact session’s in-flight set before calling Phase 2.
- Request IDs are correlation only. ACK/NACK is not made idempotent by Phase 3.
- `max_inflight` range: 1..256. `lease_seconds` range: 5..300. Ticket pre-use lifetime: at most 30 seconds. Default active-session cap: 256. Unused ticket cap: 1024. Auth/control JSON max: 32 KiB. WebSocket text-frame max: 64 KiB.
- No lease renewal in v1.
- No arbitrary intelligence publication, agent chat, request/response task protocol, subscription mutation, replay creation, group mutation, or dead-letter requeue through the gateway in Phase 3.

## Review Focus

1. **Thread affinity / shutdown:** every Phase 2 call, including construction and `close()`, must occur on the single DeliveryExecutor worker thread; test worker thread IDs and close behavior.
2. **Cross-session control:** two sessions for the same consumer must not ACK/NACK each other’s delivery even if the caller knows the valid lease token; test exact-session membership rejection before Phase 2 control.
3. **Ticket expiry/capacity races:** purge expired tickets before checking capacity, consume atomically, reject reuse, and never evict a still-valid unused ticket; cover all four cases.
4. **Lost control response:** after Phase 2 commits ACK but the network response is lost, retrying the same request must not synthesize success; test the resulting durable-state error mapping.
5. **Browser loopback attack surface:** Host validation must precede sensitive endpoint work and WebSocket Origin validation must occur before authentication/claim; test rejected Host/Origin produces zero Phase 2 calls.

---

## File Structure

- Create `icarus_engine/intelligence_gateway.py` — all Phase 3 production behavior: config, security helpers, redaction, DeliveryExecutor, ticket/session registries, gateway service, FastAPI app factory, WebSocket/SSE/HTTP transport handlers.
- Create `tests_engine/test_intelligence_gateway.py` — Phase 2 delegation, sessions, delivery/control behavior, backpressure, SSE/WS equivalence, recovery, reconnect, failure behavior.
- Create `tests_engine/test_intelligence_gateway_security.py` — bearer/Host/Origin/bind validation, tickets, bounds, redaction, thread affinity, frame/body hardening, non-idempotent lost-response semantics.
- Do not modify `icarus_engine/intelligence_delivery.py`, `icarus_engine/intelligence_fabric.py`, `icarus_engine/server.py`, `icarus_engine/agent.py`, `pyproject.toml`, or workflows unless an independently discovered defect forces a new approved scope.

### Task 1: Gateway primitives, security policy, and dedicated DeliveryExecutor

**Files:**
- Create: `icarus_engine/intelligence_gateway.py`
- Create: `tests_engine/test_intelligence_gateway_security.py`

**Interfaces:**
- Consumes: `IntelligenceDeliveryPlane(path_or_connection, *, busy_timeout_ms=5000, token_factory=None)` from Phase 2.
- Produces:
  - `PROTOCOL_VERSION: str = "icarus-intelligence-gateway-v1"`
  - `@dataclass(frozen=True) GatewayConfig`
  - `def validate_bind_host(host: str, *, allow_remote: bool) -> str`
  - `def validate_host_header(host_header: str | None, allowed_hosts: frozenset[str]) -> None`
  - `def validate_origin(origin: str | None, allowed_origins: frozenset[str]) -> None`
  - `def bearer_matches(presented: str | None, expected: str) -> bool`
  - `def redact_for_log(value: object, *, secrets_to_hide: tuple[str, ...] = ()) -> str`
  - `class DeliveryExecutor`
  - `DeliveryExecutor.start() -> None`
  - `DeliveryExecutor.submit(method: str, /, *args: object, **kwargs: object) -> concurrent.futures.Future[object]`
  - `async DeliveryExecutor.call(method: str, /, *args: object, **kwargs: object) -> object`
  - `DeliveryExecutor.close() -> None`
  - `DeliveryExecutor.queue_depth -> int`
  - `DeliveryExecutor.saturation_count -> int`

`GatewayConfig` exact fields/defaults:
- `host: str = "127.0.0.1"`
- `allow_remote: bool = False`
- `allowed_hosts: frozenset[str] = frozenset({"127.0.0.1", "localhost", "[::1]"})`
- `allowed_origins: frozenset[str] = frozenset()`
- `auth_timeout_seconds: float = 5.0`
- `heartbeat_seconds: float = 10.0`
- `client_idle_timeout_seconds: float = 60.0`
- `idle_poll_seconds: float = 0.25`
- `recovery_seconds: float = 1.0`
- `recovery_limit: int = 100`
- `default_lease_seconds: int = 30`
- `default_max_inflight: int = 16`
- `max_sessions: int = 256`
- `max_unused_tickets: int = 1024`
- `ticket_ttl_seconds: float = 30.0`
- `executor_queue_capacity: int = 128`
- `max_json_body_bytes: int = 32 * 1024`
- `max_ws_text_bytes: int = 64 * 1024`

- [ ] **Step 1: Write failing config/security tests**

Add tests named:
- `test_default_config_is_loopback_fail_closed`
- `test_non_loopback_bind_requires_explicit_remote_enablement`
- `test_host_header_rejects_unexpected_host_and_accepts_loopback_with_port`
- `test_nonempty_origin_rejected_unless_allowlisted`
- `test_bearer_matching_uses_constant_time_helper_contract`
- `test_redaction_removes_bearer_ticket_and_lease_values`
- `test_config_rejects_out_of_range_resource_limits`

Assert exact protocol constant, 1..256 in-flight range, 5..300 lease range, positive finite timing values, finite queue/session/ticket caps, and redaction output containing `[REDACTED]` instead of supplied secrets.

- [ ] **Step 2: Run Task 1 security tests and verify RED**

Run: `python -m pytest tests_engine/test_intelligence_gateway_security.py -q`
Expected: FAIL during import because `icarus_engine.intelligence_gateway` does not exist.

- [ ] **Step 3: Implement config and pure security helpers**

Use `ipaddress.ip_address()` plus explicit `localhost` handling for bind validation; Host parser must tolerate an optional port but reject empty/malformed/unexpected host names. Use `hmac.compare_digest()` for bearer comparison. Redaction must never return supplied secret substrings.

- [ ] **Step 4: Write failing DeliveryExecutor tests**

Add:
- `test_delivery_executor_constructs_uses_and_closes_plane_on_one_worker_thread`
- `test_delivery_executor_queue_is_bounded_and_reports_saturation`
- `test_delivery_executor_rejects_unknown_method_name`
- `test_delivery_executor_call_does_not_execute_phase2_on_event_loop_thread`
- `test_delivery_executor_startup_failure_propagates_without_starting_gateway_state`

Use an injectable `plane_factory` fake recording constructor, method, and close thread IDs. Allowed method names are exactly: `claim`, `ack`, `nack`, `recover_expired`, `metrics`.

- [ ] **Step 5: Run DeliveryExecutor tests and verify RED**

Run the five executor tests directly with `pytest -q` node selectors.
Expected: FAIL because `DeliveryExecutor` is absent/incomplete.

- [ ] **Step 6: Implement `DeliveryExecutor` minimally**

Use one `queue.Queue(maxsize=configured_capacity)`, one daemon worker thread, and `concurrent.futures.Future` results. The worker constructs the Phase 2 plane from the file-backed path inside `_run()`, dispatches only the five allowlisted public methods, and closes the plane in the worker `finally`. `submit()` fails immediately with a stable `GatewayBusyError` when the queue is full and increments saturation count. `call()` wraps the concurrent future with `asyncio.wrap_future()`.

- [ ] **Step 7: Run Task 1 focused tests GREEN**

Run: `python -m pytest tests_engine/test_intelligence_gateway_security.py -q`
Expected: all Task 1 tests PASS.

- [ ] **Step 8: Commit Task 1**

Commit message: `feat: add gateway security core and delivery executor`

### Task 2: Ephemeral ticket and session state

**Files:**
- Modify: `icarus_engine/intelligence_gateway.py`
- Modify: `tests_engine/test_intelligence_gateway_security.py`
- Create/Modify: `tests_engine/test_intelligence_gateway.py`

**Interfaces:**
- Consumes: `GatewayConfig`.
- Produces:
  - `@dataclass(frozen=True) SessionBinding(subscription_id: str, revision: int, consumer_id: str, lease_seconds: int, max_inflight: int)`
  - `@dataclass GatewaySession(session_id: str, transport: Literal["websocket", "sse"], binding: SessionBinding, connected_at: str, last_client_activity_at: str, last_server_activity_at: str, inflight_delivery_ids: set[str], closed: bool = False)`
  - `class TicketStore`
  - `TicketStore.issue(binding: SessionBinding, *, now_monotonic: float) -> str`
  - `TicketStore.consume(ticket: str, *, now_monotonic: float) -> SessionBinding`
  - `TicketStore.count(*, now_monotonic: float) -> int`
  - `class SessionRegistry`
  - `SessionRegistry.create(transport: str, binding: SessionBinding, *, now: str) -> GatewaySession`
  - `SessionRegistry.get(session_id: str) -> GatewaySession | None`
  - `SessionRegistry.close(session_id: str) -> tuple[str, ...]`
  - `SessionRegistry.add_inflight(session_id: str, delivery_id: str) -> None`
  - `SessionRegistry.remove_inflight(session_id: str, delivery_id: str) -> bool`
  - `SessionRegistry.remove_inflight_everywhere(delivery_id: str) -> int`
  - `SessionRegistry.snapshot() -> dict[str, int]`

- [ ] **Step 1: Write failing ticket tests**

Add:
- `test_ticket_is_one_use_and_returns_exact_binding`
- `test_ticket_expires_at_configured_ttl`
- `test_ticket_store_purges_expired_before_capacity_check`
- `test_ticket_store_never_evicts_valid_ticket_when_full`
- `test_ticket_values_are_opaque_and_not_present_in_snapshot_or_repr`

Use an injectable token factory returning deterministic unique tokens in tests.

- [ ] **Step 2: Run ticket tests RED**

Expected failures: missing `SessionBinding` / `TicketStore`.

- [ ] **Step 3: Implement `SessionBinding` validation and `TicketStore`**

Validate `revision >= 1`, `lease_seconds in 5..300`, `max_inflight in 1..256`, and bounded non-empty IDs. Store `{ticket: (expires_monotonic, binding)}` under a lock; purge expiry before count/capacity; `consume()` removes before returning so concurrent second consume fails.

- [ ] **Step 4: Write failing session-registry tests**

Add:
- `test_session_registry_enforces_max_sessions_without_evicting_live_session`
- `test_session_close_returns_inflight_ids_without_ack_or_nack_side_effect`
- `test_same_consumer_may_have_two_sessions_with_independent_inflight_sets`
- `test_remove_inflight_everywhere_reconciles_expired_delivery`
- `test_snapshot_counts_transport_and_inflight_without_secrets`

- [ ] **Step 5: Run session tests RED**

Expected: missing/incomplete `SessionRegistry`.

- [ ] **Step 6: Implement `SessionRegistry`**

Use a lock for all state. `close()` marks/removes only ephemeral session data and returns prior in-flight IDs; it performs no Phase 2 operation. Snapshot reports active/WebSocket/SSE session counts and total in-flight count only.

- [ ] **Step 7: Run Task 1+2 tests GREEN**

Run: `python -m pytest tests_engine/test_intelligence_gateway_security.py tests_engine/test_intelligence_gateway.py -q`
Expected: PASS.

- [ ] **Step 8: Commit Task 2**

Commit message: `feat: add gateway sessions and one-time tickets`

### Task 3: Gateway service — Phase 2 delegation, backpressure, control scoping, recovery

**Files:**
- Modify: `icarus_engine/intelligence_gateway.py`
- Modify: `tests_engine/test_intelligence_gateway.py`
- Modify: `tests_engine/test_intelligence_gateway_security.py`

**Interfaces:**
- Consumes: `DeliveryExecutor.call`, `SessionRegistry`, `TicketStore`.
- Produces `class IntelligenceGatewayService` with:
  - `async start() -> None`
  - `async close() -> None`
  - `create_ws_session(binding: SessionBinding, *, now: str) -> GatewaySession`
  - `create_sse_ticket(binding: SessionBinding, *, now_monotonic: float) -> str`
  - `consume_sse_ticket(ticket: str, *, now_monotonic: float, now: str) -> GatewaySession`
  - `async claim_for_session(session_id: str, *, now: str) -> list[dict[str, object]]`
  - `async ack_for_session(session_id: str, delivery_id: str, lease_token: str, *, now: str) -> dict[str, object]`
  - `async nack_for_session(session_id: str, delivery_id: str, lease_token: str, *, now: str, reason: Mapping[str, object] | None = None) -> dict[str, object]`
  - `async recover_expired(*, now: str) -> list[dict[str, object]]`
  - `async durable_metrics(subscription_id: str, revision: int, *, now: str) -> dict[str, object]`
  - `ephemeral_metrics() -> dict[str, object]`
  - `close_session(session_id: str) -> None`

- [ ] **Step 1: Write failing delegation/backpressure tests**

Add:
- `test_claim_for_session_calls_phase2_with_exact_binding_and_free_slot_limit`
- `test_claim_for_session_does_not_call_phase2_when_inflight_full`
- `test_claim_result_becomes_session_inflight_without_rewriting_event_or_delivery_identity`
- `test_claim_rejects_unknown_or_closed_session`
- `test_service_never_auto_registers_consumer_or_mutates_group_membership`

Use an async fake executor recording exact method/args and returning Phase 2-shaped delivery mappings.

- [ ] **Step 2: Run delegation tests RED**

Expected: missing `IntelligenceGatewayService`.

- [ ] **Step 3: Implement claim path minimally**

`claim_for_session()` computes free slots first; zero means zero executor calls. For positive capacity, call exact Phase 2 `claim(subscription_id, revision, consumer_id, as_of=now, lease_seconds=binding.lease_seconds, limit=available)`. Add returned delivery IDs to the session only after successful result receipt. Never alter embedded `event`, `event_id`, `delivery_id`, or lease fields.

- [ ] **Step 4: Write failing session-scoped ACK/NACK tests**

Add:
- `test_ack_calls_phase2_with_exact_consumer_delivery_token_and_frees_slot`
- `test_nack_calls_phase2_with_exact_fields_reason_and_frees_slot`
- `test_cross_session_ack_rejected_before_phase2_even_same_consumer_and_valid_token`
- `test_cross_session_nack_rejected_before_phase2`
- `test_failed_phase2_ack_or_nack_keeps_inflight_membership_for_reconciliation`
- `test_lost_ack_response_retry_does_not_synthesize_success`

For lost-response test: first fake call commits external fake state then raises simulated transport/runtime failure; second request returns a durable-state-invalid error. Assert service never fabricates `ACKED`.

- [ ] **Step 5: Implement ACK/NACK scoping**

Require exact live session and in-flight membership before submitting Phase 2 control. Remove the ID only after a successful Phase 2 result. Do not cache request IDs or synthesize idempotency.

- [ ] **Step 6: Write failing recovery tests**

Add:
- `test_recovery_delegates_to_phase2_and_removes_recovered_ids_from_all_sessions`
- `test_disconnect_drops_ephemeral_state_without_phase2_ack_or_nack`
- `test_reconnect_has_no_gateway_cursor_and_asks_phase2_again`

- [ ] **Step 7: Implement recovery/close-session behavior**

Submit exact `recover_expired(as_of=now, limit=config.recovery_limit)`; remove every returned `delivery_id` from all session in-flight sets. Session close only deletes local state.

- [ ] **Step 8: Run Task 3 focused tests GREEN**

Run: `python -m pytest tests_engine/test_intelligence_gateway.py tests_engine/test_intelligence_gateway_security.py -q`
Expected: PASS.

- [ ] **Step 9: Commit Task 3**

Commit message: `feat: add gateway delivery service semantics`

### Task 4: FastAPI app, HTTP authentication, health, tickets, metrics, and SSE control endpoints

**Files:**
- Modify: `icarus_engine/intelligence_gateway.py`
- Modify: `tests_engine/test_intelligence_gateway.py`
- Modify: `tests_engine/test_intelligence_gateway_security.py`

**Interfaces:**
- Produces:
  - `def create_intelligence_gateway_app(*, db_path: str, bearer_token: str, config: GatewayConfig | None = None, plane_factory: Callable[..., object] = IntelligenceDeliveryPlane) -> FastAPI`
  - HTTP `GET /healthz`
  - HTTP `POST /v1/intelligence/tickets`
  - HTTP `POST /v1/intelligence/ack`
  - HTTP `POST /v1/intelligence/nack`
  - HTTP `GET /v1/intelligence/metrics`
- Application lifespan starts/closes `IntelligenceGatewayService` and `DeliveryExecutor` exactly once.

- [ ] **Step 1: Write failing app-startup and Host/auth tests**

Add:
- `test_app_requires_nonempty_bearer_and_file_backed_db_path`
- `test_healthz_exposes_only_coarse_health_and_protocol`
- `test_rejected_host_hits_no_sensitive_handler_or_phase2_operation`
- `test_authenticated_endpoints_reject_missing_invalid_bearer_generically`
- `test_http_body_over_32k_rejected_before_durable_operation`
- `test_nan_and_infinity_json_rejected_before_durable_operation`

- [ ] **Step 2: Run HTTP security tests RED**

Expected: no app factory/routes.

- [ ] **Step 3: Implement app factory, lifespan, Host middleware, bearer dependency, bounded strict JSON helper**

Host validation executes before route logic. `healthz` may probe coarse store reachability through the executor but cannot expose consumers/subscriptions/deliveries. Strict JSON uses `allow_nan=False` semantics / parse rejection and bounded raw body length.

- [ ] **Step 4: Write failing ticket/metrics/control endpoint tests**

Add:
- `test_ticket_endpoint_returns_one_time_ticket_without_echoing_bearer`
- `test_metrics_delegates_phase2_and_labels_gateway_counters_ephemeral`
- `test_sse_ack_requires_matching_open_sse_session_and_inflight_delivery`
- `test_sse_nack_requires_matching_open_sse_session`
- `test_sse_ack_success_immediately_releases_inflight_slot`
- `test_http_error_mapping_sanitizes_phase2_exception_text`

- [ ] **Step 5: Implement ticket/metrics/ACK/NACK endpoints**

Ticket creation validates `SessionBinding` before issue. HTTP ACK/NACK requires bearer, active session, `transport == "sse"`, matching consumer, and in-flight membership; then delegates to service methods. Durable metrics come from Phase 2; gateway counters are a separate object/namespace marked `ephemeral: true`.

- [ ] **Step 6: Run Task 4 tests GREEN**

Run focused security + HTTP tests.
Expected: PASS.

- [ ] **Step 7: Commit Task 4**

Commit message: `feat: add authenticated gateway HTTP surface`

### Task 5: WebSocket v1 protocol

**Files:**
- Modify: `icarus_engine/intelligence_gateway.py`
- Modify: `tests_engine/test_intelligence_gateway.py`
- Modify: `tests_engine/test_intelligence_gateway_security.py`

**Interfaces:**
- Endpoint: `WS /v1/intelligence/ws`
- Internal helpers:
  - `def delivery_frame(session: GatewaySession, delivery: Mapping[str, object]) -> dict[str, object]`
  - `def error_frame(code: str, *, message: str, retryable: bool, request_id: str | None = None) -> dict[str, object]`
  - `def heartbeat_frame(session: GatewaySession, *, server_time: str, sequence_lag: int | None = None) -> dict[str, object]`
- Accepted first frame: `authenticate` only.
- Accepted post-auth client frames: `ack`, `nack`, `ping` only.

- [ ] **Step 1: Write failing authentication/Origin tests**

Add:
- `test_websocket_rejects_unexpected_host_before_authentication`
- `test_websocket_rejects_nonallowlisted_origin_before_authentication`
- `test_websocket_auth_timeout_closes_with_zero_claim_calls`
- `test_websocket_invalid_token_closes_with_zero_claim_calls_and_no_secret_echo`
- `test_websocket_unsupported_protocol_rejected_before_claim`
- `test_websocket_auth_does_not_auto_register_consumer`

- [ ] **Step 2: Run WS auth tests RED**

Expected: route/helper missing.

- [ ] **Step 3: Implement WS handshake/authentication**

Validate Host/Origin before accepting sensitive use. Accept socket only enough to receive bounded first text frame. Enforce `auth_timeout_seconds`; max raw frame <=64 KiB before JSON parse. Validate protocol/token/binding; create session; emit `hello` with both authority flags false; never echo token.

- [ ] **Step 4: Write failing WS delivery/backpressure/control tests**

Add:
- `test_websocket_delivery_frame_preserves_phase2_delivery_and_phase1_event_identity`
- `test_websocket_never_claims_above_free_inflight_capacity`
- `test_websocket_full_window_emits_flow_without_additional_claim`
- `test_websocket_ack_and_nack_delegate_exactly_and_emit_result_frames`
- `test_websocket_cross_session_control_rejected`
- `test_websocket_ping_returns_heartbeat`
- `test_websocket_disconnect_never_auto_acks_or_nacks`
- `test_websocket_applicable_frames_always_include_false_authority_flags`

- [ ] **Step 5: Implement bounded WS run loop**

Run receive/control and claim/heartbeat work without CPU spin. No application delivery queue beyond session in-flight state. Claim only when capacity exists. Preserve claim-batch order on send. Invalid frame types return stable sanitized errors and do no durable operation.

- [ ] **Step 6: Write failing runtime failure tests**

Add:
- `test_websocket_phase2_runtime_failure_never_sends_delivery_or_ack_success`
- `test_websocket_external_errors_never_include_stack_sql_path_bearer_ticket_or_lease_secret`

- [ ] **Step 7: Implement stable exception-to-error-code mapping**

Map gateway prevalidation and known Phase 2 failure classes/messages to the spec’s stable external codes; unknown exception text is not exposed. Increment protocol/auth counters without storing secret values.

- [ ] **Step 8: Run Task 5 tests GREEN**

Run both gateway test files.
Expected: PASS.

- [ ] **Step 9: Commit Task 5**

Commit message: `feat: add live intelligence WebSocket protocol`

### Task 6: SSE stream, heartbeat, transport equivalence, and recovery lifecycle

**Files:**
- Modify: `icarus_engine/intelligence_gateway.py`
- Modify: `tests_engine/test_intelligence_gateway.py`
- Modify: `tests_engine/test_intelligence_gateway_security.py`

**Interfaces:**
- Endpoint: `GET /v1/intelligence/stream?ticket=<ticket>`
- Internal helper: `def encode_sse(event: str, payload: Mapping[str, object]) -> bytes`
- App lifespan owns one bounded periodic recovery coroutine that submits Phase 2 `recover_expired` through the service/executor.

- [ ] **Step 1: Write failing SSE ticket/stream tests**

Add:
- `test_sse_stream_consumes_ticket_atomically_and_reuse_fails`
- `test_sse_unknown_or_expired_ticket_is_generic_auth_failure`
- `test_sse_stream_hello_contains_session_id_and_false_authority_flags`
- `test_sse_delivery_uses_same_phase2_delivery_shape_as_websocket`
- `test_sse_full_inflight_window_stops_claiming`
- `test_sse_heartbeat_keeps_idle_stream_alive`
- `test_sse_disconnect_does_not_ack_or_nack`

- [ ] **Step 2: Run SSE tests RED**

Expected: stream route/encoder missing.

- [ ] **Step 3: Implement SSE route and encoder**

Consume ticket exactly once before session creation. Emit `hello`, `delivery`, `heartbeat`, `flow`, `error` event names only. Use the same service claim path and delivery-frame data fields as WS; do not create transport-specific durable state.

- [ ] **Step 4: Write failing transport-equivalence tests**

Independently seed two equivalent Phase 1/Phase 2 durable databases, one for WS and one for SSE. Assert first delivered `delivery_id`, `event_id`, `journal_sequence`, event envelope, attempt, lease-expiry shape, and both authority flags are equivalent. Do not race two transports for one live lease.

- [ ] **Step 5: Implement any shared framing extraction needed for equivalence**

Keep framing transport-specific but derive payload fields from one shared delivery-frame helper.

- [ ] **Step 6: Write failing recovery-lifecycle tests**

Add:
- `test_periodic_recovery_runs_through_delivery_executor_not_event_loop_connection`
- `test_recovered_delivery_is_removed_from_all_session_inflight_sets`
- `test_gateway_restart_loses_sessions_and_tickets_but_phase2_can_redeliver_after_expiry`
- `test_service_close_cancels_recovery_then_closes_executor_on_owner_thread`

- [ ] **Step 7: Implement recovery coroutine and orderly lifespan shutdown**

Recovery sleeps `recovery_seconds`, submits one bounded `recover_expired`, reconciles local sets, and survives retryable store-busy errors without claiming/synthesizing control success. Shutdown stops transport/recovery tasks before closing the worker.

- [ ] **Step 8: Run all Phase 3 focused tests GREEN**

Run: `python -m pytest tests_engine/test_intelligence_gateway.py tests_engine/test_intelligence_gateway_security.py -q`
Expected: all pass with no skipped Phase 3 tests.

- [ ] **Step 9: Commit Task 6**

Commit message: `feat: add SSE intelligence streaming and recovery lifecycle`

### Task 7: Regression verification, exact-head CI, stacked PR, and independent review

**Files:**
- No expected product changes.
- Only test fixes are allowed if they reveal a real Phase 3 defect; production fixes require a new RED test first.

**Interfaces:**
- Consumes completed Phase 3 module and tests.
- Produces verification evidence and a stacked Phase 3 PR whose base is the Phase 2 implementation branch/PR until Phase 2 merges.

- [ ] **Step 1: Run Phase 3 focused suite fresh**

Run: `python -m pytest tests_engine/test_intelligence_gateway.py tests_engine/test_intelligence_gateway_security.py -q`
Expected: PASS, zero failed/skipped.

- [ ] **Step 2: Run Phase 1 + Phase 2 regressions**

Run all Intelligence Fabric and Intelligence Delivery Plane test files, including integrity/hardening suites.
Expected: PASS.

- [ ] **Step 3: Run full Linux-equivalent suite**

Run: `python -m pytest tests_engine -q`
Then:
- `python -m icarus_plant --root /tmp/icarus-plant-ci setup`
- `icarus-control --help`
- `python -m icarus_engine.cli doctor --json`
Expected: all PASS.

- [ ] **Step 4: Verify no forbidden diff**

Compare Phase 3 implementation head to Phase 2 head. Expected changed implementation scope only:
- `icarus_engine/intelligence_gateway.py`
- `tests_engine/test_intelligence_gateway.py`
- `tests_engine/test_intelligence_gateway_security.py`
- Phase 3 design/plan docs

Reject accidental changes to server, Field Agent, UI, Brain, schedulers/workflows, providers, execution, Atlas paths, `pyproject.toml`, or Phase 1/2 source.

- [ ] **Step 5: Push exact implementation head and wait for repository CI**

Required GitHub Actions `tests` workflow:
- Linux `engine`: success on full `tests_engine`, plant setup, control CLI, doctor.
- Windows `engine-windows`: success on the repository’s existing Windows regression matrix.

Do not claim cross-platform completion from local/Linux evidence alone.

- [ ] **Step 6: Open Phase 3 stacked PR**

Base it on `chatgpt/beyond-ib-delivery-plane-impl-20261012` / PR #335 while Phase 2 remains unmerged. State explicitly that Phase 1 PR #334 and Phase 2 PR #335 are prerequisites and must not be bypassed.

PR body must include:
- exact head SHA
- spec and plan paths
- RED→GREEN evidence by task
- focused test count
- full Linux and Windows CI evidence
- exact changed-file scope
- authority invariants
- no server/UI/Brain/scheduler/provider/execution changes

- [ ] **Step 7: Request independent Claude review through coordination inbox**

Review focus:
- SQLite thread affinity and executor shutdown
- Host/Origin/token/ticket security
- session-scoped control
- backpressure boundedness
- WS/SSE durable equivalence
- secret/error leakage
- failure/reconnect semantics

Do not merge Phase 3 until required independent review is satisfied. Do not merge around unresolved Phase 1/2 review gates.

- [ ] **Step 8: If review finds defects, use review/debugging workflow**

Before changes, invoke `superpowers:receiving-code-review`; for any failing test/unexpected behavior invoke `superpowers:systematic-debugging`; add a RED regression test before production fix.

- [ ] **Step 9: Final verification before completion claim**

Invoke `superpowers:verification-before-completion`, rerun exact-head focused/regression checks needed after the last code change, and confirm PR CI on that same head.
