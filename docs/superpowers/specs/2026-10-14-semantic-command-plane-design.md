# ICARUS Phase 4B–4E — Authenticated command plane design

Date: 2026-10-14
Status: implementation complete locally; automated suite not run
Parent: `icarus-collaboration-v1` and the Phase 1–3 intelligence stack

## Goal

Add authenticated human/agent command access and coordination surfaces over the
Phase 4A semantic work protocol. Phase 1 `fabric_events` remains canonical;
work, room, escalation, and council conclusions are immutable journal events
with deterministic projections. Presence is a short-lived lease and is not
historical truth. This work does not authorize broker actions or production
decisions.

## Phase boundaries

### 4B — authenticated ingress and principal binding

The gateway binds configured credentials to server-side `(principal_id,
principal_kind, groups)` identities. Request bodies never choose or override
the actor. The command API accepts bounded work requests and semantic
transitions, returns a replayed `WorkSnapshot`, and authorizes reads against the
projected requester, assignee, reviewer, group, or direct target identity.
Without an explicit configured principal, command routes stay disabled. A
bounded credential map supports multiple principals in one gateway process;
an external identity provider remains a later adapter, not an invented client
claim.

### 4C — incident rooms, escalation, capability presence

Capabilities are authenticated, expiring presence leases. Capability matching
returns eligible principals for explicit operator/worker selection and never
silently changes an existing work target. Escalation is represented by Phase 1
collaboration events and deterministic incident-room events. A room is a
projection over immutable events, not a second message database. Routing
notifications are ordinary delivery-plane events; delivery ACK does not imply
semantic acceptance.

### 4D — autonomous decomposition and synthesis councils

Decomposition plans are bounded, explicit child `WorkRequest`s created through
Phase 4A. Child work retains parent/head causation. Councils are declared
reviewer sets whose individual findings and disagreements are journal events;
the policy module only reports quorum/coverage and never fabricates consensus.
Synthesis requires referenced child/evidence events and preserves unresolved
challenges. No model-generated plan executes implicitly.

### 4E — human command interface

Serve an authenticated command interface from the gateway. It supports creating
work, viewing authorized threads, responding with semantic transitions,
presence capability registration, and incident-room summaries. Credentials
remain in page memory for the current tab and are never placed in URLs,
persistent browser storage, or returned by the API. The interface is a research
and coordination console, not a trading terminal.

## Invariants

- Identity comes from server-side credential binding, never request JSON.
- Every command uses the public Phase 4A API and Phase 1 journal.
- All JSON and collections are bounded and finite; malformed inputs fail closed.
- Projected access is checked after replay, including each room/incident query.
- Capability presence expires and is advisory until a work request explicitly
  targets the selected principal/group.
- Council outputs preserve dissent and source references.
- `execution_authorized` and `production_decision_authorized` remain false.
- No route calls broker, order, position, or portfolio execution code.

## Delivery order

1. Implement and verify 4B ingress with immutable configured identity.
2. Add 4C presence, routing, room event schema, and projections.
3. Add 4D bounded decomposition and council/synthesis policy.
4. Add 4E browser command console over the same authenticated API.
5. Review integration, document operational configuration, and run project CI.
