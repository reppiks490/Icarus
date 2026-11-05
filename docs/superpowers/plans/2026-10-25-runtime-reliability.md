# Runtime reliability implementation plan

**Goal:** Repair the observed live cloud UI failures and verify runtime, API, browser, mobile, research and federation contracts without disguising absent evidence or authorizing live execution.

**Architecture:** Preserve native workspace identities and authority. Bound repeated reads, separate worker availability from valuation, preserve authoritative credential revocation, and exercise the real app after repairs.

**Spec:** Owner's request in this session and /workspace/ui-audit/FINDINGS.md.

## Constraints

- Existing isolated cloud checkout; preserve user changes and private state.
- No live broker arming, fake market/depth data, invented credentials or performance claims.
- Root owns dashboard.html, learning-ui.js, brain-ui.js, workspace-client.js, workspace_power_ui.js, server.py and related new regression files.
- Access repair agent owns access_control.py and access contention regressions.
- Status repair agent owns command-centers-ui.js, paper-pnl-ui.js and focused status regressions.
- Test the failure before implementation. Run focused checks, combined suite, and repeat actual browser interactions.

## Tasks

- [ ] Trace AccessRegistry contention; reproduce concurrent audit writes and authentication reads; repair without cached credential authority or weaker revocation; verify viewer/revocation/lock contracts.
- [ ] Reproduce read overlap under delayed responses; bound/deduplicate Brain requests and make Learning refresh manual as documented; preserve cancellation and selected-workspace isolation.
- [ ] Diagnose busy CC power transition; make accepted worker lifecycle operations complete under ordinary reads while preserving configuration revisions and no double execution.
- [ ] Separate actual runtime health from incomplete/stale P&L; provide accurate valuation messages and preserve unavailable monetary values.
- [ ] Make audit revision/freshness visible; historical success must not claim verification of the running checkout.
- [ ] Run canonical full suite and browser suites, repair additional confirmed defects, then expand sibling/integration checks and mobile validation.
- [ ] Restart only this task's runtime with its retained private state; repeat all-panel browser tour, longer Brain/Learning checks, controls and request-error capture. Save exact results and remaining real external prerequisites.
