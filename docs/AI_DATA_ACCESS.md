# AI data access

Every AI unit working in `reppiks490/Icarus` must use the shared GitHub-native ICARUS evidence plane rather than account-local API-key knowledge.

Canonical cross-repository state lives in `reppiks490/Icarus-engine`:

- `config/data_ingestion_manifest.json`
- `docs/agent-handoffs/FEDERATED_DATA_COLLECTION.md`
- `docs/agent-handoffs/DATA_GAP_LEDGER.md`
- `automation_intelligence/sentinel/data_health.json`

Read those before making source-availability, freshness, entitlement, coverage, or downstream-consumption claims. The local provider workflow keeps `intrinio` as this repository's preferred-owner lane and defers other K1 providers to Icarus-engine unless the bounded failover rule authorizes takeover.

Never copy plaintext credentials between AI accounts. GitHub Actions Secrets/Variables are the credential authority; runtime receipts are the data-access authority.
