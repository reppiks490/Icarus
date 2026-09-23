# ML execution at d9d4db8

Owner objective: follow ASTRA_ORDER.md at d9d4db8: unzip the six batches,
install the ML extra, build MODELS_GROK.md per traded symbol and family,
then and only then run the candidate audit with --require-xgb.

## Invariants

- Pulse and emulator remain unchanged. No runtime/broker restart or activation.
- NQ ES YM GC SI PL PA BTCF BTC only. No MBT, SOL, ETH, or ETHUSD training.
- Candidate stocks are sensors, never the futures execution tape.
- Preserve per-file order, index, timeframe, chart type, source and content hash.
- No concatenation of unrelated timeframes, chart families or symbols.
- No invented ticks, spreads, institutional identities, book depth or events.
- Execution authorization is false in every model and audit artifact.
- No inference of Renko versus clock bars from ambiguous numeric filenames.

## Ordered work

1. Acquire and verify six archives and extracted files; inventory other owner
   exports to locate execution data. Keep the running plant untouched.
2. Make feature/label construction causal, validate schema/index, and preserve
   baseline logit weights. Split chronologically with next-label boundary purge.
3. Implement and verify genuine XGBoost primary, agreement model, boosted regime,
   separate holdout calibration/evaluation and conditional journal-loss model.
4. Fit eligible symbol/family cells on identified datasets. Save reloadable
   models, feature schema, source hashes, parameters, split boundaries and metrics.
   Record missing/ambiguous/insufficient cells rather than inventing data.
5. Validate genuine model content, identity and provenance before candidate audit.
   Keep descriptive correlation distinct from predictive/strategy profitability.
6. Independently review code and evidence, run tests, and report remaining gaps.

## Initial evidence

- Isolated worktree: C:/Users/tripl/Icarus-ml-d9d4db8.
- Source commit: d9d4db8. Branch: codex/ml-d9d4db8.
- Six-archive command completed: 30 + 30 + 30 + 30 + 29 + 28 CSVs.
- No extraction into HistoryHub; all six batches classified as candidates.
- Separate Python venv, ML and test extras installation requested.

## Interpretation requiring explicit reporting

The spec asks for calibration on holdout only. Reserve the first part of that
holdout for calibration and the later part for untouched calibrated evaluation;
never describe calibration-fit metrics as independent out-of-sample evidence.
Raw primary holdout metrics are measured before calibration. Failure training
requires actual journal outcomes and decision-time features; a table of losses
alone cannot train or evaluate a loss classifier.

Prepared by Codex/Astra, 2026-09-22. This is an execution ledger, not certification
of trading performance and not permission to activate a broker.
