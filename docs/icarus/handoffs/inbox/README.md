# ICARUS Loop Handoff Inbox

This directory is the landing zone for the remaining ICARUS/AEGIS/DAEDALUS/NEXUS/HELIOS loop handoffs before convergence.

## One file per source loop

Use:

`YYYY-MM-DD_<loop-name>_<source>.md`

Never overwrite another loop's handoff. Never fold two source loops into one file before convergence.

## Required metadata

Every handoff begins with:

```
SOURCE_LOOP=
SOURCE_CHAT_OR_WORKSTREAM=
PRODUCER=
CAPTURE_DATE=
PINNED_REPO_REVISION=
POLICY_VERSION=
EXECUTION_AUTHORIZED=false
```

Unknown values remain explicitly unknown.

## Import discipline

1. Preserve the raw handoff first.
2. Do not edit claims to make them agree with the current canonical registry.
3. Mark each claim during convergence as:
   - COMPATIBLE
   - DUPLICATE
   - DERIVED_DUPLICATE
   - REVISION_CONFLICT
   - CONFIG_CONFLICT
   - EVIDENCE_CONFLICT
   - STALE
   - UNVERIFIED
   - BLOCKED
4. Preserve failed/rejected attempts.
5. Do not reset the global attempt ledger.
6. Do not let a later loop silently increase execution authority.

See `../INBOX_PROTOCOL.md` for the full contract.
