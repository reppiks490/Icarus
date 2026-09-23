# Intelligence-stack bundle intake (CA, 2026-09-23)

The owner supplied four archives. Their documents are design inputs, not
authority to change running trades, expose secrets, or relax research gates.

| Archive | SHA-256 | Contents | Status |
| --- | --- | --- | --- |
| `DAEDALUS_WITH_BLUEPRINT_AND_INSTRUCTIONS.zip` | `4f4ae387ead09be2ebcafc1f012c8140ca3ab59fca5f4e797d8009459efdaa90` | Updated DAEDALUS Python package, tests, artifacts, and handoff | Inventory read; updated code not yet accepted |
| `ATHENA_BLUEPRINT_AND_INSTRUCTIONS.zip` | `e5b3e2c7eec5c8c2a5455f7233a487b03c40a002805487db0af6ae3bddd4bf29` | Supervisory architecture and next-model brief only | Blueprint, no runnable build |
| `ARGUS_MICROSTRUCTURE_BLUEPRINT_AND_INSTRUCTIONS.zip` | `55e0f9ef78ced3f55121cafe47a806e6a9e9769f2cddf67198b3541c5e6e79af` | Microstructure architecture and interface contracts only | Blueprint, no runnable build |
| `ICARUS_INTELLIGENCE_STACK_HANDOFF_BUNDLE.zip` | `c66e95baeab1dcc9efc69b2d9a4c35fc00fbfc3cc4b0d4f3866681a` | The above package/docs gathered under DAEDALUS, ATHENA, ARGUS | Do not double-count as independent evidence |

The newer DAEDALUS archive is distinct from the earlier
`DAEDALUS_CURRENT_BUILD_FOR_CLAUDE.zip` reviewed in
`DAEDALUS_PACKAGE_REVIEW_20260923.md`. That earlier 45-test pass does not
certify the newer ZIP. The latter reports a checkpoint dated 2026-09-23 and
explicitly names unfinished SQLite resource cleanup, orchestration tests,
authoritative corpus validation, and real-data protocol-v3 smoke tests.

## Sequencing

1. Finish the active ICARUS replay-evidence checkpoint. It is an internal
   research screen only; calendar and recorded-bar validation do not prove
   exchange execution parity or an untouched final holdout.
2. Review the updated DAEDALUS source in an isolated sibling directory. Fix
   verified release blockers without weakening candidate gates. Catalog the
   actual owner corpus by content and representation; the ZIP's 238-file
   subset cannot stand in for the claimed 800+ authoritative corpus.
3. Implement ATHENA as a separate advisory sibling, starting with versioned
   contracts, provenance, plane firewalls, deterministic replay and abstention.
4. Implement ARGUS as a separate evidence-tiered sibling, beginning with
   source capability classification. Candle-only E0 proxies cannot be called
   L2 depth, order flow, or a book map; no E3/E4 path exists without actual
   quotes/depth/order events.
5. Only after independent tests and shadow evidence, connect read-only
   research/advisory manifests to ICARUS. ICARUS retains execution authority.

Across all components: preserve repeated timestamps and chart identities;
freeze selection before protected evaluation; label synthetic stress as
synthetic; carry source/evidence/plane lineage; default to abstention on stale
or unsupported inputs. No archive contains proof of a qualified candidate or
permission to place live orders.

## AION / PARALLAX continuation (CA, 2026-09-23)

The separate Icarus branch `codex/aion-parallax-handoff` at `20c1f15`
contains a source-only AION ZIP and a PARALLAX proposal. Its ZIP SHA-256 is
`32ca851227bbce99d58df1e39fb69ac08f9fc2f42ba5a05239018f624dc1ce40`.
The ZIP did not contain the original Work task's Git history. Its 30 source
files were imported into the private native sibling repository
`reppiks490/aion-parallax-research` at `ca9f575`; continuation commit
`12a7cb8` adds a research-only ZIP/member inventory and hardens evidence
boundaries. Python 3.11 tests pass 21/21 and its 22-event synthetic demo
verifies its event chain. The independent code review found material gaps;
its disposition and remaining gates are in that repo's
`docs/CA_REVIEW_20260923.md`. This is **not** a live-data or performance
acceptance.

PARALLAX remains a proposed market-state/analog atlas. Only its provenance
inventory is implemented. The ten reviewed ZIPs contain 659 physical CSV
members and 542 byte-distinct contents; the DAEDALUS six-root extracted
catalog contains 803 physical files with the exact same 542 SHA-256 contents.
The extra 144 physical copies add no new bytes and were not deleted. Chart
type, contract, provider, availability and execution safety remain unverified;
no AION/PARALLAX packet may influence Icarus orders or spend a protected
DAEDALUS holdout. AION's native repo is the canonical place for its future
work; do not develop against the archived ZIP.
