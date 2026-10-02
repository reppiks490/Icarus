# ICARUS Integration Workspace

This directory is the stable interchange surface for connecting additional ICARUS agents, satellites, data providers, research labs and assurance workers.

## Files

- `ICARUS_MESH.json` — known topology and authority boundaries.
- `schemas/control-manifest.schema.json` — revision-bound control snapshot schema.
- `schemas/evidence-record.schema.json` — provenance-first evidence schema.
- `schemas/handoff.schema.json` — cross-agent/repository handoff schema.
- `templates/HANDOFF_TEMPLATE.json` — starting handoff document.

## Integration rule

Do not wire external systems straight into trade decisions. Attach them here, validate their evidence and revision identity, then promote only through the control cycle.

## Satellite onboarding

A satellite should provide:

1. repository URL/full name
2. revision SHA
3. owner/agent identity
4. authority requested
5. artifacts and hashes
6. evidence/claim IDs
7. compatibility constraints
8. tests/replay evidence
9. limitations
10. handoff expiry/staleness rule

## Current topology status

The mesh now distinguishes **active research-only federations** from unvalidated
candidate satellites.

- `reppiks490/Icarus-engine` is an active `RESEARCH` satellite through the
  bilateral MCP/Adaptive Brain federation contracts under
  `automation_intelligence/mcp_interface/`. ICARUS verifies the producer and
  consumer contracts plus event Git blobs before ingest. Remote automation
  receipts remain observability/research evidence only.
- `reppiks490/icarus-csv-evidence-lab` is an active `OBSERVE` satellite
  through `automation_intelligence/advanced_csv/icarus_consumer_contract.json`.
  `RUN_PERSISTED` is durability only; substantive evidence authority remains
  `evidence_state.EVIDENCE_STATUS`. Raw owner market data is not imported by
  the federation.

All other listed satellites remain candidates until they receive an explicit
validated contract. No active satellite has cross-repository execution
authority.

## Future reducer

A later implementation can add a deterministic reducer that validates these manifests and writes a compact accepted-state index. That reducer should be the only automated path from handoff artifacts into canonical control state.
