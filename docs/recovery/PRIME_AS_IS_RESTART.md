# ICARUS restart checkpoint and mobile connection — 24 October 2026

**Working stopping point: retain the engine currently running on the PC and begin phone pairing against it.** New subsystem/defaults work is paused. Use the [complete current phone commands](../PHONE_ACCESS.md); they start a separately verified relay without changing the running desktop source, saved Inputs or journals.

## Full restart is held for Windows verification

The updated production candidate `3122d349524fbce803970dc34ab6fc74dad87467` (tree `9ad37de97e160aead6602351b54c43608086a006`) remains on draft [PR #471](https://github.com/reppiks490/Icarus/pull/471). It has not been deployed to the owner's PC by this cloud session.

Local frozen validation passed 4,152 runtime checks, 128 skipped and 111 subtests, plus 107 real Chromium checks. Both exact-head hosted Linux full suites passed. Both hosted Windows full suites failed: Windows 8.3 short-name paths are incorrectly classified as redirects by the defaults helper; the stopped-engine preparation fixture receives a Windows socket timeout instead of a refusal. Windows restart persistence checks passed. Visual CI also failed the delayed-start/power test. A local forced-delay browser experiment is retained as unshipped work; it is not included in the mobile correction.

These are pending gates, not an error-free release. Do not use the superseded full-restart block while they remain unresolved. The prior guide is [archived byte-for-byte](archive/2026-10-24/pre-mobile-pairing-PRIME_AS_IS_RESTART.md). Its old fetch-head checks target the previous branch head and are historical, not current commands. [Earlier notes remain archived](archive/2026-10-24/INDEX.md).

## Mobile-only correction and commands

The branch now adds a bounded relay correction at `8ec6199d0133db345b4ea81ef89f7519b3bf238f` (tree `d713310928c8f779f8e085e4e898f17180b4452a`): the hosted phone dashboard can send workspace/revision headers and read CSV identity headers. Exactly the relay and its test changed from candidate 3122; authentication, Origin restrictions and all other production files are unchanged.

The [phone procedure](../PHONE_ACCESS.md) fetches immutable Git objects and executes only the hash-verified, standard-library relay. It keeps the working desktop checkout and engine untouched. Relay tests: 37 passed; independent regressions: 3 passed; actual Python 3.10 operator rehearsal: 7 cases passed. New full-head hosted CI is separate and is not claimed green by these focused checks.

Owner action: create or reuse a strong viewer token through Main → Access, launch the relay and tunnel in separate Git Bash windows, then pair the printed HTTPS URL in the existing mobile Site. Actual PC readiness is checked by the command. Actual phone observation still requires owner readback; this cloud session cannot run the PC terminal or phone browser.

## Required settings for the next full restart

The [HIGHLY IMPORTANT NQ/ETHUSD/SOLUSD requirements](HIGHLY_IMPORTANT_RESTART_INFO.md) remain unchanged: every Main and CC asset receives actual current Main NQ strategy/chart inputs, except BOTH ETHUSD and SOLUSD use 30-minute charts, RTH/session filtering disabled and quantity input 25. Journals, asset selections, CC power settings and native instrument economics must remain preserved. Preparation must capture authenticated actual NQ or validate its saved sources, never silently substitute stock defaults.

NEXUS/AION connections and deadline/auth/status fixes remain published on the draft branch. No broader integration, live execution, provider purchase or main runtime merge is authorized by this checkpoint. Phone access proceeds against the currently working PC engine; default migration waits for the remaining verification fixes.
