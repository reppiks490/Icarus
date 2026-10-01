# Research Governance

## Objective

Maximize the probability that a discovered effect survives contact with unseen data, realistic costs, and live execution.

## Experiment attempt ledger

Every search attempt must be append-only and include:

- attempt ID
- experiment family ID
- hypothesis ID
- code commit
- dataset fingerprint
- feature/config fingerprint
- search-space definition
- train/validation windows
- holdout status
- random seed
- cost/slippage assumptions
- metrics
- selection decision
- rejection reason
- operator/agent identity
- timestamp

Failed experiments are first-class evidence.

## Multiple-testing controls

Priority additions:

- Deflated Sharpe Ratio (DSR)
- Probability of Backtest Overfitting (PBO)
- Combinatorially Symmetric Cross-Validation (CSCV)
- bootstrap confidence intervals
- family-level attempt counts
- parameter-surface stability
- negative controls / placebo signals

No metric should be presented without the search context that produced it.

## Holdout policy

- Training and validation can iterate.
- Final holdout must remain untouched until a preregistered candidate is frozen.
- Once consumed, the result and reason are recorded.
- Reusing the same holdout for repeated model selection converts it into validation data and requires a new final holdout.

## Mechanism + falsification

Before adding a candidate to a voting stack, document:

1. mechanism
2. minimum required data
3. expected sign
4. expected horizon
5. expected failure regime
6. strongest alternative explanation
7. test that would falsify it
8. incremental out-of-sample contribution versus existing features

## Promotion ladder

```text
IDEA
-> PROXY_RESEARCH
-> DATA_VALIDATED
-> OOS_VALIDATED
-> COST_STRESSED
-> SHADOW
-> PAPER
-> SMALL_LIVE
-> VERIFIED_FOR_INTEGRATION
```

A candidate cannot skip states merely because its backtest metric is large.
