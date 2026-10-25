# HIGHLY IMPORTANT — Icarus Prime restart requirements

Use only the [current Prime as-is restart](PRIME_AS_IS_RESTART.md). It includes the paper-only Git Bash procedure, Main asset set, backup, NQ capture, defaults migration, launch, and local HTTP checks. Superseded per-panel notes are preserved in the [restart archive](archive/restarts/2026-10-25/pre-final/INDEX.md). Candidate `b0d67889143221087e5f7045cae9109ede0af031` passed all hosted exact-head checks and the full local engine suite (4,269 passed, 5 skipped, 111 subtests). The prior head's Windows shutdown test exposed a real start/close race; the regression test failed before the fix and passes afterward. A docs-only follow-up is being published to PR #471, so wait for its exact-head checks before installation.

| Assets | Strategy/chart baseline | Special settings |
| --- | --- | --- |
| Every Main/selected-CC asset except ETH | Actual current Main NQ inputs and chart/session settings | Preserve instrument-specific contract economics; SOL follows NQ |
| ETH / COINBASE:ETHUSD | Same strategy settings as current Main NQ | 30-minute chart, session filter off, quantity input 25 |

The migration captures live Main NQ when available or validates saved Main NQ plus its preset when stopped. It never silently substitutes built-in stock settings. Saved selections, journals, and CC on/off state are preserved. The 35-symbol list and commands are in the current restart guide.

The restart remains paper-only. `execution_authorized=false`; no broker adaptation or live order path is started. Green automated checks do not certify the owner's PC has restarted. Run the procedure locally and verify health, public status, all dashboard routes, asset count, and warm state.

For the distinction between a visible panel, a selected-runtime read adapter, and an operational write/automation path, use the [adapter status matrix](ICARUS_ADAPTER_STATUS.md).
