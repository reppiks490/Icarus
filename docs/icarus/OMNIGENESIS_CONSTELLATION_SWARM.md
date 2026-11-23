# ICARUS OMNIGENESIS — Sovereign Constellation Swarm

Status: implemented on development branch agent/omnigenesis-phase-01-foundation in DRAFT PR #503. No merge, live deployment, broker connection, authenticated external market data, autonomous strategy promotion or claim of sentience.

## Actual GitHub execution topology

The Constellation is a finite scientific research fabric, not merely a themed dashboard or a collection of freeform LLM prompts. It combines three nested GitHub Actions workflows with a deterministic Python plan/worker/tribunal implementation.

1. .github/workflows/omnigenesis-constellation.yml is the top-level plan dispatcher. Pull requests and explicit dispatch may invoke it; hourly minute-17 UTC scheduling becomes active ONLY after review and merge to the default branch. A SHA-256-derived run seed determines a fixed 6-lane by 2-shard matrix. Concurrency cancels superseded source revisions; max-parallel is six. No paid providers, credentials, trade orders or dynamic code installation.
2. .github/workflows/omnigenesis-constellation-worker.yml is a reusable workflow called separately for each of 12 specialist/shard combinations. Each ubuntu-24.04 Python 3.11 process independently validates the exact plan ID and role assignment, executes only the assigned bounded scientific harness, and uploads one seven-day small derived receipt.
3. .github/workflows/omnigenesis-constellation-tribunal.yml is a separate reusable final gate. It downloads the sealed plan and all 12 calling-run worker artifacts. Missing, conflicting, duplicated, extra, altered or mismatched receipts fail the run. Successful deterministic same-revision re-execution yields a tribunal receipt retained for 14 days; scientific approval and live release remain prohibited.

Source: icarus_engine/omnigenesis/constellation.py. Methods: build_plan, run_worker, arbitrate, and CLI plan / worker / tribunal. Contracts: versioned constellation plan, per-worker research receipt, and tribunal verdict, each with content-addressed SHA-256 ID and immutable research-only authority flags. The worker plan contains exactly 12 registered roles, no operator-defined code and no broker permissions.

## Six distinct disciplines; two deterministic evidence shards each

| Role | Real code exercised | Scientific truth boundary |
| --- | --- | --- |
| CHRONOS | historical_paper.run_historical_paper_replay | Synthetic historical fixture with explicit received/open clocks; hypothetical fills only, never actual venue executions |
| EXECUTION | paper_harness.run_paper_execution | Deterministic toy strategy; fee/slippage/drawdown stress, no real profit |
| RECONCILIATION | offline_order_router.replay_offline_order_router | Mock order acknowledgments, fills, cancellation race and position assertions |
| NEMESIS | adverse mutation attacks against offline order router | Reject injected API tokens, attempted live mode, conflicting event identity |
| WORLDLINE | umbra_bridge.audit_umbra_worldlines | Internally consistent fabricated UMBRA v5 paired outcomes; independent UMBRA engine replay remains false |
| MEMORY | agent_workflow and ResearchLedger | Dependency execution, chained receipts and idempotent local derived-artifact storage |

Each shard derives a distinct deterministic case seed using SHA-256 over the run seed, role and shard. These are deliberately small engineering scenarios, not a statistically representative market dataset, qualified MBO tape or independent machine-learning experiments.

## Tribunal behavior

The tribunal must see one complete, registered, nonduplicate receipt for every planned specialist/shard. It validates each worker's content hash, exact plan lineage and no-execution/no-promotion flags, then independently RECOMPUTES results with the same code revision and requires exact equality. This detects missing and modified artifacts, not a bug shared by both computations. A run may only report RESEARCH_CONSISTENCY_PASS_PENDING_INDEPENDENT_REVIEW. It may not report certified external origin, real profitability, live market execution, automatic strategy promotion, scientific independent replication or a successful production deployment.

Hash identities do not constitute a signed provider attestation. No on-disk customer data, market credentials, broker secrets, licensed raw vendor payloads or private financial account records are written into artifacts. GitHub-hosted workflow jobs are ephemeral compute processes, not always-running conscious entities.

## Verification and deployment gates

- Tests: tests_engine/test_omnigenesis_constellation.py covers all 12 specialists and the complete local tribunal, missing/extra/forged/duplicated evidence, plan authority mutation, false profit claims, invalid lane/shard, local CLI write-once behavior, malformed and symlinked inputs. tests_engine/test_omnigenesis_historical_paper.py covers the strict Phase 21 late-arriving event clock and declared-file integrity contracts.
- The existing OMNIGENESIS research-only CI discovers all tests_engine/test_omnigenesis*.py. Its dedicated Python tests alone are not end-to-end orchestration evidence. **E2E VERIFIED on exact source commit `8af18d360d8ec1f94a5f9c6612b4181830768031`: [research-only Actions run 45121812267](https://github.com/reppiks490/Icarus/actions/runs/45121812267) completed SUCCESS, all 16 actual jobs SUCCESS (Python, mobile TypeScript, sealed dispatcher, 12 reusable specialist/shard jobs, reusable tribunal); 14 nonexpired artifacts included the plan, 12 unique worker receipts and tribunal.** Nested reusable workflow calls, same-run artifact transfers and independent-job fanout were genuinely exercised. This is *same-code deterministic evidence consistency*, NOT independently validated scientific claims, real data, financial performance or deployment. After any source or workflow change, recheck the new exact HEAD instead of treating the old CI as current.
- GitHub Actions schedule in a draft PR is INACTIVE. It can only run from the default branch after explicitly authorized merge. The existing ChatGPT ICARUS Sovereign Evolution hourly task is separate and remains bounded/non-Codex.
- GitHub concurrency, minute-hourly trigger, job timeouts and seven/fourteen day artifact retention cap resource and storage consumption; no claim of unlimited continuous compute. Every run is self-contained: it does not establish distributed consensus, durable cross-run task leases or autonomous retries.

## Reproducible operator CLI

From an existing authorized checkout, with an unused output path:

    python -m icarus_engine.omnigenesis.constellation plan --seed 49021 --output constellation-plan.json
    python -m icarus_engine.omnigenesis.constellation worker --plan constellation-plan.json --lane chronos --shard 0 --output worker-chronos-0.json

Run the remaining registered lane/shard combinations and place all twelve worker-<lane>-<shard>.json files in a single directory:

    python -m icarus_engine.omnigenesis.constellation tribunal --plan constellation-plan.json --worker-dir ./worker-receipts --output constellation-tribunal.json

Existing output files cannot be overwritten. These paths are examples, not automatically generated user files.

## Roadmap beyond this code, not yet shipped

- Independently authenticated, licensed provider/venue market data and actual MBO depth/queue reconstruction; real order latencies, rejections, partial fills, fees, tick/roll calendars and calibration.
- Independent external APEX/DAEDALUS implementations, data-rights attestations, purged out-of-distribution holdouts, multiple-testing corrections, signed provenance and standardized adverse network-event injection.
- Durable ASCENDANCY-owned task leasing, persistent idempotency, checkpoint/resume and bounded recovery; current worker fanout is ephemeral CI.
- Optional externally connected agents only after tool-specific permissions, no-spend provider rights and isolation are verified. Mentions of apps/plugins do not prove actual use or entitlement.
- Native dashboard and iPhone observability of real workflow states and receipts with measured frame latency, reduced-motion support and separate authenticated read-only transport. No invented public live swarm URL.
- Explicit owner-approved trading authorization and independent broker sandbox certification; user currently prohibits live broker arming, so research integration cannot grant itself trade execution.

Source remains in ICARUS draft PR #503, UMBRA remains a separately versioned synthetic-world source, and live chatgpt.site UMBRA experiences remain untouched. The stale live federation peer blocker is tracked in ICARUS issue #504. Prioritize exact-HEAD GitHub Actions evidence, independent review, and safe scoped repairs over feature-count claims.

Coordination session in reppiks490/icarus-owner-actions: chatgpt-20261123-omnigenesis-constellation-swarm.


## Phase 24 — Bounded missing-shard recovery and archived checkpoints

**Implementation on this draft branch; exact-HEAD CI/E2E must be checked before acceptance.** The original 12-worker plan, specialist contracts and separate Evidence Tribunal remain unchanged. New source: icarus_engine/omnigenesis/constellation_recovery.py.

The recovery planner accepts only source-valid, registered, nonduplicate worker receipts. It invokes the SAME deterministic worker implementation to verify each accepted receipt, including all authority and source-derived values. It saves a versioned SHA-256 content-addressed checkpoint with the exact plan identity, GitHub source revision, run ID, run attempt, accepted receipt set and missing tasks. Existing receipts cannot be removed or changed when a checkpoint is continued; source SHA/run/attempt changes fail. A retry may run only ONCE, only for missing registered shards. Zero valid receipts, exhausted retries, extra artifacts or malformed input result in a failure requiring review, not a rewritten pass.

The parent workflow .github/workflows/omnigenesis-constellation.yml now nests a recovery-plan job after the initial matrix, a conditional retry-workers matrix and an independent recovery-finalize job. Recovery-finalize checks complete evidence before it permits the existing final tribunal. In normal runs (all 12 pass) the retry matrix is empty and no extra workers run. In interrupted runs, only missing specialists are retried; if the original worker job failed, the original GitHub job failure remains visible even if the later retry and tribunal pass. No source permissions, broker capabilities, unbounded self-healing, automatic CI greenwashing, or independent provider authenticity are conferred.

The recovery checkpoint is an artifact retained for 14 days. This is ARTIFACT-BACKED REPLAYABILITY, not durable indefinite state or exactly-once orchestration across arbitrary GitHub runs. A later replay could supply a prior checkpoint only if the original immutable plan, exact source SHA/run identity and all accepted worker receipts are available; there is currently no automatic cross-run task lease manager, secret-bearing state database or production scheduler migration. A same-code worker recomputation and SHA-256 digest are consistency checks, not cryptographic signatures.

Adversarial tests: tests_engine/test_omnigenesis_constellation_recovery.py, verifying 12/12, 11/12, 0/12, one-time continuation, exhausted retry, immutable accepted receipts, plan/source/run binding, duplicate or unregistered workers, forged statuses, CLI exclusive writes, malformed JSON, symlinked inputs and filename mismatch. These tests must pass at the exact source SHA, and an actual GitHub Actions nested rehearsal must pass plan → workers → recovery-plan → conditional retry → recovery-finalize → tribunal before Phase 24 is declared operational.

Next upgrade, NOT implemented: independently signed immutable cross-run journal backed by authorized durable storage, strict repo/commit ancestry and data-rights validation, crash-resume after expiry, proved order/position reconciliation against broker sandbox, read-only authenticated iPhone telemetry with measured frame times, incident classification and human-reviewed exception routing. research_only=true, execution_authorized=false, production_decision_authorized=false, auto_promote=false remain mandatory.


## Phase 25 — Completed-only observational evidence and authenticated research-snapshot compatibility

**Implemented on the draft ICARUS branch.** Source: icarus_engine/omnigenesis/constellation_observation.py. A caller supplies the sealed plan, the complete Phase 24 checkpoint and the real completed tribunal JSON. If a worker retry occurred, the original partial checkpoint is also REQUIRED. The module revalidates the plan/worker lineage, complete checkpoint content hash, monotonic predecessor chain and exact same-revision tribunal result. Failed, incomplete, changed, unsigned-by-digest or authority-escalated observations are refused.

The output is a versioned, content-addressed, data-minimized observation describing exactly twelve COMPLETED_RESEARCH_ONLY workers with receipt IDs. It has active_workers_now=0, snapshot_is_live=false, github_api_provenance_verified=false, source_commit_attested=false, independent_scientific_validation=false, real_profitability_verified=false, release_authorized=false and broker_order_count=0. The named GitHub run/source revision comes from the checkpoint's CALLER-DECLARED context, not an authenticated GitHub API response. This is an audit of local source/replay consistency, not a signed remote workflow-state certificate.

The tribunal reusable workflow .github/workflows/omnigenesis-constellation-tribunal.yml now downloads the final and initial recovery checkpoint artifacts after the original twelve-worker tribunal succeeds, constructs the observation and uploads omnigenesis-constellation-observation (14-day retention). If the observation cannot be verified, that tribunal job fails rather than writing a fake status. No public website, live UI gateway, account credentials or provider/financial data are touched.

ICARUS already exposes an authenticated, read-only research snapshot from ResearchLedger.snapshot(). A new ResearchLedger.append_constellation(plan, checkpoint, tribunal, predecessor=None) method verifies all input evidence again and writes ONLY a small six-field derived artifact summary to the existing SQLite scientific ledger, never the full worker receipts, raw market data or caller-supplied run metadata. Its artifact kind is constellation_observation, its status is LOCAL_REPLAY_ONLY, and metric 12 denotes twelve COMPLETED specialist receipts—not twelve currently active workers. Existing dashboard/mobile read surfaces can display this derived record after explicit local import. No new HTTP write route is introduced.

Example explicit offline import on an authorized local checkout, using actual artifacts from ONE source/run:

    python -m icarus_engine.omnigenesis constellation-import \
      --plan ./constellation-plan.json \
      --checkpoint ./checkpoint-final.json \
      --tribunal ./constellation-tribunal.json \
      --root /path/to/icarus

For an actual recovery attempt, also supply --predecessor ./checkpoint-0.json. The input paths above are examples, not preinstalled files. Imports are idempotent for identical evidence and reject tampering, forged status, missing shards, missing recovery predecessor and any attempted authority escalation. CLI output explicitly reports LOCAL_REPLAY_ONLY and github_api_provenance_verified=false.

Unit regressions: tests_engine/test_omnigenesis_constellation_observation.py (normal/recovered completed runs, forged tribunal, partial checkpoint, predecessor mismatch, immutable stored summary, CLI exclusive creation and import). The separate recovery tests assert the GitHub workflow retry condition has a failure-aware always() guard. Dedicated OMNIGENESIS Python/mobile tests passed at a source commit preceding this documentation; the new tribunal artifact step and workflow-level transfer require exact-head GitHub Actions E2E proof.

**Still missing:** automatic authenticated GitHub-to-local polling/streaming, verifiable provenance from GitHub's own API, durable cross-run signed incident history beyond 14-day artifacts, native iPhone real-time activity rendering and device FPS measurements, independently authenticated market data/exchange fills, and actual broker-safe live execution certification. No claim of those capabilities should be made from a successful local replay or a synthetic worker animation.
