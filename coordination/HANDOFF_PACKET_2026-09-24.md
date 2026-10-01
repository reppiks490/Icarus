# ICARUS Baton-Pass Packet — 2026-09-24

## Repository target

- Repository: `reppiks490/Icarus`
- Baseline branch: `main`
- Baseline commit at branch creation: `007e70189945b8e112904cf92b2b1a12e43792d6`
- Integration branch: `integration/icarus-capability-fabric-20260924`

## Scope

This packet packages the architecture, findings, safety invariants, research-validation requirements, provider boundaries, and agent connection contract produced during the ICARUS architecture/extraction work.

It intentionally does **not** modify:

- strategy semantics,
- Pine logic,
- Python engine logic,
- broker/bridge logic,
- plant runtime,
- quantity/sizing,
- session rules,
- order routing,
- `state.json`,
- `instruction.txt`.

All current changes under this branch are additive coordination files.

## Canonical entrypoint

Start with `coordination/README.md`, then follow its read order.

## Included artifacts

- `coordination/README.md`
- `coordination/CURRENT_FINDINGS.md`
- `coordination/ARCHITECTURE_CAPABILITY_FABRIC.md`
- `coordination/CONTROL_PLANE_CONTRACT.md`
- `coordination/RESEARCH_VALIDATION_PLAN.md`
- `coordination/AGENT_CONNECTION_GUIDE.md`
- `coordination/schemas/handoff.schema.json`
- `coordination/schemas/state-index.schema.json`
- `coordination/manifests/provider-registry.yaml`

## Canonical versions

- `PIPELINE_POLICY_VERSION=icarus-control-v1`
- `HANDOFF_SCHEMA_VERSION=icarus-pipeline-v1`

## Current package status

- `IMPLEMENTATION_STATUS=SPEC_ONLY`
- `execution_authorized=false`
- no production behavior change claimed
- no live deployment claimed
- no merge to `main` claimed
- no Stage 5 verification claimed

## Facts verified before packaging

Direct reads of `README.md`, `pyproject.toml`, `state.json`, and `instruction.txt` established the factual basis summarized in `CURRENT_FINDINGS.md`.

GitHub code search is not indexed for this repository, so absence claims must be based on concrete file inspection rather than negative search results.

## Connection contract for other agents

A newly connected agent should:

1. read the coordination entrypoint and contracts,
2. pin the repository revision it is inspecting,
3. inspect only its bounded subsystem first,
4. identify inputs, outputs, state, temporal assumptions, ownership, tests, and failure modes,
5. preserve evidence/claim lineage,
6. emit a structured handoff,
7. avoid production behavior changes until the relevant approval/evidence gates are satisfied.

## Immediate recommended next assignments

These can run independently so long as they preserve the same revision and policy:

### Repository cartography agent

Map the canonical package/module/test tree and subsystem ownership. Do not modify behavior.

### Evidence/provenance agent

Design the concrete on-disk claim/evidence manifest representation compatible with the supplied schemas.

### Ablation/diagnostics agent

Inspect the actual Pulse implementation and determine what instrumentation is required for independent vote/family masking with production defaults unchanged.

### Test-oracle agent

Inventory current tests and identify where mutation/fault-injection or independent reference oracles are missing.

### Provider-adapter agent

Select one provider at a time and define its normalized observation schema, freshness semantics, and failure modes. Do not connect provider payloads directly to strategy/execution.

### Verification agent

Review this package against the baseline revision and confirm the branch contains additive coordination material only.

## Merge condition

Do not merge merely because these documents exist. Merge only after an independent reviewer confirms:

- the docs accurately distinguish observations from inferences,
- contracts do not contradict canonical repository behavior,
- machine schemas parse,
- provider registry grants no direct execution authority,
- no production file was modified,
- no unsupported claim of verification is present.

## Baton-pass instruction

Future agents should cite the exact repository revision they consumed and write their outputs as new evidence, research, implementation, or verification artifacts rather than overwriting prior conclusions in place.
