# ICARUS Agent Connection Guide

## Purpose

Allow additional agents to connect safely without requiring access to prior chat history and without creating competing versions of strategy truth.

## Mandatory onboarding

Before acting on ICARUS, an agent should read:

1. `coordination/README.md`
2. `coordination/CURRENT_FINDINGS.md`
3. `coordination/CONTROL_PLANE_CONTRACT.md`
4. `coordination/ARCHITECTURE_CAPABILITY_FABRIC.md`
5. `coordination/RESEARCH_VALIDATION_PLAN.md`
6. machine schemas/manifests under `coordination/schemas` and `coordination/manifests`

Then inspect the canonical repository files relevant to its assigned subsystem.

## Agent classes

### Evidence acquisition agents

Responsibilities:

- retrieve external facts,
- preserve source identity and timestamps,
- avoid converting summaries into independent evidence,
- emit normalized evidence candidates.

Not allowed:

- direct strategy changes,
- direct execution commands,
- promotion of their own claims to integration readiness.

### Research agents

Responsibilities:

- empirical analysis,
- ablation,
- stress,
- redundancy,
- estimator validity,
- temporal leakage detection,
- reproducibility artifacts.

Not allowed:

- use holdout to tune,
- silently alter production defaults,
- treat synthetic tests as empirical observations.

### Architecture / implementation agents

Responsibilities:

- consume qualified upstream evidence,
- preserve revision/policy lineage,
- produce smallest safe repair or approved implementation,
- add independent tests,
- record rollback and residual risk.

Not allowed:

- implement new behavior without approval,
- self-certify S5 status,
- alter acceptance criteria to force GREEN.

### Verification / release-assurance agents

Responsibilities:

- independently inspect change package,
- reproduce tests where possible,
- inspect mutation/fault-injection coverage,
- check temporal and revision integrity,
- decide whether `VERIFIED_FOR_INTEGRATION` is supported.

### Provider adapter agents

Responsibilities:

- normalize provider-specific payloads,
- preserve source metadata,
- enforce time/freshness semantics,
- expose capability and failure modes.

Not allowed:

- provider payload → direct trade instruction.

### Visualization / design agents

Responsibilities:

- make architecture, evidence state, diagnostics, and experiment results understandable.

Not allowed:

- visuals that silently change source-of-truth state.

## Shared handoff discipline

Every handoff should identify:

- sender stage/agent,
- receiver stage/agent,
- cycle ID,
- execution instance ID,
- repository revision,
- config digest,
- policy version,
- policy epoch,
- evidence IDs,
- claim IDs,
- dependency/conflict state,
- status gates,
- requested next action.

## Conflict behavior

If two agents disagree:

1. preserve both claims,
2. link the conflict,
3. compare source independence and temporal validity,
4. do not merge disagreement into artificial confidence,
5. route unresolved material conflicts to a lower-authority state.

## Repository-write discipline

- Prefer additive files and isolated branches for coordination/design work.
- Do not edit strategy/execution code merely to "make room" for agents.
- Separate unrelated defects into separate changes.
- Inspect CI/test expectations before behavioral modification.
- Do not merge/deploy/trade/publish without separate authorization.

## Provider routing

### Financial / market evidence

Potential sources include Massive, Twelve Data, FMP, Bigdata.com, Zacks, StackerScan, Gold Bureau, and Bybit.

Use multiple providers only when independence or compatibility actually matters. More providers do not automatically equal more truth.

### Scientific / research evidence

Scite is appropriate for scientific-literature verification and citation context.

### Web / public information

Agent Reach or DataBlue can retrieve public evidence where repository or primary provider data does not answer the question.

### Blockchain

Blockscout is appropriate for supported EVM on-chain state.

### Visual / product communication

Figma, Visualize, and Runway can support diagrams, interfaces, presentations, or media, but should remain outside decision authority.

## First task for a newly connected agent

A safe first assignment is:

> Inspect one bounded subsystem, report its ownership, inputs, outputs, temporal assumptions, state, tests, failure modes, and any mismatch with the coordination contracts. Do not modify behavior.

This produces useful integration knowledge without creating accidental forks.

## Prepared integration seams

New agents should attach through one of these seams:

- evidence adapter,
- research experiment,
- validation/falsification worker,
- architecture/spec worker,
- implementation worker,
- verification worker,
- observability/replay worker,
- visualization worker.

Avoid introducing a second hidden strategy engine.
