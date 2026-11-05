# 24 — Financial news integration

Read-only inspection; no downloads or tests. The three repositories appear in `github-public-branch-heads.json` (lines 6, 159, 182); inventory proves pinned repository identities, not corpus possession or usage rights. No named adapter references were found in the inspected Icarus/Engine source trees.

The missing integration is a historical-news intake/replay adapter with publisher URL, stable article/revision IDs, timezone-qualified publication time, first-known availability, symbol/asset mapping, content checksum, duplicate policy, and a corpus receipt recording dataset revision, files, row counts, date coverage, and permitted retention/use.

Existing consumers already provide useful contracts: both `icarus_engine/market_sources.py` implementations collect official Fed/BEA RSS; Engine lines 122–158 preserve first retrieval and derive advisory events. `advisory.py:285,347–407` requires allowlisted provenance and dated text and defaults to 35-day freshness. FNSPID's historical records need replay-time handling; ingestion today must not make them fresh.

Reuse `starred-forked-repository-review-20261026.md:18–20` for the rights catalog. Outstanding evidence: reconciled FNSPID dataset/publisher permissions; a reviewed dataset/license/schema snapshot for `virattt/financial-datasets`; source-specific delivery and permitted-use terms for each Sovai link. Engine `config/data_ingestion_manifest.json:53` records Financial Datasets as interactive-only/evidence-only, not a durable corpus feed. Primary upstream license/content verification remains unperformed locally.
