# HIGHLY IMPORTANT — Icarus Prime restart requirements

Use only the [current Prime as-is restart](PRIME_AS_IS_RESTART.md). It includes the paper-only Git Bash procedure, Main asset set, backup, NQ capture, defaults migration, launch, and local HTTP checks. Superseded per-panel notes are preserved in the [restart archive](archive/restarts/2026-10-25/pre-final/INDEX.md). Current release code source candidate is `2fd305598cdbaf1937c3c4214a6f5a72ef13e15a`. Local client/UI tests (42), disconnect regressions (19), the control-retry browser regression, and the full dashboard/performance/runtime/Connections browser suite passed; the optional Node-based performance subtest skipped because that Node package is unavailable in this local environment. The candidate retries only the selected-workspace busy-before-execution response. Exact-head hosted checks for the updated #462 must pass before installation. Older run IDs and source hashes below this current note are historical evidence; they do not certify this candidate.

| Assets | Strategy/chart baseline | Special settings |
| --- | --- | --- |
| Every Main/selected-CC asset except ETH | Actual current Main NQ inputs and chart/session settings | Preserve instrument-specific contract economics; SOL follows NQ |
| ETH / COINBASE:ETHUSD only | Same strategy settings as current Main NQ | 30-minute chart, session filter off, quantity input 25 |

The migration captures live Main NQ when available or validates saved Main NQ plus its preset when stopped. It never silently substitutes built-in stock settings. Saved selections, journals, and CC on/off state are preserved. The 35-symbol list and commands are in the current restart guide.

The restart remains paper-only. `execution_authorized=false`; no broker adaptation or live order path is started. Green automated checks do not certify the owner's PC has restarted. The local verification waits up to five minutes for `warm:true` and the expected active asset set; HTTP 200 alone is not warm readiness. Then verify public status and every dashboard route.

The selected-workspace Intuition Ω bridge is included in the current #462 candidate: the Learning page reports read-only source/ledger state and imports only after an owner click, with workspace/revision checks. The Learning page no longer polls every five seconds. Require current exact-head checks before installing this candidate.

The candidate also connects a bounded, read-only discovery-registry summary to the shared Financial & data page and includes an optional, manually invoked GRU research challenger. The normal paper restart does not refresh/probe catalog services, install PyTorch, or start model training; both features retain false production/execution authority.

For the distinction between a visible panel, a selected-runtime read adapter, and an operational write/automation path, use the [adapter status matrix](ICARUS_ADAPTER_STATUS.md).
