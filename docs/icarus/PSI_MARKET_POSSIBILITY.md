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
4. Counterfactual price — local force-balance synthetic price plus explicit residual-identifiability status. The same snapshot cannot independently identify an unexplained residual from the forces used to build that synthetic price.
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

For dynamic cross-asset leadership, Ψ now warm-starts from the engine's replayed `AssetRunner.bars` rather than accumulating history from dashboard/API polling. Peers are eligible only when chart cadence matches the target and lag pairs line up on exact bar timestamps. Returns spanning missing-bar gaps are discarded and reported in data health. Status-poll history remains an explicitly labelled fallback for minimal adapters that do not expose runner bars.

### Optional external evidence

Authenticated research callers may POST provenance-labelled evidence to `POST /admin/possibility/evidence`.

Supported values are `gamma_pressure`, `basis_pressure`, `cta_pressure`, `liquidation_pressure`, and `rebalance_pressure`. Values are bounded to `[-1,+1]`, confidence to `[0,1]`, and evidence expires after a bounded TTL anchored to its observation time. RFC3339 timestamps require an explicit timezone, future observations are rejected, and evidence already stale at receipt is rejected. Unknown feature names are rejected.

Accepted evidence is persisted in an append-only local SQLite ledger when ICARUS has a durable `base_dir`. Exact receipts are idempotent, restart recovery is deterministic, and the ledger preserves the causal receipt rules already enforced by Ψ: future observations and observations already stale for their requested TTL are rejected before storage.

Authenticated readers can inspect the ledger through `GET /api/possibility/evidence` or the MCP `engine_possibility_evidence` tool. The optional `as_of` timestamp returns only observations that were causally available by that historical time, so later evidence cannot leak backward into replay.

## Fabric integration

ARGUS / NEXUS / DATA provide live market evidence. Ψ produces latent-pressure and possibility state for the trader UI and contributes a distinct `psi` research vote to PARALLAX. PARALLAX can then measure Ψ through paired ablation; DREAMSTATE only generates hypotheses from observed counterfactual evidence.

PARALLAX decision ingestion does **not** auto-inject a fresh Ψ snapshot. A Ψ packet may be bound only when it was captured causally at the decision instant and supplied explicitly; this prevents look-ahead and preserves immutable decision identity.

AEGIS / DAEDALUS remain the falsification and protected-validation authorities for future Ψ-derived candidates. Adaptive Brain registers Ψ separately so it cannot be confused with ORACLE, ARGUS, PARALLAX, DREAMSTATE, or ML.

## Edge gate

Ψ returns `NO_EDGE` unless evidence requirements pass: finite latent-pressure magnitude, confidence-weighted coverage, sufficient future-space collapse, a warmed leader graph, microstructure evidence when broader coverage is weak, and forced-consensus confirmation when broader evidence is weak.

Passing the research gate can produce `LONG_BIAS` or `SHORT_BIAS`, but those labels cannot place, size, or authorize an order.

## Trader interface

The first-class **ICARUS Ψ** tab shows latent pressure, component provenance, evidence coverage, elasticity, information-wave novelty, synthetic price, residual-identifiability status, future entropy/collapse, future clusters, leaders, phase boundary/event horizon, forced consensus, hidden-state hypotheses, market shadows, explicit `NO_EDGE` blockers, and data health.

The panel polls only while the Ψ tab is active.