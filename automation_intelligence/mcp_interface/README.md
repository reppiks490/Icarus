# ICARUS MCP Interface Event Feed

This directory is the durable, repository-native bridge from MCP/agent work into the running ICARUS trader interface.

Cloud agents cannot call the operator's localhost trader directly. Important repairs, audits, subsystem evolutions, provenance changes, integrations, and findings are therefore published as immutable JSON files under:

`automation_intelligence/mcp_interface/events/`

The engine's background `EvolutionRemoteSync` verifies the Git blob, validates the event schema, mirrors the event into System Intelligence and the Adaptive Brain, and displays it in the **MCP Evolution** trader panel.

Machine-readable contract: `automation_intelligence/mcp_interface/contract.json`. Both the local Engine Control projector and remote Evolution sync must remain compatible with this contract.

## Required event schema

```json
{
  "schema_version": "icarus-interface-event-v1",
  "event_id": "unique-stable-id",
  "category": "REPAIR|AUDIT|EVOLUTION|INTEGRATION|FINDING",
  "severity": "info|success|warn|error",
  "status": "observed|active|verified|qualified|rejected|blocked|degraded|retired|unverified",
  "subsystems": ["argus", "athena", "parallax"],
  "recorded_at": "2026-10-01T04:00:00Z",
  "title": "Short operator-facing title",
  "summary": "Truthful concise description of what changed, what remains unverified, and any blocker.",
  "source_repository": "owner/repository",
  "source_ref": "branch-or-tag",
  "source_commit": "40-character-git-commit-sha",
  "evidence": ["tests: 12 passed", "ci: pending"],
  "execution_authorized": false,
  "production_decision_authorized": false
}
```

Allowed subsystem identifiers are:

`aegis, aion, argus, ascension, athena, daedalus, infrastructure, janus, nexus, oracle, parallax, prometheus, provenance, supermesh-x, ml, data, dreamstate, psi`.

## Mandatory policy

Any materially important MCP repair, audit, evolution, integration, provenance finding, or ML/subsystem state change must publish one event file here if it should be visible to the operator.

The feed is observability only. An event cannot authorize a live trade, strategy promotion, production decision, asset change, timeframe change, chart change, broker action, or order.

Do not rewrite prior event files. Publish a new event for later verification, supersession, regression, or failure.
