# HIGHLY IMPORTANT — Icarus Prime restart requirements

Use only the [current Prime as-is restart](PRIME_AS_IS_RESTART.md). It includes the paper-only Git Bash procedure, Main asset set, backup, NQ capture, defaults migration, launch, and local HTTP checks. Superseded per-panel notes are preserved in the [restart archive](archive/restarts/2026-10-25/pre-final/INDEX.md). PR #471's latest exact-head Windows, browser, Linux, and contract gates passed. Integrated source candidate `36b3c1f6f931d74b480661ea931af19245058d5d` adds current Icarus main to that tested source; its integrated local suite and exact PR #462 hosted checks are pending. Wait for PR #462's exact-head checks before installation.

| Assets | Strategy/chart baseline | Special settings |
| --- | --- | --- |
| Every Main/selected-CC asset except ETH | Actual current Main NQ inputs and chart/session settings | Preserve instrument-specific contract economics; SOL follows NQ |
| ETH / COINBASE:ETHUSD | Same strategy settings as current Main NQ | 30-minute chart, session filter off, quantity input 25 |

The migration captures live Main NQ when available or validates saved Main NQ plus its preset when stopped. It never silently substitutes built-in stock settings. Saved selections, journals, and CC on/off state are preserved. The 35-symbol list and commands are in the current restart guide.

The restart remains paper-only. `execution_authorized=false`; no broker adaptation or live order path is started. Green automated checks do not certify the owner's PC has restarted. Run the procedure locally and verify health, public status, all dashboard routes, asset count, and warm state.

For the distinction between a visible panel, a selected-runtime read adapter, and an operational write/automation path, use the [adapter status matrix](ICARUS_ADAPTER_STATUS.md).
