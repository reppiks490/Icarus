# Unzipped CSV access — Grok (xAI) 2026-09-22

Owner is unzipping the `multi-level-csv` packs. Astra **reads** those files.
Do not `ingest-drop` BATS/LSE/BCBA into HistoryHub.

## Where to put them

Preferred (plant):

```
%ICARUS_HOME%/history/unzipped/execution/     CME_* CBOT_* COMEX_* NYMEX_* COINBASE BITSTAMP
%ICARUS_HOME%/history/unzipped/candidates/    BATS_* LSE_DLY_* BCBA_* MAG7 TSMC stocks
```

Also searched, in order:

1. `ICARUS_CSV_ROOT` (set this if you unzip somewhere else)
2. `ICARUS_HOME/history/unzipped`
3. `ICARUS_HOME/history/drop/candidates` (quarantine from ingest-drop)
4. sibling checkout `../multi-level-csv` next to the Icarus repo

Windows example:

```
set ICARUS_HOME=C:\IcarusHome
set ICARUS_CSV_ROOT=C:\Users\trip\Downloads\csv-unzipped
```

## How Astra lists files

```
python -m icarus_engine.csv_access --kind execution
python -m icarus_engine.csv_access --kind candidates --asset AAPL
python -m icarus_engine.csv_access --kind all --json
```

Execution files may later be ingested with `icarus-plant ingest-drop` **only** if the name is CME/CBOT/COMEX/NYMEX/COINBASE/BITSTAMP.
Candidate files stay in `candidates/` and go to `python -m icarus_engine.audit` after XGB exists.

Grok (xAI). Do not rewrite Pulse.
