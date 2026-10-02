# ICARUS Research and Architecture Knowledge Base

This subtree is the durable home for loop-generated research, audits, architecture,
decisions, and handoffs that are too large to keep as root-level one-off notes.

## Current state
ICARUS now has a persistent research-only Continuous Learning Fabric in addition
to the existing empirical qualification and architecture research planes.

### Canonical status
- Pipeline policy: `icarus-control-v1`
- Schema: `icarus-pipeline-v1`
- Continuous learning: **installed and background-capable**
- Historical replay: **installed; runtime data remains outside Git**
- Shadow recalibration: **chronological, label/revision scoped, overlap-aware**
- Calibrator drift retirement: **installed**
- Realized trade experience: **closure-time configuration scoped when provenance is available**
- Execution authorization: `false`
- Production decision authorization: `false`
- Last knowledge verification: 2026-10-02 against `main@e84385f287ce0d6e1ea6faddc4aef882c739629c`

Review this status when the learning fabric, qualification gates, or execution
authority contracts change.

## Artifact map
- `status/` — current pipeline and resume state.
- `research/` — progressive S3 edge registry and attempt accounting.
- `audits/` — direct repository/source evidence and verified defects.
- `decisions/` — architectural rulings and rejected shortcuts.
- `providers/` — external data capability/entitlement matrix.
- `handoffs/` — current loop state and future loop intake.
- `../superpowers/specs/` — approved architecture specifications.
- `../superpowers/plans/` — implementation plans derived from approved specs.
- [`CONTINUOUS_LEARNING.md`](CONTINUOUS_LEARNING.md) — durable replay, prediction/outcome maturation, shadow calibration, drift retirement, and realized-experience architecture.

## Core doctrine
```
Observable market state
    != estimator
    != predictive relationship
    != incremental alpha
    != executable edge
```

A composite of existing evidence is not a new independent vote.
A correlation is not a lead/lag result.
A backtest profit is not proof.
A connected data provider is not automatic trading authority.
