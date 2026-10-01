# SIBYL Ω — Probabilistic Future-Lightcone Engine

SIBYL Ω is ICARUS's future-state synthesis layer. It does **not** claim deterministic foresight. It estimates a bounded distribution of reachable market states from time-valid, provenance-bearing research evidence and then measures whether that future distribution is converging, bifurcating, or remaining diffuse.

SIBYL is research/shadow-only. It cannot place orders, change sizing, arm a broker, mutate production strategy rules, or promote itself into production.

## Role in the ICARUS fabric

SIBYL is owned by AION and consumes evidence published by sibling systems through an explicit contract.

- **NEXUS / DATA** own market-data identity, clocks, freshness, representation quality and replay truth.
- **ARGUS** owns authenticated microstructure and execution-physics evidence.
- **ORACLE** owns causal financial / latent-pressure research evidence in its own branch and lifecycle.
- **PARALLAX** owns observed counterfactual decision twins and regret evidence.
- **DREAMSTATE** owns bounded policy-hypothesis incubation.
- **ATHENA** owns supervisory uncertainty/risk routing.
- **DAEDALUS / AEGIS** own protected validation and adversarial falsification.
- **SIBYL** owns probabilistic future-state synthesis, convergence/collapse, bifurcation/fracture, reachable-state bands, attractor/invalidation concentration, counterfactual future maps and measured forecast calibration.

SIBYL never infers directional meaning from another subsystem's presence or status. A sibling must publish a directional claim through the SIBYL evidence contract before that claim can influence probabilities. This prevents semantic contamination and accidental double counting.

## Evidence contract

Authenticated endpoint:

`POST /admin/sibyl/evidence`

Required fields:

- `asset`
- `source`
- `domain`
- `observed_at` with explicit timezone
- `direction` in `[-1, 1]`
- `confidence` in `[0, 1]`
- `horizon_seconds`
- `source_commit`

Optional fields:

- `magnitude`
- `target_price`
- `invalidation_price`
- `payload` such as `volatility_pct`

Evidence is content-addressed and immutable.

## Correlation guard

Multiple signals from the same evidence domain are collapsed **before** cross-domain consensus.

For example, order-book imbalance, trade imbalance and sweep detection may all originate from ARGUS microstructure. They are not allowed to count as three independent confirmations merely because they are three features.

This is the central protection against false "future collapse" caused by correlated evidence.

## Multi-horizon future basins

Default horizons:

- 60 seconds
- 5 minutes
- 15 minutes
- 1 hour
- 4 hours

For every horizon SIBYL reports:

- probability of **up**
- probability of **rotation**
- probability of **down**
- normalized entropy
- convergence
- evidence coverage
- collapse score
- bifurcation/fracture score
- independent domain count
- contributing evidence count
- reachable price band when current price is available

The distribution is deliberately expressed as probabilities rather than a single target.

## Temporal Collapse

A **Future Collapse** is emitted only when:

1. at least three independent evidence domains contribute;
2. evidence coverage is sufficiently high;
3. one basin dominates the reachable-state distribution;
4. entropy is sufficiently low.

It means the currently modeled future-state distribution has narrowed materially. It does **not** mean the future is guaranteed.

## Temporal Fracture

A **Temporal Fracture** identifies a horizon where opposing directional basins retain substantial probability mass.

This is a decision-instability state: small new evidence may rapidly move the distribution from one basin to another.

## Attractors and invalidations

Evidence publishers may attach:

- `target_price` — contributes to the attractor field;
- `invalidation_price` — contributes to repulsion / thesis-failure boundaries.

Nearby levels are clustered and weighted by confidence, magnitude and freshness. SIBYL therefore exposes concentrated future levels without pretending they are deterministic destinations.

## Counterfactual future map

Authenticated endpoint:

`POST /admin/sibyl/scenario`

A scenario adds temporary interventions such as:

- volatility shock
- order-flow reversal
- macro impulse
- derivatives-pressure change
- liquidity withdrawal
- a hypothetical target or invalidation

Counterfactual interventions exist only for the request. They are never written to the evidence ledger.

## Immutable forecasts and calibration

Create a forecast:

`POST /admin/sibyl/forecast`

Score a realized outcome:

`POST /admin/sibyl/outcome`

Forecasts are bound to:

- exact source commit;
- evidence IDs;
- current price;
- volatility assumption;
- requested horizons.

Observed outcomes are immutable per forecast + horizon. SIBYL calculates a multiclass Brier score and exposes:

- sample count;
- mean Brier score;
- dominant-basin hit rate;
- mean stated dominant confidence.

Unmeasured confidence is explicitly labeled **unmeasured**. The UI does not convert confidence into an accuracy claim.

## Trader interface

Authenticated read endpoint:

`GET /api/sibyl?asset=NQ`

The **SIBYL Ω** tab displays:

- current future-lightcone state;
- strongest collapse horizon;
- strongest fracture horizon;
- up / rotation / down probabilities;
- entropy and convergence;
- coverage and independent domain count;
- reachable-state bands;
- attractor / invalidation concentrations;
- observed calibration;
- recent immutable forecasts;
- explicit shadow-only authority state.

## Storage

SQLite WAL database:

`research/sibyl.sqlite3`

Tables:

- `evidence`
- `forecasts`
- `outcomes`

## Truth contract

SIBYL intentionally refuses these shortcuts:

- correlated features cannot masquerade as independent confirmation;
- future timestamps are rejected;
- timezone-free evidence is rejected;
- counterfactual interventions cannot contaminate observed evidence;
- unmeasured confidence is not labeled accuracy;
- a high collapse score is not labeled certainty;
- sibling subsystem context is not silently converted into directional evidence;
- no result grants production-decision or execution authority.

The purpose of SIBYL is not to "know" the market's future. It is to continuously narrow, falsify and calibrate the set of futures that remain plausible.
