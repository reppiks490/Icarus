# Masterbuild Roadmap

## P0 — Restore clean qualification

1. Correct CI `icarus_plant --root ... setup` invocation.
2. Confirm Linux and Windows workflows.
3. Record a green baseline before architectural code changes.

**Exit:** current suite passes and no behavior change is introduced.

## P1 — Capability and provenance substrate

1. Provider capability registry.
2. Entitlement/auth/quota/freshness state model.
3. Typed data-quality and fallback policy.
4. Point-in-time observation envelope.
5. Cross-source reconciliation.

**Exit:** unsupported feeds fail explicitly; research jobs can declare minimum data contracts.

## P2 — Research validity layer

1. Persistent experiment-attempt ledger.
2. Family-level search accounting.
3. DSR.
4. PBO/CSCV.
5. Bootstrap uncertainty.
6. Negative controls.
7. Parameter-neighborhood and regime stability.

**Exit:** every promoted strategy carries search-context-adjusted evidence.

## P3 — Execution truth

1. Futures execution state machine.
2. Idempotency and client intent IDs.
3. Partial fills / cancel-replace races.
4. Broker rejection taxonomy.
5. Restart/reconnect reconciliation.
6. Broker-vs-engine position mismatch handling.

**Exit:** deterministic simulated broker tests cover recovery and mismatch scenarios.

## P4 — Portfolio risk

1. Contract-value normalization.
2. Gross/net exposure.
3. correlated-risk clusters.
4. vol targeting.
5. daily/rolling loss controls.
6. event/session risk budgets.
7. global flatten/recovery semantics.

**Exit:** portfolio risk is evaluated before execution intent reaches adapters.

## P5 — Market microstructure expansion

1. Separate trade-footprint and quote-book data contracts.
2. L1/L2 ingestion where legitimately available.
3. Event sequencing and clock-quality checks.
4. Queue/latency models only when supported by data.
5. adverse-selection diagnostics.

**Exit:** simulation fidelity is tagged and never exceeds underlying data resolution.

## P6 — Audit/operations

1. End-to-end decision traces.
2. digest chaining.
3. independent/witnessed checkpoints.
4. incident replay.
5. fault injection / chaos qualification.
6. feed-gap and stale-data SLOs.

**Exit:** important production incidents can be reconstructed and privileged local tampering cannot be silently hidden by rewriting only local history.

## P7 — Scale

Only after P0-P6:
- distributed parameter studies
- multi-asset portfolio research
- cache/content-addressed datasets
- batch orchestration
- compute-budget governance
- larger empirical surfaces

Scale should multiply valid experiments, not multiply overfitting.
