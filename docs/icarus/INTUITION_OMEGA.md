# ICARUS INTUITION Ω — Evidence-Bounded Market Cognition

**Status: isolated research implementation; NOT trained on authenticated history, NOT integrated into production, NOT merged.** A subsystem commit is not a validated trading advantage.

This package strengthens the existing ICARUS Learning Fabric, APEX Ω, PARALLAX, SIBYL, Ψ, DREAMSTATE, Adaptive Brain and installed protected trainers. It contains no broker, order, position, sizing, strategy-input mutation or production-promotion API. Its authority flags are always false.

## Implemented in this branch

| Layer | File | Scientific safeguards |
|---|---|---|
| Strict point-in-time contracts | intuition_omega/contracts.py | Venue/asset/timeframe/regime/target/feature schema; source SHA, evidence IDs and real-vs-HA fill separation |
| Episodic memory | intuition_omega/episodic.py | SQLite WAL, immutable content hashes, settled outcome receipts, overlap purge, as-of retrieval |
| Analogue cognition | intuition_omega/episodic.py | Precommitted scales, bounded distances, temporal adaptation, minimum independent events/sessions, abstention |
| Prequential truth ledger | intuition_omega/calibration.py | Immutable forecast/outcome pairs; forecast must be recorded before maturity |
| Precision scorecards | intuition_omega/calibration.py | Brier, log loss, tie-preserving ECE, locked-baseline Brier skill, deterioration checks |
| Model council | intuition_omega/expertise.py | Rejects shared roots, future scorecards, degraded models and material disagreement |
| Falsifiable hypotheses | intuition_omega/expertise.py | Recorded contradictions, supports, falsifiers and horizon; no invented probabilities |
| Mega API admission | intuition_omega/providers.py | Entitlement, research-use, granularity, vintage, receive time and local receipt checks |
| Cross-examination | intuition_omega/evaluation.py | Chronological prequential walk-forward, non-overlapping support, frozen final fold |
| Negative tests | tests_engine/test_intuition_omega.py | Time travel, identity collisions, HA fill mismatches, drift, source rights, calibration, independence |

These are **importable research components**, not running collectors, deployed dashboard gauges or a production-trained model. Real authorized data fitting remains unperformed.

## From pattern recognition to advanced intuition

1. OBSERVE: market tapes, order-book samples, price bars, official releases and historical revisions must retain true evidence classes. Candle/volume proxies are never presented as an observed order book.
2. RECALL: analogues must have matured and been received before the target decision. Exact target, instrument, venue, chart, fill, timeframe, feature schema and regime identities must agree. A TradingView synthetic Heikin Ashi fill is never silently substituted for a real-price fill.
3. HYPOTHESIZE: distinguish directly observed, reconstructed, derived, inferred and unavailable. Attach falsifiers and contradictory observations instead of creating post-hoc causal stories.
4. PREDICT BEFORE THE ANSWER: immutable forecast, source commit, observation/emission/receipt/maturity times and reference evidence must precede settlement.
5. MEASURE: properly scoped log loss, Brier, calibration error, model-versus-baseline skill, coverage, abstentions, contamination and drift.
6. CHALLENGE: ablate every provider, feature family and expert; compare against naive locked baselines and the actual incumbent in protected regimes.
7. ADAPT: pursue regime-specific competence, transparent recency weights, held-out challenger recalibration and drift retirement. Never silently auto-promote.
8. GOVERN: source rights, event causality, model revision identity, full ancestry and non-execution are unbreakable boundaries.

### Critical calibration distinction

Analogue similarity is not predictive probability. The reasoner reports a descriptive weighted historical hit rate and a conservatively session-sized **heuristic** Wilson interval. It explicitly labels this NOT prospectively calibrated. The separate forecast ledger is required to accumulate predictions committed before outcome and evaluate reliability honestly. Weighted intervals do not have guaranteed nominal frequentist coverage. Expand with clustered/block-bootstrap uncertainty, protected out-of-fold isotonic/conformal diagnostics and the existing Learning Fabric calibration machinery when real outcomes are available.

Likewise, an expert ensemble is **not calibrated by averaging individually calibrated experts**. The current model council labels consensus uncalibrated; it must earn its own prospective calibration before any strong precision claim.

## Mega API plan — evidence contribution by domain

ICARUS already has an upstream collector inventory documenting approximately **1,105 provider operations** (docs/research/provider-exhaustive-collection.md). That is a catalog count, NOT a claim all endpoints are connected, entitled or fully harvested. This research package *does not replicate those collectors or make paid requests*.

- **Market microstructure:** Databento GLBX.MDP3 historical/live MBO, MBP-10 and trade/quote datasets where licensed, plus appropriately entitled CME, Nasdaq, OPRA feeds. Measure liquidity raids, absorptions, imbalance and resiliency only from data that actually observes those phenomena. No imaginary depth or queue position.
- **Cross-market/derivatives:** CBOE term structure, VIX, futures basis, rates, equities, options, FINRA positioning, CFTC COT, FX and sector proxies; potential sources include Massive, Intrinio, Tiingo, EODHD, FMP, Twelve Data, Quiver, Alpaca market data and Nasdaq Data Link. Respect market hours, latency and distinct symbol identities.
- **Official macro/vintage:** FRED/ALFRED, Federal Reserve, Treasury, BLS, BEA, Census, EIA, SEC EDGAR, USDA and NOAA. Store the original *release vintage* and when it became knowable, never today's revised value in yesterday's forecast.
- **Crypto/on-chain:** Bybit, Binance, Kraken, CoinGecko, Blockscout and available licensed derivatives/on-chain data. Keep spot, perp, funding, open interest, liquidations and aggregate metrics distinct.
- **Research documents/alternative:** Exa, Tavily, Parallel Search, Firecrawl, DataBlue, Consensus, Scite, Zacks, FactorWeave, TickerLayer and similar sources only with real access/rights. Document observations are hypothesis context, not executable prices.

Every admitted input requires verified entitlement, authorized research use, basic quality checks, dataset and record identity, precise observed time, reported receipt, engine-owned local receipt, granularity and original vintage where required. The ultimate HTTP/MCP intake must stamp local receipt **server-side**, not trust a caller-supplied timestamp. Connector presence is not verification of any feed. Sensitive raw files remain in private licensed archives, not public Git history. Metered external APIs require separate spending authorization; do not evade plan/credit limits using duplicate accounts.

**No arbitrary small-sample caps:** collectors should enumerate the authorized full history and report provider quota/coverage limitations honestly; limits on requests per run are transport throttling, never proof of complete acquisition.

## Expert-maximal training plan — NOT yet executed

1. Inventory existing credential and dataset coverage without reading/exposing raw secrets. Join revision-pinned historical data by venue, adjusted contract, session and genuine first-available timestamp.
2. Lock separate target labels: TP1-before-stop, TP2-before-stop, expected return, liquidity reclaim, and drawdown/invalidation. Encode real next-bar/tick fills, fees and slippage in distinct target contracts; measure HA strategy-state separately from synthetic HA fills.
3. Train specialist challengers per market/regime/horizon: causal-proxy ablations, fixed baselines, regime models, nearest-neighbor memory, tabular ensembles and sequence experts, and any novel hypothesis only if full data supports it.
4. Evaluate by chronological nested purged walk-forward with maximum-label-horizon embargo; hold a final untouched regime split and instrument stress splits. Use only timestamps and data vintages available at each decision.
5. Compare proper scores, prospective calibration, reliability, independence-adjusted uncertainty, cluster/block uncertainty, false confidence, and cost-aware net expectancy. Penalize complexity and multiple-comparison mining.
6. Train explicit **abstention and unlearning** policy: identify OOD states, stale data, collapsing edge, model disagreement, source outages and drift. Drift leads to quarantine/challenger research, not automatic self-modification.
7. Build cross-agent independent expertise from APEX, PARALLAX, SIBYL, DREAMSTATE and other candidates only when their forecasts have lineage-verified, matured, comparable scorecards. Shared data/model ancestry must collapse rather than multiply confidence.
8. Validate adversarial conditions: roll changes, FOMC/CPI, gaps, macro revisions, incorrect timestamps, major volatility shocks, contradictory flow, unavailable depth, HA-versus-real entry differences, future-scorecard leaks, and rejected entitlements.
9. Compare *every* addition with the same held-out incumbent and publish zero-fabrication receipts. The complexity must earn its place; high model count is not quality.
10. After documented approval and passing end-to-end tests, expose a **read-only** INTUITION Ω dashboard: independent episode count, empirical evidence vs calibrated probability, model skill/coverage, credible drift warnings, disagreement, contradictory hypotheses, provenance and **UNMEASURED** values. No unapproved styling changes to the rest of ICARUS.

No 100x improvement is claimed without real measured evidence. The goal is ambitious competence, not a fictional accuracy metric.

## Tests and integration gates

Run the new test suite: python -m pytest tests_engine/test_intuition_omega.py -q

Run existing regression: python -m pytest tests_engine/test_learning_fabric.py tests_engine/test_apex_*.py -q

Then full suite: python -m pytest tests_engine -q

Run Windows/Linux CI and manually inspect no-leakage and archival provenance. This branch has not yet been connected to current Learning Fabric/API/UI or authenticated providers. Implementation acceptance requires an approved, locally timestamped adapter, protected real-data tests and an independently verified prospective scorecard. Never trust caller-created model scorecards as proof at an untrusted HTTP boundary: authenticate and load immutable source receipts server-side before using expert reconciliation.

No active ICARUS loop or workflow, production UI, broker configuration, main branch or trading permission is changed here.


## Trusted Learning Fabric bridge (added after initial draft)

The optional research adapter intuition_omega/learning_bridge.py can inspect the *existing* Learning Fabric predictions/outcomes tables through SQLite read-only mode and transfer verifiable prospective binary forecasts to the Intuition Ω immutable forecast ledger. It does not mutate Learning Fabric, invent missing chart/fill/timeframe/label metadata, recover secrets or treat retrospectively uploaded historical forecasts as advance predictions. It requires the source database's actual recorded_at timestamps to precede the forecast maturity and the outcome's engine-recorded receipt to be no earlier than observation. Inputs missing an exact scope or source evidence fail closed with counted rejection reasons. The invoking future authenticated service must control which trusted SQLite source path may be read. This bridge is opt-in and not attached to the live scheduler.
