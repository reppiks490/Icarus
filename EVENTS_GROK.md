# Event socket for candidate testing — Grok (xAI) 2026-09-22

Opus/Astra may use dated events when scoring candidates. They may **not** scrape news or invent CPI/NFP numbers.

## What moves a candidate score

| Source | How it enters |
|---|---|
| FOMC decision days | Seeded in `icarus_engine/events/calendar.py` (same family as engine inputs) |
| CPI PPI NFP PCE GDP ISM earnings geopol | Owner CSV in `history/events/*.csv` |
| VIX VXN TNX DXY | Already in the catalog — z-score = micro stress |
| Tide / RATE on candidate CSV | Feature, not a headline |
| Bookmap / dark pool / "big business flow" | No tape in repo — do not fake |

## Owner calendar format (`history/events/macro.csv`)

```
ts_or_date,name,kind,scope,surprise
2026-09-17,FOMC,fomc,"rates,equity,metals,dollar",
2026-10-15,CPI,cpi,equity,0.1
2026-10-16,AAPL earnings,earnings,AAPL,
```

`kind`: fomc|cpi|ppi|nfp|pce|gdp|ism|earnings|geopol|other
`scope`: all / rates / equity / metals / dollar / crypto / a symbol
`surprise`: optional actual-minus-consensus. Blank is fine.

## Audit join

On each candidate bar `ts`:
- `event_n`, `fomc`, `cpi`, `nfp`, `any_macro`, `earnings`, `surprise_abs`
- `vix_z`, `tnx_z`, `dxy_z`, `stress` from sensor CSVs
- Tide from the candidate file

Window: 6h before print through 20h after (session + next cash open). Tighten later; do not peek future prints beyond the bar `ts`.

## Candidate rule add-on
A name that fails the quiet-session screen can still stay if it **beats** peers **inside** a macro window (owner: exceeding criteria is accepted). Quiet-session failures without an event stay rejected.

```
python -c "from icarus_engine.events.calendar import load_events; print(len(load_events('.')))"
```
