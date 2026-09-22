# Unzipped CSV access — Grok (xAI) 2026-09-22

Owner could not reach the six newest batches. **Astra unzips them.**
Repo: `reppiks490/multi-level-csv`.

## The six batches (17:32–17:48Z uploads)

- `Csv first 60.zip`
- `First 60 half.zip`
- `Csv 2nd 60.zip`
- `2nd 60 half.zip`
- `Csv last 57.zip`
- `Last 57 half.zip`

Older zips in that repo (`Full csv candles only`, chart-type, tick/profile) are **not** this command.

## Astra command (do this first)

Needs `git` auth to the private repo (same GitHub account as the owner).

```
cd Icarus
python -m icarus_engine.unzip_batches --fetch
python -m icarus_engine.csv_access --kind candidates
```

Writes:

- `%ICARUS_HOME%/history/unzipped/execution/` — CME/CBOT/COMEX/NYMEX/Coinbase/Bitstamp names
- `%ICARUS_HOME%/history/unzipped/candidates/` — BATS/LSE/BCBA/stocks

Does **not** call `ingest-drop`. Does **not** write `history/NQ_1m.csv`.

If the csv repo is already cloned next to Icarus:

```
python -m icarus_engine.unzip_batches --src ..\multi-level-csv
```

Grok (xAI). Do not rewrite Pulse. Do not trade MBT/SOL/ETHUSD.
