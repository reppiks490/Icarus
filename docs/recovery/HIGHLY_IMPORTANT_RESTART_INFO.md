# HIGHLY IMPORTANT — Icarus Prime restart requirements

Use only the [current Prime as-is restart](PRIME_AS_IS_RESTART.md). It includes the paper-only Git Bash procedure, Main asset set, backup, NQ capture, defaults migration, launch, and local HTTP checks. Superseded per-panel notes are preserved in the [restart archive](archive/restarts/2026-10-25/pre-final/INDEX.md). Release source `2fd305598cdbaf1937c3c4214a6f5a72ef13e15a` is integrated by merged PR #462 at `8c1dbf0d989894683d9daaefe6f1a4b6bcf4cc25`. Exact-head hosted checks passed for PR head `9a44dc1c6d20088bac1df013e6ec09e80446d30e`; the merge-triggered `main` checks must finish green before installation. Local client/UI tests (42), disconnect regressions (19), the control-retry browser regression, and the dashboard/performance/runtime/Connections browser suite passed; the optional Node-based performance subtest skipped because that Node package is unavailable in this local environment. The runtime retries only the selected-workspace busy-before-execution response. Older run IDs and source hashes below this current note are historical evidence; they do not certify this release.

| Assets | Strategy/chart baseline | Special settings |
| --- | --- | --- |
| Every Main/selected-CC asset except ETH | Actual current Main NQ inputs and chart/session settings | Preserve instrument-specific contract economics; SOL follows NQ |
| ETH / COINBASE:ETHUSD only | Same strategy settings as current Main NQ | 30-minute chart, session filter off, quantity input 25 |

The migration captures live Main NQ when available or validates saved Main NQ plus its preset when stopped. It never silently substitutes built-in stock settings. Saved selections, journals, and CC on/off state are preserved. The 35-symbol list and commands are in the current restart guide.

The restart remains paper-only. `execution_authorized=false`; no broker adaptation or live order path is started. Green automated checks do not certify the owner's PC has restarted. The local verification waits up to five minutes for `warm:true` and the expected active asset set; HTTP 200 alone is not warm readiness. Then verify public status and every dashboard route.

The selected-workspace Intuition Ω bridge is included in merged `main`: the Learning page reports read-only source/ledger state and imports only after an owner click, with workspace/revision checks. The Learning page no longer polls every five seconds. Wait for the merge-triggered `main` checks before installation.

The candidate also connects a bounded, read-only discovery-registry summary to the shared Financial & data page and includes an optional, manually invoked GRU research challenger. The normal paper restart does not refresh/probe catalog services, install PyTorch, or start model training; both features retain false production/execution authority.

For the distinction between a visible panel, a selected-runtime read adapter, and an operational write/automation path, use the [adapter status matrix](ICARUS_ADAPTER_STATUS.md).
