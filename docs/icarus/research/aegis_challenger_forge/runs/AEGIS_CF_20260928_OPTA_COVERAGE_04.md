# AEGIS Challenger Forge — Incremental Collection Run

- run_id: AEGIS_CF_20260928_OPTA_COVERAGE_04
- date: 2026-09-28
- mode: COLLECTION_ONLY
- parent_remote_head: 2aee52dfe5731ba9f264e4ad443f80b33f13a8b4
- prohibited_actions_performed: none (no backtest, scoring, ranking, promotion, componentization, coding, execution, or production mutation)
- numeric_effort_control: unavailable

## NEW SOURCES

### AEGIS-CF-CME-OPTA-PRODUCTLIST-20250801
- source: CME Options Analytics - Greeks and Implied Volatility - Product List
- publication date: 2025-08-01
- organization: CME Group
- provenance: first-party static support list
- source URL: https://cmegroupclientsite.atlassian.net/wiki/spaces/EPICSANDBOX/pages/871596033/Options+Analytics+-+Greeks+and+Implied+Volatility+-+Product+List
- core taxonomy: supported option-product mapping and pricing-model metadata for CME Options Analytics
- observed supported products relevant to AEGIS:
  - E-mini Nasdaq-100 | Equity | product code NQ | Bjerksund Stensland 1993 Approximation / Black-Scholes
  - Micro E-mini Nasdaq-100 | Equity | product code MNQ | Bjerksund Stensland 1993 Approximation / Black-Scholes
  - Gold | Metals | product code GC | Bjerksund Stensland 1993 Approximation
- required downstream query input: productCodes value matching the published product code; actual API response remains subject to client entitlement
- applicability: NQ/MNQ/GC implied-volatility/Greek surface collection
- unverified-claim boundary: support-list membership is observed; no statement about predictive value or strategy utility is admitted
- access/licensing: public documentation; API data access is entitlement/subscription controlled

### AEGIS-CF-CME-OPTA-FAQ-20250911
- source: CME Options Analytics - Greeks and Implied Volatility - FAQ
- updated: 2025-09-11
- organization: CME Group
- provenance: first-party API-service FAQ
- source URL: https://cmegroupclientsite.atlassian.net/wiki/spaces/EPICSANDBOX/pages/871628804/Options+Analytics+-+Greeks+and+Implied+Volatility+-+FAQ
- core taxonomy: snapshot cadence, market-quality gating, field precision, historical retention, delivery format and dataset exclusions
- observed facts:
  - API covers outright options only; User Defined Spreads are excluded
  - IV is based on mid price of top of book
  - data populate only when the strike has a two-sided market
  - REST API snapshots are five-minute cadence
  - REST delivery is JSON; historical CME DataMine files are CSV
  - REST API data are available for the current Sunday-to-Friday window
  - CME DataMine historical Options Analytics data are available back to 2020
  - option settlement, volume and open interest are not part of this Options Analytics API
- applicability: provenance/retention schema for NQ/MNQ/GC Options Analytics collection
- access/licensing: entitlement required for REST product access; historical DataMine orders require purchase/subscription and applicable license agreements

## NEW CORPUS IDS
- AEGIS-CF-CME-OPTA-PRODUCTLIST-20250801
- AEGIS-CF-CME-OPTA-FAQ-20250911

## DUPLICATES
- AEGIS-CF-CME-OPTA-REST-DOC-v20251030 already captures base URL/endpoints/message schema and remains the canonical REST specification identity.
- AEGIS-CF-CME-OPTVOL-GREEKS-DOCSNAP-20260928T1705Z remains the broader options-volatility documentation corpus.
- This run adds product membership and retention/access semantics only; no endpoint/schema duplication is admitted.
- Known AEGIS families remain excluded: OperationGoldenExecutioner, BTC MASTER, NQ Confluence, pivot/fractal, Renko/tick-volume, HMM/KNN, VWAP/volume-sweep, SMC/FVG, generic regime, Kalman and cointegration/stat-arb.

## COVERAGE BY FACET
- Official documentation: NQ, MNQ and GC Options Analytics support now directly proven by first-party product list.
- NQ: NQ and MNQ explicit support plus documented model family.
- Gold: GC explicit support plus documented model family.
- Volatility/options: snapshot cadence, two-sided-market gating, API retention and DataMine history now pinned.
- Alternative data: options Greeks/IV remain a distinct forward-looking derivatives-data family.
- Pine/academic/GitHub/microstructure: no new admission required in this narrow checkpoint.

## SOURCE QUALITY/PROVENANCE
- Both additions are first-party CME documentation.
- Public static product support is kept distinct from per-client entitlement returned by /products.
- Observed product codes/model labels/retention are separated from marketing or performance claims.
- No strategy evaluation or production use occurred.

## ACCESS/Licensing LIMITS
- Production API base requires OAuth Bearer authorization and entitlement; /products returns products available to that client.
- Static product-list support does not itself prove a specific account entitlement.
- DataMine historical access is purchase/subscription based and subject to CME license agreements.
- Consensus remains quota-blocked until 2026-10-01 and was not counted as used.
- Scite remains quota-blocked until 2026-10-01 and was not counted as used.
- Numeric effort control is not exposed.

## COLLECTION GAPS
- Exact DataMine dataset-level field schema/file naming for historical Options Analytics.
- Licensed CME MBO/trade-summary corpora for NQ/MNQ/GC/MGC.
- GC/MGC-specific empirical iceberg/display-refresh evidence under current FIFO rules.
- Independent validation lineage for hidden-liquidity implementations.
- Bitcoin Volatility Futures historical field/retention/licensing semantics.
- Cross-market venue-native versus common-clock volatility aggregation research.

## NEXT COLLECTION TARGETS
1. Pin the exact CME DataMine Options Analytics dataset identity, field schema and delivery filenames.
2. Collect MBO/display-quantity/PriorityID evidence for GC/MGC/NQ/MNQ.
3. Trace hidden-liquidity implementations to ground-truth papers/data.
4. Collect Bitcoin Volatility Futures historical field and licensing metadata.
5. Continue cross-market session-normalization research.

## CAPABILITY LEDGER
Successfully used in this continuation:
- Superpowers process/verification guidance
- Exa Deep Research / fetch
- Firecrawl source extraction and live browser
- GitHub authenticated read/write/verification surfaces

Known unavailable:
- Consensus monthly quota exhausted until 2026-10-01
- Scite monthly MCP quota exhausted until 2026-10-01

Not required after source convergence:
- Tavily, Parallel Search, DataBlue, Google Drive/File Library fallback

No AEGIS production component, strategy, score, test, ranking or sibling workstream was modified.
