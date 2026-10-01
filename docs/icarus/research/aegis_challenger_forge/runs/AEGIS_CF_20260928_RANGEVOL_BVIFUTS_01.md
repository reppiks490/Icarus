# AEGIS Challenger Forge — Incremental Collection Run

- run_id: AEGIS_CF_20260928_RANGEVOL_BVIFUTS_01
- date: 2026-09-28
- mode: COLLECTION_ONLY
- parent_remote_head: 2e43fcbe5aca12552381cda0b4231931c6558b57
- scope: incremental additions only; preserves all prior AEGIS and sibling checkpoints
- prohibited_actions_performed: none (no backtest, scoring, ranking, promotion, componentization, coding, execution, or production mutation)
- numeric_effort_control: unavailable; deepest safe analysis exposed by runtime used

## NEW SOURCES

### AEGIS-CF-RANGE-PARKINSON-DOI-10.1086-296071
- source identity: DOI 10.1086/296071
- title: The Extreme Value Method for Estimating the Variance of the Rate of Return
- author: Michael Parkinson
- publication: The Journal of Business, 53(1), 61-65, January 1980
- provenance: primary peer-reviewed research identity; bibliographic metadata cross-checked through RePEc/EconPapers
- core taxonomy: high-low range-based variance estimation under continuous-random-walk / zero-drift style assumptions
- required inputs: period high and low prices
- applicability: generic OHLC market series; transfer to BTC/NQ/Gold depends on sampling/session/gap conventions
- observed facts: estimator uses extreme high-low information rather than close-only returns
- unverified-claim boundary: relative-efficiency statements remain paper results, not AEGIS performance evidence
- access/licensing: journal/JSTOR access restrictions apply to publisher full text; DOI metadata public

### AEGIS-CF-RANGE-GK-DOI-10.1086-296072
- source identity: DOI 10.1086/296072
- title: On the Estimation of Security Price Volatilities from Historical Data
- authors: Mark B. Garman; Michael J. Klass
- publication: The Journal of Business, 53(1), 67-78, January 1980
- provenance: primary peer-reviewed research identity; CME-hosted author manuscript plus RePEc bibliographic metadata
- core taxonomy: OHLC volatility estimation using open/high/low/close under Brownian-motion assumptions
- required inputs: open, high, low, close
- applicability: generic OHLC series; zero-drift/no-opening-jump assumptions must be preserved when interpreting the classical estimator
- observed facts: method explicitly uses intraperiod range and open/close information
- unverified-claim boundary: relative-efficiency results remain source findings
- access/licensing: publisher full text is restricted; a CME-hosted manuscript copy is publicly readable but does not alter underlying copyright

### AEGIS-CF-RANGE-RS-DOI-10.1214-aoap-1177005835
- source identity: DOI 10.1214/aoap/1177005835
- title: Estimating Variance From High, Low and Closing Prices
- authors: L. C. G. Rogers; Stephen E. Satchell
- publication: The Annals of Applied Probability, 1(4), 504-512, 1991; published online 1991-11-14
- provenance: primary peer-reviewed journal identity / Project Euclid lineage
- core taxonomy: drift-independent range-based variance estimation
- required inputs: open-relative high/low/close price relationships over each period
- applicability: generic OHLC series; removes the zero-drift restriction but does not by itself solve opening-jump handling
- observed facts: paper proposes an estimator unbiased with respect to drift under its model assumptions
- unverified-claim boundary: correction/efficiency comparisons remain paper results
- access/licensing: Project Euclid/journal access terms apply

### AEGIS-CF-RANGE-YZ-DOI-10.1086-209650
- source identity: DOI 10.1086/209650
- title: Drift-Independent Volatility Estimation Based on High, Low, Open, and Close Prices
- authors: Dennis Yang; Qiang Zhang
- publication: The Journal of Business, 73(3), 477-491/492, July 2000
- provenance: primary peer-reviewed research identity; RePEc and institutional bibliographic records cross-checked
- core taxonomy: multi-period OHLC volatility; decomposition into overnight/open jump, open-close and Rogers-Satchell terms
- required inputs: consecutive-period open, high, low, close prices
- applicability: generic OHLC series; particularly relevant where opening/session gaps are meaningful
- observed facts: method is designed to be drift-independent and to incorporate opening jumps
- unverified-claim boundary: minimum-variance/accuracy comparisons remain author findings
- access/licensing: University of Chicago Press copyright; publisher/JSTOR access restrictions apply

### AEGIS-CF-RANGE-TTR-GH-d152a3f6ddc7
- source identity: joshuaulrich/TTR tag v0.24.4 -> commit d152a3f6ddc7a27299758bd2fa8f41d409965390
- release date: 2023-11-28
- authors/maintainers: Joshua Ulrich; Ethan B. Smith contributor
- provenance: commit-pinned open-source implementation + CRAN release metadata
- core taxonomy: runnable implementations of Parkinson, Garman-Klass, Rogers-Satchell, Garman-Klass/Yang-Zhang and Yang-Zhang estimators
- required inputs: OHLC xts/matrix data, lookback n, annualization N; Yang-Zhang optional alpha/k controls
- applicability: generic R time series including BTC/NQ/Gold when session/calendar annualization and gap semantics are configured appropriately
- observed facts: source file R/volatility.R at pinned commit directly implements the estimator formulas; package DESCRIPTION at tag v0.24.4 reports version 0.24.4
- unverified-claim boundary: documentation efficiency statements are not treated as independent validation
- access/licensing: GPL version 2 or later
- implementation source blob: 6a73c4adba22f97a5394f8a191671b58cb784ccf

### AEGIS-CF-CME-BVIFUT-SPECS-DOCSNAP-20260928
- source identity: CME Bitcoin Volatility Futures Contract Specs, retrieval snapshot 2026-09-28
- organization: CME Group
- provenance: first-party exchange contract specification
- core taxonomy: financially settled Bitcoin implied-volatility futures linked to CME CF Bitcoin Volatility Index
- required market fields: futures price/volume/OI plus underlying BVXS reference for final settlement
- observed current-state facts as of 2026-09-28:
  - current CME Globex/ClearPort/clearing product code: BVI
  - BTIC code: BVB
  - contract unit: $500 x CME CF Bitcoin Volatility Index
  - minimum tick: 0.05 index points = $25; BTIC 0.01 = $5
  - listed months: two consecutive monthly contracts
  - settlement: financial
  - current contract page states 24/7 trading subject to documented maintenance windows
- applicability: BTC forward-volatility futures / volatility term-structure and positioning corpora
- access/licensing: public specifications; real-time/historical exchange market data governed separately
- source URL: https://www.cmegroup.com/markets/cryptocurrencies/volatility/bitcoin-volatility/specs

### AEGIS-CF-CME-BVIFUT-CODECHANGE-SER9819-20260909
- source identity: CME SER-9819
- notice date: 2026-09-09
- effective date: 2026-09-30
- organization: CME Group
- provenance: first-party exchange Special Executive Report
- core taxonomy: commodity-code transition for Bitcoin Volatility Futures
- observed fact: commodity code changes to BTCV effective 2026-09-30
- current-state boundary: this collection run is dated 2026-09-28, therefore BVI remains the current code in the contemporaneous contract-spec snapshot; BTCV is preserved as a future effective transition, not current metadata
- access/licensing: public exchange notice; underlying data rights separate
- source URL: https://www.cmegroup.com/notices/ser/2026/09/ser-9819.html

## NEW CORPUS IDS
- AEGIS-CF-RANGE-PARKINSON-DOI-10.1086-296071
- AEGIS-CF-RANGE-GK-DOI-10.1086-296072
- AEGIS-CF-RANGE-RS-DOI-10.1214-aoap-1177005835
- AEGIS-CF-RANGE-YZ-DOI-10.1086-209650
- AEGIS-CF-RANGE-TTR-GH-d152a3f6ddc7
- AEGIS-CF-CME-BVIFUT-SPECS-DOCSNAP-20260928
- AEGIS-CF-CME-BVIFUT-CODECHANGE-SER9819-20260909

## DUPLICATES
- AEGIS-CF-PINE-GYTS-VOLTOOL-TV-Th3bPWea-SNAPSHOT-20260928 already implements the four range-estimator families in Pine. This run adds primary-paper identities plus an independently versioned R implementation rather than re-admitting the Pine family.
- ATR/generic volatility regimes remain known-family overlaps and were not admitted.
- BVX/BVXS methodology corpora were admitted in the prior run. This run adds the traded Bitcoin Volatility Futures contract/reference layer, not another benchmark-methodology copy.
- The repository Trumpingtons/RangeVol.jl at commit c266f235... was inspected but not admitted because its README install path still points to antseabra/RangeVol.jl while the currently exposed repository owner/path is Trumpingtons/RangeVol.jl. TTR v0.24.4 provides a cleaner immutable implementation identity.
- Known AEGIS families remain excluded: OperationGoldenExecutioner, BTC MASTER, NQ Confluence, pivot/fractal, Renko/tick-volume, HMM/KNN, VWAP/volume-sweep, SMC/FVG, generic regime, Kalman and cointegration/stat-arb.

## COVERAGE BY FACET
- Pine/TradingView: no new script; provenance behind the already-collected range-volatility Pine family materially strengthened.
- Academic/public quantitative research: four original range-volatility source papers admitted.
- Official documentation: current CME Bitcoin Volatility Futures contract specs and dated future code transition admitted.
- GitHub/open source: commit-pinned CRAN/TTR implementation admitted.
- Market microstructure/execution: no new queue rule in this increment.
- BTC: benchmark methodology now links to a distinct traded volatility-futures product layer.
- NQ/Gold: range-volatility source/implementation family is instrument-agnostic; no current GC/MGC matching inference made.
- Volatility/factor: strengthened estimator assumptions around drift, opening jumps, range information and calendar/session treatment.
- Alternative data: BVI/BVXS-linked futures price/volume/OI form a distinct tradable forward-volatility market-data plane.

## SOURCE QUALITY/PROVENANCE
- Four estimator identities are primary peer-reviewed research references with stable DOIs.
- TTR is pinned to an exact release tag and commit, and the exact implementation source file was inspected.
- CME contract and code-transition corpora are first-party exchange documentation.
- Observed formulas, metadata, assumptions and contract fields are separated from efficiency/accuracy/predictive claims.
- No paper, implementation or futures product is converted into a strategy score, ranking, promotion or production rule.

## ACCESS/Licensing LIMITS
- Parkinson, Garman-Klass and Yang-Zhang publisher full text may require journal/JSTOR access; bibliographic/DOI metadata remains public.
- Rogers-Satchell access follows Project Euclid/journal terms.
- TTR v0.24.4 is GPL >= 2.
- CME specifications/notices are publicly readable; market-data redistribution and historical-feed usage are separate licensed rights.
- Bitcoin Volatility Futures code transition to BTCV is future-dated relative to this run and must not be applied to pre-2026-09-30 observations.
- Consensus remains known quota-blocked until 2026-10-01.
- Scite remains known MCP-quota-blocked until 2026-10-01.
- Numeric effort control is not exposed.

## COLLECTION GAPS
- Live/current standard GC/MGC outright MatchAlgorithm rows remain unresolved.
- Exact current CME Options Analytics product membership for NQ/GC remains entitlement-gated.
- Point-in-time Bitcoin Volatility Futures market data retention/redistribution terms and historical-field schema.
- Venue/calendar guidance for applying daily OHLC range estimators consistently to 24/7 BTC versus sessioned NQ/Gold.
- Original-method provenance for additional range estimators such as Alizadeh-Brandt-Diebold remains optional future collection.
- Commit-pinned permissive implementation of hidden-liquidity inference remains unresolved.

## NEXT COLLECTION TARGETS
1. Resolve standard GC/MGC MatchAlgorithm from current CME instrument reference data without inference.
2. Collect historical-field/retention/licensing semantics for Bitcoin Volatility Futures price, volume and OI.
3. Add Alizadeh-Brandt-Diebold and other non-duplicate range/stochastic-volatility source papers where methodologically distinct.
4. Collect exchange-session/calendar normalization references for applying range estimators to BTC/NQ/Gold.
5. Continue hidden-liquidity implementation provenance and current CME options-product coverage.

## CAPABILITY LEDGER
Successfully invoked in this increment:
- Superpowers using-superpowers guidance
- Superpowers brainstorming guidance
- Superpowers verification-before-completion guidance (to govern final verification)
- Exa Deep Research
- Firecrawl primary-source page extraction
- Parallel Search cross-check
- GitHub authenticated repository read/search/fetch/write surfaces and public-repository tag/commit/file inspection

Known unavailable:
- Consensus: monthly quota exhausted until 2026-10-01
- Scite: monthly MCP quota exhausted until 2026-10-01

Exposed but not materially required after source convergence:
- Tavily
- DataBlue
- Google Drive/File Library fallback

No AEGIS production component, strategy, test, score, ranking or sibling workstream was modified.
