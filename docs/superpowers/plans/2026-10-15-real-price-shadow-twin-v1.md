# Real-price shadow twin v1 implementation plan

**Owner:** Codex (RT01)
**Design:** Engine PR #148, `docs/superpowers/specs/2026-10-14-real-price-shadow-twin-design.md`
**Scope:** backend, default-off, read-only paper evidence; no broker/bridge/activation/UI changes.

## Contract

- Keep `Emulator` as the canonical primary emulator and preserve its exact order, state, and fills.
- When explicitly enabled, route `PulseStrategy` emulator mutations through a facade that forwards the same calls to a second emulator. Every strategy-visible read continues to resolve to the primary.
- Advance the shadow only with the corresponding standard OHLC bar and matching timestamp. Missing, malformed, or mismatched bars degrade the shadow and never substitute a synthetic bar.
- Record deterministic intents, link entry fills to the exact shared intent sequence, and expose separately partitioned primary/shadow results with `execution_authorized: false`.
- Report the win/loss/break-even outcome matrix, guarded P&L realization ratios, entry-time warm-up/live attribution, and bar-close-marked drawdown. Do not aggregate per-asset drawdown as portfolio drawdown without synchronized marks.
- Runtime/admin cancellation and flatten paths must not leave the shadow reporting a valid comparison when they mutate only the primary.
- Keep UI work and dashboard aesthetic files outside this package.

## Sequence

1. Add focused tests for the facade: primary-only reads, mirrored mutators, real-bar timestamp validation, closed-trade pairing, and fail isolation.
2. Implement `icarus_engine/shadow_twin.py` with explicit emulator mutation methods and deterministic summary.
3. Add an opt-in `RunnerConfig`/`Portfolio` setting and CLI switch; default remains off.
4. Wire the facade into `AssetRunner` bar processing, passing the standard bar alongside the primary fill bar; add a per-asset read-only evidence field.
5. Cover runtime order behavior with deterministic fixtures; run focused and relevant existing suites.
6. Review exact diff and tests, then push a feature branch and open a draft PR for independent review. Do not merge until exact-head CI and review are green.

## Acceptance

- Default-off path produces the existing emulator type and does not allocate a second emulator.
- With the feature on, primary order/fill/trade/state outputs match a feature-off replay on the same deterministic fixture.
- Twin consumes only finite standard bars with the same timestamp; no fallback or shadow exception can alter primary behavior.
- The public summary labels synthetic/reference versus real-price shadow evidence distinctly and never grants execution authority.
- Focused tests and relevant runtime/emulator regression suites pass.

## Known limits for v1

This slice reports order intents, intent-linked entry fills and price deltas, paired closed-trade episodes, aggregate P&L/outcome comparison, and unmatched pieces. Drawdown is sampled only at paired bar closes and can understate intrabar risk; MAE/MFE analysis, exit-fill attribution, synchronized cross-asset portfolio drawdown, broker realization, and strategy qualification remain follow-up work before broad interpretation or live enablement.
