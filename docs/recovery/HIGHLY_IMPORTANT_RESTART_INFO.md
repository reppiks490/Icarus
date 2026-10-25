# HIGHLY IMPORTANT — Icarus Prime restart requirements

Use only the [current Prime as-is restart](PRIME_AS_IS_RESTART.md). It includes the paper-only Git Bash procedure, Main asset set, backup, NQ capture, defaults migration, launch, and local HTTP checks. Superseded per-panel notes are preserved in the [restart archive](archive/restarts/2026-10-25/pre-final/INDEX.md). The integrated source candidate is `5160a55368fc5c7e5a61dcf53c85193c028042ab` for PR #462. Its full local suite exited 0 with 4,331 cases collected. Hosted checks for this new source commit are pending; do not install until its exact-head checks pass. The previous `350f93e` candidate passed both Windows engine runs and the other listed hosted contracts, but those results do not cover this added source.

| Assets | Strategy/chart baseline | Special settings |
| --- | --- | --- |
| Every Main/selected-CC asset except ETH | Actual current Main NQ inputs and chart/session settings | Preserve instrument-specific contract economics; SOL follows NQ |
| ETH / COINBASE:ETHUSD only | Same strategy settings as current Main NQ | 30-minute chart, session filter off, quantity input 25 |

The migration captures live Main NQ when available or validates saved Main NQ plus its preset when stopped. It never silently substitutes built-in stock settings. Saved selections, journals, and CC on/off state are preserved. The 35-symbol list and commands are in the current restart guide.

The restart remains paper-only. `execution_authorized=false`; no broker adaptation or live order path is started. Green automated checks do not certify the owner's PC has restarted. Run the procedure locally and verify health, public status, all dashboard routes, asset count, and warm state.

For the distinction between a visible panel, a selected-runtime read adapter, and an operational write/automation path, use the [adapter status matrix](ICARUS_ADAPTER_STATUS.md).
