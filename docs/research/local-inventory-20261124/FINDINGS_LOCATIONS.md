# Findings location guide — 2026-11-24

**Deeper follow-up:** [DEEP_DISCOVERIES.md](DEEP_DISCOVERIES.md), [deep-source-evidence.json](deep-source-evidence.json), and [deep-artifact-evidence.json](deep-artifact-evidence.json) preserve 15 targeted source inspections with exact paths/revisions/file hashes, new AION clock counts and MYRIAD weight metadata, integration opportunities and acceptance gates. Read before implementing new financial-world adapters.

This is the navigation layer for the complete session handoff, not a new scan of all files. Use [findings-locations.json](findings-locations.json) to find every one of the 275 measured project locations, their recorded Git HEADs, logical sizes, and the fourteen pinned model/tokenizer artifact directories. It also records 35 fresh local existence checks, 42 individual model/config/receipt file metadata observations, selected directory listings and system/environment locations. All 35 checked locations existed at the latest readback. Historical repository paths have not all been freshly rechecked.

## 1. Start here: GitHub and authorized local device

- Handoff: [Icarus PR #505](https://github.com/reppiks490/Icarus/pull/505), branch agent/local-inventory-20261124, directory docs/research/local-inventory-20261124/. Read [README.md](README.md), [SESSION_HANDOFF.md](SESSION_HANDOFF.md), [CONTINUE.md](CONTINUE.md), and [RECOVERY_CATALOG.md](RECOVERY_CATALOG.md).
- [repository-metadata.json](repository-metadata.json) is the source of historical Git HEADs and index counts. [repository-sizes.json](repository-sizes.json) is the measured storage evidence; [GIT_STORAGE_AUDIT.md](GIT_STORAGE_AUDIT.md) ranks the largest Git stores. [runtime-evidence.json](runtime-evidence.json) holds model acquisition and runtime receipts. [findings-locations.json](findings-locations.json) joins these sources into a navigable index.
- Use the authorized Remote Desktop Commander connection to the owner's Windows PC. The location aliases are intentionally portable: <USER_HOME> = the connected user's Windows profile directory ($env:USERPROFILE); <SYNC_ROOT> = the existing local synced research root containing ICARUS-EXTERNAL-GITHUB and ICARUS-GITHUB-DOWNLOADS. Account-identifying names stay local.
- Resolve <SYNC_ROOT> from the original local roots manifest at <USER_HOME>/projects/icarus-local-inventory-20261124-roots.json. Its entries have user-home-relative paths. Find a path whose component equals ICARUS-EXTERNAL-GITHUB or ICARUS-GITHUB-DOWNLOADS; the preceding path components identify the sync root relative to the user profile. Verify each collection exists. If the collections have moved or there are multiple possible roots, use existing manifest evidence and report ambiguity rather than guessing or hydrating cloud placeholders.
- On the PC, enter %USERPROFILE% in File Explorer, then navigate to the relative path below; use the resolved synced root for <SYNC_ROOT>. In PowerShell, use Join-Path $env:USERPROFILE 'relative/path' and Test-Path -LiteralPath to verify. Quoted literal paths are required for names with spaces, exclamation marks and parentheses. Do not paste aliases as literal Windows folder names. Do not print credential values or raw private directory content.
- Original 269-root census files: <USER_HOME>/projects/icarus-local-inventory-20261124-roots.json and <USER_HOME>/projects/icarus-local-inventory-20261124-sizes.json. Both were confirmed present. The final 275-root combined evidence is in GitHub JSON, not the earlier local 269-root file.
- The Desktop/ICARUS-COMPLETE-LOCAL-INVENTORY folder was found, but its earlier two three-byte CSVs were not a substantive inventory. Use the GitHub records, not those files.

## 2. All 275 repositories and the Git storage opportunity

Open [findings-locations.json](findings-locations.json) and search its projects array by project name, path, or HEAD. Each entry contains the exact alias-relative path and measured logical bytes, Git bytes, dataset/weight bytes, and Git index evidence when available. This covers 243 Git locations and 32 extracted source projects. Repository presence does not prove an operational runtime.

| Collection | Where to look | Count |
|---|---|---:|
| External research | `<SYNC_ROOT>/ICARUS-EXTERNAL-GITHUB/source` | 88 |
| Downloaded research | `<SYNC_ROOT>/ICARUS-GITHUB-DOWNLOADS` | 65 |
| MYRIAD capability sources | `<USER_HOME>/projects/MYRIAD-v32-local-pilot-20261124/capability-acquisition` | 21 |
| New numerical research sources | `<USER_HOME>/projects/icarus-ml-research-sources` | 14 |
| Other local projects and historical checkouts | Individual exact paths in projects array | 87 |

The 53,015,505,445 logical bytes attributed to .git directories are not confirmed reclaimable bytes. For Git candidates, inspect the exact indexed local root and locate its real Git directory/common directory (read-only git rev-parse --git-dir and --git-common-dir); do not assume .git is a directory rather than a worktree pointer. Use [GIT_STORAGE_AUDIT.md](GIT_STORAGE_AUDIT.md) for preservation gates. Top paths include FinanceDatabase, ClickHouse and CCXT. Do not run gc, repack, prune, deletion or replacement without explicit owner authorization.

## 3. ICARUS source, data and existing learning systems

All paths below are relative to <USER_HOME> unless explicitly prefixed. The top-level Icarus, Icarus-engine and Icarus-ml-d9d4db8 directories were freshly confirmed.

| Finding | Location | Notes |
|---|---|---|
| Canonical primary checkout | `Icarus` | Live runtime must not be changed by inventory work. |
| Research engine | `Icarus-engine` | Verify current branch before edits. |
| Existing trainer workspace | `Icarus-ml-d9d4db8` | Prior 627 CSVs and training code. |
| Trainer implementation | `Icarus-ml-d9d4db8/icarus_engine/trainers` | Inspect catalog.py, dataset.py, xgb implementation and tests; exact filenames may vary by revision. |
| Trainer receipt | `Icarus-ml-d9d4db8/run/trainers/training_run.json` | Confirmed file metadata. |
| Candidate catalog | `Icarus-ml-d9d4db8/run/candidates/catalog.json` | Confirmed file metadata. |
| Primary trainer source | `Icarus/icarus_engine/trainers` | Historical source observation; reverify. |
| Market-source DB | `Icarus/research/market-sources.sqlite3` | Confirmed, 232,693,760 bytes at latest readback. |
| Main AION DB | `Icarus/audit/subsystem_connections/main/aion.sqlite3` | Confirmed, 187,834,368 bytes at latest readback. |
| Engine DB | `Icarus/icarus_engine.db` | Confirmed, 67,416,064 bytes. |
| Other AION/Command Center databases | Under Icarus; search for aion.sqlite3 and relevant .sqlite3 files within authorized project roots | Earlier sizes in README; exact individual paths beyond Main not freshly established. |
| MNQ CSVs | `Icarus-engine/data` | Historical mnq_5m_full.csv, mnq_10m_full.csv, mnq_20m_full.csv, mnq_30m_full.csv, mnq_20m.csv. |
| Historical control/data project variants | Search projects array for Icarus-g, Icarus-as-is, Icarus-causal-asof, Icarus-aion-review, icarus-reset, backup | Distinguish historical copies from running checkout. |

Original Pulse: owner-provided attachment title THE PULSE OF ICARUS X AGENT REACH — FULL EVOLUTION 4.0 (3,977 lines). Retrieve the exact original from the authorized conversation/file attachment or owner-approved file source. A local exact path and hash for this original are not established. The newly observed Downloads/ICARUS.pine and the four files under projects/pine-strategies (HYDRA-X.pine, LEVIATHAN.pine, OBELISK-F.pine, WRAITH.pine) are candidates or separate strategies, **not verified identical to the original Pulse**. See [SESSION_HANDOFF.md](SESSION_HANDOFF.md) for line-level findings; do not substitute a truncated version.

## 4. Historical CSVs and archives

Confirmed collection roots:
- `Downloads/Csv`
- `Downloads/Csv files for different chart types`
- `Downloads/Csv indexes`
- `Downloads/csv of icarus`
- `Downloads/Full csv candles only`
- `Downloads/divine providence`
- `Downloads/everything so far for opus`
- `Downloads/data-2026-04-07-18-42-59-batch-0000`

Earlier scan also found two 174-file collections whose names begin "More csv by ticks with chart candle and volume profiles technicals built in". Locate both by matching that prefix in Downloads, and compare hashes before treating them as duplicates. Names, exact sizes, and scope of earlier CSV and archive findings are in [RECOVERY_CATALOG.md](RECOVERY_CATALOG.md). Standalone BATS_HSBC, 20.csv and CME_MINI_DL_NQ1! exports were observed in Downloads; validate instrument, timeframe and provenance. A filtered listing of recent-observed relevant download names is in findings-locations.json (directory_entries); its first 160 names are not an exhaustive archive listing.

Historical archive scope: inspect Downloads, Downloads/divine providence, and Downloads/everything so far for opus. The earlier 204 ZIPs/82 distinct hashes finding applies only to the scanned scope. Use the archived filenames in RECOVERY_CATALOG.md and enumerate ZIP member metadata without extracting. Historical extracted trees may have a .zip or .bundle suffix **on a directory name**; use Test-Path -PathType Container before deciding it is an archive file. Do not blindly extract, execute or delete.

## 5. Exact recovered intelligence system locations

These are selected exact historical paths taken from the reconciled repository index. A dash means no resolved HEAD in the metadata. For every other checkout, use the full projects array.

| Local path | Observed HEAD |
|---|---|
| `&lt;USER_HOME&gt;/ICARUS-OPTIONAL-SOURCES/STARNET` | `74fcd5040ba0eb93c8f9fa07b2d0a9fcfddd1475` |
| `&lt;USER_HOME&gt;/ICARUS-OPTIONAL-SOURCES/STARNET-74fcd5040ba0` | — |
| `&lt;USER_HOME&gt;/Downloads/divine providence/divine-providence` | `5e4ed5fe005a4454512beca161bcb6879cc2ac0f` |
| `&lt;USER_HOME&gt;/icarus-reset-20261015/divine-providence` | `0e17bbe0a7b5fa223f6ec0f975e2446e5b96f450` |
| `&lt;USER_HOME&gt;/icarus-reset-20261015-070848/divine-providence` | `eeb82bd0fee67b6d76beb648e3e16c27aaa557dd` |
| `&lt;USER_HOME&gt;/daedalus-review/daedalus-research-os` | — |
| `&lt;USER_HOME&gt;/dp-runtime` | `e13b949b50470898d5ad84b4d0473091867c6fc6` |
| `&lt;USER_HOME&gt;/ICARUS-OPTIONAL-SOURCES/STARNET-74fcd5040ba0/src-tauri` | — |
| `&lt;USER_HOME&gt;/Icarus-causal-asof` | `232ea462a94cd7b3a8aa574e588a8843f5338974` |
| `&lt;USER_HOME&gt;/nexus-review-20260923/bundle-checkout` | `6529eed7623e9a967bb053c9a78e4102d2c18d6d` |
| `&lt;USER_HOME&gt;/nexus-review-20260923/NEXUS_ADAPTIVE_MARKET_FABRIC_v0.3_SOL_FOR_SOL_EXTRA_HIGH/nexus-adaptive-market-fabric` | — |
| `&lt;USER_HOME&gt;/aion-review-20260923/icarus-aion` | `12a7cb8ef99e84ce50b766db0aea1592b3906f80` |
| `&lt;USER_HOME&gt;/daedalus-intake-20260923/daedalus-research-os` | `74ad94149b02ddd3f69d535ee5fdc00c1fdbe096` |
| `&lt;USER_HOME&gt;/Downloads/divine providence/_analysis/x/NEXUS_v0.3_SOL.git (1).bundle` | `03b2265536aebdd111e83c13d7bafb03f68f4a50` |
| `&lt;USER_HOME&gt;/Icarus-aion-review` | `20c1f153a21f48fce628a139f5485eff794c76de` |
| `&lt;USER_HOME&gt;/Downloads/divine providence/_analysis/x/JANUS_INFINITY_HANDOFF_RUN_032(1).zip` | — |
| `&lt;USER_HOME&gt;/Downloads/divine providence/_analysis/x/JANUS_INFINITY_HANDOFF_RUN_038.zip` | — |
| `&lt;USER_HOME&gt;/Downloads/divine providence/_analysis/x/JANUS_INFINITY_HANDOFF_RUN_037.zip` | — |
| `&lt;USER_HOME&gt;/Downloads/divine providence/_analysis/x/JANUS_INFINITY_HANDOFF_RUN_027.zip` | — |
| `&lt;USER_HOME&gt;/Downloads/divine providence/_analysis/merge/prometheus` | `136563e25ca3325df13ca56672d2c20cbfbe74da` |
| `&lt;USER_HOME&gt;/Downloads/divine providence/_analysis/x/JANUS_INFINITY_HANDOFF_RUN_032.zip` | — |
| `&lt;USER_HOME&gt;/Downloads/divine providence/_analysis/x/JANUS_INFINITY_HANDOFF_RUN_030.zip` | — |
| `&lt;USER_HOME&gt;/Downloads/divine providence/_analysis/x/JANUS_INFINITY_HANDOFF_RUN_029.zip` | — |
| `&lt;USER_HOME&gt;/icarus-csv-evidence-lab` | `d6a5868e3f3202ef82579aca40b83cb3f8a4b491` |
| `&lt;USER_HOME&gt;/Downloads/divine providence/_analysis/x/JANUS_INFINITY_HANDOFF_RUN_028.zip` | — |
| `&lt;USER_HOME&gt;/Downloads/divine providence/_analysis/x/JANUS_INFINITY_HANDOFF_RUN_025.zip` | — |
| `&lt;USER_HOME&gt;/Downloads/divine providence/_analysis/x/PROMETHEUS_v0.5_VERIFIED_2026-09-25.bundle` | `444d978134f2b138e647b2c6c9e219f83074ac75` |
| `&lt;USER_HOME&gt;/Downloads/divine providence/_analysis/x/PROMETHEUS_v0.4_VERIFIED_2026-09-25(1).bundle` | `2659350553f23f2314b27a80bb04604d5747418e` |
| `&lt;USER_HOME&gt;/Downloads/divine providence/_analysis/x/ORACLE_CHECKPOINT_C_75_SOL.git (1).bundle` | `6255339daf80b709357a2ea581b572ebbcef5905` |
| `&lt;USER_HOME&gt;/Downloads/divine providence/_analysis/x/PROMETHEUS_v0.5_VERIFIED_2026-09-25(1).zip` | — |
| `&lt;USER_HOME&gt;/aion-gap-integrity-20260924` | `12a7cb8ef99e84ce50b766db0aea1592b3906f80` |
| `&lt;USER_HOME&gt;/icarus-causal-router` | `d95a53c70b04349fbef42c0a9dc35de87ca72f40` |
| `&lt;USER_HOME&gt;/Downloads/divine providence/_analysis/x/PROMETHEUS_ALL_CURRENT_WORK_FRESH_2026-09-24.zip` | — |
| `&lt;USER_HOME&gt;/oracle-review-20260923/ICARUS_ORACLE_CHECKPOINT_C_75_SOL_FOR_SOL_EXTRA_HIGH/icarus-oracle` | — |
| `&lt;USER_HOME&gt;/Downloads/divine providence/_analysis/x/PROMETHEUS_v0.5_VERIFIED_2026-09-25(1).bundle` | — |
| `&lt;USER_HOME&gt;/Downloads/divine providence/_analysis/x/PROMETHEUS_v0.4_VERIFIED_2026-09-25.bundle` | — |
| `&lt;USER_HOME&gt;/Downloads/divine providence/_analysis/x/PROMETHEUS_v0.2_SIBLING_BINDINGS_PLAN_2026-09-24.zip` | — |
| `&lt;USER_HOME&gt;/Downloads/divine providence/_analysis/x/PROMETHEUS_v0.3_VERIFIED_2026-09-25.bundle` | — |
| `&lt;USER_HOME&gt;/Downloads/divine providence/_analysis/x/PROMETHEUS_v0.1_2026-09-24.zip` | — |
| `&lt;USER_HOME&gt;/Downloads/divine providence/_analysis/x/PROMETHEUS_v0.2_SIBLING_BINDINGS_PLAN_2026-09-24.bundle` | — |
| `&lt;USER_HOME&gt;/Downloads/divine providence/_analysis/x/PROMETHEUS_v0.1_2026-09-24.bundle` | — |
| `&lt;USER_HOME&gt;/Downloads/divine providence/_analysis/x/PROMETHEUS_DESIGN_CHECKPOINT_2026-09-24.bundle` | `e057047ff1b5b7999186e8f649fb8a437b88b42c` |
| `&lt;USER_HOME&gt;/ICARUS-OPTIONAL-SOURCES/STARNET-74fcd5040ba0/test/native-connector-keychain` | — |
| `&lt;USER_HOME&gt;/ICARUS-OPTIONAL-SOURCES/STARNET-74fcd5040ba0/test/native-process-ownership` | — |

## 6. Numerical model banks, weights and receipts

The actual numerical bank is `<USER_HOME>/projects/icarus-numerical-models`. At latest metadata readback, all fourteen revision-pinned acquisition directories had a model.safetensors, config.json and acquisition-receipt.json (42 file metadata records). This verifies path presence, not current file hashes or correct inference. The receipt describes acquisition; verify license, hash, input contract and inference before use. Model IDs/revisions and exact filenames are in the model_locations array of findings-locations.json.

| Model / tokenizer | Revision-pinned directory name under numerical bank |
|---|---|
| ibm-granite/granite-timeseries-ttm-r3 | `ibm-granite--granite-timeseries-ttm-r3--ea17cfd2e3edcaea21eb8dcecd18bf88971482fa` |
| ibm-granite/granite-timeseries-tspulse-r1 | `ibm-granite--granite-timeseries-tspulse-r1--2e64fcdc2a06d3565dfadaf0065c0ab5055f80f2` |
| NeoQuasar/Kronos-mini | `NeoQuasar--Kronos-mini--f4e68697d9d5aed55cef5c96aabc3376bcad9f81` |
| NeoQuasar/Kronos-Tokenizer-2k | `NeoQuasar--Kronos-Tokenizer-2k--26966d0035065a0cae0ebad7af8ece35bc1fb51c` |
| amazon/chronos-bolt-tiny | `amazon--chronos-bolt-tiny--a0e552de83495b5c28c14c71c374f3e33280b340` |
| amazon/chronos-bolt-mini | `amazon--chronos-bolt-mini--251268337516a88e253628c43e1d26ec577b376b` |
| NeoQuasar/Kronos-small | `NeoQuasar--Kronos-small--901c26c1332695a2a8f243eb2f37243a37bea320` |
| NeoQuasar/Kronos-Tokenizer-base | `NeoQuasar--Kronos-Tokenizer-base--0e0117387f39004a9016484a186a908917e22426` |
| autogluon/chronos-2-small | `autogluon--chronos-2-small--ddec01313e50b6bc58ebaa92ede81bc24a3d9f9a` |
| ibm-granite/granite-timeseries-ttm-r2 | `ibm-granite--granite-timeseries-ttm-r2--d6a79570cac0f33d526601cd3a0fc7c80a8f9a2f` |
| Datadog/Toto-2.0-4m | `Datadog--Toto-2.0-4m--8306a9801cf98c0f5ffe4b2dcc8f496e616d84d9` |
| AutonLab/MOMENT-1-small | `AutonLab--MOMENT-1-small--411e288267f82cce86296dbe4d6c8bc533cc162f` |
| amazon/chronos-bolt-small | `amazon--chronos-bolt-small--772f3d25d38aec6d914c8949dab4462e2d46f5d8` |
| amazon/chronos-2 | `amazon--chronos-2--29ec3766d36d6f73f0696f85560a422f50e8498c` |

Other local banks and runtime locations:
- `<USER_HOME>/.ollama/models` — Ollama blobs/manifests, including possible partials; 34.64 GB prior logical metadata. Resolve tags via authorized local Ollama inventory; no automatic pulls or deletion.
- `<USER_HOME>/projects/icarus-pending-ollama-20261124.json` — owner pending queue, confirmed. Do not resume automatically.
- `<USER_HOME>/projects/umbra-polymind-models` — directory confirmed, contents and model qualification not established here.
- `<USER_HOME>/projects/umbra-polymind-acquisition-pinned/polymind_acquire.py` — observed filename; do not run acquisition automatically.
- `<USER_HOME>/projects/icarus-ml-runtime/installed-inventory.json` — observed package-inventory filename. Runtime interpreter Scripts/python.exe; package metadata Lib/site-packages. The existing gplearn/scikit-learn conflict remains documented, not fixed.
- `<SYNC_ROOT>/ICARUS-EXTERNAL-GITHUB/venvs` — hft, nautilus, quant, research. Runtime evidence in runtime-evidence.json.
- `<USER_HOME>/projects/umbra-polymind-runtime` — ONNX/tokenizer environment.
- `<USER_HOME>/projects/icarus-ml-research-sources` — fourteen cloned source locations indexed individually.

## 7. UMBRA, MYRIAD and POLYMIND work

- Canonical UMBRA repo: https://github.com/reppiks490/umbra-sovereign-worlds. Exact draft PR links: https://github.com/reppiks490/umbra-sovereign-worlds/pull/21 (MYRIAD) and PRs 24–33 (replace number in that URL). Historical heads and scope in SESSION_HANDOFF.md; verify current HEAD/CI before using.
- Native compute local checkouts: `<USER_HOME>/projects/umbra-native-compute-20261124` and `<USER_HOME>/projects/umbra-native-compute-review-20261124`. Confirmed directories; do not switch running worktrees.
- Within the relevant checked-out PR source, inspect mcp/polymind_router.mjs, mcp/owner_once.mjs and scripts/polymind_infer.py. These are earlier source observations; do not assume all are on main.
- MYRIAD pilot: `<USER_HOME>/projects/MYRIAD-v32-local-pilot-20261124`, its .training-venv and capability-acquisition directories. Latest selected listing contains evolution_receipt_audit_v91.py, evolution_proof_feedback_v90.py, evolution_skill_composition_v88.py, evolution_capability_fabric_v86.py and prior generations/tests/runner scripts; directory_entries lists observed immediate names. The private-pilot subtree is a candidate location for experiment artifacts: inspect counts, approved metadata and receipts only. Exact individual FP16/checkpoint paths and provenance beyond the earlier aggregate have not been established. Never publish private artifacts or execute unknown scripts.
- Proposed ICARUS Ω architecture is a design record in SESSION_HANDOFF.md, not a directory of completed trained agents. The private UMBRA plugin and scheduled research loops require their authorized app/automation interfaces; current installed plugin version and automation status need rechecking. Do not change them here.

## 8. System and dependency findings

Use runtime-evidence.json and findings-locations.json system/environment arrays for recorded locations and metadata. System directories, package caches and virtual disks are not part of the 275-root storage census. Main paths: C:/Windows, C:/Program Files, C:/Program Files (x86), C:/ProgramData, <USER_HOME>/AppData/Local, <USER_HOME>/AppData/Roaming, AppData/Local/Temp, AppData/Local/uv/cache, AppData/Local/pip/Cache, AppData/Local/npm-cache, .cache/huggingface, .ollama/models, AppData/Local/wsl, AppData/Local/Docker. WSL Ubuntu and docker-desktop were registered; virtual disks were not mounted or inspected. Windows credential store findings are presence/accessibility metadata only in runtime-evidence.json; protected system areas are not navigation targets for secret extraction. Do not bypass access controls, print tokens or open encrypted credential blobs.

## 9. Evidence gaps and continuation rules

Every observed project root is individually indexed; model file metadata and targeted checks are newly read back. The guide cannot provide precise file paths for unlocated original attachments, unknown archive members, uninspected private checkpoint descendants, protected areas, deleted artifacts or unrecorded four-month history. Mark these as unknown and recover only through authorized read-only evidence. Do not invent filenames or substitute similar artifacts. The previous Deep Research plan is not a completed report. Continue following CONTINUE.md. Keep the original source, historical copies, current runtime and owner-approved constraints intact.
