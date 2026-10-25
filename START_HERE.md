# Current ICARUS restart

Follow [the current Prime as-is restart](docs/recovery/PRIME_AS_IS_RESTART.md) and its [highly important defaults](docs/recovery/HIGHLY_IMPORTANT_RESTART_INFO.md). Use the exact PR #474/PR #471 release commit only after its Linux, Windows, and browser checks pass. The procedure backs up private state, captures actual current Main NQ settings, applies and verifies the all-assets template, then starts the local paper engine.

Earlier restart commands and results remain in Git history; do not combine them with the current procedure. Automated checks are not an owner-PC restart receipt. The owner must run the commands locally and verify runtime health and each dashboard. `execution_authorized=false`.
