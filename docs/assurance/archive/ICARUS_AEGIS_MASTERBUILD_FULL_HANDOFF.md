# ICARUS AEGIS Ω — Full Masterbuild Handoff

## Status

This file consolidates the work produced in this chat around ICARUS / AEGIS Ω.

This chat produced:
- evidence-led research synthesis
- corrections to earlier overclaims
- failure-mode analysis
- advanced AEGIS Ω architecture
- kernel implementation plan
- masterbuild sequencing
- red-team sequencing
- Codex handoff instructions

**Important:** this chat did not modify the Icarus repository or produce a verified integrated build. Any earlier conversational statement implying completed code or a passing test suite should not be treated as implementation evidence. The next Codex/build session should implement and verify from this document.

---

# 1. Research Synthesis

There is no single universally dominant algorithmic method across all assets and timeframes. The strongest recurring architecture is a layered system combining structural-return signals, short-horizon microstructure/order-flow signals, volatility-aware sizing, regime/change-point awareness, execution-cost modeling, and aggressive anti-overfitting validation.

A durable architecture is:

\[
\text{Market State}
\rightarrow
\text{Structural Edge}
\rightarrow
\text{Entry/Path Forecast}
\rightarrow
\text{Risk/Volatility Normalization}
\rightarrow
\text{Execution}
\rightarrow
\text{Statistical Validation}
\]

## Strong recurring mechanisms

- time-series momentum / trend following
- volatility normalization / targeting
- order-flow imbalance / queue imbalance / microprice
- carry / term structure / basis
- cross-sectional momentum / relative strength
- factor-neutral residual mean reversion
- regime / changepoint detection
- nonlinear ML combination
- Kalman / state-space estimation
- Hawkes / event-intensity modeling
- explicit transaction-cost and execution modeling

## Major corrections from the initial sweep

### Trend / TSM

The claim that time-series momentum is universally strong was too categorical. A more defensible conclusion is:
- diversified trend-following as a strategy family has compelling long-run evidence;
- the stronger claim that individual assets possess a stable universal 1–12 month TSM forecasting coefficient is disputed;
- trend should be treated as a robust family of directional-persistence estimators, not a universal law.

### Volatility targeting

Volatility targeting is not universally beneficial. Benefits can concentrate in some strategy families, especially momentum. Turnover, execution costs, and rebalancing frequency can erase apparent improvements. Volatility scaling should be bounded, smoothed, and explicitly cost-aware.

### Microstructure

At short horizons, L2/L3 state, OFI, queue imbalance, microprice, signed trades, replenishment/depletion, spread and depth can dominate candle-based indicators. But:

\[
\text{predictability} \neq \text{tradable alpha}
\]

because latency, queue position, spread, adverse selection and competition can consume the edge.

### Hawkes

Use Hawkes processes for event clustering, endogenous excitation, trade/cancel cascades, liquidity stress and exhaustion. Do not treat Hawkes intensity as directional alpha by itself.

### Kalman

Kalman filtering is infrastructure for latent-state estimation: fair value, dynamic beta, hedge ratio, trend, velocity and volatility state. It is not inherently alpha.

### Mean reversion

Prefer residual mean reversion:

\[
r_i = \beta F + \epsilon_i
\]

and model \(\epsilon_i\), rather than naive price-minus-moving-average logic. Relationship stability and structural-break detection are mandatory.

### Carry / term structure

Carry remains one of the strongest structural cross-asset components. Futures should explicitly model curve state: basis, backwardation/contango, roll yield and front/back relationships.

### Machine learning

The strongest use cases are nonlinear interactions, weighting, regime probabilities, conditional thresholds, meta-labeling, calibration and ensemble combination. Complexity must prove incremental out-of-sample information net of cost.

Recommended escalation:

\[
\text{Linear baseline}
\rightarrow
\text{Boosted trees}
\rightarrow
\text{small neural model}
\rightarrow
\text{transformer/state-space model}
\]

### Execution

Always evaluate:

\[
NetAlpha = GrossAlpha - Spread - Slippage - Fees - Impact - AdverseSelection
\]

Execution should have veto authority over trades whose expected edge does not survive realistic frictions.

---

# 2. Timeframe-Specific Information Hierarchy

| Horizon | Primary information |
|---|---|
| µs–ms | queue position, latency, book events |
| 10 ms–1 s | OFI, queue imbalance, microprice, event intensity |
| 1–30 s | depth dynamics, signed trades, microstructure |
| 30 s–5 m | order flow + structural price state |
| 5–60 m | intraday trend, regime, relative strength, volatility/liquidity |
| 1 h–1 d | trend + cross-market state + carry/reversion |
| days–weeks | trend + carry + cross-sectional factors |
| weeks–months | carry + trend + relative value + macro/fundamental factors |

---

# 3. Global Ticker-Tape Architecture

Do not treat every ticker as a flat vote. Build a dynamic influence graph:

\[
G_t = (V,E_t)
\]

Each edge:

\[
E_{ij,t} = [lag, sign, strength, stability, regime, decay, redundancy, confidence]
\]

Estimate:

\[
Influence(i,j,\tau,t)
\]

instead of static correlation.

Recommended information universes:
- Micro tape: 20–100 tightly related instruments at tick/book resolution
- Intraday global tape: 200–500 instruments
- Macro tape: 500–2,000+ instruments and economic series

Use sparse attention / Top-K influence selection at each instant.

---

# 4. What Can Break It

Key failure modes:
- regime inversion
- lead-lag collapse
- spurious causality
- hidden common drivers
- timestamp leakage
- clock synchronization errors
- stale-feed artifacts
- latency arbitrage against the system
- transaction-cost domination
- capacity collapse
- crowding
- attention instability
- online-learning instability
- confidence miscalibration
- distribution shift
- constituent-weight drift
- continuous-futures contamination
- revised macro-data leakage
- extreme-event blindness
- correlation collapse
- graph explosion
- multiple-testing blindness
- research/live mismatch
- silent infrastructure failures

Therefore the system must maximize falsification and safe degradation, not just prediction.

Governing loop:

\[
\text{Predict}
\rightarrow
\text{Doubt}
\rightarrow
\text{Attack}
\rightarrow
\text{Verify}
\rightarrow
\text{Decide}
\]

---

# 5. ICARUS AEGIS Ω — Architecture Specification

## Mission

AEGIS Ω is the supervisory intelligence substrate of Icarus.

Its purpose is to determine:
- what the market most likely is doing,
- what could invalidate that interpretation,
- how uncertain the system is,
- whether the opportunity survives adverse assumptions,
- how much authority each model deserves,
- whether Icarus should act at all.

Objective:

\[
\max \text{Useful Information}
+\max \text{Adaptability}
+\max \text{Robustness}
-\max \text{Silent Failure}
-\max \text{False Confidence}
\]

Absolute immunity to every market condition cannot be guaranteed. The engineering objective is:

\[
\boxed{\text{No known single failure should silently convert bad evidence into increased trading authority.}}
\]

Failures must be detected, localized, downgraded, quarantined, or cause abstention.

## System hierarchy

```text
                 DAEDALUS
            discovery / research
                    │
                    ▼
                  NEXUS
          global market world model
                    │
                    ▼
          EXISTING ICARUS ENGINES
       RATE / TIDE / structure / ML
                    │
                    ▼
╔══════════════════════════════════════════╗
║              ICARUS AEGIS Ω             ║
║                                          ║
║ Evidence Fabric                          ║
║ Temporal Reconstruction                  ║
║ Multiscale World Model                   ║
║ Dynamic Influence Graph                  ║
║ Expert Lattice                           ║
║ Regime Memory                            ║
║ Causal-Skeptic Layer                     ║
║ Drift / OOD Detection                    ║
║ Distributional Path Forecasting          ║
║ Uncertainty Decomposition                ║
║ Adversarial Falsification                ║
║ Robust Decision Optimization             ║
║ Portfolio Intelligence                   ║
║ Execution Qualification                  ║
║ Immutable Decision Ledger                ║
╚══════════════════════════════════════════╝
                    │
                    ▼
             RISK / EXECUTION
```

Daedalus = discover.
Nexus = understand.
Icarus = predict.
AEGIS = decide what deserves trust.

## 5.1 Evidence Fabric

Every observation becomes an evidence object with:
- value
- instrument
- venue
- contract
- event timestamp
- source timestamp
- ingest timestamp
- processing timestamp
- sequence identifier
- revision state
- latency estimate
- freshness
- schema version
- quality score
- provenance hash

Distinguish:

\[
t_{event}, t_{exchange}, t_{vendor}, t_{ingest}, t_{decision}
\]

Conflicting feeds are not silently averaged. Disagreement becomes a data-quality state. Historical replay must be deterministic.

## 5.2 Temporal Integrity Engine

Responsibilities:
- sequence reconstruction
- lateness detection
- clock-offset estimation
- stale-feed detection
- missing-event detection
- out-of-order handling

Cross-market prediction:

\[
X_i(t-\tau)\rightarrow X_j(t)
\]

is valid only when the information was actually observable before the target event.

No silent time repair.

## 5.3 Multiscale Market Representation

Maintain distinct memories:

\[
M_{\mu}, M_s, M_m, M_h, M_d, M_w
\]

for microstructure, seconds, minutes, hours, daily and weekly/slower structural state.

Fuse:

\[
Z_t = F(M_\mu,M_s,M_m,M_h,M_d,M_w)
\]

Do not force all horizons to agree.

## 5.4 Continuous World State

Latent state:

\[
Z_t = [P,V,L,F,T,C,J,D,S,U,E]
\]

Possible meanings:
- persistence
- volatility
- liquidity
- directional flow
- flow toxicity
- crowding
- jump intensity
- drift
- structural stability
- uncertainty
- event pressure

Use continuous/probabilistic states, not simplistic labels.

## 5.5 Global Market Influence Graph

Dynamic directed graph:

\[
G_t=(V,E_t)
\]

Each edge stores:

\[
E_{ij,t} = [lag,direction,strength,stability,regime,decay,redundancy,confidence,cost\ relevance]
\]

Target:

\[
Influence(i,j,\tau,t)
\]

not simple correlation.

## 5.6 Causal-Skeptic Layer

Every relationship competes against:

\[
X\rightarrow Y
\]
\[
Y\rightarrow X
\]
\[
Z\rightarrow X,Y
\]
\[
\text{temporal coincidence}
\]

Use conditional independence tests, lag perturbation, placebo variables, feature removal, counterfactuals and common-driver analysis. Predictive usefulness and causal confidence remain separate.

## 5.7 Expert Lattice

Expert families:
- Persistence
- Equilibrium
- Microstructure
- Liquidity
- Cross-market
- Curve/carry
- Volatility
- Event
- Structural break
- Execution
- Failure expert

The Failure Expert estimates when other experts are likely to fail.

No expert gets authority due to mathematical sophistication alone.

## 5.8 Model Population

Each family may contain:

\[
E_k=\{E_k^{frozen},E_k^{adaptive},E_k^{regime1},E_k^{regime2},E_k^{simple}\}
\]

Retain frozen experts, an adaptive expert, regime specialists and simple baselines. Complex models must prove incremental net value.

## 5.9 Episodic Regime Memory

Retrieve similar historical latent states:

\[
\mathcal N(Z_t)=\operatorname{TopK}\{Z_{past}\}
\]

Store expert performance, failure modes, relationship transitions and alpha decay. Memory informs priors; it never overrides current evidence.

## 5.10 Dynamic Expert Credibility

\[
w_{k,t}=P(E_k\text{ reliable}\mid Z_t,D_{1:t})
\]

Inputs:
- OOS history
- current regime fit
- calibration
- residual drift
- cost robustness
- redundancy
- live predictive contribution

Trust should fall faster than it rises.

## 5.11 Information Redundancy Control

\[
IndependentValue_i = \frac{IncrementalInformation_i}{1+Redundancy_i}
\]

Hurst, DFA, FDI, Ehlers, adaptive kernels, RSI, CCI, WaveTrend, Lorentzian similarity and Kalman-derived states remain candidates but cannot manufacture confidence by redundancy.

## 5.12 Distributional Path Intelligence

Predict:

\[
p(P_{t+1:t+H}\mid\mathcal F_t)
\]

Outputs:
- expected return
- quantiles
- skew
- tail probability
- expected MFE
- expected MAE
- first-passage probabilities
- time-to-event distributions

Example:

\[
P(+100\ before\ -25)
\]

is more useful than next-candle classification.

## 5.13 Hazard Engine

Maintain:

\[
\lambda_{reversal}(t),
\lambda_{breakout}(t),
\lambda_{stop}(t),
\lambda_{target}(t),
\lambda_{liquidity\ failure}(t)
\]

## 5.14 Uncertainty Decomposition

\[
U_t = U_{aleatoric}+U_{epistemic}+U_{drift}+U_{data}+U_{disagreement}+U_{execution}
\]

Different uncertainty types produce different responses.

## 5.15 Calibration Layer

Raw neural confidence is not trading confidence. Calibration must be horizon- and state-specific. Monitor empirical coverage. Conformal-style methods may be used only with time-series-aware assumptions and active coverage monitoring.

## 5.16 OOD and Drift Intelligence

Maintain:

\[
D_{feature},D_{representation},D_{residual},D_{relationship},D_{calibration},D_{execution}
\]

Distinguish changed inputs from changed model relationships.

## 5.17 Adversarial Falsification Engine

Attack candidates with:
- feed delay
- stale markets
- feature corruption
- missing instruments
- reversed correlations
- widened spreads
- increased volatility
- liquidity disappearance
- expert dropout
- timestamp changes
- common-driver substitutions
- regime shifts

\[
Robustness(a)=P(a\ remains\ acceptable\mid\mathcal A)
\]

Fragile trades are rejected.

## 5.18 Counterfactual Engine

For each candidate:

\[
a,-a,0
\]

Evaluate action, opposite action and abstention. Also evaluate expert removal:

\[
Prediction_{\setminus E_k}
\]

to measure dependency.

## 5.19 Distributionally Robust Decision Optimizer

\[
a^* = \arg\max_a \min_{Q\in\mathcal B(P)} E_Q[U(a,Y)]
\]

Include CVaR, drawdown proxies, turnover penalties, cost uncertainty, correlation exposure and liquidity limits.

## 5.20 Decision Lower Bound

\[
LCB(NetEdge)=E(NetEdge)-kU(NetEdge)
\]

Qualification requires:

\[
LCB(NetEdge)>0
\]

after spread, slippage, fees, impact, adverse selection and latency.

## 5.21 Portfolio Intelligence

\[
\max_q\{\mu^\top q-\lambda q^\top\Sigma q-\gamma CVaR-C(q)\}
\]

Subject to margin, concentration, correlation, liquidity and risk limits.

## 5.22 Execution Qualification

Estimate fill probability, expected fill time, queue position, adverse-selection probability, spread evolution, temporary impact and permanent impact.

Reject when:

\[
ExpectedAlpha < ExpectedExecutionCost
\]

Advanced RL/POMDP execution may be a challenger but never a bypass around fixed safety constraints.

## 5.23 Formal Safety Invariants

\[
Uncertainty\uparrow \not\Rightarrow RiskAuthority\uparrow
\]

\[
DataIntegrity=0 \Rightarrow Qualification=0
\]

\[
CriticalFeedStale=1 \Rightarrow NewAuthority=0
\]

\[
UnknownSchema=1 \Rightarrow RejectInput
\]

\[
OOD\uparrow \Rightarrow MaximumAuthority\downarrow
\]

\[
ExecutionCost>Edge \Rightarrow TradeRejected
\]

These are architectural laws, not learned behaviors.

## 5.24 Reliability Quorum

Confidence comes from independent evidence domains, not indicator count. Possible domains: state, market structure, cross-market information, uncertainty integrity, data integrity and execution economics.

Ten correlated momentum-like signals cannot replace one missing independent domain.

## 5.25 Research Integrity Ledger

Every Daedalus experiment must record:
- hypothesis family
- variants attempted
- parameter-search volume
- markets
- periods
- regimes
- cost assumptions
- validation protocol
- OOS behavior
- failure regimes

Penalize discovery significance as trial count rises.

## 5.26 Champion / Challenger Evolution

Production models are immutable champions. New models become challengers.

Promotion requires superiority across:
- predictive quality
- calibration
- net-of-cost performance
- drawdown
- tail behavior
- cross-regime stability
- adversarial resilience
- live shadow behavior

Previous champions remain recoverable.

## 5.27 Shadow Deployment

Challengers run without authority first. Compare predictions, uncertainty, decisions and hypothetical executions. Only sustained shadow evidence can unlock promotion.

## 5.28 Digital Market Twin

Replay/simulation should support:
- recorded-market replay
- latency perturbation
- spread shocks
- liquidity removal
- order-book disturbances
- correlation breaks
- synthetic structural transitions for testing only

Synthetic test disturbances must never be confused with live/historical bars.

## 5.29 Software Reliability Plane

Every decision links:

\[
DataVersion\rightarrow FeatureVersion\rightarrow ModelVersion\rightarrow ConfigVersion\rightarrow DecisionVersion
\]

Artifacts are hashed, schemas versioned, outputs append-only, critical decisions reproducible.

## 5.30 Security Plane

- verify model/config integrity before loading
- treat external data as untrusted
- isolate credentials
- do not execute arbitrary research-generated code
- separate research and production environments

## 5.31 Computational Degradation Hierarchy

\[
Full\rightarrow ReducedExpert\rightarrow Baseline\rightarrow ObserveOnly\rightarrow Halt
\]

Every transition is explicit and logged.

## 5.32 Immutable Decision Envelope

Final status vocabulary:

\[
QUALIFIED, DEGRADED, ABSTAIN, QUARANTINED
\]

Example:

```json
{
  "symbol": "NQ",
  "family": "clock_minutes",
  "candidate": "LONG",
  "state_id": "...",
  "expected_net_edge": 0.0,
  "edge_lcb": 0.0,
  "p_target_before_stop": 0.0,
  "expected_mfe": 0.0,
  "expected_mae": 0.0,
  "epistemic_uncertainty": 0.0,
  "aleatoric_uncertainty": 0.0,
  "drift_score": 0.0,
  "ood_score": 0.0,
  "calibration_score": 0.0,
  "model_disagreement": 0.0,
  "data_integrity": true,
  "cost_stress": true,
  "adversarial_robustness": 0.0,
  "status": "QUALIFIED|DEGRADED|ABSTAIN|QUARANTINED",
  "execution_authorized": false
}
```

## 5.33 Integration Principle

Existing Icarus systems remain evidence producers. AEGIS does not rewrite trainer slot semantics.

Frozen constraints:
- no invented trainer slots/features
- no Pulse rewrite
- execution_authorized=false
- no synthetic bars
- deterministic time ordering

## 5.34 Definition of Success

Evaluate jointly:

\[
PredictiveAccuracy,
Calibration,
NetEdge,
CVaR,
Drawdown,
Stability,
OODBehavior,
DriftRecovery,
FaultContainment,
ExecutionEfficiency,
Reproducibility
\]

Success means survival-adjusted decision quality, not vanity accuracy.

## Governing Law

Every future component must satisfy:

\[
\boxed{\Delta Information\quad\text{or}\quad\Delta Robustness\quad\text{or}\quad\Delta Safety>0}
\]

If it does not, it does not belong in production.

---

# 6. AEGIS Kernel Implementation Plan

## Goal

Build the immutable AEGIS Ω supervisory kernel that:
- validates evidence
- enforces temporal integrity
- fails closed under uncertainty or bad data
- produces immutable decision envelopes
- maintains tamper-evident audit history
- supports deterministic replay
- does not change existing Icarus trainer slots
- does not grant execution authority

## Architecture

Create an isolated `icarus_engine.aegis` package.

Existing Icarus components remain evidence producers.

The kernel contains no predictive ML in Phase 1. It establishes safety, provenance, audit and reproducibility for later layers.

## Tech Stack

- Python 3.10+
- stdlib: dataclasses, enum, datetime, hashlib, json, pathlib, argparse, typing
- pytest

## Global Constraints

- preserve existing Icarus universe
- preserve feature ordering
- preserve label semantics
- preserve trainer slots and swap rules
- never synthesize missing bars
- never use event with `ts_event > ts_bar`
- never create a hidden Pulse execution path
- `execution_authorized` remains false
- invalid evidence degrades or blocks qualification
- unknown critical schemas are rejected
- persisted artifacts use deterministic canonical serialization
- no third-party runtime dependency in Kernel Phase 1
- AEGIS state lives under `run/aegis/`
- existing trainer artifacts remain untouched
- existing trainer slots 0–4 remain unchanged

## Review Focus

1. Future/stale timestamps
2. Malformed/unknown schemas
3. Hash-chain tampering
4. Uncertainty monotonicity
5. Replay equality

## Task 1 — Immutable Evidence and Decision Contracts

Create:
- `icarus_engine/aegis/__init__.py`
- `icarus_engine/aegis/models.py`
- `tests_engine/test_aegis_models.py`

Interfaces:
- `EvidenceRecord`
- `EvidenceQuality`
- `DecisionStatus`
- `DecisionEnvelope`
- `canonical_json(value) -> str`
- `canonical_sha256(value) -> str`

Statuses:

```python
class DecisionStatus(str, Enum):
    QUALIFIED = "QUALIFIED"
    DEGRADED = "DEGRADED"
    ABSTAIN = "ABSTAIN"
    QUARANTINED = "QUARANTINED"
```

Evidence qualities:

```python
class EvidenceQuality(str, Enum):
    GOOD = "GOOD"
    DEGRADED = "DEGRADED"
    INVALID = "INVALID"
```

`DecisionEnvelope` must reject:
- `execution_authorized=True`
- risk authority outside `[0,1]`

Canonical serialization:

```python
json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
```

SHA-256 over UTF-8 canonical JSON.

Use strict TDD: red -> green -> refactor.

## Task 2 — Temporal Integrity and Provenance Guard

Create:
- `icarus_engine/aegis/timeguard.py`
- `tests_engine/test_aegis_timeguard.py`

Interface:

```python
@dataclass(frozen=True)
class TemporalPolicy:
    max_future_skew_ns: int
    max_staleness_ns: int
    require_monotonic_sequence: bool = True
```

Detect:
- future-dated evidence
- stale evidence
- sequence regression

`TemporalIntegrity`:

```python
ok: bool
stale: bool
future_dated: bool
sequence_regression: bool
findings: tuple[TemporalFinding, ...]
```

No interpolation or silent correction.

## Task 3 — Fail-Closed Qualification Kernel

Create:
- `icarus_engine/aegis/invariants.py`
- `icarus_engine/aegis/qualification.py`
- `tests_engine/test_aegis_qualification.py`

Context:

```python
data_integrity: bool
critical_feed_stale: bool
unknown_schema: bool
ood_score: float
drift_score: float
calibration_error: float
model_disagreement: float
execution_cost_stress_pass: bool
edge_lcb: float
```

Required precedence:

```text
QUARANTINED
    > ABSTAIN
        > DEGRADED
            > QUALIFIED
```

Required rules:
- `data_integrity=False -> QUARANTINED`
- `unknown_schema=True -> QUARANTINED`
- `critical_feed_stale=True -> ABSTAIN`
- `edge_lcb <= 0 -> ABSTAIN`
- `execution_cost_stress_pass=False -> ABSTAIN`

Monotonicity:

\[
riskAuthority(highUncertainty)\le riskAuthority(lowUncertainty)
\]

Phase 1 authority formula must be deterministic and transparent.

## Task 4 — Tamper-Evident Append-Only Decision Ledger

Create:
- `icarus_engine/aegis/audit.py`
- `tests_engine/test_aegis_audit.py`

Ledger:
`run/aegis/decisions.jsonl`

Record fields:
- previous_hash
- payload_hash
- record_hash

Hash chain:

\[
recordHash_n=SHA256(previousHash_n\Vert canonicalPayload_n)
\]

Tests:
- valid ledger verifies
- edited record fails
- deleted middle record fails
- reordered records fail

Use `flush()` and `os.fsync()` before success return.

## Task 5 — Deterministic Evidence Replay

Create:
- `icarus_engine/aegis/replay.py`
- `tests_engine/test_aegis_replay.py`

Pipeline:

```text
deserialize
→ schema validation
→ temporal validation
→ safety context
→ qualification
→ envelope creation
→ canonical hash
```

Same input must reproduce:
- same envelope hash
- same status
- same risk authority

Mutating evidence time must change replay hash and, where applicable, qualification.

## Task 6 — AEGIS Doctor and Verification CLI

Create:
- `icarus_engine/aegis/__main__.py`
- `tests_engine/test_aegis_cli.py`

Modify:
- `pyproject.toml`

Command:
`icarus-aegis`

Subcommands:
- `doctor`
- `verify-ledger`
- `replay`

`doctor` checks:
- AEGIS version
- Python compatibility
- writable `run/aegis`
- ledger verification
- execution-authorization invariant

Corrupt ledger -> nonzero exit.

## Task 7 — Property and Fault-Injection Tests

Create:
- `tests_engine/test_aegis_faults.py`
- `tests_engine/test_aegis_properties.py`

Campaigns:
- future timestamps
- negative freshness
- duplicate sequence
- sequence regression
- massive staleness
- boundary timestamps
- uncertainty monotonicity
- canonical hash ordering
- ledger corruption

## Task 8 — Repository Knowledge and Handoff Synchronization

Create:
- `docs/aegis/README.md`
- `docs/aegis/contracts.md`
- `docs/aegis/safety-invariants.md`
- `docs/aegis/audit-ledger.md`
- `docs/aegis/replay.md`

Where integrated, update:
- README
- COMMANDS
- MODEL_HANDOFF
- HANDOFF_LOG

Ownership boundary:

```text
Existing Icarus trainers = predictive evidence producers.
AEGIS Kernel = validation, qualification, audit and replay authority.
AEGIS Kernel does not alter trainer slot semantics.
AEGIS Kernel does not authorize execution.
```

## Final Kernel Gate

Must pass:
- engine test suite
- `icarus-aegis doctor`
- `icarus-aegis verify-ledger`

Verify:
- `execution_authorized == false` everywhere
- trainer slots unchanged
- feature order unchanged
- symbol universe unchanged
- no new third-party runtime dependency
- no synthetic data path
- no Pulse execution path

Acceptance criteria:
1. malformed critical evidence cannot qualify
2. future/stale critical evidence cannot silently qualify
3. increasing uncertainty cannot increase authority
4. non-positive conservative edge cannot qualify
5. ledger tampering is detectable
6. replay is deterministic
7. existing Icarus tests still pass
8. all AEGIS tests pass
9. persisted artifacts remain `execution_authorized=false`
10. documentation matches behavior

Only after this gate should World-State Substrate begin.

---

# 7. Masterbuild Sequencing

Build order:

1. Evidence / provenance / temporal-integrity kernel
2. Multiscale state representation and deterministic feature contracts
3. Dynamic cross-market influence graph with causal-skeptic tests
4. Expert lattice with simple baselines and redundancy controls
5. Drift / OOD / calibration / uncertainty decomposition
6. Distributional path and hazard forecasting
7. Adversarial falsification / counterfactuals / robust optimization
8. Portfolio and execution qualification
9. Champion-challenger / shadow deployment / digital twin
10. Full integration and simplification audit

The key rule is depth-first validation: try to break each layer before adding the next one.

---

# 8. Masterbuild Loop Prompt

Continue the ICARUS AEGIS Ω masterbuild as a disciplined engineering program, not a feature brainstorm. Each run must complete one substantive extraction-ready batch and improve the weakest remaining layer. Work depth-first in this order unless evidence forces reprioritization: (1) evidence/provenance/temporal-integrity kernel, (2) multiscale state representation and deterministic feature contracts, (3) dynamic cross-market influence graph with causal-skeptic tests, (4) expert lattice with simple baselines and redundancy controls, (5) drift/OOD/calibration/uncertainty decomposition, (6) distributional path and hazard forecasting, (7) adversarial falsification/counterfactuals/robust optimization, (8) portfolio and execution qualification, (9) champion-challenger/shadow deployment/digital twin, (10) full integration and simplification audit.

For the chosen layer, do all of the following in the same run:
- identify the strongest unresolved failure mode;
- specify or refine exact interfaces, schemas, invariants, algorithms and failure semantics;
- add concrete tests or adversarial cases;
- remove redundant or ornamental complexity;
- produce code-level pseudocode or extraction-ready Python where appropriate;
- verify consistency with prior AEGIS constraints;
- state what remains unproven.

Preserve these non-negotiables:
- execution_authorized=false
- no synthetic bars
- no invented Icarus trainer slots/features
- no Pulse rewrite
- deterministic canonical serialization
- strict time-order validation
- fail-closed qualification
- immutable/tamper-evident audit
- deterministic replay
- uncertainty cannot increase authority
- critical stale/unknown data cannot silently qualify
- no model gets authority without incremental OOS value net of cost

Never call the system perfect. If a layer is mature, try to break it before adding anything new. Prefer falsification, simplification and measurable robustness over additional sophistication. Output only substantive progress another Codex chat can directly extract into Icarus.

---

# 9. Red-Team Loop Prompt

Independently red-team the current ICARUS AEGIS Ω masterbuild every hour. Do not duplicate the builder loop.

Attack:
- silent failure
- overfitting
- timestamp leakage
- calibration error
- nonstationarity
- common-driver confusion
- redundant expert evidence
- execution-cost blindness
- fault propagation
- schema ambiguity
- replay nondeterminism
- security/integrity gaps
- contradictions with Icarus constraints

For each run:
1. identify the highest-severity unresolved weakness;
2. construct a concrete adversarial scenario or counterexample;
3. specify the exact test/invariant/interface change that would catch it;
4. recommend simplification where complexity adds no incremental information;
5. state what remains unproven.

Preserve all non-negotiables and produce only actionable findings that the builder or main Codex chat can directly integrate.

---

# 10. Codex Handoff

## Objective

Use this document as the implementation source for AEGIS Ω inside the Icarus engine.

Do not assume prior conversational claims of code completion or passing tests are implementation evidence. Rebuild and verify everything from source.

## Immediate next step

Implement the AEGIS Kernel first using TDD.

Do not start graph models, transformers, expert routing or execution intelligence until the Kernel gate is green.

## Required implementation sequence

### Phase 1 — Kernel
- immutable evidence contracts
- canonical serialization / hashes
- temporal integrity
- fail-closed qualification
- monotonic authority reduction with uncertainty
- tamper-evident ledger
- deterministic replay
- doctor / verify-ledger / replay CLI
- property / fault-injection tests

### Phase 2 — World-State Substrate
- multiscale memories
- deterministic feature contracts
- latent-state interface
- dynamic market graph
- temporal alignment

### Phase 3 — Expert Lattice
- persistence
- equilibrium
- microstructure
- liquidity
- cross-market
- carry
- volatility
- event
- structural break
- failure expert
- simple baselines

### Phase 4 — Epistemic Intelligence
- OOD detection
- drift detection
- calibration
- coverage monitoring
- disagreement decomposition
- change-point-aware uncertainty

### Phase 5 — Falsification / Robust Control
- counterfactuals
- adversarial perturbations
- expert dropout
- common-driver tests
- robust optimization
- CVaR
- edge lower bounds

### Phase 6 — Portfolio / Execution Qualification
- concentration
- contagion
- liquidity capacity
- queue/fill/adverse-selection models
- execution veto

### Phase 7 — Evolution / Deployment
- champion/challenger
- immutable model versions
- shadow-live
- promotion gates
- rollback
- digital market twin
- fault-injection campaigns

## Invariants that must never be weakened

1. `execution_authorized=false`
2. no synthetic bars
3. no invented trainer slots/features
4. no Pulse rewrite
5. deterministic canonical serialization
6. strict time ordering
7. fail closed on critical data uncertainty
8. deterministic replay
9. tamper-evident audit
10. uncertainty cannot increase authority
11. stale/unknown critical data cannot silently qualify
12. complexity must prove incremental OOS value net of cost

## Verification philosophy

The build is not complete when it merely looks sophisticated.

Every layer must be:
1. specified
2. implemented
3. unit tested
4. property tested where appropriate
5. adversarially attacked
6. verified against prior constraints
7. simplified if complexity is redundant

## Definition of complete

A complete AEGIS integration requires:
- kernel gate green
- all later strata integrated without bypassing kernel controls
- deterministic replay from evidence to decision
- explicit OOD/drift behavior
- calibrated uncertainty
- robust decision lower bounds
- portfolio-aware qualification
- execution-cost veto
- champion/challenger deployment discipline
- full-system red-team and simplification audit
- no hidden execution authority

---

# 11. Final Design Principle

The final system should not be judged by how many advanced modules it contains.

It should be judged by whether every retained module adds at least one of:
- independent information
- robustness
- safety
- calibration
- execution value
- reproducibility

If not, remove it.

The master principle remains:

\[
\boxed{\text{Predict + Doubt + Attack + Verify + Decide}}
\]