# Model, Economics, and Robustness Contract

## Baseline hierarchy

NULL -> LOGISTIC -> XGB.

Primary predictive metric is logloss. XGB must beat logistic and null on untouched OOS evidence.

Use paired per-observation loss differences.

## Logistic

Keep deliberately simple and feed identical qualified rows/features to logistic and XGB. Any preprocessing is fit on training data only.

## XGB

Use current frozen parameters before any search. Validation controls early stopping. Final holdout never enters fitting, early stopping, calibration, threshold/feature/candidate selection.

Record exact dependency versions, best iteration, model hash and experiment identity. Reloaded model must reproduce predictions.

## Calibration

Fit from pre-holdout chronological predictions only. Retain raw and calibrated probabilities separately. Isotonic requires sample sufficiency. Alternatives are counted experiments.

## Artifact binding

Bind dataset manifest, chart/instrument identity, feature/label/temporal contracts, split, model config, calibration config, versions, seed, code commit and serialized hash.

Path existence is not qualification.

## Candidate

Contemporaneous agreement is descriptive only. Predictive testing requires candidate information fully available before execution decision. Candidate universe/lag/threshold/family freeze before validation/holdout.

## Economics

Freeze decision rule before final OOS economic evaluation. Stress commission, spread, slippage, latency, fills, path and quantity/capacity.

No depth evidence -> no capacity qualification.

## Robustness

After predictive/economic admission run regime, parameter, seed, transfer, OOD/risk-coverage, calibration drift, corruption monotonicity, ablation, trial-ledger and tail/failure-clustering tests.

Any critical failed gate returns authority zero.
