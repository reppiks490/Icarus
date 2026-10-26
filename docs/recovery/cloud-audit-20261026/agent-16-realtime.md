# Real-time dataset catalog: incremental capabilities

Local assessment; endpoints and entitlements unverified.

Icarus already implements Coinbase REST candles/trades, Kraken minute candles, Yahoo/FMP history, local CSV replay, and optional Databento GLBX.MDP3 OHLCV/trades/MBP-10/MBO (`icarus_engine/feeds/`). Re-adding these providers as catalog entries adds no payload capability.

- **First priority: Coinbase WebSocket L2.** The catalog explicitly links order-book streaming. Add a venue-specific snapshot/update collector alongside existing Coinbase trades; retain instrument identity, event/receipt timestamps, reconnect boundaries, and book integrity status. This supplies free spot-crypto depth absent from the current REST adapters.
- **Second: Binance spot depth.** Adds an independent venue’s book, useful for spread/imbalance comparisons. Preserve BTC-USDT versus BTC-USD identity; reconcile snapshot/update identifiers and resynchronize after gaps. Existing crypto OHLC history does not establish usable depth.
- **Third: DexPaprika OHLCV/trades.** Pool/chain-specific DEX history adds coverage beyond centralized feeds. Catalog claims up-to-15-second delay; retain pool address, chain, units and delay. Treat SSE availability and free-tier coverage as unverified.
- **Optional: 0xArchive.** Investigate Hyperliquid/Lighter historical and streaming data for distinct derivatives venues; catalog description alone establishes neither depth schema nor retention.

Free crypto books cannot supply CME futures depth or remove exchange entitlements. Retain Databento’s licensed lane and explicit integrity/budget blockers. Alpaca/Finnhub are already federated provider lanes with recorded access blockers; avoid duplicate collectors. Yahoo’s undocumented stream is low priority.

The README is a discovery index, not market payload. Index values, token tickers and oracle prices do not constitute OHLCV, time-and-sales or executable order books. Require schema-qualified payload receipts before advertising coverage.

Evidence: `/workspace/awesome-public-real-time-datasets/README.md`; `/workspace/publish/Icarus/icarus_engine/feeds/{__init__,events,databento}.py`; `/workspace/publish/Icarus-engine/config/data_ingestion_manifest.json` and `automation_intelligence/sentinel/data_health.json`.
