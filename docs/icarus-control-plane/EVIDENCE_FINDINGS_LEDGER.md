# ICARUS Evidence & Findings Ledger — Consolidated Delta

## VERIFIED

### F-001 — public plant CLI contract remains open
Observed behavior/tests support the global option form `icarus-plant --root DIR setup`.
Repository documentation advertises `icarus-plant setup --root DIR`.
PR #18 made CI green by changing invocation order; no verified regression proves the documented form.
Status: **WORKAROUND_VERIFIED / CONTRACT_DEFECT_OPEN**.

### F-002 — control-plane receipt verification implemented
PR #18 adds deterministic JSON canonicalization, SHA-256 receipt digests, same-cycle policy/snapshot checks, maturity ceilings, origin de-duplication and structural promotion gates.
Status: **IMPLEMENTED_STACKED**.
Boundary: structural coherence does not prove a trading claim or grant execution authority.

### F-003 — market-data vintage preservation implemented
PR #19 records point-in-time observations/revisions before canonical history merge and fails closed on provenance failure.
Verified run: `36065964176`.
Status: **IMPLEMENTED_VERIFIED_STACKED**.
Residual: cryptographic chain/head verification and complete as-of reconstruction not yet established.

### F-004 — OMNIVISION Stage 0 temporal controls verified
Runs:
- `36071102061` success
- `36071102460` success
at revision `511814e1d4f4a2527abaa3b6e3472a66df666281`.
Coverage includes non-reused walk-forward boundaries, decision-time/availability-time safety, boundary tests and Python 3.10-3.13 verification.
Status: **VERIFIED GO FOR STAGE-0 SCOPE**.

### F-005 — OMNIVISION Stage 1 planned, not implemented
Current branch head observed: `9f3c792d44fd9142e0b98676224dfe50d740db3b`.
Stage-1 plan adds:
- source capability registry
- provenance DAG
- search-aware trial ledger
- governed evidence gateway
without provider adapters or execution authority.
Status: **IMPLEMENTATION_READY PLAN / NOT IMPLEMENTED**.

### F-006 — AION replay gap history integrity gap
Current pinned head: `12a7cb8ef99e84ce50b766db0aea1592b3906f80`.
Replay-relevant `source_gap_history` is not covered by the main integrity verification chain.
Status: **OPEN DEFECT**.

### F-007 — DAEDALUS protected-evidence lineage gap
Current pinned head: `74ad94149b02ddd3f69d535ee5fdc00c1fdbe096`.
Protected exposure identity is tied to full snapshot SHA without proven stable logical-source ancestry across descendants.
Status: **OPEN DEFECT**.

### F-008 — canonical ARGUS/ATHENA/NEXUS/ORACLE repos not found
Installed-repository searches found AION and DAEDALUS only for these named sibling systems.
Status: **FAIL-CLOSED / CANONICAL IDENTITY REQUIRED**.

### F-009 — provider capability is runtime/versioned state
Observed during provider admission work:
- some connectors reachable and useful,
- some authenticated but plan/entitlement constrained,
- some quota exhausted,
- some blocked by network/source policy,
- some syntactically usable but semantically irrelevant.
Status: **ARCHITECTURAL REQUIREMENT**.

### F-010 — evidence independence must follow upstream lineage
Two vendors sourcing the same upstream record are not independent corroboration.
Status: **LOCKED IN OMNIVISION v2 DESIGN**.

## REPORTED / NOT YET CANONICALLY RECONCILED

### R-001 — AEGIS isolated hardening work
Conversation history reported deterministic replay, nanosecond temporal checks, fail-closed qualification, monotonic uncertainty authority, tamper-evident ledger behavior and multiple passing test batches.
Do not call merged/current until canonical repo/revision is located and revalidated.

### R-002 — empirical qualification contamination
Conversation history reported isotonic calibration using a nominal holdout, implying the affected performance claims are NOT QUALIFIED until clean calibration/evaluation separation is rerun.
Treat as a high-priority research-integrity warning pending canonical artifact revalidation.

### R-003 — empirical research candidate domains
Carry/term structure, variance-risk-premium, intraday/session effects, pre-FOMC behavior and cross-market transmission were explored.
Several proxy shortcuts were rejected.
Do not promote any as live edge without exact data/provenance + chronological OOS evidence.

## Supersession rule

A later finding supersedes an earlier one only when:
- scope is compatible,
- revision/config is equal or newer,
- validation is equal or stronger,
- no load-bearing conflict remains.

Green CI alone does not supersede a root-cause defect if the behavior was merely bypassed.
