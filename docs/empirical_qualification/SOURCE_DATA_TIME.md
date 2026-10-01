# SOURCE + DATA + TIME Contract

## ProviderObservation

```python
ProviderObservation(
    provider_id,
    provider_role,
    evidence_schema,
    instrument_identity,
    source_event_time,
    received_at,
    available_at,
    payload_sha256,
    auth_state,
    entitlement_state,
    freshness,
    execution_authorized=False,
)
```

Evidence schema is explicit: OHLC_BAR, QUOTE_SNAPSHOT, ORDERBOOK_SNAPSHOT, EVENT_RELEASE, MACRO_OBSERVATION, FUNDAMENTAL_SNAPSHOT, BLOCKCHAIN_STATE.

## QuoteSnapshot

LAST, MARK, BID, ASK and MID remain distinct. Cumulative total volume is not bar volume.

## Canonical timestamp

One parser normalizes numeric seconds/ms/us/ns and supported ISO timestamps while recording raw value, normalized epoch seconds, detected unit and timezone basis.

## Chart identity

`ChartIdentity(family, mechanism, exact_interval_seconds)`

60m = 3600 seconds; 61m = 3660 seconds; uppercase 1M remains monthly/unsupported until explicitly implemented.

## DatasetManifest

Must bind raw-file hash, canonical-row hash, parser version, source name, symbol, family, declared/detected interval, row counts, duplicates/conflicts, source-order inversions, nonpositive deltas, invalid timestamps/OHLC and first/last timestamps.

## Duplicate policy

Identical complete-evidence duplicates may be counted and collapsed. Any same-timestamp conflict hard-fails. Final training rows are strictly increasing.

## OHLC invariants

- high >= max(open, close)
- low <= min(open, close)
- high >= low

## TemporalSample

`feature_available_time <= decision_time < label_available_time`

## EventObservation

Separate scheduled_for, schedule_known_at and result_available_at.

Scheduled metadata requires known-at <= decision. Realized/surprise requires result-available <= decision.

## Split purging

Training labels resolve before validation start. Validation labels resolve before holdout start.

## Irregular bars

Renko/range/tick completion time must come from qualified source evidence. If unresolved: TEMPORAL_AVAILABILITY_UNRESOLVED.
