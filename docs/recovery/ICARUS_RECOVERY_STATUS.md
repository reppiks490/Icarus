# Icarus recovery status

**Current release — 2026-10-25.** Icarus paper source is pinned at `a21507b8b9bb46ec418a0a9b89fae448fb3eae96`. It contains PR #479's restart-default migration, PR #476's dashboard scroll/layout correction, and PR #481's mobile observer and gateway with explicitly rate-limited backtest requests and no trade-state mutations. PR #481's merge-triggered Linux/Windows/mobile tests and deep-learning contract passed (runs [40224524803](https://github.com/reppiks490/Icarus/actions/runs/40224524803), [40224524804](https://github.com/reppiks490/Icarus/actions/runs/40224524804)). PR #482's exact-head Linux/Windows/mobile tests and bilateral gate passed ([40224637484](https://github.com/reppiks490/Icarus/actions/runs/40224637484), [40224637590](https://github.com/reppiks490/Icarus/actions/runs/40224637590)); it merged at `fb639c45b1c1afb3b1eb6dd0979784b7e4f4f6c3`. The post-merge gate [40227416952](https://github.com/reppiks490/Icarus/actions/runs/40227416952) passed; its checkpoint receipt recorded Icarus `fb639c45...` with Engine `f49d93d9...`, a fresh packet, zero substantive peer lanes, and `execution_authorized=false`. Engine main can advance independently. Read the [canonical acceptance JSON](../../automation_intelligence/federation/icarus_engine_acceptance.json) and compare its peer SHA with current Engine `main` before treating the pair as current. This observe-only federation receipt is not provider qualification or freshness.

## Restart and defaults

The single current operator procedure is the [Prime as-is restart](PRIME_AS_IS_RESTART.md), with release-critical defaults in [HIGHLY IMPORTANT restart information](HIGHLY_IMPORTANT_RESTART_INFO.md). It backs up private state, captures actual Main NQ settings, applies and verifies defaults, starts the paper runtime with the six assets from the last successful warm Main check (the later `warm:false`/empty-assets probe is treated as a failed readiness check), waits for `/healthz` to report `warm:true` with that exact set, and checks Main, public status, CC1–CC4, and Connections. HTTP 200 alone is not readiness.

The defaults migration covers all 35 registered Main symbols and saved selected CC assets. Every asset inherits actual current Main NQ chart/session/strategy settings except ETH / COINBASE:ETHUSD and SOL / COINBASE:SOLUSD, each set to 30-minute, session filter off, quantity 25. Instrument-specific contract economics and saved selections remain intact.

## Runtime performance and errors

PR #476 caches dashboard topology and scroll geometry; its required Chromium regression verifies scroll handling performs no geometry reads during scroll. Workspace status polling is scoped to the selected workspace. If an observation request exceeds its deadline, the UI clears that expired snapshot; a later successful poll can restore it. The current server catches broken-pipe, reset, and aborted-client errors at the response write boundary, and normalizes aborted request-line reads as client disconnects. A browser cancel/close therefore closes that request instead of escaping as the repeated Windows 10053 server traceback. Genuine application/provider failures still need diagnosis; no test or cloud check can promise zero future errors or establish sustained uptime on the owner's PC. Verify warm health and rendered dashboards locally after restart.

## Adapter and mobile state

The [adapter matrix](ICARUS_ADAPTER_STATUS.md) records which surfaces have shared or selected-runtime readers and their authority boundaries. Native mobile code and the dedicated observation gateway are integrated; explicit rate-limited backtest requests are supported, but trade-state mutations are blocked. Physical phone pairing remains pending: it needs the owner's PC and phone, Expo project linking, a reachable HTTPS/private-network hostname, and account/signing setup for distributable builds. The phone never receives the engine admin token; mobile has no trade-state mutation path.

## Remaining gated work

- Owner-side restart, `warm:true`, sustained observation, and rendered dashboard verification have not been observed from this cloud session.
- Provider authentication, entitlement, freshness, and data history remain separate from code integration. Broker adaptation, live order flow, and live trading are excluded.
- Icarus-engine FR-1 research PRs #137, #142, and #209 remain gated on preregistration and recoverable versioned evidence; no real evaluation or ledger write is authorized by this restart.
- Engine PR #141 is an offline advisory research package with passing software review, but it has no runtime adapter and no validated empirical decision benefit. It remains disconnected from the trading/dashboard runtime.

The previous long recovery audit has been preserved at [the archived recovery status](archive/restarts/2026-10-25/pre-final/ICARUS_RECOVERY_STATUS.md). Historical counts and old source hashes there are not current release gates.

**Authority:** `execution_authorized=false`.