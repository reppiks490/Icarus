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

## Unfinished integration and next engineering gates

1. Current standalone PR #503 is DRAFT. Check complete GitHub Actions at its current HEAD; a dedicated workflow passing does not establish all canonical Linux/Windows, Expo installation, UI workspace browser or portfolio Playwright success.
2. Phase 17 digest, source and venue metadata are all caller claims. Extend only through NEXUS/ARGUS independent verified vendor receipts and licensed instrument-master data, official contracts/ticks/roll/sequence gaps and bitemporal history. No personal finances, real brokerage or trading credentials. No paid API ingestion without authorization. Do not mislabel a local digest match as a signed vendor attestation.
3. Extend failure handling with cancellation/runtime isolation, explicit idempotent retries, checkpoints, independent reviewer agents and verified external attestations; current DAG is deterministic local execution, not continuous autonomous workers. Honor existing ASCENDANCY rather than adding a second governor.
4. Add actual real market order-book evidence, venue latencies, queue, slippage, fees, spread, missing liquidity, risk and independent OOD replication before claiming high-fidelity market simulation or profitable alpha.
5. Independently replay pinned UMBRA v5 source rather than trusting internally consistent paired report only. Do not use the UMBRA archive PR #4 until its accessor/toJSON security finding is fixed/reviewed. Do not alter the original live site's three products or browser data.
6. Genuine cinematic desktop and native iPhone observatories require separately measured motion, frame intervals (p50/p95), touch selection, low-power and reduced-motion behavior. Existing OMNIGENESIS artifacts are already displayed as truthful research nodes but a dedicated multi-scale hybrid renderer is NOT implemented.
7. Human-reviewed merge/deployment decision only after canonical CI, real device and scientific gate signoff. No force push, blind merge, self-promotion, real trading or unattended Codex-driven loop.

**Verification evidence is per exact source SHA. This document is a continuing source map, not a production release certificate.**
