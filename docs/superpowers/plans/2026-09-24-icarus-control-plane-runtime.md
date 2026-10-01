# ICARUS Repo-Native Control-Plane Runtime — Implementation Plan

**Goal:** Implement the smallest dependency-free verifier that closes the proven S1->S5 handoff gap without touching trading logic.

## Batch 1 — Contracts, canonicalization, validation

Code:
- `icarus_control/__init__.py`
- `icarus_control/canonical.py`
- `icarus_control/validation.py`
- `icarus_control/cli.py`
- `pyproject.toml`

Contracts:
- `docs/icarus-control-plane/contracts/icarus-control-v1.json`
- `docs/icarus-control-plane/contracts/icarus-pipeline-v1.json`

Tests:
- `tests_engine/test_control_plane.py`

Knowledge delta:
- `docs/superpowers/specs/2026-09-24-icarus-control-plane-runtime-design.md`
- this plan
- `docs/icarus-control-plane/README.md`
- `docs/icarus-control-plane/UNIFIED_CYCLE_RUNBOOK.md`
- `MODEL_HANDOFF.md`
- `HANDOFF_LOG.md`

Rules/skills/context/memory:
- no new repository-local skill: the procedure is part of the control-plane runbook.
- no new execution rule beyond existing owner-hard constraints.
- no broker/strategy context changes.

## Batch 2 — Repair pre-existing CI invocation defect

Modify:
- `.github/workflows/test.yml`

Reason:
The existing workflow invokes global `--root` after the `setup` subcommand, while argparse defines it before the subcommand. Both Linux and Windows test suites pass before this command fails. Correct the invocation; do not remove or weaken the gate.

## Gate

Fresh pull-request CI must show:
- Linux full `python -m pytest tests_engine -q` passes;
- Windows focused plant/bars/doctor tests pass;
- both plant setup smoke steps pass;
- new control-plane tests pass as part of the Linux full suite.

If CI is unavailable, report verification as unavailable rather than inferred.

## Assumptions

- The repo remains Python 3.10+ and dependency-free for core engine/control logic.
- `icarus-control-v1` and `icarus-pipeline-v1` are immutable v1 contract identities.
- Receipt persistence is performed by an external stage runner into a separate evidence branch; this tool only verifies.
- A future signer/attestation layer may wrap these receipts without changing their canonical v1 payload.
