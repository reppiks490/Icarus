# ICARUS dashboard adapter status

This inventory separates a visible dashboard tab from its Python adapter. A tab is only a view; a connected adapter routes data/actions to a particular runtime or explicitly to shared evidence. This matrix describes source at restart candidate `41f5c8a8b0d9a62a1e15b69bca91f16a2885d34c`.

| Surface | Adapter state | Scope and actual behavior |
| --- | --- | --- |
| Access | Connected, shared | One authenticated security registry for Main and CC1–CC4; it is not a per-workspace data reader. Owner authentication controls changes. |
| Possibility / Chronofold / Commissioning / Engine Control | Connected, selected-runtime | Reads use that CC's portfolio. Paper controls require owner permission and current config revision. Evidence ingestion is selected-asset scoped. |
| Adaptive Brain | Connected, selected-runtime reader | Reads selected workspace market/research state. Its mutation/learning event plane remains outside this reader. |
| Research | Connected, selected-runtime reader | Reads private workspace research services and records; no collection or worker start from a read. |
| PARALLAX / DREAMSTATE / PANTHEON / SIBYL / APEX | Connected, selected-runtime readers | Read native private state. APEX composition is bound to the selected asset/context. No provider sessions start from these reads. |
| ASCENDANCY | Connected, selected-runtime reader | Reads selected private archive, capability, work-order, validation and intelligence state. Plan/execute callbacks are disabled. |
| Learning | Connected, selected-runtime reader | Reads existing private state. Shared-history admission and automatic scan are explicitly unavailable. |
| Tactical Autopilot | Connected, selected-runtime status reader | Reads selected paper state; autonomous mutation/execution remains disabled. |
| Go-live integrity | Connected, selected-runtime reader | Reports selected cached-tape/paper integrity; it does not arm a broker or refresh providers. |
| NEXUS / AION Connections | Connected, local native observer | Reads bounded published runtime metadata and local durable receipts. It reports its local observation state; provider SLO/freshness qualification is not asserted. |
| Market Data | Connected, cached selected-runner reader | Uses existing selected-runner caches only. A request does not acquire a feed or start a subscription. |
| Sources / Evolution / Integrity / System / Agent / Evidence | Connected, shared evidence views | These are shared repository/federation evidence, not proof of a selected workspace's operation. Mutating controls are disabled in CC context. |

The earlier [panel restart checkpoint](ICARUS_PANEL_RESTARTS.md) correctly described the first four stateful CC adapters at its checkpoint, but its statement that the other eleven had no adapters is superseded by the readers above. Those eleven have selected-runtime **read adapters**, not full write/automation workflows.

## What remains intentionally unavailable

In a CC context, the read-only set (`brain`, `research`, `parallax`, `pantheon`, `sibyl`, `apex`, `ascendancy`, `learning`, `autopilot`, and `golive`) disables collection, training, activation, shared-history admission, and autonomous controls. The selector set and server API reject unsupported routes/actions instead of falling back to Main. This is a deliberate safety boundary for a paper workspace; it is not evidence that those subsystem readers are disconnected.

The dashboard can render a panel while its native data is empty or stale. NEXUS/AION `UNAVAILABLE`, `STALE`, `DEGRADED`, or unknown provider-SLO fields must stay visible as such. A 200 panel route proves the adapter returned a response, not that a provider is fresh or entitled. Broker adaptation, broker qualification, order execution, and live trading remain outside this restart.

Focused evidence in the candidate includes `tests_engine/test_workspace_research_panels.py`, `test_workspace_intelligence_panels.py`, `test_workspace_golive.py`, `test_workspace_access.py`, `test_subsystem_connections.py`, `test_subsystem_connections_api.py`, and `test_subsystem_connections_browser.py`. The hosted exact-head results must also pass before installing the restart source. Owner-PC observation is a separate operator verification in [the restart guide](PRIME_AS_IS_RESTART.md).
