# ICARUS Canonical Futures Authority — Design

## Purpose

Converge the fragmented futures definitions in `Icarus` and `Icarus-engine` into one canonical authority inside `reppiks490/Icarus`, while preserving ICARUS's fail-closed separation between continuous research identities and exact dated execution identities.

This phase is deliberately paper/shadow only. It must not arm live execution or weaken the existing fixed-paper-account / exact-contract / reconciliation boundaries.

## Success criteria

1. The canonical runtime exposes the complete recovered 32-root futures universe:
   `NQ MNQ ES MES YM MYM RTY M2K GC MGC SI SIL PL PA HG MHG CL MCL NG MNG 6E M6E 6J MJY 6B M6B 6A M6A ZN ZB BTCF MBT`.
2. Every registered futures root has one authoritative product definition containing exchange, asset class, continuous provider identity, TradingView identity, tick size, point value, session/calendar, micro-parent relationship, execution cycle and execution roll policy.
3. `icarus_engine.assets.REGISTRY` and `icarus_futures.contracts.SPECS` are generated from that authority rather than duplicating contract economics.
4. Unknown or dated futures-looking symbols continue to fail closed and are never reinterpreted as spot crypto.
5. Every canonical futures root can resolve a continuous identity to a deterministic dated-paper contract according to its product cycle and roll rule.
6. Contract economics tests enforce `tick_value == tick_size * point_value`, micro/full ratios, and exact parity between analytical and execution registries.
7. Existing continuous-only research behavior remains unchanged.
8. No live order path is added or enabled.

## Architecture

Create `icarus_futures/products.py` as the single typed futures product catalog. `FuturesProduct` owns immutable product economics and identity metadata. `icarus_engine.assets` imports the catalog to construct `AssetSpec` objects. `icarus_futures.contracts` imports the same catalog to construct `ContractSpec` objects and retains the dated-contract resolver.

The product authority distinguishes three identities:

- **Research identity** — canonical ICARUS root plus continuous provider / TradingView symbols.
- **Market-data identity** — provider-specific continuous symbol used for historical/live bars.
- **Execution identity** — exact dated contract produced by the resolver and later qualified by the broker adapter.

A continuous pseudo-contract is never sent directly to a broker.

## Product classes and roll policy

The catalog uses explicit `cycle` and `roll_kind` values rather than inferring them from symbol names.

- Equity indexes: quarterly `HMUZ`, CME equity roll convention.
- Metals: product-specific listed cycles, roll before first notice day.
- Energy: monthly cycle `FGHJKMNQUVXZ`, roll before first notice day.
- FX: quarterly `HMUZ`, expiry/roll based on third-Wednesday family with a conservative business-day lead.
- Treasuries: quarterly `HMUZ`, conservative pre-delivery roll rule.
- CME Bitcoin: monthly cycle `FGHJKMNQUVXZ`, conservative pre-expiry roll rule.

Where ICARUS does not yet model an exchange holiday calendar for a product family, the resolver must remain deterministic and conservative; it must not claim exchange-perfect live tradability from static rules alone. Broker-paper qualification remains a separate gate.

## Canonical products

The canonical catalog ports the owner-directed 32-root universe already present in `Icarus-engine`, while preserving the stricter canonical resolver semantics in `Icarus`.

Micro contracts must keep independent product economics and explicit `micro_of` relationships. A micro must never inherit a parent multiplier.

## Runtime integration

`icarus_engine.assets.REGISTRY` continues to expose `AssetSpec` with continuous-only futures semantics. The added metadata fields are `exchange`, `asset_class`, `micro_of`, and `feed_mode`. Existing call sites that do not use those fields remain source-compatible.

`ALIASES` is generated for every futures root (`ROOT1!`, provider `=F` where applicable) plus existing human aliases. Dated futures remain rejected before alias resolution.

## Execution integration

`icarus_futures.contracts.SPECS` is derived from the product catalog. `ContractSpec.point_value` must equal the catalog point value. `ratio_to_full` is derived from point-value ratios when `micro_of` is present.

The resolver remains paper/shadow infrastructure. Static contract resolution does not itself establish broker entitlement, margin sufficiency, contract details, or live authorization.

## Testing

The first regression test is written before production changes and must fail on current main because only 16 research roots and 12 execution specs exist.

Required tests:

- exact 32-root futures universe in the canonical product catalog;
- parity between product catalog, runtime registry, and execution specs;
- `tick_value == tick_size * point_value` for every product;
- micro products have smaller point value than their parent and correct ratio;
- all products parse via `ROOT1!` and resolve to a dated symbol;
- dated/unknown futures identities fail closed in the runtime registry;
- representative quarterly, monthly, metals, FX, Treasury, and Bitcoin roots resolve deterministically.

## Non-goals for this phase

- No live broker arming.
- No claim that static roll rules supersede broker contract-details validation.
- No changes to strategy logic, Brain promotion, risk sizing, or capital defaults.
- No direct UI redesign. Dashboard expansion consumes this authority in the next phase.
