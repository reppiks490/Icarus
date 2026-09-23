# ICARUS ML handoff (CA, 2026-09-22)

## Where to resume

Repository: `https://github.com/reppiks490/Icarus.git`.
Branch: `codex/ml-d9d4db8`, based on `d9d4db8`. This is an isolated worktree
at `C:/Users/tripl/Icarus-ml-d9d4db8`; the running dashboard checkout at
`C:/Users/tripl/Icarus` was not changed. Read the latest native goal attachment
and `ASTRA_ORDER.md`, `ASTRA_DO_NOT.md`, `MODELS_GROK.md`, then this file.

This checkpoint is **research infrastructure**, not a profitable strategy or
live trading authorization. Pulse and emulator have no changes in this branch.
`execution_authorized` is false in model and audit outputs.

## Completed and checked

1. Installed isolated Python environment with `.[ml,dev]` and Windows
   `tzdata`. XGBoost 3.4.1 loaded and native booster save/reload checked.
2. Fetched six owner CSV archives from `reppiks490/multi-level-csv`; 177 CSVs
   were verified and extracted as **candidate** data. Older chart exports
   were inventoried separately. `run/data_inventory.json` records source
   archive/member/file SHA-256, rejected/ambiguous files, and deterministic
   selections. Raw CSVs remain in their owner repository and the local
   `history/unzipped` tree, rather than duplicating them in Git.
3. Identified 44 usable symbol/family cells of a possible 72 across NQ, ES,
   YM, GC, SI, PL, PA, BTCF, BTC. Banned MBT, SOL, ETH/ETHUSD were excluded.
   Unidentified Renko files, close-only tick files, invalid OHLC and missing
   families were recorded rather than silently relabeled.
4. Trained 44 genuine, per-cell native XGBoost primary models and scaled L2
   logistic baselines. The agreement slot uses causal expanding-window labels.
   The regime slot predicts whether the next family bar's absolute return
   exceeds the training median using current-bar features; this replaces an
   earlier tautological same-bar volatility classifier. RATE/FDI are absent
   from the current source exports. Holdout calibration was fit on an earlier
   holdout slice and
   evaluated later. The journal-loss slot is deferred until an actual
   decision-time feature/outcome journal exists. Native JSON and training
   summaries are in `run/trainers/` (explicitly staged for this branch).
5. Strict source parsing, as-of event/sensor features, purged chronological
   boundaries, model reload, source hashes and atomic writes are covered by
   focused tests. The full `tests_engine` suite passed after correcting two
   stale environment-dependent tests. The independent artifact replay command
   `python -m icarus_engine.trainers.verify --manifest run/data_inventory.json
   --models run/trainers --root .` reloaded all 44 native trees, reparsed the
   exact CSVs and reproduced split boundaries and primary holdout metrics:
   44 verified, 0 failed after the next-bar-magnitude regime retrain. Its
   report is `run/trainers/verification.json`. The full `tests_engine` suite
   passed 540 collected tests on 2026-09-23.
6. `icarus_engine.audit --require-xgb` now checks a fitted native model,
   current training code signature, event calendar, symbol/family/interval
   provenance and exact execution CSV hash. It reports `diagnostic` with
   `candidate_qualified=false`; the old same-bar concordance score does not
   issue trading or qualification claims. NQ 4-minute source versus AAPL
   produced 743 overlaps, 51.14% same-time sign agreement and 16 macro
   overlaps; none of those figures are an edge certificate.
7. The operator's pinned `tools/goal.py` and `tools/duration.py` at source
   commit `6e0da352` are copied into `icarus_engine/qualification/` with
   only a local import adaptation. `assess_trade_metrics` requires complete
   tune/hold metrics and a real clock interval. It reports only that supplied
   metrics meet thresholds; it cannot authenticate the underlying trade tape
   or qualify a live candidate. Nonclock chart durations remain unresolved.

The 44 raw next-family-bar sign holdout accuracies range 46.06% to 72.14%,
mean 52.51%. They are **not** strategy win rates. Search over many cells can
make the maximum look impressive; selection needs a fresh final holdout.
The verifier now reports positive training examples per event flag. For
example, NQ clock-minutes has 40 seeded FOMC rows but zero CPI, payroll or
earnings rows. A zero-example flag has not been learned, and the FOMC seed is
not an authenticated released-time event history. No event-based trading
claim follows from these artifacts.

The six newest candidate archives contain 177 CSV files but only 89 unique
content hashes and 15 distinct instrument names. The read-only catalog command
`python -m icarus_engine.audit.candidate_catalog --archives
history/unzipped/_repo --flat history/unzipped/candidates --out
run/candidates/catalog.json` checks every flat file against its archive
member byte-for-byte, reports chart/time metadata as unverified, and marks
all entries unqualified. On 2026-09-23 it found 177/177 matching members,
no missing flat filenames and no same-name content collision. Its committed
report is `run/candidates/catalog.json`. File count is not candidate count,
and stock context exports are not futures execution tapes.

## Reproduce or audit

Install in a clean Python environment with `python -m pip install -e ".[ml,dev]"`.
Regenerate owner data with `python -m icarus_engine.unzip_batches --fetch`,
then `python -m icarus_engine.trainers.catalog --src history/unzipped/_repo
--plant . --out run/data_inventory.json`. Fit with
`python -m icarus_engine.trainers --manifest run/data_inventory.json
--model xgb --root . --out run/trainers`.
The catalog paths are local absolute paths; regenerate the inventory after
moving the checkout. Artifacts are resumable only when source hash, code
signature, event hash, rounds and native reload all match.

Run `python -m pytest tests_engine -q`. Audit one source with
`python -m icarus_engine.audit --exec <exact-trained-source.csv>
--cand <candidate.csv> --future NQ --asset AAPL --require-xgb --root .`.
Use a matching `{SYM}_clock_minutes_xgb.json` or `--xgb` for another family.
The gate blocks a different execution CSV until that exact source is modeled.
The verifier needs the raw owner archives to be available locally; they are
not bundled with the model files in this branch.

## Work still required for the owner goal

- Review the 44 artifacts independently for causal availability, source
  identity, early stopping, OOF agreement training, calibration isolation,
  robustness and any false performance inference. A separate review agent
  was interrupted by a usage limit; it issued **no approval**.
- Resolve ambiguous Renko chart identity from owner metadata. Inventory
  additional distinct source cells; do not claim all possible input
  combinations have been tested. Build a reproducible, budgeted search over
  individual/pair/full configuration interactions with a frozen final test
  window and multiplicity controls. Replaying Pulse is required to measure
  trade outcomes; the bar-sign models alone cannot qualify candidates.
- Implement the **operator's** trade-level acceptance rules from
  `docs/OPUS_CANDIDATE_RULES.md` and the pinned source commit. Require complete
  tune/hold metrics. Expose `insufficient_evidence`, failed, qualified and
  distinctly starred exceptional results only after the actual thresholds
  have been met. Do not invent lower thresholds to fill a candidate list.
- Add released-time event feeds and genuinely as-of macro/stock sensors with
  licensing and revision provenance. Current trained artifacts mostly have
  seeded/date-only event flags; optional sensor support is an API, not an
  automatically loaded market data set. No order-flow, depth or named
  institutional holdings feed has been authenticated or integrated.
- Exchange product codes and contract sizes are recorded with primary sources
  in `docs/MICRO_CONTRACTS_20260922.md`. Add each available micro instrument as
  its **own** symbol, exchange spec,
  feed and trained data with a distinct paper ledger. The owner explicitly
  bans MBT despite the general micro request; do not register/train/trade it.
  Do not transform parent futures fills into micro performance.
- Independent end-to-end paper replay/parity, fill costs, contract rolls,
  calendar and feed latency validation remain necessary before any execution
  proposal. The dashboard/broker are out of scope for this checkpoint.
- The owner's separate private manual-action register is
  `https://github.com/reppiks490/icarus-owner-actions`. It lists the exact
  TradingView parity exports, exchange-data decisions, broker/prop checks,
  distinct micro tapes and optional contextual asset universe. Raw licensed
  CSVs and secrets are excluded from that repository.

## Signed handoff to Opus

**CA / Codex Astra:** I hand off live AI x ML candidate orchestration and
unstructured-context design to Opus, using the 44 immutable model profiles
only after review. Specify per-asset/timeframe candidates, causal decision
timestamps, stale-data handling, loss-brain evidence with real journal labels,
flat-position swap boundaries, rollback, bounded risk, and paper-only
authorization. The orchestrator must never self-promote a candidate based on
the current diagnostic score or treat stocks as futures execution data.
Preserve the owner's qualifications and separate future holdout. Integrate
micros except MBT only when distinct verified tapes and specs exist. Please
record exact commit and tests for any implementation and challenge this
checkpoint's assumptions before adopting its outputs.

This handoff is intentionally candid about unfinished requirements. Continuing
work should produce additional reviewed commits; it must not silently switch
the running strategy or place broker orders.
