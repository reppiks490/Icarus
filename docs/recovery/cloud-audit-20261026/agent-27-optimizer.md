# 27/50 — Portfolio optimizer audit

Read-only source review; no network or tests.

**Existing behavior:** `workspace_api.py:113–150` exposes status/performance/assets/inputs/trades, without allocation solving. `pyproject.toml:16–24` declares no CVXPY dependency. `icarus_futures/risk.py:76–135` deterministically vetoes individual intents; it does not optimize joint allocations.

**Concrete convex candidate:** For continuous target contracts x, current positions x₀, fixed valid positive marks p, point values v, and PSD covariance Σ, minimize xᵀΣx + λ‖x−x₀‖₁ (λ≥0). Impose each family’s |Σᵢ ratioᵢxᵢ|≤family_limit; each cluster’s Σᵢ pᵢvᵢ|xᵢ|≤cluster_limit; and total Σᵢ pᵢvᵢ|xᵢ|≤gross_limit. These reproduce the economic limits in `risk.py:122–134` and `contracts.py:56–72`. Add explicit margin and turnover budgets only with defined, validated inputs. Futures integer quantities require mixed-integer solving or separately checked rounding; continuous feasibility is insufficient.

**Gaps:** No covariance/objective/solver-status contract exists in these APIs. `risk.py:128` substitutes the candidate’s price for missing marks on other holdings, making exposure unreliable. `engine.py:73–75` copies filled positions without reserving outstanding order exposure; a future allocator needs commitments too.

Keep pause, stale-data, reconciliation, losses, blackout/session checks (`risk.py:91–114`) and final intent authorization (`engine.py:84–90`) authoritative. Preserve reduction behavior. Optimization cannot establish profitability or live authorization.
