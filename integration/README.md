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

The mesh lists discovered adjacent repositories as `candidate`. Candidate status means: visible and potentially useful, but not trusted or production-authorized.

## Future reducer

A later implementation can add a deterministic reducer that validates these manifests and writes a compact accepted-state index. That reducer should be the only automated path from handoff artifacts into canonical control state.
