# S&P 500 reference contract

Read-only audit; no source mutation, network, tests, commits, or agents.

Local `s-and-p-500-companies/data/constituents.csv`: 53,607 bytes; 503 rows, 503 unique nonblank symbols, 500 unique CIKs. Latest `Date added`: 2026-10-06. Multiple share classes explain the additional symbols.

SHA-256: `a13dc3b5f1c1dafd36e8c700a82ba90bc06c434623dfb5780c516134cee1d48e`.

File commit: `2f083ae70907cca3b644a94744dde87f3199fc5b`, timestamp `2026-10-26T01:59:54Z`; this is repository provenance, not membership effective time. README/datapackage declare `ODC-PDDL-1.0`; scraper sources Wikipedia. No Wikipedia revision, retrieval receipt, or upstream licensing reconciliation is bundled.

Actual destination: `icarus_engine/data/research_context/`, not repository-root `data/research_context/`. Existing manifest labels constituents UNAVAILABLE because of an earlier catalog 404. Local availability supersedes that narrow statement; live freshness remains unverified.

Minimal API contract: add `reference_datasets` to `MarketContextStore.snapshot()` and the existing `/api/research/market-context` response. Preserve price `datasets`, `limit`, and `active_series=3`. Add a separate `ACTIVE_REFERENCE` catalog status/count; exclude it from quarantined counts.

Each reference contains `id=sp500-constituents`, `symbols` (503 strings), `symbol_count=503`, `company_count=500`, `sha256`, `source_url=https://en.wikipedia.org/wiki/List_of_S%26P_500_companies`, immutable GitHub `snapshot_url` at the above commit, `declared_license=ODC-PDDL-1.0`, `license_verification=UNVERIFIED`, `membership_as_of=null`, `freshness=UNVERIFIED`, `point_in_time=false`, `authority=REFERENCE_ONLY`, `execution_authorized=false`.

Copy exact CSV bytes; require bounded in-directory file, pinned hash, exact eight-column header, unique symbols, and expected count. Preserve ticker punctuation and string CIKs. Never interpret `Date added` as membership intervals. This is a current-list snapshot reference, unsuitable for historical universes, signals, qualification, or orders.

No patch: publication rights/as-of evidence remain unresolved; retain this implementable contract without activating the dataset.
