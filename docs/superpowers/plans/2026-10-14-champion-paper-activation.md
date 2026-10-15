# Champion Paper Activation Handoff Implementation Plan

> **For Codex:** Execute this plan task by task and keep `.superpowers/sdd/2026-10-14-champion-paper-activation/progress.md` current.

**Goal:** Connect Tactical Autopilot champions to the existing qualified research, independent review, and local paper activation workflow.

**Architecture:** Keep champions by asset and regime; add a champion-to-fixed-study bridge in ResearchWorkspace; expose an authenticated admin endpoint; add a per-champion action in Tactical Autopilot UI. Preserve existing qualification and activation boundaries.

**Tech Stack:** Python 3.10+, existing HTTP server/admin action framework, vanilla JS UI, pytest.

### Task 1: Champion study bridge

**Files:** `icarus_engine/research_service.py`, `tests_engine/test_research_service.py`

- Resolve requested asset and exact current champion ID from TacticalAutopilot state.
- Reject stale input snapshots and unsupported chart/session overrides.
- Construct a single-configuration input grid and fresh train/validation/holdout windows from cached closed bars beyond the durable holdout watermark.
- Start the normal research study and persist champion ID plus regime context in study provenance.
- Add tests for exact transfer and all fail-closed cases.

### Task 2: API and UI handoff

**Files:** `icarus_engine/server.py`, `icarus_engine/autopilot-ui.js`, relevant server/UI tests

- Add authenticated `/admin/research/champion-study` endpoint.
- Add a promotion action for each champion that starts the study and shows its job ID.
- Make clear in UI that this queues qualification, not activation.
- Verify auth, malformed request rejection and endpoint wiring.

### Task 3: Verification and documentation

**Files:** `.superpowers/sdd/2026-10-14-champion-paper-activation/progress.md`

- Run focused handoff, research, autopilot and activation tests.
- Run the complete test suite and inspect the final diff.
- Record test evidence and any remaining constraints.
