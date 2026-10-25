# Current ICARUS restart

Use the single [Prime as-is restart guide](docs/recovery/PRIME_AS_IS_RESTART.md) and its [highly important defaults](docs/recovery/HIGHLY_IMPORTANT_RESTART_INFO.md). The pinned paper runtime source is `712057cbb7b42d94bd0238068019b0f55aa8ef5a` on PR #462. Install it only when every required check is green for the current PR head. The procedure backs up private state, captures actual Main NQ settings, applies and verifies the all-assets template, then starts the local paper engine.

Earlier per-panel restart instructions are preserved in [the restart archive](docs/recovery/archive/restarts/2026-10-25/pre-final/INDEX.md); use the current guide by itself. Automated checks do not prove the owner's PC restarted. The owner must run the commands locally and verify warm runtime health and each dashboard. `execution_authorized=false`.
