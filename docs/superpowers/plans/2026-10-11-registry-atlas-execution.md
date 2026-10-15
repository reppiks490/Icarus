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
- Tasks 6–11 implemented and independently reviewed; human/peer integration
  approval remains separate. No main code merge or workflow activation.
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
- R11: Corrective independent review verified the original regressions fixed,
  then reproduced two additional explicitly labeled credential variants: `API
  key` and non-Bearer Authorization schemes. Two more end-to-end RED cases
  preceded the broader label/header guard. Cost: explicit nonempty credential
  headers/assignments, including documentary placeholders, fail conservatively;
  the safeguard still cannot identify arbitrary unlabeled secrets.
- R12: Git-blob-verified current upstream input revealed valid nested link labels
  that the inherited label regex rejected. A synthetic equivalent was RED before
  a linear balanced-bracket scanner restored those entries. Parser revision now
  advances to `catalog-registry-v3`, retaining v2 evidence rather than rewriting
  it. Non-entry marketing/statistics rows and unsupported URLs remain audited;
  observed row totals are parser totals, not upstream popularity/quality claims.
- R13: The plan also names a substantive-work flag as possible positive evidence.
  The current collector publishes `COLLECTED_PARTIAL` for completed positive
  pages; every other currently admitted status is blocked, incomplete or
  no-ready-work. A substantive flag cannot override one of those statuses or an
  unknown future status. Cost: future positive producer statuses require explicit
  schema review instead of silently broadening qualification semantics.

## Regression checkpoint

- Inherited baseline `b882078`: full `tests_engine` passed (2,181 passed,
  3 skipped, 90 subtests). After installing the repository's declared optional
  bridge/ML/Databento extras, the pre-review-fix implementation also passed the
  full suite (2,220 passed, 3 skipped, 90 subtests). No environment failures were
  patched in unrelated peer-owned code.
- Published Tasks 6–8 checkpoint `bd9914c165ac6d21e5fc1a81fb13e62413ddedcd`:
  GitHub Actions runs 38175184910 and 38175182144 both concluded success.
- Reviewed implementation full engine suite passed: 2,228 passed, 3 skipped,
  90 subtests (87.81s). Targeted suite before R11: 113 passed. The subsequent
  credential-label correction requires fresh final-tree verification below.
- Final code a432943: **116 targeted registry/CLI/unchanged-provider tests passed**;
  **2,229 full engine tests passed, 3 skipped, 90 subtests** (84.76s).
  Independent fresh-context review is **CLEAR**: no remaining Critical/Important
  findings. Eighteen failing-first corrections were exercised after review and
  upstream-format inspection; scope and authority remain unchanged.
- Full combined `tests tests_engine` also passed: **2,268 passed, 3 skipped,
  90 subtests** (85.12s); the CLI and existing provider regression are included.
- Published predecessor 022a40fa: GitHub Actions run38176831346 succeeded.
  Final corrective publication/CI is tracked on draft PR333; no earlier run is
  represented as proof of a later remote tree.

## Pinned upstream verification and limitations

The adjacent `2026-10-11-registry-atlas-verification.json` preserves exact source
commits, Git blob SHA-1, UTF-8 byte lengths, SHA-256, parser revision, snapshots
and bounded import counts. Both source bodies matched their pinned Git blob
hashes before the real-input run. No raw catalog/provider payload is committed.

| Pinned catalog | Commit | Imported entries | Unique observations | Audit failures |
|---|---|---|---|---|
| scraping-apis-for-devs | 8d3f03d15293077576cdb870925a5495a8414a7d | 4,131 | 2,591 | 22 |
| ai-agent-tools | 017b11024524bdb97a2c636c53b1069ce4ebb3e3 | 153 | 149 | 65 |

The local v3 verification retained 4,284 entry/candidate links and 2,740
candidates. Failures include non-entry marketing/statistics syntax and unsupported
URLs; counts are parser observations, not source quality or independence. All
imported candidates remained review-required/DISCOVERED with both authority flags
false; this root had no provider evidence and created zero qualification events.

Acquisition was through the configured GitHub connector and an injected pinned
input client, **not** the CLI's production HTTP path. Ordinary sandbox HTTP
returned NETWORK_FAILURE for all three sources. API-mega-list's immutable main
ref was resolved, but its large blob could not be obtained through the connector
(transport failure); it remains covered by offline contract tests, not current
upstream-input verification. No network/permission restriction was bypassed.

## Resumable handoff

Draft implementation: https://github.com/reppiks490/Icarus/pull/333. The original
worker acknowledged the reservation in Engine's 20261011T2107Z message and has no
concurrent writer. Atlas's scope is complete within the approved foundation;
release reservation to peer review, not automatic integration. Design PR332
remains separate. Next safe steps: review final exact-head CI and rulings, inspect
any intervening main changes, then obtain the human integration decision. Later
qualification/empirical/operator-surface plans are not silently started.

## Verification authority

Tests use offline synthetic fixtures, the approved contract and negative controls.
They establish implementation behavior, not empirical source quality or alpha.
Independent release/peer review is still required. No main merge or deployment.
