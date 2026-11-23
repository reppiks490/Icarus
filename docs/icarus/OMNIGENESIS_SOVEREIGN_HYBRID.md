# ICARUS OMNIGENESIS × UMBRA Ω — Sovereign Hybrid Research Protocol

**Status:** Source implemented on ICARUS development branch, PR #503; dedicated Python/mobile verification passed on SHA 3925deeb92289821c0bdece584bea127036dadd1. **Draft/unmerged, not deployed; independent integration, live vendor provenance and real iPhone QA remain unverified.**

## Identity and architectural separation

ICARUS retains the authority, scientific memory, data contracts and native desktop/iPhone research read surfaces. UMBRA Sovereign Worlds remains separately versioned under https://github.com/reppiks490/umbra-sovereign-worlds . Its v5 pairedExperiment() JSON output is a deliberately synthetic research source, not a licensed market feed. The live https://umbra-focus-orbit.orange-cake-1541.chatgpt.site/ is a separate deployed product with a Living World, Decision Atlas and Focus Timer, not an ICARUS endpoint and not modified.

This is a hybrid **scientific evidence protocol** and explicitly invoked agent research executor. It is not a merged game engine, full-precision exchange digital twin, live feed connector, autonomous agent swarm, continuously scheduled workflow, or broker trading integration.

## Implemented source map

- icarus_engine/omnigenesis/data_intake.py — Phase 17: inspect explicit local JSONL event tapes. The operator provides raw market bytes plus a typed manifest, 64-hex SHA-256, claimed provider/venue/license, capture cutoff, asset and contract-roll schedule. Validate exact bytes, strict event keys, observations/arrival clocks, bounded receive-time plus sequence ordering, positive integer tick indices and sizes, symbol and roll membership, finite file/line/record/byte bounds. Does not call vendor APIs, persist raw tape, trust unsigned manifest identity or verify feed entitlements. Its result has evidence_kind DECLARED_OBSERVED_BYTES_CHECKED and source_authenticity_verified false.
- icarus_engine/omnigenesis/umbra_bridge.py — UMBRA v5 paired experiment adapter: versioned strict schema, exactly expected hash32 replicate seed schedule, policy ranges, baseline-treatment difference and aggregate sample statistics. It returns evidence_kind SYNTHETIC_MODEL_INTERNAL. It does NOT independently rerun the UMBRA engine or validate the reporter's Git source claim. All real-world validity and production flags stay false.
- icarus_engine/omnigenesis/agent_workflow.py — Phase 18 deterministic research task DAG. Compile and seal 1–24 typed tasks, reject unknown operators, cycles, duplicate identifiers, missing prerequisites, forged authority or oversized input and over-budget estimates. Explicitly invoked in-process executor supports prime, synthetic_book, market_intake, umbra_worldline and formal. Produces PASS/FAIL/BLOCKED receipt chains and dependency failure isolation. No shell, generated code evaluation, paid API, network, scheduling, broker access, model auto-promotion or synthetic→observed reclassification. Compute estimates are planning admission limits, not enforced runtime deadlines.
- icarus_engine/omnigenesis/ledger.py — Existing research ledger extended to accept immutable validated agent_workflow summary artifacts. Checks run hash, receipt sequence hashes, status/count consistency, no execution authority. Existing authenticated read-only /api/omnigenesis desktop/mobile data snapshot can display these as genuine recorded derived artifacts. No new web write routes.
- icarus_engine/omnigenesis/__main__.py — Local CLI commands market-intake, audit-umbra and workflow; workflow only executes on explicit --execute, and only persists derived research to existing ledger when --root is given. --output uses exclusive creation, no overwrite.
- tests_engine/test_omnigenesis_data_intake.py, test_omnigenesis_umbra_bridge.py and test_omnigenesis_agent_workflow.py — adversarial tests for timestamp order, future leakage, SHA mismatch, duplicate JSON object keys, contract rolls, invalid ticks, suspicious synthetic data, forged UMBRA aggregates/seeds, task DAG cycles and authority escalation, tampered receipt chains and immutable CLI ledger persistence.

## Commands from canonical ICARUS repository

  python -m pytest tests_engine/test_omnigenesis*.py -q

  python -m icarus_engine.omnigenesis market-intake path/to/local_tape.jsonl path/to/manifest.json

  python -m icarus_engine.omnigenesis audit-umbra path/to/paired_worldlines.json --claimed-source-commit 0123456789012345678901234567890123456789

  python -m icarus_engine.omnigenesis workflow path/to/workflow.json

  python -m icarus_engine.omnigenesis workflow path/to/workflow.json --execute --root . --output research/workflow_receipt.json

These are illustrative file paths; no authentic market tape or approved license has been ingested in this work. All processing is local.

Workflow JSON root: schema_version = icarus-omnigenesis-agent-workflow-v1; name (3–100 chars); compute_budget_seconds (1–3600); tasks (1–24). Each task: task_id, operator, depends_on [ids], parameters matching its operator, estimated_compute_seconds. The operators cannot be extended with arbitrary executable text; changes require code review.

## Scientific truth tiers

- MATHEMATICAL_WITHIN_GRAMMAR: prime and formal finite numeric guard proof. Not a proof of market profitability, universal intelligence or future regimes.
- DECLARED_OBSERVED_BYTES_CHECKED: local JSONL SHA-256 and declared timestamp/roll schema passed. The expected digest was supplied by the same operator. Vendor identity, source-signature trust, license and exchange sequence completeness are NOT independently verified.
- SYNTHETIC_MODEL_INTERNAL: UMBRA worldlines structurally and arithmetically consistent. Not empirical causality or observed market facts; world engine replay not verified.
- SYNTHETIC: ICARUS toy limit-order-book experiment. Not exchange MBO or actual fills.
- EXPLORATORY: one-feature ICARUS historical hypothesis result; external statistical/market qualification blocked.
- REVIEW_REQUIRED: failed/blocked workflow or an incomplete external approval gate. Even an all-PASS research workflow remains unqualified for production.

APEX owns evidence truth, DAEDALUS/AEGIS independent qualification, ASCENDANCY governed scheduling. ICARUS/Pulse remains sole owner of broker and trading-execution controls. Research authority flags always: research_only true, execution_authorized false, production_decision_authorized false, auto_promote false.

## Phase 17 event-order precision clarification

Normalized historical files are checked against a **global nondecreasing received timestamp** and a **strictly increasing sequence per declared contract**. A later receive timestamp must never conceal a regressed sequence for the same contract. Different contract symbols may reset sequence counters after a roll, so a globally increasing sequence is not assumed. The current format has no venue-channel/packet gap map: passing the ordering check does **not** establish exchange sequence completeness, authentic MBO, provider source identity or tradeability. Negative tests exercise per-contract regression, allowed contract reset and arrival-clock reversal. The exact source/file SHA still comes from an operator-authored manifest until NEXUS independent evidence is connected.

## Unfinished integration and next engineering gates

1. Current standalone PR #503 is DRAFT. Check complete GitHub Actions at its current HEAD; a dedicated workflow passing does not establish all canonical Linux/Windows, Expo installation, UI workspace browser or portfolio Playwright success.
2. Phase 17 digest, source and venue metadata are all caller claims. Extend only through NEXUS/ARGUS independent verified vendor receipts and licensed instrument-master data, official contracts/ticks/roll/sequence gaps and bitemporal history. No personal finances, real brokerage or trading credentials. No paid API ingestion without authorization. Do not mislabel a local digest match as a signed vendor attestation.
3. Extend failure handling with cancellation/runtime isolation, explicit idempotent retries, checkpoints, independent reviewer agents and verified external attestations; current DAG is deterministic local execution, not continuous autonomous workers. Honor existing ASCENDANCY rather than adding a second governor.
4. Add actual real market order-book evidence, venue latencies, queue, slippage, fees, spread, missing liquidity, risk and independent OOD replication before claiming high-fidelity market simulation or profitable alpha.
5. Independently replay pinned UMBRA v5 source rather than trusting internally consistent paired report only. Do not use the UMBRA archive PR #4 until its accessor/toJSON security finding is fixed/reviewed. Do not alter the original live site's three products or browser data.
6. Genuine cinematic desktop and native iPhone observatories require separately measured motion, frame intervals (p50/p95), touch selection, low-power and reduced-motion behavior. Existing OMNIGENESIS artifacts are already displayed as truthful research nodes but a dedicated multi-scale hybrid renderer is NOT implemented.
7. Human-reviewed merge/deployment decision only after canonical CI, real device and scientific gate signoff. No force push, blind merge, self-promotion, real trading or unattended Codex-driven loop.

**Verification evidence is per exact source SHA. This document is a continuing source map, not a production release certificate.**


## Phase 19 — Causal synthetic paper execution

**Status: implemented on the DRAFT ICARUS PR #503 branch, not deployed, not a broker connection. CI result depends on exact current HEAD and independent review.**

New source: icarus_engine/omnigenesis/paper_harness.py. The paper executor produces 100–2048 seeded, fabricated bars; reads only already-closed prices when making an SMA-cross decision; schedules a target-position action for an open **at least one bar later**. Position books settle in integer ticks and cents, with 1–5 synthetic contracts, adverse configurable fill slippage and per-contract fees. It handles long/short/flat and reversals, cash mark-to-market drawdown, max loss and maximum order-event guards, plus final synthetic liquidation. A close-based loss trigger exits no earlier than the *next open*, never a retroactive guaranteed stop. Price gaps and fees may exceed a requested stop budget. The fill event budget allows emergency liquidation; no real order has been sent.

New second operator: tournament_paper_strategies takes 2–8 preregistered SMA variants, ranks them by training-segment synthetic P&L minus drawdown on the first 70% of the same fabricated timeline, selects one by deterministic tie break and scores **only that chosen** strategy on the latter 30%. No winner is promoted or granted production/execution authority. The reproducible holdout is NOT access controlled; repeated retries and user seed selection can overfit it. Independently collected exchange data, cost/queue evidence, OOD validation and independent review remain absent.

Phase 18 DAG's allowlist was extended by two *typed research operators*, paper_execution and paper_tournament. Each accepts one spec object, hashes the underlying research receipt and persists only a bounded synthetic-summary record via the existing, authenticated, read-only OMNIGENESIS scientific ledger. Direct CLI commands:

    python -m icarus_engine.omnigenesis paper ./operator-paper-config.json
    python -m icarus_engine.omnigenesis paper-arena ./operator-tournament-config.json

The paths above are illustrative: these input files are **not** automatically included or authenticated. For the paper config the exact JSON keys are schema_version, seed, bars, strategy, execution, risk. Schema version is icarus-omnigenesis-paper-execution-v1. Strategy: kind SMA_CROSS, fast integer 2–30, slow integer 4–80 (fast < slow), direction trend or reversion. Execution: contracts (1–5), tick_value_cents (positive integer), fee_per_contract_cents (nonnegative integer), slippage_ticks (1–100) and latency_bars (1–10). Risk: initial_cash_cents, max_loss_cents, max_drawdown_cents and max_order_events. Arena schema is icarus-omnigenesis-paper-arena-v1, replacing strategy with a 2–8-member candidates array; requires >=160 bars.

**Falsification tests:** tests_engine/test_omnigenesis_paper_harness.py and test_omnigenesis_agent_workflow.py check seeded reproducibility, later-open fills, no broker capability, realistic adverse cost ordering within the toy model, losses and order-event killing, forced flat end, invalid/extra API-key fields, train/holdout separation, and receipt/ledger transparency. Passing tests establish implemented code constraints, not market edge.

**Missing before any production rollout:** independently authenticated licensed historical market data (provider/channel/contract/calendar), order-book queue/partial-fill model, exchange slippage/fees, robust no-lookahead backtests, OOD/purged holdouts, multiplicity and data-mining penalties, broker sandbox certification, idempotent order entry/cancel/reconcile, connectivity failures, live position risk monitoring, full audit + independent APEX/DAEDALUS qualification and explicit owner-approved risk/capital limits. Current paper configuration values are research assumptions, not authoritative futures contract specifications. Self-improvement here means bounded parameter comparison and falsifiable receipt collection. There is no basis to assert sentience or consciousness.

**Knowledge delta / Akinator provenance:** Before: research DAG and synthetic order book, but no strategy signal-to-delayed-fill accounting. After: causal paper execution, conservative cost knobs and risk switches plus training-only challenger evaluation. Decision: research-only, isolate live trading. Rejected alternative: connecting broker/API secrets or letting generated strategies self-promote. Verification: current-HEAD Actions and adversarial tests, independently reviewed before merge. This record becomes stale if authentic market feeds, margin, order routing or execution venue behavior changes.


## Phase 20 — Offline order lifecycle, idempotency and reconciliation

**Implemented only on draft PR #503:** source
icarus_engine/omnigenesis/offline_order_router.py; adversarial tests
tests_engine/test_omnigenesis_offline_order_router.py; Phase 18 workflow
operator offline_order_router and explicit offline-router CLI. This module
has **no broker adapter, network, credentials, real order entry or fill
claims**. It evaluates strict user-authored messages in an OFFLINE_SANDBOX
state machine.

Typed actions: SUBMIT, ACK, FILL, CANCEL, CANCEL_ACK, REJECT, HALT and
RECONCILE. Every unique message must have a stable event ID, strictly
increasing numeric sequence and timezone-aware increasing receive clock.
Exact event-ID replay with unchanged bytes is deduplicated *within the
current replay only*; conflicting duplicate content fails. This is NOT
durable exactly-once broker execution. Client order IDs and execution IDs
are unique, fills never exceed the submitted order quantity, fills can
arrive before ACK or while cancellation is pending, delayed ACK cannot
reopen terminal orders, and fills after confirmed cancellation are
rejected pending an independently verified exchange audit.

Worst-case exposure is bounded by the current signed position **plus all
in-flight same-direction quantities**, without netting unconfirmed
opposite orders. An explicit HALT forbids new submits; previously
submitted simulated orders can still produce late fills and should be
canceled/reconciled outside this model. A RECONCILE mismatch latches
HALT but cannot prove the external position snapshot is authentic.
Its report therefore has actual_exchange_reconciled=false,
source_authenticity_verified=false, broker_order_count=0 and no
profitability or production authority.

Workflow integration: a clean mock replay yields a bounded typed
SIMULATED_ORDER_LIFECYCLE research receipt. A safety HALT or
reconciliation mismatch **fails the DAG operator and blocks downstream
tasks**, even if the stand-alone replay returned an informative report.
The existing append-only research ledger stores only derived run
summaries; there are no new write APIs for broker execution.

Local example command (provide your own typed JSON input):

    python -m icarus_engine.omnigenesis offline-router ./sandbox-messages.json

The root JSON keys are schema_version
icarus-omnigenesis-offline-order-router-v1, mode OFFLINE_SANDBOX, asset,
max_position_contracts, max_single_order_contracts, max_active_orders,
and events (1–2000). Events always include event_id, sequence,
received_at and action; action-specific fields are validated exactly.
A result cannot be promoted to production by changing this mode,
adding a broker token, or inserting an unapproved action.

**Unfinished real execution gates:** real broker sandbox, separate
account-scoped signed idempotency keys with durable storage, exchange
execution-ID provenance and async out-of-order repair, actual order state
snapshot reconciliation, crash/restart replay, reconnect/timeout,
kill switch acknowledgment and external cancel-on-disconnect, risk
position and margin guardrails, market/venue limit rules, account
permissions, independent APEX/DAEDALUS failure injection, and explicit
owner-approved live risk policies. Synthetic tests cannot prove those.
Order "profit" is not calculated here; Phase 19's P&L is purely toy
simulation.

**Automation:** GitHub workflow
.github/workflows/omnigenesis-offline-agent-evidence.yml runs adversarial
local tests and a deterministically seeded synthetic strategy tournament
on pull requests, emits a short research witness and archives it for
seven days. Its daily cron (06:41 UTC) can execute ONLY after that
workflow is merged into the repository default branch; PR existence
does not activate a recurring schedule. The job has contents: read,
no market vendor access, no broker secrets, no deployment, no Codex
usage, no auto-trading and no automatic model promotion.

**Akinator provenance / decision:** Before: typed synthetic bar P&L
harness but no asynchronous order/cancel/reconcile invariants. After:
explicit offline message replay, bounded orders/exposure, replay-local
idempotency, fail-closed agent dependency and evidence in CI. Alternative
rejected: connecting live broker endpoints or declaring simulation
receipts "verified exchange execution." Review must challenge extreme
gaps, server-side unknown order states, partial fills, duplicate delivery,
API rate limits and loss in transit before any live adapter is authorized.
Current evidence is versioned source and exact-commit CI, not a
production certification or a claim of machine consciousness.


### Final-liquidation risk-accounting regression

Phase 19's synthetic settlement previously deducted adverse exit slippage and commissions from ending cash but did not always update the *minimum marked equity* and *maximum drawdown* after settlement. That could under-report simulated drawdown even when net P&L reflected fees. Corrected in `paper_harness.py`: after forced terminal liquidation, account for final after-fee cash as a mark and recompute drawdown against the pre-existing equity high-water mark. Added deterministic, monotonically rising toy-path adversarial test in `tests_engine/test_omnigenesis_paper_harness.py` with substantial commissions proving the post-settlement equity extreme. This only improves **synthetic accounting**, not real market risk guarantees. Reverify exact-current-HEAD CI before acceptance.


## Phase 20 offline safety-halt reconciliation assertion (2026-11-23)

Adversarial review of the exact current offline_order_router.py found that must_cancel_and_reconcile_externally was previously computed as halted AND any remaining working order. This incorrectly cleared the external reconciliation warning after a safety HALT if the simulated orders were all canceled, filled, or absent. A local simulated position snapshot—even a matching RECONCILE event—is not an authenticated external exchange or broker reconciliation. The reporting predicate is now halted (regardless of the number of open mock orders). The existing status and authority remain research-only, no live broker adapter is enabled, and no actual cancel request is sent. This field means an external operator would need to confirm order/position state before considering any real execution recovery; it does not mean that an external operation was performed.

Adversarial tests assert the warning survives (1) HALT with no submitted orders, (2) HALT followed by mock CANCEL/CANCEL_ACK and matching mock RECONCILE, and (3) HALT with a late partial fill followed by cancellation. No changes to position caps, fills, order semantics, live strategies, or broker authorization. The exact-head CI run must pass before this change is called verified; the independent live peer federation gate remains separate and cannot be bypassed.


### Follow-up: CI-confirmed report-key formatting regression

Exact source HEAD bdf8481ec7de45a6ab4b35f246662febfc24b1b7 failed the dedicated OMNIGENESIS research run 45131735551, canonical tests 45131735702 and offline evidence 45131735689. Root cause: a source comment contained literal escaped newline characters, causing Python to treat the following must_cancel_and_reconcile_externally dictionary field as part of the comment. The field was absent, causing KeyError and blocking typed research DAG receipts. Replaced those escaped characters with actual comment line breaks without changing the intended halted predicate or any execution policy. Added a parameterized-state regression for flat, filled, halted and canceled offline states, asserting the field is always present, matches halted and is bound into the final content digest. This repair is not accepted until exact new HEAD CI succeeds. The independently failing browser and stale federation gates are unaffected; no live broker operations are enabled.
