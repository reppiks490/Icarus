# Local research inventory — 2026-11-24

**Deeper follow-up:** [DEEP_DISCOVERIES.md](DEEP_DISCOVERIES.md), [deep-source-evidence.json](deep-source-evidence.json), and [deep-artifact-evidence.json](deep-artifact-evidence.json) preserve 15 targeted source inspections with exact paths/revisions/file hashes, new AION clock counts and MYRIAD weight metadata, integration opportunities and acceptance gates. Read before implementing new financial-world adapters.

**Findings navigation:** [FINDINGS_LOCATIONS.md](FINDINGS_LOCATIONS.md) contains directions to the recorded local and GitHub findings. [findings-locations.json](findings-locations.json) indexes all 275 measured project roots, all 14 pinned model/tokenizer directories and 42 observed artifact paths, plus targeted path checks and environment locations. Resolve local path aliases on the authorized Windows device; do not guess missing paths.
## START HERE for the next agent
This is a local Windows-machine evidence handoff for ICARUS / UMBRA / MYRIAD / POLYMIND. It is research-only, not a deployment or authorization to trade. Read this file, repository-metadata.json and repository-sizes.json before downloading more repositories. All findings are snapshots, not current runtime guarantees. Use authorized Remote Desktop Commander to reverify local paths. <USER_HOME> means the connected Windows user's home; <SYNC_ROOT> means its local Dropbox-synced research root (resolve locally; do not publish account-identifying path components). Unprefixed size-record paths are relative to user home.

## Discovery and storage
Original discovery: 269 locations (237 Git, 32 extracted source projects). Expanded index audit: 275 locations (243 Git, 32 source), 238 resolved HEADs, 217 distinct full HEAD hashes, 243 index inventories, 5 unverified HEADs, 78 skipped reparse entries. Distinct HEADs are not distinct software projects. Index test paths do not prove passing tests. See the metadata JSON for revisions and per-project counts.

The completed storage census measured **275/275 discovered locations**, comprising 243 Git locations and 32 extracted source projects. Original 269-root pass: 100,765,857,325 bytes and 1,771,110 files. Six additional ML repositories: 369,190,311 bytes and 3,285 files. Reconciled total: **101,135,047,636 logical bytes (101.135 GB)** and **1,774,395 files**. Both measurement processes exited successfully; no traversal errors or placeholder entries were reported within the measured scope. Four nested inventoried roots were excluded from their parent totals. Both JSON inventories contain 275 unique normalized paths with exact set equality. The original local output files under projects/icarus-local-inventory-20261124-*.json preserve the 269-root pass only; the GitHub size JSON reconciles the extra six. See the full session handoff and system/runtime evidence for the earlier research, development and acquisition history.

| Category | Logical bytes |
|---|---:|
| git | 53,015,505,445 |
| source_other | 35,806,794,936 |
| data | 5,740,776,416 |
| dependencies | 4,591,978,539 |
| archives | 1,136,483,111 |
| build | 566,938,515 |
| weights | 276,570,674 |

| Collection | Locations | Logical bytes |
|---|---:|---:|
| downloads | 65 | 34,774,034,887 |
| external | 88 | 45,524,148,658 |
| other | 87 | 19,561,924,241 |
| myriad | 21 | 466,702,692 |
| new_ml | 14 | 808,237,158 |

These are logical file lengths, not actual NTFS allocation or reclaimable space. Categories are heuristics. The metadata discovery was depth-limited and excluded 78 reparse entries; measuring discovered paths does not prove complete PC coverage. Shared hardlinks, sparse files, compression, cloud sync and duplicate histories require separate verification. No deletion, compaction, cloud hydration or runtime change is authorized. Earlier overlapping snapshots below must not be added to this total.

## Full-session continuation documents
- [SESSION_HANDOFF.md](SESSION_HANDOFF.md): chronological technical history, actual UMBRA changes, POLYMIND, acquisition and proposed ICARUS research architecture, Pulse findings and next-agent instructions.
- [repository-metadata.json](repository-metadata.json): 275 locations and Git index/HEAD evidence.
- [repository-sizes.json](repository-sizes.json): reconciled 275-root storage census.
- [runtime-evidence.json](runtime-evidence.json): sanitized system, environment, dependency-cache and model acquisition observations.
- [CONTINUE.md](CONTINUE.md): prioritized operational handoff with explicit gates.
- [RECOVERY_CATALOG.md](RECOVERY_CATALOG.md): detailed historic archive names, local project paths, owner federation and acquisition context.
- [GIT_STORAGE_AUDIT.md](GIT_STORAGE_AUDIT.md): 53.015 GB Git metadata opportunity, ranked repositories and safe investigation plan.

## Previously recovered local assets
- Primary Icarus: 871,066,987 bytes excluding selected dependency/cache paths; 41 SQLite3 files, 363 Python files. research/market-sources.sqlite3 232,505,344 bytes; audit/subsystem_connections/main/aion.sqlite3 187,785,216; CC2 AION 106,287,104; icarus_engine.db 67,416,064. Schema inspection: market source records/trades/streams; AION events with event/availability/ingestion times, forecasts, settlements and gaps; engine trade/fill/equity/log tables. No row-level qualification performed. Avoid reading credential or access-registry payloads.
- Icarus-ml-d9d4db8: earlier scoped scan 627 CSVs totaling 922,835,471 bytes, 131 Python files, 9 archives. Existing trainers/catalog.py, dataset.py, xgb.py, verify.py, run/trainers/training_run.json. Primary Icarus trainers include logit, xgb_slot, rank_slot, regime_slot, fail_slot, calibrate, qualify, ledger, integrity, metrics, purged_slices. Some slots incomplete. Historical TRAINER-CALIBRATION-001 identifies holdout contamination risk: do not fit calibration on final evaluation data. Resolve the frozen-spec conflict before qualification; preserve Pulse.
- Icarus-engine: 5 MNQ CSVs (5m, 10m, 20m, 30m, alternate 20m) totaling 18,840,173 bytes; PulseStrategy and validation/replay/sweep tools.
- Downloads CSV collections: 288 + 248 + 66 + 9 + 476 + 174 + 174 = 1,435 entries, ~462 MB before deduplication. The two 174-file sets have matching aggregate sizes; not yet hash-confirmed identical. Real OHLC, Heikin Ashi and tick/range exports must remain separate, with availability, venue, contract and cadence provenance. Trade exports are not certified live fills.
- Downloads/divine providence: earlier scoped scan 39,694 files, 4,664,031,814 bytes. 204 research archives examined, 82 unique SHA-256s, 122 redundant archive copies; archive scope limited to three known folders. Preserve history; never extract or delete indiscriminately.
- MYRIAD-v32-local-pilot-20261124: 182 FP16 files (650,345,728 bytes), 5 SQLite DBs, 1,520 JSON, 14 JSONL; prior total 677,735,887 bytes excluding selected environments. No claim of independently trained financial predictors. Its 21 capability repositories include llama.cpp, FAISS, GraphRAG, Haystack, DSPy, Optuna, Qwen-Agent, LangGraph, smolagents, Inspect AI, LM evaluation harness, CLRS, LeRobot, Evidently, MCP SDK, Outlines, LM Format Enforcer, scientific-agent-skills, SearXNG, Trafilatura, MarkItDown.
- Numerical acquisition: both jobs completed with 14 verified model/tokenizer acquisitions totaling 1,228,929,627 download bytes; see runtime-evidence.json. Earlier snapshot: 12 safetensors files 559,976,504 bytes (overlapping, not additive). Includes Kronos, Chronos, Granite, Toto, MOMENT. Verify current acquisition receipts, exact hashes, licenses and runtime compatibility; file presence != inference qualification. Pending Ollama pulls (Gemma3:12b, Llama3.2:3b and queued models) were paused at owner request; do not resume without authorization. Earlier Ollama storage snapshot 34,644,252,308 logical bytes includes partial blobs.
- STARNET local checkout 74fcd5040 plus extracted source copy. Existing lifecycle, execution router, evidence, learning eligibility, memory and visual station modules. Inspect capabilities and license before integration; do not start agents or invoke paid tools automatically.
- NEXUS v0.3 03b2265, local review 6529eed: causal data features, source hashing, replay bus, availability checks, multi-resolution representation registry. DAEDALUS 74ad941: logistic/forest/extra-trees/hist-gradient-boosting, causal features, regimes, purged validation and independent holdout gates. AION 12a7cb8: temporal market memory and labeled replay; settlement not independently verified. ORACLE 6255339: research orchestration, not broker access. PROMETHEUS v0.5 444d978: experiment routing, same-instant replay, evidence lineage, deferral. JANUS runs 025/027/028/029/030/032/037/038 plus additional extracted 032: proof-carrying bi-temporal project twin. Causal router d95a53c AdaptiveRegressor; check unresolved journal import before use. Evidence lab d6a5868 structural audits, not market-data certification. No live execution authority.
- 88 repositories under ICARUS-EXTERNAL-GITHUB/source and 65 under ICARUS-GITHUB-DOWNLOADS; duplicates and forks exist. Acquisition manifests and logs retained locally. Important already present: Qlib, RD-Agent, FinGPT, FinRL, GluonTS, NeuralForecast, StatsForecast, Darts, River, Optuna, SHAP, PyMC, Tigramite, DoWhy, EconML, finlab-ml, purgedcv, holdout, MLFinLab, CVXPY, ABIDES-JPMC, AlphaTrade/JAX-LOB, HftBacktest, NautilusTrader, LEAN, VectorBT, Databento, CCXT, OpenBB, FinanceDatabase, CME parsers, MBO-to-MBP-10, Arrow, DataFusion, DuckDB, Polars, Feast, MLflow, DVC, lakeFS, Graphiti, Mem0, LangGraph, AutoGen, CrewAI, Pydantic AI, Phoenix, Langfuse, Promptfoo. Full names/revisions in metadata. RD-Agent README describes Qlib factor/model joint optimization; holdout README describes PBO and deflated Sharpe; purgedcv README describes CPCV; AlphaTrade README describes JAX-LOB; ABIDES README describes discrete event exchange simulation; HftBacktest README describes queue and latency fill models. These are documented capabilities, not local smoke-test results.
- New research clone inventory: 14 measured Git locations after the expanded scan (8 in original pass, 6 additional). Includes Kronos, PySINDy, pyribs, TS2Vec, ABIDES, Time-Series-Library, Qlib, NeuralForecast, DreamerV3, TD-MPC2, d3rlpy, aeon, TALENT; verify current clone receipts.

## Runtime and system findings (metadata only)
Existing synced venvs: hft (47 distributions, hftbacktest 2.4.4); nautilus (2 distributions, nautilus_trader 2.0.0rc7, incomplete compatibility unverified); quant (194, pyqlib 0.9.7, LightGBM, CVXPY, MLflow, scikit-learn, SciPy); research (220, River, Optuna, Ruptures, DuckDB, Polars, statsmodels, MLflow). New icarus-ml-runtime (105 distributions at inspection) contains xgboost_cpu, LightGBM, River, hmmlearn, arch, PySINDy, DEAP, pymoo, ribs, Optuna, SymPy, aeon, PyOD and others. MYRIAD training env torch CPU and SymPy metadata; POLYMIND runtime ORT, numpy, tokenizers, HF hub. Final installer receipt reports gplearn 0.4.3 requires scikit-learn>=1.8.0 but 1.7.2 was installed. The environment is not qualified; resolve in isolation and check representative imports, pip check and inference before use.
Temp 215 wheels 408,738,235 bytes, 421 NPZ only 132,496 bytes (not evidence of major model banks). UV bounded scan 457,276,113 bytes, npm 82,537,778 bytes, Temp 745,784,384 bytes. WSL registered Ubuntu and docker-desktop; virtual disks observed 15,294,529,536 bytes WSL and 6,788,481,024 Docker. Not mounted or inspected. Installed metadata: Python 3.10–3.13, Node 26.13.0, Git 2.54.0, Ollama 0.40.17, WSL 2.6.3.0, Docker 4.92.0, PostgreSQL 18.3-2, VS Build Tools. System directory snapshots depth-limited. Credential locations inspected for presence only; protected system areas denied; no secret extraction or bypass. Do not publish private logs or raw licensed data.

## Ranked next-agent plan
1. Size coverage of all 275 discovered locations is closed; compare physical allocated disk bytes only via supported local filesystem metadata, account for hardlinks/cloud placeholders. No deletion or compaction without explicit owner approval.
2. Verify active downloads, free space, exact model receipts and isolated environments. Avoid duplicate installs/clones. Preserve existing runtime and current owner constraints; no scheduled Codex use.
3. Build a local reference-only inventory of CSVs, DB sources, archive entries and trained artifacts with hashes, lineage, timestamps and rights; avoid loading pickle or unknown code. Keep raw artifacts local.
4. Extend existing Icarus trainer adapters, starting with Qlib/LightGBM/XGBoost/River; numerical models as challenger forecasts, family-specific inputs and independently calibrated evaluation. Preserve original Pulse and current paper system.
5. Use NEXUS/AION for chronological feature availability, DAEDALUS/purgedcv/holdout for scientific gates; UMBRA + ABIDES/AlphaTrade/HftBacktest only for simulation and replay, never claim real fills from synthetic evidence.
6. Route MYRIAD/POLYMIND research specialists through constrained evidence interfaces, evaluate using existing capabilities; no automatic paid actions, model authority, broker arming or unapproved merges.
7. Publish sanitized evidence and exact revisions; check current coordination reservations before implementation. No proof of profitability or complete four-month history. Historical filesystem timestamps do not establish actual usage.

## Completion boundary
This branch is documentation only. No source changes, deletion, credential disclosure, live broker activity, provider calls, deployments, or main merge. The 275 discovered-root size snapshot is complete; whole-machine usage, actual allocation, content-level security, model qualification and historical evidence remain incomplete. The report does not establish actual physical disk allocation, tested functionality of all repositories, or unique software count.
