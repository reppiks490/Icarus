21/50 — SEC ingestion (read-only inspection; no tests/network/source edits).

Trace: Engine `cl_lab/feeds/sec_edgar.py:100,118,143,230` fetches submissions/companyfacts, joins facts to accession acceptance timestamps, and caches gzip CSVs. `.github/workflows/sec-edgar-data.yml:90–122` caches rows and commits bounded manifest/context JSON. `icarus_engine/interrepo_bridge.py:81` exports SEC context; Icarus `icarus_engine/brain_sync.py:71` consumes it as collection-only historical evidence. Separate Icarus `market_sources.py:337` collects SEC into SQLite (`:76,136`), exposed through server records API (`server.py:2253`) and Financial/data Companies (`sources-ui.js:145–156`).

Confirmed gaps:

- **Stale revenue masquerades as latest:** Engine's concept allowlist (`sec_edgar.py:24–29`) omits `RevenueFromContractWithCustomerExcludingAssessedTax` (supported by Icarus's separate collector, `market_sources.py:359`). Committed context lists AAPL's latest `Revenues` as September 2018 and `SalesRevenueNet` as June 2018 (`sec_edgar_research_context.json:87–99`), while other facts reach June 2026. These stale revenue values propagate into Brain's ticker summary.
- **Health falsely passes collection failure:** Engine `tools/data_sentinel.py:166–169` checks only top-level `error`. Collector all-ticker failures write `status:error` with errors nested under tickers (`sec_edgar.py:269,318–333`); sentinel consequently reports OK, including zero filings or missing manifest.
- **UI lane discards available causal timestamps:** Icarus `market_sources.py:353–354` omits `acceptanceDateTime` from saved filing entries; facts receive period-end observation times (`:370`) despite submissions providing acceptance timestamps. Companies users cannot inspect exact availability through this lane.
