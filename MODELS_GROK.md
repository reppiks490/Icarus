# Models — Grok (xAI) 2026-09-22

**Frozen numbers live in `SPEC.md` and `icarus_engine/spec.py`.** This file is the why.
Logit = slot 0 baseline. Astra builds slot 1 XGB with **exactly** `XGB_CLASSIFIER` in spec.py.
Do not change max_depth/eta/seed without a Grok spec commit.

Slots 2–4 as in SPEC.md. Swap is a JSON file, not a Pulse hook.
Ignore MBT SOL ETHUSD. One family per file. No shuffle.
