# MCP → ICARUS Interface Surface Contract

Status: mandatory.

Any material repair, audit, hardening, provenance correction, data-quality change, subsystem evolution, or research/evidence capability added through MCP must have a corresponding visible record inside the ICARUS trading interface.

## Required visible record

Every important record must show:

- subsystem and change type;
- concise user-facing summary;
- source repository, branch, and exact commit;
- verification state;
- interface effect;
- whether the work is merged, branch-only, blocked, failed, or otherwise not deployed;
- execution/broker authority boundary.

Repository work alone is not sufficient. Documentation alone is not sufficient. An important MCP change is fully surfaced only when the running ICARUS interface can render its record.

## Current implementation

- Canonical ledger: `icarus_engine/system_evolution.json`
- Validator/report: `icarus_engine/evolution.py`
- Server exposure: `ResearchWorkspace.status()["system_evolution"]`, returned through the existing authenticated `GET /api/research` route
- UI integration: `icarus_engine/research-ui.js` augments the existing **System** tab with a **System evolution & audit** panel
- Existing repository/CI health stays in the same System tab; the evolution ledger is additive, not a replacement

The panel is read-only. It must never arm a broker, alter positions, mutate strategy inputs, or imply that branch-only work is deployed.

## Enforcement

Tests must verify the ledger contract and the UI wiring. Every ledger entry must keep `execution_authorized=false`. If the contract is enabled, removing the ICARUS surface is a regression.
