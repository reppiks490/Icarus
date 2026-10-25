# NEXUS and AION Connections Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement task-by-task.

**Goal:** Connect actual native NEXUS health processing and AION durable monitoring history to Main and selected CC runtimes for the next paper restart.
**Architecture:** Pinned stdlib cores, private scoped background services, cached authenticated APIs and a disposable UI component. Reuse the existing worker power lifecycle; no heavy work occurs in HTTP handlers.
**Tech Stack:** Existing Python 3.10+, SQLite, JavaScript, pytest and Chromium; no new runtime package dependency.
**Spec:** docs/superpowers/specs/2026-10-24-nexus-aion-connections-design.md

## Global Constraints

Source pin27ae69c593ede3019957100cd401625bd2424f43. Preserve cached chart performance and request deadlines. Receipt-time availability; unknown provider SLO/sequence stay unknown. Research/monitoring only; execution and production authority false. Preserve saved state and independent CC power. Use actual native code and explicit source hashes. Python3.10 compatibility is tested, not assumed from upstream3.11 declaration.

## Review Focus

- Slow/busy SQLite must not delay HTTP reads or resurrect an OFF workspace.
- Missing/reused runner caches must remain unknown/stale with truthful observation time.
- Repeated unchanged observations must not grow the ledger at every UI poll.
- Corrupt history and unknown native SLOs must not be relabelled as healthy.
- Config/portfolio replacement must not attach old observations to a new selected identity.

### Task 1: Pin and verify the two native cores

Files: icarus_engine/native_subsystems/**; tests_engine/test_native_subsystem_sources.py.
Produces namespaced native NEXUS SourceHealthRegistry/VectorEvent and AION SourceSpec/Observation/EventStore.
- [x] Write integrity/import/actualPython3.10 smoke regressions; run to observe missing-module failure.
- [x] Embed the four unchanged canonical modules, loader namespaces and source manifest.
- [x] Run integrity/import/native persistence tests and document the compatibility boundary.

### Task 2: Build the scoped background connection

Files: icarus_engine/subsystem_connections.py; tests_engine/test_subsystem_connections.py.
Consumes Task1 native classes and a snapshot_supplier callback. Produces NativeSubsystemConnections and capture_portfolio per the spec.
- [x] Write actual native health/store tests: dedup, time visibility, close/reopen chain, corruption, invalid input, busy I/O and read latency.
- [x] Implement metadata-only capture and bounded cached service lifecycle with native processing outside requests.
- [x] Verify explicit failure/unknown states and deterministic recovery; no provider access or authority escalation.

### Task 3: Wire Main and selected lifecycle/API

Files: icarus_engine/server.py; icarus_engine/workspace_panels.py; tests_engine/test_subsystem_connections_api.py.
Consumes Task2; produces authenticated cached Main/CC readers and independent worker lifetime.
- [x] Add failing route/isolation/OFF-replacement/shutdown regressions.
- [x] Start/drain native services with existing background/lifecycle hooks. No sampling from GET, no shared runtime lock during slow I/O.
- [x] Verify API identity and Main availability while a CC/native store is blocked.

### Task 4: Expose actual status without dashboard churn

Files: icarus_engine/subsystem-connections-ui.js; icarus_engine/dashboard.html; tests_engine/test_subsystem_connections_browser.py; tests_engine/test_workspace_dashboard_browser.py.
Consumes cached API schema; produces IcarusSubsystemConnections.mount(container, client) and disposal.
- [x] Add failing real-browser status, unknown/error, visibility/disposal, source-isolation and steady-refresh checks.
- [x] Build the small mounted view, selected request mapping and explicit diagnostic state.
- [x] Exercise it through the existing hosted browser module without changing chart/status deadlines.

### Task 5: Integrate, review and publish the next restart

Files: .github/workflows/test.yml; current guide/START_HERE and byte-exact archive.
- [x] Ensure new pure/API tests run on Windows; browser tests run in the existing required Chromium step.
- [ ] Run meaningful scoped and combined suites, actualPython3.10 and hosted Linux/Windows/visual checks; preserve failures and source identities.
- [ ] Independently review core/lifecycle/UI boundaries, publish on existing restart PR only after local gates, then pin exact tested source in the new guide and archive prior bytes.
- [ ] Deliver full Git Bash commands, retain owner-PC verification as a separate observation, and publish a durable handoff.

Integration evidence before publication: native core 16 checks including actual Python3.10 lifecycle; API/browser independent review 23 checks; canonical LF checkout regression5checks; wheel on Python3.10 includes all four exact native source modules and provenance. Revision mismatch and all-invalid-state regressions failed before their corrections, then passed. Full and broader browser suites run on the frozen production files; hosted and PC readback remain delivery gates.
