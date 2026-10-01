# ICARUS Integration Index

Status: integration staging package  
Branch: `integration/chatgpt-icarus-fabric-2026-09-24`  
Purpose: consolidate the architecture, findings, control-plane contracts, evidence rules, and agent handoff material produced in the ChatGPT ICARUS architecture pass without changing production trading behavior.

## Start here

1. [Architecture + findings](docs/icarus/ARCHITECTURE_AND_FINDINGS.md)
2. [Control plane + assurance](docs/icarus/CONTROL_PLANE_AND_ASSURANCE.md)
3. [Agent integration contract](docs/icarus/AGENT_INTEGRATION.md)
4. [Integration workspace](integration/README.md)
5. [Machine-readable mesh](integration/ICARUS_MESH.json)
6. [Handoff template](integration/templates/HANDOFF_TEMPLATE.json)
7. Schemas:
   - [Control manifest](integration/schemas/control-manifest.schema.json)
   - [Evidence record](integration/schemas/evidence-record.schema.json)
   - [Agent handoff](integration/schemas/handoff.schema.json)

## Scope boundary

This package records material actually derived in the current ChatGPT architecture pass and direct inspection of the canonical `reppiks490/Icarus` repository. It does **not** claim to contain unseen work from other chats, agents, branches, local files, or repositories.

No strategy threshold, execution rule, broker route, sizing rule, Pine behavior, or production configuration is modified by this package.

## Repository facts observed during this pass

- Canonical repository: `reppiks490/Icarus`
- Default branch: `main`
- Code search indexing: unavailable at inspection time; negative code-search conclusions must not be treated as exhaustive.
- `state.json` currently contains only `{}`.
- `instruction.txt` asks another process to inspect 760 CSV files and write mathematical values directly into `state.json`; those CSVs were not available to this ChatGPT pass, so no values were fabricated.
- `pyproject.toml` exposes `icarus-engine`, `icarus-bridge`, `icarus-plant`, and `icarus-train`; optional ML dependency includes XGBoost.
- The README separates TradingView/Alpaca-paper alert handling from the Python engine and documents explicit data/parity limitations.

## Existing adjacent repositories discovered

- `reppiks490/Icarus-engine`
- `reppiks490/icarus-owner-actions`
- `reppiks490/icarus-causal-router`
- `reppiks490/icarus-csv-evidence-lab`

These are declared as **candidate satellites**, not trusted modules. Integration requires a valid handoff manifest and revision-bound validation.

## Primary architectural decision

ICARUS should scale through a **layered capability fabric**, not by directly injecting every model/provider into strategy execution. External providers and agents produce evidence; a protected decision core consumes only canonical, validated state through explicit authority gates.

## Non-negotiable invariants

- Research surfaces do not directly alter live execution.
- Uncertainty, stale data, missing data, conflicts, or provenance gaps can only preserve or reduce authority.
- Cross-revision evidence cannot silently authorize a different code revision.
- Synthetic or reconstructed data must never be presented as empirical market evidence.
- Composite/model slots must not be labeled as trained estimators without training artifacts.
- Test expectations must not be invented to make CI pass.
- S4 implementation work does not self-certify S5 integration readiness.
- Default-disabled research controls must preserve existing production behavior.
