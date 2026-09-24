# ICARUS Loop Integration Index

This is the canonical entry point for research/architecture handoffs produced by the ICARUS loop work.

## Current integration branch
- Branch: `icarus-loop-integration-2026-09-24`
- Baseline main revision: `007e70189945b8e112904cf92b2b1a12e43792d6`
- Strategy/runtime mutation in this handoff: **none**
- `execution_authorized=false`

## Read first
1. [Current state](docs/icarus/status/CURRENT_STATE.md)
2. [S3 empirical edge registry](docs/icarus/research/S3_EMPIRICAL_EDGE_REGISTRY.md)
3. [Direct repository evidence](docs/icarus/audits/REPO_EVIDENCE_2026-09-24.md)
4. [S4 curve research design](docs/superpowers/specs/2026-09-24-icarus-curve-research-design.md)
5. [S4 implementation plan](docs/superpowers/plans/2026-09-24-icarus-curve-research.md)
6. [Architectural rulings](docs/icarus/decisions/ARCHITECTURAL_RULINGS_2026-09-24.md)
7. [Current loop handoff](docs/icarus/handoffs/CURRENT_LOOP_HANDOFF_2026-09-24.md)
8. [Future loop intake protocol](docs/icarus/handoffs/INBOX_PROTOCOL.md)

## Integration rule for the other loops
Each loop should add a dated handoff under `docs/icarus/handoffs/inbox/` and update
`docs/icarus/handoffs/INBOX_PROTOCOL.md` only if the intake contract itself changes.
Do not overwrite another loop's evidence. Conflicts are recorded explicitly and resolved
into canonical documents only after provenance/revision compatibility is checked.

## Authority hierarchy
1. Pinned repository code and tests.
2. Current canonical ICARUS specs/registries in this branch.
3. Direct primary/exchange/official evidence.
4. Reproducible independent research.
5. Secondary summaries.
6. Hypotheses.

Uncertainty, source failure, or unresolved conflict can only preserve or reduce authority.
They may never increase trading authority.
