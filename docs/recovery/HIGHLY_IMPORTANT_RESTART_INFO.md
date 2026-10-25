# HIGHLY IMPORTANT — Icarus Prime restart requirements

Use only the [current Prime as-is restart](PRIME_AS_IS_RESTART.md). It includes the paper-only Git Bash procedure, Main asset set, backup, NQ capture, defaults migration, launch, and local HTTP checks. Superseded per-panel notes are preserved in the [restart archive](archive/restarts/2026-10-25/pre-final/INDEX.md). PR #462 release tree `f4a4a2800069bcefc3661b38d0b4d134ae775326` includes runtime source `1283551fbec56113da656d998ff4c04866c1624e` plus the current-main catalog receipt. At source `1283551`, both full Linux/Windows CI runs (`40183899072`, `40183897492`) passed, including Windows restart-persistence and private-intake checks. The current PR head includes documentation updates; check that head's required checks before installation. The prior Windows failure was the provider JSON line-ending mismatch; `.gitattributes` fixes it and both exact-source Windows portfolio contracts passed.

| Assets | Strategy/chart baseline | Special settings |
| --- | --- | --- |
| Every Main/selected-CC asset except ETH | Actual current Main NQ inputs and chart/session settings | Preserve instrument-specific contract economics; SOL follows NQ |
| ETH / COINBASE:ETHUSD only | Same strategy settings as current Main NQ | 30-minute chart, session filter off, quantity input 25 |

The migration captures live Main NQ when available or validates saved Main NQ plus its preset when stopped. It never silently substitutes built-in stock settings. Saved selections, journals, and CC on/off state are preserved. The 35-symbol list and commands are in the current restart guide.

The restart remains paper-only. `execution_authorized=false`; no broker adaptation or live order path is started. Green automated checks do not certify the owner's PC has restarted. Run the procedure locally and verify health, public status, all dashboard routes, asset count, and warm state.

The selected-workspace Intuition Ω bridge is included in the current #462 candidate: the Learning page reports read-only source/ledger state and imports only after an owner click, with workspace/revision checks. The Learning page no longer polls every five seconds. Require current exact-head checks before installing this candidate.

For the distinction between a visible panel, a selected-runtime read adapter, and an operational write/automation path, use the [adapter status matrix](ICARUS_ADAPTER_STATUS.md).
