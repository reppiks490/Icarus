# ICARUS Phase 4A — Semantic Work Fabric design

Date: 2026-10-13
Owner: ChatGPT/Codex
Status: design specification
Parent stack:
- Phase 1: `icarus-intelligence-fabric-v1`
- Phase 2: durable Intelligence Delivery Plane
- Phase 3: Live Intelligence Gateway, PR #336

## 1. Purpose

Phase 4A turns the existing ICARUS intelligence stack from a transport/event system into a machine-native collaboration system.

The unit of collaboration is not a chat message. It is a durable semantic work contract whose complete lifecycle is represented by immutable Phase 1 intelligence events.

A work contract can ask a human or agent to perform research, collect evidence, investigate an anomaly, review a model or risk claim, challenge a hypothesis, cross-verify a conclusion, make a bounded decision, perform a delegated subtask, or synthesize prior results.

The system must preserve:

- the request that initiated the work;
- who declared the request and who it targeted;
- the exact causal event chain;
- evidence references;
- partial and final outputs;
- disagreements and challenges;
- delegation ancestry;
- lifecycle state;
- concurrency conflicts;
- deadlines and expiry;
- execution-authority invariants.

The result must remain replayable and auditable from the append-only Intelligence Fabric alone.

## 2. Success criteria

Phase 4A is successful when ICARUS can represent and deterministically project a work thread such as:

1. an agent requests an NQ regime investigation;
2. another agent accepts it;
3. the assignee begins work;
4. partial evidence arrives;
5. the requester challenges one inference;
6. the assignee responds with additional evidence;
7. the assignee delegates a child verification request;
8. the child work completes;
9. the parent synthesizes the child result;
10. the parent completes with a traceable evidence bundle;
11. every event remains immutable and authority-safe;
12. replay produces the same semantic state.

No prose-only conversation is required for correctness.

## 3. Architectural classification

Phase 4A is an architectural subsystem.

It sits above Phase 1 and below future human/agent collaboration UI and authenticated agent identity.

It must not become:

- a second canonical message store;
- a second delivery broker;
- a scheduler replacement;
- a chat-room database;
- an execution command plane;
- an identity/authentication service.

## 4. Selected architecture

Use a semantic protocol layered over existing Phase 1 events.

Protocol identifier:

`icarus-collaboration-v1`

Canonical persistence remains the existing Phase 1 `fabric_events` journal.

Phase 4A introduces a semantic writer/projector module that:

- validates collaboration request material;
- creates collaboration-shaped `IntelligenceEvent` objects;
- publishes them through the existing `IntelligenceFabric.publish()` API;
- reconstructs work state from `IntelligenceFabric.thread()` / `query()`;
- detects semantic forks and stale-head races;
- rejects illegal lifecycle transitions;
- exposes deterministic work snapshots and work history;
- never grants execution or production-decision authority.

No new event database is introduced.

## 5. Rejected approaches

### 5.1 New Phase 1 event taxonomy

Rejected for Phase 4A.

Adding many new Phase 1 event types such as `research_request`, `task_result`, `challenge`, and `delegation` would widen the frozen foundation and create unnecessary compatibility surface.

The existing event taxonomy already has `agent_note`, `human_note`, `research`, `decision_request`, `decision_response`, and `system`.

### 5.2 Separate collaboration/chat store

Rejected.

A separate collaboration database would create split-brain truth between chat/work state and the canonical Intelligence Fabric.

### 5.3 Broker-first orchestration

Rejected.

Phase 2 already owns durable routing/delivery. Phase 3 already owns live network transport. Phase 4A must not recreate either responsibility.

## 6. Scope decomposition

The larger collaboration objective is split into independent phases.

### Phase 4A — Semantic Work Core

This specification.

### Phase 4B — Authenticated command ingress and principal binding

Future work. Binds authenticated transport principals to collaboration actor identities.

### Phase 4C — Incident rooms, escalation routing, capability presence

Future work. Adds collaborative rooms/presence/capability discovery around the semantic work core.

### Phase 4D — Autonomous synthesis/councils

Future work. Coordinates multi-agent work graphs and synthesis policies.

### Phase 4E — Immersive human command UI

Future work. Visual operator environment over the same canonical events.

## 7. Canonical semantic object

The canonical semantic object is a work thread.

A work thread is identified by `work_id` and represented by Phase 1 events whose:

- `channel == "collaboration"`;
- `thread_key == "work:<work_id>"`;
- `correlation_id == <work_id>`;
- payload uses protocol `icarus-collaboration-v1`.

The journal events remain canonical. The projected work snapshot is derived state.

## 8. Work kinds

Phase 4A supports these normalized `work_kind` values:

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

Unknown work kinds fail validation.

Extending the enum requires a protocol-version decision, not an ad-hoc free string.

## 9. Principal model

Phase 4A uses declared principals only.

A principal is:

- `principal_id`: bounded non-empty string;
- `principal_kind`: one of `agent`, `human`, `system`.

Important security boundary:

Phase 4A does not authenticate a principal string.

It only validates semantic consistency among declared principals.

Untrusted external clients must not gain arbitrary Phase 4A publication rights until Phase 4B binds authenticated transport identity to principal identity.

Phase 3 currently does not provide arbitrary inbound intelligence publication, so this boundary is compatible with the existing stack.

## 10. Work target

A request target is one of:

- `principal`
- `group`

Required fields:

- `target_kind`
- `target_id`

Capability-based dynamic targeting is deferred to Phase 4C.

Required capabilities may still be declared in the request for later routing/discovery.

## 11. Work identifier and idempotency

Every root request requires an `idempotency_key` chosen by the requester.

The semantic layer derives:

`work_id = sha256([protocol, requester_principal, idempotency_key])`

The implementation may expose the full digest or a stable prefixed representation such as `work_<hex>`.

The same requester + idempotency key must always address the same work thread.

If the material request is identical, repeated creation is idempotent.

If the same requester + idempotency key is reused with different material, the semantic layer reports a request-material conflict.

Concurrent duplicate roots may both reach the append-only journal in a cross-process race; deterministic projection selects the first valid root by Phase 1 journal sequence and classifies later root attempts as conflicts.

## 12. Request material

A valid root request contains:

- `protocol`
- `work_id`
- `transition = "requested"`
- `requester_principal`
- `requester_kind`
- `target_kind`
- `target_id`
- `work_kind`
- `idempotency_key`
- `objective`
- optional `constraints`
- optional `required_capabilities`
- optional `reviewer_principals`
- optional `deadline`
- `priority`
- optional `result_contract`
- optional `parent_work_id`
- optional `parent_event_id`

Top-level Phase 1 fields carry assets, evidence IDs, causation IDs, timestamps, severity, urgency, and other generic intelligence metadata.

## 13. Objective and constraints

`objective` is a bounded human-readable description of the requested outcome.

Correctness must not depend on natural-language parsing of `objective`.

Machine-relevant constraints belong in a finite JSON `constraints` mapping.

Examples:

- allowed data sources;
- time horizon;
- asset universe;
- required statistical tests;
- prohibited inference classes;
- maximum cost budget metadata;
- required evidence classes.

Phase 4A validates structural finiteness and size, not domain-specific semantics for every possible constraint.

## 14. Result contract

`result_contract` is optional finite JSON describing the expected machine-readable result.

Phase 4A supports a minimal normalized contract shape:

- `result_kind`: one of `json`, `event_refs`, `evidence_bundle`, `decision`, `text_plus_refs`;
- optional `required_fields`: bounded unique strings;
- optional `schema_id`: external schema identifier;
- optional `schema_version`.

Phase 4A validates this structural contract.

Full arbitrary JSON Schema execution is not required and no new schema-validation dependency is introduced.

## 15. Required capabilities

`required_capabilities` is a bounded unique string collection.

It is descriptive in Phase 4A.

Phase 4C may later bind it to capability advertisements and automatic routing.

## 16. Reviewer principals

A request may declare zero or more reviewer principals.

Reviewers may:

- add evidence;
- challenge an applied semantic head;
- escalate a work thread.

They may not accept, reject, start, complete, fail, or cancel work unless another role also grants that action.

## 17. Parent/child work

Delegation uses ordinary child work requests.

A child request sets:

- `parent_work_id`;
- `parent_event_id` equal to the parent work's applied semantic head at delegation time;
- Phase 1 `causation_ids` containing that parent event ID.

The child requester must be the parent assignee for normal delegation.

No separate mutable task tree is stored.

Child discovery is a projection/query operation.

Cancellation of a parent does not automatically cancel children in Phase 4A. Cascading orchestration is deferred.

## 18. Semantic transitions

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

## 19. Lifecycle state

Projected lifecycle states:

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

`challenge`, `challenge_response`, `evidence_added`, and `escalated` are semantic events that advance the work head without necessarily changing lifecycle state.

## 20. State machine

### Root

`requested -> OPEN`

### Acceptance

`OPEN + accepted -> ACCEPTED`

### Rejection

`OPEN + rejected -> REJECTED`

### Start

`ACCEPTED + started -> IN_PROGRESS`

A `started` transition from `PARTIAL` returns lifecycle state to `IN_PROGRESS`.

### Partial result

`ACCEPTED | IN_PROGRESS | PARTIAL + partial_result -> PARTIAL`

### Completion

`ACCEPTED | IN_PROGRESS | PARTIAL + completed -> COMPLETED`

### Failure

`ACCEPTED | IN_PROGRESS | PARTIAL + failed -> FAILED`

### Cancellation

Any non-terminal lifecycle state may become `CANCELLED` when the declared actor is semantically authorized to cancel.

### Expiry

Any non-terminal lifecycle state may become `EXPIRED` only after the request deadline and only through a valid `system` actor transition.

Illegal lifecycle transitions are not applied.

## 21. Semantic head and optimistic concurrency

Every non-root transition requires:

`expected_head_event_id`

It must equal the currently applied semantic head before that transition.

The transition must also include the expected head in top-level Phase 1 `causation_ids`.

This creates an explicit optimistic-concurrency contract without adding a second canonical state table.

## 22. Concurrent writers and semantic forks

Phase 1 is append-only and does not currently expose an atomic compare-and-append API for thread heads.

Therefore two processes can race after reading the same head.

Phase 4A handles this deterministically:

1. both well-formed events may be durably appended;
2. replay is ordered by immutable Phase 1 journal sequence;
3. the first event whose `expected_head_event_id` matches the current applied head is applied;
4. later events based on the stale head are classified `conflicted`;
5. conflicted events remain in immutable history but do not alter lifecycle state, assignee, challenge state, result state, or semantic head;
6. a caller using the Phase 4A API must re-project after publish and report whether its event became applied.

This makes concurrency conflicts auditable rather than destructive.

## 23. Root-race behavior

The first valid `requested` event for a derived `work_id` becomes the root.

A later root event with identical normalized request material is classified `duplicate_root`.

A later root with different material is classified `conflicting_root`.

Neither changes the applied semantic root.

## 24. Actor rules

### Requester

The requester may:

- create the root request;
- add evidence;
- challenge;
- escalate;
- cancel non-terminal work.

### Principal target

For `target_kind=principal`, only the declared target principal may accept or reject.

On acceptance it becomes the assignee.

### Group target

For `target_kind=group`, the first valid actor to accept becomes the semantic assignee.

Phase 4A does not cryptographically prove group membership. Routing/group membership remains a Phase 2 concern; authenticated principal binding is Phase 4B.

After acceptance, assignee-only actions require that exact assignee principal.

### Assignee

The assignee may:

- start;
- add evidence;
- publish partial results;
- answer challenges;
- escalate;
- complete;
- fail;
- create delegated child work.

### Reviewer

A declared reviewer may:

- add evidence;
- challenge;
- escalate.

### System

A `system` actor may mark work expired only after the deadline.

## 25. Challenge model

A `challenge` transition contains:

- `challenge_id`;
- bounded `claim` or question;
- optional evidence references through top-level `evidence_ids`;
- optional finite JSON metadata.

`challenge_id` must be unique within the work thread.

A `challenge_response` contains:

- `challenge_id`;
- response material;
- top-level causation including both current semantic head and the original challenge event ID;
- optional evidence references.

A challenge response closes that challenge in the projection.

## 26. Completion with unresolved challenges

Completion is allowed with unresolved challenges only if the `completed` payload explicitly lists `unresolved_challenge_ids`.

The list must exactly match the projector's currently open challenges.

If open challenges exist and the completion payload omits or misstates them, completion is not applied.

This preserves disagreement rather than silently erasing it.

## 27. Evidence semantics

Evidence identity remains top-level Phase 1 `evidence_ids`.

Phase 4A does not copy entire evidence objects into collaboration payloads by default.

`evidence_added`, `partial_result`, `challenge`, `challenge_response`, and `completed` may reference evidence IDs.

The projected work snapshot includes the cumulative evidence reference set and per-event evidence provenance.

## 28. Causal semantics

Every applied non-root transition must causally depend on the prior semantic head.

Additional causation may reference:

- evidence-producing events;
- parent work heads;
- child completion events;
- challenge events;
- synthesis inputs.

Phase 4A must preserve these top-level Phase 1 causation IDs exactly.

## 29. Result semantics

`partial_result` and `completed` may carry finite JSON `result` material.

A final completion may also reference child work results by event ID rather than embedding them.

Phase 4A verifies the minimal `result_contract` when possible:

- required fields exist for JSON-like results;
- required reference collections are present for reference-based result kinds;
- result kind is compatible with the declared request contract.

Domain correctness is not inferred merely because structural validation passes.

## 30. Decision work

For `work_kind=decision`:

- the root Phase 1 event type is `decision_request`;
- a successfully applied final completion uses Phase 1 event type `decision_response`.

The result remains non-authoritative for production execution.

`production_decision_authorized` remains `false`.

## 31. Non-decision result event mapping

Recommended Phase 1 event-type mapping:

- root request from human: `human_note`;
- root request from agent: `agent_note`;
- system control transition: `system`;
- lifecycle/control transition from human: `human_note`;
- lifecycle/control transition from agent: `agent_note`;
- `partial_result` or `completed` for research/evidence/investigation/review/synthesis kinds: `research`;
- decision root/final result: `decision_request` / `decision_response`.

The semantic transition remains in the collaboration payload and is the authoritative collaboration discriminator.

## 32. Event envelope mapping

Every collaboration event uses:

- `channel = "collaboration"`;
- `thread_key = "work:<work_id>"`;
- `correlation_id = <work_id>`;
- `source = actor principal ID`;
- `source_kind = actor principal kind`;
- `title` generated deterministically from transition/work kind where practical;
- `body` human-readable but never required for state projection;
- `assets` inherited from request/result context;
- `evidence_ids` canonical evidence references;
- `causation_ids` canonical causal references;
- `tags` bounded routing/discovery hints;
- `payload` containing the strict collaboration protocol object.

## 33. Collaboration payload

Every collaboration payload contains at minimum:

```json
{
  "protocol": "icarus-collaboration-v1",
  "work_id": "...",
  "transition": "...",
  "actor_principal": "...",
  "actor_kind": "agent|human|system",
  "expected_head_event_id": "... or null",
  "data": {}
}
```

Root `requested` payload additionally carries normalized request material and its digest.

Later transitions must not redefine stable root fields such as requester, target, work kind, or idempotency key.

## 34. Tags

Recommended tags include one or more of:

- `collaboration:v1`
- `work-kind:<kind>`
- `to:<principal>`
- `group:<group>`
- `requester:<principal>`
- `assignee:<principal>`
- `parent:<work_id>`
- `transition:<transition>`

Tags are routing/discovery hints only.

Current Phase 2 tag filtering matches any tag in a configured tag set, not a conjunction of all supplied tags. Therefore semantic authorization and state correctness must never depend on multi-tag conjunction behavior.

## 35. Phase 2 integration

Phase 2 continues to own delivery.

Typical subscriptions may filter:

- `channel="collaboration"`;
- one or more collaboration tags;
- event types;
- source;
- asset;
- severity.

Delivery ACK/NACK remains independent of semantic work acceptance/rejection.

Critical invariant:

**Phase 2 ACK means the delivery was processed. It does not mean the work was accepted.**

A semantic `accepted` event is required to accept work.

## 36. Phase 3 integration

Phase 3 may stream collaboration events like any other Phase 1 event delivered by Phase 2.

Phase 4A does not add a new transport protocol to Phase 3.

Phase 3 currently does not accept arbitrary inbound event publication; Phase 4A therefore initially serves trusted internal writers and future authenticated ingress.

## 37. Semantic projector

The core projector consumes a single work thread ordered by Phase 1 `sequence`.

For each event it performs:

1. Phase 1 schema/authority sanity checks;
2. collaboration channel/thread/correlation checks;
3. protocol-version check;
4. work-ID consistency check;
5. transition-shape validation;
6. actor-rule validation;
7. expected-head validation;
8. causation validation;
9. lifecycle legality validation;
10. transition-specific validation;
11. deterministic application or conflict classification.

Projection must be pure with respect to the supplied event history.

Replaying the same ordered thread yields the same snapshot.

## 38. Work snapshot

A projected work snapshot contains at least:

- `protocol`
- `work_id`
- `work_kind`
- `requester_principal`
- `requester_kind`
- `target_kind`
- `target_id`
- optional `assignee_principal`
- optional `parent_work_id`
- lifecycle `state`
- `head_event_id`
- `root_event_id`
- `created_at`
- `updated_at`
- optional `deadline`
- `priority`
- `objective`
- normalized constraints
- required capabilities
- reviewer principals
- result contract
- latest partial result metadata
- final result metadata when terminal-completed
- cumulative evidence IDs
- open challenge IDs
- resolved challenge IDs
- `escalated` boolean
- applied event IDs or count
- conflict records
- authority flags hard false.

No lease token, bearer token, or Phase 3 session secret is part of this snapshot.

## 39. Conflict classification

Well-formed but unapplied semantic events receive deterministic diagnostic classifications such as:

- `duplicate_root`
- `conflicting_root`
- `stale_head`
- `illegal_transition`
- `actor_not_permitted`
- `missing_required_cause`
- `challenge_mismatch`
- `result_contract_mismatch`

Conflicts remain immutable history.

They do not advance semantic head.

## 40. Malformed collaboration events

A malformed event is different from a semantic conflict.

Examples:

- wrong collaboration protocol type;
- mismatched thread/work ID;
- authority flag violation;
- non-finite JSON;
- missing required structural fields.

The strict projector must fail closed with a dedicated integrity error rather than silently treating malformed collaboration data as valid state.

A diagnostic-history API may expose raw malformed event IDs for investigation, but ordinary state operations do not continue through an integrity failure.

## 41. Direct Phase 1 publication outside Phase 4A

Phase 1 remains a general event journal and cannot prevent another caller from creating a syntactically valid event with `thread_key=work:<id>`.

Phase 4A therefore treats the work-thread namespace as semantically reserved.

Any unexpected event inside a reserved work thread is either:

- ignored only when it is provably unrelated and outside collaboration channel/protocol; or
- treated as an integrity anomaly when it claims collaboration semantics but violates the protocol.

Implementation tests must pin this behavior precisely.

## 42. Deadline semantics

Root request `deadline` is optional UTC ISO-8601 with timezone.

If present, it must not precede the root event's observed/received boundary.

Crossing the deadline does not mutate history automatically.

Projection may expose:

- `deadline_passed` at a caller-supplied `as_of` time;
- current durable lifecycle state.

A durable `EXPIRED` lifecycle state requires an explicit valid `expired` event from a system actor after the deadline.

## 43. Time semantics

Phase 1 `observed_at` and `received_at` remain canonical event times.

Phase 4A uses no client-supplied clock to decide prior-event ordering.

Journal `sequence` determines replay order.

Deadline checks normalize to UTC.

## 44. Priority and attention

Work `priority` is a bounded integer `0..5`.

It is semantically distinct from Phase 1 attention score.

The event may map work priority into Phase 1 severity where appropriate, but work correctness must not depend on attention ranking.

## 45. Cancellation semantics

Cancellation is a terminal semantic state.

Phase 4A does not delete pending Phase 2 deliveries when a work item is cancelled.

Consumers receiving an older collaboration event must consult the latest semantic work state before performing new work if cancellation sensitivity matters.

Future orchestration may create cancellation notifications/subscriptions, but durable Phase 2 delivery history is not rewritten.

## 46. Failure semantics

`failed` requires bounded finite failure metadata:

- stable failure code;
- bounded summary;
- retryability hint;
- optional evidence IDs through top-level envelope;
- optional diagnostic finite JSON.

Failure does not automatically create retry work.

A new work request with its own idempotency key is required for a semantically new retry attempt unless future orchestration defines a higher-level retry policy.

## 47. Escalation semantics

`escalated` in Phase 4A is an immutable semantic marker.

It records:

- actor;
- reason code;
- bounded summary;
- optional intended escalation target metadata.

It does not create an incident room or presence session.

Those effects belong to Phase 4C.

## 48. Work history API

Expected high-level APIs include:

- `create_request(...)`
- `transition(...)`
- convenience helpers for common transitions where they improve correctness;
- `project(work_id, *, as_of=None)`
- `history(work_id)`
- `children(work_id)`
- `find_work(...)`

Exact signatures belong in the implementation plan.

## 49. Publication result

After publishing a transition through Phase 4A, the API re-projects the work thread and reports:

- Phase 1 `event_id` and sequence;
- whether the semantic event was applied;
- current work head;
- current lifecycle state;
- conflict classification when not applied;
- hard false authority flags.

A successful Phase 1 append is not automatically reported as a successful semantic transition.

## 50. Persistence

Phase 4A adds no new canonical tables.

The Phase 1 journal is sufficient to reconstruct semantic state.

A future performance optimization may add disposable materialized projections, but any such cache must be rebuildable solely from Phase 1 and must never become canonical truth.

No materialized-state table is part of Phase 4A.

## 51. Limits

Phase 4A remains within existing Phase 1 limits.

Additional semantic limits should include:

- bounded principal IDs;
- bounded idempotency keys;
- bounded objective text;
- bounded reviewer/capability collections;
- bounded transition result/failure/challenge metadata;
- maximum projected events per work thread no greater than the Phase 1 query maximum supported by implementation.

The implementation plan must choose exact limits consistent with Phase 1's existing 32 KiB payload and repeated-item constraints.

## 52. Long work threads

Phase 1 currently caps query limits.

Phase 4A must not silently truncate a work thread and project false state.

Implementation must either:

- guarantee a strict maximum semantic event count per work thread within Phase 1's safe query limit; or
- read the complete thread through an explicitly safe pagination/replay mechanism.

The implementation plan must resolve this before product code.

## 53. Authority invariants

Every Phase 4A public result must preserve:

- `execution_authorized = false`
- `production_decision_authorized = false`

No transition changes those values.

A `decision_response` is a semantic collaboration result, not production execution approval.

Phase 4A must never call broker/execution code.

## 54. Security boundaries

Phase 4A does not solve:

- principal authentication;
- cryptographic signatures;
- tenant/RBAC policy;
- remote publication authorization;
- secret distribution;
- transport authentication beyond what Phase 3 already provides.

Those are not accidental omissions. They are explicit Phase 4B+ boundaries.

## 55. Logging

Collaboration logs may include:

- work ID;
- event ID;
- transition;
- lifecycle state;
- declared principal ID;
- conflict code.

Logs should not dump full result/evidence payloads by default.

Existing Phase 3 secret-redaction requirements remain unaffected.

## 56. Error model

Minimum stable Phase 4A error categories:

- invalid request material;
- request material conflict;
- unknown work;
- malformed collaboration event;
- integrity failure;
- illegal transition;
- actor not permitted;
- stale semantic head;
- missing causal dependency;
- challenge mismatch;
- result contract mismatch;
- deadline violation;
- thread too large to project safely.

Publication APIs should distinguish durable append success from semantic application success.

## 57. Testing contract

Implementation is TDD-first.

### Root/idempotency

- deterministic work ID;
- duplicate identical request idempotency;
- conflicting reuse of idempotency key;
- concurrent duplicate roots select one deterministic root.

### Lifecycle

- every legal state transition;
- every illegal state transition;
- terminal states cannot be resurrected;
- partial result lifecycle behavior;
- started-after-partial behavior.

### Actors

- requester permissions;
- principal-target acceptance;
- group-target first assignee;
- assignee-only actions;
- reviewer challenge/evidence limits;
- system-only expiry.

### Optimistic concurrency

- stale head event is preserved but not applied;
- first sequence winner advances head;
- caller receives `applied=false` for losing race;
- conflict does not corrupt subsequent valid transitions.

### Causation

- every applied non-root event includes semantic head cause;
- challenge response includes original challenge cause;
- delegated child links to parent work/event;
- synthesis may reference child completion event.

### Challenges

- unique challenge IDs;
- response closes exact challenge;
- unknown challenge response rejected;
- completion with open challenges requires exact unresolved list.

### Evidence/results

- evidence accumulation;
- result contract required fields;
- result refs preserved;
- no inference of correctness from structural validity.

### Integrity

- wrong work/thread/correlation mismatch fails closed;
- wrong protocol fails closed when event claims collaboration semantics;
- hard authority flags remain false;
- malformed semantic payload never changes projected state;
- direct conflicting journal events cannot bypass projector rules.

### Deadline

- deadline normalization;
- pre-deadline expiry rejected;
- post-deadline system expiry accepted;
- crossing deadline without event only affects `deadline_passed`, not durable state.

### Phase integration

- Phase 1 Fabric tests remain green;
- Phase 2 Delivery tests remain green;
- Phase 3 Gateway tests remain green;
- collaboration events route through Phase 2 without special delivery state;
- delivery ACK does not create semantic acceptance.

### Regression

- full Linux `tests_engine` green;
- Windows regression matrix green.

## 58. Planned implementation boundaries

Expected new production file:

- `icarus_engine/intelligence_collaboration.py`

Expected focused tests may include:

- `tests_engine/test_intelligence_collaboration.py`
- `tests_engine/test_intelligence_collaboration_state.py`
- `tests_engine/test_intelligence_collaboration_integrity.py`

Expected documentation:

- this design spec;
- later implementation plan.

## 59. Explicitly excluded files/systems

Phase 4A should not require edits to:

- `icarus_engine/intelligence_fabric.py` unless the implementation plan proves an unavoidable correctness gap;
- `icarus_engine/intelligence_delivery.py`;
- `icarus_engine/intelligence_gateway.py`;
- `icarus_engine/server.py`;
- UI/dashboard assets;
- Field Agent;
- Brain / brain_sync;
- provider/collector modules;
- scheduler workflows;
- broker/execution modules;
- Atlas `research_allocation/**`.

The preferred implementation has zero changes to Phase 1–3 production files.

## 60. Compatibility

Phase 4A is additive.

Non-collaboration Phase 1 events remain unchanged.

Phase 2 and Phase 3 treat collaboration events as ordinary immutable intelligence events.

No existing subscription must be migrated merely because Phase 4A exists.

## 61. Observability

At minimum, semantic projections should expose diagnostic counts for:

- applied events;
- conflicted events;
- open challenges;
- child work count when requested;
- lifecycle state;
- deadline-passed state;
- integrity status.

Global metrics aggregation is not required in Phase 4A.

## 62. Example work flow

Example semantic sequence:

1. `requested` — requester asks `macro-agent` to investigate NQ rate sensitivity.
2. `accepted` — macro-agent accepts.
3. `started` — macro-agent begins.
4. `evidence_added` — adds rate-event evidence refs.
5. `partial_result` — emits preliminary result.
6. `challenge` — requester challenges causal direction.
7. child `requested` — macro-agent delegates historical analogue verification.
8. child completes.
9. `challenge_response` — macro-agent answers with child result/evidence refs.
10. `completed` — final synthesis references the evidence chain.

Every step is replayable from the journal.

## 63. Beyond-IB property

The objective is not merely faster human communication.

The system should support machine-native workflows where multiple agents can receive explicit semantic work, produce evidence-backed outputs, disagree, delegate, and synthesize while preserving a causal record that can be replayed and audited.

A human can later observe and intervene in the same work graph without becoming the canonical storage model.

## 64. Deferred Phase 4B+

Deferred:

- cryptographically authenticated actor identity;
- inbound publication through Phase 3;
- capability advertisements and dynamic matching;
- presence/typing/online state;
- human/agent rooms;
- incident-room lifecycle;
- automatic escalation routing;
- autonomous multi-agent council policies;
- automatic work decomposition;
- automatic child cancellation;
- UI/mobile command surfaces;
- production execution authority.

## 65. Design invariants summary

1. Phase 1 events remain canonical truth.
2. No second collaboration database is canonical.
3. Work state is deterministic replayable projection.
4. Every applied non-root transition names the expected semantic head.
5. Stale-head races remain immutable history but do not alter projected state.
6. Semantic ACK/acceptance is distinct from Phase 2 delivery ACK.
7. Evidence and causation stay first-class.
8. Delegation is ordinary child work with explicit ancestry.
9. Principal strings are semantic declarations only until Phase 4B authentication.
10. Both authority flags remain hard false.
11. Phase 4A does not touch execution.
12. Phase 4A should be implementable as an additive module plus focused tests.
