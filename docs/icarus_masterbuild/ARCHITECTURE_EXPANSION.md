# ICARUS Horizon Expansion Architecture

## Design objective

Increase capability by increasing **independent evidence, execution fidelity, falsifiability, fault isolation, and observability**. Avoid complexity that only increases parameter count or narrative sophistication.

## Control flow

```text
Source Mesh
  -> Point-in-Time Truth Layer
  -> Research Governance
  -> Qualification / Falsification
  -> Execution State Machine
  -> Portfolio Risk Kernel
  -> Broker / Venue
  -> Reconciliation
  -> Audit + Incident Replay
```

Authority moves right only when every required upstream state is known and valid.

Any `UNKNOWN`, `STALE`, `PROXY_ONLY`, `ENTITLEMENT_BLOCKED`, `PROVENANCE_FAILED`, or `ORACLE_DEPENDENT` state must either block promotion or explicitly downgrade the allowed action.

## 1. Provider Capability Registry

Add a typed registry with, at minimum:

- provider
- endpoint/dataset
- asset classes/instruments
- granularity
- historical depth
- live/delayed state
- authentication state
- entitlement state
- request limits/quota
- event-time semantics
- publication/revision semantics
- timezone
- expected freshness
- fallback priority
- data-license notes
- current health

A strategy/research job requests capabilities; routing resolves only providers that satisfy the declared contract.

## 2. Point-in-Time Truth Fabric

Every observation should carry:

- `event_time`
- `published_at`
- `received_at`
- `effective_at`
- `revision_id`
- `source_id`
- `source_payload_hash`
- `quality_state`
- `entitlement_state`
- `freshness_state`
- `conflict_state`

Revisions must never rewrite history invisibly.

## 3. Research Governance 2.0

Add:

- persistent experiment-attempt ledger
- experiment-family IDs
- hypothesis preregistration fields
- selection-space accounting
- nested walk-forward
- Deflated Sharpe Ratio
- PBO / CSCV
- stationary/block bootstrap uncertainty
- negative-control strategies
- parameter-neighborhood sensitivity
- ablation matrices
- cross-regime holdouts
- cost/latency stress surfaces

The final untouched holdout remains consumable only under explicit governance.

## 4. Mechanism Registry

Each alpha/risk candidate declares:

- economic/market mechanism
- required observables
- expected direction/sign
- who supplies the edge / who pays
- expected decay horizon
- failure regimes
- proxy substitutions allowed
- falsification tests
- minimum data quality

This prevents mechanism drift and post-hoc storytelling.

## 5. Microstructure 2.0

Keep two distinct systems:

### Trade-event footprint
Valid with trades:
- signed/aggressor volume
- cumulative delta
- trade imbalance
- realized trade intensity
- trade-price response

### Quote/order-book event model
Requires L1/L2:
- bid/ask adds
- cancels
- executions
- queue depletion
- spread/depth state
- genuine order-flow imbalance
- queue/latency fill modeling

Never silently cross the boundary.

## 6. Futures Execution State Machine

Required states and identifiers:

- deterministic client intent ID
- broker/exchange order ID
- idempotency key
- submitted / acknowledged / partial / filled / canceled / rejected / replaced
- reconnect state
- broker position snapshot
- engine expected position
- reconciliation delta
- recovery action
- operator intervention state

The broker is authoritative for actual fills/positions; ICARUS records intent and reconciles.

## 7. Execution Simulation

Models must be resolution-gated:

- bar-level: coarse slippage/commission only
- quote-level: spread + quote-dependent execution
- event/L2-level: queue, cancel, partial fill, latency and adverse-selection modeling

Simulation fidelity must never exceed data fidelity.

## 8. Portfolio Risk Kernel

Add:

- tick/point/contract-value normalization
- gross/net notional
- asset-class buckets
- correlation clusters
- realized-volatility targeting
- concentration limits
- session risk
- scheduled-event risk
- daily and rolling loss gates
- max order rate
- max open orders
- broker/exchange position mismatch gate
- flatten-all and recovery policies

## 9. Tamper-Evident Observability

For each decision/order/fill:

```text
data snapshot -> features -> config -> model/strategy version
-> decision -> risk decision -> order intent -> broker response
-> fill/reject -> position -> PnL -> audit checkpoint
```

Add digest chaining plus optional independent checkpoint anchoring/witnessing.

## 10. Cross-Asset and Event Lab

Research DXY, Treasury rates, equities, metals, crypto and macro releases with:

- synchronized timestamps
- explicit lead/lag matrices
- publication-known-at timestamps
- revision awareness
- event surprise fields when consensus exists
- leakage tests
- session-specific conditioning
- robustness across instruments/regimes

## 11. Redundancy Graph

Measure incremental value rather than vote count across EMA/VWAP/RSI/CCI/Kalman/Hurst/FDI/volatility/regime families.

Candidates that add no stable out-of-sample information should be deleted or demoted, even if they look sophisticated.

## 12. Release Qualification

No module reaches `VERIFIED_FOR_INTEGRATION` without:

- unit tests
- regression tests
- deterministic replay check
- dataset/config fingerprints
- cross-platform CI where relevant
- oracle-independence check
- stress/fault tests appropriate to risk
- backward-compatibility review
- rollback path
- evidence ledger entry
