# Subsystem connection map

This map is intentionally asymmetric: a subsystem may have a documented contract without being integration-ready.

| Subsystem | Pinned evidence | Defensible responsibility | Current connection state | Authority ceiling |
|---|---|---|---|---|
| ICARUS | `reppiks490/Icarus@007e7018...` | Execution bridge, paper/shadow execution telemetry, audit/trainer framework | CANONICAL HOST | No execution authorization from this package |
| AION | `reppiks490/aion-parallax-research@12a7cb8...` | Time/identity/as-of/replay evidence substrate | CONTRACT_EVIDENCED | Research/shadow; integrity scope gap open |
| DAEDALUS | `reppiks490/daedalus-research-os@74ad941...` + AION integration docs | Protected research evidence/promotion workflow | CONTRACT_EVIDENCED | Research; no automatic promotion |
| ATHENA | AION code-atlas + DAEDALUS supervisory docs | Advisory/supervisory state and risk-routing boundary | CONTRACT_EVIDENCED, SOURCE_ADMISSION_REQUIRED | Advisory only |
| ARGUS | AION code-atlas | Validated microstructure semantics boundary | CONTRACT_EVIDENCED, SOURCE_ADMISSION_REQUIRED | Research/shadow |
| NEXUS | `reppiks490/icarus-csv-evidence-lab@d6a5868...` audit | Corpus catalog, representations, replay/sibling routing handoff | EVIDENCE_ONLY / SOURCE_REQUIRED | Research/shadow |
| ORACLE | No canonical repository source established here | UNKNOWN CANONICAL RESPONSIBILITY | BLOCKED | None |

## Connection protocol

Every sibling connection should present an admission descriptor containing at least:

1. `subsystem_id` and semantic version.
2. immutable source revision / package hash.
3. schema version(s) and canonical serialization rules.
4. time model: event time, availability time, ingestion time, timezone, replay/as-of behavior.
5. provenance/evidence identifiers with deduplication semantics.
6. uncertainty representation and explicit abstention/failure behavior.
7. execution authority flag (must default false).
8. required upstream dependencies and their exact versions.
9. emitted downstream interface contracts.
10. regression/oracle evidence actually run at the admitted revision.
11. known blockers/conflicts.
12. supersession policy.

## Cross-subsystem invariants

- No sibling may increase another sibling's authority merely by repeating a claim.
- Derived/composite evidence is not an independent replication of its source evidence.
- Cross-revision evidence must be marked and revalidated before promotion.
- Missing clocks/availability semantics block empirical promotion.
- Missing source identity blocks integration authority.
- Unknown/unsupported input fails closed at the receiving boundary.
- Execution is downstream of technical qualification; it is never implied by it.
