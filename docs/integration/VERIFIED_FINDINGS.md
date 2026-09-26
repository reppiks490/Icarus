# Verified findings

All statements in this file are bounded by the pinned source revisions in `PROVENANCE_LEDGER.json`.

## ICARUS-RISK-001 — unsupported authenticated event can enter fill handling

**Status:** CONFIRMED DEFECT  
**Risk:** HIGH  
**Maturity:** SPECIFIED / REPAIR_READY, not VERIFIED_FOR_INTEGRATION  
**Execution authority:** false

At the pinned ICARUS revision, webhook parsing authenticates the payload and constructs an `Alert`, while the execution dispatcher special-cases `text` and `stop_update`; other event values flow into the order-fill path. The inspected bridge tests cover valid fills and malformed/invalid inputs but no negative contract test was found for an authenticated unknown event type.

**Required behavior:** only the explicit event set `order_fill | stop_update | text` may be accepted. Unknown events must fail closed before broker action. The dispatcher must also defend against internally/manual constructed `Alert` objects that bypass parser validation.

See `repair/ICARUS-RISK-001_UNSUPPORTED_EVENT_FAIL_OPEN.md`.

## AION-INTEGRITY-001 — event hash chain does not cover every durable decision-state family

**Status:** CONFIRMED SCOPE GAP  
**Risk:** MEDIUM-HIGH for provenance claims  
**Maturity:** SPECIFIED / DESIGN_REQUIRED

AION's pinned `EventStore` cryptographically chains the `events` ledger and `verify_chain()` recomputes source-manifest and event-chain integrity. Separate durable tables for `source_gap_history`, `predictions`, and `settlements` are protected by SQLite immutability triggers, but they are not part of the same global event hash chain.

Therefore the defensible claim is: **event history is hash-chain verified; not every durable AION decision-state family is currently covered by that chain.** Immutability triggers and cryptographic tamper evidence are distinct controls.

See `repair/AION-INTEGRITY-001_DURABLE_STATE_HASH_SCOPE.md`.

## TRAINER-CALIBRATION-001 — frozen Slot-1 contract contaminates the stated holdout

**Status:** CONFIRMED SPECIFICATION CONFLICT  
**Risk:** HIGH for model-evaluation validity  
**Maturity:** SPECIFIED / DESIGN_AWAITING_APPROVAL

The frozen ICARUS spec defines a time-ordered 60% train / 20% valid / 20% holdout split, says valid is for early stopping, requires reporting holdout log-loss/sign accuracy, and also requires fitting isotonic calibration on the holdout after the booster is frozen.

Once the holdout is used to fit calibration, that partition is no longer an untouched final evaluation set. Reporting metrics on the same partition no longer measures performance on data unused by fitting/calibration.

The current `xgb_slot.py` at the pinned revision is not an implemented XGB trainer, so this is a pre-implementation contract defect rather than evidence of already-produced contaminated XGB results.

See `repair/TRAINER-CALIBRATION-001_HOLDOUT_CONTAMINATION.md`.

## NEXUS-RELEASE-001 — corpus/release handoff requires reconciliation and reseal

**Status:** CONFIRMED HANDOFF BLOCKER  
**Risk:** HIGH for corpus identity and promotion authority  
**Maturity:** EVIDENCE_ONLY / SOURCE_REQUIRED

The pinned NEXUS handoff audit records:
- owner bundle SHA-256 `11bc19567b0e02c10a5508610e0218065513e70197ea2f766cdc7da048010cec`;
- bundle head/tag `6529eed7623e9a967bb053c9a78e4102d2c18d6d`;
- release manifest naming older ancestor `763497739c89f54d215e211e9be295363c84bc5b`;
- one release verification artifact whose actual file hash differs from the manifest entry;
- historical handoff catalog of 238 usable streams / 1,970,753 rows;
- rerun/reconciliation evidence totaling 659 usable members / 13,788,256 logical rows across ten ZIPs.

Until the NEXUS-native source identity, unified manifest, clocks/availability, and release seal are reconciled, NEXUS must remain research/shadow and cannot receive execution or model-promotion authority.

See `repair/NEXUS-RELEASE-001_CORPUS_RESEAL.md`.

## Cross-cutting finding — subsystem boundaries are now partially repository-evidenced

Pinned repository documentation supports these boundaries:

- **ICARUS:** execution/paper-fill telemetry and bridge surface.
- **AION:** shared temporal identity/as-of/replay evidence contract.
- **DAEDALUS:** protected research evidence and promotion workflow.
- **ATHENA:** advisory/supervisory state and risk-routing contract in current integration documentation.
- **ARGUS:** validated microstructure semantics contract in current integration documentation.
- **NEXUS:** adaptive corpus/representation/replay/sibling-routing fabric according to the evidence-lab handoff; native canonical source remains required.
- **ORACLE:** no canonical repository authority was established in this package. Any prior library/handoff role description remains provisional and must not be treated as canonical.

No subsystem name by itself establishes responsibility.
