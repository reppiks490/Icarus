# Current State — 2026-09-24

## Repository baseline inspected

Current inspected head before this handoff branch:

`007e70189945b8e112904cf92b2b1a12e43792d6`

No newer repository commit was observed during the final audit cycle.

## Design state

| Layer | Contract | Real-data proof |
|---|---|---|
| SOURCE | frozen | partial provider smoke tests only |
| DATA | frozen | pending implementation/run |
| TIME | frozen | pending implementation/run |
| BASELINE | frozen | existing logistic insufficient for final qualification |
| XGB | frozen contract | implementation missing / stub |
| ECONOMICS | frozen | pending |
| ROBUSTNESS | frozen | pending |

## Highest-priority P0 blockers

1. Canonical timestamp semantics differ across trainer/feed/event code.
2. `1M` monthly can collapse to `1m` minute semantics.
3. 60m and 61m exact dataset identities can collapse through snapped granularity.
4. Duplicate timestamp conflicts are not fail-closed in trainer parsing.
5. Completed-bar features can be associated with bar-open timestamps.
6. Event windows can expose future events.
7. Train/valid/holdout label resolution can cross split boundaries.
8. Candidate audit currently measures same-interval agreement rather than strict predictive lead.
9. Candidate quality metrics are selected on full supplied history.
10. Model artifact identity is too coarse and audit gates can rely on file existence rather than semantic identity.
11. Schwab quote snapshots lose vendor event time and are encoded as synthetic OHLC compatibility rows.
12. Provider failures (auth, entitlement, rate limit, network) are not yet unified into a typed source-state contract.

## Important corrections

- ZIP basename-collision code is structurally unsafe, but the source-data repo documented the six current candidate ZIPs as 177 CSVs with 0 filename overlap. Collision is a defensive weakness, not an observed failure in those six packs.
- `csv_access.py` can rediscover nested physical paths through overlapping recursive roots; downstream double-processing was not proven.
- Schwab quote CSVs are not automatically included in current `csv_access.py` search roots, so there is no proven automatic Schwab-to-trainer contamination path.
- Slot-1 XGB remains unimplemented; no XGB empirical performance is claimed.

## Immediate next action

Implement SOURCE+DATA kernel with tests first. Do not move to XGB before SOURCE/DATA/TIME pass.
