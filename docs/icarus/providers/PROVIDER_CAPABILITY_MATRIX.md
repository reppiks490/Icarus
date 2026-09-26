# ICARUS Provider Capability Matrix — 2026-09-24

This matrix records what was actually observed during the current research cycle.
Connection status is not authority to trade, and a current snapshot is not historical evidence.

| Provider | Observed capability | Current limitation | Research use |
|---|---|---|---|
| Massive | Point-in-time futures contract metadata; explicit GC maturities; historical contract OHLC/settlements; quote endpoint exists | Connected plan did not entitle the requested live futures snapshot | Primary candidate for explicit contract/curve reconstruction |
| FMP | Historical U.S. Treasury yield curve by tenor | Treasury yields are only a financing proxy; not gold lease/storage/convenience yield | Candidate financing input after normalization |
| Twelve Data | Authenticated; XAU/USD spot quote/history capability observed | Spot convention/timestamp semantics must be preserved | Independent spot source / cross-check |
| StackerScan | Current gold/silver/copper spot observations | Current observations alone do not create historical backtest data | Independent spot cross-check |
| U.S. Gold Bureau | Connector exists | Request blocked by IP allowlist during this cycle | Unavailable until access issue resolved |
| Bybit | Current BTCUSDT perpetual funding observable | Historical point-in-time funding series not established in this cycle | Separate crypto-funding research only |
| Scite | Core carry literature previously verified | Monthly MCP usage limit reached later in the cycle | Literature verification resumes when quota permits |
| DataBlue | Public-source discovery worked; CME results found | Search/scrape layer, not primary market truth | Discovery/primary-source routing |
| Zacks | GLD/news data available | Secondary/editorial market evidence; not curve data | Context only |
| Blockscout | Blockchain research connection available | Not relevant to GC curve construction | Separate crypto/on-chain research only |
| Runway | Creative image workspace connected | No quantitative-market evidentiary role | Excluded from research authority |
| Figma | Authenticated design workspace | No quantitative-market evidentiary role | Documentation/design only |

## Source-state rule
Provider health and provider capability are separate.

Example states:
```
AVAILABLE
PARTIAL
NOT_ENTITLED
RATE_LIMITED
AUTH_FAILED
NETWORK_RESTRICTED
STALE
SEMANTIC_MISMATCH
UNVERIFIED
```

A provider failure can lower `DATA_SUFFICIENCY_STATUS`; it cannot silently
change estimator definition, fallback semantics, or confidence.

## Multi-provider rule
Provider agreement is quality evidence. It is not permission to average incompatible
records. Timestamp, price semantic, units, methodology, and origin must first be compatible.
