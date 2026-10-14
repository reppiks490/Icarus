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
