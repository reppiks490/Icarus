# Agent Handoff / Connection Contract

This file is for other Codex/ChatGPT/agent lanes joining the ICARUS build.

## Read first

1. `ICARUS_EMPIRICAL_QUALIFICATION.md`
2. `CURRENT_STATE.md`
3. `BLOCKER_MATRIX.md`
4. the contract relevant to your subsystem

## This lane is authoritative for

Evidence integrity, temporal validity, empirical model-value qualification, trial accounting, calibration/OOD authority constraints, economic and robustness admission gates.

## What connected lanes should provide

### Engine/data
Raw source bytes, parser code, row schemas, timestamp semantics and deterministic hashes.

### Model
Only qualified DatasetManifest + TemporalSample rows; null/logistic comparisons and exact experiment identity.

### Candidate/cross-market
Instrument identity, source availability time, lag definitions, candidate universe and all attempted specs.

### Execution
Contract specs, commission, tick size, multiplier, slippage/fill assumptions and latency evidence. Never infer real capacity from bar-level P&L.

### UI/reporting
Display qualification state without reinterpreting blocked/unqualified as success.

### Infrastructure
Preserve append-only experiment/audit semantics and exact artifact hashes.

## Handshake

```json
{
  "lane": "...",
  "code_commit": "...",
  "dataset_manifest_hash": "...",
  "temporal_contract_hash": "...",
  "feature_contract_hash": "...",
  "component_config_hash": "...",
  "execution_authorized": false
}
```

## Integration rule

If this lane marks an upstream condition P0/FAIL, downstream agents must not claim empirical authority from outputs depending on it.

## Current next dependency

SOURCE+DATA implementation and tests.

This branch intentionally changes documentation/state only. Pulse, broker execution and live trading logic remain untouched.
