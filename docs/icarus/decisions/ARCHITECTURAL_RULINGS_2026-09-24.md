# ICARUS Architectural Rulings — 2026-09-24

These rulings were made while converting the S4 curve design into an implementation plan.
They correct load-bearing defects before code is written.

## R1 — Contract metadata is itself point-in-time
**Decision:** require both `definition_asof <= snapshot_date` and
`contract.available_at <= snapshot_asof`.

**Why:** a historically named contract definition can still leak future database knowledge.

**Cost if wrong:** legitimate records may be rejected until provider timestamp semantics are
mapped explicitly; this is preferred to false historical knowledge.

## R2 — Financing uses canonical decimal-per-year units
**Decision:** normalize rates to `DECIMAL_PER_YEAR`; e.g. 5.18% is stored as `0.0518`.

**Why:** prevents 100x scaling mistakes between vendor percentage fields and estimator arithmetic.

## R3 — One authoritative financing value
**Decision:** `FinancingPoint` derives its rate from its canonical `Observation`.
Do not store an independent duplicate numeric field.

**Why:** duplicated state can diverge.

## R4 — No naked liquidity floats
**Decision:** volume/OI/spread inputs either retain point-in-time observation provenance or
remain absent from Phase A.

**Why:** an un-timestamped liquidity number can leak future information even when price data is valid.

## R5 — Provider agreement does not create a synthetic market price
**Decision:** `SourceComparison` reports consistency/dislocation but does not automatically
average providers.

**Why:** averaging can hide timestamp or methodology mismatches.

## R6 — Synchronization is semantic-specific
**Decision:** settlement-to-settlement, quote-to-quote, and futures-to-spot comparisons use
separate tolerances/policies.

**Why:** one generic time-skew threshold is not economically meaningful across all semantics.

## R7 — Price-domain validation depends on semantic type
**Decision:** futures/spot prices must be strictly positive; reference rates may be zero or negative.

## R8 — Test helpers must be explicit
**Decision:** create a dedicated test support module for deterministic builders such as
`make_contract`, `make_observation`, `make_snapshot`, and fixture loading.

**Why:** the earlier plan referenced undefined helpers/fixtures.

## R9 — Combo contracts are excluded from Phase A
**Decision:** initial curve construction accepts explicit outright `type="single"` contracts only.

## R10 — Capability and health are different
**Decision:** record what a provider supports separately from whether the current account/session
is entitled, authenticated, rate-limited, stale, or network-blocked.

## R11 — Strategy boundary stays hard
No direct `CurveSnapshot -> Pulse` path exists in S4.
`execution_authorized=false`.

## Governing principle
```
provider availability
    != data validity
    != estimator validity
    != trading authority
```
