# Blocker Matrix

| ID | Severity | Finding | Required clearance |
|---|---|---|---|
| SRC-01 | P0 | Provider failures lack unified typed contract | Distinguish auth/entitlement/rate/network/no-data/stale |
| SRC-02 | P0 | Quote snapshots can look OHLC-compatible | OHLC trainer rejects non-OHLC schema |
| SRC-03 | P0 | Source event time can be lost | Preserve source_event_time, received_at, available_at |
| DAT-01 | P0 | Timestamp semantics duplicated | One parser for seconds/ms/us/ns/ISO |
| DAT-02 | P0 | 1M vs 1m collision | Case-sensitive chart identity before normalization |
| DAT-03 | P0 | 60m vs 61m collapse risk | Exact interval retained independent of family |
| DAT-04 | P0 | Conflicting duplicates survive trainer parsing | Hard reject conflict before labels/features |
| DAT-05 | P0 | OHLC geometry not fail-closed | Reject malformed rows |
| TIM-01 | P0 | Completed-bar features associated with bar-open time | Explicit feature_available_time |
| TIM-02 | P0 | Future events can enter event window | Separate schedule-known/result-available |
| TIM-03 | P0 | Labels cross split boundaries | Purge on label_available_time |
| CAN-01 | P0 | Same-interval agreement treated as predictive | Strict future lead test |
| CAN-02 | P0 | Candidate selection uses full history | Nested discovery/validation/holdout |
| ART-01 | P0 | Artifact path too coarse | Semantic experiment hash and content validation |
| BASE-01 | P1 | Logistic reporting insufficient | Null/logistic logloss+Brier+calibration |
| CAL-01 | P1 | Holdout isotonic contaminates final evidence | Pre-holdout calibration only |
| XGB-01 | P1 | Slot 1 unimplemented | Implement after upstream gates |
| ECON-01 | P1 | Emulator not real market microstructure | Stress costs/latency/capacity |
| ROB-01 | P1 | OOD/transfer/fragility unqualified | Run robustness harness after admission |

Do not create new sophisticated model layers while a P0 remains unresolved unless needed to clear that P0.
