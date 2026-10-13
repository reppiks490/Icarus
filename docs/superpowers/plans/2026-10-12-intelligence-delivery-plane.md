# ICARUS Durable Intelligence Delivery Plane — Phase 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a durable, transport-independent intelligence delivery plane over the Phase 1 Intelligence Fabric with crash-safe leases, broadcast and competing-consumer delivery, ACK/NACK/retry/dead-letter semantics, replay, receipts, and lag metrics while preserving hard execution denial.

**Architecture:** Add one backend-only module, `icarus_engine/intelligence_delivery.py`, that shares the same SQLite database as the Phase 1 journal but owns only delivery-state tables and append-only delivery receipts. Delivery is sequence-driven and at-least-once: subscriptions define immutable eligibility revisions, claims use transactional leases, ACK/NACK validates opaque lease tokens, and replay creates new durable subscription state rather than rewinding live state. No server/UI/network/scheduler integration is part of this slice.

**Tech Stack:** Python 3.11, stdlib `sqlite3`, `json`, `hashlib`, `secrets`, dataclasses/typing; pytest; existing ICARUS GitHub Actions Linux/Windows test workflows.

**Spec:** `docs/superpowers/specs/2026-10-12-intelligence-delivery-plane-design.md`

## Global Constraints

- Base implementation on Phase 1 exact head `01d29ce037698d930e8511a7e748b7132f187248` / PR #334 semantics.
- Do not modify `brain.py`, `brain_sync.py`, UI/aesthetic paths, provider collectors, workflows/schedulers, credentials, Atlas registry paths, brokerage, or execution modules.
- Do not adopt or mutate `Icarus-engine/automation_intelligence/agent_fabric` scheduler IDs/state.
- The Phase 1 `fabric_events` journal remains canonical; Phase 2 adds delivery state/projections only.
- Every delivery-facing result carries or inherits `execution_authorized=false` and `production_decision_authorized=false`.
- ACK means processed, never true/endorsed/trade-approved.
- Delivery order is ascending Phase 1 journal sequence; do not claim total provider event-time ordering.
- Core time-sensitive methods require explicit timezone-aware `as_of`; normalize to UTC. No hidden wall-clock reads in contract logic.
- No external broker/database dependency, paid infrastructure, credential, or network transport in Phase 2.
- Use bounded lengths/counts/JSON payloads consistent with Phase 1; reject NaN/Infinity and malformed state fail-closed.
- At-least-once semantics only. Do not claim exactly-once processing or distributed consensus.
- Full repository CI at the exact implementation head and independent review are required before merge.

## Review Focus

1. **Duplicate or conflicting subscription revision:** creating the same `(subscription_id, revision)` with identical canonical spec is idempotent; different material fields under the same identity raise and never reinterpret existing deliveries. Covered in Task 1.
2. **Boundary-time lease actions:** ACK/NACK at or after `lease_expires_at` must fail even when no recovery job has run yet. Covered in Task 3.
3. **Corrupted/tampered Phase 1 journal row:** event SHA/authority mismatch must fail closed before delivery and must not create an ACKable delivery. Covered in Task 6.
4. **Retry ceiling under mixed NACK + expiry:** attempt counting must reach dead-letter deterministically regardless of failure path and must preserve receipt history. Covered in Task 4.
5. **Filtered subscription with no historical matches:** metrics must return an explicit empty/zero state rather than a misleading huge sequence lag. Covered in Task 5.

---

## File Structure

- Create `icarus_engine/intelligence_delivery.py` — validation, delivery schema, immutable subscription revisions, consumer/group routing, lease state machine, receipts, retries/dead-letter/replay, metrics, and Phase 1 envelope verification.
- Create `tests_engine/test_intelligence_delivery.py` — all focused Phase 2 tests, including file-backed durability and independent-connection contention checks.
- Do **not** modify `icarus_engine/intelligence_fabric.py` unless a later RED proves an extension is unavoidable; the intended design shares a caller-supplied `sqlite3.Connection` or the same database path instead.

## Locked Public Interfaces

The implementation tasks below must converge on these names unless a test proves a signature is impossible without violating the spec:

```python
@dataclass(frozen=True)
class SubscriptionSpec:
    subscription_id: str
    revision: int
    mode: str  # "broadcast" | "competing"
    consumer_id: str | None = None
    consumer_group: str | None = None
    start_sequence: int = 1
    channel: str | None = None
    event_types: tuple[str, ...] = ()
    assets: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    source: str | None = None
    min_severity: int | None = None
    max_attempts: int = 5
    retry_delay_seconds: int = 0

class IntelligenceDeliveryPlane:
    def __init__(
        self,
        path_or_connection: str | sqlite3.Connection = ":memory:",
        *,
        busy_timeout_ms: int = 5000,
        token_factory: Callable[[], str] | None = None,
    ) -> None: ...

    def register_consumer(self, consumer_id: str, *, as_of: str) -> dict[str, Any]: ...
    def set_group_membership(self, consumer_id: str, consumer_group: str, enabled: bool, *, as_of: str) -> dict[str, Any]: ...
    def create_subscription(self, spec: SubscriptionSpec, *, as_of: str) -> dict[str, Any]: ...
    def set_subscription_enabled(self, subscription_id: str, revision: int, enabled: bool, *, as_of: str) -> dict[str, Any]: ...
    def claim(self, subscription_id: str, revision: int, consumer_id: str, *, as_of: str, lease_seconds: int = 30, limit: int = 1) -> list[dict[str, Any]]: ...
    def ack(self, delivery_id: str, consumer_id: str, lease_token: str, *, as_of: str) -> dict[str, Any]: ...
    def nack(self, delivery_id: str, consumer_id: str, lease_token: str, *, as_of: str, reason: Mapping[str, Any] | None = None) -> dict[str, Any]: ...
    def recover_expired(self, *, as_of: str, limit: int = 100) -> list[dict[str, Any]]: ...
    def dead_letters(self, *, subscription_id: str | None = None, revision: int | None = None, limit: int = 100) -> list[dict[str, Any]]: ...
    def requeue_dead_lettered(self, delivery_id: str, *, as_of: str, reason: Mapping[str, Any] | None = None) -> dict[str, Any]: ...
    def receipts(self, *, delivery_id: str | None = None, subscription_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]: ...
    def metrics(self, subscription_id: str, revision: int, *, as_of: str) -> dict[str, Any]: ...
    def create_replay_subscription(self, source_subscription_id: str, source_revision: int, replay_subscription_id: str, start_sequence: int, *, as_of: str) -> dict[str, Any]: ...
```

Every returned delivery/control record must include both authority flags set to `False`.

---

### Task 1: Delivery schema, validation, consumers, groups, and immutable subscription revisions

**Files:**
- Create: `icarus_engine/intelligence_delivery.py`
- Create: `tests_engine/test_intelligence_delivery.py`

**Interfaces:**
- Consumes: existing Phase 1 tables in the same SQLite database; no Phase 1 Python API change.
- Produces: `SubscriptionSpec`, `IntelligenceDeliveryPlane.__init__`, `register_consumer`, `set_group_membership`, `create_subscription`, `set_subscription_enabled`.

- [ ] **Step 1: Write failing validation/schema tests**

Add tests named:
- `test_subscription_revision_is_canonical_idempotent_and_conflict_fails_closed`
- `test_subscription_mode_target_and_retry_policy_validation`
- `test_consumer_registration_and_group_membership_are_receipt_audited`
- `test_subscription_enable_disable_is_receipt_audited_without_rewriting_material_spec`

Assert: identical subscription recreation returns `idempotent=True`; conflicting material spec under same `(subscription_id, revision)` raises `ValueError`; broadcast requires exactly `consumer_id`; competing requires exactly `consumer_group`; `start_sequence >= 1`; `max_attempts >= 1`; retry delay is non-negative; malformed/non-timezone `as_of` fails; membership/enable transitions produce append-only receipts and all results carry false authority flags.

- [ ] **Step 2: Run focused tests and confirm RED**

Run: `python -m pytest tests_engine/test_intelligence_delivery.py -k "subscription or consumer or group" -q`
Expected: FAIL because `icarus_engine.intelligence_delivery` does not exist.

- [ ] **Step 3: Implement module validation helpers and schema**

Implement `SubscriptionSpec` and `IntelligenceDeliveryPlane.__init__` with exact signatures above. Create only Phase 2 tables: `fabric_subscriptions`, `fabric_consumers`, `fabric_consumer_groups`, `fabric_deliveries`, `fabric_delivery_receipts`. Enable foreign keys, configure bounded busy timeout, and enable WAL only for file-backed databases where SQLite accepts it. Canonical subscription material is compact sorted finite JSON; store a SHA-256 material hash for identity comparison.

- [ ] **Step 4: Implement consumer/group/subscription control methods**

Implement the four Task 1 public methods. Material subscription fields are immutable per revision. `enabled` is operational state and receipt-audited. Group membership changes are receipt-audited. Registration/group/subscription receipts use the same append-only receipt table with a control transition type and no fake Phase 1 event identity.

- [ ] **Step 5: Run Task 1 tests**

Run: `python -m pytest tests_engine/test_intelligence_delivery.py -k "subscription or consumer or group" -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add icarus_engine/intelligence_delivery.py tests_engine/test_intelligence_delivery.py
git commit -m "feat: add durable intelligence delivery subscriptions"
```

---

### Task 2: Broadcast claiming, durable leases, ACK, and delivery receipts

**Files:**
- Modify: `icarus_engine/intelligence_delivery.py`
- Modify: `tests_engine/test_intelligence_delivery.py`

**Interfaces:**
- Consumes: Task 1 subscription/consumer schema; Phase 1 `fabric_events`, `fabric_assets`, `fabric_tags` tables.
- Produces: `claim`, `ack`; durable delivery rows and delivery-state receipts.

- [ ] **Step 1: Write failing broadcast tests**

Add:
- `test_broadcast_subscriptions_independently_claim_same_phase1_event`
- `test_ack_is_terminal_only_for_its_subscription_target`
- `test_claim_order_is_phase1_sequence_and_start_sequence_is_inclusive`
- `test_disabled_subscription_cannot_claim`

Use one `sqlite3.Connection`; pass it to both `IntelligenceFabric(connection)` and `IntelligenceDeliveryPlane(connection, token_factory=...)`. Publish two Phase 1 events. Create two broadcast subscriptions for different consumers. Assert both can lease the same event independently; each delivery has deterministic event identity/sequence, non-empty lease token, attempt `1`, `LEASED` state, and false authority flags; ACK on one target does not suppress the other; `start_sequence=2` may begin with sequence 2; disabled subscription returns no claims.

- [ ] **Step 2: Run tests and confirm RED**

Run: `python -m pytest tests_engine/test_intelligence_delivery.py -k "broadcast or claim_order or disabled_subscription" -q`
Expected: FAIL because `claim` / `ack` are missing.

- [ ] **Step 3: Implement deterministic eligibility query and logical delivery identity**

Add private helpers that query matching Phase 1 rows by ascending `sequence`, applying subscription channel/type/asset/tag/source/min-severity filters. Logical `delivery_id` is SHA-256 of canonical `[subscription_id, revision, target_kind, target_id, event_id]`; one logical row per target/event is enforced by a unique constraint.

- [ ] **Step 4: Implement transactional `claim`**

Use `BEGIN IMMEDIATE` for claim transactions. For broadcast mode require `consumer_id` to equal the subscription target. Lazily create `PENDING` rows for eligible events, then transition up to `limit` to `LEASED`, increment `attempt`, assign a token from `token_factory`/`secrets.token_urlsafe`, set normalized lease times, and append the receipt atomically.

- [ ] **Step 5: Implement transactional `ack`**

Validate delivery exists, belongs to consumer (or later competing lease owner), state is `LEASED`, supplied token matches, and `as_of < lease_expires_at`. Transition to `ACKED` and append receipt in the same transaction. No direct pending-to-acked path.

- [ ] **Step 6: Run Task 2 tests**

Run: `python -m pytest tests_engine/test_intelligence_delivery.py -k "broadcast or claim_order or disabled_subscription" -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add icarus_engine/intelligence_delivery.py tests_engine/test_intelligence_delivery.py
git commit -m "feat: add broadcast intelligence leasing and ack"
```

---

### Task 3: Competing consumer groups and stale-lease protection

**Files:**
- Modify: `icarus_engine/intelligence_delivery.py`
- Modify: `tests_engine/test_intelligence_delivery.py`

**Interfaces:**
- Consumes: Task 1 group membership, Task 2 claim/ACK state machine.
- Produces: competing-group routing; strict lease-owner/token/time validation shared by ACK/NACK.

- [ ] **Step 1: Write failing competing-group and boundary-time tests**

Add:
- `test_competing_group_allows_only_registered_member_to_claim`
- `test_competing_group_has_only_one_active_lease_for_event`
- `test_wrong_consumer_or_wrong_token_cannot_ack`
- `test_ack_at_or_after_lease_expiry_fails_even_before_recovery`

Assert an unregistered consumer cannot claim; two group members cannot both obtain a valid simultaneous lease for the same delivery; wrong consumer/token raises; `as_of == lease_expires_at` raises and leaves state unacked.

- [ ] **Step 2: Run tests and confirm RED**

Run: `python -m pytest tests_engine/test_intelligence_delivery.py -k "competing or wrong_token or lease_expiry" -q`
Expected: FAIL because group claim/strict lease validation is incomplete.

- [ ] **Step 3: Extend `claim` for competing mode**

Require active group membership for the claiming consumer. The logical delivery target is the group, while the active lease owner is the claiming consumer. The same `BEGIN IMMEDIATE` transaction and unique logical delivery constraint must ensure one active lease per group/event.

- [ ] **Step 4: Centralize lease validation**

Add one private validator used by ACK and later NACK. It must compare consumer identity, active token, `LEASED` state, and strict pre-expiry time. A stale token can never operate after a new attempt is leased.

- [ ] **Step 5: Run Task 3 tests**

Run: `python -m pytest tests_engine/test_intelligence_delivery.py -k "competing or wrong_token or lease_expiry" -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add icarus_engine/intelligence_delivery.py tests_engine/test_intelligence_delivery.py
git commit -m "feat: add competing intelligence consumer leases"
```

---

### Task 4: NACK, lease recovery, bounded retries, dead-letter, and explicit requeue

**Files:**
- Modify: `icarus_engine/intelligence_delivery.py`
- Modify: `tests_engine/test_intelligence_delivery.py`

**Interfaces:**
- Consumes: Task 3 strict lease validator and Task 2 delivery rows/receipts.
- Produces: `nack`, `recover_expired`, `dead_letters`, `requeue_dead_lettered`.

- [ ] **Step 1: Write failing retry/dead-letter tests**

Add:
- `test_nack_retries_after_fixed_delay_when_attempts_remain`
- `test_expired_lease_recovers_and_can_be_redelivered`
- `test_mixed_nack_and_expiry_reaches_max_attempts_then_dead_letters`
- `test_dead_letter_requeue_is_explicit_and_preserves_attempt_history`
- `test_nack_reason_is_bounded_finite_json`

Use `max_attempts=3` and explicit timestamps. Assert attempt count increments only when a lease is issued; NACK/expiry after attempt 3 transitions to `DEAD_LETTERED`; no claim occurs before retry eligibility; requeue emits `REQUEUED -> PENDING` receipts without erasing prior attempts; malformed/oversized reason metadata fails before mutation.

- [ ] **Step 2: Run tests and confirm RED**

Run: `python -m pytest tests_engine/test_intelligence_delivery.py -k "nack or recover or dead_letter or requeue" -q`
Expected: FAIL because retry/dead-letter methods are missing.

- [ ] **Step 3: Implement `nack` and retry eligibility**

Use the shared lease validator. Append `NACKED` receipt. If `attempt >= max_attempts`, transition in the same transaction to `DEAD_LETTERED`; otherwise set deterministic `retry_eligible_at = as_of + retry_delay_seconds`, transition back to `PENDING`, and append the corresponding receipt(s).

- [ ] **Step 4: Implement `recover_expired`**

Select bounded currently `LEASED` rows with `lease_expires_at <= as_of`. For each, append `LEASE_EXPIRED`; dead-letter when attempts are exhausted, otherwise set retry eligibility and return to `PENDING`. Recovery never increments attempts by itself.

- [ ] **Step 5: Implement dead-letter listing and explicit requeue**

`dead_letters` returns only terminal dead-letter rows. `requeue_dead_lettered` requires current state `DEAD_LETTERED`, appends `REQUEUED` then `PENDING`, clears active lease/retry blocking state, preserves cumulative attempt count/history, and requires future claims to increment from that existing attempt count.

- [ ] **Step 6: Run Task 4 tests**

Run: `python -m pytest tests_engine/test_intelligence_delivery.py -k "nack or recover or dead_letter or requeue" -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add icarus_engine/intelligence_delivery.py tests_engine/test_intelligence_delivery.py
git commit -m "feat: add intelligence retry and dead-letter recovery"
```

---

### Task 5: Replay subscriptions, receipts API, and backlog/lag observability

**Files:**
- Modify: `icarus_engine/intelligence_delivery.py`
- Modify: `tests_engine/test_intelligence_delivery.py`

**Interfaces:**
- Consumes: Task 1 subscription spec persistence; Tasks 2–4 receipts/delivery states.
- Produces: `receipts`, `metrics`, `create_replay_subscription`.

- [ ] **Step 1: Write failing replay/metrics tests**

Add:
- `test_replay_subscription_copies_material_contract_and_uses_new_inclusive_start_sequence`
- `test_replay_does_not_mutate_live_subscription_or_phase1_events`
- `test_metrics_report_backlog_active_expired_retry_deadletter_and_tail`
- `test_filtered_subscription_with_no_matches_has_explicit_empty_zero_lag_state`
- `test_receipts_are_append_only_and_filterable`

Snapshot Phase 1 event IDs/sequences before replay and assert unchanged afterward. For empty filtered subscription assert `matching_event_count == 0`, `pending_count == 0`, and `sequence_lag == 0` with explicit empty marker (for example `has_matching_events=False`).

- [ ] **Step 2: Run tests and confirm RED**

Run: `python -m pytest tests_engine/test_intelligence_delivery.py -k "replay or metrics or receipts" -q`
Expected: FAIL because public methods are missing.

- [ ] **Step 3: Implement `receipts`**

Return append-only receipt rows ordered by receipt sequence, with optional delivery/subscription filter and bounded limit. Never synthesize missing history from current projection state.

- [ ] **Step 4: Implement `metrics`**

Compute subscription-revision operational state from current Phase 1 tail, matching eligible sequences, delivery projection, retry/lease state, and explicit `as_of`. Include: matching-event count, pending count, active/expired leases, ACK/NACK receipt counts, retry count, dead-letter count, oldest pending sequence/age, tail sequence, sequence lag, and `has_matching_events`.

- [ ] **Step 5: Implement `create_replay_subscription`**

Copy the source revision's material filter/mode/target/retry policy into a new `replay_subscription_id`, revision `1`, with the requested inclusive `start_sequence`. Reject self-overwrite or an already-conflicting replay identity. Do not alter source subscription or Phase 1 journal.

- [ ] **Step 6: Run Task 5 tests**

Run: `python -m pytest tests_engine/test_intelligence_delivery.py -k "replay or metrics or receipts" -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add icarus_engine/intelligence_delivery.py tests_engine/test_intelligence_delivery.py
git commit -m "feat: add intelligence replay and delivery metrics"
```

---

### Task 6: Durability, corruption fail-closed behavior, and concurrent-claim integrity

**Files:**
- Modify: `icarus_engine/intelligence_delivery.py`
- Modify: `tests_engine/test_intelligence_delivery.py`

**Interfaces:**
- Consumes: complete delivery API from Tasks 1–5.
- Produces: verified reopen durability, exact Phase 1 envelope checks, contention behavior, rollback guarantees.

- [ ] **Step 1: Write failing durability/integrity tests**

Add:
- `test_file_backed_reopen_preserves_subscriptions_deliveries_receipts_and_ack_state`
- `test_tampered_phase1_envelope_or_authority_flags_fail_closed_before_delivery`
- `test_claim_race_across_independent_sqlite_connections_yields_one_competing_lease`
- `test_failed_transition_rolls_back_projection_and_receipt_together`
- `test_every_public_result_keeps_execution_authority_false`

For tamper test, modify a stored Phase 1 `envelope_json` or event authority field directly after publication and assert `claim` raises before creating a usable delivery. For race test, use a file-backed DB and two independent connections; both may attempt claim, but only one can return a valid lease for the same competing logical delivery.

- [ ] **Step 2: Run tests and confirm RED**

Run: `python -m pytest tests_engine/test_intelligence_delivery.py -k "reopen or tampered or race or rollback or authority" -q`
Expected: at least the tamper/race/rollback tests FAIL until hardening is added.

- [ ] **Step 3: Add exact Phase 1 envelope verification at delivery boundary**

Before projecting a Phase 1 event downstream, parse `envelope_json`, require schema/authority fields expected by Phase 1, canonical-serialize with the Phase 1 JSON rules, recompute SHA-256, and require it to equal stored `event_id`. A failure raises and must not produce an ACKable delivery.

- [ ] **Step 4: Harden transaction helpers and busy behavior**

Ensure `BEGIN IMMEDIATE` claim/transition transactions rollback both projection and receipt on any exception. Keep bounded busy timeout behavior; do not spin indefinitely. Independent connection contention must never create two current competing leases.

- [ ] **Step 5: Run all focused Phase 2 tests**

Run: `python -m pytest tests_engine/test_intelligence_delivery.py -q`
Expected: PASS with zero failures.

- [ ] **Step 6: Verify Phase 1 regression suite remains unchanged**

Run: `python -m pytest tests_engine/test_intelligence_fabric.py tests_engine/test_intelligence_fabric_integrity.py -q`
Expected: PASS; Phase 1 event identity/bytes behavior remains unchanged.

- [ ] **Step 7: Commit**

```bash
git add icarus_engine/intelligence_delivery.py tests_engine/test_intelligence_delivery.py
git commit -m "fix: harden intelligence delivery durability and integrity"
```

---

### Task 7: Exact-head repository verification and review handoff

**Files:**
- Modify only if verification reveals a Phase 2 defect: `icarus_engine/intelligence_delivery.py`, `tests_engine/test_intelligence_delivery.py`
- Do not edit unrelated files to force CI green.

**Interfaces:**
- Consumes: Tasks 1–6 complete branch.
- Produces: exact-head verification evidence and review-ready PR; no merge without independent review.

- [ ] **Step 1: Run focused combined intelligence tests locally/in harness**

Run: `python -m pytest tests_engine/test_intelligence_fabric.py tests_engine/test_intelligence_fabric_integrity.py tests_engine/test_intelligence_delivery.py -q`
Expected: PASS.

- [ ] **Step 2: Run Python compile check**

Run: `python -m py_compile icarus_engine/intelligence_delivery.py`
Expected: exit 0.

- [ ] **Step 3: Open a Phase 2 PR stacked on the Phase 1 branch while PR #334 remains unmerged, or retarget to `main` only after Phase 1 merges**

PR body must identify the exact base/head SHAs, TDD RED/GREEN evidence, scope exclusions, authority contract, and relationship to PR #334. Do not flatten or silently reimplement Phase 1.

- [ ] **Step 4: Require exact-head GitHub Actions evidence**

Verify Linux full `tests_engine`, plant setup, control CLI, doctor, and the repository's Windows regression matrix/plant setup all pass at the exact Phase 2 head. Any new commit invalidates prior exact-head evidence.

- [ ] **Step 5: Request independent Claude review through the established coordination lane**

Include exact PR number/head, changed paths, verification run IDs, and explicit instruction not to infer scheduler/UI/Brain ownership transfer.

- [ ] **Step 6: Apply review feedback with new RED→GREEN tests where behavior changes**

Every material defect fix gets a regression test before production correction and requires fresh exact-head CI.

- [ ] **Step 7: Stop at merge gate**

Do not merge until the independent review/evidence gate is satisfied. If Phase 1 PR #334 is not merged yet, keep Phase 2 stacked and reviewable rather than bypassing Phase 1.
