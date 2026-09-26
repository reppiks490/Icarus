# Findings Ledger

Status vocabulary:

- **VERIFIED** — directly observed in repository/tool output during this cycle.
- **SUPPORTED** — strong architecture conclusion derived from verified evidence.
- **BLOCKED_EXTERNAL** — external capability could not be exercised because of quota, entitlement, auth, or provider restriction.
- **NOT_CLAIMED** — deliberately not asserted because evidence is insufficient.
- **TRANSIENT** — time-sensitive provider state; re-check before relying on it.

## Repository findings

| ID | Status | Finding |
|---|---|---|
| F-001 | VERIFIED | Current baseline inspected at commit `007e70189945b8e112904cf92b2b1a12e43792d6`. |
| F-002 | VERIFIED | `icarus_plant` defines `--root` as a global parser option; CI passed it after the `setup` subcommand. |
| F-003 | VERIFIED | Core engine tests had passed in the previously inspected failing CI run; the overall run failed at the plant/setup invocation rather than an engine-test assertion. |
| F-004 | VERIFIED | Research code contains train/validation/holdout separation and holdout-consumption controls. |
| F-005 | VERIFIED | Frozen replay/provenance mechanisms and source/config/data fingerprints exist. |
| F-006 | VERIFIED | Live/paper/activation boundaries and execution safety controls exist. |
| F-007 | VERIFIED | Existing microstructure code avoids fabricating quote-book states from trade-only inputs. |
| F-008 | SUPPORTED | Statistical governance is stronger than typical retail research but still needs explicit multiple-testing corrections and experiment-attempt accounting. |
| F-009 | SUPPORTED | Execution/reconciliation and production venue state are the largest maturity gap relative to institutional systems. |
| F-010 | SUPPORTED | Provider capability/entitlement discovery should be a first-class contract because live data connectors expose materially different access/failure modes. |

## Audit-integrity finding

| ID | Status | Finding |
|---|---|---|
| A-001 | SUPPORTED | A local hash chain improves edit/delete detection but does not, by itself, prevent privileged truncation to an older valid prefix or private forks. Independent/witnessed anchoring or external checkpoints are required for stronger tamper evidence. |

## External-provider observations — 2026-09-24

These are **TRANSIENT** and must not be treated as permanent provider guarantees.

| Provider | State observed | Architectural implication |
|---|---|---|
| Bigdata.com | Usable market tearsheet and economic-calendar data returned. | Useful macro/cross-asset input, but preserve provider/source timestamps and provenance. |
| Bybit | BTC price/funding/order-book routes returned usable public data. | Crypto microstructure/funding can be validated independently from futures pathways. |
| StackerScan | Precious-metals spot route returned usable data. | Can serve as a cross-source metal reference, not an exchange-futures substitute. |
| U.S. Gold Bureau | BLOCKED_EXTERNAL: IP authorization restriction observed. | Auth/network restrictions belong in capability discovery, not silent retries. |
| Massive | BLOCKED_EXTERNAL: futures snapshot entitlement/tier restriction observed. | Entitlement-aware routing is mandatory. |
| FMP direct commodity path | BLOCKED_EXTERNAL: plan restriction observed. | Provider product surfaces may have different entitlements; track per-endpoint capability. |
| Scite | BLOCKED_EXTERNAL: MCP quota exhausted until next quota window. | Literature evidence path must expose quota state and allow alternate primary-source route. |
| Runway | Connected/authenticated during reconnaissance; media capacity was constrained. | Do not spend credits or make media generation part of core quant validity. |
| Figma | Connected/authenticated during reconnaissance. | Useful for interface/design artifacts; not a trading-evidence authority. |

## Explicit non-claims

- No percentile ranking of the user or ICARUS versus all professional quants is claimed.
- No claim of production alpha, live Sharpe, capacity, or institutional-grade execution is made.
- No provider that was blocked is treated as unavailable permanently.
- No research mechanism is promoted solely because it is mathematically complex.
