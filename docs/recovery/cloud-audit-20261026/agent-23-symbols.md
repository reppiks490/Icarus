# 23 — FinanceDatabase / symbol interoperability

Local audit evidence (`starred-forked-repository-review-20261026.md:19`) identifies FinanceDatabase as MIT reference/discovery metadata, explicitly not current fundamentals or prices. Its actual catalog was not inspected; no import or download occurred.

Useful future intake: provider-qualified ticker, name, asset type, exchange, country, currency, aliases, source/version/as-of and mapping confidence. Preserve futures tick size, multiplier, micro-parent, continuous-versus-expiring identity and FX base/quote separately; external catalog entries must remain candidates until qualified.

Exact local interoperability findings:

- Futures: `ES` → Yahoo `ES=F` / TradingView `CME_MINI:ES1!`; `MES` stays distinct (point values 50 versus 5). Icarus rejects dated contracts; Engine’s unknown-symbol fallback can reinterpret `ESZ26` as Coinbase `ESZ26-USD`.
- Registry drift: Icarus `futures_catalog.py:138,142,146` uses `COMEX_MINI:MGC1!`, `COMEX_MINI:SIL1!`, PA tick 0.50; Engine `assets.py:82,84,86` uses `COMEX:MGC1!`, `COMEX:SIL1!`, PA tick 0.10.
- FX: `6E=F` / `CME:6E1!` is a futures identity, not EUR/USD spot. Engine `assets.py:141–158` statically maps unknown `EURUSD` to crypto `EUR-USD`; Icarus rejects unregistered FX.
- Crypto: `BTC` → Coinbase `BTC-USD` / `COINBASE:BTCUSD`; `BTCF` → `BTC=F` / `CME:BTC1!`. Both resolvers discard exchange prefixes before alias lookup; namespaces therefore need explicit validation.

No tests or repository changes; only this report was written.
