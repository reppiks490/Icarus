# ICARUS Phase 4A Semantic Work Fabric Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic, append-only semantic work protocol over Phase 1 Intelligence Fabric events so humans and agents can request, accept, challenge, delegate, evidence, and complete work without creating a second canonical collaboration store.

**Architecture:** Add one focused production module, `icarus_engine/intelligence_collaboration.py`, that validates collaboration material, creates Phase 1 `IntelligenceEvent` records, publishes only through `IntelligenceFabric.publish()`, retrieves complete work-thread history through Phase 1 public APIs, and projects immutable event history into semantic work state. Phase 2 delivery and Phase 3 live transport remain unchanged and treat collaboration events as ordinary Phase 1 events.

**Tech Stack:** Python 3, stdlib dataclasses/hashlib/json/datetime, existing `icarus_engine.intelligence_fabric` public API, pytest, existing GitHub Actions Linux/Windows test workflow.

**Spec:** `docs/superpowers/specs/2026-10-13-semantic-work-fabric-design.md`

## Global Constraints

- Protocol is exactly `icarus-collaboration-v1`.
- Phase 1 remains the only canonical journal; do not add a second canonical collaboration table/database.
- Preferred production scope is one new file: `icarus_engine/intelligence_collaboration.py`.
- Preferred focused tests are `tests_engine/test_intelligence_collaboration.py`, `tests_engine/test_intelligence_collaboration_state.py`, and `tests_engine/test_intelligence_collaboration_integrity.py`.
- Do not modify `intelligence_fabric.py`, `intelligence_delivery.py`, or `intelligence_gateway.py` unless a correctness requirement proves unavoidable; if that occurs, stop and re-plan rather than silently widening scope.
- Explicitly do not edit server/UI/Field Agent/Brain/brain_sync/providers/collectors/schedulers/workflows/broker/execution/Atlas paths.
- `channel == "collaboration"`, `thread_key == "work:<work_id>"`, and `correlation_id == work_id` for every collaboration event.
- `work_id` is the lowercase SHA-256 hex digest of canonical JSON `[
  "icarus-collaboration-v1", requester_principal, idempotency_key
]`.
- Every non-root transition requires `operation_id`, `expected_head_event_id`, and top-level causation containing the expected head.
- Same-head races are preserved in journal history; only the first sequence-valid transition applies.
- Phase 2 ACK never implies Phase 4A semantic acceptance.
- Principal IDs are declared identities only; Phase 4A does not authenticate them.
- Payload construction must reject normalized collaboration payloads exceeding 30 KiB before Phase 1 publication.
- Principal/group/capability IDs are <=64 chars; idempotency/operation/challenge IDs <=128 chars.
- Work priority is integer 0..5 and is distinct from Phase 1 attention score.
- Terminal states are `COMPLETED`, `FAILED`, `REJECTED`, `CANCELLED`, `EXPIRED` and cannot be resurrected.
- Long work threads must never be knowingly projected from truncated history.
- Every public Phase 4A result preserves `execution_authorized=false` and `production_decision_authorized=false`.
- Phase 4A never calls broker/execution code.
- TDD is mandatory: each production slice follows a demonstrated RED for the intended missing behavior.

## Review Focus

1. **Duplicate/racing roots and operations:** simultaneous identical/conflicting requests must produce deterministic projection without double state changes; Task 3 pins this.
2. **Malformed or foreign events in reserved `work:` threads:** strict projection must fail closed rather than silently skip corruption; Task 5 pins this.
3. **Long thread completeness at exactly/above the Phase 1 1000-record query cap:** projector must fall back to replay and preserve global sequence order; Task 5 pins this.
4. **Group-target semantics:** first valid acceptance wins, one member cannot reject the whole group, and declared identity is not treated as authentication; Tasks 2 and 3 pin this.
5. **Completion under disagreement:** open challenges may survive only when `completed.unresolved_challenge_ids` exactly equals the projector's open set; Task 4 pins this.

---

## File Structure

### New production file

`icarus_engine/intelligence_collaboration.py`

Responsibilities:
- constants/enums and bounded normalization helpers;
- request/work-ID and material-digest derivation;
- `WorkRequest` / transition material dataclasses or equivalent immutable value objects;
- conversion to canonical Phase 1 `IntelligenceEvent` objects;
- complete-thread retrieval;
- pure deterministic projector and conflict diagnostics;
- high-level publication API that appends through Phase 1 then re-projects;
- child-work discovery helpers.

It must not own a second persistence connection/table or duplicate Phase 2 delivery state.

### Focused tests

`tests_engine/test_intelligence_collaboration.py`
- canonical request normalization, IDs, publication envelope, high-level API, discovery.

`tests_engine/test_intelligence_collaboration_state.py`
- lifecycle, actor permissions, concurrency, idempotency, challenges, results, delegation.

`tests_engine/test_intelligence_collaboration_integrity.py`
- malformed/foreign history, authority invariants, full-thread retrieval, payload limits, Phase 1/2/3 integration boundaries.

---

### Task 1: Protocol normalization, canonical IDs, and Phase 1 envelope construction

**Files:**
- Create: `tests_engine/test_intelligence_collaboration.py`
- Create: `icarus_engine/intelligence_collaboration.py`

**Interfaces:**
- Consumes: `icarus_engine.intelligence_fabric.IntelligenceEvent` and `IntelligenceFabric`.
- Produces:
  - `COLLABORATION_PROTOCOL = "icarus-collaboration-v1"`
  - `COLLABORATION_CHANNEL = "collaboration"`
  - `derive_work_id(requester_principal: str, idempotency_key: str) -> str`
  - `request_material_hash(material: Mapping[str, object]) -> str`
  - `@dataclass(frozen=True) WorkRequest`
  - `WorkRequest.normalized() -> dict[str, object]`
  - `WorkRequest.work_id() -> str`
  - `build_request_event(request: WorkRequest, *, observed_at: str, received_at: str, actor_kind: str, assets: Iterable[str] = (), evidence_ids: Iterable[str] = (), parent_causation_ids: Iterable[str] = ()) -> IntelligenceEvent`

`WorkRequest` fields:
- `requester_principal: str`
- `requester_kind: str`
- `target_kind: str`
- `target_id: str`
- `work_kind: str`
- `idempotency_key: str`
- `objective: str`
- `priority: int = 0`
- `constraints: Mapping[str, object] = {}` via safe factory
- `required_capabilities: tuple[str, ...] = ()`
- `reviewer_principals: tuple[str, ...] = ()`
- `deadline: str | None = None`
- `result_contract: Mapping[str, object] | None = None`
- `parent_work_id: str | None = None`
- `parent_event_id: str | None = None`

- [ ] **Step 1: Write failing canonical-ID tests**

Add tests:
- `test_derive_work_id_matches_exact_protocol_requester_key_digest`
- `test_request_normalization_deduplicates_and_sorts_unordered_collections`
- `test_request_limits_reject_oversized_identifiers_objective_and_nonfinite_json`
- `test_request_rejects_unknown_work_kind_target_kind_or_principal_kind`
- `test_request_material_hash_changes_for_semantic_material_but_not_mapping_order`

Assertions must compute the expected digest from `json.dumps([...], sort_keys=True, separators=(",", ":"), ensure_ascii=False)` encoded UTF-8 and SHA-256.

- [ ] **Step 2: Run Task 1 ID tests and verify RED**

Run: `python -m pytest tests_engine/test_intelligence_collaboration.py -q`
Expected: FAIL during import because `icarus_engine.intelligence_collaboration` does not exist.

- [ ] **Step 3: Implement protocol constants, finite-JSON/text/time helpers, work-ID derivation, request normalization, and digest**

Use stdlib only. Reject bool where integer semantics matter. Normalize timezone-aware timestamps to UTC `Z`. Enforce spec limits exactly.

- [ ] **Step 4: Write failing root-envelope tests**

Add:
- `test_build_request_event_uses_reserved_channel_thread_and_correlation`
- `test_request_event_payload_contains_protocol_work_id_transition_and_material_hash`
- `test_decision_root_maps_to_decision_request_event_type`
- `test_nondecision_root_event_type_follows_actor_kind`
- `test_root_preserves_assets_evidence_and_parent_causation`
- `test_root_payload_is_rejected_above_30_kib`
- `test_root_authority_flags_are_false_after_normalization`

- [ ] **Step 5: Run envelope tests and verify RED**

Expected: FAIL because `build_request_event` is absent/incomplete.

- [ ] **Step 6: Implement `build_request_event` minimally**

Map actor kind to Phase 1 event type exactly per spec; decision requests always use `decision_request`. Use Phase 1 top-level assets/evidence/causation rather than duplicating them in payload.

- [ ] **Step 7: Run Task 1 tests GREEN**

Run: `python -m pytest tests_engine/test_intelligence_collaboration.py -q`
Expected: PASS.

- [ ] **Step 8: Commit Task 1**

Commit message: `feat: add semantic work protocol and canonical requests`

---

### Task 2: Pure deterministic projector and legal lifecycle

**Files:**
- Create: `tests_engine/test_intelligence_collaboration_state.py`
- Modify: `icarus_engine/intelligence_collaboration.py`

**Interfaces:**
- Consumes: normalized Phase 1 event mappings from Task 1.
- Produces:
  - `class CollaborationIntegrityError(ValueError)`
  - `@dataclass(frozen=True) WorkConflict` with `event_id: str`, `sequence: int`, `code: str`, `operation_id: str | None`
  - `@dataclass(frozen=True) WorkSnapshot`
  - `project_work(events: Sequence[Mapping[str, object]], *, as_of: str | None = None) -> WorkSnapshot`

`WorkSnapshot` exposes at least:
- `protocol`, `work_id`, `work_kind`, requester identity/kind, target kind/ID, optional assignee;
- parent linkage;
- lifecycle `state`;
- `root_event_id`, `head_event_id`;
- created/updated timestamps, deadline, `deadline_passed`;
- priority/objective/constraints/capabilities/reviewers/result contract;
- latest partial/final result;
- cumulative evidence IDs;
- open/resolved challenge IDs;
- escalation flag;
- applied-event count;
- conflicts tuple;
- integrity status;
- both false authority flags.

- [ ] **Step 1: Write failing root/lifecycle projector tests**

Add tests:
- `test_project_root_produces_open_snapshot`
- `test_principal_target_acceptance_establishes_assignee`
- `test_principal_target_rejection_is_terminal`
- `test_group_target_first_acceptance_establishes_assignee`
- `test_group_member_rejection_is_not_supported`
- `test_accepted_started_partial_started_completion_lifecycle`
- `test_terminal_state_cannot_be_resurrected`

Use small helper factories in the test file to produce already-normalized Phase 1-shaped event mappings with explicit sequence/event IDs.

- [ ] **Step 2: Run Task 2 lifecycle tests RED**

Expected: FAIL because projector/snapshot types are absent.

- [ ] **Step 3: Implement root parsing, lifecycle enum/state application, and snapshot**

Projection input is ascending Phase 1 sequence. Reject empty history as unknown work. Root must be the first valid collaboration request for the work ID.

- [ ] **Step 4: Write failing actor-permission/head-causation tests**

Add:
- `test_requester_may_evidence_challenge_escalate_cancel`
- `test_assignee_only_started_partial_complete_fail`
- `test_declared_reviewer_may_evidence_challenge_escalate_only`
- `test_nonroot_requires_expected_current_head_and_cause`
- `test_system_expiry_requires_deadline_and_system_actor`
- `test_actor_permission_is_semantic_only_not_authentication_claim`

- [ ] **Step 5: Run actor/head tests RED**

Expected: failures for missing permission/head rules.

- [ ] **Step 6: Implement actor permission matrix, expected-head preconditions, causation validation, terminal protection**

A rejected semantic event is a conflict where structurally well-formed; malformed integrity violations raise `CollaborationIntegrityError`.

- [ ] **Step 7: Run Task 1+2 tests GREEN**

Run: `python -m pytest tests_engine/test_intelligence_collaboration.py tests_engine/test_intelligence_collaboration_state.py -q`
Expected: PASS.

- [ ] **Step 8: Commit Task 2**

Commit message: `feat: project semantic work lifecycle deterministically`

---

### Task 3: Operation idempotency, same-head races, and root conflicts

**Files:**
- Modify: `tests_engine/test_intelligence_collaboration_state.py`
- Modify: `icarus_engine/intelligence_collaboration.py`

**Interfaces:**
- Extends `project_work` conflict classification.
- Produces internal canonical operation material digesting sufficient to distinguish identical retry vs conflicting reuse.
- Conflict codes added: `duplicate_root`, `conflicting_root`, `duplicate_operation`, `conflicting_operation`, `stale_head`, `illegal_transition`, `actor_not_permitted`, `missing_required_cause`.

- [ ] **Step 1: Write failing root race/idempotency tests**

Add:
- `test_first_valid_root_wins_and_identical_later_root_is_duplicate`
- `test_same_work_id_different_material_is_conflicting_root`
- `test_duplicate_root_does_not_advance_head_or_applied_count`

- [ ] **Step 2: Run root-race tests RED**

Expected: missing/incomplete root conflict classification.

- [ ] **Step 3: Implement root duplicate/conflict classification by normalized request material hash**

Never mutate the root snapshot from a later root event.

- [ ] **Step 4: Write failing operation retry/race tests**

Add:
- `test_identical_operation_id_retry_returns_duplicate_without_head_advance`
- `test_operation_id_reuse_with_different_material_is_conflict`
- `test_same_head_race_applies_first_sequence_winner_and_marks_loser_stale`
- `test_later_valid_transition_can_continue_from_winning_head`
- `test_group_same_head_double_accept_applies_first_only`

- [ ] **Step 5: Run operation/race tests RED**

Expected: failures because operation digest and race rules are absent/incomplete.

- [ ] **Step 6: Implement operation material digest registry within pure projection and first-sequence-winner rule**

Do not add persistence. Registry exists only during replay/project call.

- [ ] **Step 7: Run Task 1–3 tests GREEN**

Run: `python -m pytest tests_engine/test_intelligence_collaboration.py tests_engine/test_intelligence_collaboration_state.py -q`
Expected: PASS.

- [ ] **Step 8: Commit Task 3**

Commit message: `feat: add semantic work idempotency and race resolution`

---

### Task 4: Challenges, evidence, results, deadlines, and explicit disagreement

**Files:**
- Modify: `tests_engine/test_intelligence_collaboration_state.py`
- Modify: `icarus_engine/intelligence_collaboration.py`

**Interfaces:**
- Extends projector transition-specific validation.
- Adds conflict codes: `challenge_mismatch`, `result_contract_mismatch`, `deadline_violation`.
- Snapshot challenge/evidence/result/deadline fields become fully populated.

- [ ] **Step 1: Write failing challenge tests**

Add:
- `test_unique_challenge_opens_and_response_closes_exact_challenge`
- `test_challenge_response_requires_current_head_and_original_challenge_causes`
- `test_unknown_or_already_closed_challenge_response_does_not_apply`
- `test_completion_with_open_challenges_requires_exact_unresolved_set`
- `test_completion_can_preserve_explicit_unresolved_disagreement`

- [ ] **Step 2: Run challenge tests RED**

Expected: challenge model absent/incomplete.

- [ ] **Step 3: Implement challenge registry and exact unresolved-completion rule**

Preserve original challenge event IDs and resolved/open IDs in snapshot.

- [ ] **Step 4: Write failing evidence/result-contract tests**

Add:
- `test_evidence_accumulates_only_from_applied_events`
- `test_stale_conflicted_event_does_not_add_evidence_or_result`
- `test_json_result_contract_requires_declared_fields`
- `test_event_refs_and_evidence_bundle_contracts_require_references`
- `test_decision_completion_maps_to_decision_response`
- `test_nondecision_partial_and_completed_results_map_to_research_event_type_when_built`

- [ ] **Step 5: Run result/evidence tests RED**

Expected: missing/incomplete result validation.

- [ ] **Step 6: Implement structural result-contract checks and evidence/result projection**

No JSON Schema dependency. Validate only the contract fields the spec defines.

- [ ] **Step 7: Write failing deadline tests**

Add:
- `test_deadline_normalizes_to_utc`
- `test_deadline_before_root_time_is_invalid`
- `test_crossing_deadline_only_sets_derived_deadline_passed`
- `test_predeadline_expired_event_is_deadline_violation`
- `test_postdeadline_system_expiry_applies`

- [ ] **Step 8: Run deadline tests RED then implement deadline projection/expiry validation**

Expected after implementation: PASS.

- [ ] **Step 9: Run Task 1–4 tests GREEN**

Run: `python -m pytest tests_engine/test_intelligence_collaboration.py tests_engine/test_intelligence_collaboration_state.py -q`
Expected: PASS.

- [ ] **Step 10: Commit Task 4**

Commit message: `feat: preserve evidence challenges results and deadlines`

---

### Task 5: Complete-thread retrieval, integrity hardening, and authority invariants

**Files:**
- Create: `tests_engine/test_intelligence_collaboration_integrity.py`
- Modify: `icarus_engine/intelligence_collaboration.py`

**Interfaces:**
- Produces:
  - `load_complete_work_history(fabric: IntelligenceFabric, work_id: str) -> list[dict[str, object]]`
  - `project_work_from_fabric(fabric: IntelligenceFabric, work_id: str, *, as_of: str | None = None) -> WorkSnapshot`
  - optional `diagnose_work_history(...)` only if needed to expose offending event IDs without relaxing strict projection.

- [ ] **Step 1: Write failing reserved-thread/integrity tests**

Add:
- `test_mismatched_thread_correlation_or_payload_work_id_fails_closed`
- `test_foreign_event_inside_reserved_work_thread_fails_closed`
- `test_unsupported_protocol_claiming_reserved_thread_fails_closed`
- `test_authority_true_in_history_fails_closed`
- `test_malformed_payload_cannot_change_semantic_state`

- [ ] **Step 2: Run integrity tests RED**

Expected: missing strict integrity validation.

- [ ] **Step 3: Implement strict envelope/protocol/thread/correlation/authority validation**

Distinguish malformed integrity failures from normal well-formed semantic conflicts.

- [ ] **Step 4: Write failing complete-history retrieval tests**

Use a fake fabric implementing public `thread()` and `replay()` methods only.

Add:
- `test_history_under_1000_uses_thread_fast_path_only`
- `test_exactly_1000_thread_records_triggers_global_replay_fallback`
- `test_over_1000_history_filters_work_thread_and_preserves_global_sequence_order`
- `test_history_retrieval_failure_does_not_return_truncated_projection`

- [ ] **Step 5: Run retrieval tests RED**

Expected: missing `load_complete_work_history`.

- [ ] **Step 6: Implement complete-thread fast path and replay fallback exactly as spec**

When direct `thread(..., limit=1000)` returns exactly 1000, replay globally in pages of 1000 until a short page, filtering only matching thread records.

- [ ] **Step 7: Write failing payload/authority output tests**

Add:
- `test_collaboration_payload_rejects_over_30_kib_before_publish`
- `test_every_snapshot_and_public_record_hard_false_authority`
- `test_nonfinite_transition_material_is_rejected`

- [ ] **Step 8: Implement remaining limits and authority result helper**

- [ ] **Step 9: Run Task 1–5 tests GREEN**

Run: `python -m pytest tests_engine/test_intelligence_collaboration.py tests_engine/test_intelligence_collaboration_state.py tests_engine/test_intelligence_collaboration_integrity.py -q`
Expected: PASS.

- [ ] **Step 10: Commit Task 5**

Commit message: `feat: harden semantic work integrity and complete replay`

---

### Task 6: Publication service, transition builders, delegation, and discovery

**Files:**
- Modify: `tests_engine/test_intelligence_collaboration.py`
- Modify: `tests_engine/test_intelligence_collaboration_state.py`
- Modify: `icarus_engine/intelligence_collaboration.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) TransitionRequest` or equivalent normalized value object containing work ID, transition, actor principal/kind, operation ID, expected head event ID, transition data, evidence IDs, assets, additional causation IDs.
  - `build_transition_event(snapshot: WorkSnapshot, transition: TransitionRequest, *, observed_at: str, received_at: str) -> IntelligenceEvent`
  - `class IntelligenceCollaboration`
  - `IntelligenceCollaboration.__init__(fabric: IntelligenceFabric)`
  - `create_work(request: WorkRequest, *, observed_at: str, received_at: str, assets: Iterable[str] = (), evidence_ids: Iterable[str] = ()) -> dict[str, object]`
  - `append_transition(transition: TransitionRequest, *, observed_at: str, received_at: str) -> dict[str, object]`
  - `snapshot(work_id: str, *, as_of: str | None = None) -> WorkSnapshot`
  - `history(work_id: str) -> list[dict[str, object]]`
  - `children(parent_work_id: str, *, limit: int = 100) -> list[dict[str, object]]`

Publication result fields:
- `event_id`, `sequence`, `applied`, optional `conflict_code`, `head_event_id`, `state`, optional `original_event_id` for duplicates, and both false authority flags.

- [ ] **Step 1: Write failing high-level create/publish tests**

Add:
- `test_create_work_publishes_through_fabric_and_reprojects_result`
- `test_identical_root_retry_reports_duplicate_without_new_semantic_state`
- `test_conflicting_request_material_is_reported_not_silently_rewritten`
- `test_publication_success_does_not_imply_semantic_application`

Use an actual in-memory `IntelligenceFabric` for these focused integration tests.

- [ ] **Step 2: Run create/publish tests RED**

Expected: `IntelligenceCollaboration` absent.

- [ ] **Step 3: Implement collaboration service create/snapshot/history and post-publish re-projection**

Never infer semantic success from `fabric.publish()` alone.

- [ ] **Step 4: Write failing transition-builder/publication tests**

Add:
- `test_transition_event_copies_current_head_into_expected_head_and_causation`
- `test_duplicate_operation_retry_returns_original_event_reference`
- `test_stale_head_publication_remains_history_but_reports_not_applied`
- `test_delivery_ack_has_no_collaboration_acceptance_side_effect`

The final assertion is proven by publishing/delivering or by showing no Phase 2 receipt appears in collaboration projection; do not modify Phase 2.

- [ ] **Step 5: Run transition tests RED then implement `build_transition_event` and `append_transition`**

Builders must apply event-type mapping from spec, but the semantic `transition` payload is authoritative.

- [ ] **Step 6: Write failing delegation tests**

Add:
- `test_child_request_requires_parent_clean_nonterminal_assignable_state`
- `test_child_requester_must_be_parent_assignee`
- `test_child_parent_event_must_equal_parent_current_head`
- `test_child_root_top_level_causation_contains_parent_head`
- `test_children_discovers_parent_tagged_child_requests`
- `test_parent_cancel_does_not_automatically_cancel_child`

- [ ] **Step 7: Run delegation tests RED then implement child validation and `children()` discovery**

Discovery may use Phase 1 indexed tags/query but semantic correctness must verify child root material after retrieval.

- [ ] **Step 8: Run Task 1–6 tests GREEN**

Run: `python -m pytest tests_engine/test_intelligence_collaboration.py tests_engine/test_intelligence_collaboration_state.py tests_engine/test_intelligence_collaboration_integrity.py -q`
Expected: PASS.

- [ ] **Step 9: Commit Task 6**

Commit message: `feat: publish and delegate semantic work contracts`

---

### Task 7: Phase integration, full regression, exact-head CI, and independent review

**Files:**
- Modify tests only if a demonstrated integration gap requires a regression test.
- Do not broaden production scope without re-planning.

**Interfaces:**
- Final deliverable is a stacked Phase 4A implementation PR based on the approved Phase 4A spec/plan history and frozen Phase 3 head ancestry.

- [ ] **Step 1: Run focused collaboration suite**

Run: `python -m pytest tests_engine/test_intelligence_collaboration.py tests_engine/test_intelligence_collaboration_state.py tests_engine/test_intelligence_collaboration_integrity.py -q`
Expected: PASS.

- [ ] **Step 2: Run prerequisite regression suites**

Run: `python -m pytest tests_engine/test_intelligence_fabric.py tests_engine/test_intelligence_delivery.py tests_engine/test_intelligence_delivery_competing.py tests_engine/test_intelligence_delivery_retry.py tests_engine/test_intelligence_delivery_observability.py tests_engine/test_intelligence_delivery_integrity.py tests_engine/test_intelligence_gateway.py tests_engine/test_intelligence_gateway_security.py tests_engine/test_intelligence_gateway_transport.py tests_engine/test_intelligence_gateway_sse.py tests_engine/test_intelligence_gateway_review.py -q`
Expected: PASS.

- [ ] **Step 3: Verify branch scope against frozen Phase 3 head**

Compare against `46118f49200f0acf20c4a00471601e7924850fe9` and confirm changed production scope is only `icarus_engine/intelligence_collaboration.py` plus Phase 4A tests/docs.

- [ ] **Step 4: Run full Linux repository suite**

Run: `python -m pytest tests_engine -q`
Expected: PASS.

- [ ] **Step 5: Run plant/control/doctor checks matching repository CI**

Run:
- `python -m icarus_plant --root /tmp/icarus-plant-ci setup`
- `icarus-control --help`
- `python -m icarus_engine.cli doctor --json`
Expected: all exit successfully.

- [ ] **Step 6: Push exact implementation head and require GitHub Actions Linux + Windows GREEN**

Capture workflow IDs and exact SHA. Do not claim verification from a previous head.

- [ ] **Step 7: Open stacked PR**

Base it on the Phase 3 implementation branch unless prerequisite merges require a mechanically updated stack. PR body must state dependency on PR #336 and earlier review gates; do not retarget around them.

- [ ] **Step 8: Request independent Claude review through coordination**

Review focus:
- replay determinism and >1000 completeness;
- semantic vs integrity failure classification;
- idempotency/race handling;
- challenge disagreement preservation;
- declared-vs-authenticated identity boundary;
- delegation ancestry;
- absence of Phase 1–3 semantic mutation;
- hard-false authority.

- [ ] **Step 9: Process review feedback before merge**

If feedback arrives, invoke `superpowers:receiving-code-review` before changing code. Critical/Important findings must be resolved with TDD and fresh exact-head verification.

- [ ] **Step 10: Do not merge around prerequisite review gates**

PR #334 → #335 → #336 → Phase 4A remain ordered unless their reviewed/merged state changes legitimately.

---

## Self-Review Record

### Spec coverage

Mapped all spec areas to tasks:
- protocol/IDs/request material/envelope: Task 1;
- lifecycle/actors/head/causation: Task 2;
- root/operation idempotency and concurrency: Task 3;
- challenges/evidence/results/deadlines: Task 4;
- integrity/full-history/limits: Task 5;
- public publication API/delegation/discovery: Task 6;
- Phase 1–3 regressions/CI/review: Task 7.

No spec section requires a Phase 1–3 production edit.

### Type consistency

`WorkRequest` creates root events; `WorkSnapshot` is produced only by projection; `TransitionRequest` consumes a current snapshot/head; `IntelligenceCollaboration` is the stateful facade only in the sense that it owns a reference to the existing Phase 1 fabric, not its own persistence.

### Review-focus coverage

- duplicate/race behavior: Tasks 3 and 6;
- malformed reserved thread: Task 5;
- >1000 history: Task 5;
- group-target semantics: Tasks 2/3;
- unresolved challenge completion: Task 4.

### Scope/proportion

The plan creates one production module and three test modules. It deliberately avoids a new database, broker, gateway protocol, authentication layer, scheduler, room system, capability registry, or UI. Those remain Phase 4B+.

### Execution method

Preserve previously supplied **Native** execution for this harness once the mandatory plan-review gate is crossed.
