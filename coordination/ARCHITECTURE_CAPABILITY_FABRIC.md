# ICARUS Capability Fabric Architecture

## Objective

Expand ICARUS across research, market intelligence, modeling, diagnostics, validation, observability, and agent collaboration while preserving deterministic strategy ownership and preventing accidental execution-authority escalation.

## Preferred architecture

Use a **layered capability fabric**, not a monolithic strategy rewrite.

### L0 — Immutable truth layer

Owns facts that downstream systems must not reinterpret casually:

- symbol / contract identity,
- exchange and session definition,
- timezone,
- raw timestamps,
- observed-at / available-at / decision-at,
- roll rules,
- raw bar or event payload hashes,
- source identity,
- repository revision,
- configuration digest.

### L1 — Evidence and provenance fabric

Canonicalizes provider outputs into traceable evidence objects.

Required concepts:

- `EVIDENCE_ID`
- `CLAIM_ID`
- `RESEARCH_ATTEMPT_ID`
- `SOURCE_ID`
- `RAW_ARTIFACT_HASH`
- dependency edges
- conflict edges
- evidence freshness
- policy version / epoch
- repository revision
- source reliability metadata
- derivation lineage

A transformed summary is not automatically independent evidence. New evidence IDs should represent genuinely new canonical observations, tests, or independent compatibility results.

### L2 — Research and diagnostic laboratory

Research surfaces may be broad and experimental. They remain non-authoritative until qualified.

Capabilities include:

- leave-one-vote-out,
- leave-one-family-out,
- threshold surfaces,
- walk-forward validation,
- bootstrap distributions,
- regime-conditioned analysis,
- perturbation tests,
- latency sensitivity,
- missing/stale/corrupt-data tests,
- execution-cost stress,
- slippage and commission stress,
- delayed-provider scenarios,
- session-boundary stress,
- parameter sensitivity,
- temporal leakage probes,
- reproducibility hashes.

Default production behavior must be identical when diagnostics are disabled.

### L3 — Model and composite layer

Models may include statistical, signal-processing, ML, and composite mechanisms, but authority is mediated by:

```
raw output
→ calibration
→ uncertainty
→ estimator validity
→ redundancy status
→ data sufficiency
→ stress/falsification status
→ evidence authority
```

A more complex model is not automatically a stronger authority.

### L4 — Strategy decision core

This layer owns production strategy semantics.

Rules:

- accepts only canonical features / evidence-approved configuration,
- never consumes arbitrary provider payloads directly,
- does not silently inherit research-only switches,
- maintains deterministic replay requirements,
- preserves existing ownership boundaries unless a separately approved design changes them.

### L5 — Execution boundary

Owns broker / automation interfaces, order intent, idempotency, quantity, duplicate suppression, and explicit authorization.

Default for this coordination work:

`execution_authorized=false`

No provider, researcher, model, or design agent may bypass this boundary.

## Control plane

The target stage sequence is:

```
S1 → S2 → S3 → S4 → S5
```

Where later stages consume exact same-cycle, exact-policy, exact-revision evidence from earlier stages.

A safe promotion chain is:

```
OBSERVED
→ RESEARCHED
→ EMPIRICALLY_SUPPORTED
→ IMPLEMENTATION_READY
→ VERIFIED_FOR_INTEGRATION
```

Stage 4 may at most produce `IMPLEMENTATION_READY`; Stage 5 owns `VERIFIED_FOR_INTEGRATION`.

## Provider mesh

Providers should connect through adapters that terminate at L1, not at L4/L5.

### Market / price / fundamentals

Examples available to the user include:

- Massive
- Twelve Data
- FMP
- Bigdata.com
- Zacks Financial Data
- StackerScan
- U.S. Gold Bureau Metal Spots
- Bybit

### Literature / external research / web evidence

Examples:

- Scite
- Agent Reach
- DataBlue

### Blockchain / crypto state

- Blockscout

### Design / presentation / visualization

- Figma
- Visualize
- Runway

These surfaces can document, visualize, or communicate ICARUS state but are not trading authorities.

### Orchestration / specialist coordination

Orchestrators should read the control contract and emit structured handoffs, never hidden authority changes.

## Authority monotonicity

The following must never increase decision authority:

- missing data,
- unknown provenance,
- stale evidence,
- conflicting evidence,
- estimator invalidity,
- insufficient ablation,
- cross-revision mismatch,
- mixed control policy,
- failed stress tests,
- unknown oracle independence.

At best these preserve authority; normally they reduce it.

## Deterministic replay target

Given identical:

- raw artifacts,
- repository revision,
- config digest,
- policy version,
- environment contract,
- stage inputs,

the system should be able to reproduce the same normalized observations, claim graph, and decision-state transitions.

## Migration philosophy

1. Add observability before changing behavior.
2. Add schemas before adding agent autonomy.
3. Add research-only switches before production switches.
4. Add stress and mutation tests before trusting new model logic.
5. Prefer deletion/simplification when a new mechanism is redundant.
6. Preserve subsystem ownership; avoid duplicate shadow engines.
