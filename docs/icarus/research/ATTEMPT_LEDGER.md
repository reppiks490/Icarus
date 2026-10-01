# ICARUS S3 Attempt Ledger

This ledger records the effective trial universe represented by the current research
corpus. It is intentionally append-only in concept: failures and discarded hypotheses
must not disappear when a later loop changes direction.

## Control fields
- `MULTIPLE_TESTING_STATUS=UNCONTROLLED`
- `execution_authorized=false`
- Pinned repo baseline: `007e70189945b8e112904cf92b2b1a12e43792d6`

## Recorded attempt IDs
- `S3-TSMOM-001`
- `S3-OFI-001`
- `S3-OFI-COST-001`
- `S3-CARRY-001`
- `S3-HEDGE-001`
- `S3-VRP-001`
- `S3-VRP-PROXY-001`
- `S3-VRP-COMDIR-001`
- `S3-TOD-001`
- `S3-FOMC-DRIFT-001`
- `S3-XLAG-001`
- `S3-FIXEDLEADER-001`
- `S3-CORRVOTE-001`
- `S3-REV-001`
- `S3-REV-GENERIC-001`
- `S3-BASISREV-001`
- `S3-LP-001`
- `S3-SPREADCAPTURE-001`
- `S3-LP-QUEUE-001`
- `S3-REGIME-001`
- `S3-REGIME-LABEL-001`
- `S3-REGIME-SMOOTH-001`
- `S3-CORR-ALPHA-001`
- `S3-CORR-INDEP-001`
- `S3-DISP-001`
- `S3-XGB5-LINEAGE-001`
- `S3-MACRO-SCHEDULE-DIR-001`
- `S3-MACRO-SURPRISE-001`
- `S3-MACRO-REDUNDANCY-001`
- `S3-CARRY-DATA-002`
- `S3-CARRY-CONTINUOUS-001`

## Accounting rule
A failed test, abandoned parameter family, data-source revision, changed market root,
or new research cycle does not reset effective trial count. Any future DSR/PBO/CSCV
or other multiple-testing correction must operate on a defensible trial universe rather
than only the surviving winners.

## Future append contract
Every new loop entry should record at least:
```
RESEARCH_ATTEMPT_ID
CLAIM_ID
family
market
sample/horizon
data revision
estimator/config family
outcome
failure reason
OOS status
cost model
dependency/conflict links
```
