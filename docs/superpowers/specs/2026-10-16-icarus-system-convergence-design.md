# ICARUS System Convergence Design

## Objective

Converge the currently fragmented ICARUS runtime into one evidence-backed, fail-closed capability graph so that every agent and subsystem can answer the same questions about an asset: what it is, where its data comes from, whether its corpus is qualified, whether Brain can consume its evidence, whether an exact dated paper contract can be resolved, what risk/authorization applies, and what the dashboard may expose.

This design preserves the existing owner directive that live execution is disabled. The target execution boundary is research, replay, simulated paper, and broker-paper qualification only.

## Current verified gap

`icarus_engine.assets.REGISTRY` and `icarus_futures.contracts.SPECS` are independent authorities. The canonical runtime currently contains 16 futures roots while the Engine satellite contains the owner-directed 32-root macro universe. The execution table contains only 12 roots. That makes registration, data availability, dashboard visibility, and executable contract qualification divergent states.

The recovered 32-root futures target is:

`NQ MNQ ES MES YM MYM RTY M2K GC MGC SI SIL PL PA HG MHG CL MCL NG MNG 6E M6E 6J MJY 6B M6B 6A M6A ZN ZB BTCF MBT`.

## Architecture

### 1. Canonical futures product catalog

Create `icarus_engine/futures_catalog.py` as the sole typed authority for futures identity and economics. Each product record owns canonical root, name, continuous provider identity, TradingView identity, exchange, asset class, calendar/session/group, tick size, point value, full-size parent, full-equivalent ratio, listing cycle, and roll model.

`icarus_engine.assets` derives futures `AssetSpec` objects from this catalog. `icarus_futures.contracts` derives execution `ContractSpec` objects from the same catalog. No second hand-maintained tick/multiplier/exchange table is permitted.

Research identities remain continuous-only and fail closed for dated symbols. Execution resolves continuous identities to exact dated contracts; continuous pseudo-contracts are never sent as broker orders.

### 2. Contract-resolution models

The resolver supports explicit product families rather than pretending equity and metals calendars apply to every future:

- equity index: quarterly HMUZ, roll Monday before third-Friday expiry;
- precious/base metals: product-specific cycle with notice-aware roll model;
- energy: monthly cycle with product-specific expiry/roll metadata;
- FX: quarterly HMUZ with currency-futures expiry/roll metadata;
- Treasury: quarterly HMUZ with Treasury expiry/roll metadata;
- CME crypto: monthly cycle with cash-settled expiry/roll metadata.

Where exact expiry/roll behavior is not yet independently qualified, the catalog exposes the product but execution qualification must remain false rather than guessing.

### 3. Canonical capability index

Create `icarus_engine/system_index.py`. It compiles a schema-versioned capability record from runtime sources, not chat memory. At minimum each asset record exposes:

- identity: root, continuous/provider/TV identities, exchange, asset class;
- market data: configured source and current qualification state when available;
- execution: ContractSpec presence, resolver model, paper authorization, live authorization;
- dashboard eligibility and explicit blockers;
- corpus/Brain integration hooks and provenance status;
- integrity hash over the deterministic index payload.

A human-readable Markdown projection and deterministic JSON projection must be derivable from the same object.

### 4. Asset-centric paper command-center state

Create `icarus_engine/asset_command_center.py` as backend state only; do not touch currently-colliding UI files. One typed record per futures root reports the exact reasons an asset is or is not paper-tradeable. A root is paper-tradeable only if registration, execution specification, dated-contract resolution support, paper execution authorization, risk controls, and state/journal capability are all present.

The backend record includes asset economics, authorization state, execution blockers, and placeholders for runtime statistics. UI work consumes this state later; no dashboard contains independent order logic.

### 5. Brain evidence provenance and regime contract

Create `icarus_engine/brain_evidence.py` to standardize provenance-bearing evidence. Raw provider/corpus values do not directly become decisions. Evidence records carry event time, retrieval time, source/provider, source/corpus hash, feature revision, regime label/confidence, drift/OOD state, unresolved validation gates, and execution authorization.

Evidence validation fails closed when required provenance is missing or when a required source is stale/degraded. Regime snapshots must be decision-time causal: their `observed_at` cannot be after the decision timestamp.

## Safety invariants

1. Unknown or dated futures-looking symbols never fall through to spot crypto.
2. Continuous research identity and dated execution identity are separate types/paths.
3. Tick value equals tick size × point value within floating tolerance for every execution-qualified product.
4. Micro products retain their own economics; no micro may inherit full-size multiplier.
5. Missing provider/corpus evidence is represented as a blocker, never silently replaced by zero/neutral data.
6. Current owner policy keeps live authorization false everywhere.
7. Existing command-center UI collision paths (`icarus_engine/dashboard.html`, `command-centers-ui.js`, `experience-ui.css`, `experience-ui.js`, `world-*.js`) are out of scope for this branch.

## Testing and acceptance

The branch is acceptable only when exact-head CI proves:

- all 32 target roots derive consistently into canonical runtime identities;
- every catalog record has unique canonical/provider/TV identities;
- micro/full relationships and economics are valid;
- unknown/dated-symbol fail-closed tests remain green;
- execution coverage is explicit: qualified products resolve deterministically and unqualified products expose a typed blocker instead of guessing;
- system-index output is deterministic and integrity-hashed;
- asset command-center state never marks a product paper-tradeable unless all gates pass;
- Brain evidence rejects future-dated regime context and missing/stale required provenance;
- existing `tests_engine` regression suite remains green;
- no live-execution path is enabled.

## Delivery strategy

This is implemented in independent, reviewable slices on `atlas/icarus-system-convergence-20261016`: futures authority first, then capability index, backend asset state, then Brain provenance. UI rendering is deferred until the active dashboard collision clears; the backend contract is completed now so that rendering becomes a consumer-only change.
