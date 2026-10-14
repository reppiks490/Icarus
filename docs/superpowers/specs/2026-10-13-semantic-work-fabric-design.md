# ICARUS Phase 4A — Semantic Work Fabric design

Date: 2026-10-13
Owner: ChatGPT/Codex
Status: design specification
Protocol: `icarus-collaboration-v1`
Parent stack:
- Phase 1: `icarus-intelligence-fabric-v1`
- Phase 2: durable Intelligence Delivery Plane
- Phase 3: Live Intelligence Gateway, PR #336

## 1. Purpose

Phase 4A turns the existing ICARUS intelligence stack from an event/transport system into a machine-native collaboration system.

The unit of collaboration is not a chat message. It is a durable semantic work contract whose entire lifecycle is represented by immutable Phase 1 intelligence events.

A work contract can request research, evidence collection, anomaly investigation, model review, risk review, hypothesis challenge, cross-verification, a bounded decision, delegated work, or synthesis.

The system must preserve the request, declared participants, causal chain, evidence references, partial/final outputs, disagreement, delegation ancestry, lifecycle state, concurrency conflicts, deadlines, idempotency, and authority invariants.

The full semantic state must be reconstructible from the append-only Intelligence Fabric alone.

## 2. Success criteria

Phase 4A is successful when ICARUS can deterministically represent and replay a thread such as:

1. an agent requests an NQ regime investigation;
2. another agent accepts;
3. the assignee starts work;
4. evidence and a partial result arrive;
5. the requester challenges one inference;
6. the assignee delegates historical verification to a child work item;
7. the child work completes;
8. the assignee responds to the challenge using child/evidence references;
9. the parent completes with a traceable synthesis;
10. replay produces the same state, head, conflicts, challenge set, evidence set, and result.

No prose-only conversation is required for correctness.

## 3. Architectural boundary

Phase 4A is an additive semantic subsystem above Phase 1.

It must not become:
- a second canonical event/message database;
- a second delivery broker;
- a scheduler replacement;
- a chat-room store;
- an execution command plane;
- an authentication service.

The larger collaboration program remains decomposed as:
- 4A: semantic work core;
- 4B: authenticated command ingress and principal binding;
- 4C: incident rooms, escalation routing, capability presence;
- 4D: autonomous work decomposition/synthesis councils;
- 4E: immersive human command UI.

## 4. Selected architecture

Phase 4A is a strict semantic protocol layered over existing `IntelligenceEvent` records.

Canonical persistence remains Phase 1 `fabric_events`.

The new module validates collaboration material, creates collaboration-shaped `IntelligenceEvent` objects, publishes through the public `IntelligenceFabric.publish()` API, reads through public `thread/query/replay` APIs, and deterministically projects semantic state.

No Phase 4A canonical table is added.

A future disposable materialized projection may be allowed only if it is fully rebuildable from Phase 1 and never treated as truth.

## 5. Rejected architectures

### 5.1 Expanding Phase 1 with many new event types

Rejected for 4A. Existing types already cover human/agent notes, research, decisions, and system events. Collaboration semantics belong in the versioned collaboration payload.

### 5.2 Separate collaboration/chat database

Rejected because it creates split-brain history.

### 5.3 New broker/orchestrator

Rejected because Phase 2 already owns durable delivery and Phase 3 owns live transport.

## 6. Canonical work thread

A work thread is identified by `work_id` and represented by Phase 1 events whose:
- `channel == "collaboration"`;
- `thread_key == "work:<work_id>"`;
- `correlation_id == <work_id>`;
- payload protocol is `icarus-collaboration-v1`.

The `work:` thread namespace is reserved by Phase 4A.

Once a valid root exists, any foreign/non-collaboration event in that exact `work:` thread is an integrity anomaly under strict projection rather than silently participating in state.

## 7. Work kinds

Supported normalized kinds:
- `research`
- `evidence`
- `investigation`
- `model_review`
- `risk_review`
- `hypothesis_challenge`
- `cross_verification`
- `decision`
- `delegation`
- `synthesis`

Unknown kinds fail validation.

## 8. Exact identifier limits

To remain compatible with Phase 1 tag limits:
- principal ID: 1..64 Unicode characters after trimming;
- group/target ID: 1..64;
- idempotency key: 1..128;
- operation ID: 1..128;
- challenge ID: 1..128;
- capability identifier: 1..64;
- reviewer count: <=32;
- capability count: <=32;
- objective: 1..2000 characters;
- failure/challenge summary: <=2000 characters.

Collections are normalized, deduplicated, and deterministically ordered where order has no semantic meaning.

## 9. Declared principal model

A principal has:
- `principal_id`;
- `principal_kind` in `agent | human | system`.

Phase 4A validates semantic consistency only. It does **not** authenticate the claimed principal.

Untrusted clients must not gain arbitrary Phase 4A publication rights until Phase 4B binds authenticated transport identity to principal identity.

This is compatible with Phase 3 because Phase 3 does not currently expose arbitrary inbound event publication.

## 10. Target model

A request target is:
- `principal`, or
- `group`.

Fields:
- `target_kind`;
- `target_id`.

Capability-based dynamic targeting is deferred to Phase 4C. `required_capabilities` may still be declared as request metadata.

## 11. Canonical work ID

Every root request requires a requester-scoped `idempotency_key`.

After trimming/validating requester and key, the work ID is exactly:

```text
sha256(utf8(canonical_json([
  "icarus-collaboration-v1",
  requester_principal,
  idempotency_key
])))
```

`canonical_json` uses UTF-8 JSON with no insignificant whitespace and stable string encoding.

The public `work_id` is the 64-character lowercase hexadecimal SHA-256 digest.

Therefore `work:<work_id>` and `parent:<work_id>` remain inside Phase 1 thread/tag limits.

## 12. Request-material digest

The root request contains a `request_material_hash` over canonical normalized request material.

The hash includes semantic request fields such as requester, target, kind, objective, constraints, capabilities, reviewers, deadline, priority, result contract, and parent linkage.

It excludes Phase 1 journal sequence, event ID, attention score, received timestamp, and other storage-derived values.

Reusing the same requester + idempotency key with identical normalized material is idempotent.

Reusing it with different normalized material is a request-material conflict.

## 13. Operation idempotency

Every non-root semantic transition requires an `operation_id` chosen by the actor.

Within one work thread:
- first valid occurrence of an operation ID owns that semantic operation;
- a retry with identical normalized operation material is `duplicate_operation` and returns/references the first operation rather than changing state;
- reuse with different material is `conflicting_operation` and is not applied.

This permits safe client retry after a lost response without manufacturing a new semantic state transition.

Cross-process simultaneous duplicates may both be durably appended; projection resolves them deterministically by Phase 1 sequence.

## 14. Root request material

A valid root request contains:
- `protocol`;
- `work_id`;
- `transition = "requested"`;
- `requester_principal`;
- `requester_kind`;
- `target_kind`;
- `target_id`;
- `work_kind`;
- `idempotency_key`;
- `request_material_hash`;
- `objective`;
- optional `constraints`;
- optional `required_capabilities`;
- optional `reviewer_principals`;
- optional `deadline`;
- `priority`;
- optional `result_contract`;
- optional `parent_work_id`;
- optional `parent_event_id`.

Top-level Phase 1 fields remain canonical for assets, evidence IDs, causation IDs, severity, urgency, and timestamps.

## 15. Structured constraints

Natural-language `objective` is human-readable context, not a parser-dependent state machine input.

Machine-relevant constraints belong in finite JSON `constraints`, for example:
- allowed data sources;
- time horizon;
- asset universe;
- required statistical tests;
- prohibited inference classes;
- budget metadata;
- evidence requirements.

`constraints` is structurally validated but domain-specific semantics are owned by the worker/consumer.

## 16. Result contract

Optional `result_contract` supports:
- `result_kind`: `json | event_refs | evidence_bundle | decision | text_plus_refs`;
- optional bounded unique `required_fields`;
- optional `schema_id`;
- optional `schema_version`.

Phase 4A performs structural validation only. It does not add a general JSON Schema dependency.

For JSON-like results, required fields must exist. Reference-oriented result kinds must contain the required reference collections.

Passing structural validation never implies domain correctness.

## 17. Payload-size budget

Phase 1 already caps payload JSON at 32 KiB.

Phase 4A must reject collaboration payload construction before Phase 1 publication if the normalized collaboration payload exceeds 30 KiB, leaving margin for deterministic wrapper fields while remaining below the Phase 1 hard limit.

Individual `constraints`, `result_contract`, result/failure/challenge metadata should be bounded so the complete normalized collaboration payload remains below this threshold.

No result should embed large raw datasets; use event/evidence/file references.

## 18. Parent/child work

Delegation is ordinary child work, not a second mutable task tree.

A delegated child root includes:
- `parent_work_id`;
- `parent_event_id` equal to the parent's currently applied semantic head;
- top-level `causation_ids` containing that parent event ID.

Creation is valid only when:
- parent exists and projects cleanly;
- parent state is `ACCEPTED`, `IN_PROGRESS`, or `PARTIAL`;
- child requester is the parent's current assignee;
- supplied parent event equals the parent's current semantic head.

Child cancellation is not automatically cascaded from parent cancellation in 4A.

## 19. Semantic transitions

Supported transitions:
- `requested`
- `accepted`
- `started`
- `partial_result`
- `evidence_added`
- `challenge`
- `challenge_response`
- `escalated`
- `completed`
- `failed`
- `rejected`
- `cancelled`
- `expired`

No free-form transition names are accepted.

## 20. Lifecycle states

States:
- `OPEN`
- `ACCEPTED`
- `IN_PROGRESS`
- `PARTIAL`
- `COMPLETED`
- `FAILED`
- `REJECTED`
- `CANCELLED`
- `EXPIRED`

Terminal states:
- `COMPLETED`
- `FAILED`
- `REJECTED`
- `CANCELLED`
- `EXPIRED`

Evidence, challenge, challenge-response, and escalation events advance semantic head without necessarily changing lifecycle state.

## 21. Lifecycle transition table

- root `requested` -> `OPEN`;
- principal target: `OPEN + accepted` -> `ACCEPTED`;
- principal target: `OPEN + rejected` -> `REJECTED`;
- group target: `OPEN + accepted` -> `ACCEPTED` and accepting principal becomes assignee;
- group-target `rejected` is **not supported** because one group member cannot reject work for the entire group; non-accepting members simply do not claim semantic ownership;
- `ACCEPTED + started` -> `IN_PROGRESS`;
- `PARTIAL + started` -> `IN_PROGRESS`;
- `ACCEPTED | IN_PROGRESS | PARTIAL + partial_result` -> `PARTIAL`;
- `ACCEPTED | IN_PROGRESS | PARTIAL + completed` -> `COMPLETED`;
- `ACCEPTED | IN_PROGRESS | PARTIAL + failed` -> `FAILED`;
- requester may `cancelled` any non-terminal state -> `CANCELLED`;
- system may `expired` any non-terminal state after deadline -> `EXPIRED`.

Terminal states cannot be resurrected.

## 22. Semantic head

Every non-root transition requires `expected_head_event_id`.

It must equal the currently applied semantic head before that transition.

Top-level Phase 1 `causation_ids` must contain that same head event ID.

Additional causal IDs are permitted when transition-specific rules require them.

## 23. Optimistic concurrency and forks

Phase 1 does not expose an atomic compare-and-append thread-head primitive.

Therefore two processes can race after observing the same semantic head.

Phase 4A resolves this without a second canonical table:
1. both well-formed events may be appended;
2. replay is ordered by immutable Phase 1 sequence;
3. the first event whose precondition matches the current applied head is applied;
4. later stale-head events are classified `stale_head`;
5. stale/conflicted events remain immutable history but do not change lifecycle, assignee, challenges, evidence accumulation, result, or head;
6. Phase 4A re-projects after publication and reports whether its newly appended event actually applied.

Concurrency loss is auditable rather than destructive.

## 24. Root races

The first valid `requested` event for a derived work ID becomes semantic root.

Later identical material is `duplicate_root`.

Later different material is `conflicting_root`.

Neither advances semantic head.

## 25. Actor permissions

### Requester
May create root, add evidence, challenge, escalate, and cancel non-terminal work.

### Principal target
Only the exact target principal may accept or reject while state is `OPEN`. Acceptance establishes assignee.

### Group target
Any declared principal delivered/routed to the group may semantically attempt acceptance; the first applied acceptance establishes assignee. 4A cannot prove membership cryptographically. Group membership/routing remains Phase 2 data, and authenticated binding is Phase 4B.

A group-target actor cannot issue a group-wide semantic rejection in 4A.

### Assignee
May start, add evidence, publish partial results, answer challenges, escalate, complete, fail, and create valid child work.

### Reviewer
Declared reviewers may add evidence, challenge, and escalate only.

### System
System actors may issue `expired` only after deadline. System identity remains a declared identity until Phase 4B.

## 26. Challenge model

A challenge contains:
- unique `challenge_id`;
- bounded claim/question;
- optional finite metadata;
- optional top-level evidence references.

A challenge response contains:
- existing open `challenge_id`;
- bounded response/result material;
- top-level causation containing both current semantic head and original challenge event ID;
- optional evidence references.

A valid response closes exactly that challenge.

Unknown/already-closed challenge responses are not applied.

## 27. Completion with unresolved challenges

Completion with open challenges is allowed only if `completed` explicitly lists `unresolved_challenge_ids`.

That list must exactly equal the projector's current open-challenge set.

Omission or mismatch prevents semantic application.

Thus disagreement can survive into a final result but can never be silently erased.

## 28. Evidence semantics

Canonical evidence identity remains top-level Phase 1 `evidence_ids`.

Phase 4A does not duplicate large evidence bodies into semantic payloads.

`evidence_added`, `partial_result`, `challenge`, `challenge_response`, and `completed` may add evidence refs.

The projection exposes cumulative evidence plus per-event provenance.

## 29. Result semantics

`partial_result` and `completed` may carry bounded finite JSON result material.

A result may reference child work completion events rather than embed child outputs.

Structural result-contract validation occurs before semantic application.

## 30. Decision work mapping

For `work_kind=decision`:
- root event type is `decision_request`;
- applied final completion event type is `decision_response`.

A decision response remains research/collaboration output. It does not authorize trading or production execution.

## 31. Non-decision Phase 1 event-type mapping

- human lifecycle/control event -> `human_note`;
- agent lifecycle/control event -> `agent_note`;
- system lifecycle/control event -> `system`;
- `partial_result` or `completed` for research/evidence/investigation/review/synthesis work -> `research`;
- system-created non-decision root -> `system`;
- human-created non-decision root -> `human_note`;
- agent-created non-decision root -> `agent_note`.

The collaboration payload transition is the authoritative semantic discriminator.

## 32. Event envelope mapping

Every collaboration event uses:
- `channel = "collaboration"`;
- `thread_key = "work:<work_id>"`;
- `correlation_id = <work_id>`;
- `source = actor_principal`;
- `source_kind = actor_kind`;
- bounded human-readable title/body that projection does not parse;
- top-level `assets`, `evidence_ids`, and `causation_ids`;
- bounded routing/discovery tags;
- strict collaboration payload.

## 33. Collaboration payload shape

Every payload contains at minimum:

```json
{
  "protocol": "icarus-collaboration-v1",
  "work_id": "<64 hex>",
  "transition": "<enum>",
  "actor_principal": "...",
  "actor_kind": "agent|human|system",
  "operation_id": "... or null for root",
  "expected_head_event_id": "... or null for root",
  "data": {}
}
```

Root additionally carries normalized request material and its digest.

Later transitions may not redefine stable root identity fields.

## 34. Routing/discovery tags

Safe tags may include:
- `collaboration:v1`
- `work-kind:<kind>`
- `to:<principal>`
- `group:<group>`
- `requester:<principal>`
- `assignee:<principal>`
- `parent:<work_id>`
- `transition:<transition>`.

The 64-character principal/target limits keep these tags within Phase 1's 80-character tag-item limit.

Tags are discovery/routing hints only.

Current Phase 2 tag filtering is OR-within-the-configured tag collection. Semantic authorization and correctness must never rely on multiple-tag conjunction.

## 35. Phase 2 integration

Phase 2 remains the durable delivery owner.

Subscriptions may route collaboration events by channel, one or more tags, event type, source, asset, or severity.

Critical invariant:

**Phase 2 ACK means a delivery was processed. It does not mean semantic work was accepted.**

Only an applied Phase 4A `accepted` event accepts work.

## 36. Phase 3 integration

Phase 3 streams collaboration events exactly like other Phase 1 events delivered through Phase 2.

Phase 4A adds no WebSocket/SSE protocol and does not modify the gateway.

## 37. Pure deterministic projector

The projector consumes complete Phase 1 history for one work thread in ascending journal sequence.

For each event it checks:
1. Phase 1 schema and hard authority flags;
2. reserved thread namespace;
3. collaboration channel/protocol;
4. work/thread/correlation consistency;
5. structural transition shape;
6. root/operation idempotency;
7. actor permissions;
8. expected-head precondition;
9. required causation;
10. lifecycle legality;
11. challenge/result/deadline transition-specific rules.

Projection is pure with respect to ordered input events plus an optional `as_of` used only for derived deadline status.

## 38. Complete-thread retrieval

Projection must never silently truncate a thread.

Fast path:
- call `IntelligenceFabric.thread(work_thread, limit=1000)`;
- if fewer than 1000 events are returned, that is the complete thread under current API semantics.

Fallback when exactly 1000 are returned:
- page through global `IntelligenceFabric.replay(after_sequence=..., limit=1000)` until a page contains fewer than 1000 records;
- retain only records whose thread key matches the work thread;
- preserve global Phase 1 sequence ordering.

This avoids changing Phase 1 while still allowing work threads longer than the direct query cap.

Implementations may optimize later, but may not project from a knowingly truncated thread.

## 39. Work snapshot

A snapshot contains at least:
- protocol and work ID;
- work kind;
- requester identity/kind;
- target kind/ID;
- assignee if accepted;
- parent linkage if any;
- lifecycle state;
- root/head event IDs;
- created/updated times;
- deadline and derived `deadline_passed` when `as_of` is supplied;
- priority/objective/constraints;
- required capabilities/reviewers;
- result contract;
- latest partial/final result metadata;
- cumulative evidence IDs;
- open/resolved challenge IDs;
- escalation flag;
- applied-event count;
- semantic conflict records;
- integrity status;
- `execution_authorized=false`;
- `production_decision_authorized=false`.

## 40. Semantic conflict classes

Well-formed but unapplied events may be classified:
- `duplicate_root`
- `conflicting_root`
- `duplicate_operation`
- `conflicting_operation`
- `stale_head`
- `illegal_transition`
- `actor_not_permitted`
- `missing_required_cause`
- `challenge_mismatch`
- `result_contract_mismatch`
- `deadline_violation`.

Conflicts remain immutable history and do not advance semantic head.

## 41. Malformed/integrity failures

Malformed collaboration claims are not normal conflicts.

Examples:
- unsupported protocol value/type;
- mismatched work/thread/correlation IDs;
- authority flag violation;
- invalid finite JSON;
- required structural fields absent;
- foreign event inside a reserved work thread.

Strict projection fails closed with a dedicated integrity error rather than continuing with potentially false state.

A diagnostic history API may expose offending event IDs separately.

## 42. Deadline and expiry semantics

Optional deadline is timezone-aware ISO-8601 normalized to UTC and may not precede root receipt/observation boundary.

Crossing the deadline does not mutate the journal automatically.

At `as_of`, projection may expose `deadline_passed=true` while durable lifecycle remains unchanged.

Durable `EXPIRED` requires an explicit applied `expired` event from a system actor at/after deadline.

## 43. Time semantics

Phase 1 `sequence` controls replay ordering.

Phase 1 `observed_at` and `received_at` remain canonical event timestamps.

Client timestamps never override journal order or semantic-head causality.

Deadline comparison is UTC-normalized.

## 44. Priority vs attention

Work `priority` is an integer `0..5`.

It is separate from Phase 1 attention score.

A writer may map priority into event severity where appropriate, but semantic correctness never depends on attention ranking.

## 45. Cancellation semantics

Only requester cancellation is a Phase 4A lifecycle cancellation.

Cancellation does not rewrite existing Phase 2 delivery state and does not automatically cancel child work.

A consumer acting on older delivered events should project the latest work state before new expensive/cancellation-sensitive work where appropriate.

## 46. Failure semantics

`failed` includes:
- stable bounded failure code;
- bounded summary;
- retryability hint;
- optional finite diagnostic metadata;
- optional top-level evidence references.

Failure does not auto-create retry work. A semantically new retry uses a new requester idempotency key unless later orchestration defines a higher-level retry policy.

## 47. Escalation semantics

`escalated` is an immutable semantic marker containing actor, bounded reason code/summary, and optional intended target metadata.

It does not create a room, page a user, or establish presence. Those effects belong to Phase 4C.

## 48. High-level API boundary

Expected module: `icarus_engine/intelligence_collaboration.py`.

Expected public capabilities:
- create a request;
- append a transition with operation idempotency;
- convenience helpers where they reduce invalid states;
- project current semantic state;
- return semantic/raw history diagnostics;
- discover child work;
- query work by supported Phase 1-indexable criteria.

Exact Python signatures belong in the implementation plan.

## 49. Publication result

After publication, Phase 4A re-projects and returns:
- Phase 1 event ID/sequence;
- whether the semantic event applied;
- semantic conflict code when not applied;
- current semantic head;
- current lifecycle state;
- original event reference for duplicate operation retries where applicable;
- hard false authority flags.

A successful Phase 1 append is not automatically a successful semantic state change.

## 50. Error categories

Stable error families must distinguish:
- invalid request/transition material;
- request-material conflict;
- unknown work;
- reserved-thread integrity failure;
- malformed collaboration event;
- illegal transition;
- actor not permitted;
- stale semantic head;
- missing causation;
- challenge mismatch;
- result-contract mismatch;
- deadline violation;
- payload/identifier limit violation;
- complete-history retrieval failure.

## 51. Authority invariants

Every Phase 4A event and public result preserves:
- `execution_authorized = false`;
- `production_decision_authorized = false`.

No semantic transition can change them.

Phase 4A never calls broker/execution code.

## 52. Security boundary

Phase 4A explicitly does not provide:
- principal authentication;
- cryptographic signatures;
- RBAC/tenant isolation;
- remote publication authorization;
- secret distribution.

These belong to 4B+.

Declared actor permission checks are semantic validation, not proof of real-world identity.

## 53. Logging

Logs may include work ID, event ID, transition, lifecycle state, declared principal, and conflict code.

Logs should not emit complete result/evidence payloads by default.

Phase 3 bearer/ticket/lease secret redaction remains unchanged.

## 54. Observability

A snapshot/diagnostic surface should expose at least:
- applied event count;
- conflict count/categories;
- open challenge count;
- state;
- deadline-passed status;
- integrity status.

Global dashboards/metrics aggregation are deferred.

## 55. Testing contract

Implementation is TDD-first.

### Root/idempotency
- exact canonical work-ID derivation;
- identical request retry;
- conflicting request-material reuse;
- simultaneous root race resolution.

### Operation idempotency
- lost-response retry returns original semantic operation;
- duplicate identical operation does not advance head twice;
- conflicting operation-ID reuse does not apply.

### Lifecycle
- every legal transition;
- illegal transitions;
- terminal-state non-resurrection;
- partial/start behavior;
- principal rejection vs group non-rejection.

### Actors
- requester permissions;
- principal-target acceptance/rejection;
- group first-accept assignee;
- assignee-only actions;
- reviewer limits;
- system expiry.

### Concurrency
- same-head race applies first sequence winner only;
- stale event remains history but not state;
- later valid transition can proceed from winning head.

### Causation
- every non-root applied event requires current-head cause;
- challenge response requires challenge cause;
- delegated child requires parent head cause;
- child requester must be parent assignee.

### Challenges
- unique challenge IDs;
- exact challenge closure;
- unknown/closed challenge response blocked;
- completion with open challenges requires exact unresolved list.

### Evidence/results
- evidence accumulation/provenance;
- result-contract structural checks;
- child result references preserved.

### Thread completeness
- <1000 event fast path;
- exactly-1000 path triggers replay fallback;
- >1000 thread projects completely without silent truncation.

### Integrity
- thread/correlation/work mismatch fails closed;
- unsupported protocol claiming collaboration fails closed;
- foreign event in reserved work thread fails closed;
- malformed payload cannot change state;
- authority flags hard false.

### Deadlines
- normalization;
- pre-deadline expiry blocked;
- post-deadline system expiry accepted;
- deadline crossing without event changes only derived `deadline_passed`.

### Phase integration
- Phase 1 tests green;
- Phase 2 tests green;
- Phase 3 tests green;
- collaboration events route normally through Phase 2;
- Phase 2 ACK never creates semantic acceptance.

### Regression
- full Linux `tests_engine` green;
- Windows repository regression matrix green.

## 56. Planned file boundaries

Expected new production file:
- `icarus_engine/intelligence_collaboration.py`

Expected focused tests:
- `tests_engine/test_intelligence_collaboration.py`
- `tests_engine/test_intelligence_collaboration_state.py`
- `tests_engine/test_intelligence_collaboration_integrity.py`

Documentation:
- this spec;
- later implementation plan.

## 57. Explicitly excluded production scope

Preferred implementation has zero changes to Phase 1–3 production modules.

Do not edit unless the later implementation plan proves an unavoidable correctness requirement:
- `icarus_engine/intelligence_fabric.py`;
- `icarus_engine/intelligence_delivery.py`;
- `icarus_engine/intelligence_gateway.py`.

Explicitly outside 4A:
- `icarus_engine/server.py`;
- UI/dashboard assets;
- Field Agent;
- Brain / brain_sync;
- providers/collectors;
- schedulers/workflows;
- broker/execution modules;
- Atlas `research_allocation/**`.

## 58. Compatibility

Phase 4A is additive.

Non-collaboration Phase 1 events remain unchanged.

Phase 2/3 treat collaboration events as ordinary immutable intelligence events.

No existing subscription requires migration solely because 4A exists.

## 59. Example

1. `requested`: requester asks `macro-agent` to investigate NQ rate sensitivity.
2. `accepted`: macro-agent becomes assignee.
3. `started`.
4. `evidence_added`: rate-event references.
5. `partial_result`.
6. `challenge`: requester disputes causal direction.
7. child `requested`: macro-agent delegates historical-analogue verification from current parent head.
8. child completes.
9. `challenge_response`: parent assignee references child completion/evidence.
10. `completed`: final synthesis lists any unresolved challenge IDs exactly.

Every applied transition is causally chained and replayable.

## 60. Beyond-IB property

The objective is not merely better messaging.

ICARUS should be able to say, in machine-readable form:

> investigate this anomaly, use these constraints, prove or challenge these claims, involve these reviewers, delegate this subproblem, preserve disagreement, return this output shape, and show the complete evidence/causal chain.

Humans and agents later observe/intervene in that same work graph without becoming a separate canonical storage model.

## 61. Deferred 4B+

Deferred:
- authenticated actor binding/signatures;
- arbitrary inbound publication through Phase 3;
- capability advertisements/dynamic matching;
- presence/typing;
- rooms/incident lifecycle;
- automatic escalation routing;
- autonomous work decomposition/council policies;
- automatic child cancellation;
- UI/mobile surfaces;
- any production execution authority.

## 62. Final invariants

1. Phase 1 remains canonical truth.
2. There is no second canonical collaboration database.
3. Work state is deterministic replayable projection.
4. Root and transition retries have semantic idempotency.
5. Every applied non-root transition names and causes from the current semantic head.
6. Same-head races are preserved but only the deterministic winner changes state.
7. Phase 2 ACK is never semantic acceptance.
8. Evidence, disagreement, and causation are first-class.
9. Delegation is ordinary child work with explicit ancestry.
10. Group members cannot individually reject a whole group-target request.
11. Principal strings are declared identities only until Phase 4B.
12. Long work threads are never silently truncated.
13. Both authority flags remain hard false.
14. Phase 4A never touches execution.
