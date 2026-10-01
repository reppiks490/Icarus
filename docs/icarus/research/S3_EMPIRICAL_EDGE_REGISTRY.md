# ICARUS S3 Empirical Edge Registry

Progressive registry. Do not restart this table between loops. Failed, blocked,
conflicted, and rejected hypotheses remain part of the research history.

## Global state
- Maximum S3 maturity: `EMPIRICALLY_SUPPORTED`
- Current maximum achieved by any ICARUS edge in this registry: below that threshold
- `MULTIPLE_TESTING_STATUS=UNCONTROLLED`
- `execution_authorized=false`

| Claim / attempt | Family | Current status | Data | Estimator | Key result |
|---|---|---|---|---|---|
| `EDGE-TSMOM-001 / S3-TSMOM-001` | trend/momentum | HYPOTHESIS | PARTIAL | PARTIAL | External medium-horizon TSMOM evidence does not validate ICARUS short-horizon transforms. |
| `EDGE-OFI-001 / S3-OFI-001` | order flow / queue | HYPOTHESIS | DATA_BLOCKED | external PARTIAL; ICARUS proxy UNKNOWN | True OFI/queue research requires quote/order-event data; bar proxies do not qualify. |
| `EDGE-CARRY-001 / S3-CARRY-001` | carry / term structure | HYPOTHESIS | GC now PARTIAL; generic market coverage mixed | PARTIAL | Explicit maturity reconstruction is feasible for GC; continuous/front contracts remain insufficient. |
| `S3-HEDGE-001` | hedging pressure | REJECTED simplification | — | — | Commercial hedging pressure alone does not authorize return direction. |
| `EDGE-VRP-001 / S3-VRP-001` | variance risk premium | HYPOTHESIS | DATA_BLOCKED | external PARTIAL; proxy UNKNOWN | ATR/realized volatility alone is not VRP; options/implied variance is required. |
| `S3-VRP-PROXY-001` | VRP proxy | REJECTED | — | — | ATR/realized volatility cannot be labeled VRP. |
| `EDGE-TOD-001 / S3-TOD-001` | intraday/session | HYPOTHESIS | PARTIAL | PARTIAL | Time-of-day effects exist externally but are market/horizon dependent and can decay. |
| `S3-FOMC-DRIFT-001` | macro event | CONFLICTED/DECAYED | PARTIAL | PARTIAL | Historical pre-FOMC drift evidence does not justify assuming persistence. |
| `EDGE-XLAG-001 / S3-XLAG-001` | lead-lag / cross-market | HYPOTHESIS | DATA_BLOCKED | external PARTIAL; ICARUS proxy UNKNOWN | Cross-market transmission exists, but permanent leader/follower assumptions are rejected. |
| `S3-FIXEDLEADER-001` | lead-lag | REJECTED | — | — | No permanent fixed leader/follower authority. |
| `S3-CORRVOTE-001` | correlation | REJECTED | — | — | Contemporaneous correlation is not independent predictive evidence. |
| `EDGE-REV-001 / S3-REV-001` | short-horizon reversal | HYPOTHESIS | PARTIAL / DATA_BLOCKED by mechanism | PARTIAL | Generic "prices mean revert" fades are rejected; mechanism/horizon must be identified. |
| `S3-REV-GENERIC-001` | reversal | REJECTED | — | — | Generic fading of extremes is not a valid edge specification. |
| `EDGE-BASISREV-001 / S3-BASISREV-001` | basis reversal | OBSERVED/HYPOTHESIS | DATA_BLOCKED without synchronized maturities | PARTIAL | Adjacent-maturity negative autocorrelation evidence is interesting but not independently replicated for ICARUS. |
| `EDGE-LP-001 / S3-LP-001` | liquidity provision | HYPOTHESIS | DATA_BLOCKED | external PARTIAL; bar proxy UNKNOWN | Queue priority/adverse selection/inventory are real; bar-only "spread capture" is not qualified. |
| `S3-SPREADCAPTURE-001` | market making | REJECTED | — | — | Resting at bid/ask does not imply earned spread. |
| `EDGE-REGIME-001 / S3-REGIME-001` | regime conditioning | HYPOTHESIS | PARTIAL | PARTIAL | Regime state may aid risk/description; it is not automatically directional alpha. |
| `EDGE-REGIME-RISK-001` | regime/risk | HYPOTHESIS | PARTIAL | PARTIAL | Risk/volatility conditioning can be valuable even if directional alpha fails. |
| `S3-REGIME-LABEL-001` | regime confluence | REJECTED | — | — | Multiple related regime indicators do not become independent confirmation. |
| `S3-REGIME-SMOOTH-001` | temporal integrity | REJECTED | — | — | Full-sample/smoothed contemporaneous regime labels are not allowed. |
| `EDGE-CORR-001` | conditional dependence | HYPOTHESIS | SUFFICIENT for descriptive DXY association; PARTIAL/DATA_BLOCKED for predictive lead | VALIDATED_FOR_ASSOCIATION_ONLY | Correlation can describe risk/state; it is not directional authority. |
| `S3-CORR-ALPHA-001` | correlation alpha | REJECTED | — | — | Correlation sign cannot directly authorize BUY/SELL. |
| `S3-CORR-INDEP-001` | confluence independence | REJECTED absent OOS proof | — | — | Correlated confirmations cannot each receive full independent weight. |
| `S3-DISP-001` | dispersion | NO_CHANGE_JUSTIFIED | UNKNOWN/PARTIAL | UNKNOWN | Bounded pass found insufficient evidence for standalone directional dispersion alpha. |
| `S3-XGB5-LINEAGE-001` | composite lineage | VERIFIED_DERIVED_COMPOSITE | code-verified | HEURISTIC_ONLY as model | Pulse XGBoost5 is hand-built from existing indicators, not trained XGBoost. |
| `EDGE-MACRO-001` | macro/event | HYPOTHESIS | PARTIAL | PARTIAL | Event-conditioned futures behavior is plausible; current event semantics require hardening. |
| `S3-MACRO-SCHEDULE-DIR-001` | event direction | REJECTED | — | — | Scheduled macro event presence does not imply trade direction. |
| `S3-MACRO-SURPRISE-001` | event surprise | HYPOTHESIS | requires point-in-time consensus/actual | PARTIAL | Surprise can only exist after release availability. |
| `S3-MACRO-REDUNDANCY-001` | event feature lineage | VERIFIED redundancy | SUFFICIENT for code claim | — | Current trainer's `fomc` and `any_macro` collapse to the same information source. |
| `S3-CARRY-DATA-002` | carry data | OBSERVED | PARTIAL | — | Explicit GC maturity reconstruction is possible through connected sources. |
| `S3-CARRY-CONTINUOUS-001` | carry identification | REJECTED | — | — | `GC=F` / continuous front series alone cannot identify term-structure carry. |
| `EDGE-BTC-FUNDING-001` | crypto funding | HYPOTHESIS | historical DATA_BLOCKED/PARTIAL | UNKNOWN | Current funding is observable; adequate point-in-time historical funding was not established. |

## Combination rule
The effective weight of evidence must reflect both incremental value and independence:

```
W_effective = W_raw * I_incremental * D_independence
```

Both incremental-value and independence terms fail closed when unverified.

## Architecture boundary
Research progresses through:

```
Association -> Risk State -> Predictive Lead -> Incremental Alpha -> Executable Edge
```

Movement right requires additional evidence. No layer inherits authority automatically.
