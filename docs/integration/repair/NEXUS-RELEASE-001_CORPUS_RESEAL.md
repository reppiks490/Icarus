# NEXUS-RELEASE-001 — reconcile corpus identity and reseal release

Pinned evidence-lab revision: `d6a5868e3f3202ef82579aca40b83cb3f8a4b491`.

## Evidence already established by the handoff audit

- Owner bundle SHA-256: `11bc19567b0e02c10a5508610e0218065513e70197ea2f766cdc7da048010cec`.
- Bundle head/tag: `6529eed7623e9a967bb053c9a78e4102d2c18d6d`.
- Manifest's older code checkpoint: `763497739c89f54d215e211e9be295363c84bc5b` (ancestor, not final bundle head).
- Test evidence recorded in the audit: 117 passed and `compileall -q src tests` passed in that audit workspace.
- Release seal inconsistency: the manifest-listed hash for `artifacts/final_verification.v0.3.SOL.json` did not match the extracted file after the bundle's last commit.
- Older handoff catalog: 238 usable streams / 1,970,753 rows.
- Reconciled physical/logical evidence across ten ZIPs: 659 usable members / 13,788,256 logical rows.
- Unified all-ten distinct-hash comparison still requires a NEXUS-emitted canonical manifest.

These are audit findings, not a claim that this integration commit reran NEXUS tests.

## Required reseal procedure

1. Recover/identify the canonical NEXUS source at the exact bundle head.
2. Run the ZIP-native catalog over the approved ten-ZIP corpus.
3. Emit one deterministic unified manifest containing member identity, raw/logical hashes, row counts, duplicate-header handling, representation identity, source clock, and availability semantics.
4. Reconcile the manifest against the 659-member / 13,788,256-row evidence.
5. Resolve documentation ambiguity between old and current validation-status files.
6. Regenerate every release-manifest file hash after final artifacts are written.
7. Verify the release seal from a clean checkout/extraction.
8. Run as-of/availability leakage checks before empirical promotion.
9. Keep outputs research/shadow until realistic fills, costs, uncertainty, and independent validation are established.

## Connection gate

NEXUS may connect as an evidence/corpus provider only after source identity and manifest compatibility are established. It may not obtain broker authority or automatically promote ML candidates.

## Current status

EVIDENCE_ONLY / SOURCE_REQUIRED / RESEAL_REQUIRED.
