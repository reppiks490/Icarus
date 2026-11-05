# Real Icarus-engine evidence federation

This integration consumes **actual committed evidence** from `reppiks490/Icarus-engine`. It contains no synthetic market fixtures and makes no provider requests.

## Exact peer evidence used by the first verification

The dedicated workflow pins Engine commit:

`10d02b2e1ee20797be5945ffe3f4ebb5e4193bb3`

At that commit the reader validates these existing committed evidence surfaces directly:

- `config/data_ingestion_manifest.json`
- `automation_intelligence/provider_collection_v1/research_context.json`
- `automation_intelligence/sentinel/data_health.json`
- `automation_intelligence/cl_lab/sec_edgar_manifest.json`
- `automation_intelligence/native_research_v1/latest.json`
- `automation_intelligence/interrepo/latest.json`

The workflow checks out both repositories, verifies the Engine checkout's exact Git HEAD, and then runs the Icarus reader against those real files in place.

## What is connected

The catalog exposes only redistribution-safe metadata/provenance already committed by Engine:

- source credential/ingestion/consumption states and explicit blockers from the canonical ingestion manifest;
- current provider receipt status, row/page/request counts and timestamps from the real provider research context;
- SEC/EDGAR real persisted manifest counts and the existing fact/filing SHA-256 digests;
- Native Five run identity and lane receipts;
- the existing inter-repository acceptance packet identity and authority state;
- current Sentinel health counts, including BLOCKED/DEGRADED/FAILING states instead of hiding them;
- SHA-256 and byte size for each consumed evidence document.

The reader does **not** copy licensed raw vendor payloads or decrypt provider archives. It performs zero provider calls and zero new collection.

## Authority boundary

This is a research/evidence connection only. It never turns evidence availability into trade permission.

The output hard-codes and validates:

- `raw_payloads_copied=false`
- `provider_requests_made=0`
- `new_collection_performed=false`
- `automatic_model_promotion=false`
- `production_decision_authorized=false`
- `execution_authorized=false`

Provider BLOCKED/DEGRADED states, Sentinel failures, entitlement limits, and historical-only receipts remain visible. They are not relabeled as healthy.

## No synthetic evidence

The dedicated integration test does not generate synthetic provider rows or fake market observations. It reads the exact pinned Engine checkout. Assertions are against the actual committed provider/SEC/native/interrepo evidence at that commit, including the real Massive receipt, FRED receipt, SEC/EDGAR manifest, Native Five status, and Sentinel state.

The dedicated GitHub Actions run is the evidence of connectivity. A later Engine commit requires an explicit pin update and re-verification rather than silently drifting to a different evidence state.
