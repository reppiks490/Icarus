# ICARUS Control Plane and Assurance

## 1. Canonical control cycle

Suggested stages:

- **S1 Acquire** — raw observations, source metadata, hashes
- **S2 Normalize** — canonical symbols, clocks, sessions, contracts, units
- **S3 Research** — derived features, experiments, ablations, hypotheses
- **S4 Implement** — code/artifact construction behind guarded interfaces
- **S5 Assure** — independent validation, replay, adversarial and release checks

S4 must never self-certify S5.

Every stage handoff should be revision-bound and digest-linked.

## 2. Authority monotonicity

If evidence quality worsens, execution/research authority cannot increase.

Examples that must preserve or reduce authority:
- missing source
- stale source
- unresolved provider conflict
- calibration failure
- unknown contract roll
- timestamp ambiguity
- schema violation
- replay mismatch
- revision mismatch
- insufficient out-of-sample evidence

## 3. State architecture

Recommended conceptual layout:

```
control/
  manifest.json
  evidence/
  claims/
  runs/
  handoffs/
  snapshots/
  research/
  audit/
```

This package does not create those production directories yet. The schemas under `integration/schemas/` define the boundary for later implementation.

`state.json` should eventually act as a small index containing current control revision, latest accepted snapshot, and pointers/hashes—not an arbitrary bucket of opaque mathematical constants.

## 4. Experiment manifest minimum

Every experiment should capture:

- experiment ID
- source revision
- data snapshot ID
- asset universe
- clock/session definition
- contract/roll rule
- parameter set
- feature set
- ablation mask
- cost/slippage assumptions
- train/validation/test split, when applicable
- seed, when stochastic
- generated artifacts
- metrics
- failure status
- reproducibility digest

## 5. Independent test-oracle record

Important subsystems should document:

- `TEST_ORACLE_ORIGIN`
- `TEST_ORACLE_DERIVED_FROM`
- `ORACLE_INDEPENDENCE_STATUS`
- `GOLDEN_VECTOR_PROVENANCE`
- `NEGATIVE_CONTROLS`
- `MUTATION_OR_FAULT_INJECTION_PLAN`

## 6. Mandatory assurance families

### Behavioral parity
All new research controls disabled -> same baseline decision semantics.

### Temporal integrity
No source or transform may use information unavailable at decision time.

### Deterministic replay
Same canonical inputs + same revision -> same canonical state and decision trace.

### Mutation testing
Deliberately inject plausible defects:
- invert a comparison
- shift one bar
- allow one-bar lookahead
- modify session boundary
- reverse a weight
- drop a source
- stale a timestamp
- corrupt a contract identifier

The suite should detect them.

### Adversarial provider tests
Inject:
- source outage
- disagreement
- stale values
- duplicate data
- malformed timestamps
- partial history

### Cross-revision protection
A claim approved on SHA A cannot silently authorize SHA B.

## 7. Release gate

A release candidate is not production-authorized unless:

1. schemas validate
2. source lineage is complete
3. baseline parity holds
4. temporal-integrity checks pass
5. replay is deterministic
6. independent oracle checks pass
7. mutation tests demonstrate detection power
8. unresolved provider conflicts are below configured authority threshold
9. revision digests match
10. explicit owner/release authorization exists
