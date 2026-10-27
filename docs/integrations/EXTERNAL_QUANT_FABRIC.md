# External quantitative research fabric — first isolation boundary

**Status:** source integration candidate, not deployed or empirically qualified. Canonical ICARUS repository: `reppiks490/Icarus`. This is an additive research-only seam; no changes to strategy decision paths, broker adapters, live order authorization, mobile/UI defaults, schedules, provider entitlements, or existing data collectors.

## Current shipped candidate (this PR)

- `python -m icarus_engine.external_research probe` reports **installed distribution metadata** for Qlib, RD-Agent, HFTBacktest, NautilusTrader, DuckDB, Polars, and Arrow. No plugin is imported, executed, downloaded, or represented as runtime-verified. Availability on a GitHub runner does **not** establish availability in the owner's WSL2 virtual environment or Windows UI process.
- `export-qlib` is a bounded-memory staging adapter for **one actual futures contract** with explicit UTC source timestamps, a declared raw-price basis, deterministic timestamps, required per-record contract identity, OHLCV geometry checks, duplicate/out-of-order rejection, and no arbitrary record limit. It accepts only exactly seven columns: `timestamp,contract_id,open,high,low,close,volume`.
- A clean new output directory receives `qlib-bars.csv` (`instrument,datetime,open,high,low,close,volume`) and `manifest.json`. The source CSV and export are SHA-256 bound. Both outputs remain outside ICARUS state; existing directories are not overwritten.
- Every emitted manifest carries `source_authenticity_verified=false`, `entitlement_verified=false`, `roll_mapping_verified=false`, `training_approved=false` and `execution_authorized=false`. Row consistency is **not** vendor-authenticity verification or proof of profitable execution.

Example on a separately authorized local dataset, with its actual contract identity and source provenance:

```bash
python -m icarus_engine.external_research probe

python -m icarus_engine.external_research export-qlib \
  --input /authorized/data/nq_march_2026_5m.csv \
  --output /authorized/research/staging/nqh2026_5m \
  --instrument NQ \
  --contract-id NQH2026 \
  --source-id approved_vendor_receipt_id \
  --bar-seconds 300 \
  --price-basis raw
```

The example paths and receipt ID are placeholders, **not discovered or collected datasets**. No command retrieves market data. Output is a Qlib-oriented CSV staging artifact, **not** a Qlib native binary store, factor model, HFT event feed, or Nautilus data catalog.


## Canonical handoff into the isolated evidence plane

After **independently proving** the data source and actual producer Git commit, an operator may generate a quarantined, revision-bound candidate. Availability time is a caller attestation; the adapter rejects any availability earlier than the last bar but does not claim independent verification:

```bash
python -m icarus_engine.external_research emit-handoff \
  --staging /authorized/research/staging/nqh2026_5m \
  --producer-repository reppiks490/Icarus \
  --producer-revision <FULL_40_CHARACTER_COMMIT_SHA> \
  --available-at 2026-01-06T00:00:00Z
```

The adapter rehashes staged CSV against the manifest, checks that every safety flag remains denied, and creates `candidate_handoff/evidence_record.json` and `candidate_handoff/handoff.json`. These follow the structures at `integration/schemas/evidence-record.schema.json` and `integration/schemas/handoff.schema.json`. Any handoff is **stale by default**, `authority_granted=NONE` and requires independent canonical consumer-side validation and explicit review before research adoption. It is **never** written to the runtime's state or live decision input.

## Engineering still required — not implied complete

| Framework | Next adapter / validation work | Hard blocker or proof needed |
| --- | --- | --- |
| Qlib | Map authorized source-specific schema to strict staging; ingest with installed Qlib CSV-to-binary tools; prove window/timezone/instrument parity; as-of features and quarantined model lineage | Tested WSL2 runtime, installed version/API, licenses and legitimate market data |
| RD-Agent | Verify host RAM/VRAM and installed chat + embedding models, endpoint health, code-execution sandbox; register a read-only experiment contract that outputs revision-hashed candidates | WSL2 hardware/memory audit and independently verified local model |
| HFTBacktest | Build time-aligned MBP/MBO depth event converter with tick/lot value, sequence ordering and exchange-local timestamps; calibrate queue/latency/fees, and use independently controlled fills | Permitted depth data and actual execution validation; OHLCV staging is insufficient |
| NautilusTrader | Instrument/provider specification adapter; normalized tick/bar catalog, replay engine and independent paper-fill reconciliation | Correct versions and instrument definitions, parity against trusted raw prints |
| ABIDES / FinRL | Isolated synthetic market and learning experiments only; log seeds and prohibit promotion of synthetic gains as real-market edge | Reproducible, data-proven, causally validated experiment |
| Polars / DuckDB / Arrow / ClickHouse | Streaming ingestion into versioned local datasets with integrity, provenance, entitlements and cost receipts; benchmark against current pipelines | Exact local environment and storage assessment; no blind historical backfill or paid calls |
| REA | Restrict to authorized code/artifact inspection in an isolated disposable worker; never ingest private tokens or execute arbitrary third-party repository scripts without audit | Confirm local Codex/WSL operation and each external repository's license and trust boundary |
| ICARUS Brain/UI | Evidence adapter against existing `integration/schemas/*` and Brain contracts, cross-revision validation, preview gauges displaying sample adequacy, uncertainty and refusal status; paper-only shadow comparison | Independent reviewed CI plus empirical admission; owner-PC rendered UI tests |

## End-to-end promotion gates

1. Inventory every locally downloaded external repository **by URL, immutable commit, license, dependency lock, purpose, duplication, and executable risk**. Prior download counts are not an inventory with verified versions.
2. Verify owner-PC Windows/WSL2 CPU, memory, disk, GPU, tool virtual environments, and process boundaries before deploying resource-intensive models.
3. Audit the known source provenance, applicable market-data rights, secrets, and cost controls. Never commit vendor-licensed rows, model secrets, or credentials.
4. For every adapter, independently verify exact data schema, units, timezone/calendar, underlying futures contract and roll metadata, monotonicity, timestamps at decision versus availability, and completeness. No arbitrary sampling ceilings.
5. Separate training, tuning, holdout, and forward periods; pre-register trials; count the whole search family; exclude future information. No repeated use of the protected holdout to choose a model.
6. Evaluate Heikin Ashi on the visualization side only; measure fills against **real prices**, fees, slippage and conservative intrabar rules.
7. Test replay determinism, restart recovery, Windows/WSL compatibility, large-data streaming, failure/refusal paths and evidence hashing on exact HEAD.
8. Connect an accepted experiment only through the revision-bound canonical handoff schema, and never directly into live orders or sizing. No model from downloaded code earns an empirical "edge" badge by installation.
9. Require separate authorization and stronger empirical proof for any future production promotion. The current owner constraint leaves live broker arming disabled.

## Change isolation / conflicts

This seam is limited to the new module `icarus_engine/external_research.py`, its focused `tests_engine/test_external_research.py`, this documentation, and a dedicated offline CI check if added. It does **not** supersede the ongoing owner-PC takeover, phone pairing, draft Icarus PR #485, Engine PR #260, or FR-1 draft #209. Coordinate further work on the owner-actions bus and preserve branches and existing collectors.

## Explicit limitations

The input flag `--price-basis raw` is a **caller declaration**, not proof that an opaque file was measured directly from the exchange. Contract identity and OHLCV validators prevent some false matches but cannot establish vendor authenticity, gap-free delivery, an executable fill, or that the local owner machine can run Qlib. The fabric currently exports only this first validated offline staging format. It has not trained a model or installed/downloaded anything on the user's PC.
