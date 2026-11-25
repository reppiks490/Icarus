# Git history storage opportunity — 2026-11-24

## Verified measurement
The reconciled 275-root local census measured 101,135,047,636 logical bytes across 1,774,395 files. Of this, **53,015,505,445 bytes (53.016 GB; 49.375 GiB; 52.42% of census)** were classified under .git directories. This includes object packs, refs, logs, indexes, LFS caches and other Git metadata, not exclusively commit history. Source: repository-sizes.json, measured on the authorized Windows machine, 2026-11-24 local time. No repository was modified or cleaned.

## Largest Git-storage contributors (ranked by .git bytes)
| Local repository | Total logical GB | .git GB | .git share | Exact .git bytes |
|---|---:|---:|---:|---:|
| `&lt;SYNC_ROOT&gt;/ICARUS-GITHUB-DOWNLOADS/JerBouma/FinanceDatabase` | 14.972 | 14.754 | 98.5% | 14,753,996,337 |
| `&lt;SYNC_ROOT&gt;/ICARUS-EXTERNAL-GITHUB/source/ccxt__ccxt` | 9.650 | 9.132 | 94.6% | 9,132,449,951 |
| `&lt;SYNC_ROOT&gt;/ICARUS-EXTERNAL-GITHUB/source/ClickHouse__ClickHouse` | 12.815 | 2.870 | 22.4% | 2,870,131,381 |
| `&lt;SYNC_ROOT&gt;/ICARUS-EXTERNAL-GITHUB/source/openbq-org__OpenBB` | 2.728 | 2.548 | 93.4% | 2,548,201,158 |
| `ICARUS-OPTIONAL-SOURCES/STARNET` | 5.947 | 2.337 | 39.3% | 2,336,801,508 |
| `&lt;SYNC_ROOT&gt;/ICARUS-GITHUB-DOWNLOADS/grafana/grafana` | 2.372 | 2.145 | 90.4% | 2,144,754,802 |
| `&lt;SYNC_ROOT&gt;/ICARUS-GITHUB-DOWNLOADS/heygen-com/hyperframes` | 2.036 | 1.113 | 54.7% | 1,113,191,079 |
| `&lt;SYNC_ROOT&gt;/ICARUS-EXTERNAL-GITHUB/source/dgunning__edgartools` | 3.571 | 0.919 | 25.7% | 919,150,595 |
| `&lt;SYNC_ROOT&gt;/ICARUS-GITHUB-DOWNLOADS/vectorize-io/hindsight` | 1.127 | 0.853 | 75.7% | 853,251,249 |
| `&lt;SYNC_ROOT&gt;/ICARUS-GITHUB-DOWNLOADS/polakowo/vectorbt` | 0.966 | 0.795 | 82.3% | 794,903,017 |
| `&lt;SYNC_ROOT&gt;/ICARUS-GITHUB-DOWNLOADS/pingdotgg/t3code` | 2.255 | 0.753 | 33.4% | 752,877,547 |
| `&lt;SYNC_ROOT&gt;/ICARUS-GITHUB-DOWNLOADS/ruvnet/ruflo` | 0.835 | 0.683 | 81.9% | 683,160,968 |
| `&lt;SYNC_ROOT&gt;/ICARUS-EXTERNAL-GITHUB/source/duckdb__duckdb` | 0.931 | 0.651 | 69.9% | 650,759,941 |
| `&lt;SYNC_ROOT&gt;/ICARUS-EXTERNAL-GITHUB/source/apache__datafusion` | 1.530 | 0.642 | 41.9% | 641,596,024 |
| `&lt;SYNC_ROOT&gt;/ICARUS-GITHUB-DOWNLOADS/anomalyco/opencode` | 0.771 | 0.626 | 81.3% | 626,474,815 |
| `&lt;SYNC_ROOT&gt;/ICARUS-EXTERNAL-GITHUB/source/Arize-ai__phoenix` | 0.681 | 0.609 | 89.4% | 609,284,847 |
| `&lt;SYNC_ROOT&gt;/ICARUS-GITHUB-DOWNLOADS/grafana/loki` | 0.949 | 0.602 | 63.4% | 602,043,870 |
| `&lt;SYNC_ROOT&gt;/ICARUS-GITHUB-DOWNLOADS/kungfu-systems/kungfu` | 0.914 | 0.601 | 65.7% | 600,727,730 |
| `&lt;SYNC_ROOT&gt;/ICARUS-GITHUB-DOWNLOADS/K-Dense-AI/scientific-agent-skills` | 0.775 | 0.484 | 62.4% | 483,686,168 |
| `&lt;SYNC_ROOT&gt;/ICARUS-GITHUB-DOWNLOADS/NationalSecurityAgency/ghidra` | 0.772 | 0.442 | 57.2% | 441,736,007 |

Top 20 account for 43,559,178,994 bytes (82.2% of measured Git bytes). Prioritize these for inspection. FinanceDatabase and CCXT alone have 23,886,446,288 logical .git bytes; these are candidates for investigation, not a promise of recoverable storage.

## What the number does and does not mean
- Logical file lengths are not allocated NTFS clusters, and this census is not a whole-drive inventory. Hard links, compression, sparse files, shared object stores, LFS, cloud sync and reparse points may materially change physical usage.
- 217 distinct verified HEAD hashes do not prove 217 distinct projects or duplicate object stores. Equal HEADs do not prove equal branch/tag/ref coverage, dirty working trees, stashes, reflogs, LFS objects, alternates or unpublished work.
- A large pack may already be efficiently compressed and contain essential reachable objects; normal garbage collection may reclaim little. A shallow clone or source-only snapshot can be smaller but cannot replace preserved unique history without explicit owner approval and evidence.
- Git storage savings are not currently verified. **Confirmed reclaimable bytes: unknown.** Theoretical upper bound of removing the measured Git metadata is not a safe or realistic savings estimate. Never remove .git to achieve this figure.

## Non-destructive next-agent procedure
1. Recheck free space and currently running jobs. Resolve local paths on the authorized device; do not publish remote URLs with credentials or account-identifying paths.
2. Measure physical allocation using supported Windows file metadata, track file IDs/hardlinks once per volume, detect sparse/compressed/offline files, and avoid hydration. Confirm repository gitdir/common-dir locations and any external worktree metadata.
3. For each prioritized repo, use read-only Git inspection with GIT_OPTIONAL_LOCKS=0, GIT_NO_LAZY_FETCH=1, and network disabled where feasible. Inspect git count-objects -vH, refs, stash presence, worktree list, shallow/partial clone state, alternates, and LFS object metadata. Do not run unknown repo hooks, filters or scripts. Do not read credential values. Determine unique local commits and uncommitted/untracked state before proposing any replacement.
4. Compare exact histories only with authorized read-only remote evidence, preferably existing refs; no unnecessary network fetches or spending. Identify genuinely redundant immutable third-party checkouts; protect owner repositories, active branches, research results, old handoffs and unique local revisions.
5. Produce a per-repo proposal with measured allocated bytes, required retained history, candidate method, projected savings range, temporary-space needs, risk, rollback and validation. A source-only checkout or new shallow clone is a separate candidate; never silently overwrite an existing checkout. Account for sync propagation and retained versions.
6. Request explicit owner approval before any mutation, cleanup, repack, reflog expiration, pruning, deletion, migration or re-clone. Preserve a verified recovery copy with all required objects and refs; do not perform large repacks with insufficient disk headroom. Verify before and after allocation, source identity, branches and runnable checks, and record exact evidence.

## Boundaries
No destructive action was taken. No force push, Git history rewrite, automatic cleanup, duplicate removal or live runtime change is authorized by this finding. Preserve research integrity over speculative space savings. This is a high-priority storage optimization investigation, not an execution directive.
