# ICARUS Multi-Agent Onboarding Map

This file is the connection contract for additional agents/models.

## Read order

1. `docs/icarus-handoff/README.md`
2. `ARCHITECTURE.md`
3. `CONTROL_PLANE.md`
4. `FINDINGS_AND_DEFECTS.md`
5. `XGB_SLOT1_IMPLEMENTATION.md`
6. `AUTOMATION_STATUS.json`
7. `MANIFEST.json`
8. Then inspect canonical repository code at the pinned/current revision.

Repository evidence overrides this handoff when they conflict.

## Lane A — Engineering

Primary objective:
- implement verified/canonical repairs and approved XGB work.

First work package:
1. reproduce trainer event leakage,
2. RED test,
3. trainer-only causal/as-of repair,
4. explicit execution lock on every trainer exit,
5. implement XGB Slot 1,
6. holdout-consumption ledger,
7. artifact provenance,
8. baseline promotion gate,
9. hardened audit validator,
10. targeted + full tests.

Rules:
- isolated branch/worktree,
- TDD for defects,
- no Pulse rewrite,
- no new feature universe,
- no execution authorization,
- do not weaken tests/acceptance to create green results,
- report pre-existing unrelated failures separately.

## Lane B — Empirical research

Primary objective:
- falsify claims and characterize incremental information.

Required:
- honest attempt ledger,
- time-respecting validation,
- realistic costs,
- parameter-neighborhood sensitivity,
- subperiod/regime stability,
- transfer tests where appropriate,
- redundancy/ablation,
- estimator validity,
- contrary evidence,
- multiple-testing status.

Do not implement features directly.

## Lane C — Verification

Primary objective:
- independently attack the engineering result.

Verify:
- temporal integrity,
- holdout isolation/reuse rules,
- artifact identity,
- baseline comparison,
- malformed/stale/wrong-symbol artifacts,
- explicit execution lock,
- independent test oracle,
- fault/mutation detection where useful,
- full regression suite.

Only this lane may recommend VERIFIED_FOR_INTEGRATION, and that recommendation still does not authorize merge/deploy/trading.

## Lane D — Observability / UX

Primary objective:
- expose system truth without changing research behavior.

Allowed surfaces:
- model lineage,
- source health/freshness,
- claim maturity,
- conflict/dependency graph,
- holdout state,
- calibration state,
- verification status,
- repo/config identity.

Figma/visual/media tooling belongs here when useful.

## Lane E — Control-cycle research

The active Unified Control Cycle should:
- continue evidence convergence,
- rotate subsystems deterministically,
- research only when it can change a decision,
- produce repair/spec packages when writes are unavailable,
- verify authority chains,
- stop on no-change rather than manufacture work.

Do not create another competing hourly control loop unless an explicit isolated purpose is justified.

## Merge/deploy/trade boundary

This handoff grants none of:
- merge permission,
- deployment permission,
- production publication,
- broker execution,
- trading authority.

Keep `execution_authorized=false`.
