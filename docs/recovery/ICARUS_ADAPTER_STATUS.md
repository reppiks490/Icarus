# ICARUS dashboard adapter status

This inventory separates a visible dashboard tab from its Python adapter. A tab is only a view; a connected adapter routes data/actions to a particular runtime or explicitly to shared evidence. This matrix describes integrated restart candidate `36b3c1f6f931d74b480661ea931af19245058d5d`; its exact integrated PR #462 hosted checks are pending.

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

The earlier [panel restart checkpoint](archive/restarts/2026-10-25/pre-final/ICARUS_PANEL_RESTARTS.md) correctly described the first four stateful CC adapters at its checkpoint, but its statement that the other eleven had no adapters is superseded by the readers above. Those eleven have selected-runtime **read adapters**, not full write/automation workflows.

## What remains intentionally unavailable

In a CC context, the read-only set (`brain`, `research`, `parallax`, `pantheon`, `sibyl`, `apex`, `ascendancy`, `learning`, `autopilot`, and `golive`) disables collection, training, activation, shared-history admission, and autonomous controls. The selector set and server API reject unsupported routes/actions instead of falling back to Main. This is a deliberate safety boundary for a paper workspace; it is not evidence that those subsystem readers are disconnected.

The dashboard can render a panel while its native data is empty or stale. NEXUS/AION `UNAVAILABLE`, `STALE`, `DEGRADED`, or unknown provider-SLO fields must stay visible as such. A 200 panel route proves the adapter returned a response, not that a provider is fresh or entitled. Broker adaptation, broker qualification, order execution, and live trading remain outside this restart.

Focused evidence in the candidate includes `tests_engine/test_workspace_research_panels.py`, `test_workspace_intelligence_panels.py`, `test_workspace_golive.py`, `test_workspace_access.py`, `test_subsystem_connections.py`, `test_subsystem_connections_api.py`, and `test_subsystem_connections_browser.py`. The hosted exact-head results must also pass before installing the restart source. Owner-PC observation is a separate operator verification in [the restart guide](PRIME_AS_IS_RESTART.md).

## Offline provider archive consumption

This is separate from live feed connectivity. The stale [Icarus-engine PR #216](https://github.com/reppiks490/Icarus-engine/pull/216) was stacked on a closed base and is closed as superseded with its branch retained. Its five unique files were reconstructed directly on current Engine main in [Icarus-engine PR #249](https://github.com/reppiks490/Icarus-engine/pull/249), then merged at `2f9a10c516d7294d875a9e808bd669e208ed0e0c`. Local validation passed 107 focused archive tests and the full Engine suite (1,455 tests and 17 subtests). Exact-head CI passed on Python 3.11/3.12/3.13 and all core/CLI/MCP contracts. Exact-main offline workflow run [40171645677](https://github.com/reppiks490/Icarus-engine/actions/runs/40171645677) passed all eight profiles and their metadata receipt and payload-cleanup checks.

The workflow uses immutable retained archives and emits metadata-only receipts. It blocks provider network requests, exports no raw values, and grants no execution authority. It does not establish current provider freshness or live-feed connectivity. The offline archive adapter is qualified for those eight retained archives only.
