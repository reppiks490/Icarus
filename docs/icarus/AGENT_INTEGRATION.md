# ICARUS Agent Integration Contract

## Objective

Allow multiple agents, satellite repositories, research labs and specialist providers to contribute without creating an uncontrolled shared brain.

## Core rule

**Agents exchange evidence and artifacts through signed/revision-bound handoffs. They do not write directly into each other's authority state.**

## Candidate satellites currently known

- `reppiks490/Icarus-engine`
- `reppiks490/icarus-owner-actions`
- `reppiks490/icarus-causal-router`
- `reppiks490/icarus-csv-evidence-lab`

Their existence is known; their full current internal state was not audited in this pass.

## Required handshake

Every incoming contribution should identify:

- producer
- producer repository
- producer revision/SHA
- target repository
- target revision expectation
- handoff ID
- artifact list
- evidence references
- claims
- assumptions
- known limitations
- test results
- authority requested
- authority granted (initially none)
- expiry/staleness policy

Machine-readable structure: `integration/schemas/handoff.schema.json`.

## Authority classes

- `OBSERVE` — may supply raw observations
- `RESEARCH` — may create experiments/derived features
- `PROPOSE` — may propose code/config changes
- `IMPLEMENT` — may write isolated implementation artifacts
- `ASSURE` — may independently validate
- `RELEASE` — explicit owner-controlled production promotion

No handoff should infer a higher authority class from a lower one.

## Cross-agent connection sequence

1. Producer emits handoff manifest.
2. Consumer validates schema.
3. Consumer verifies producer revision.
4. Artifacts are hashed.
5. Evidence lineage is checked.
6. Claims are imported as provisional.
7. Consumer runs its own validation.
8. Conflicts are stored, not overwritten.
9. Authority is explicitly assigned.
10. Promotion/release occurs only after S5.

## Collision policy

When two agents disagree:

- preserve both claims
- preserve both source chains
- record conflict type
- compare timestamps/revisions
- run independent adjudication
- never resolve by silent last-writer-wins

## Write policy for canonical state

Satellite agents should not write arbitrary values directly into canonical `state.json`.

Preferred path:
- write evidence/experiment artifacts
- produce handoff manifest
- submit to canonical control plane
- allow validated reducer/indexer to update canonical pointers

## Minimal integration adapter responsibilities

Every adapter should:
- translate source schema -> canonical schema
- preserve raw source reference
- preserve source timestamp and availability timestamp
- expose health/staleness
- expose deterministic version
- fail closed when required identity/clock fields are unknown

## Security boundary

Market-data credentials and order credentials are different authority classes. Access to a data source does not imply order permission.

## Handoff acceptance checklist

- [ ] schema valid
- [ ] source revision known
- [ ] target revision compatible
- [ ] artifact hashes verified
- [ ] no secret material embedded
- [ ] temporal metadata present
- [ ] tests attached where applicable
- [ ] limitations explicit
- [ ] requested authority explicit
- [ ] consumer S5 validation completed
