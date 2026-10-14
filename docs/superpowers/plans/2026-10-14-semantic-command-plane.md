# ICARUS Phase 4B–4E implementation record

Date: 2026-10-14
Owner request: “Begin do all of it.”
Base: main after Phase 4A, `8e5e1990549923099f07767a63de4bcf35c77ec3`

## Implemented scope

- 4B adds optional server-bound command identity to the gateway. The principal
  is taken from gateway configuration, never the request. The API rejects
  extra actor fields and supports work creation, authorized work reads, and
  Phase 4A transitions. Without configured identity, command routes are absent.
- 4C adds expiring, in-memory capability presence, explicit capability-matched
  escalation routing, and journal-backed incident rooms. Presence is advisory
  and expires; rooms and updates are Phase 1 events, not a second chat store.
- 4D adds bounded child-work decomposition, reviewer council evidence events,
  deterministic council projection that retains dissent, and result synthesis
  linked to child head events. Completion requires completed child work and
  carries unresolved challenge IDs forward.
- 4E adds a same-origin command console. The bearer remains in page memory and
  is not stored in browser persistence, URL parameters, or API responses.

## Operational configuration

The standalone gateway reads `ICARUS_INTELLIGENCE_GATEWAY_TOKEN` as before.
To enable one command identity, also set both `ICARUS_COMMAND_PRINCIPAL_ID`
and `ICARUS_COMMAND_PRINCIPAL_KIND` (`human`, `agent`, or `system`). Optional
`ICARUS_COMMAND_GROUPS` is a comma-separated server-side group allowlist for
group-targeted work. For multiple principals in one process, set
`ICARUS_COMMAND_CREDENTIALS_JSON` to a JSON object mapping each additional
bearer string to `{ "principal_id": "...", "principal_kind": "agent",
"groups": [] }`. The map is bounded to 32 credentials; credentials are never
returned or logged by command responses. A gateway with no configured command
identity gets only the Phase 3 transport routes.

Open `/command` on the gateway origin, enter the bearer, and use the console.
The UI does not persist that credential. API body limits continue to use the
gateway JSON limit. Capability TTL is limited to 10–300 seconds by the UI and
10–3600 seconds by the registry; the deployed default maximum is 300.

## Boundaries

- Presence is intentionally volatile, process-local state. Multiple configured
  principals in the same gateway can match capabilities; it is not a claim of
  durable history or cross-process consensus.
- Escalation selects an explicitly supplied principal from the current
  capability-eligible set. It records the parent transition and then creates a
  causally linked child request. It does not silently reroute existing work.
- Acceptance automatically executes a bounded `constraints.decomposition_plan`
  if the request includes one. The plan may also be run explicitly through the
  decomposition endpoint. Plans are declared structured tasks; the system does
  not invent model-generated subtasks. Each child is still a normal Phase 4A
  work request.
- Council tally has no calibrated probabilities or automatic trading action.
  Review claims, votes, source event IDs, and disagreement remain visible.
- Incident membership is fixed at room creation in this initial version.
- The console is a coordination UI, not a portfolio/order interface.
- Both authority flags remain false; no broker code is called.

## Validation status

Implementation and static integration review are complete on the local feature
branch. Python compilation/import checks, JavaScript syntax validation, and
`git diff --check` pass. Automated tests and CI have not been run in this task.
Cross-principal deployment validation remains necessary before production
exposure.
