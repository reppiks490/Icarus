# OMNIGENESIS ∞ — phases 1–3 implementation (research only)

This is a real, narrowly bounded foundation for the larger OMNIGENESIS roadmap.
It **does not** train AI agents, predict the future, automatically modify
ICARUS's strategies, or grant broker permissions.

## Current capabilities

- Exact prime successor and historical first-event primitives (phase 1).
- Strict provenance and as-of feature/label timestamps (phase 1).
- Deterministic, bounded, safe hypothesis search (phase 2).
- 60/20/20 chronological train/validation/holdout, with label-maturity purges
  before validation and test windows (phase 2).
- Train-only candidate parameter generation, validation-only model selection,
  holdout-only final comparison, explicit trial count (phase 2).
- Immutable, content-addressed SQLite research artifacts, no raw market data
  persistence and no access to live orders (phase 3).
- Read-only derived status and CLI (phase 3).

## CLI

Use Python 3.10+ from the repository root:

    python -m icarus_engine.omnigenesis prime 100
    python -m icarus_engine.omnigenesis run ./example_dataset.json --root .
    python -m icarus_engine.omnigenesis status --root .
    python -m pytest tests_engine/test_omnigenesis.py -q

The JSON dataset must contain exactly:

- dataset_id: unique 1–128 char identifier
- source_commit: exact lowercase 40-character source Git commit SHA
- records: 30–50,000 records of **one** asset, chronological after sorting

Each record requires precisely:

    {
      "record_id": "event-001",
      "asset": "NQ",
      "decision_at": "2026-01-01T14:00:00Z",
      "observed_at": "2026-01-01T13:59:59Z",
      "received_at": "2026-01-01T14:00:00Z",
      "label_resolved_at": "2026-01-01T14:05:00Z",
      "feature": 0.25,
      "outcome": true,
      "source_record_id": "databento:record-001"
    }

`feature` is strictly one floating-point as-of observable; `outcome` is a
**historically resolved** yes/no target. Producing causally valid event labels
from raw market tapes, contract-roll and cost handling remain upstream tasks.
Do **not** put feature values calculated from the future into this field.

Output `EXPLORATORY` means only the held-out Brier score improved on this
one dataset. It does not mean a verified trading edge or a deployable signal.
Results are never auto-promoted. No direct REST endpoint or dashboard binding
exists yet; operators can inspect the CLI status output.

## Guardrails

- No `eval`, arbitrary code, internet, broker, production route, order
  mutation, position mutation, auto-promotion, scheduling, or background loops.
- Strict event timestamps and source identity; fail closed on violations.
- No future observations for model input at an as-of decision.
- Validation and holdout do not tune the final model after selection.
- Existing APEX, DAEDALUS and DREAMSTATE gates remain mandatory for any
  future cross-subsystem qualification.
- Offline data may contain overlapping labels: use properly embargoed,
  non-overlapping episodes and independent market datasets for validation.
- Input source and dataset provenance should be independently audited.

## Next phases — not implemented in this branch

4. Evidence adapter: ingest source-verified APEX/NEXUS and CL results, typed
   interoperability, calendar-safe data extraction, asset-specific cost models.
5. Simulation foundry: exchange order books, agents, liquidity/impact,
   scenario generation and replay against observed data.
6. Program synthesis: typed safe DSL and formally checked strategy-state
   automata with independently verified counterexamples.
7. Evolution control: bounded proposal workers, resource accounting,
   independent approval, explicit sandboxing, no autonomous deployment.
8. Observability: authenticated read-only MCP/HTTP contracts and motion-driven
   dashboard with *real* telemetry, not fabricated research activity.
9. Independent validation: cross-market forwarding, selection-bias controls,
   OOD/drift, failure injection, CI, long-run soak testing and explicit release.
