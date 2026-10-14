# Databento execution cost estimates

ICARUS exposes an authenticated, read-only counterfactual estimate for an
immediate market order against the latest Databento MBP-10 depth snapshot:

```text
POST /admin/execution-cost/estimate
```

The request requires one running asset, a side, an integer contract quantity,
and an operator-supplied fee schedule. Fee values are **per contract per side**
except `per_order`, which is charged once for the estimated side. The fee source
must identify the schedule used; ICARUS does not look up, infer, or invent rates.

Example request (zero values are placeholders, not an actual broker schedule):

```sh
curl -sS -X POST http://127.0.0.1:8791/admin/execution-cost/estimate \
  -H 'Authorization: Bearer YOUR_LOCAL_ADMIN_TOKEN' \
  -H 'Content-Type: application/json' \
  --data '{"asset":"NQ","side":"buy","quantity":2,"fee_schedule":{"broker_per_contract":0,"exchange_per_contract":0,"clearing_per_contract":0,"regulatory_per_contract":0,"other_per_contract":0,"per_order":0,"currency":"USD","source":"Replace with your broker rate card","effective_date":"YYYY-MM-DD"}}'
```

The response separates the supplied fee components from estimated spread cost
and impact across the displayed top-ten levels. It reports the latest book
event and receive timestamps, the estimated sweep VWAP, and any requested
contracts left unpriced because the displayed book was too shallow. It also
summarizes slippage percentiles across the latest 1,000 MBP-10 updates returned
by the feed. ICARUS does not extrapolate the remaining quantity.

To compare actual fills, add an optional `fills` array to the request. Each fill
needs a Databento-clock-compatible epoch nanosecond timestamp, side, quantity,
and price; `actual_fee` and `actual_fee_currency` are optional. Example shape:

```json
{"fill_id":"paper-17","timestamp_ns":1791986400123456789,"side":"buy","quantity":1,"price":25001.25,"actual_fee":0,"actual_fee_currency":"USD"}
```

For each fill, the endpoint uses the latest captured book whose Databento
receive timestamp is at or before the fill timestamp. It reports realized
fill-to-preceding-book-midpoint cost and, when displayed depth covers the entire quantity, compares
the fill with a same-snapshot book sweep. Fills without a preceding quote or a
usable quote are labeled and left unmatched; no quote is fabricated.

## Interpretation limits

- This is a static book sweep at one Databento snapshot. It is a what-if estimate,
  not a queue-aware fill simulation, a realized fill, or a broker invoice.
- It does not model order arrival latency, queue priority, hidden liquidity,
  cancellations, routing, market response, or later book movement.
- The one-side snapshot cannot establish round-trip slippage. The response's
  round-trip fee value assumes two orders of the same filled quantity under the
  same supplied schedule.
- The fee schedule is accepted as supplied. Its correctness, product mapping,
  account tier, effective date, and currency conversion are not independently
  verified.
- Snapshot percentiles are weighted by received book updates. Updates cluster
  during active trading and are not independent trials or time-weighted
  observations; they describe only the bounded live buffer, not a full history.
- Fill matching assumes the supplied fill timestamp and Databento receive
  timestamps use compatible clocks. Clock offset is not inferred. Actual fill
  records and fee values are operator-supplied and are not independently
  authenticated.
- The estimate never submits, changes, or authorizes an order.

For actual billed fees, reconcile the fee schedule against broker statements and
reconcile the slippage model against timestamped broker fills. Keep the schedule
source and effective date with any saved result.
