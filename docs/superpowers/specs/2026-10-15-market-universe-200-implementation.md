# A200 catalog implementation and current readiness

Date: 2026-10-15  
Branch: `codex/market-universe-catalog-200`  
Contract: `2026-10-15-market-universe-200-contract.md`

## Catalog delivered

The checked-in catalog contains 200 distinct US-listed common stock, ordinary share, and depositary receipt listings from Nasdaq, NYSE, and NYSE American's public stock screener. The builder requests market-cap ordering, selects from the screener-reported values, discards those values, and records response hashes plus source retrieval metadata. This is a hash-anchored snapshot, not an independently reproducible ranking: raw source responses and market-cap values are not retained. The anomalous SPCX record is explicitly quarantined and unsupported security classes such as preferred shares, warrants, and units are excluded.

Each row has a provisional exchange-plus-symbol listing identity, a candidate Yahoo symbol mapping, an explicit instrument type, and unknown fields where the source snapshot does not establish tick size, share/point value, corporate-action treatment, terms, entitlements, or historical/live bar quality. Provider mappings have not been probed. All 200 are `pulse_enabled=false` and `strategy_qualified=false`.

## Connection state

The engine exposes the catalog at `GET /api/market-universe` and in the Market Data dashboard. The API reports 200 catalogued and zero source-connected, historical-qualified, live-qualified, Pulse-enabled, or strategy-qualified entries. It has no feed or broker side effects and does not change the existing runtime asset registry.

Existing registered-asset historical warm-up now records a bounded per-run receipt history with provider, expected/observed symbol, interval, window, timestamps, row count, checksum, alignment, and observed gap count. Receipt identity or entitlement uncertainty remains visible; session qualification is unknown and therefore no batch is counted as A200-qualified. These receipts do not establish connectivity for the 200 catalog candidates.

This is not a claim that 200 assets are fully connected. Connection requires confirmed provider mappings and account entitlements, receipt-validated bars, execution-critical metadata, and the acceptance gates in the A200 contract. Those steps remain pending the source and entitlement evidence.

## Regeneration

Run `python tools/build_equity_catalog.py --limit 200`. The builder performs read-only GET requests to the public Nasdaq screener endpoints and writes no secrets or raw price/market-cap values. Review the diff before replacing a published snapshot because constituents and source response digests can change.
