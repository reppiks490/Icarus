# Atlas registry foundation execution record

Owner-transferred handoff: `b882078d6442af6d4ca674d572450009b004bffe`
on `feat/capability-data-discovery-registry-foundation`. Tasks 1–5 were
completed by the original worker; Atlas resumes Task 6 under the approved
2026-10-11 foundation plan and design. Isolated checkout; no peer-owned runtime,
collector, Brain/UI or strategy changes. Research/shadow authority only.

## Progress and verification

- Baseline: 29 inherited registry tests passed at handoff.
- Task 6 RED: missing `dedupe` module, as expected, before implementation.
- Task 6 GREEN: 7 dedupe tests plus 4 contract tests passed.
- Task 7 RED: missing `service` module before implementation.
- Task 7 GREEN: 43 foundation tests passed, including 7 service cases.
- Task 8 RED: missing CLI/tool module before implementation.
- Tasks 7–11: pending.
- Peer reservation sent to Claude and ChatGPT via the Engine coordination inbox,
  20261011T2101Z-atlas-registry-handoff.md. Delivery is not acknowledgement.

## Plan rulings

- R1: Task 6 references `DuplicateGroup.effective_independent_count`, which the
  inherited contract does not yet expose. Add its read-only constant-one property
  with this task. Groups reduce independence, never candidate/provenance records.
- R2: Structural keys retain meaningful query parameters (e.g. symbol=NQ versus
  symbol=ES) and constrain provider-capability keys by domain. Shared hosting is
  not shared capability; semantic similarity never auto-merges. Cost: more
  conservative families may require subsequent explicit review.
- R3: A normalized identity alone would delete referral observations (contradicting
  Task 7's explicit two-candidate gate). Candidate IDs combine the normalized
  identity, catalog ID and raw-row hash; entry/snapshot links retain all provenance.
  Revisions with unchanged rows reuse candidates. Cost: changed rows become new
  observations and are grouped non-destructively, not implicitly replaced.
- R4: Inherited store methods committed independently and could leave partial
  imports. Composable savepoints provide atomic pipeline rollback. Persist exact
  snapshot import summaries so later global ancestry changes do not rewrite old
  receipts; a repeat fetch preserves the first retrieval time. Cost: one small
  summary table and transaction helper; no runtime dependency.

## Verification authority

Tests use offline synthetic fixtures, the approved contract and negative controls.
They establish implementation behavior, not empirical source quality or alpha.
Independent release/peer review is still required. No main merge or deployment.
