# Advanced CSV Data Collector — historical loop handoff

SOURCE_LOOP=Advanced CSV Data Collector
PRODUCER=ChatGPT historical-loop migration
CAPTURE_DATE=2026-09-28
PINNED_REPO_REVISION=449aef107bb868d1f18ab7eddc2bf4c3398f783b
EXECUTION_AUTHORIZED=false
SENSITIVITY=PUBLIC_SAFE
CLASSIFICATION=COLLECTION_PIPELINE
SNAPSHOT_STATUS=ACTIVE_AT_MASTER_HANDOFF
OWNERSHIP=CSV acquisition/validation; preferred reconciliation sink reppiks490/icarus-csv-evidence-lab

## Mission
Collect, validate, hash, classify and preserve CSV/market-data corpora without silently changing downstream model/strategy state.

## Recovered evidence
- preferred evidence repo: reppiks490/icarus-csv-evidence-lab (private at handoff);
- related raw/historical repos: reppiks490/multi-level-csv and reppiks490/csv-data-multi-chart-type;
- one recovered run structurally validated six Cboe CSVs and produced SHA-256 identities;
- checked Drive destination was empty, so those validated inputs remained transient rather than falsely described as durable;
- required durable behavior: append-only manifest, immutable retrieval/version lineage, hashes, licensing/access status.

## Gaps
Not all historical CSVs were reconciled into one manifest. Historical collection without persistence is backfill-eligible only from evidence. Raw licensed data must not be copied into the public repo; prefer hashes, schemas and provenance pointers.

## Preservation boundary
Repository evidence outranks chat summaries. Historical test counts/hashes are historical evidence unless re-run on the current revision. No sibling system is merged or overwritten. No broker/order authority is granted. EXECUTION_AUTHORIZED=false.
