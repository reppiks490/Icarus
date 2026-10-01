# ORACLE Ψ — Market Possibility Research Layer

ORACLE Ψ is a research-only possibility engine inside ICARUS. It is deliberately separated from broker authority, live strategy mutation, asset/timeframe/chart configuration, and the execution path.

## What it computes

- **Latent pressure** from authenticated/observed evidence domains when available: trade-flow, order-book queue/repricing, lagged cross-asset context, basis, gamma, and forced-flow evidence.
- **Pressure / price elasticity** diagnostics for absorption, normal response, and liquidity-vacuum hypotheses.
- **Dynamic leadership** from lagged cross-asset associations. These are descriptive diagnostics, not proof of structural causality.
- **Synthetic force-balance price** and one-force-removed market shadows.
- **Deterministic future-space scenarios**, entropy, and future-space collapse.
- **Phase-boundary diagnostics** only when latent pressure is directionally non-neutral.
- **Forced consensus** across distinct evidence domains. Multiple correlated microstructure features count as one domain and cannot create false independence.
- **NO_EDGE** when evidence, coverage, future-space collapse, leader state, or consensus is insufficient.

## Evidence and provenance rules

1. Missing evidence stays unavailable. It is never silently filled with zero.
2. Coverage is confidence-weighted, not merely a count of present fields.
3. External evidence must carry a named source and an RFC3339 observation timestamp with an explicit timezone when supplied.
4. Future observation timestamps are rejected.
5. Gamma, basis, CTA, liquidation and rebalance inputs remain optional provenance-labelled research evidence.
6. Scenario cluster shares are **not calibrated probabilities**.
7. Cross-asset lagged association is **not causal proof**.
8. A directional research bias is **not a trade authorization**.

## Trader interface

The ICARUS trader exposes a dedicated **ORACLE Ψ** tab backed by authenticated:

- `GET /api/possibility?asset=NQ`
- `POST /admin/possibility/evidence`

The panel surfaces latent pressure, evidence coverage, future entropy/collapse, counterfactual price, phase-boundary state, forced consensus, evidence health, dynamic leaders, market shadows, and explicit blockers.

Every response preserves:

- `production_decision_authorized=false`
- `execution_authorized=false`

## Isolation boundary

This integration does **not** modify the separate engine-repair workstream: asset registry/add-assets, timeframe support, chart construction, sub-minute handling, broker routing, strategy execution, and order handling remain untouched.

## Known research limitations

- The current market-history cache is populated by possibility snapshots; a future research-only background sampler can make the history independent of UI polling.
- Cross-asset histories are currently tail-aligned rather than exchange-time bucket aligned.
- Optional external force evidence is currently process-local and should later gain a durable provenance ledger.
- Model thresholds and scenario weights require forward/shadow validation before any stronger interpretation.

These limitations are visible research gaps, not hidden assumptions.
