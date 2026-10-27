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

## Independent read-only consumer verification (implemented)

```bash
python -m icarus_engine.external_research_verify \
  --staging /authorized/research/staging/nqh2026_5m \
  --producer-repository reppiks490/Icarus \
  --producer-revision <FULL_40_CHARACTER_COMMIT_SHA>
```

This checks every exported row independently of the producer function, verifies the staged and canonical artifact hashes, recalculates the revision-bound evidence ID, rejects inconsistent first/last bar timestamps, rejects a different producer repository or revision, refuses path traversal and symlinks, and ensures the candidate's authority and training status remain denied. Returns a **read-only structural receipt**; authenticity, entitlement, calendar completeness and research model quality are not inferred.

## Qlib official CSV-input preparation (implemented; Qlib binary conversion pending)

Microsoft Qlib's maintained `scripts/dump_bin.py` takes individual symbol-named CSVs with a date column and open/close/high/low/volume/factor fields (see <https://github.com/microsoft/qlib/blob/main/docs/component/data.rst>). We now prepare that intermediate format without importing/executing Qlib:

```bash
python -m icarus_engine.external_qlib_prepare \
  --staging /authorized/research/staging/nqh2026_5m \
  --output /authorized/research/prepared/nqh2026_5m \
  --producer-repository reppiks490/Icarus \
  --producer-revision <FULL_40_CHARACTER_COMMIT_SHA>
```

Outputs:
- `qlib_input/NQH2026.csv` with date, open, high, low, close, volume and factor columns; each date string is in **UTC without a timezone suffix** to match Qlib's documented parser. `prepare_manifest.json` permanently records that those naive strings mean UTC, the actual underlying futures contract, bar cadence, source revision, and SHA-256 input/output evidence.
- Factor is **1** for unadjusted raw prices; it does not convert a continuous futures synthetic series into genuine fills. Rollover stitching and provenance require separate research work.
- Supported offline CSV cadences: 1, 2, 5, 10, 15, 30 and 60 minutes. Other bar, event-tick and order-book inputs must use a dedicated adapter; no silent resampling or truncation.
- The output is immutable at the directory level (pre-existing targets are refused), uses bounded streaming, and refuses unsafe filenames such as continuous ticker aliases as actual contract identities.
- The tool never runs `dump_bin.py`, installs a dependency, downloads market data, trains a model or writes into Brain/strategy/broker state. Real Qlib binary export and native Qlib queries **remain not verified on the owner's Windows/WSL2 machine**.

Only after explicit local verification of the installed Qlib code and licenses may a research operator use its official `dump_bin.py dump_all` converter against this isolated `qlib_input` directory and a **separate, new** binary output location. That additional execution path is *not* implemented or authorized by this PR. Qlib provider/calendar behavior, inference pipelines and ML model acceptance still require independent validation, not just command success.



## Native Qlib binary parity — independent read-only consumer (implemented)

After a separately verified Qlib dump produced its files into a **fresh isolated directory**, the candidate can be audited against the exact prepared single-contract input. The verifier checks the official writer's little-endian float32 feature format (first float is calendar start index, followed by each observation), every price/volume/factor, contract-specific instrument start/end, and the frequency calendar. It streams all rows; neither rows nor features are silently truncated. The expected producer repository, immutable commit revision, and handoff identifier must come from an independent trusted source.

```bash
python -m icarus_engine.external_qlib_verify \
  --prepared /authorized/research/prepared/nqh2026_5m \
  --qlib-dir /authorized/research/native_qlib/nqh2026_5m \
  --contract-id NQH2026 \
  --producer-repository reppiks490/Icarus \
  --producer-revision <FULL_40_CHARACTER_COMMIT_SHA> \
  --handoff-id <64_CHAR_VERIFIED_HANDOFF_SHA256>
```

This verifier is **not the Qlib dump itself** and does not execute Qlib code, download source, connect to a provider, validate model prediction quality, or promote training/broker authority. Its offline regression fixtures emulate the published binary format; they do not constitute an authentic Qlib binary run. A verified structural match still does not establish market-data authenticity, entitlement, complete exchange sessions, accurate queue fills, or a profitable edge. Only a successful native Qlib dump+readback on the authorized owner host can clear the separate runtime step.

## RD-Agent local Windows/WSL2 capacity preflight (implemented; local execution pending)

```bash
python -m icarus_engine.external_rd_agent_preflight --workspace .
```

This optional **read-only** inventory reports host/WSL kernel class, logical CPU count, available RAM, cgroup-v1/v2 effective memory ceilings and consumption when exposed, free disk bytes, and whether installed distribution metadata for `rdagent` exists. It never contacts a model endpoint, executes the agent, installs models, checks credentials, invokes GPU drivers, or changes host configuration.

Capacity classes are deliberately provisional: fewer than 4 GiB effective available or 10 GiB free disk is blocked; under 12 GiB available or 25 GiB disk is constrained; above those thresholds means **capacity measured but model suitability unverified**, not permission to install or run a particular model. Unknown cgroup headroom remains unknown. It cannot measure available GPU VRAM or chat/embedding model compatibility.

**Important:** A readout in the GitHub runner or this chat's container says nothing about the owner's Windows/WSL2 limits. The actual owner's host report remains outstanding, so RD-Agent local chat+embedding model selection, download, endpoint verification and experiment execution have not been performed.


## HFTBacktest MBP L2 event-column staging (implemented; replay not authorized)

HFTBacktest documents an 8-field Event dtype: `ev, exch_ts, local_ts, px, qty, order_id, ival, fval`; ICARUS now prepares a provenance-bound **CSV with these fields**, not an executable NumPy structured array. Upstream specification: https://github.com/nkaz001/hftbacktest/blob/master/docs/data.rst and https://github.com/nkaz001/hftbacktest/blob/master/hftbacktest/src/types.rs.

The source CSV must have exactly `sequence,contract_id,kind,side,exchange_ts_ns,local_ts_ns,price,quantity`. Supported records are market-by-price `depth_update` (bid or ask, zero size means remove level) and `trade` (buy or sell aggressor, positive size). An actual futures contract, positive tick/lot sizes, strict sequence order, tick/lot grid alignment, nondecreasing exchange and local clock, and local reception no earlier than exchange timestamp are mandatory. The converter refuses unsupported snapshots, MBO order IDs and add/cancel events instead of inventing them.

```bash
python -m icarus_engine.external_hft_stage \
  --input /authorized/data/physical_contract_mbp_l2.csv \
  --output /authorized/research/hft/staged_nqh2026 \
  --contract-id NQH2026 --source-id authorized_vendor_receipt \
  --tick-size 0.25 --lot-size 1
```

Output is `hft-events.csv` and `manifest.json`, with input/output SHA-256, clock bounds, event counts and authority explicitly denied. Streaming has no arbitrary row limit and never overwrites an existing directory. This does **not** verify vendor entitlement, source authenticity, clock synchronization, snapshot completeness, L3 order IDs, queue placement, real fills or profitability. Conversion to version-pinned HFTBacktest-native NumPy and independent simulator replay remain separate unimplemented gates.

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
