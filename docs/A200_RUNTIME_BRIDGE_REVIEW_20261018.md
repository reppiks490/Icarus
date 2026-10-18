# A200 receipt boundary review and repair

Reviewed original PR #443 at `0e772ec4541cc3b26e34da13de3a7832a614e3c0` in an isolated worktree. The bridge retained a receipt checksum but cast timestamps with `int()` before hashing. Replacing a validated timestamp `1799999700` with `1799999700.5` still reused the receipt while keeping the altered runtime value. Numeric-string OHLCV and a non-Bar object with matching attributes also passed the canonical digest check.

The repair checks the original validator's Bar/integer-timestamp contract before hashing and requires numeric OHLCV values. It preserves numeric int, float, Decimal and Fraction semantics. It does not rewrite the receipt, coerce timestamps, change eligibility or assert entitlement. Execution remains unauthorized.

Ten new regression checks failed before repair (nine accepted aliases/impostors and a Boolean timestamp rejected only at the later checksum check); eleven module cases passed. After repair, all 21 bridge cases and the 70-case bridge/market-universe/qualification selection pass. Independent exact-source review of `7b0b818d95df2270449a50ef0a8448203537799c` found no severity findings and independently reran all 70 cases.

The original branch's full suite passed 2,894 tests with two known expired listing-fixture failures, three skips and 111 passing subtests. These dated test failures were already repaired in #447. Ordinary merge `4173e38586d4425303b73ae629d748b97634adf5` brings in verified futures #450 at `63e238f4aedf06744b0581281727cdafb7f0e0a1`, including current main and deterministic fixtures. The merged runtime passes **3,004 tests, 3 skips and 111 subtests**, in 140.59 seconds. The original #443 and futures feature branches remain untouched.

The explicit Windows pytest selection now also includes this 21-case bridge module. Fresh hosted verification is required for the published head; the older futures green run does not cover this repair. No provider request, protected-holdout experiment, licensed-data export, broker connection or main merge occurred. This remains a contract boundary without a production caller; runtime consumption requires a separate bounded integration.
