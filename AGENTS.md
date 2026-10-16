# ICARUS federation instructions for AI units

Every AI unit working in this repository must treat `reppiks490/Icarus` and `reppiks490/Icarus-engine` as one source-qualified research/evidence federation. There is **no model-specific task ownership**: Claude, ChatGPT, Codex, Grok, Atlas, local agents, and future workers coordinate by declared work/reservations and evidence, not permanent model gates.

## Mandatory many-chat coordination

Before substantial work, read the canonical cooperation bus in `reppiks490/icarus-owner-actions`:

- `coordination/START_HERE.md`
- `coordination/ACTIVE.md`
- `coordination/collisions.json`
- applicable files under `coordination/directives/`

Create or resume a unique coordination session. Publish a `PLAN` or `CLAIM` note before modifying shared code, workflows, UI, data contracts, or other reserved paths. Publish `WAITING` while CI/review/provider/dependency work is pending, `UPDATE` when scope changes, `HANDOFF` when another chat can use or take over a subproblem, and `COMPLETE` only with fresh verification evidence. If another session reserves an overlapping path, choose another boundary or explicitly cooperate; do not silently overwrite it.

Claude is currently inactive by owner direction. Its unfinished work is reclaimable under the central Claude-reclamation directive after a takeover/cooperation note. Absence is not completion and no worker should wait for model-specific authorization.

## Shared data/evidence truth

Before making claims about provider access, data freshness, market context, source coverage, research evidence, or blockers, read:

- `docs/AI_DATA_ACCESS.md`
- `GITHUB_NATIVE_DATA_FEDERATION.md`
- `reppiks490/Icarus-engine:config/data_ingestion_manifest.json`
- `reppiks490/Icarus-engine:config/federated_repo_evidence.json`
- `reppiks490/Icarus-engine:docs/agent-handoffs/FEDERATED_DATA_COLLECTION.md`
- `reppiks490/Icarus-engine:docs/agent-handoffs/DATA_GAP_LEDGER.md`
- current Engine `automation_intelligence/sentinel/data_health.json`

GitHub Actions Secrets/Variables are the credential authority. Never copy plaintext API keys between AI accounts, chats, repositories, logs, or artifacts. Credential presence alone is not proof of authentication, entitlement, collection, freshness, or downstream consumption. Variables are for non-sensitive configuration; secrets remain in GitHub Actions Secrets.

Provider ownership remains bounded: this repository is the preferred owner for Intrinio; the Engine repository is the preferred owner for the other shared K1 providers. Preserve `STANDBY_PREFERRED_OWNER` and bounded failover behavior so the repositories do not duplicate provider requests.

All AI units must consume relevant cross-repository specialist, provider, macro, depth, filing, public-market, and coordination evidence. If a source or repository is inaccessible, record the blocker explicitly rather than silently omitting it. Zero known ICARUS-owned gaps is the completion condition; external provider/account/licensing blockers stay explicit.

## Execution boundary

**Live broker arming is disabled** by current owner direction. Research, replay, paper/shadow execution, adapters, validation, and UI may be built and tested, but do not arm live broker execution, bypass execution gates, or reinterpret paper connectivity as live authorization.

A slow CI job is not a reason to go silent. Record the `WAITING` state in the central bus and continue useful non-conflicting work where possible.
