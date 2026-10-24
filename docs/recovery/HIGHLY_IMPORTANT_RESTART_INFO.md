# HIGHLY IMPORTANT — current ICARUS restart settings

**Owner requirement, 24 October 2026. Use the [current full restart guide](PRIME_AS_IS_RESTART.md); earlier restart notes are historical.**

Verified runtime source: `3122d349524fbce803970dc34ab6fc74dad87467`; tree: `9ad37de97e160aead6602351b54c43608086a006`; branch: `prime/as-is-restart-20261022`; [PR #471](https://github.com/reppiks490/Icarus/pull/471). Main contains the instructions; the runtime remains on the pinned branch.

| Assets | Strategy/chart defaults | Timeframe | RTH gate | Quantity input |
| --- | --- | --- | --- | --- |
| Every asset except ETH and SOL | Actual current Main NQ defaults | Same as NQ | Same as NQ | Same as NQ |
| ETH / COINBASE:ETHUSD | Same as NQ except these three fields | 30 minutes | Disabled (`use_session=false`; crypto calendar is 24/7) | 25 |
| SOL / COINBASE:SOLUSD | Same as NQ except these three fields | 30 minutes | Disabled (`use_session=false`; crypto calendar is 24/7) | 25 |

This applies to Main and all selected CC assets, including newly added assets. It intentionally resets saved per-asset strategy/chart overrides to the owner's NQ template. Saved asset selections, journals and CC on/off settings stay intact. Later explicit per-asset edits retain their normal precedence.

The preparation command captures authenticated Main NQ settings while running. If the engine is already stopped, it verifies actual saved NQ and preset records. It refuses missing records, authentication errors, timeouts, changed source files or malformed settings rather than substituting stock Inputs. The following full restart backs up stopped state, applies the prepared template, verifies it, and starts all 35 canonical Main symbols.

The saved strategy defaults match NQ. Native contract economics and the existing per-instrument runtime point/tick scaling remain asset-specific. Quantity is a configured strategy input; it is not a guarantee that every signal produces a fill of that size.

The build includes NEXUS source-health observations and AION durable monitoring receipts. It also repairs the reproduced request-deadline causes: synchronous access-audit writes and runner/journal recomputation on status requests. Authentication remains authoritative and immediately revocable. Status readers consume published snapshots; unavailable accounting remains explicitly unknown while assets stay observable. Request deadlines and freshness limits are not extended.

Run the complete preparation and restart commands in the [current guide](PRIME_AS_IS_RESTART.md). Keep the launcher window open. Confirm the actual PC restart and saved Inputs before reconnecting the phone. Cloud checks do not certify sustained PC uptime, provider freshness or live trading; execution authority remains false.
