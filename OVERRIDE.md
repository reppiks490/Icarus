# Override — owner 2026-09-22

Astra and Opus may **exceed Grok's spec** when they judge it necessary.
Owner ranks them above Grok on model design, features, hyperparameters, extra pipelines, and audit method.
Grok does not block that. Grok logs it and updates SPEC only if their change should become the new default.

## May override without asking Grok
- FEATURE_KEYS / extra features
- XGB_CLASSIFIER and other model families (more than slot 1)
- Walk-forward fractions, early stop, calibration method
- Train vs inspect order if they have a better reason
- Ranker / regime / failure design
- File layout under `run/` if they document the new path in HANDOFF_LOG.md

How: commit message `Astra: OVERRIDE` or `Opus: OVERRIDE` and a HANDOFF_LOG.md section:
```
OVERRIDE
why:
what changed vs spec.py:
repro:
```

## Still owner-hard (not Grok vanity)
These are the owner's plant, not Grok's ego. Do not override unless the **owner** says so in chat:
- Do not rewrite `pulse.py` / `emulator.py` to hook a model
- `execution_authorized` stays false until the owner arms a broker
- Do not trade MBT, SOL, ETHUSD
- Do not drop BATS/LSE/BCBA into HistoryHub as NQ/ES/YM tape
- Do not commit secrets or scrape TradingView
- Do not bind 0.0.0.0

If an OVERRIDE and an owner-hard rule collide, **owner-hard wins**. Everything else, Astra/Opus win.
