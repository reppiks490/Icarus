# AEGIS Challenger Forge — Incremental Collection Run

- run_id: AEGIS_CF_20260928_SESSION_RANGEVOL_02
- date: 2026-09-28
- mode: COLLECTION_ONLY
- parent_remote_head: 069f4e638aaaf08d563a58d33c09f9f413989bbf
- scope: incremental additions only; preserves all prior AEGIS and sibling checkpoints
- prohibited_actions_performed: none (no backtest, scoring, ranking, promotion, componentization, coding, execution, or production mutation)
- numeric_effort_control: unavailable; deepest safe analysis exposed by runtime used

## NEW SOURCES

### AEGIS-CF-RANGE-ABD-DOI-10.1111-1540-6261.00454
- source identity: DOI 10.1111/1540-6261.00454
- title: Range-Based Estimation of Stochastic Volatility Models
- authors: Sassan Alizadeh; Michael W. Brandt; Francis X. Diebold
- publication: The Journal of Finance, 57(3), 1047-1091, June 2002
- first-published metadata observed on Wiley: 2002-12-17; journal issue identity is 2002 volume 57 issue 3
- provenance: primary peer-reviewed paper; Wiley and Duke bibliographic records cross-checked
- core taxonomy: use of log price range as a volatility proxy inside stochastic-volatility model estimation; range-based Gaussian quasi-maximum likelihood; latent-volatility extraction
- required inputs: daily high-low range (or equivalent log range) over a consistent trading/session definition
- empirical source in paper: daily exchange-rate volatility
- applicability: methodologically distinct from standalone Parkinson/GK/RS/YZ estimators because it embeds range proxies into stochastic-volatility model estimation
- observed facts: paper proposes range-based stochastic-volatility estimation and evaluates one- versus two-factor volatility dynamics
- unverified-claim boundary: efficiency, approximate-Gaussianity, robustness-to-microstructure-noise, and model-comparison conclusions remain author findings
- access/licensing: Wiley/publisher copyright and access terms apply; DOI metadata public

### AEGIS-CF-BTC-YZ-PREPRINT-10.20944-PREPRINTS202602.0560.v1
- source identity: DOI 10.20944/preprints202602.0560.v1
- title: Realised Volatility Estimation Shortcuts: An Empirical Analysis
- authors: David Edmund Allen; Chialin Chang; Kok-Haur Ng; Shelton Peiris
- publication identity: Preprints.org v1, posted 2026-02-06
- provenance: primary preprint; not peer-reviewed evidence in this corpus
- core taxonomy: empirical Bitcoin application of Yang-Zhang range-based realized volatility benchmarked against bipower variation
- required inputs: hourly BTC/USDT OHLC, aggregated to daily estimates; comparison BPV inputs
- sample: 2018-01-01 through 2025-05-29; 64,823 hourly observations reported by authors
- data provenance: authors state Binance-originated data distributed through a Kaggle dataset
- applicability: directly relevant to 24/7 Bitcoin/session-normalization research
- observed fact: paper explicitly notes Bitcoin trades 24 hours/day and therefore lacks the traditional closed-market overnight gap mechanism
- unverified-claim boundary: regression fit, persistence, and equivalence/forecasting implications remain author results
- access/licensing: preprint access public; underlying Kaggle/Binance data retain separate terms

### AEGIS-CF-YZ-SWIMPACTS-DOI-10.1016-J.SIMPA.2024.100613
- source identity: DOI 10.1016/j.simpa.2024.100613
- title: Yang & Zhang's realized volatility: Automated estimation in Python
- authors: Hugo Gobato Souto; Amir Moradi
- publication: Software Impacts 19, article 100613, 2024
- accepted: 2024-01-09; source metadata shows 2024 publication
- provenance: peer-reviewed software publication
- core taxonomy: automated univariate/multivariate Yang-Zhang realized-volatility estimation from high-frequency intraday OHLC; local-data and Yahoo/yfinance input paths
- required inputs: timestamped OHLC intraday data with consistent day grouping; optional ticker/date/interval parameters for Yahoo path
- applicability: implementation methodology for session-aware OHLC realized-volatility generation
- observed facts: publication points to the authors' public repository and reproducible capsule
- unverified-claim boundary: statements about first open-source automation, accuracy, or downstream research utility remain author/publication claims
- access/licensing: article metadata indicates Creative Commons/open publication terms; exact article license should be checked before redistribution

### AEGIS-CF-YZ-GH-HUGOGOBATO-deaa987542ce
- source identity: hugogobato/Yang-Zhang-s-Realized-Volatility-Automated-Estimation-in-Python
- pinned commit: deaa987542cea262255b3fb325a89deeacf5f6dc
- commit date: 2023-12-07
- authors: Hugo Gobato Souto; Amir Moradi
- provenance: commit-pinned implementation associated with Software Impacts DOI 10.1016/j.simpa.2024.100613
- core taxonomy: Python Yang-Zhang realized-volatility automation; univariate and multivariate; own-data and yfinance paths
- required inputs: DatetimeIndex OHLC DataFrame(s) or Yahoo ticker/date/interval requests
- observed implementation fact: code groups intraday observations using pandas Grouper(freq='1D'), making calendar-day/session boundary choice an explicit preprocessing dependency
- source file verified at commit: Yang_Zhang_RV_proxy.py blob 312b1a338cffdeb67ebc155a4f9fcf3f9a05dfdf
- license: MIT; LICENSE.md verified
- unverified-claim boundary: no performance claim promoted

### AEGIS-CF-BTC-BINANCE-KLINE-DAYBOUNDARY-DOCSNAP-20260928
- source: official Binance Spot API documentation / binance-spot-api-docs
- retrieval snapshot: 2026-09-28
- provenance: first-party venue API documentation
- core taxonomy: kline/candlestick day-boundary semantics
- required inputs/parameters: symbol, interval, optional startTime/endTime, optional timeZone
- observed facts:
  - klines are uniquely identified by open time
  - default kline timeZone is 0 (UTC)
  - provided timeZone changes interval interpretation
  - startTime/endTime remain UTC regardless of timeZone
  - daily intervals are supported
- applicability: 24/7 BTC/crypto OHLC construction; day boundary is configurable and therefore must be stored as provenance for range-volatility corpora
- access/licensing: public API docs; venue terms/rate limits/data rights apply separately
- source URL: https://github.com/binance/binance-spot-api-docs/blob/master/rest-api.md

### AEGIS-CF-CME-NQ-SESSION-DOCSNAP-20260928
- source: CME Group E-mini Nasdaq-100 contract specifications
- retrieval snapshot: 2026-09-28
- provenance: first-party exchange product documentation
- core taxonomy: session/trading-day boundary definition for NQ
- observed facts:
  - NQ Globex trades Sunday 6:00 p.m. through Friday 5:00 p.m. ET
  - daily maintenance period 5:00 p.m.-6:00 p.m. ET
  - product code NQ
- applicability: NQ daily/intraday OHLC aggregation and cross-asset volatility normalization
- access/licensing: public specs; exchange historical/realtime data licensed separately
- source URL: https://www.cmegroup.com/markets/equities/nasdaq/e-mini-nasdaq-100.contractSpecs.html

### AEGIS-CF-CME-GC-SESSION-DOCSNAP-20260928
- source: CME Group Gold futures contract specifications
- retrieval snapshot: 2026-09-28
- provenance: first-party exchange product documentation
- core taxonomy: session/trading-day boundary definition for benchmark GC Gold futures
- observed facts:
  - GC Globex trades Sunday-Friday 6:00 p.m.-5:00 p.m. ET
  - daily 60-minute break begins at 5:00 p.m. ET
  - product code GC
- applicability: Gold OHLC aggregation and range-volatility normalization; MGC should not be assumed identical without preserving its own product metadata
- access/licensing: public specs; exchange historical/realtime data licensed separately
- source URL: https://www.cmegroup.com/markets/metals/precious/gold.contractSpecs.html

## NEW CORPUS IDS
- AEGIS-CF-RANGE-ABD-DOI-10.1111-1540-6261.00454
- AEGIS-CF-BTC-YZ-PREPRINT-10.20944-PREPRINTS202602.0560.v1
- AEGIS-CF-YZ-SWIMPACTS-DOI-10.1016-J.SIMPA.2024.100613
- AEGIS-CF-YZ-GH-HUGOGOBATO-deaa987542ce
- AEGIS-CF-BTC-BINANCE-KLINE-DAYBOUNDARY-DOCSNAP-20260928
- AEGIS-CF-CME-NQ-SESSION-DOCSNAP-20260928
- AEGIS-CF-CME-GC-SESSION-DOCSNAP-20260928

## DUPLICATES
- Yang-Zhang method itself was already admitted through the original 2000 paper, TTR implementation and Pine VolatilityToolkit. This run admits a software-publication/implementation identity and a Bitcoin-specific empirical application because they add distinct provenance and session-boundary behavior.
- Parkinson/Garman-Klass/Rogers-Satchell/Yang-Zhang original method identities were not duplicated.
- Generic ATR/regime/HMM/KNN/Kalman/VWAP/SMC-FVG/pivot/fractal/Renko/cointegration families remain excluded.
- Weak or unlicensed hidden-liquidity GitHub candidates were not admitted.
- GC/MGC MatchAlgorithm remains unresolved; no inference from session specs, TAS, options, 1-Ounce Gold or historical notices was made.

## COVERAGE BY FACET
- Pine/TradingView: no new script; supporting provenance for the existing range-volatility Pine family improved.
- Public quantitative research: added range-based stochastic-volatility modeling and Bitcoin-specific Yang-Zhang empirical work.
- Academic papers: one peer-reviewed Journal of Finance paper, one peer-reviewed Software Impacts paper, one clearly labeled preprint.
- Official documentation: added Binance day-boundary semantics plus current NQ and GC session specs.
- GitHub/open source: added commit-pinned MIT Yang-Zhang implementation associated with the software paper.
- Market microstructure/execution: no new execution model; session construction is added as a data-definition layer.
- BTC: explicit UTC/configurable daily kline semantics and 24/7 empirical range-volatility evidence.
- NQ: current product trading-day/session boundary source.
- Gold: current GC trading-day/session boundary source.
- Volatility/factor: extends from standalone range estimators into stochastic-volatility modeling and session-aware application.
- Alternative data: no new alternative-data source admitted in this increment.

## SOURCE QUALITY/PROVENANCE
- Grade A: first-party Binance and CME session documentation.
- Grade A/B: peer-reviewed Journal of Finance and Software Impacts publications.
- Grade B/C: 2026 Bitcoin study is preserved explicitly as a preprint, not promoted to peer-reviewed evidence.
- GitHub implementation is exact-commit and MIT-license pinned.
- Source mechanics, data definitions and assumptions remain separate from reported statistical/predictive performance.

## ACCESS/Licensing LIMITS
- Journal of Finance/Wiley access and copyright terms apply to Alizadeh-Brandt-Diebold.
- Software Impacts paper has open-publication metadata; exact article license should be normalized before redistribution.
- GitHub Yang-Zhang implementation is MIT.
- Binance/CME public documentation does not confer redistribution rights for underlying market data.
- Bitcoin empirical preprint relies on Binance-originated data distributed via Kaggle; dataset terms must be checked independently.
- Consensus invocation in this run was blocked: all 30 monthly searches used; resets 2026-10-01.
- Scite invocation in this run was blocked: 25-call monthly MCP limit reached; resets 2026-10-01.
- Numeric effort control is not exposed.

## COLLECTION GAPS
- Current standard GC/MGC outright MatchAlgorithm/tag-1142 rows remain unresolved.
- MGC-specific session metadata should be independently pinned if direct MGC range-volatility work is collected.
- Session-normalized cross-asset OHLC convention still requires an explicit corpus schema choice (e.g. venue-native day versus common UTC cut); this collection run records the source facts but does not choose a production convention.
- Exact license normalization for the 2026 Bitcoin preprint and Software Impacts article.
- Licensed CME MBO/trade-summary data for NQ/MNQ/GC/MGC.
- Commit-pinned hidden-liquidity inference implementation remains unresolved.

## NEXT COLLECTION TARGETS
1. Resolve current GC/MGC MatchAlgorithm from live CME reference/security-definition data.
2. Pin MGC contract session metadata separately from GC.
3. Collect primary research on venue-native versus common-clock volatility aggregation across 24/7 and sessioned markets.
4. Normalize licenses for Software Impacts 100613 and the 2026 Bitcoin preprint.
5. Continue commit-pinned hidden-liquidity implementation search with explicit license/source lineage.
6. Collect point-in-time field/retention/licensing semantics for Bitcoin Volatility Futures.

## CAPABILITY LEDGER
Successfully used in this increment:
- Superpowers using-superpowers guidance
- Superpowers verification-before-completion guidance
- Exa Deep Research
- Firecrawl first-party source extraction
- GitHub authenticated repository read/search/fetch/write surfaces
- GitHub public-repository source/commit/license inspection

Blocked in this increment:
- Consensus: monthly quota exhausted until 2026-10-01
- Scite: monthly MCP quota exhausted until 2026-10-01

Exposed but not materially required after source convergence:
- Tavily
- Parallel Search
- DataBlue
- Google Drive/File Library fallback

No AEGIS production component, strategy, test, score, ranking or sibling workstream was modified.
