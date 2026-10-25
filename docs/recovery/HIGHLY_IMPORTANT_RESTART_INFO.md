# HIGHLY IMPORTANT — current Icarus Prime restart requirements

Use only the [current Prime as-is restart](PRIME_AS_IS_RESTART.md). It is pinned to release commit `a21507b8b9bb46ec418a0a9b89fae448fb3eae96` and contains the backup, Main NQ capture, defaults apply/verify, launch, and HTTP/warm-health checks. The release integrates:

- All-asset defaults from PR #479: every registered Main symbol and saved selected CC asset inherits the actual Main NQ inputs except ETH / COINBASE:ETHUSD and SOL / COINBASE:SOLUSD, each set to 30 minutes, session filter off, quantity 25.
- Main dashboard scroll/layout fix from PR #476.
- Native mobile observer and isolated gateway; explicit rate-limited backtest requests are allowed, while trade-state mutations are blocked from PR #481. Physical phone pairing, Expo project linking, and signing are still pending owner-PC/account work.

The last successful warm owner-PC Main observation had six active assets: `NQ,ES,YM,GC,SI,BTC`. A later `warm:false` probe with no assets was not a healthy zero-asset runtime. The launch keeps the saved six-asset set to avoid increasing runtime load; the defaults migration still covers all 35 registered Main symbols and saved selected CC assets. Preserve the existing private state and back it up before changing files. Do not start a second engine: stop the current launcher with Ctrl+C once, then follow the guide.

Automated checks passed on PR #481's merged revision (`40224524803`, `40224524804`) and PR #482's exact head (`40224637484`, `40224637590`). The #482 main-push bilateral gate (`40227416952`) passed and stored the accepted revision pair in the [canonical receipt](../../automation_intelligence/federation/icarus_engine_acceptance.json). PR #476's dashboard scroll browser regression passed on its exact commit. These hosted results do not establish the owner's PC is running, provider data is fresh, or a phone is paired.

ETH and SOL default exceptions are only chart/session/quantity overrides; native contract economics remain instrument-specific. Saved asset selections, journals, and CC on/off toggles remain preserved.

The restart is paper-only. `execution_authorized=false`; broker adaptation, live order flow, and live trading remain excluded. Require `/healthz` `warm:true` with the expected active assets before calling the local runtime ready; HTTP 200 alone is insufficient.