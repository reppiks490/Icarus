# AI data access

Every AI unit working in `reppiks490/Icarus` must use the shared GitHub-native ICARUS evidence plane rather than account-local API-key knowledge.

## Do not search for plaintext provider keys

A chat not being able to *read* a provider API key is expected. GitHub Actions Secrets are injected into approved workflows at runtime and are not a shared plaintext credential store.

**Do not search `$ICARUS_HOME/.env`, local `.env` files, DAV task comments, Plant/operator notes, another ChatGPT account, or another agent workspace for a shared provider key. Do not wait for another AI to reveal one.**

The federation shares credentialed execution, collection status, and persisted evidence—not secret strings.

Before declaring provider access unavailable, read the mandatory cross-chat directive:

- `reppiks490/icarus-owner-actions:coordination/directives/GITHUB_NATIVE_DATA_ACCESS.md`

Then read the Engine credential/data authority:

- `reppiks490/Icarus-engine:AGENT_CREDENTIALS.md`
- `reppiks490/Icarus-engine:docs/agent-handoffs/GITHUB_NATIVE_CREDENTIALS.md`
- `reppiks490/Icarus-engine:config/credential_contract.json`
- `reppiks490/Icarus-engine:config/data_ingestion_manifest.json`
- `reppiks490/Icarus-engine:automation_intelligence/sentinel/data_health.json`

The ingestion manifest is the routing table. Consume its `evidence_paths` first. Core shared outputs include `automation_intelligence/provider_collection_v1/latest/` and `automation_intelligence/provider_collection_v1/research_context.json`. If fresh collection is required, use the established Engine GitHub Actions provider lanes instead of extracting a key.

## Plant/runtime control is a different secret plane

`ADMIN_TOKEN` / `ICARUS_ADMIN_TOKEN`, bridge webhook secrets, and machine-local broker/runtime credentials are privileged local Plant/bridge controls. They are **not** the GitHub-native provider credential plane. Legacy local bridge code may correctly load those from the operator's `.env` because the bridge runs on the operator machine.

A cloud worker that cannot read `ADMIN_TOKEN` must not conclude that provider data is unavailable. It should continue through the shared GitHub-native evidence plane. If the task genuinely requires a privileged Plant operation, report `LOCAL_RUNTIME_CAPABILITY_REQUIRED` rather than asking for or copying the token. **Live broker arming remains disabled.**

Read the authority sources above before making source-availability, freshness, entitlement, coverage, or downstream-consumption claims. The local provider workflow keeps `intrinio` as this repository's preferred-owner lane and defers other K1 providers to Icarus-engine unless the bounded failover rule authorizes takeover.

Never copy plaintext credentials between AI accounts. GitHub Actions Secrets are the sensitive provider-credential authority; redacted health/receipts and normalized persisted evidence are the data-access authority. A green wrapper is not proof of provider entitlement or successful collection.
