# ICARUS Current State — 2026-10-02

**Snapshot verified against:** `main@e84385f287ce0d6e1ea6faddc4aef882c739629c`  
**Review when:** main changes the learning, qualification, runtime journal, or execution-authority contracts.

## Authority boundary

- `execution_authorized=false`
- `production_decision_authorized=false`
- automatic production promotion from the learning plane: **off**

Research and shadow systems may learn, calibrate, rank evidence, and retire
degraded models. They do not independently authorize orders.

## Continuous learning

The Continuous Learning Fabric is installed and starts as a research background
service from its persisted/default configuration.

Current capabilities include:

- durable prediction/outcome ledger
- maturity enforcement and immutable outcomes
- historical CSV cataloging by hash
- manifest-aware data provenance
- protected OHLC replay/training
- TradingView trade-list experience import
- fail-closed manifest linkage from trade lists to unique strategy-report artifacts
- separate historical artifact-configuration P&L scorecards (never runtime strategy fingerprints)
- native SIBYL / Ψ / Performance Proof / Source Reliability / Commissioning harvest
- APEX empirical credibility feedback
- closure-time strategy provenance for realized live-sim trades
- configuration-specific P&L/expectancy/drawdown scorecards
- chronological isotonic shadow recalibration
- predicted-label and exact-source-revision isolation
- overlapping-window purge before calibration and drift measurement
- stable refresh batching
- OOS calibrator drift retirement

Canonical architecture: [../CONTINUOUS_LEARNING.md](../CONTINUOUS_LEARNING.md).

## Historical data

Runtime historical data is intentionally not stored in Git. The learner scans:

- `history/`
- `history/drop/`
- `research/imports/`

This allows previously exported multi-year CSVs to continue contributing to
replay and realized-experience analysis when those files are present locally.
Where the intake manifest uniquely pairs a trade-list CSV with a
`strategy_report_xlsx` artifact, the historical trades also inherit the
report-declared chart type, timeframe, and execution assumptions under a
separate manifest-linked artifact fingerprint. Ambiguous pairings remain
unscoped.

## Empirical research status

A result is not promoted merely because it exists or because a backtest is
profitable. Current research doctrine remains:

`observation != estimator != predictive relationship != incremental alpha != executable edge`

Important remaining research risks include:

- multiple-testing and selection bias
- nonstationarity/regime change
- provider/source degradation
- temporal leakage
- evidence redundancy
- proxy-only data paths
- insufficient independent OOS samples

Overlap-aware calibration and drift retirement reduce two forms of false
confidence; they do not eliminate these broader risks.

## Runtime integration

The learning plane is wired through:

- `ResearchWorkspace` lifecycle
- engine HTTP API/admin routes
- MCP research tools
- Learning Fabric dashboard panel
- APEX credibility feedback
- persistent SQLite/WAL research state

The service is non-blocking at engine startup.

## Resume instruction

1. Preserve exact source/data/code provenance for all new forecasts and outcomes.
2. Prefer independent non-overlapping samples over raw observation count.
3. Keep historical and live outcomes in the same evidence ledger but preserve
   their source/configuration scopes; never treat a manifest-linked artifact
   fingerprint as a closure-time runtime strategy fingerprint.
4. Retire or withhold degraded calibrators instead of forcing consensus.
5. Keep execution and production authority separate from research confidence.
6. Re-verify this page whenever learning or authority contracts change.
