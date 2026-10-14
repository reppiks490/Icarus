# Semantic work review fixes

Date: 2026-10-14. Owner: Codex, at the user's request to fix all four reproduced review findings.
Base: Phase 4A PR #338, `9dd6c4b45d7cecfe7862b3447e3c75e90555e733`.

## Scope and decisions

This follow-up remains stacked above #338. Prerequisite PRs #334–#336 and #338 retain their independent-review gates. Fixing these findings does not imply the entire stack has received an exhaustive audit or that deferred authenticated ingress (4B) exists.

Knowledge delta: this plan/evidence record, the Phase 4A design's hardening section, and README's link to that design. No unrelated product, trading or broker behavior changes.

1. Add real-journal regressions before implementation for root identity consistency, child retry after parent progress, operation ownership and fractional-time boundaries.
2. Apply root checks during pure replay, preserve existing child identity on retries, and derive operation receipt references only from semantically applied events.
3. Fix exact timestamp ordering in collaboration and the journal/delivery interfaces it depends on. Preserve canonical timestamp serialization, stored event bytes and deterministic event IDs. A fixed-precision rewrite would change old event identity; SQLite Julian-day comparisons lose submillisecond precision. Instead, Python aware datetimes compare values, and connection-local `ICARUS_TIME` collation provides the same ordering in SQL. No persisted schema, index or migration depends on the collation. Existing time indexes may no longer accelerate these predicates; sequence/filter predicates still apply. No new throughput claim is made.
4. Run all engine tests, CLI/plant smoke checks and workflow validation, then push a follow-up PR and check CI.

## Behavior changes

- Root and later requested events require envelope/payload actor principal and kind to match the normalized request's principal and kind. Inconsistent existing threads fail closed; no automatic event rewriting is attempted. This enforces declared semantic consistency, not authentication.
- Existing child history is projected before retry publication. A byte-identical retry returns its durable root even after parent progress, completion, cancellation or conflict. Changed request material is recorded as a conflicting root without changing the child. Genuinely new children still require a clean, current, assignable parent.
- Operation lookup excludes every projector-rejected event. A valid operation retry references the applied occurrence even if earlier unauthorized material reused its ID. A byte-identical rejected/conflicting event keeps its original semantic failure instead of being mislabeled as a successful-operation duplicate.
- Root/transition observation checks, deadlines, query/inbox visibility, delivery eligibility/retry, lease validation/recovery and lease metrics compare exact instants. Optional fractions and timezone offsets cannot reverse chronological order. Existing canonical bytes and IDs remain unchanged across reopening.

## Evidence

The initial 15 regression cases all failed on the unmodified base for the expected behaviors. After the implementation, all passed; a test assertion initially used `status` rather than the existing delivery API's `state` key, which was corrected without changing that API. Two additional guard tests cover preserved event IDs across reopening at a one-microsecond boundary and byte-identical conflicting-operation receipts. The Windows CI regression matrix now includes the new regression module.

All execution and production-decision authority flags remain false. No protected trading data or live broker operation is part of this change.

Final results are appended after verification. The review claims become stale if the stack bases, protocol, publication or persistence interfaces change; rerun the regressions and full suite on the resulting head.

## Local verification results

- Full engine suite on Python 3.12 with the repository's dev/bridge/ml/databento extras: **2429 passed, 3 skipped, 90 subtests passed**, exit 0.
- Original intelligence-stack suite plus the initial 15 regressions: **262 passed**, exit 0; the two later guard tests are included in the full-suite result above.
- Initial regression RED run: 15 failures against the unmodified reviewed base. Each failure reproduced the behavior described above.
- Plant setup, control CLI help and doctor JSON commands: exit 0 (smoke checks, not a claim of configured live feeds).
- actionlint 1.7.7 on the edited workflow and `git diff --check`: exit 0.
- Inline source/documentation consistency review: clear for this patch's four findings. No external reviewer approval is claimed. Akinator's packaged helper scripts are not installed in the workspace; no automated Akinator coverage/ledger gate is claimed.

Remote Linux/Windows CI and independent prerequisite reviews remain separate merge gates; consult the follow-up PR's current checks rather than treating these local results as stack approval.

## Full prerequisite-stack review and merge authorization

The owner subsequently instructed: “Review them then and merge.” Codex reviewed the complete stack with separate read-only reviewers for Phase 1, Phase 2, Phase 3 and Phase 4A. These are Codex reviews, not a claim that the previously requested Claude review happened. The owner's instruction authorizes this review-and-merge workflow; prerequisite ordering is preserved.

Additional confirmed findings and corrections:

- Phase 1: inbox tie-breaks now use exact timestamp order; mapping ingestion rejects string-valued collections rather than splitting identifiers into characters.
- Phase 2: candidate indexed routing fields and complete asset/tag membership must agree with the verified immutable envelope before delivery. Integrity failures roll back delivery creation. New receipts retain a lease-token SHA-256 digest (never the token), lease owner/window, journal sequence and explicit state transitions even after mutable cleanup. Existing receipts are historical evidence and are not backfilled or rewritten. Failure reason receipts record LEASED→PENDING/DEAD_LETTERED; subsequent state notices record that target→itself. Requeue records DEAD_LETTERED→PENDING. User reason metadata cannot overwrite generated audit fields.
- Phase 3: HTTP JSON reads stop incrementally at the body limit, and bearer comparison uses UTF-8 bytes with invalid Unicode rejected safely. The constant-time helper remains in use; its existing mock contract now expects bytes. One transport chunk is already allocated by ASGI before this application can reject it; the application does not continue consuming or accumulating an over-limit body.
- Phase 4A: byte-identical conflicting-root retries retain their conflict; child discovery accepts only canonical applied ancestry; challenges require a bounded claim and challenge responses require substantive text or a nonempty result mapping.

Regression evidence: the 20 initial additional cases failed on the reviewed implementation. Receipt state-chain review then exposed three further desired-state failures, corrected with explicit logical transitions. A separate invalid-Unicode token regression also failed before its correction. The final focused intelligence suite passes **286 tests**, including **39 review regressions**. Independent reviewers confirmed closure of their findings; their scope was the relevant layer, not a claim of mathematical absence of defects.

Merge strategy: merge the remediation into the Phase 4A branch, then merge #334, #335, #336 and #338 to main in that dependency order. Preserve merge ancestry so stacked diffs do not replay prerequisites. Validate the combined current-main tree before final integration and check final main CI. No broker service is launched and no execution authority is enabled by merging these backend libraries.

Final full-stack local run after all code/test changes: **2451 passed, 3 skipped, 90 subtests passed**, exit 0 (Python 3.12). Phase 1 closure reviewer independently ran 59 scoped tests; Phase 2 reviewer confirmed routing and receipt fixes with 38 scoped tests; Phase 3 reviewer independently ran 132 scoped tests; Phase 4A closure reviewer independently ran 129 scoped tests. These overlap and must not be summed. Workflow and whitespace validation passed. Remote checks and merge receipts remain externally verifiable in the PR history.
