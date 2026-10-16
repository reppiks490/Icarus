# ICARUS GitHub-Native Data Federation

This repository participates in the shared ICARUS data plane owned across `reppiks490/Icarus` and `reppiks490/Icarus-engine`.

## Mandatory for all AI units

All AI units working in this repository must consult the Engine-side machine ledger and directives before making data-access claims:

- `reppiks490/Icarus-engine:config/data_ingestion_manifest.json`
- `reppiks490/Icarus-engine:docs/agent-handoffs/FEDERATED_DATA_COLLECTION.md`
- `reppiks490/Icarus-engine:docs/agent-handoffs/DATA_GAP_LEDGER.md`
- `reppiks490/Icarus-engine:automation_intelligence/sentinel/data_health.json`

The Engine repository is the canonical GitHub-native credential/data-health authority. This repository must not invent a competing secret vocabulary or infer access from a particular ChatGPT/Claude/Codex account.

## GitHub Actions credentials

Provider workflows consume GitHub Actions Secrets or Variables through canonical environment names with legacy-alias fallback. GitHub Actions Secrets are for sensitive credentials; Variables are for non-sensitive configuration only. Do not copy plaintext API keys into chat, source files, commits, artifacts, logs, or handoff documents.

Credential presence is not proof of provider validity or entitlement. Runtime receipts remain authoritative for authentication, plan denial, quota, collection and downstream-consumption status.

## Cross-repository provider ownership

The existing provider collector preserves one preferred repository per provider so the two repositories do not double-spend request budgets:

- `intrinio` preferred owner: `reppiks490/Icarus`.
- every other provider in the shared K1 catalog preferred owner: `reppiks490/Icarus-engine`.

A secondary repository may take over only under the collector's bounded failover rule after a fresh preferred-owner missing-credential or authentication failure. Otherwise it writes `STANDBY_PREFERRED_OWNER` and must not duplicate provider calls.

## Evidence consumption

This repository's consumers must use the source-qualified Engine evidence plane when relevant, including provider research context, native public research, CL lab data, Databento/depth context, SEC/EDGAR, official economic events, specialist evidence, MCP events, and the inter-repository peer packet.

Connector-only services remain account-specific capabilities. If the current AI unit lacks a connector, it records the capability blocker instead of assuming another unit's connector session is transferable.

The standing rule is the same for all AI units: close ICARUS-owned gaps when discovered; preserve explicit external/provider blockers; never relabel missing credentials, HTTP 401, plan 403/402, rate 429, missing licensing rights, or unavailable connector access as success.