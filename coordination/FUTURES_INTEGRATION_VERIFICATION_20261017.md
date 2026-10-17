# Futures stack verification — 2026-10-17

This isolated integration continues the stopped #415/#438/#432/#435 stack. It does not merge the stack to main, enable a broker, or certify the entire Icarus system.

## Source and change

Branch: `codex/futures-convergence-review-20261017`.

Preserved inputs, integrated using ordinary non-rewriting merges:

- #438 `75079156357070dfa6f20d8fbe22354e27a795a7`: convergence plus the CL execution/paper-readiness correction.
- #432 `e77dae0fb1d3860be677f6d2761e1bf75d065513`: Databento admission and execution qualification tests.
- #435 `3250e42043c21f593e120532c5e440b5821a614b`: calendar coverage rejection.
- Main `335148c8d911f3320b5bde1ed77b38df1ba9704e`: intervening runtime, UI and provider changes preserved.
- #447 `a9217cc16086130a30883162903bccb3f67e9357`: dated listing/research test fixtures made deterministic.

The additional production repair is in `icarus_engine/brain_evidence.py`. Dataclass annotations do not enforce runtime types: truthy strings such as `"false"` previously satisfied decision authorization, and false-like values such as `0` satisfied the disabled-execution check. Validation now requires `decision_authorized is True`, `execution_authorized is False`, and an actual boolean for each source's `required` flag. Values are rejected rather than coerced. Existing causal, freshness, provenance and unresolved-gate checks remain in force.

## Verification

- Before the production repair: 15 malformed-flag regression cases failed and 15 cases passed. Failures showed invalid evidence returning `valid=True`.
- After repair: all 30 Brain evidence cases pass, including strict flag checks and existing causal/freshness/live-policy rejection cases.
- Focused stack: 167 tests pass across Brain evidence, futures catalog, contract families, command state, system index and Databento tests.
- Full integrated code at `a017008717d4ed130e9bfe58edb55e7d127a828f`: **2,975 passed, 3 skipped, 111 subtests passed**, in 147.46 seconds on local Linux/Python 3.12/Node 24 with the workflow ML/bridge/Databento extras installed.

Reproduce from this branch with:

```sh
python -m pip install -e '.[dev,ml,bridge,databento]'
python -m pytest tests_engine -q -o addopts='' --tb=short
```

Hosted exact-head checks and independent integration review are still required. Local Linux success is not Windows or browser visual verification. Documentation added after the pinned code run changes no tested Python source.

## Reach and remaining gates

The 32-root catalog is static discovery capability; it does not establish provider access, execution qualification, or paper eligibility. CL remains a visible static candidate without execution/paper qualification. Calendar coverage failures remain explicit.

`brain_evidence.py` currently has no production caller in the inspected tree (`rg` finds its definitions and tests). These tests verify an evidence contract; they do not prove source-to-Brain ingestion or a live decision path. Runtime integration requires its own bounded acceptance and provenance review. The backend command-state/index contracts likewise do not certify API-to-rendered-UI integration.

No market trial, protected-holdout evaluation, paid collection, broker connection, or live-order authority was introduced. Original feature branches remain preserved. Rollback before a separate merge decision is simply to leave this integration branch unmerged; any later integration must retain the source identities and rerun checks after new changes.
