# ICARUS Continuous Learning Fabric

**Scope:** research/shadow learning only.  
**Last verified:** 2026-10-02 against `main@e84385f287ce0d6e1ea6faddc4aef882c739629c`.  
**Review when:** `icarus_engine/learning_fabric.py`, `research_service.py`, the runtime trade journal schema, or the learning HTTP/MCP/UI surfaces change.

## Purpose

ICARUS no longer treats historical replay, model forecasts, observed outcomes, and realized trade results as separate research silos. The Continuous Learning Fabric joins them into one durable empirical loop:

`observation -> forecast -> maturity -> outcome -> calibration -> credibility -> drift check -> refresh/retirement`

The fabric measures and learns in the research plane. It does **not** authorize trades, rewrite production decisions, or promote models into execution.

Non-negotiable authority flags remain:

- `execution_authorized=false`
- `production_decision_authorized=false`
- automatic production promotion: **off**

## Runtime lifecycle

`ResearchWorkspace.start_background()` starts the learning service from its persisted/default configuration. The default cadence is:

- learning cycle: 60 seconds
- history scan: every 3,600 seconds
- historical backfills per cycle: 1
- default automatic trainer slot: `logit`

The service is daemonized/non-blocking; engine startup does not wait for a historical training run.

Persistent state lives in `research/learning.sqlite3` using SQLite WAL mode.

## Historical data lanes

The default scan roots are:

- `history/`
- `history/drop/`
- `research/imports/`

Raw historical CSVs are intentionally excluded from Git by `.gitignore`. They are runtime research data, not repository source.

The learner catalogs files by content hash and records coverage/provenance. It recognizes:

- OHLC/bar data suitable for protected replay/trainers
- TradingView Strategy Tester trade-list CSVs
- `EXPORT_INTAKE_MANIFEST.csv` metadata, including symbol, timeframe, chart type, row count, coverage window, and supplied SHA-256

Duplicate files are deduplicated by hash rather than filename.

### Historical replay

OHLC datasets run through the existing protected trainer stack, preserving its existing controls:

- purged/chronological walk-forward behavior
- protected holdouts
- isotonic calibration
- deterministic replay
- no automatic production promotion

TradingView trade lists are imported into the realized-experience ledger instead of being treated as forecast calibration samples.

## Prediction and outcome ledger

A prediction record is immutable and includes, at minimum:

- producer
- asset
- target type
- predicted label/value
- raw probability or class distribution
- event/emission time
- maturity time/horizon
- regime
- exact source Git commit
- evidence identifiers
- metadata/provenance

An outcome cannot settle before its prediction matures. Once settled, the outcome is immutable.

The fabric tracks empirical metrics by scoped producer/asset/regime/horizon/target dimensions, including:

- settled sample count
- hit rate
- Wilson interval
- mean Brier score
- calibration gap
- mean absolute error where applicable

## Native empirical feeds

The learner currently federates real empirical information from these ICARUS subsystems:

- **SIBYL** — native forecasts and matured outcomes
- **Ψ / Market Possibility** — non-overlapping scenario-share calibration against observed endpoints
- **Performance Proof** — immutable forecast/outcome pairs, incrementally harvested with a durable cursor
- **Source Reliability** — observed source/stream reliability context
- **Chronofold Commissioning** — settled prediction metrics and promotion-gate state
- **PARALLAX** — decision/outcome/regret summary metrics
- **DREAMSTATE** — stage/family research state
- **PANTHEON/AETHER** — claim/ecology state
- **APEX Ω** — receives empirical model-credibility feedback
- **runtime trade journal** — fully closed live-sim trade experience

A source without a defensible forecast/outcome contract is not silently converted into one.

## Ψ empirical calibration

Ψ scenario shares remain explicitly labeled **uncalibrated scenario shares**. The learner:

1. commits the forecast before the outcome,
2. binds it to exact chart cadence and horizon,
3. refuses capture when the exact code revision is not clean/known,
4. prevents overlapping unresolved Ψ forecasts from creating pseudoreplication,
5. settles only after the committed maturity using observed price,
6. measures empirical calibration without rewriting Ψ's production logic.

## Shadow recalibration

For eligible probabilistic forecasts, ICARUS can build research-only isotonic calibrators.

Calibrators are scoped by:

- producer
- asset
- regime
- horizon
- target
- predicted label
- exact source Git commit

They are trained chronologically and validated on a later holdout. A calibrator can be attached only to forecasts emitted **after** the full train+validation evidence cutoff.

The raw forecast probability is never rewritten. The calibrated probability is stored in a separate shadow ledger.

### Overlap protection

Overlapping forecast windows are purged before calibration fitting and drift evaluation. The ledger preserves:

- raw sample count
- effective independent sample count
- number of overlapping samples purged

This prevents many correlated forecasts over the same target interval from masquerading as independent evidence.

### Proper-score diagnostics

Exact label/revision scorecards compute reliability diagnostics only from the effective non-overlapping classified sample: adaptive equal-count Expected Calibration Error (ECE), maximum calibration error, mean logarithmic loss, climatology Brier score, and Brier skill score. The adaptive bin count is `ceil(sqrt(n))`, capped at 10, so small samples remain auditable without pretending sparse fixed bins are precise. These metrics are diagnostic evidence only; they do not rewrite forecast probabilities or authorize execution. A zero mean calibration gap is therefore not treated as proof of calibration when confidence errors cancel across probability levels.
### Refresh batching

A validated calibrator is held stable until a minimum new settled-sample batch accumulates. This creates a genuine out-of-sample period instead of refitting after every outcome.

### Drift retirement

Later shadow outcomes compare calibrated Brier score with the original raw Brier score. If the calibrator becomes materially worse than raw confidence, that revision is marked `DRIFT_RETIRED`.

Retirement:

- stops that revision from attaching to future forecasts,
- preserves all historical forecasts/outcomes/calibration evidence,
- records the retirement reason and evidence,
- does not alter execution authority,
- allows a later revision to earn validation again after sufficient new evidence.

## Realized trade experience

Fully closed runtime trades are harvested from the durable journal, not just volatile in-memory runner state.

At trade closure, the runtime records a strategy provenance receipt containing the exact configuration context and a deterministic strategy fingerprint. Configuration-scoped experience can therefore separate P&L for materially different setups instead of pooling them under a generic asset label.

Realized experience has three explicit, source-bound provenance classes:

- `RUNTIME_CLOSURE_CONFIG` — only `runtime_live_sim` records with `CLOSURE_TIME_CONFIG` quality and an exact 64-hex strategy fingerprint. This is the only class that may appear in exact runtime-configuration scorecards.
- `HISTORICAL_ARTIFACT_CONFIG` — only historical trade-list or Strategy Tester XLSX records with a verified manifest/direct strategy-report link, an exact artifact-configuration fingerprint, and the report SHA-256. This class describes historical artifact identity; it is not runtime state.
  - If the intake manifest explicitly declares `session_mode` (accepted values normalize to `rth`, `eth`, or `all`), that session identity becomes part of the historical artifact fingerprint and scorecard. Missing or unrecognized session labels remain unknown; ICARUS does **not** infer RTH/ETH from timestamps, date ranges, filenames, or chart cadence.
- `UNSCOPED` — all other realized experience, including ambiguous historical linkage and runtime-memory fallback that lacks a durable closure receipt.

The class is derived from source plus evidence on write; a caller-supplied label cannot promote one source class into another. Legacy persisted rows are classified fail-closed when read, without rewriting their immutable original semantic payload. **Never use `HISTORICAL_ARTIFACT_CONFIG` as proof of `RUNTIME_CLOSURE_CONFIG`.** A future source or provenance mechanism must be explicitly admitted into the taxonomy rather than inheriting authority by naming convention.

Configuration experience includes:

- count / win rate
- net and average P&L
- average win / average loss
- payoff ratio
- profit factor
- max cumulative drawdown

Legacy/unscoped experience remains visible but is excluded from exact-configuration scorecards. These classes remain descriptive research provenance only: they do not change `execution_authorized=false`, do not authorize automatic production promotion, and do not alter historical outcomes.

**Staleness trigger:** revisit this section whenever a new realized-experience source, strategy-receipt format, or historical linkage mechanism is added; the source-bound class allowlists and fail-closed tests must change together.

## API, MCP, and UI surfaces

Authenticated HTTP read surfaces:

- `GET /api/learning`
- `GET /api/learning/health`
- `GET /api/learning/experience`
- `GET /api/learning/scorecards`
- `GET /api/learning/datasets`

Authenticated research/admin mutations:

- `POST /admin/learning/config`
- `POST /admin/learning/tick`
- `POST /admin/learning/prediction`
- `POST /admin/learning/outcome`
- `POST /admin/learning/scan`
- `POST /admin/learning/backfill`

Equivalent research-oriented MCP tools expose the same bounded operations.

The Learning Fabric dashboard panel surfaces dataset coverage, empirical scorecards, replay/training state, live maturity, realized trade experience, and exact-configuration experience.

## When not to trust a learned result

Do **not** treat a result as strong evidence merely because the learner produced a score.

Downgrade or withhold confidence when:

- sample counts are early/small,
- forecasts overlap heavily,
- source revision differs,
- label/regime/horizon scope differs,
- evidence source quality degrades,
- the market regime changes,
- a calibrator is rejected or drift-retired,
- exact event-time provenance is unavailable,
- historical data is proxy-only or missing required fields.

A mature ICARUS result is one that survives these gates, not one that merely has more observations.

## Operational consequence

This subsystem changes research maturation, not order execution. It can consume years of local history quickly and continue accumulating live outcomes over time, but the output remains shadow/research evidence until separate qualification and authorization gates explicitly promote something.
