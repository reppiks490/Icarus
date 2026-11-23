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
- The existing OMNIGENESIS research-only CI discovers all tests_engine/test_omnigenesis*.py. A passing dedicated Python suite verifies the engine but NOT the GitHub reusable-workflow scheduling and artifact transfer path. An actual independently named Constellation Swarm Actions run with plan, all 12 individual worker jobs and the final tribunal is required before declaring the workflow operational.
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
