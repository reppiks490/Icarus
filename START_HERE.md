# Current ICARUS restart

Use the single [Prime as-is restart guide](docs/recovery/PRIME_AS_IS_RESTART.md) and its [highly important defaults](docs/recovery/HIGHLY_IMPORTANT_RESTART_INFO.md). The current paper runtime source candidate is `2fd305598cdbaf1937c3c4214a6f5a72ef13e15a` on PR #462. Install it only when every required check is green for the current PR head. The procedure backs up private state, captures actual Main NQ settings, applies and verifies the all-assets template, then starts the local paper engine.

Earlier per-panel restart instructions are preserved in [the restart archive](docs/recovery/archive/restarts/2026-10-25/pre-final/INDEX.md); use the current guide by itself. Automated checks do not prove the owner's PC restarted. The owner must run the commands locally and verify warm runtime health and each dashboard. `execution_authorized=false`.
