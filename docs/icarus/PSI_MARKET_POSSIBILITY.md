# ICARUS Ψ — Latent Pressure & Market Possibility Engine

## Identity

**ICARUS Ψ (`psi`) is a distinct AION-owned research subsystem.** It does not rename, replace, merge into, or redefine the existing ICARUS **ORACLE** subsystem.

Ψ is shadow/research only:

- `execution_authorized=false`
- `production_decision_authorized=false`
- scenario cluster shares are not calibrated probabilities
- lagged leader associations are not represented as structural causality
- missing evidence stays unavailable rather than becoming a neutral zero
- the edge gate defaults to `NO_EDGE`

## Purpose

Ψ asks how constrained the near-term market possibility space is, what observable forces create that constraint, and what remains unexplained.

It combines:

1. Latent pressure — queue, repricing, aggressive-volume, cross-asset, basis, gamma and forced-flow evidence.
2. Pressure/price elasticity — absorption and liquidity-vacuum diagnostics.
3. Dynamic leadership — rolling lagged cross-asset association, explicitly diagnostic rather than proof of causality.
4. Counterfactual price — local force-balance synthetic price plus unexplained dislocation.
5. Future-space lattice — deterministic constraint-aware scenarios clustered into UP / FLAT / DOWN.
6. Future entropy / collapse — normalized Shannon entropy over scenario clusters.
7. Phase boundary / event horizon — research transition thresholds.
8. Forced consensus — multiple distinct observed mechanisms must align.
9. Inverse hidden-state inference — ranked explanations without asserting an unobserved participant identity.
10. Market shadows — remove one observed force at a time from the synthetic state.
11. Information wave — source-agnostic residual novelty for unexplained information arrival before provenance is identified.

## Evidence hierarchy

### Native live evidence

When the active feed supports it, Ψ consumes signed trade ticks, MBP-10 depth, and ICARUS cross-asset observations. Unsupported domains remain unavailable.

### Optional external evidence

Authenticated research callers may POST provenance-labelled evidence to `POST /admin/possibility/evidence`.

Supported values are `gamma_pressure`, `basis_pressure`, `cta_pressure`, `liquidation_pressure`, and `rebalance_pressure`. Values are bounded to `[-1,+1]`, confidence to `[0,1]`, and evidence expires after a bounded TTL. Unknown feature names are rejected.

Evidence is persisted in an append-only local SQLite ledger under ICARUS research state whenever the runtime exposes a durable `base_dir`. Exact receipts are idempotent, TTL is anchored to the observation timestamp, expired evidence remains auditable but cannot become active, and restart recovery deterministically selects the newest causally available observation per feature.

Authenticated readers can inspect this ledger through `GET /api/possibility/evidence` or the MCP `engine_possibility_evidence` tool. An optional `as_of` timestamp reconstructs which external force observation was active historically without allowing later observations to leak backward.

## Fabric integration

ARGUS / NEXUS / DATA provide live market evidence. Ψ produces latent-pressure and possibility state for the trader UI and contributes a distinct `psi` research vote to PARALLAX. PARALLAX can then measure Ψ through paired ablation; DREAMSTATE only generates hypotheses from observed counterfactual evidence.

PARALLAX decision ingestion automatically adds a fresh `psi` subsystem vote when the caller did not provide one. This vote is research context and never an execution vote.

AEGIS / DAEDALUS remain the falsification and protected-validation authorities for future Ψ-derived candidates. Adaptive Brain registers Ψ separately so it cannot be confused with ORACLE, ARGUS, PARALLAX, DREAMSTATE, or ML.

## Edge gate

Ψ returns `NO_EDGE` unless evidence requirements pass: finite latent-pressure magnitude, confidence-weighted coverage, sufficient future-space collapse, a warmed leader graph, microstructure evidence when broader coverage is weak, and forced-consensus confirmation when broader evidence is weak.

Passing the research gate can produce `LONG_BIAS` or `SHORT_BIAS`, but those labels cannot place, size, or authorize an order.

## Trader interface

The first-class **ICARUS Ψ** tab shows latent pressure, component provenance, evidence coverage, elasticity, information-wave novelty, synthetic price, unexplained dislocation, future entropy/collapse, future clusters, leaders, phase boundary/event horizon, forced consensus, hidden-state hypotheses, market shadows, explicit `NO_EDGE` blockers, and data health.

The panel polls only while the Ψ tab is active.