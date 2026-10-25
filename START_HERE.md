# Current ICARUS restart

Use the single [Prime as-is restart guide](docs/recovery/PRIME_AS_IS_RESTART.md) and its [highly important defaults](docs/recovery/HIGHLY_IMPORTANT_RESTART_INFO.md). Paper runtime source `2fd305598cdbaf1937c3c4214a6f5a72ef13e15a` is integrated by merged PR #462 at `8c1dbf0d989894683d9daaefe6f1a4b6bcf4cc25`; its exact-head checks passed. Wait for the merge-triggered `main` checks to finish green before installing. The procedure backs up private state, captures actual Main NQ settings, applies and verifies the all-assets template, then starts the local paper engine.

Earlier per-panel restart instructions are preserved in [the restart archive](docs/recovery/archive/restarts/2026-10-25/pre-final/INDEX.md); use the current guide by itself. Automated checks do not prove the owner's PC restarted. The owner must run the commands locally and verify warm runtime health and each dashboard. `execution_authorized=false`.
