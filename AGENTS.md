# ICARUS federation instructions for AI units

Every AI unit working in this repository must treat `reppiks490/Icarus` and `reppiks490/Icarus-engine` as one source-qualified research/evidence federation.

Before making claims about provider access, data freshness, market context, source coverage, research evidence, or blockers, read:

- `docs/AI_DATA_ACCESS.md`
- `GITHUB_NATIVE_DATA_FEDERATION.md`
- `reppiks490/Icarus-engine:config/data_ingestion_manifest.json`
- `reppiks490/Icarus-engine:config/federated_repo_evidence.json`
- `reppiks490/Icarus-engine:docs/agent-handoffs/FEDERATED_DATA_COLLECTION.md`
- `reppiks490/Icarus-engine:docs/agent-handoffs/DATA_GAP_LEDGER.md`
- current Engine `automation_intelligence/sentinel/data_health.json`

GitHub Actions Secrets/Variables are the credential authority. Never copy plaintext API keys between AI accounts, chats, repositories, logs, or artifacts. Credential presence alone is not proof of authentication, entitlement, collection, freshness, or downstream consumption.

Provider ownership remains bounded: this repository is the preferred owner for Intrinio; the Engine repository is the preferred owner for the other shared K1 providers. Preserve `STANDBY_PREFERRED_OWNER` and bounded failover behavior so the repositories do not duplicate provider requests.

All AI units must consume relevant cross-repository specialist, provider, macro, depth, filing, public-market, and coordination evidence. If a source or repository is inaccessible, record the blocker explicitly rather than silently omitting it. Zero known ICARUS-owned gaps is the completion condition; external provider/account/licensing blockers stay explicit.
