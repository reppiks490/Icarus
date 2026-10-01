# Empirical Methodology References

This ledger captures the external methodology references used while designing the current ICARUS XGB/holdout integrity plan. These references support research methodology; they do not prove a trading edge.

## Probability calibration

1. Niculescu-Mizil, A., & Caruana, R. (2005). **Predicting Good Probabilities With Supervised Learning.** Proceedings of ICML. DOI: 10.1145/1102351.1102430
   - Relevant to post-hoc probability calibration, including Platt/isotonic methods.

2. Ding, Z., Han, X., & Liu, P. (2020). **Local Temperature Scaling for Probability Calibration.** arXiv:2008.05105. DOI: 10.48550/arxiv.2008.05105
   - Relevant to keeping calibration conceptually separate from model fitting/evaluation.

3. scikit-learn calibration documentation (current at research time)
   - Used to cross-check disjoint calibration semantics and the warning that isotonic calibration can overfit when calibration samples are small.

## Backtest/model-selection overfitting

4. Bailey, D. H., Borwein, J. M., & López de Prado, M. (2014). **Pseudo-Mathematics and Financial Charlatanism: The Effects of Backtest Overfitting on Out-of-Sample Performance.** Notices of the AMS. DOI: 10.1090/noti1105
   - Supports preserving honest OOS boundaries and avoiding repeated selection on the same evidence.

5. Bailey, D. H., Borwein, J. M., & Salehipour, A. (2015). **Online Tools for Demonstration of Backtest Overfitting.** SSRN. DOI: 10.2139/ssrn.2597421
   - Relevant to experiment-universe and repeated-testing risk.

## XGBoost behavior

6. XGBoost Python / sklearn-interface documentation (current at research time)
   - Used to verify that early stopping depends on an evaluation set and that best-iteration state can be used for subsequent inference.

## Methodology conclusions carried into ICARUS

- Validation used for early stopping is model-selection evidence, not terminal evidence.
- Raw terminal-holdout evaluation should occur before any calibration fitted on that terminal set.
- A calibrator fitted on terminal holdout is provisional until fresh forward validation.
- Repeated parameter/model trials must remain in the effective attempt universe.
- Provider/agent summaries do not create independent evidence origins.
- Stronger model complexity is not a promotion criterion; incremental OOS value is.
