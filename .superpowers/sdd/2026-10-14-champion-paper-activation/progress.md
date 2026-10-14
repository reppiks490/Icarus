# Progress Ledger

Plan: `docs/superpowers/plans/2026-10-14-champion-paper-activation.md`

- [x] Task 1: Champion study bridge
- [x] Task 2: API and UI handoff
- [x] Task 3: Verification and documentation
- [x] Task 4: Durable paper outcome guard, regime scorecards, hold duration, and pressure pause

## Verification

- Created an isolated `.venv` and installed the declared dev, bridge, ML 2.0.3 and Databento extras needed for the complete suite.
- Focused tests: `.venv/bin/python -m pytest tests_engine/test_autopilot.py tests_engine/test_research_service.py tests_engine/test_activation.py tests_engine/test_activation_runtime.py -q` — passed.
- Final full suite: `.venv/bin/python -m pytest` — 2,187 passed, 3 skipped, 90 subtests passed.
- Browser scripts: `node --check icarus_engine/autopilot-ui.js` and `node --check icarus_engine/research-ui.js` — passed.
- Diff whitespace: `git diff --check` — passed.

## Remaining constraints

- Regime-scoped champions are recorded and used as search seeds, but their source replay still spans configured historical windows. Regime context is preserved as provenance and must not be read as proof that the observed trades were all generated in that regime.
- Champion context changes to chart type or session are rejected by the bridge until the qualified research engine can evaluate those dimensions in paired windows.
- Per-regime performance now reports last 30 settled lots, with a 12-lot minimum, <85% watch and <75% pressure pause. A reviewed paper activation checkpoints the cohort for the replacement configuration.
- The new performance-guard changes were not run through tests or verification commands in this continuation, at the user's direction.
- Regime-specific rates describe realized paper outcomes, not a guarantee of future accuracy or profits. Redeployment still goes through fresh research evidence and the existing paper activation boundary.
