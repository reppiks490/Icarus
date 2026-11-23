# ICARUS OMNIGENESIS ∞ — AUTHORITATIVE CHAT-TO-CHAT HANDOFF

**Handoff compiled:** 2026-11-22 (America/Chicago).
**User goal:** Continue building a spectacular, mathematically sophisticated, deeply integrated ICARUS scientific intelligence subsystem, with native desktop/iPhone visualization, independently verified research, and phased evolution. Do the actual engineering, not only architectural brainstorming.

> IMPORTANT: This document captures verified code and GitHub evidence. It does not attest that the feature was installed on the user's Windows computer, deployed to a public URL, operating autonomously, or producing profitable trading signals. Future agents must read the CURRENT GitHub branch, PR, and Actions before claiming any change or status.

## 0. Exact source of truth / how to resume

- Canonical repository: https://github.com/reppiks490/Icarus
- **Only active OMNIGENESIS development branch:** agent/omnigenesis-phase-01-foundation
- **Draft pull request:** https://github.com/reppiks490/Icarus/pull/503
- Base branch: main.
- Pre-handoff verified PR head (the next commit adds this handoff file): 245bb31d2fdc29e11cec95c2101eebda9c2592df.
- Pre-handoff state: **64 commits, 37 changed files**, draft, open, **unmerged**. GitHub mergeability can change; check its CURRENT value on arrival.
- Existing source documents: docs/icarus/OMNIGENESIS.md and icarus_engine/omnigenesis/README.md.
- Existing dedicated CI: .github/workflows/omnigenesis-research-ci.yml.
- Do NOT create another OMNIGENESIS repository, duplicate implementation or start over. Inspect PR #503 and continue its branch without force-pushing, resetting, altering live execution, or prematurely merging.
- This handoff is subordinate to ACTUAL CURRENT code and tests. When documentation and code disagree, identify the discrepancy and verify it rather than inventing a reconciliation.

## 1. Origin / mathematical motivation

The user supplied an exact prime-successor formula, with n >= 1:

    Next(n) = n + 1 +
              SUM(m=1..n!) PRODUCT(j=1..m) [
                1 - PRODUCT(k=2..n) (
                  1 - floor((n+j)/k) + floor((n+j-1)/k)
                )
              ]

For integers x and k, floor(x/k)-floor((x-1)/k) is 1 precisely when k divides x; the product is a coprimality screen relative to n!. The first integer > n with no divisor in [2,n] is the next prime; n!+1 guarantees the search terminates. This is exact, NOT an efficient numeric implementation or established novel theorem.

The generalized first-event construction motivates historical market-event labeling:

    FirstEvent(t, H) = t + 1 + SUM(m=1..H)
                         PRODUCT(j=1..m)(1 - E[t+j])

with E[x] in {0,1}. If no event occurs within H, output t+H+1 (a sentinel), not a prediction.

COMPUTATION RULE: The system implements optimized prime search and explicit event scans, NOT the factorial-length expression. Historical event labels use completed future windows; these must NOT leak into live decisions.

A Turing-machine/state-machine idea became a typed, finite, deterministic transition language and formal overlap/counterexample checking. It is NOT a literal universal Turing-machine runtime.

## 2. Identity and system hierarchy

Project designation: **OMNIGENESIS ∞ / ICARUS-ΩG**.

It is the computational science and research-instrument *foundry* for ICARUS. It produces mathematical instruments, bounded experiments, safe program specifications, synthetic scenarios, falsification evidence, and proposed capability changes. It does not have the authority to approve its own strategies or execute trades.

Boundaries against existing subsystems:

- ICARUS / Pulse: production strategy, paper execution and orders. **No strategy, position, broker or order mutations** in OMNIGENESIS.
- ARGUS / NEXUS: market data, integrity, historical MBO/MBP. Source validation belongs upstream; OMNIGENESIS currently accepts caller-provided files and timestamps, not independently authenticated licensed feeds.
- AION: memory/replay; OMNIGENESIS adds versioned derived scientific evidence, not a replacement.
- ATHENA: risk/supervision; OMNIGENESIS does not grant risk exceptions.
- PROMETHEUS: hypotheses; OMNIGENESIS builds reusable mathematical research mechanisms.
- PANTHEON / AETHER: specialist intelligence faculties; OMNIGENESIS proposes new research instrument types.
- CHRONOFOLD / SIBYL: temporal geometry and forecasting; OMNIGENESIS builds first-event analysis and verifiable programs.
- DREAMSTATE / PARALLAX: incubated policies / counterfactuals; OMNIGENESIS is strictly research-only and must not auto-promote.
- APEX Ω: world model, causal/evidence truth. Still owns scientific truth contracts.
- ASCENDANCY: governed evolution/work orders. OMNIGENESIS must NOT establish an unauthorized parallel scheduler or governor.
- DAEDALUS / AEGIS: adversarial verification and qualification. Independent approval remains mandatory.
- Adaptive Brain: registry/health. OMNIGENESIS is registered there for observability, not elevated to live authority.

Hardcoded research-only authority contract in icarus_engine/omnigenesis/__init__.py and derived outputs:

    research_only: true
    execution_authorized: false
    production_decision_authorized: false
    auto_promote: false

Do not weaken or reinterpret those flags.

## 3. Precisely implemented phases — 1 through 16

| Phase | Implemented content | Main sources |
|---|---|---|
| 1 | Exact successor-prime and historical first-event primitives; strict source/as-of schema | arithmetic.py, contracts.py |
| 2 | Bounded one-feature model discovery: raw and absolute value threshold hypotheses, train/validation/held-out Brier scores, label-maturity purges | foundry.py |
| 3 | Derived-study append-only application-level SQLite ledger, identity hashing, read-only snapshot | ledger.py, __main__.py |
| 4 | Safe typed market-state machines, allowed numeric comparisons, deterministic replay and trace | automata.py |
| 5 | Seeded SYNTHETIC order-book simulator, price-time priority, self-match avoidance, quantity conservation | simulation.py |
| 6 | Bounded capability proposal compiler, dependency ordering, compute/dollar budgets, no actual agent execution | evolution.py |
| 7 | HTML offline research observatory, real stored records, no fabricated study activity | observatory.py |
| 8 | Desktop crimson/void animated research galaxy, 4 projection modes (COSMOS, LATTICE, HELIX, RIFT), ring/filament/particle motion, pan/zoom, reduced-motion support | omnigenesis-ui.js, omnigenesis-ui.css |
| 9 | Native desktop tab, authenticated read-only local research snapshot and asset routes | dashboard.html, server.py |
| 10 | Formal numeric transition collision analysis, finite-float witnesses, structured certificates and tests | formal.py, automata.py |
| 11 | Exact integer-tick historical OHLC first-passage: UPPER / LOWER / AMBIGUOUS_BOTH / CENSORED, incomplete-window exclusion | first_passage.py |
| 12 | Mobile gateway allowlisted read-only path, no writes | icarus_mobile_gateway/proxy.py |
| 13 | Unified immutable derived summaries: model study, proof, synthetic experiment, first-passage, capability plan | ledger.py, observatories |
| 14 | Offline HTML record authenticity/schema and script-injection regression tests | tests_engine/test_omnigenesis_observatory.py |
| 15 | React Native animated scientific observatory, record selection, accessibility motion settings, 15-second foreground Intelligence-tab refresh | mobile/src/OmnigenesisMobile.tsx, mobile/App.tsx, mobile/src/api.ts |
| 16 | Retrospective event-to-model bridge, joins completed first-passage labels with as-of received numeric features; excludes censored/ambiguous outcomes | event_bridge.py, __main__.py |

IMPORTANT: The earlier architecture document's phase table skips 14 and 16 and PR #503 title still says 1–15 at the pre-handoff snapshot. Those are documentation discrepancies, NOT missing phase-16 code. The next developer should update docs/PR text after verifying CURRENT source and tests.

This is 16 **engineering phases**, not 16 self-training AI agents, 16 independently proven profitable strategies, or a completed multi-agent market digital twin.

## 4. Complete changed-file inventory at pre-handoff PR head (37 files)

### Core Python and operator documentation
- icarus_engine/omnigenesis/__init__.py
- icarus_engine/omnigenesis/__main__.py
- icarus_engine/omnigenesis/arithmetic.py
- icarus_engine/omnigenesis/automata.py
- icarus_engine/omnigenesis/contracts.py
- icarus_engine/omnigenesis/event_bridge.py
- icarus_engine/omnigenesis/evolution.py
- icarus_engine/omnigenesis/first_passage.py
- icarus_engine/omnigenesis/formal.py
- icarus_engine/omnigenesis/foundry.py
- icarus_engine/omnigenesis/ledger.py
- icarus_engine/omnigenesis/observatory.py
- icarus_engine/omnigenesis/simulation.py
- icarus_engine/omnigenesis/README.md
- docs/icarus/OMNIGENESIS.md

### Desktop and server integration
- icarus_engine/brain.py
- icarus_engine/dashboard.html
- icarus_engine/omnigenesis-ui.js
- icarus_engine/omnigenesis-ui.css
- icarus_engine/server.py

### Native mobile and gateway
- icarus_mobile_gateway/proxy.py
- mobile/App.tsx
- mobile/README.md
- mobile/src/OmnigenesisMobile.tsx
- mobile/src/api.ts

### Verification
- .github/workflows/omnigenesis-research-ci.yml
- tests_engine/test_omnigenesis.py
- tests_engine/test_omnigenesis_artifacts.py
- tests_engine/test_omnigenesis_automata.py
- tests_engine/test_omnigenesis_event_bridge.py
- tests_engine/test_omnigenesis_evolution.py
- tests_engine/test_omnigenesis_first_passage.py
- tests_engine/test_omnigenesis_formal.py
- tests_engine/test_omnigenesis_integration.py
- tests_engine/test_omnigenesis_mobile.py
- tests_engine/test_omnigenesis_observatory.py
- tests_engine/test_omnigenesis_simulation.py

This new HANDOFF.md file becomes an additional changed file after the handoff commit; always refresh PR file counts.

## 5. Real execution paths and interfaces

Python package: icarus_engine.omnigenesis

Core APIs include: next_prime(n), first_event_offset(flags,horizon), evaluate_dataset(dataset), ResearchLedger(root), compile_automaton(spec), replay_automaton(program,observations), formal_certificate(program), replay_book(events), synthetic_scenario(seed,steps), label_first_passage(tape,...), bridge_first_passage(report,feature_rows,...), compile_proposal(spec), plan_capabilities(proposals,...), render_observatory(snapshot,output).

Native server:
- Authenticated **GET /api/omnigenesis** (bounded derived ledger snapshot).
- Static desktop assets **/omnigenesis-ui.js**, **/omnigenesis-ui.css**.
- Native dashboard tab "OMNIGENESIS ∞" in icarus_engine/dashboard.html.
- Snapshot schema "icarus-omnigenesis-snapshot-v1".
- Stores derived reports under root/research/omnigenesis.sqlite3.
- REST route is read-only: do not add unauthenticated writes, order endpoints or execution hooks.

Mobile gateway:
- Authenticated **GET /v1/omnigenesis** forwards to local authenticated engine GET; no POST.
- The existing gateway/phone setup must already work; this code does NOT expose the PC to the Internet.
- Native mobile Intelligence tab imports OmnigenesisMobile and calls client.omnigenesis().
- 15-second tab-scoped read polling; no unattended research automation.
- RN native-driver animation and reduced-motion support; taps select actual study or artifact nodes.
- Real device performance, visual QA, and iPhone remote reachability have NOT been confirmed.

Offline export:
- HTML file generated via the Python CLI from the local ledger, not a live research portal.
- Ambient motion is **decorative**. If there are no persisted records, the interface must truthfully show zero records; no hallucinated agents, models, fills, signals, or learning.

## 6. Reproducible commands (execute in checked-out repository)

Installation is repository-environment dependent; dedicated CI uses:

    python -m pip install -e ".[dev,bridge]" "cryptography>=44,<47"

Research-focused regression suite (the shell wildcard works in CI's Linux bash):

    python -m pytest tests_engine/test_omnigenesis*.py -q

Portable alternative (test discovery on Windows and Linux):

    python -m pytest tests_engine -k omnigenesis -q

Native app:

    cd mobile
    npm ci --no-audit --no-fund
    npm run typecheck

Native desktop JS parser:

    node --check icarus_engine/omnigenesis-ui.js

CLI examples from repository root:

    python -m icarus_engine.omnigenesis prime 100
    python -m icarus_engine.omnigenesis status --root .
    python -m icarus_engine.omnigenesis run ./dataset.json --root .
    python -m icarus_engine.omnigenesis formal ./machine.json --root .
    python -m icarus_engine.omnigenesis automaton ./machine.json ./observations.json
    python -m icarus_engine.omnigenesis synthetic-book --seed 17 --steps 300 --root .
    python -m icarus_engine.omnigenesis first-passage ./tape.json --up-ticks 20 --down-ticks 15 --horizon 12 --root .
    python -m icarus_engine.omnigenesis bridge-event ./first_passage_report.json ./asof_features.json --positive-event UPPER --output ./research_dataset.json
    python -m icarus_engine.omnigenesis propose ./capability.json
    python -m icarus_engine.omnigenesis plan ./proposals.json --seconds 1800 --dollars 0 --root .
    python -m icarus_engine.omnigenesis dashboard --root . --output ./research/omnigenesis.html

IMPORTANT: Input JSON files in examples are illustrative filenames; NO such user-supplied real data files or approved MBO dataset were verified in this chat. Do not pretend they exist. Bridge command's --output uses exclusive file creation and refuses overwrite.

## 7. Data and scientific truth contracts

Research training dataset schema:
- Top-level exactly: dataset_id, source_commit, records.
- 30–50,000 records, **single asset**, exactly one numeric feature per record.
- Each record exactly: record_id, asset, decision_at, observed_at, received_at, label_resolved_at, feature, outcome, source_record_id.
- All times timezone-aware, observed_at <= received_at <= decision_at < label_resolved_at; duplicate IDs rejected.
- source_commit must match syntactic lowercase 40-hex SHA, but authenticity is NOT checked by the parser.
- 60% train / 20% validation / 20% final holdout; purge immature preceding labels; candidates are fit only on train and selected on validation; final holdout evaluated once within a run.
- Two supported feature transforms: raw and absolute. Quantile threshold candidate search, **not** an open-ended neural-network, evolutionary learner or genuine alpha validator.
- "EXPLORATORY" means favorable held-out Brier difference on one dataset; "REJECTED" otherwise. Neither means deployable.

First-passage tape:
- Top-level exactly: asset, source_commit, bars.
- 5–50,000 strictly increasing received-at historical bars, positive integer OHLC tick values.
- Each bar exactly: record_id, observed_at, received_at, open_ticks, high_ticks, low_ticks, close_ticks.
- One event per completed horizon (upper/lower/ambiguous/censored). Default stride = horizon to reduce overlap. Both extremes hit in same OHLC bar -> AMBIGUOUS_BOTH, never assumed stop-first or profit-first.
- Incomplete horizon -> pending count, no label. Censored or ambiguous are not ordinary negative samples.

Phase-16 event bridge:
- Takes first-passage report with integrity-bound report_id + feature rows.
- Feature-row fields exactly: decision_record_id, source_record_id, source_commit, observed_at, received_at, feature.
- Only labels UPPER/LOWER become boolean learning outcomes; ambiguous and censored excluded.
- Requires at least 30 eligible records, source commit agreement, as-of features, proper label maturity, no unused/missing source feature IDs.
- Output dataset and audit; no market order or fabricated future features.
- The source commitment and timestamps are still **caller-provided claims**, not independently verified Databento records.

Formal proof:
- Numeric guard grammar is intentionally finite; supports gte/gt/lte/lt/eq/neq and source-to-target state transitions.
- Compiler rejects ambiguous simultaneous guards; certificate verifies structural properties. Does NOT prove liveness, realized future regimes, trade success or profitability.
- The "proof" is within the declared typed finite-comparison model, not universal market mathematics.

Synthetic exchange:
- Discrete toy book with price/time priority, self-match prevention, order cancellation ownership, seeded reproducibility and quantity conservation.
- Results are tagged SYNTHETIC and must not be classified as licensed MBO or real fills.
- Costs, real queue dynamics, latency, partial venue visibility, liquidation mechanics and calibration remain future work.

Storage:
- SQLite journal uses application-level append-only/content-addressed semantics for derived **summaries**; no authenticated tamper-resistant audit service, and no raw vendor market tape is stored by this ledger.
- Do not call it cryptographically tamper-proof against disk administrators.

## 8. Exact CI evidence at pre-handoff head

PR head 245bb31d2fdc29e11cec95c2101eebda9c2592df had these GitHub Actions runs (all completed at inspection time):

| Workflow | Run ID | Conclusion |
|---|---|---|
| OMNIGENESIS research-only verification | 45006975066 | SUCCESS — both "omnigenesis" Python/HTTP/JS test job and "mobile-typescript" job succeeded |
| configuration-job-contract | 45006975034 | SUCCESS — Ubuntu and Windows |
| intelligence-feed-contract | 45006975037 | SUCCESS — Ubuntu and Windows |
| tests | 45006975061 | FAILURE overall; engine Linux, engine Windows and Windows Python 3.10 restart jobs PASSED; mobile job FAILED at Expo install version check |
| ui-visual-contract | 45006975055 | FAILURE: Playwright workspace browser test selected a disabled option in #btTf and timed out |
| Four portfolio performance | 45006975042 | FAILURE: Ubuntu and Windows contracts PASSED; browser job FAILED on npx playwright install --with-deps chromium |
| live-engine-federation-gate | 45006975082 | FAILURE: canonical BrainRemoteSync live peer corpus acceptance; downstream canonical acceptance job skipped |

Relevant CI job IDs:
- dedicated Python/JS: 137160629787; dedicated mobile TypeScript: 137160630005.
- standard engine Windows restart 137160640780, mobile 137160640928, engine Windows 137160640979, engine Linux 137160640988.
- UI browser: 137160648495.
- portfolio contracts Windows 137160629570, Chromium install 137160629780, Ubuntu 137160629800.
- live federation: 137160640838.

Known exact mobile Expo version mismatch:
- expo installed 57.0.31; expected ~57.0.33.
- expo-constants installed 57.0.22; expected ~57.0.24.
- expo-notifications installed 57.0.24; expected ~57.0.25.

Do not automatically blame OMNIGENESIS for repository-wide failures, but equally do NOT declare them harmless/preexisting without proving that using main/base comparison. Repair with isolated evidence, keeping canonical tests intact. The standalone native TypeScript job PASSED even though Expo's dependency version check failed in a separate workflow.

GitHub PR "mergeable" has fluctuated across checks; latest pre-handoff inspection reported **true**, but this is not authorization to merge.

After this HANDOFF file is committed, refresh the new SHA and CI statuses. Documentation-only commits may not trigger every path-limited workflow.

## 9. Open blockers and work not yet implemented

**Do not claim readiness to integrate or deploy until these are addressed:**

1. Refresh PR #503, compare against latest main, review changed files. Confirm no conflicts or unwanted API authority escalation.
2. Triage/repair standard mobile Expo dependency version drift with correct package-lock updates; do not casually bypass the check.
3. Reproduce/repair disabled #btTf selection in workspace browser test without masking the underlying UI contract.
4. Investigate portfolio Chromium install failure separately: host tooling/dependency issue versus repository issue.
5. Investigate live bilateral BrainRemoteSync federation acceptance using its exact logs and canonical peer witness contracts; do not fabricate a peer packet to force green.
6. Obtain actual desktop and mobile screenshots / device rendering from real running application. No validated measured FPS or successful iPhone 5G access exists from this work.
7. Test auth failures and no-write routes; review persistence, schema, input-size limits, browser XSS safety, and run realistic long-duration stress/soak tests.
8. Integrate verified source-licensed historical MBO/MBP and contract-roll-safe datasets with exact as-of record/witness verification; source commit syntax alone is NOT enough.
9. Add cost/slippage/latency/venue/queue-aware validation and independent statistical replication to avoid false alpha claims.
10. Submit scientific evidence to existing DAEDALUS/APEX/ASCENDANCY review gates; never auto-promote experiments.
11. Prepare staged deployment/rollback and obtain owner merge approval.
12. Consider fixing mismatched documentation phase table and PR title to explicitly include Phases 14 and 16.
13. The planned "market-data intake" / file-hash-and-contract verification phase was DISCUSSED, but **no committed market-data intake module was verified** before this handoff. Do not represent it as complete.

High-level envisioned future systems, **not shipped**: reality-calibrated multi-agent market ecology/digital twin, broad automated mathematical invention, freely evolving self-modifying intelligence, GPU-based real-time market universe, cross-venue agent swarms, unsupervised live learning and self-deployment. These require substantial new engineering and independent scientific validation.

There are NO automatic two-hour work sessions started by this branch. Prior assistant could only perform in-session work, not indefinitely continue after context loss.

## 10. Immediately next developer action

**First**: Read this handoff and the current files in PR #503; query GitHub current PR head, changed paths, CI and relevant failure logs.

**Second**: Resolve the four overall failing workflows with diagnosis and isolated fixes; preserve passing jobs. In parallel only where supported, review the proposed market-data ingestion phase and genuine UI performance bottlenecks.

**Third**: Implement Phase 17 (proposed): source-verifiable market data intake, with file hash, timestamps, tick-size/instrument/expiry validation, accepted-venue/source lineage, source license and cost controls, and futures roll handling. Integrate with NEXUS, not a shadow untrusted source.

**Fourth**: Implement the next sound research capability (not just more decorative charts), such as an exchange-replay comparison harness that measures simulation-vs-observed divergence and rejects unjustified microstructure claims.

**Fifth**: Verify desktop/iPhone visuals via actual real-browser/device render, responsiveness, motion preference, memory/GPU cost, frame latency and touch navigation. Optimize based on measurements rather than arbitrary 5,000-FPS claims.

**Sixth**: Update PR #503 body, actual architecture docs, tests, and HANDOFF.md to the new VERIFIED state. Draft until release gates are met. Do not merge without the user's explicit approval or instruction.

## 11. Non-negotiable truth/permission constraints

- Research/shadow only. No broker/order/position mutation.
- No direct code execution of generated research text; typed DSL only where currently supported.
- No invented model performance, scientific proof, historical dataset, timestamp, source hash, integration or CI status.
- No fabricating screenshots or claiming an animated effect is agent intelligence.
- No automatic external paid API calls, scheduling or background work without explicit approval.
- Never write arbitrary live market strategies into ICARUS as a side effect of research.
- Do not overwrite distinct subsystem ownership contracts or remove verification gates.
- Do not force-push, reset PR history, or merge blindly.
- Preserve users' branch history and isolate changes under PR #503.

## 12. Copy-and-paste next-chat starter

Continue building **ICARUS OMNIGENESIS ∞** from the REAL source of truth, not from memory or a new greenfield design. Canonical repository: reppiks490/Icarus. Branch: agent/omnigenesis-phase-01-foundation. PR: https://github.com/reppiks490/Icarus/pull/503. First read docs/icarus/OMNIGENESIS_HANDOFF.md, docs/icarus/OMNIGENESIS.md, icarus_engine/omnigenesis/README.md, the entire PR file diff, and CURRENT Actions. Phases 1–16 are coded on the draft PR; Phase 17 market-data intake was NOT implemented. Respect APEX/DAEDALUS/ASCENDANCY and research-only authority. Reproduce unresolved repository CI issues, verify native desktop/mobile animations against a real browser/device, fix blockers without force-pushing or altering trading permissions, then build the next sound scientific capability with tests and documented evidence. Keep the PR draft until integration gates and owner merge approval. Don't guess what is complete; report source-backed status, code paths, exact checks, and remaining gaps.

---
This handoff is deliberately exact about what is BUILT versus what is only PROPOSED. Revalidate everything at the beginning of the next session.

---

## 13. Phase 17–18 implemented hybrid update (2026-11-22 America/Chicago; overrides older proposed-only statements)

**Important chronological correction:** Earlier sections 3, 9, 10, 12 above document the historical pre-handoff state, where Phase 17 had not yet been implemented. **It has now been implemented on this draft branch**, together with Phase 18 and an expressly synthetic UMBRA bridge. Read the latest source and CI before treating this appendix as current.

**New source paths:**
- icarus_engine/omnigenesis/data_intake.py — Phase 17 read-only inspection of operator-declared local historical normalized JSONL market data; strict manifest, SHA-256 exact bytes, accepted event schema, declared contract-roll period, timestamp and sequence tests, and bounded file/row/size limits.
- icarus_engine/omnigenesis/umbra_bridge.py — UMBRA Sovereign Worlds v5 pairedExperiment arithmetic/seed validation. Separate repo: https://github.com/reppiks490/umbra-sovereign-worlds . Source commit is caller-claimed; UMBRA model is **not** independently replayed by this adapter.
- icarus_engine/omnigenesis/agent_workflow.py — Phase 18 compiled, on-demand, deterministic research DAG with strictly allowlisted local operators: prime, synthetic_book, market_intake, umbra_worldline and formal. Input plans and receipts hash-bound; on failure downstream dependencies are BLOCKED. Budget estimates are metadata; no real-time preemption, agent LLM workers, broker execution or scheduler.
- icarus_engine/omnigenesis/ledger.py — original application-level append-only research artifacts now include validated agent_workflow summaries with receipt-chain and count/status checks; new results flow through existing read-only /api/omnigenesis and mobile gateway and may appear as genuine derived artifact nodes in the existing dashboard.
- icarus_engine/omnigenesis/__main__.py — adds market-intake, audit-umbra and explicit workflow CLI; optional --execute --root writes derived summaries to the existing research ledger, --output creates a new file only.
- Tests: tests_engine/test_omnigenesis_data_intake.py, test_omnigenesis_umbra_bridge.py, test_omnigenesis_agent_workflow.py. These include tampering, future timestamps, row ordering, invalid contract roll and unknown operator denial, DAG cycles, authority escalation, receipt tampering, ledger read-only summaries and CLI idempotence/exclusive output.

**Combined source and nonclaims:** docs/icarus/OMNIGENESIS_SOVEREIGN_HYBRID.md; phase matrix in docs/icarus/OMNIGENESIS.md; user-facing source/CLI notes in icarus_engine/omnigenesis/README.md.

**Observed CI evidence:** On earlier interim head 3925deeb92289821c0bdece584bea127036dadd1, the dedicated OMNIGENESIS research-only workflow was observed **SUCCESS** after a corrected timestamp-confounded test fixture. The newer documentation commits and any subsequent source changes MUST be checked against the final source SHA. Full repository-wide UI/Playwright/Expo/portfolio workflows have independent failures or pending jobs at earlier snapshots; dedicated success does NOT establish release readiness. Do not invent full passing CI.

**Beyond synthetic, precisely:** Phase 17 can structurally inspect user-provided *historical observed-byte datasets* but DOES NOT verify exchange/provider origin, license rights, truth of clock claims, MBO completeness or broker fills. SHA-256 expected bytes are supplied by the same operator, so an internally matching digest is **not independent authentication**. NEXUS/ARGUS vendor-authorized source verification, instrument masters and roll/sequence policy remain required before live/read-only market-fed model comparisons.

**Actual hybrid limitation:** It is now one typed research evidence/workflow integration hosted in ICARUS, **not** a merged world engine or real-time UMBRA-to-ICARUS link. The public UMBRA site is a separate product with three routes and distinct browser storage keys. No site was modified. UMBRA draft archive PR #4 has a source-review accessor/toJSON safety finding; do not import that archive until it is fixed and independently reviewed.

**Next work and release gates:** Verify current PR #503 HEAD and dedicated CI, repair canonical CI failures without weakening tests, independently attest source/contract/rights via NEXUS, implement replay/queue/latency/transaction-cost comparisons against actual licensed historical depth if available, and measure real desktop/iPhone rendered UI and touch paths. Independent APEX/DAEDALUS review and ASCENDANCY governance remain mandatory. No force push, automatic merge, scheduled Codex, live trades or undocumented production deployment.

**Exact handoff mode:** This is a **development-branch** status record, not an installed Windows application or owner-authorized release. Do not create a second repository or fresh replacement microkernel. Continue PR #503 on agent/omnigenesis-phase-01-foundation and preserve all pre-existing phases 1–16.


---

## 14. Phases 19–20 offline execution research — authoritative current supplement

**Scope:** ICARUS branch agent/omnigenesis-phase-01-foundation, draft PR #503.
Older handoff instructions asserting Phase 17 is unimplemented or listing
only five workflow operators are superseded by sections 13–14 and actual
source. Do not replace ICARUS or its existing live/paper execution engine.

### New source and operations

- icarus_engine/omnigenesis/paper_harness.py — seeded synthetic OHLC
  generator, causal SMA-cross strategy, signals calculated at close and
  filled at later opens with adverse slippage, per-contract fee and
  integer-cent/tick accounting. Risk event and loss/drawdown caps and
  synthetic forced end settlement, plus training-only champion evaluation
  with one 70/30 synthetic split. This is NOT observed fill reconstruction
  or a guaranteed maximum loss.
- icarus_engine/omnigenesis/offline_order_router.py — versioned
  OFFLINE_SANDBOX mock order protocol with SUBMIT/ACK/FILL/CANCEL/
  CANCEL_ACK/REJECT/HALT/RECONCILE. Replay-local duplicate-message
  handling, partial fill and cancel races, buy/sell limit price checks,
  in-flight exposure caps and fail-closed mismatch halting. No network,
  credentials, real broker, real order ID, order output API or venue claim.
- icarus_engine/omnigenesis/agent_workflow.py — allowlisted operators
  paper_execution, paper_tournament, offline_order_router now join the
  prior prime/synthetic_book/market_intake/umbra_worldline/formal operators.
  Offline router safety halt or unmatched position snapshot fails its
  operator and BLOCKS all downstream dependencies. Its successful
  synthetic receipt may enter the existing summary-only immutable ledger.
- icarus_engine/omnigenesis/__main__.py — new explicit local CLI commands
  paper, paper-arena and offline-router. No automatic scheduler on these
  commands, no side effects except explicitly authorized file outputs
  in the existing research workflow command.
- Tests: tests_engine/test_omnigenesis_paper_harness.py and
  test_omnigenesis_offline_order_router.py plus integration/CLI/ledger
  tests in test_omnigenesis_agent_workflow.py. Negative tests verify
  data timing, execution costs, kill semantics, no agent authority,
  idempotency, stale cancels, late ACK/fills, signed exposure,
  post-cancel fills rejection and price limits.
- .github/workflows/omnigenesis-offline-agent-evidence.yml — new
  PR-triggered synthetic CI + seven-day JSON witness upload, read-only
  permissions, daily UTC seeded experiments. The cron does not run on
  this draft PR: scheduled GitHub workflows run from default branch
  only. After a review-approved merge, it can run at 06:41 UTC daily.
  No broker, live market, paid data, Codex or automatic promotion.

**Current evidence discipline:** See exact current PR head GitHub Actions.
Earlier Phase 19 and Phase 20 dedicated Python/mobile checks passed at
their respective SHAs; they do not prove later edits and are not a
full repository release certificate. A scheduled PR test was observed
passing at commit 0575a1d8, but later changes require fresh tests.
Compare canonical Linux/Windows, UI/browser, portfolio, federation,
install and native phone checks independently before any merge.

**Serious incomplete requirements:** independently authentic market data
providers, certified exchange-native MBO and quote state, order/latency/
queue/partial-fill inference with historical replay, official futures
contracts and margin, durable cross-session idempotency and order
reconciliation, verified broker sandbox adapter and outage failover,
actual kill-switch wiring, robust purged OOD validation and independent
APEX/DAEDALUS/AEGIS review. Neither synthetic nor mock router proves
live profits, survival under market gaps or human/AI consciousness.

**Reviewer acceptance rule:** preserve research_only=true,
execution_authorized=false, production_decision_authorized=false and
auto_promote=false, no live routes/secrets, no force-push, no blind
merge. Check that every new doc and source claim has code/test/CI
evidence at the same source SHA. Keep PR draft until independent
review and explicit release authorization.

---

## 15. Phase 21 and Sovereign Constellation specialist swarm (2026-11-23 UTC)

**Current status: DEVELOPMENT-BRANCH ONLY, PR #503.** This appendix supersedes any earlier claim that 16/18/20 are the latest phases. The project now contains an additional historical causality adapter and a drafted 12-worker GitHub-native research constellation. Confirm all source HEADs and exact CI again before modifying or merging.

- Phase 21: icarus_engine/omnigenesis/historical_paper.py and tests_engine/test_omnigenesis_historical_paper.py. Uses explicitly supplied historical OHLC with open_at, close_at, received_at and operator-declared SHA-256/source/license metadata. A signal may affect a simulated future open only AFTER its receipt timestamp. Late data delay entries and risk exits. This is hypothetical bar-open replay, never exchange-authenticated orders or observed profits.
- Constellation orchestration: icarus_engine/omnigenesis/constellation.py and tests_engine/test_omnigenesis_constellation.py. Immutable research-only plan and 12 SHA-256 receipts (CHRONOS, EXECUTION, RECONCILIATION, NEMESIS, WORLDLINE, MEMORY, each 2 shards). One fail-closed tribunal requires all 12 unique canonical receipts and same-code recomputation, rejects missing, duplicated, tampered, authority-escalated, malformed/symlinked evidence, and NEVER self-promotes.
- GitHub-native nested worker graph: .github/workflows/omnigenesis-constellation.yml parent, omnigenesis-constellation-worker.yml reusable specialists, omnigenesis-constellation-tribunal.yml reusable gate. PR/explicit trigger; post-merge hourly UTC :17 schedule is not active on a draft branch. Parent computes exact finite matrix, max 6 parallel, 7-day specialist and 14-day tribunal artifacts, read-only job permissions. No Codex, broker, paid provider, auto-merge or deploy.
- Full precise architecture, role map, truth and CI gates: docs/icarus/OMNIGENESIS_CONSTELLATION_SWARM.md. This is GitHub Actions process orchestration, not 12 sentient models, continuous cloud hosting, a real market MBO twin or guaranteed-profit strategy.
- Existing OMNIGENESIS research-only workflow includes all new Python unit/negative tests on the source branch. **DO NOT confuse its passing with verified nested GitHub Actions E2E:** independently verify a Constellation Swarm Actions run with 12 worker jobs and callable tribunal. If unavailable, record NESTED_WORKFLOW_E2E_UNVERIFIED. The separate upstream live peer expiry remains [issue #504](https://github.com/reppiks490/Icarus/issues/504) and must not be bypassed by raising freshness tolerance.
- Coordination source: reppiks490/icarus-owner-actions session chatgpt-20261123-omnigenesis-constellation-swarm (PLAN, subsequent UPDATE/HANDOFF). The existing ICARUS Sovereign Evolution ChatGPT automation is separate and remains non-Codex. Never force push, auto-merge, arm live broker execution or relabel research data.

Current acceptance must compare PR #503 exact HEAD against all canonical CI, not just experimental science tests. Ephemeral GitHub workers do not provide durable cross-run claims, authenticated market provenance or independent production signoff.
