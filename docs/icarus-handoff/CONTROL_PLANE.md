# ICARUS Unified Control Plane

## Current automation

Active automation:
- Title: **ICARUS Unified Control Cycle**
- ID: `6ab50595ccb0819184e68bf620480e91`
- Policy: `icarus-control-v1`
- Handoff schema: `icarus-pipeline-v1`
- Schedule: hourly at minute 00, America/Chicago
- `execution_authorized=false`

The unified cycle replaced five independent scheduled stages so same-cycle policy, snapshot, claim, evidence, dependency, conflict, and integrity state remain in one execution context.

## Sequential stages

### S1 — Evidence Convergence
- establish repository truth,
- pin immutable revision(s),
- recover/validate prior state when possible,
- select one evidence-backed priority,
- initialize/refresh claim/evidence/dependency/conflict/attempt ledgers,
- short-circuit when no positive-EV action exists.

### S2 — Subsystem Rotation
Deterministic rotation:
`NEXUS -> AION -> ARGUS -> ATHENA -> DAEDALUS -> ORACLE`

Fixed epoch: 2026-09-24 07:00 America/Chicago.

The active subsystem is computed from scheduled hourly cycles since the epoch modulo six. No external pointer is required.

### S3 — Empirical Research
- preserve honest attempt universe,
- inspect mechanism and who plausibly pays,
- verify minimum observables/data sufficiency,
- test estimator validity,
- inspect signal lineage and redundancy,
- require time-respecting OOS/holdout evidence where available,
- include realistic costs/failure regimes,
- search contrary evidence,
- never treat backtest profitability as proof.

### S4 — Repair / Architecture Forge
- consume only mature same-cycle findings,
- use systematic debugging + TDD for verified defects,
- root cause first,
- regression test first,
- smallest authorized fix,
- if writes are unavailable, produce extraction-ready repair package,
- new behavior stays design/spec until approved.

### S5 — Verification / Release Assurance
- independently reconcile S1–S4,
- verify snapshot/policy/evidence/dependency/conflict/oracle chains,
- inspect actual tests/checks run,
- only this stage may grant VERIFIED_FOR_INTEGRATION,
- technical qualification never grants deployment/trading authority.

## Safeguard families now designed into the control plane

1. Coordinated same-cycle pipeline.
2. Structured handoff schema.
3. Deterministic cycle IDs.
4. Progress fingerprint and anti-stagnation.
5. Factual execution receipts.
6. Circuit breakers / short-circuit behavior.
7. Liveness / completeness / degraded-mode distinction.
8. Overlap protection.
9. Claim authority ledger.
10. Maturity ladder.
11. Canonical handoff integrity / optional SHA-256.
12. Immutable repo snapshot pinning.
13. Adaptive work budget.
14. Claim dependency graph.
15. Conflict arbitration / supersession.
16. Evidence lineage / anti-double-counting.
17. Policy-version pinning.
18. Test-oracle independence.
19. Cross-cycle continuity gate.
20. Single-flight duplicate suppression.
21. Hard hourly cycle-time budget.
22. Rejection/attempt persistence for multiple-testing integrity.
23. Fail-closed authority under missing/unknown provenance.

## Legacy automations disabled

- `6ab487f2edac8191ac50c99b26775ad1` — 1/5 Evidence Convergence
- `6ab47d0f7ab08191a5293ec9181e4fce` — 2/5 Subsystem Rotation
- `6ab45acb71a481919e7cda2fcae073a1` — 3/5 Agent Reach Edge Research
- `6ab47cac6eec8191b4e22fcdf4314cf2` — 4/5 Repair & Architecture Forge
- `6ab45cd29df4819182b4ad09661de84e` — 5/5 Verification & Release
- `6ab487512e9c8191b7bbc2bd42bfd304` — Implementation Extraction Loop
- `6ab47d3efef48191874fc2fdba18ef74` — Release Cohesion Loop
- `6ab47a8451088191970b043ccaa58abb` — HELIOS Audit Loop

Do not re-enable these automatically. The unified cycle is the canonical scheduled control lane.

## Runtime-verification caveat

At handoff creation, the active Unified Control Cycle's latest known run time preceded its latest prompt update by roughly 24 seconds. Under the strict rule `last_run_time > updated_at`, the exact newest prompt revision had not yet been runtime-verified.

Do not claim otherwise until a later execution proves the current contract.
