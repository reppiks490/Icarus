# Master Worklog

This worklog consolidates the substantive findings from the ICARUS Empirical Research / AEGIS qualification lane.

## Program transition

The lane started as an audit/red-team process, then was deliberately changed into a finite closure program to avoid endless theoretical discovery.

Final qualification chain:

`SOURCE -> DATA -> TIME -> BASELINE -> XGB -> ECONOMICS -> ROBUSTNESS`

The rule is dependency strictness, not sophistication.

## A. Evidence / provenance kernel

A reference evidence kernel was developed around deterministic canonical JSON, SHA-256 identity, feature contracts, evidence envelopes, qualification outcomes, temporal checks, source allowlists, missing/stale rejection, sequence monotonicity, correction semantics, tamper-evident audit concepts, and `execution_authorized=false`.

Core invariant: critical invalid/unknown evidence forces authority cap to zero.

## B. Event timing leakage

Repository code in `icarus_engine/events/calendar.py` permits event windows based on `ts - pre <= event_ts <= ts + post`. With current defaults this can include future events relative to the bar timestamp.

A single event `ts` is insufficient. Separate scheduled event time, schedule-known-at time, and realized-result available-at time.

Scheduled metadata is usable only when `schedule_known_at <= decision_time`. Realized value/surprise is usable only when `result_available_at <= decision_time`.

## C. Label boundary leakage

Current next-bar labels are attached before 60/20/20 slicing. The final training label can resolve on the first validation bar and the final validation label can resolve on the first holdout bar.

Every sample therefore needs `label_available_time`, and prior blocks must be purged by actual resolution time.

## D. Horizon comparability

“Next bar” has different economic meaning across seconds, minutes, hours, daily/weekly, Renko, range and tick data. Raw family-level metrics are not directly economically comparable without controlling for target horizon, entropy, and calendar exposure.

## E. Bar-open timestamp vs completed-bar features

Canonical market-bar `ts` is bar-open time while trainer features consume completed OHLC-derived values. Those values are not available at bar open.

Core invariant: `max(feature_available_times) <= decision_time < label_available_time`.

For irregular bars, completion time cannot be invented from a fixed duration.

## F. Candidate same-interval pseudo-prediction

Current candidate audit can compare candidate and execution returns over the same interval. That is contemporaneous agreement, not predictive lead.

Only candidate information fully available before the execution decision can qualify for future-outcome testing.

## G. Candidate selection leakage / multiple testing

Candidate metrics such as overlap/sign/tide/macro agreement are computed over full supplied history. Selection therefore needs a nested discovery/validation/holdout procedure.

A 55% threshold is not statistical qualification by itself; repeated candidate/specification search increases winner-by-chance risk.

## H. Dataset provenance

Final dataset hash alone is insufficient. Qualification requires source identity, raw file hash, canonical row hash, parser version, chart identity, calendar range, row counts and integrity counts.

Raw source bytes and canonical evidence are separate identities.

## I. Exact timeframe identity

Source-data documentation distinguishes 60 and 61 clocks, export variants that should be deduped by hash, and uppercase `1M` as monthly rather than one-minute.

Current lowercasing can reinterpret `1M` as `1m`; snapped granularity can also collapse 3660 seconds toward 3600 seconds.

Broad model family and exact chart identity must be separate.

## J. Duplicate timestamp integrity

Trainer parsing sorts rows but does not fail closed on conflicting duplicate timestamps. This can manufacture zero-time nonzero returns and distort features, class balance and splits.

Identical complete-evidence duplicates may be audited/collapsed. Any relevant field conflict at the same timestamp hard-fails.

## K. Parser inconsistency

Trainer, feed and event paths use different timestamp logic. One canonical parser must handle seconds, milliseconds, microseconds, nanoseconds and supported ISO strings while preserving detected unit/timezone metadata.

## L. Model artifact identity

Current artifact naming is too coarse and audit gates can rely on expected file existence.

Correct semantic identity binds instrument/chart/dataset/features/labels/time/splits/model/calibration/code/dependency versions/seed/model hash.

Path existence is never qualification.

## M. Baseline contract

Qualification hierarchy: NULL -> LOGISTIC -> XGB.

Primary metric: logloss. Also report Brier, accuracy, class balance, calibration diagnostics and paired per-row loss differences.

Logistic and XGB must use identical qualified rows/features.

## N. Holdout and calibration

Final holdout trains nothing: no model, early stopping, calibration, threshold, feature selection or candidate selection.

Calibration comes from pre-holdout chronological predictions. Raw and calibrated results remain separate.

Isotonic additionally requires sample sufficiency. Alternative calibrators are separately counted experiments.

## O. XGB Slot-1

Slot-1 remains unimplemented/stubbed. Use frozen initial parameters before any search.

Admission requires XGB to beat logistic and null on untouched OOS logloss.

Validation is for early stopping. Exact versions, best iteration, dataset identity and model hash are recorded. Reloaded model must reproduce predictions.

## P. Economic qualification

Current emulator is useful for bar-level accounting but does not prove real bid/ask path, queue position, depth, market impact, partial liquidity or exchange/broker latency.

Freeze decision rules and stress commission/spread/slippage/latency/fill/intrabar-path/quantity assumptions.

No depth evidence means no capacity qualification.

## Q. Robustness

Required lanes include regime stability, parameter fragility, seed sensitivity, cross-asset transfer, OOD, risk-coverage, confidence inversion, calibration drift, corruption monotonicity, ablation, multiple-testing ledger and tail/failure clustering.

Uncertainty may only reduce/cap authority.

## R. External provider federation

Live provider smoke tests demonstrated why provider state must be typed.

Observed examples during this research cycle:
- StackerScan returned precious-metal spot observations.
- Bybit returned BTCUSDT exchange/perpetual observations.
- Twelve Data returned BTC/USD quote data.
- DataBlue/Google Finance returned another BTC reference observation.
- FMP supplied accessible market/macro/commodity data.
- Gold Bureau requests were blocked by environment/network policy.
- Massive crypto last-trade access was entitlement-gated.
- Scite retrieval later hit quota limits.
- Blockscout exposed supported EVM-chain state.
- Runway/Figma/Cheat Database are capabilities, not market-signal authorities.

Do not collapse auth, entitlement, rate limit, network failure, no observation, staleness or semantic mismatch into generic missing.

Instrument semantics must remain explicit: XAU spot != GC != MGC; BTC/USD spot != BTCUSDT perpetual != BTC futures; NQ != QQQ; mark != last != bid != ask.

## S. Schwab quote-snapshot finding

Schwab integration correctly forbids order writes and isolates failures per symbol.

The poller records local ingestion time rather than preserving vendor event time and writes one selected quote as `open=high=low=close` with cumulative `totalVolume` in a generic volume field.

This is a compatibility dump, not a genuine OHLC bar.

Quote snapshots need their own schema, explicit price kind, cumulative-volume semantics, and separate source-event/received/available times.

Current discovery roots do not automatically include the Schwab history directory; automatic trainer contamination was not established.

## T. Existing ICARUS controls worth preserving

Research/adaptation code already contains useful concepts: bounded trials, chronological windows, persistent holdout ledger, revealed-history watermark, no reuse of revealed history as fresh holdout, paired comparisons, stress-cost validation, reproducibility hashes, adaptation disabled by default, and no automatic execution authority.

Integrate with these controls rather than replacing them.
