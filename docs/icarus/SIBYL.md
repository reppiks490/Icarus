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

SIBYL also applies a source-revision guard. For each named source, only observations from that source's newest observed `source_commit` participate in the live lightcone. Historical rows remain in the immutable ledger for audit and replay, but an older implementation cannot be blended with a newer implementation to manufacture agreement. Repeated emissions from one source are averaged before domain fusion and cannot increase that source's authority simply by publishing more rows.

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

## Future world forker

SIBYL converts the marginal basin distributions across horizons into a bounded beam of coherent future-world paths. Each retained world contains:

- a basin state at every requested horizon;
- a compact path signature;
- terminal basin;
- relative weight within the retained beam.

Transition penalties discourage implausibly violent basin flips without making them impossible. The displayed weights are explicitly **relative across retained beam paths**, not an exhaustive joint probability claim.

## Liquidity gravity field

Attractor and invalidation clusters are projected onto a local price grid around the current market. Attractors pull the normalized field toward concentrated target levels; invalidations act as repulsive thesis-failure boundaries.

The field exposes:

- normalized local force;
- strongest attractor;
- strongest invalidation;
- approximate local equilibrium price.

This is a synthesis visualization of published evidence, not a physical law or guaranteed price destination.

## Causal delay radar

Evidence payloads may publish bounded `causal_edges` such as:

- source node;
- target node;
- reported lag in milliseconds;
- relation;
- edge confidence.

SIBYL preserves the publisher, evidence domain, observation time, and source revision with every edge. It does not independently relabel a reported lead/lag relationship as proven causality.

## Derivatives forward surface

Evidence payloads may publish a `forward_surface` by horizon containing values such as:

- expected return;
- implied volatility;
- skew;
- upside tail mass;
- downside tail mass.

SIBYL source-collapses repeated rows and confidence-weights the surviving sources into a horizon surface. Missing derivatives data produces an explicit empty surface rather than a fabricated estimate.

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

The purpose of SIBYL is not to "know" a fixed future. It continuously narrows, falsifies and calibrates the set of futures that remained plausible at a specific causal as-of boundary.

## Causal replay and as-of contract

SIBYL v2 separates the **decision clock** from the wall-clock time at which a
request happens to be computed.

- Every forecast has an immutable `observed_at` / synthesis `as_of` clock.
- Only evidence with `evidence.observed_at <= as_of` may participate.
- Evidence freshness, attractor mass, invalidation mass and horizon weights are
  measured from that same `as_of` clock, never from wall-clock "now".
- A historical forecast that supplies `observed_at` must also supply its
  historical `current_price`. SIBYL refuses to borrow the live market price.
- A historical counterfactual that supplies `as_of` follows the same rule.
- The persisted forecast semantic does not contain computation time.
  Recomputing the same forecast inputs against the same evidence ledger therefore
  yields the same forecast identity.
- `computed_at` is operational metadata only and is not evidence or forecast
  identity.

This keeps replay deterministic and prevents future/late evidence from leaking
back into an earlier forecast.

## Outcome maturity

A forecast horizon is not eligible for scoring until:

`outcome.observed_at >= forecast.observed_at + horizon_seconds`

An outcome that arrives before that maturity boundary is rejected. Outcomes
remain immutable per `forecast_id + horizon_seconds` after settlement.

## PANTHEON -> SIBYL structural bridge

The source name `pantheon-ananke` is reserved. Generic SIBYL evidence ingestion
cannot publish under that identity.

PANTHEON may feed SIBYL only through the validated internal structural export:

- source: `pantheon-ananke`
- domain: `structural_constraints`
- producer: `PANTHEON/ANANKE`
- explicit shadow-only authority block
- execution, production decision, broker, sizing and automatic promotion
  authority all false

GÖDEL ambiguity, NEMESIS survival and PANTHEON data quality are already folded
into the export confidence before SIBYL sees it. No other PANTHEON faculty is
turned into an extra directional vote.

PANTHEON durability is upstream of the bridge. If SIBYL ingestion fails, the
already-recorded PANTHEON observation is not rolled back; the bridge failure is
reported separately for audit.

## Forecast identity

Persisted SIBYL forecast identity is a hash of deterministic semantic state:

- asset
- exact as-of time
- historical/current price used by that forecast
- volatility assumption
- requested horizons
- exact source Git revision
- sorted evidence IDs available at the as-of boundary
- deterministic future-lightcone synthesis

Wall-clock computation time is intentionally excluded.

