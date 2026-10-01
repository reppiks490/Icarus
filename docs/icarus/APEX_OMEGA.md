# ICARUS APEX Ω

APEX Ω is the research/shadow world-model federation for ICARUS. This document records **installed** behavior only; the full approved architecture and staged implementation plans live under `docs/superpowers/`.

## Installed: Project A — Epistemic Kernel

Project A establishes the truth substrate used by later APEX layers:

- strict evidence kinds: `observed`, `derived`, `reconstructed`, `inferred`, `unavailable`;
- separate UTC observation, receipt, calculation, validity, and as-of clocks;
- content-addressed evidence identity bound to exact source repository/commit/record provenance;
- SQLite WAL persistence at `research/apex.sqlite3`;
- causal historical reads requiring both `observed_at <= as_of` and `received_at <= as_of`;
- corruption quarantine/reporting rather than silent normalization;
- evidence-ancestry DAG with effective independent-family accounting and cycle/missing-dependency failure;
- append-only proof-carrying beliefs with explicit contradictions and falsifiers;
- independence-adjusted confidence and calibration-aware research credibility;
- compact epistemic-kernel state that reports empty/degraded/active truthfully.

## Authority boundary

APEX Project A has no broker, order, sizing, strategy-input, production-decision, or execution authority.

```text
production_decision_authorized=false
execution_authorized=false
```

Those flags are invariants, not suggestions.

## Not installed yet

Participant/CROWDHUNT, force/liquidity, causal/cascade, world/unknown-force, self/conscience/scientific-governor, HTTP/MCP/dashboard integration remain staged in Projects B-F and must not be described as live until their own verification gates pass.
