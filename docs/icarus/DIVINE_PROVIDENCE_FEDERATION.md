# divine-providence ↔ ICARUS research federation

`reppiks490/divine-providence` is an active research satellite of the canonical
`reppiks490/Icarus` repository.

## Ingress model

The federation is intentionally receipt-based rather than a direct production
control channel.

`divine-providence` research work publishes immutable
`icarus-interface-event-v1` receipts into:

`automation_intelligence/mcp_interface/events`

inside the canonical ICARUS repository.

The local `EvolutionRemoteSync` validates those mirrored receipts, preserves
their exact source repository/commit provenance, and projects accepted events
into MCP Evolution and Adaptive Brain observability.

## Authority ceiling

The satellite authority ceiling is `RESEARCH`.

Cross-repository execution authority is always false:

`execution_authorized=false`

`production_decision_authorized=false`

A verified research receipt may become visible in ICARUS. It does not thereby
become a trade signal, broker authorization, production promotion, or permission
to mutate separately owned engine/runtime scopes.

## Current ARGUS continuation state

The current ARGUS continuation stack remains source-CI gated. ICARUS may surface
that stack as `blocked` while the private source repository has no real runner
execution. A no-runner GitHub Actions failure is not treated as proof that the
ARGUS code passed or failed.

Only source commits whose exact required Linux/Windows and full-system gates
actually execute and pass may later be surfaced as verified milestones.

## Ownership boundary

This federation does not grant divine-providence ownership of ICARUS broker,
Databento, asset, timeframe, chart/subminute, strategy-execution, or order-routing
code. It is an evidence and research-observability connection only.
