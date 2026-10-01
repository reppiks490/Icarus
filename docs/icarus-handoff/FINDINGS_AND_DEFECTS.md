# Findings, Defects, and Capability Facts

## Repository findings

### VERIFIED / OBSERVED

**Canonical repository**
- `reppiks490/Icarus`
- Pinned baseline for this handoff: `007e70189945b8e112904cf92b2b1a12e43792d6`

**XGB Slot 1**
- Present as a repository contract/stub.
- Not yet implemented.
- `xgb_slot.py` raises `NotImplementedError`.

**Audit qualification**
- Current XGB qualification is materially weaker than the desired authority model.
- Artifact existence is trusted too heavily.
- Structural provenance validation is required before model artifacts can influence promotion.

**Trainer temporal leak**
- The trainer feature path currently reaches a broader event-window function.
- That function can observe event records whose timestamp is after the current bar.
- This conflicts with the frozen causal rule for model features: `ts_event <= ts_bar only`.
- Future realized surprise values are especially dangerous if present in an owner CSV.
- Fix should be scoped to a trainer-only causal/as-of feature path so intentional post-hoc audit behavior is preserved.

**Safety-result omission**
- Some skipped/early trainer reports do not explicitly carry `execution_authorized=false`.
- Absence is weaker than an explicit invariant.
- Every exit path should carry the lock.

## Methodology findings

### Holdout and calibration
- A terminal evaluation set must not simultaneously be described as untouched evidence and be used to fit a calibrator before raw terminal scoring.
- Preserve raw terminal scoring as the authority-bearing evaluation.
- If frozen repository requirements fit isotonic calibration on that terminal set afterward, calibrated output must remain provisional until fresh forward validation.

### Early stopping
- Validation used for early stopping is model-selection data.
- It is not terminal performance evidence.

### Multiple testing
- Failed/discarded variants remain part of the effective experiment universe.
- Do not reset attempt counts because a new cycle or dataset revision begins.
- If the attempt universe is not recoverable, report multiple-testing status as PARTIAL/UNCONTROLLED.

### Derived channels
- A nonlinear composite of existing features does not become independent evidence.
- The currently discussed `XGBoost5` Pulse score should be treated as derived unless canonical evidence proves an independently trained model.

## External-provider capability facts

These are environment/capability observations, **not trading evidence**.

### StackerScan
- Connected and returned live precious-metals spot data during inspection.

### Bybit
- Connected and returned BTC market/funding information during inspection.

### FMP / Bigdata
- Market/macro summaries were available during inspection.
- Instrument identity and spot-vs-futures semantics must remain explicit.

### Twelve Data
- Connector/auth capability was inspected; any actual use remains subject to the connected account/endpoint state.

### U.S. Gold Bureau
- Connector call was blocked by an allowed-IP policy (HTTP 403).
- Must be optional; no pipeline may depend on it as a mandatory source.

### Massive
- Futures capability/endpoint discovery was available, but the current plan did not provide the required futures entitlement for the targeted call.
- Treat as optional/degraded, not mandatory evidence.

### Scite
- Scientific-literature tooling was useful earlier in the work, but a monthly MCP usage limit was encountered later.
- Never fabricate literature retrieval when quota is exhausted.

### Figma
- Connected.
- Current workspace/seat was observed as restrictive for MCP read/write throughput.
- Appropriate for observability/design artifacts, not empirical authority.

### Runway
- Connected.
- Current workspace did not expose usable video-generation capability in the inspected path.
- Media generation is not part of the empirical core.

### Blockscout
- Connected blockchain capability was inspected.
- On-chain inputs, if later considered, must enter as typed optional evidence adapters and never bypass validation.

### Cheat Database / marketing-oriented tools
- No defensible contribution to the ICARUS empirical trading core was established.
- Deliberately excluded from model/evidence authority.

## Important source-semantics lesson

Observed values from different providers may legitimately differ because of:
- instrument identity,
- spot vs futures,
- venue,
- timestamp,
- quote convention,
- stale/update cadence,
- entitlement/data source.

Therefore every external datum should carry semantic identity and timestamp. Provider disagreement is a conflict to understand, not something to silently average.
