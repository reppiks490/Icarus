# ICARUS Empirical Qualification Lane

This file is the top-level entry point for the ICARUS empirical-validity, evidence-integrity, and model-qualification lane.

**Branch:** `icarus-empirical-qualification-handoff-20260924`  
**Repository:** `reppiks490/Icarus`  
**Execution authority:** `false`

Read in this order:

1. [Lane README](docs/empirical_qualification/README.md)
2. [Current State](docs/empirical_qualification/CURRENT_STATE.md)
3. [Master Worklog](docs/empirical_qualification/MASTER_WORKLOG.md)
4. [Architecture](docs/empirical_qualification/ARCHITECTURE.md)
5. [Blocker Matrix](docs/empirical_qualification/BLOCKER_MATRIX.md)
6. [SOURCE + DATA + TIME Contract](docs/empirical_qualification/SOURCE_DATA_TIME.md)
7. [Model / Economics / Robustness Contract](docs/empirical_qualification/MODEL_ECONOMICS_ROBUSTNESS.md)
8. [TDD Test Plan](docs/empirical_qualification/TEST_PLAN.md)
9. [Implementation Sequence](docs/empirical_qualification/IMPLEMENTATION_SEQUENCE.md)
10. [Agent Handoff](docs/empirical_qualification/AGENT_HANDOFF.md)
11. [Machine-readable gates](docs/empirical_qualification/qualification_gates.json)

## Lane purpose

This lane determines whether ICARUS evidence and model outputs are scientifically defensible before any subsystem is allowed to gain authority.

It does **not** own Pulse strategy logic, broker execution, live-order authorization, UI, or unrelated infrastructure.

The frozen qualification chain is:

`SOURCE -> DATA -> TIME -> BASELINE -> XGB -> ECONOMICS -> ROBUSTNESS`

Any failed upstream gate forces downstream authority to zero.

Do not skip a gate because a downstream backtest appears profitable.
