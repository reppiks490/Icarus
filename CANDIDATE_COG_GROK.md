# Candidate cog — Grok (xAI) — 2026-09-22

Source zips: `reppiks490/multi-level-csv` (six uploads 17:32–17:48Z, 177 CSVs).
Do **not** drop these in `history/drop/`. FileFeed / HistoryHub stay futures+spot in REGISTRY only.

## Split

| Cluster execution | Candidates | Why |
|---|---|---|
| NQ | AAPL MSFT GOOGL TSLA AMD ORCL INTC MAG7 TSMC | Nasdaq weight / semis |
| ES | JNJ PFE BRK.B XOM JPM | S&P breadth |
| YM | CAT | Dow industrials |

## Opus now

Clock-join candidate OHLC onto `history/{NQ|ES|YM}_{tf}.csv`. Score return-sign agreement, Tide vs Pulse side, RS vs cluster. Write `audit/{CAND}__vs__{FUT}_{tf}.json`. Kill series with <200 overlap or null Tide.

## Astra after ML exists

Same join. Features on candidates. Labels from Pulse/emulator on the **future**. Per-cluster walk-forward. No CME multiplier on stocks. No Renko mixed into clock join.

## Plant

`ingest-drop` still only `CME_*` `CBOT_*` `COMEX_*` `NYMEX_*` `COINBASE` `BITSTAMP`. `BATS_*` is a candidate cog.

Grok (xAI). Do not rewrite Pulse.
