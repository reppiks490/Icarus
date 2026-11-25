# Storage recovery and per-agent intelligence expansion

Date: 2026-11-24 local. Design and read-only storage findings; no deletion, installation or training performed in this assessment. Extends LEARNING_AGENT_FEDERATION.md, QWEN3_SHARED_FLEET.md and the original inventory PR #505.

## Storage recovery: target additional 20 GB
Latest read-only Windows scan PID 31212 completed, exit 0. C: total 510,977,372,160 bytes, used 499,855,527,936, free 11,121,844,224. Sizes are logical file lengths, not allocated clusters or guaranteed recoverable space. Skip reparse/offline paths; do not hydrate or delete. Temp and caches may contain active or offline-install dependencies.

| Location relative to authorized Windows user home | Logical bytes | Qualification |
|---|---:|---|
| AppData/Local/pip/Cache | 2,494,391,824 | Download cache; confirm active use and offline reproducibility |
| AppData/Local/npm-cache | 3,923,023,096 | Package cache; use supported cleanup only with approval |
| AppData/Local/uv/cache | 636,287,165 | Dependency cache; verify active environments and links |
| AppData/Local/Temp | 1,049,616,798 | Only inactive eligible files |
| AppData/Local/CrashDumps | 348,689,774 | Retain needed debugging evidence |
| .ollama/models/blobs | 34,644,164,802 | Includes installed weights and partial downloads; no blanket deletion |
| AppData/Local/Docker | 6,820,152,603 | Virtual disks; contents/reclaimability unknown |
| AppData/Local/wsl | 15,294,534,966 | Virtual disk; contents/reclaimability unknown |
| Downloads/divine providence | 5,141,712,494 | Bounded at 60,000 files; overlapping historical archives and source trees |
| Downloads/everything so far for opus | 225,681,365 | Historical archive collection; compare hashes and preserve unique work |

Package/temporary/dump categories total 8,452,008,657 logical bytes. Windows SoftwareDistribution/Download contained only 79,238 bytes in observed scope. Do not assume system update cleanup will provide substantial capacity.

Second read-only audit PID 37152 completed, exit 0: 65 distinct manifest-referenced blob identities, zero manifest parse errors. Two large partial files have no exact references from installed manifests:
- .ollama/models/blobs/sha256-13576eb6dd8d9d04b4da04d015ff343968628d3c2984195569d9d3585651d4f1-partial — 7,309,830,496 bytes.
- .ollama/models/blobs/sha256-dde5aa3fc5ffc17176b5e8bdc82f587b24b2678c6c66101bf7da77af9f7ccdff-partial — 2,019,377,376 bytes.
All partial-marked files total 9,329,209,984 logical bytes, including small sidecars; unreferenced nonpartial files total 706 bytes. Partial files are not confirmed abandoned; owner previously paused downloads and preserved resumability. Exact model mapping and active download status not independently established. Deletion would discard download progress. Verify allocation, current pull/runner state, mapping to pending requests, and obtain explicit owner approval before deleting partials. Never delete installed blobs based on size or an unreferenced snapshot alone.

Potential first route: approved cache cleanup plus explicitly abandoned partial downloads, theoretical combined logical 17,781,218,641 bytes. Additional ~2.22 GB logical target could come from verified redundant Git/history/archive content or supported virtual disk reclamation. None of this is confirmed physically reclaimable. If preserving paused downloads is preferred, investigate virtual disks and third-party Git packs instead. Prior FinanceDatabase/CCXT Git metadata ~23.89 GB combined; OpenBB Git ~2.55 GB. Docker+WSL logical 22.11 GB; never remove virtual disk files or prune volumes blindly. Inspect supported Docker/WSL usage and backups, preserve unique data and active services. Prefer approved relocation to another drive or a verified minimal checkout with history preserved, where available. No history rewrite, blanket deletion, forced shutdown or cloud hydration.

Before actual cleanup: remeasure physical allocation, identify active users, classify retained vs disposable, preserve backups/receipts, agree on exact deletion/migration scope, apply supported cache cleanup or targeted approved action, verify free space and runtime health after each step. No claim of 20 GB recovery before measured free-space delta. The 1.8 GB available-RAM reserve is independent of disk recovery.

## Agent intelligence expansion
All 40 proposed identities in agent-federation-registry.json must receive distinct trainable state and evidence-backed capability evolution. An 8B LLM cannot become a 16B LLM by changing a runtime setting, context window or prompt. Changing base parameter count requires a different architecture/checkpoint or actual architecture expansion and training. Increasing context, inference-time deliberation, retrieval or tool access increases computational capability, not base parameter count.

Use a layered per-agent intelligence contract:
1. Shared immutable qualified base reasoning checkpoint; choose by benchmark and available memory. Existing 8B/4B/1.7B/0.6B and low-bit 8B are candidates. Larger model upgrade only after memory/quality qualification and owner approval.
2. Role-specific trainable numerical learners and individual checkpoint namespace, as already defined; add complementary forecast, calibration, routing, anomaly, symbolic or retrieval-learning components where justified. Train on eligible independently labeled outcomes, retain lineage and rollback. Count actual trainable parameters from model tensors/architecture; do not sum repeated shared weights into unique parameters. Track total shared base, unique learned state, active parameters per inference, and peak RAM separately.
3. Optional parameter-efficient adapters (LoRA-style) on compatible backend with authorized training corpus and license. Candidate rank 4/8/16 as experimental settings, not fixed performance gains or universal adapter sizes. Every agent may have an independent adapter lineage, loaded on demand; training feasibility not established on current CPU/iGPU. Rank, target modules, optimizer state, activations, quantization and evaluation determine actual resource cost. No claim of local LLM fine-tuning readiness. Train compact numerical learners first.
4. Reasoning budget and context: task-specific token budgets, verified retrieval, decomposition, tool-grounded calculations, controlled search, independent challenge, deterministic validation and evidence synthesis. Increase reasoning budget for difficult tasks only, benchmark quality per resource, do not claim longer outputs equal stronger reasoning.
5. Mixture of specialists: coordinate multiple qualified learned components and backends through POLYMIND and Reality Court; selectively activate them. This is orchestration, not a trained mixture-of-experts neural architecture or a single summed-parameter LLM.
6. Every identity's capability registry tracks role objective, base digest, independent learner/adapter hashes, actual trainable parameters, training/evaluation data versions, competence, calibrated uncertainty, failure evidence, allowed tools, measured latency, peak memory, checkpoint promotion and rollback. Shared evidence does not grant automatic permission or qualification.

All 40 identities can be upgraded as a design and registry simultaneously; actual training and inference occur only in admitted waves across compatible runtimes. Current physical RAM approximately 16.9 GB, owner reserve 1,800,000,000 bytes. Storage recovery does not increase physical RAM. Never load all weights/adapters simultaneously by assumption. Preserve active workloads, use bounded CPU and memory, lazy load, and check minimum available RAM during runs. No auto-download, scheduled Codex, paid usage, unapproved data transfer or live execution. Compare per-agent improvement versus previous champion on frozen independent tests, include unsuccessful experiments, avoid same-model correlated voting, protect final holdout.

Implementation milestones: parameter/accounting schema; 40 compact learner instances with genuine training and checkpoint receipts; per-role benchmark and challenger baselines; shared reasoning runtime and measured context scheduling; tool/algorithm integration; optional adapters after feasibility check; independently qualified competence-based routing and promotion. All prior discovery accounting, simulation, ICARUS and UMBRA integration lanes remain active in scope. This document is a plan, not evidence of trained agents or new runtime capability.
