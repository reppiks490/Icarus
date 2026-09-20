# TradingView parity (engine)

<!-- Grok (xAI) — 2026-09-20. Whole file. Documents Astra's Pine departures so they are not "fixed" by accident. -->

The Python port follows THE PULSE OF ICARUS v3.1 top to bottom. Visuals (§13) and alerts (§14) are omitted. Everything that decides an order is in `icarus_engine/strategy/pulse.py`.

Documented departures (also in module docstrings):

| ID | Topic | Engine behaviour |
|---|---|---|
| A1 | `ta.pivothigh/low` | Ties count as pivots (TV reference manual is undocumented) |
| A2 | `math.max/min` with `na` | Returns `na` (the script's `nz()` guards assume this) |
| A3 / A11 | Heikin Ashi + `request.security` | HA chart + `security_source=chart` → HTF/LTF see HA of that TF (TV). `standard` strips HA |
| A4 | VIX / DXY / TNX `request.security` | Informational in the Pine; **not fetched** here |
| A5 | LTF `lookahead_on` | Historical = first intrabar (backtest default `ltf_intrabar=first`). Live TV uses the last. **Live TV ≠ Icarus backtest** on the 2m/5m failure check |
| A9 | RTH session | 09:30–16:15 ET, 20m at `:10/:30/:50`, last bar is a 5-minute stub |
| Roll | `NQ1!` vs `NQ=F` | Live feed applies TV volume roll on contract tickers; warm-up history is still Yahoo `=F` unless you ingest a `NQ1!` export |
| Fills | Bar Magnifier | Off. `process_orders_on_close = false`. Intrabar path is O→H→L→C or O→L→H→C |
| HA | Tick quantize | Each HA open/close rounded to `mintick` |

## How to check

1. Same symbol, TF, session, chart type, inputs (`icarus-engine import-tv` the Strategy Tester Properties sheet).
2. Strategy Tester → List of Trades → Export.
3. Prefer a TradingView **chart data** dump in `history/` so both sides see the same bars.
4. `icarus-engine parity --asset NQ --tv-csv "List of Trades.csv"`

Fills default to **real** prices, not Heikin Ashi. `--fill-on chart` is TV's "Heikin Ashi bars" mode, for parity only.

Metrics (`icarus_engine/metrics.py`) are checked against a TradingView Performance / Trades / Risk export in `tests_engine/test_metrics.py`.
