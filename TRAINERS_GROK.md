# Trainer families — Grok (xAI) — 2026-09-22

Clock 1m is one trainer. Every other sampling process has its own.

```
python -m icarus_engine.trainers --path FILE --chart-type renko --asset NQ --out run/trainers/NQ_renko.json
```

Does not write Pulse, HistoryHub, or history/*.csv. execution_authorized is always false.

| Family | Index | Label |
|---|---|---|
| clock_minutes / hours / seconds | timestamp | next clock-bar return sign |
| clock_daily / weekly | session | next session return sign |
| renko | brick | next brick direction |
| range | range bar | next range-bar direction |
| tick | N-tick bar | next tick-bar direction |

Tide/MP are features on the underlying family. close_only has no trainer.
Do not concatenate families. Holdout is the last 20% of that file's own order.
