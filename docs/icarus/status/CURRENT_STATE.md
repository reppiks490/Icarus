# ICARUS Current State — 2026-09-24

## Pinned repository
`reppiks490/Icarus/main@007e70189945b8e112904cf92b2b1a12e43792d6`

## Pipeline
- `PIPELINE_POLICY_VERSION=icarus-control-v1`
- `NEXT_EXPECTED_STAGE=ARCHITECTURE_EXTRACTION_FORGE`
- `execution_authorized=false`

## S3 summary
No researched edge has independently satisfied the complete requirements for
`EMPIRICALLY_SUPPORTED` promotion.

Current global blockers:
- multiple-testing universe remains uncontrolled;
- several hypotheses remain data-blocked or proxy-only;
- many current confluence channels have high redundancy risk;
- some research paths lack behavior-neutral ablation seams;
- genuine predictive lead/lag still requires synchronized point-in-time datasets.

## Highest-value verified repo findings
1. `icarus_engine/strategy/pulse.py` "XGBoost5" is a hand-built derived composite,
   not a trained XGBoost model.
2. `icarus_engine/trainers/xgb_slot.py` still raises `NotImplementedError`.
3. Active trainer path is the logistic baseline in `trainers/run.py`.
4. Current trainer feature set excludes optional DXY/VIX/TNX fields from active
   `FEATURE_KEYS`.
5. Correlation tooling correctly labels itself association-only, but must not be
   promoted into causal/directional authority.
6. Event/calendar research has temporal and redundancy defects documented in the audit.
7. Existing explicit contract-roll logic is NQ/ES/YM-oriented; GC/SI/PL/PA remain
   unsuitable for true term-structure research through continuous/front symbols alone.

## Current S4 work
A research-only point-in-time `CurveSnapshot` architecture has been specified for
explicit futures maturities, provenance-preserving spot/rate alignment, deterministic
replay, estimator isolation, falsification, and fail-closed promotion.

## Not implemented
The curve research subsystem described in the S4 spec/plan has **not** been implemented
or tested in the repository by this loop. The documents are architecture and implementation
contracts, not completion evidence.

## Resume instruction
After all loop handoffs are uploaded to this integration branch:
1. reconcile duplicate/conflicting claims;
2. freeze the combined S3 registry;
3. preserve all failed attempts in the attempt ledger;
4. review S4 architectural dependencies;
5. continue the same research loop without resetting trial counts or maturity.
