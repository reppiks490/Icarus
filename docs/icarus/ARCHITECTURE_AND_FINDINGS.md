# ICARUS Architecture and Findings

## 1. Architecture decision

Selected path: **Layered Capability Fabric**.

Rejected as default:
- Monolithic super-engine: excessive coupling, circular confirmation, difficult fault isolation.
- Immediate full microservice split: operational complexity exceeds current verified need.

The selected architecture expands aggressively outside the protected execution boundary.

## 2. Target layers

### L0 — Temporal truth

Every datum capable of affecting research or decisions should carry, where applicable:

- source identity
- symbol/instrument identity
- contract and roll identity
- timezone
- session/calendar identity
- observed timestamp
- publication/availability timestamp
- decision timestamp
- raw artifact hash
- revision/hash of the parser or transform

A historical feature is invalid when the source information was not actually available at the historical decision time.

### L1 — Evidence fabric

Canonical lineage:

`SOURCE_ID -> RAW_ARTIFACT_HASH -> OBSERVATION_ID -> TRANSFORM_ID -> EVIDENCE_ID -> CLAIM_ID -> DECISION_CONTEXT_ID`

Evidence records must preserve disagreement. Provider quorum is not majority-vote truth; it is a comparison surface that retains provenance, latency, and conflict.

### L2 — Research laboratory

Research expands independently of production decision authority:

- leave-one-vote-out
- leave-one-family-out
- threshold surfaces
- perturbation tests
- regime-conditioned ablations
- walk-forward evaluation
- bootstrap distributions
- delayed/missing/stale source tests
- session-boundary tests
- market-cost stress
- bar corruption tests
- parameter sensitivity
- replay determinism
- feature-family attribution

### L3 — Model/composite layer

Models do not receive authority merely because they exist.

Required chain:

`raw output -> calibration -> uncertainty -> validity -> redundancy -> authority`

Candidate model families may include XGBoost, Kalman-family estimators, Hurst/DFA/FDI diagnostics, Ehlers-family transforms, Lorentzian or other distance metrics, CCI/momentum structures, and regime classifiers. Their presence is not proof of predictive value.

A component named like a model must be classified as `DERIVED_COMPOSITE` unless training artifacts, labels, split logic, calibration and out-of-sample evidence demonstrate a fitted estimator.

### L4 — Protected decision core

External providers and research processes cannot inject arbitrary trade instructions.

The decision core receives canonical validated inputs through explicit interfaces. Research-only instrumentation defaults off and must preserve baseline semantics when disabled.

### L5 — Execution boundary

Execution adapters require explicit authorization and must enforce:

- idempotency
- duplicate suppression
- position reconciliation
- sizing constraints
- broker/instrument mapping correctness
- separation between market-data access and order authority
- fail-closed behavior on ambiguous state

## 3. Repository findings

### 3.1 Control-state gap

At inspection time `state.json` is empty. This creates a major asymmetry: the repository exposes operational engine, bridge, plant and training entrypoints, but durable research/control-plane state is not yet represented there.

Recommendation: do **not** turn `state.json` into an unstructured dumping ground. Treat it as a compact index/pointer to versioned manifests and immutable evidence.

### 3.2 Explicit data separation already exists

The README correctly distinguishes:
- TradingView/Pine live-signal context
- Alpaca paper QQQ proxy routing
- Python engine using Yahoo/exported data
- CME licensing limitations
- file-feed/offline semantics

This separation should be preserved and strengthened through machine-readable data lineage.

### 3.3 Optional ML surface exists

`pyproject.toml` includes an ML extra with XGBoost. That proves dependency availability, not a validated trained model. Model authority requires artifacts and evidence.

### 3.4 Code-search limitation

Repository code search was not indexed during inspection. Therefore statements of non-existence must be based on direct file/repository evidence, not failed code search.

### 3.5 Nearby integration candidates

Adjacent repositories discovered:
- `Icarus-engine`
- `icarus-owner-actions`
- `icarus-causal-router`
- `icarus-csv-evidence-lab`

They should attach as satellites through the contract in `docs/icarus/AGENT_INTEGRATION.md`, not by directly mutating canonical state.

## 4. Provider mesh

Potential specialists can feed the evidence fabric:

- market/futures/equity/FX/crypto: Massive, Twelve Data, FMP
- financial intelligence: Bigdata.com, Zacks
- precious metals: StackerScan, U.S. Gold Bureau
- crypto exchange/on-chain: Bybit, Blockscout
- literature/evidence: Scite, Agent Reach, DataBlue
- design/monitoring surfaces: Figma, Visualize
- media/presentation: Runway

Provider output is evidence, not authority.

## 5. Failure modes to attack deliberately

- lookahead through publication latency
- contract-roll ambiguity
- session-boundary drift
- synthetic-minute invention
- hidden normalization using future windows
- target leakage
- duplicated evidence masquerading as independent confirmation
- provider disagreement collapsed into one value
- stale-model promotion
- tests derived from implementation rather than independent oracles
- cross-SHA evidence reuse
- paper/live instrument mapping mismatch
- repeated alerts or non-idempotent execution

## 6. Definition of progress

The build is more advanced when it can prove more of the following:

- exactly what evidence produced a claim
- exactly what code revision transformed it
- whether alternative providers disagreed
- whether the feature was available at decision time
- whether the result survives ablation and perturbation
- whether an intentionally broken implementation is caught
- whether replay of identical inputs reconstructs identical state
- whether external agent work can be attached without bypassing authority gates
