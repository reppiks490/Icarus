# ICARUS External Data Fabric — Canonical Orchestration

This directory documents the canonical `reppiks490/Icarus` side of the external-provider data fabric.

## Authority boundary

`Icarus-engine` owns provider adapters, normalization, point-in-time semantics, entitlement probing, Bronze/Silver storage contracts, and checkpoint logic. Canonical `Icarus` owns secret-bearing GitHub Actions orchestration and consumes only validated research artifacts.

The fabric has **RESEARCH authority only**. It grants no broker, order-routing, or production-execution authority.

## Credentials

Workflows read repository secrets only at runtime:

- `INTRINIO_API_KEY`
- `UNUSUAL_WHALES_API_TOKEN`

A missing secret is a clean `unconfigured` provider state, not a workflow crash. Secrets are passed as environment variables and are never embedded in command lines, cache keys, manifests, artifact names, or committed files.

`SEC_USER_AGENT` is intentionally outside this rollout and remains deferred.

## Storage

- Bronze: exact source response bytes, content-addressed and compressed.
- Silver: normalized point-in-time records in Parquet when available, deterministic gzipped JSONL fallback otherwise.
- Gold: compact coverage/health summaries only.
- Checkpoints: resumable pagination/backfill state.

Raw/licensed provider payloads never enter git history. GitHub Actions cache provides continuity between runs; bounded artifacts provide short-retention export/recovery surfaces.

## Workflows

- `external-provider-entitlement.yml`: probes every encoded Intrinio/UW endpoint/family and records explicit access classes.
- `external-provider-backfill.yml`: manual, budget-capped historical acquisition. UW full-tape is an explicit opt-in because daily files can be very large.
- `external-provider-incremental.yml`: hourly bounded refresh using the latest entitlement/checkpoint state.
- `external-provider-stream-capture.yml`: bounded UW WebSocket capture once the engine stream runner is pinned and validated.

The workflows check out a **pinned `Icarus-engine` revision** in a separate path. Updating the producer revision requires updating the pin and regenerating the cross-repository handoff contract.
