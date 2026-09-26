# Integration Protocol for Incoming Agents and Tools

## Mission

Incoming agents should extend ICARUS without corrupting evidence, weakening existing guarantees, or creating parallel incompatible frameworks.

## Startup sequence

Every agent should:

1. Read this directory.
2. Read the current repo HEAD and compare it with the baseline in `integration_manifest.json`.
3. Run the relevant existing tests before changing code.
4. Identify the smallest bounded workstream it owns.
5. Declare required data/capabilities and blocked dependencies.
6. Create tests/falsification criteria before implementation for safety-critical or research-validity changes.
7. Make isolated changes.
8. Re-run targeted tests plus affected integration suites.
9. Record findings and evidence.
10. Stop before live authorization unless explicitly scoped and independently reviewed.

## Shared vocabulary

Use these states consistently:

- `VERIFIED`
- `SUPPORTED`
- `BLOCKED_EXTERNAL`
- `UNKNOWN`
- `PROXY_ONLY`
- `DEGRADED`
- `VERIFIED_FOR_INTEGRATION`

Do not turn `UNKNOWN` into a boolean false/true silently.

## Ownership boundaries

### Research agents
May produce hypotheses, statistical tests, candidate features, ablations, and evidence ledgers.
Must not authorize live trading.

### Data agents
May add providers, normalizers, provenance, point-in-time semantics, and reconciliation.
Must not fabricate missing fields.

### Execution agents
May implement adapters/state machines/reconciliation.
Must not infer broker truth from strategy intent.

### Risk agents
May add exposure, drawdown, kill-switch, and event-risk constraints.
Risk failure should default closed.

### UI/design agents
May improve observability and operator interfaces.
UI state must reflect engine truth, not become a second truth source.

### Infrastructure agents
May improve CI, packaging, deployment, telemetry, and recovery.
They must preserve deterministic build/test evidence.

## Required change packet

Every non-trivial change should leave:

```text
Goal
Assumptions
Files changed
Tests added/changed
Evidence collected
Failure modes
Backward-compatibility notes
Blocked external dependencies
Rollback method
Promotion status
```

## Conflict resolution

If two agents produce competing implementations:

1. compare declared mechanism/requirements
2. compare test coverage
3. compare failure behavior
4. compare deterministic replay
5. compare empirical incremental value
6. prefer the simpler implementation unless added complexity proves independent value

Do not merge both merely to preserve effort already spent.

## Live-safety rule

Nothing in this handoff grants live-trading authority. Existing activation and risk boundaries remain authoritative.
