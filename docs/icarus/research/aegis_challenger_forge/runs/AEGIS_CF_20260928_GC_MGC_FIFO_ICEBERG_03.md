# AEGIS Challenger Forge — Incremental Collection Run

- run_id: AEGIS_CF_20260928_GC_MGC_FIFO_ICEBERG_03
- date: 2026-09-28
- mode: COLLECTION_ONLY
- parent_remote_head: 64bc8196df6e6674995f1fbb04c7b3e91960e787
- scope: incremental additions only; preserves all prior AEGIS and sibling checkpoints
- prohibited_actions_performed: none (no backtest, scoring, ranking, promotion, componentization, coding, execution, or production mutation)
- numeric_effort_control: unavailable; deepest safe analysis exposed by runtime used

## NEW SOURCES

### AEGIS-CF-CME-GC-MGC-MATCHALG-GCC-20260922
- source: CME Globex Product Reference Sheet, Global Command Center (GCC)
- source URL: https://www.cmegroup.com/globex/files/globex-product-reference-sheet.xls
- retrieval date: 2026-09-28
- workbook internal date: 2026-09-22
- provenance: first-party CME/GCC regularly updated product reference workbook; GCC Product Resources page states the workbook provides the Algorithm field for each instrument tradable on CME Globex
- workbook sheet: All Futures and Options
- workbook header: column "Algorithm*" is the matching-algorithm field; current rows inspected directly from the downloaded workbook
- observed current rows:
  - Gold Futures / Globex Symbol GC / Strategy Outright / Algorithm F
  - Gold Futures / Globex Symbol GC-GC / Strategy SP / Algorithm F
  - Micro Gold Futures / Globex Symbol MGC / Strategy Outright / Algorithm F
  - Micro Gold Futures / Globex Symbol MGC-MGC / Strategy SP / Algorithm F
- algorithm semantics: CME MDP 3.0 documentation defines MatchAlgorithm F as First In, First Out (FIFO)
- additional observed parameters:
  - GC outright minimum tick 0.1, value $10; FIFO Percent Allocation 1.0; group code GC
  - MGC outright minimum tick 0.1, value $1; FIFO Percent Allocation 1.0; group code GC
- applicability: standard outright GC and MGC plus their calendar-spread rows as explicitly identified; does not generalize to TAS/TAM/options/other Gold products
- observed contrast: Gold Futures TAS calendar-spread row GCT-GCT is separately shown with Algorithm K (Configurable), reinforcing the product/strategy-specific boundary
- access/licensing: public downloadable workbook; CME market-data and redistribution terms remain separate
- extraction method: live first-party workbook fetched in a disposable browser-research session and parsed read-only with xlrd; no workbook copy persisted to AEGIS

### AEGIS-CF-CME-MGC-SESSION-DOCSNAP-20260928
- source: CME Group Micro Gold Futures Contract Specs
- retrieval date: 2026-09-28
- provenance: first-party exchange product documentation
- core taxonomy: instrument-specific session/trading-day boundary provenance for MGC
- observed facts:
  - contract unit: 10 troy ounces
  - Product Code: CME Globex MGC; CME ClearPort MGC; Clearing MGC; TAS MGT
  - trading hours: Sunday-Friday 6:00 p.m.-5:00 p.m. ET (5:00 p.m.-4:00 p.m. CT)
  - 60-minute daily break beginning at 5:00 p.m. ET (4:00 p.m. CT)
  - minimum price fluctuation: 0.10 per troy ounce = $1.00
  - deliverable settlement method
- applicability: MGC-specific OHLC/session construction and range-volatility provenance
- novelty boundary: prior GC session corpus remains separate; MGC is now independently pinned rather than inherited from GC
- access/licensing: public CME specs; market-data rights remain separate
- source URL: https://www.cmegroup.com/markets/metals/precious/e-micro-gold.contractSpecs.html

### AEGIS-CF-ICEBERG-GH-TAYOR-v0.1.0-3651fdd044ed
- source: tayor/iceberg-detector
- source identity: GitHub commit 3651fdd044edfa814d65f637ce39f6bda2dbfb1a
- commit date: 2026-05-02
- package version: 0.1.0
- provenance: public commit-pinned implementation; PyPI/GitHub metadata; not an academic validation source
- license: MIT; LICENSE blob c405dd134ff239b56a9689a6ff99e6606c7295f7 verified
- pyproject blob: 0bce269fafe0508fc9c77fe2efde10c7b7787b2e
- core taxonomy: hidden/iceberg-order detection research toolkit for crypto order books; rule-based detector, Random Forest, LSTM/ensemble paths, order-flow/persistence/volume-clustering features, Cryptofeed and Tardis connectors
- required inputs: order-book/depth and trade-history streams; repository supports connector/data-normalization layers and synthetic/sample data utilities
- source-level observations at pinned commit:
  - src/iceberg_detector/models/rule_based.py exists
  - tests cover rule-based detection, Random Forest, LSTM, ensemble detection, connectors and feature engineering
  - repository contains Tardis and Cryptofeed data connectors and price-persistence/order-flow/volume-clustering feature modules
- applicability: BTC/crypto microstructure research; transfer to CME GC/MGC/NQ requires venue-specific event semantics and is not assumed
- unverified-claim boundary: README claims about accuracy, precision/recall, latency, throughput, production-readiness and supported exchange performance are NOT independently validated and are not treated as evidence
- quality grade: implementation corpus only; lower evidentiary weight than CME exchange docs or peer-reviewed/native iceberg studies

## NEW CORPUS IDS
- AEGIS-CF-CME-GC-MGC-MATCHALG-GCC-20260922
- AEGIS-CF-CME-MGC-SESSION-DOCSNAP-20260928
- AEGIS-CF-ICEBERG-GH-TAYOR-v0.1.0-3651fdd044ed

## DUPLICATES
- Generic supported-matching-algorithm documentation was already collected; this run adds the missing product-specific current GC/MGC rows from the actual GCC workbook.
- Historical Gold TAS FIFO/K-configurable notices are not used as substitutes for standard outright GC/MGC current state.
- Existing CME iceberg paper, ASX iceberg study and TMX iceberg guide remain separate evidence layers; the tayor repository is admitted only as an implementation corpus, not as new empirical validation.
- HMM/KNN/regime/Kalman/VWAP/volume-sweep/SMC-FVG/pivot-fractal/Renko-tick-volume/cointegration-stat-arb families remain excluded as known families.

## COVERAGE BY FACET
- Official documentation: current GC/MGC product-specific matching algorithms resolved from CME's own live workbook.
- Market microstructure/execution: standard outright GC and MGC now have first-party FIFO provenance; TAS remains explicitly separate.
- Gold: both GC and MGC execution/session provenance materially strengthened.
- GitHub/open source: one explicit-license, commit-pinned hidden-liquidity implementation added.
- BTC: iceberg implementation corpus is crypto-oriented but no performance/transfer inference is made.
- Pine/TradingView: no new source admitted in this increment.
- Academic/public quantitative research: no new paper required after first-party and implementation-source convergence.
- Volatility/session: MGC session metadata now closes the prior GC-only gap.
- Alternative data: no new feed admitted.

## SOURCE QUALITY/PROVENANCE
- Highest provenance: CME/GCC live product-reference workbook and CME MGC contract specifications.
- GCC workbook date was decoded from an actual Excel date cell (2026-09-22), not guessed from retrieval time.
- tayor/iceberg-detector is source-verifiable and MIT licensed but remains an implementation corpus with unverified README performance claims.
- Observed facts and implementation structure are separated from vendor/author performance claims.
- No source is scored, ranked, backtested, promoted, or componentized.

## ACCESS/Licensing LIMITS
- GCC workbook and CME specs are publicly accessible; this does not grant unrestricted redistribution of live/historical exchange data.
- The workbook itself was not persisted into AEGIS; only source identity, date, fields and extracted rows are recorded.
- tayor/iceberg-detector is MIT; dependencies such as Tardis.dev have separate commercial/data-access terms.
- Consensus was not retried because the same-day verified quota block lasts until 2026-10-01; blocked action: additional academic literature cross-check.
- Scite was not retried because the same-day verified MCP quota block lasts until 2026-10-01; blocked action: citation-graph/full-text cross-check.
- Temporary xlrd installation occurred only inside a disposable browser-research sandbox to parse the official XLS and did not alter the repository or AEGIS runtime.
- Numeric effort control is not exposed.

## COLLECTION GAPS
- Current CME Options Analytics product-list entitlement proving exact NQ/GC identifier coverage.
- Licensed CME MBO/trade-summary corpora for GC/MGC/NQ/MNQ showing PriorityID/display-refresh transitions.
- GC/MGC-specific empirical iceberg/replenishment evidence tied to current FIFO semantics.
- Independent validation or paper lineage for the tayor iceberg-detector implementation.
- Bitcoin Volatility Futures historical field/retention/licensing semantics.
- Primary research on venue-native versus common-clock volatility aggregation across BTC/NQ/Gold.

## NEXT COLLECTION TARGETS
1. Obtain current CME Options Analytics product mapping for NQ/GC without guessing around entitlement.
2. Search for product-specific GC/MGC MBO/display-quantity datasets or first-party examples that connect FIFO, display refresh and PriorityID.
3. Trace hidden-liquidity implementation candidates to papers/ground-truth datasets; preserve only license-clean commit-pinned implementations.
4. Collect Bitcoin Volatility Futures historical field schema, retention and redistribution terms.
5. Continue cross-market session/calendar normalization research for BTC/NQ/GC/MGC.

## CAPABILITY LEDGER
Successfully invoked this run:
- Superpowers using-superpowers guidance
- Superpowers verification-before-completion guidance
- Exa Deep Research
- Firecrawl scrape, live-browser interact and read-only workbook extraction
- GitHub authenticated repository read/search/fetch/write surfaces
- GitHub public-repository source/license/tree inspection
- native web retrieval for the CME GCC Product Resources page

Known unavailable and not falsely counted as used:
- Consensus: same-day quota state already established as exhausted until 2026-10-01
- Scite: same-day quota state already established as exhausted until 2026-10-01

Exposed but not materially required after first-party source resolution:
- Tavily
- Parallel Search
- DataBlue
- Google Drive/File Library fallback

No AEGIS production component, strategy, test, score, ranking, or sibling workstream was modified.
