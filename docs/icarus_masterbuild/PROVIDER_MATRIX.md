# Provider Capability Matrix

This file records reconnaissance state, not permanent vendor capability.

## Required provider-state model

```text
AVAILABLE
DEGRADED
AUTH_REQUIRED
ENTITLEMENT_BLOCKED
QUOTA_BLOCKED
NETWORK_RESTRICTED
STALE
UNSUPPORTED_INSTRUMENT
UNSUPPORTED_GRANULARITY
PROVENANCE_FAILED
UNKNOWN
```

## Observed routes

| Provider | Domain | 2026-09-24 observed state | Use in ICARUS |
|---|---|---|---|
| Bigdata.com | Cross-asset market snapshot, macro calendar | AVAILABLE | Macro/event context; cross-asset research; source must remain identified. |
| Bybit | BTC public market data | AVAILABLE | Crypto price, funding, order-book research. |
| StackerScan | Precious-metal spot | AVAILABLE | Independent spot reference; not CME futures truth. |
| U.S. Gold Bureau | Precious-metal spot | NETWORK_RESTRICTED | Optional cross-check only after auth/network state resolves. |
| Massive | Futures | ENTITLEMENT_BLOCKED | Do not route jobs requiring unavailable tier. |
| FMP direct commodity route | Commodities | ENTITLEMENT_BLOCKED on tested route | Treat endpoint entitlement independently from other FMP-backed surfaces. |
| Scite | Scientific literature | QUOTA_BLOCKED | Alternate to primary/academic web sources until quota resets. |
| GitHub | Repository/CI | AVAILABLE | Source of truth for code, tests, commits, workflow state. |
| Figma | Design | AVAILABLE | UI/design artifact integration; never an empirical trading evidence source. |
| Runway | Media generation | CONNECTED with capacity constraint observed | Non-core presentation capability only. |

## Routing contract

A consumer requests a `CapabilityRequest`:

```json
{
  "asset_class": "futures",
  "instrument": "GC",
  "data_kind": "trades",
  "min_granularity": "tick",
  "point_in_time": true,
  "max_age_seconds": 2,
  "allow_proxy": false
}
```

The router must return either:

1. one or more providers satisfying the contract, plus provenance/freshness metadata; or
2. an explicit blocked/degraded reason.

It must never substitute a lower-fidelity proxy without the caller explicitly allowing that substitution.

## Cross-source reconciliation

When two providers purport to represent the same observable:

- normalize instrument/unit/timezone
- align timestamps
- compare freshness
- compare expected market convention
- record disagreement
- never average incompatible semantics blindly
- promote a consensus only when the underlying definitions are compatible
