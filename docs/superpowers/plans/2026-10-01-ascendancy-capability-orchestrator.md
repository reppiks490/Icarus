# ASCENDANCY Capability Orchestrator Implementation Plan

**Goal:** Give ICARUS a machine-readable, dashboard-visible registry of every relevant connected capability, its evidence contract, point-in-time availability, prohibitions, and authority.

**Spec:** docs/superpowers/specs/2026-10-01-icarus-ascendancy-design.md

## Constraints
- Research/shadow only.
- execution_authorized=false.
- production_decision_authorized=false.
- Missing data is UNAVAILABLE or UNVERIFIED, never zero.
- Provider contracts must say both what may be claimed and what must not be inferred.
- Never commit credentials, tokens, emails, account balances, or session IDs.
- Session probe status is point-in-time evidence, not permanent engine health.
- New behavior is test-first.

## Task 1 — Registry + audit snapshot
Create:
- icarus_engine/ascendancy/__init__.py
- icarus_engine/ascendancy/capabilities.py
- icarus_engine/ascendancy/capability_catalog.json
- icarus_engine/ascendancy/capability_audit_2026-10-02.json
- tests_engine/test_ascendancy_capabilities.py

Expose:
- capability_snapshot()
- capability_contract(provider_id)

Tests cover provider inventory, blocked states, market-data boundaries, on-chain-vs-exchange distinction, no secret fields, and false authority flags.

## Task 2 — Read-only API
Modify:
- icarus_engine/server.py
- tests_engine/test_ascendancy_capabilities.py

Add:
- GET /api/ascendancy/capabilities

## Task 3 — Dashboard
Create:
- icarus_engine/ascendancy-ui.js

Modify:
- icarus_engine/dashboard.html
- tests_engine/test_dashboard_js.py

Add top-level ASCENDANCY tab with capability totals, verified/blocked/unprobed state, evidence domains, prohibited inferences, degradation reasons, and authority state.

## Task 4 — Brain registration + docs
Modify:
- icarus_engine/brain.py
- tests_engine/test_brain.py
- docs/icarus/UNIFIED_INTELLIGENCE_SPINE.md

Create:
- docs/icarus/ASCENDANCY_CAPABILITY_ORCHESTRATOR.md

Register subsystem capability-orchestrator owned by OMEGA.

## Task 5 — Verification
Run exact branch CI, inspect Linux and Windows jobs, review the whole diff against the spec, and fix Critical/Important findings using RED→GREEN.

## Knowledge delta
Code: ascendancy registry, API, dashboard, brain registration.
Tests: registry, API, dashboard, subsystem registration.
Docs: capability orchestrator and unified-spine linkage.
Rules/skills: none added; existing truth and authority rules are reused.
