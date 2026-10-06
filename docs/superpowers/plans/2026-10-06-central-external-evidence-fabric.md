# Central External Evidence Fabric Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:test-driven-development` for each behavioral task, `superpowers:executing-plans` or `superpowers:subagent-driven-development` for execution, and `superpowers:verification-before-completion` before claiming completion. Track work with the checkbox steps below.

**Goal:** Turn the approved ICARUS provider design into a central, continuously refreshable, point-in-time external evidence fabric in `reppiks490/Icarus` without creating a second trading engine, duplicating already-running vendor collectors, leaking secrets/licensed payloads, or granting any external source execution authority.

**Architecture:** Providers terminate at the existing L1 evidence/provenance boundary defined by `coordination/ARCHITECTURE_CAPABILITY_FABRIC.md`. The central pipeline is `provider/manifest bridge -> exact raw artifact capture -> temporal normalization -> canonical evidence envelope -> feature factory/research consumers -> regime/FVE/ICARUS research surfaces`. Raw bytes remain off Git in a content-addressed local/Actions cache and are catalogued by SHA-256. Canonical observations are append-only and point-in-time; vendor revisions create new lineage rather than overwriting old evidence. Existing `reppiks490/Icarus-engine` collectors for FMP/EODHD/Tiingo and Databento corpus manifests are consumed as compact manifest bridges instead of triggering duplicate paid requests.

**Tech Stack:** Python 3.10+ standard library for the central substrate (`dataclasses`, `typing`, `urllib`, `sqlite3`, `hashlib`, `gzip`, `json`, `pathlib`, `zoneinfo`), pytest, GitHub Actions, existing ICARUS coordination/control contracts. Provider-specific optional dependencies may be added only when unavoidable and must not become core runtime dependencies.

**Approved source scope:**
- Databento: MBO, MBP-10, TBBO, trades, statistics (bridge existing corpus/manifests; do not duplicate licensed raw rows).
- Existing external fabric: FMP, EODHD, Tiingo (bridge `reppiks490/Icarus-engine` compact manifests; do not duplicate the collector by default).
- Unusual Whales: options/flow, dark-pool/equity-flow surfaces, and CME/futures-related surfaces only where the account/API actually exposes them.
- Intrinio: trial/entitlement-aware real-time/fair-value, tick/equity, fundamentals, historical equity, and historical/options surfaces that the current account actually permits.
- SEC/EDGAR: 8-K, 10-Q, 10-K, Form 4, Schedule 13D/13G, and 13F capability, **dormant in this phase** until the owner configures the required SEC User-Agent and explicitly enables collection.
- Federal/public macro: NY Fed SOFR/EFFR/repo, U.S. Treasury auctions/supply/rates, CFTC TFF positioning, EIA energy data, FRED/ALFRED series and vintages.
- Quiver: export/file intake first, API collection only if an explicit credential/entitlement is present.
- Tick Stream: delayed tick surfaces with latency/delay labeling; never represent delayed data as real-time.
- Crypto venues: Bybit, Deribit, Binance, Kraken, Coinbase, preserving venue identity and only claiming order-book/funding/open-interest/liquidation/basis fields when the selected endpoint actually provides them.
- Entitlement-gated future lanes: IQFeed, Rithmic, CQG are represented in the registry now but remain capability-disabled until lawful credentials/entitlements and a supported access path exist.

## Global Invariants

1. `execution_authorized=false` and `production_decision_authorized=false` are immutable for this fabric.
2. Provider availability, data validity, estimator validity, and trading authority are separate states.
3. Preserve `source_event_time`, `source_publication_time`, `source_available_at`, `retrieved_at`, and `ingested_at`; never substitute retrieval time for event/publication time.
4. Preserve revision/vintage identifiers where the source exposes them. ALFRED vintages and vendor corrections are first-class lineage.
5. Preserve the chain `SOURCE_ID -> RAW_ARTIFACT_HASH -> OBSERVATION_ID -> TRANSFORM_ID -> EVIDENCE_ID -> CLAIM_ID -> DECISION_CONTEXT_ID` where downstream stages create the later IDs.
6. Exact raw bytes are hashed before parsing. Canonical rows have an independent canonical SHA-256.
7. Exact duplicates may collapse idempotently; incompatible revisions or same-time source disagreements must remain distinct and must never be silently averaged/overwritten.
8. Secrets are env-only. URLs, exceptions, manifests, logs, test snapshots, and committed artifacts must redact secret query/header values.
9. No live-network unit test. Provider tests use fixtures/fake transports; controlled canaries happen only after the full mocked suite is green.
10. Licensed/raw vendor payloads never enter Git. Add `corpus/external/` and local provider cache paths to `.gitignore` before any collector can write there.
11. Existing `Icarus-engine` FMP/EODHD/Tiingo and Databento collection remains authoritative for those raw lanes unless a later migration explicitly replaces it. Central ICARUS consumes their compact manifests rather than paying twice.
12. SEC is fail-closed: with `SEC_USER_AGENT` absent or SEC explicitly disabled, no SEC HTTP request may be constructed or sent. This plan does not activate SEC collection.
13. Capability declarations are static; health/entitlement/freshness are dynamic. A provider can be capable but unavailable, unconfigured, plan-limited, stale, degraded, or disabled.
14. No source may be promoted from research evidence directly into a live trade command. Existing L4/L5 strategy/execution ownership is unchanged.

---

### Task 1: Lock the existing capability-fabric contract and provider inventory

**Files:**
- Modify `coordination/manifests/provider-registry.yaml`
- Create `coordination/schemas/external-evidence.schema.json`
- Create `tests_engine/test_external_data_contracts.py`

**Interfaces:** static provider registry + JSON-schema-compatible canonical evidence contract.

- [ ] Write failing tests requiring unique provider IDs, explicit domain/role/source class, `direct_execution_authority: false`, capability-vs-health separation, credential names without secret values, cadence class, licensing/raw-retention policy, and every approved source listed above.
- [ ] Write failing schema tests requiring source/provider identity, instrument/venue where applicable, all point-in-time timestamps, revision/vintage fields, raw and canonical hashes, ingest batch ID, quality flags, authority fields, and lineage parents.
- [ ] Add negative tests proving a record with `execution_authorized=true`, missing provider/source identity, or missing provenance hashes is rejected.
- [ ] Run `python -m pytest -q tests_engine/test_external_data_contracts.py` and verify RED.
- [ ] Expand the existing v1 registry additively; do not delete currently registered provider/design/research entries.
- [ ] Add the external evidence schema with authority hard-coded/enum-constrained to false.
- [ ] Re-run the focused test and verify GREEN.
- [ ] Commit `docs+test: lock external evidence provider contract`.

### Task 2: Build canonical contracts, deterministic identity, and point-in-time time model

**Files:**
- Create `icarus_engine/external_data/__init__.py`
- Create `icarus_engine/external_data/contracts.py`
- Create `icarus_engine/external_data/identity.py`
- Create `tests_engine/test_external_data_identity.py`

**Interfaces:**
- `SourceArtifact`
- `EvidenceEnvelope`
- `ProviderDescriptor`
- `ProviderHealth`
- `canonical_json_bytes(value) -> bytes`
- `raw_sha256(payload: bytes) -> str`
- `canonical_sha256(record) -> str`
- `evidence_id(record) -> str`

- [ ] Write failing tests for deterministic canonical JSON, stable hashes independent of dict insertion order, timestamp normalization to aware UTC, separate event/publication/available/retrieval/ingest times, revision-sensitive evidence IDs, and exact-duplicate identity.
- [ ] Add tests proving a vendor revision produces a new evidence ID while retaining the prior evidence ID as a lineage parent.
- [ ] Add tests that unknown event time remains explicit `None`/unknown rather than being replaced by retrieval time.
- [ ] Run `python -m pytest -q tests_engine/test_external_data_identity.py` and verify RED.
- [ ] Implement the minimal immutable dataclasses/helpers.
- [ ] Re-run focused tests and verify GREEN.
- [ ] Commit `feat: add point-in-time external evidence contracts`.

### Task 3: Implement append-only raw event lake and idempotent canonical catalogue

**Files:**
- Modify `.gitignore`
- Create `icarus_engine/external_data/storage.py`
- Create `tests_engine/test_external_data_storage.py`

**Storage layout:**
- Raw: `corpus/external/raw/<provider>/<dataset>/<sha256>.payload[.gz]`
- Catalogue: `corpus/external/catalog.sqlite3`
- Compact status only may be committed elsewhere; raw payloads/catalogue never are.

**Interfaces:**
- `RawArtifactStore.put(provider, dataset, payload, metadata) -> RawArtifactRef`
- `EvidenceCatalog.upsert(envelope) -> UpsertResult`
- `EvidenceCatalog.revisions(source_id, observation_key) -> list[EvidenceEnvelope]`
- `EvidenceCatalog.query_as_of(cutoff, ...) -> list[EvidenceEnvelope]`

- [ ] First add `corpus/external/` and `.external_data_cache/` to `.gitignore`.
- [ ] Write failing tests for content-addressed raw storage, atomic write/rename, duplicate raw suppression, SQLite uniqueness, append-only revisions, as-of queries, crash/retry idempotency, and no overwrite of incompatible revisions.
- [ ] Add a reconciliation test: exact same evidence collapses as duplicate; different canonical hash for the same source key is stored as a new revision and flagged `REVISION`/`CONFLICT`, never averaged.
- [ ] Verify RED with `python -m pytest -q tests_engine/test_external_data_storage.py`.
- [ ] Implement minimal standard-library stores with transactions and unique constraints.
- [ ] Verify GREEN and confirm `git status --ignored` shows the storage root ignored.
- [ ] Commit `feat: add append-only external evidence lake`.

### Task 4: Add secret-safe HTTP transport, budgets, retries, and deterministic fake transport

**Files:**
- Create `icarus_engine/external_data/transport.py`
- Create `icarus_engine/external_data/redaction.py`
- Create `tests_engine/test_external_data_transport.py`

**Interfaces:**
- `HttpRequest`
- `HttpResponse`
- `Transport.request(request) -> HttpResponse`
- `UrllibTransport`
- `FakeTransport`
- `RateBudget`
- `redact_url(url, secret_keys) -> str`

- [ ] Write failing tests for timeout, bounded retry on 429/5xx, no retry on terminal 4xx unless provider policy says otherwise, `Retry-After`, per-provider call budget, deterministic user-agent injection, and byte-preserving responses.
- [ ] Add leak tests that place sentinel secrets in query params, headers, and raised exceptions and assert the sentinel never appears in log/error/manifest strings.
- [ ] Add fake-transport call-capture tests so all provider parsers can be tested without sockets.
- [ ] Verify RED, implement minimal transport, verify GREEN.
- [ ] Commit `feat: add bounded secret-safe external transport`.

### Task 5: Provider registry and orchestration pipeline

**Files:**
- Create `icarus_engine/external_data/registry.py`
- Create `icarus_engine/external_data/pipeline.py`
- Create `icarus_engine/external_data/normalization.py`
- Create `tests_engine/test_external_data_pipeline.py`

**Interfaces:**
- `ProviderAdapter` protocol: `descriptor`, `collect(ctx)`, `normalize(batch, ctx)`
- `ProviderRegistry.register(adapter)` / `get(provider_id)` / `capabilities()`
- `IngestPipeline.run_provider(provider_id, now, force=False) -> ProviderRunReceipt`
- `IngestPipeline.run_due(now) -> list[ProviderRunReceipt]`

- [ ] Write failing tests for registry collisions, disabled/unconfigured/plan-limited states, per-provider isolation, deterministic run IDs, raw-before-normalize ordering, canonical upsert, failed normalization retaining the raw artifact, stale-feed detection, and immutable authority false.
- [ ] Add test proving one provider failure does not erase successful independent provider evidence.
- [ ] Add cross-provider disagreement test proving independent sources remain separate observations with a conflict edge rather than an arithmetic average.
- [ ] Implement the minimal registry/pipeline.
- [ ] Verify focused GREEN.
- [ ] Commit `feat: add provider registry and evidence ingestion pipeline`.

### Task 6: Bridge already-running Icarus-engine data instead of duplicating vendor calls

**Files:**
- Create `icarus_engine/external_data/providers/icarus_engine_manifest.py`
- Create `tests_engine/test_external_data_icarus_engine_bridge.py`

**Inputs:**
- `reppiks490/Icarus-engine/automation_intelligence/cl_lab/external_data_fabric.json` (FMP/EODHD/Tiingo compact derived manifest)
- Databento compact corpus/depth manifests already produced by Icarus-engine workflows.

- [ ] Write fixture-driven failing tests that normalize the existing external-data manifest while preserving source repository/ref/fetched time and research-only authority.
- [ ] Add tests that bridge records reference upstream raw/cache hashes when exposed but never pretend the compact manifest is independent raw market evidence.
- [ ] Add Databento tests covering MBO, MBP-10, TBBO, trades, and statistics manifest capabilities without copying licensed raw rows.
- [ ] Add a network-call assertion proving the bridge never calls FMP/EODHD/Tiingo/Databento vendor endpoints itself.
- [ ] Implement read-only manifest adapters and verify GREEN.
- [ ] Commit `feat: bridge existing Icarus-engine data fabric`.

### Task 7: Public macro provider adapters — NY Fed, Treasury, CFTC, EIA, FRED/ALFRED

**Files:**
- Create `icarus_engine/external_data/providers/nyfed.py`
- Create `icarus_engine/external_data/providers/treasury.py`
- Create `icarus_engine/external_data/providers/cftc.py`
- Create `icarus_engine/external_data/providers/eia.py`
- Create `icarus_engine/external_data/providers/fred_alfred.py`
- Create fixtures under `tests_engine/fixtures/external_data/`
- Create `tests_engine/test_external_data_public_macro.py`

- [ ] For each provider, capture small legally redistributable/synthetic fixture shapes only; do not commit bulk source datasets.
- [ ] Write failing parser tests for NY Fed SOFR/EFFR/repo, Treasury auctions/supply/rates, CFTC TFF reports, EIA energy series, FRED observations, and ALFRED vintage/revision dates.
- [ ] Add point-in-time tests proving ALFRED vintage availability prevents future-revision leakage into historical replay.
- [ ] Add unit/scale tests so rates, percentages, dates, and quantities cannot silently change units.
- [ ] Add source-specific failure tests for malformed rows, missing fields, stale releases, and changed schemas.
- [ ] Implement adapters through the shared transport/pipeline only.
- [ ] Verify `python -m pytest -q tests_engine/test_external_data_public_macro.py` is GREEN.
- [ ] Commit `feat: add point-in-time public macro adapters`.

### Task 8: Vendor/alternative adapters — Intrinio, Unusual Whales, Quiver, Tick Stream

**Files:**
- Create `icarus_engine/external_data/providers/intrinio.py`
- Create `icarus_engine/external_data/providers/unusual_whales.py`
- Create `icarus_engine/external_data/providers/quiver.py`
- Create `icarus_engine/external_data/providers/tick_stream.py`
- Create `tests_engine/test_external_data_vendor_adapters.py`

**Credential contract:** `INTRINIO_API_KEY`, `UNUSUAL_WHALES_API_KEY` (or the exact existing secret name if repository conventions already define one), Quiver credential only when API mode is used, Tick Stream credential only if required. Never rename an existing configured secret merely to match this plan.

- [ ] Write failing Intrinio tests for entitlement discovery/classification and every approved surface that can be represented by fixtures: real-time/fair-value, ticks/equities, fundamentals, historical equities, historical/options. Plan-limited responses must become `PLAN_LIMITED`, not generic success/error.
- [ ] Write failing Unusual Whales tests for options/flow, dark-pool/equity-flow, and CME/futures-related surfaces actually returned by fixtures. Never synthesize unavailable depth/order-flow fields.
- [ ] Write Quiver file/export ingestion tests first; API mode remains independently capability-gated.
- [ ] Write Tick Stream tests requiring an explicit delay/latency classification so delayed ticks cannot be presented as live.
- [ ] Add budget, pagination, deduplication, and secret-redaction tests for all four adapters.
- [ ] Implement minimal adapters and verify GREEN.
- [ ] Commit `feat: add entitlement-aware vendor adapters`.

### Task 9: SEC/EDGAR adapter skeleton — compile and test, but remain dormant

**Files:**
- Create `icarus_engine/external_data/providers/sec_edgar.py`
- Create `tests_engine/test_external_data_sec_edgar.py`

**Capability scope:** 8-K, 10-Q, 10-K, Form 4, Schedule 13D/13G, 13F, filing metadata, accession identity, XBRL facts where applicable.

- [ ] Write failing tests for form classification, accession-number identity, filing/amendment lineage, issuer/CIK identity, filing/event/availability times, and XBRL fact normalization using local fixtures.
- [ ] Write the critical fail-closed test: with `SEC_ENABLED` false/unset or `SEC_USER_AGENT` absent, adapter status is `DISABLED`/`CONFIGURATION_BLOCKED` and `FakeTransport.calls == []`.
- [ ] Add a test that configuration objects never infer/fabricate a User-Agent and never fall back to the general ICARUS HTTP User-Agent.
- [ ] Implement parsing/configuration skeleton only. Do **not** add SEC secrets/settings to a live workflow in this phase.
- [ ] Verify focused GREEN.
- [ ] Commit `feat: stage dormant SEC evidence adapter`.

### Task 10: Crypto venue adapters with strict field truthfulness

**Files:**
- Create `icarus_engine/external_data/providers/bybit.py`
- Create `icarus_engine/external_data/providers/deribit.py`
- Create `icarus_engine/external_data/providers/binance.py`
- Create `icarus_engine/external_data/providers/kraken.py`
- Create `icarus_engine/external_data/providers/coinbase.py`
- Create `tests_engine/test_external_data_crypto_venues.py`

- [ ] Write fixtures/tests for venue-specific trades/quotes/books/funding/OI/derivatives only where each selected endpoint exposes them.
- [ ] Add negative assertions that missing liquidation, basis, funding, depth, or OI fields remain absent/unknown rather than fabricated from price/volume.
- [ ] Preserve instrument type, venue, contract/spot distinction, source timestamp, sequence/update ID when available, and retrieval time.
- [ ] Add cross-venue divergence evidence tests that compute comparisons downstream while retaining original venue observations.
- [ ] Implement adapters and verify GREEN.
- [ ] Commit `feat: add truthful multi-venue crypto evidence adapters`.

### Task 11: Register entitlement-gated IQFeed/Rithmic/CQG lanes without pretending they are active

**Files:**
- Create `icarus_engine/external_data/providers/entitlement_stubs.py`
- Modify `coordination/manifests/provider-registry.yaml`
- Extend `tests_engine/test_external_data_contracts.py`

- [ ] Write tests requiring these providers to appear in capability inventory with `UNCONFIGURED`/`ENTITLEMENT_REQUIRED` health and zero network calls.
- [ ] Ensure their presence improves completeness of the architecture but contributes zero evidence until lawful access is configured.
- [ ] Implement stubs and verify GREEN.
- [ ] Commit `feat: register future entitlement-gated feeds`.

### Task 12: Temporal feature factory and research-only handoff

**Files:**
- Create `icarus_engine/external_data/features.py`
- Create `icarus_engine/external_data/conflicts.py`
- Create `tests_engine/test_external_data_features.py`

**Interfaces:**
- `build_features(as_of, evidence, feature_specs) -> FeatureBatch`
- `detect_conflicts(evidence) -> list[ConflictEdge]`

- [ ] Write tests for as-of cutoff, no future leakage, source independence count, stale-evidence flags, cross-provider conflict preservation, revision selection by `available_at`, and deterministic replay.
- [ ] Add representative features required by the approved architecture: rate/liquidity regime context, Treasury supply/auction context, positioning changes, energy shocks, filing/event flags, cross-provider price divergence, venue divergence, and flow/activity features only when directly supported.
- [ ] Require provenance links from every feature back to exact evidence IDs and raw hashes.
- [ ] Do not connect the feature factory directly to order placement or execution authorization.
- [ ] Verify GREEN and commit `feat: add point-in-time external feature factory`.

### Task 13: Continuous GitHub Actions orchestration with due-provider dispatch and backfill

**Files:**
- Create `icarus_engine/external_data/cli.py`
- Create `.github/workflows/external-evidence-fabric.yml`
- Create `tests_engine/test_external_data_workflow_contract.py`
- Create `coordination/manifests/external-data-runtime.example.json`

**Behavior:** one frequent scheduler invokes a deterministic dispatcher; registry cadence decides which providers are due. This avoids one workflow per source and supports catch-up/backfill after temporary failure.

- [ ] Write workflow-contract tests for `workflow_dispatch`, scheduled execution, Python setup, focused tests before collection, `contents: read` by default unless compact status commit is explicitly required, Actions cache for `corpus/external/`, concurrency with `cancel-in-progress: false`, env-only secrets, and no SEC configuration/secret in this phase.
- [ ] Add scheduler tests for per-provider cadence, missed-run catch-up, bounded backfill, duplicate slot suppression, provider budget exhaustion, and stale/failed receipt classification.
- [ ] Add a historical-backfill contract: after a connector/credential outage, the next healthy run fills missing due windows when the source supports historical retrieval without rewriting prior evidence.
- [ ] Ensure FMP/EODHD/Tiingo/Databento remain bridge-only unless an explicit migration flag is introduced later.
- [ ] Implement CLI + workflow. Generated compact status must contain counts/hashes/health only, not raw/licensed payloads or secret values.
- [ ] Verify workflow syntax and focused tests GREEN.
- [ ] Commit `automation: add continuous external evidence fabric`.

### Task 14: Surface provider/evidence health in the existing ICARUS Overview without changing trading semantics

**Files:** exact backend/dashboard files must be identified from the current `main` implementation of `/api/overview/command-center` before editing; modify only those files and their existing command-center tests.

- [ ] First inspect the merged PR #325 implementation and identify the canonical command-center backend, provider-card builder, and tests. Do not guess file paths.
- [ ] Write failing tests requiring central-provider health, last successful ingest, freshness, capability/entitlement state, evidence counts, conflict count, and backfill debt while suppressing secret/raw payload content.
- [ ] Preserve existing FMP/Tiingo/EODHD/Databento observability and add new providers additively.
- [ ] Ensure UI labels distinguish `CONFIGURED`, `UNCONFIGURED`, `DISABLED`, `PLAN_LIMITED`, `STALE`, `DEGRADED`, and `OK` rather than collapsing all non-OK states.
- [ ] Keep all gauges diagnostic/research-only and fail closed to insufficient evidence.
- [ ] Verify command-center backend + dashboard contract tests GREEN.
- [ ] Commit `ui: expose external evidence fabric health`.

### Task 15: Full verification, canary rollout, and merge gate

- [ ] Run every focused external-data test file individually and require zero failures.
- [ ] Run `python -m pytest -q` from `reppiks490/Icarus` and require zero new failures; record any demonstrably pre-existing unrelated failure separately instead of weakening tests.
- [ ] Search the diff/artifacts for credential names and sentinel values; verify no secret values, bearer/basic auth, API tokens, or raw licensed payloads are committed.
- [ ] Verify `corpus/external/` and `.external_data_cache/` are ignored.
- [ ] Verify every provider receipt has `execution_authorized=false` and `production_decision_authorized=false`.
- [ ] Run fixture-only deterministic replay twice and require identical canonical hashes/evidence IDs.
- [ ] Run controlled public-source canaries (NY Fed/Treasury/CFTC/EIA/FRED as applicable) only after tests are green.
- [ ] Run credentialed canaries only for credentials already configured and permitted; missing credentials produce explicit blocked/unconfigured receipts, never fake success.
- [ ] **Do not run an SEC live canary** in this phase.
- [ ] Validate the `Icarus-engine` bridge against the current committed external-data/Databento manifests and confirm no duplicate vendor calls.
- [ ] Open a PR; require CI green and independent review of temporal leakage, secret redaction, licensing boundaries, revision handling, idempotency, and authority monotonicity before merge.
- [ ] Merge only after verification evidence is attached. No direct-to-main implementation commits.

## Acceptance Criteria

The implementation is complete only when all approved sources are represented in the central capability registry, all currently accessible sources have tested adapters or non-duplicative bridges, inaccessible/entitlement-gated sources fail closed, SEC remains intentionally dormant, every observation is point-in-time and provenance-bearing, raw/licensed bytes remain off Git, duplicate/revision behavior is deterministic, continuous orchestration/backfill is tested, the Overview exposes truthful health, and the full ICARUS test suite has no regression attributable to this work.

## Deliberately Deferred

- Enabling live SEC/EDGAR HTTP collection.
- Supplying/configuring the SEC User-Agent.
- Explaining the SEC User-Agent setup details (owner requested that explanation later).
- Granting any external provider direct production/trading authority.
- Replacing existing Icarus-engine collectors merely for architectural neatness; migration requires separate evidence that the replacement is better and non-duplicative.
