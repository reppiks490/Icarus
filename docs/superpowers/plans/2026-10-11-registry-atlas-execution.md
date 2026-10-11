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
- Task 8 GREEN: 57 targeted registry/CLI tests passed; checkpoint published in
  [Icarus PR333](https://github.com/reppiks490/Icarus/pull/333), draft.
- Task 9 RED: missing federation module before implementation.
- Task 9 GREEN: federation plus unchanged provider collector regression: 30 tests
  passed. Receipts are re-hashed before events; no provider network/acquisition.
- Task 10 RED: workflow-contract test failed because workflow file was absent.
- Task 10 GREEN: 77 registry/CLI tests passed; refresh proposed, not activated.
- Task 11 RED: documentation test failed because operator document was absent.
- Tasks 7–11 implemented; final regression/review in progress.
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
- R5: Task 9 references `ProviderLink.status`; expose it as a read-only metadata
  property. Exact name fallback establishes ancestry links only; provider access
  does not prove a scraper/tool wrapper's access. Positive access events require
  an exact admitted domain and recent re-hashed evidence; rejected candidates do
  not advance. Cost: conservative name-only matches await explicit qualification.
- R6: The plan's rebase retry conflicts with Engine's canonical no-shared-history-
  rewrite rule. The new workflow fetches and performs non-rewriting merges, then
  fast-forward pushes; conflicts abort, with no force or reset. Cost: possible
  merge commits or an explicit blocked refresh instead of rewriting history.
- R7: Credential-bearing URL userinfo/query parameters are invalid metadata,
  not a reason to silently strip credentials and keep the original secret URL.
  New failing tests confirmed the inherited normalizer accepted these; now they
  are hashed parse failures. CLI federation is invoked only over existing local
  files and emits bounded status counts; malformed provider catalogs fail closed.
- R8: Fresh-context review confirmed rejected secret URLs could still enter raw
  gzip cache. Intake now rejects explicit credential-bearing content before any
  snapshot/cache persistence; three regression cases were RED before this fix.
  Cost: an entire credential-bearing catalog needs upstream correction rather
  than a silent partial success; failure receipts contain only safe reason codes.
- R9: Independent review reproduced five important defects and a fractional-
  timestamp ordering defect. Fourteen failing regressions preceded the fixes:
  quoted credential assignments/aliases, transport origins, operation denials,
  replay-cache integrity, parser fidelity/empty-format failure and time ordering.
  An additional non-admitted `www` origin was RED before its guard. Access needs
  an admitted HTTPS hostname/effective port 443; ancestry links remain intact.
  Sanitized operation blockers remain separate from aggregate provider access.
  Cost: conservative transport eligibility and allowlisted/unknown failure codes.
- R10: Parser corrections advance the CLI parse revision to `catalog-registry-v2`;
  federation links similarly carry `registry-federation-v2`. This avoids mutating
  evidence under a previously pinned parse/link identity. Gzip cache integrity is
  verified before success and corrupt caches are atomically repaired from pinned
  bytes. Zero-import refreshes fail closed rather than overwriting latest with an
  empty success. Cost: an audited empty snapshot may remain locally and upstream
  format changes require operator correction, not implicit parser guessing.

## Regression checkpoint

- Inherited baseline `b882078`: full `tests_engine` passed (2,181 passed,
  3 skipped, 90 subtests). After installing the repository's declared optional
  bridge/ML/Databento extras, the pre-review-fix implementation also passed the
  full suite (2,220 passed, 3 skipped, 90 subtests). No environment failures were
  patched in unrelated peer-owned code.
- Published Tasks 6–8 checkpoint `bd9914c165ac6d21e5fc1a81fb13e62413ddedcd`:
  GitHub Actions runs 38175184910 and 38175182144 both concluded success.
- Final-tree targeted/full regressions and independent re-review are pending;
  earlier green runs are not represented as proof of later tree changes.

## Verification authority

Tests use offline synthetic fixtures, the approved contract and negative controls.
They establish implementation behavior, not empirical source quality or alpha.
Independent release/peer review is still required. No main merge or deployment.
