# MCP → ICARUS Interface Surface Contract

Status: mandatory integration contract.

Any material repair, audit, hardening, provenance correction, data-quality change, subsystem evolution, or research/evidence capability added through MCP must have a corresponding visible record inside the ICARUS trading interface.

The interface record must show:

- subsystem and change type;
- concise user-facing summary;
- source repository, branch, and exact commit;
- verification state;
- what changed in the interface or engine understanding;
- whether the change is merged, branch-only, blocked, or failed;
- execution/broker authority boundary.

Repository work alone is not sufficient. Documentation alone is not sufficient. A change is considered fully surfaced only when the running ICARUS interface can render it.

The canonical data contract is `icarus_engine/system_evolution.json`, validated by `icarus_engine/evolution.py`.

The intended UI surface is a read-only **System** tab labeled **System evolution & audit**. It must never arm a broker, alter positions, change strategy inputs, or imply that a branch-only change is deployed.

Required HTTP/UI wiring when the dashboard/server files are edited:

1. `GET /api/evolution` returns `icarus_engine.evolution.report()`.
2. The dashboard exposes a **System** tab.
3. The tab renders the ledger with provenance, verification, status, and execution authority.
4. Dashboard JavaScript and server tests cover the route and tab.
5. CI must fail if the panel is removed while the interface contract remains enabled.
