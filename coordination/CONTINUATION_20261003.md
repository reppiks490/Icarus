# ICARUS continuation ownership — 2026-10-03

Owner: this Codex takeover session. Branch: `codex/continuation-config-jobs-20261003`.
Baseline: `0fd773d159bf39dd2756b7589b46cd20c1b7be05`.

## Narrow owned lane
Independent verification of the newly merged configuration background jobs and repair of reproduced request identity/HTTP lifecycle defects. Intended write scope: `icarus_engine/server.py` configuration-job section only, new `tests_engine/test_config_jobs.py`, this handoff. Existing synchronous replay/preflight/rollback semantics remain canonical. No second replay engine or federation path.

## Concurrent work preserved
Do not take over open PRs #302 (ASCENDANCY governor), #301 (historical packet projection), #297 (Psi history), #296 (Evolution reconciliation), #295 (private satellite CI hold), #198 (mobile), or satellite DAEDALUS/AEGIS registry/caller-chain work. Their activity is observed; current model ownership is not independently known. Do not treat this claim as exclusive ownership of the entire UI/runtime or repo.

## Takeover queue
1. Reproduce configuration-job request delivery and conflicting edits.
2. Validate dashboard/runtime controls and both repository suites.
3. Record concrete failures, exact revisions, evidence and next steps.
4. Recheck current main and competing changes before publishing.

Cross-repository contracts remain research-only. `execution_authorized=false`; `production_decision_authorized=false`. No schedule changes or deployment are implied.

## Verified repair checkpoint

Configuration jobs now distinguish identical retries from different edits. Conflicting overlapping edits return HTTP 409 so the dashboard retains them; exact retries reuse the same replay. The worker uses the server's actual bound port. Replay, exposure preflight and rollback remain delegated to the original authenticated synchronous endpoints.

Tests: four RED failures demonstrated lost request identity / port-zero delivery before the fix; seven job regressions GREEN; configuration + execution controls + dashboard checks: 127 passed. Local full suite: 1849 passed, one PowerShell-only launcher test skipped. The launcher regression now executes the real PowerShell script with a controlled Python boundary on Windows, instead of requiring obsolete NQ-only source text. The sync-all partial-failure regression now includes the existing evidence-lab synchronizer rather than performing uncontrolled network I/O.

Fresh main `2e23227f49f299c5616d8c6fe771668876f5b159` adds only an OMEGA evidence receipt and was incorporated without overwriting concurrent code. Hosted Linux/Windows qualification remains pending.

## Recovered continuation queue

- UI/runtime: this request-delivery repair; actual user-machine responsiveness and restart checks remain unobserved.
- Federation: canonical acceptance is implemented and the last scheduled gate succeeded. Persisted receipt reports 5 lanes, 0 substantive lanes, 4 durability-only lanes. Transport success does not establish native worker inference. Projection proof remains owned by open #301.
- ASCENDANCY: bounded autonomous governor is open #302; its latest observed CI failed. Preserve its owner and qualification gates.
- Evolution: open #296 reconciles timestamp monotonicity/migration; #295 records the private satellite runner-allocation hold. Do not recreate those patches.
- Psi: 900-bar follow-up remains open #297. Do not repeat its implementation.
- DAEDALUS/AEGIS: latest retrieved registry immutability and holdout crash/recovery work is an active separate lane; exact live owner is unknown. Preserve the lane.
- Mobile: open draft #198 contains the tested native foundation; physical-device/EAS/account steps remain external. Browser/Tailscale access is the user's existing path.
- Satellite suite at `d422f1fd41d76d4ff47a3f2bc190cda7de24b39c`: 1003 collected; process identity tests `test_restart_abandons_confirmed_dead_owner_without_replaying_interval` and `test_process_identity_is_stable_for_current_process` fail in this container. Local PID/proc identity is inconsistent; no production process-death workaround was introduced.

Test oracle: real HTTP request effects, independent literal input values, injected replay delay/failure. No market-performance claim or holdout use. Next stage: independent verification/release assurance. Rollback: revert the request-delivery delta, retaining original synchronous endpoints.

## Newly requested work

Recurring Windows Git console popups: trace background provenance/training/worker subprocess launch policy, implement Windows no-console creation without changing visible manual launchers, and verify separately. This task is a separate change package.
