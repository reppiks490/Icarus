# OMNIVISION v2 Stage 0 Verification, Audit, and Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce executable proof that the existing OMNIVISION foundation is temporally correct, provenance-safe, statistically honest, regression-safe, and fully separated from live execution; repair every load-bearing defect found before any v2 feature implementation is allowed.

**Architecture:** Stage 0 is a verification/remediation gate, not a feature-expansion phase. It executes the existing foundation, adds only tests/audit infrastructure and minimal defect fixes required by evidence, then emits a durable audit report and a binary go/no-go checkpoint. If any load-bearing audit remains unresolved, v2 Stage 1 stays blocked.

**Tech Stack:** Python 3.10+ stdlib, pytest, setuptools build backend, SQLite, Git/GitHub. No new runtime dependency.

**Spec:** `docs/superpowers/specs/2026-09-24-omnivision-epistemic-control-plane-v2-design.md`

## Global Constraints

- `execution_authorized=false` remains invariant for OMNIVISION research artifacts.
- No Pulse rewrite.
- No autonomous credential acquisition.
- No sandbox escape, credential discovery, access-control bypass, stealth persistence, unauthorized access, or prohibited scraping.
- No fabricated observations, publication times, ticks, fills, revisions, or source availability.
- Inputs must be public, licensed, connected, or explicitly user-authorized.
- Observed, derived, latent/inferred, hypothesized, contradicted, stale, invalidated, and unknown states remain distinct.
- Inference never upgrades itself into an observation.
- Source opinion, attention, sentiment, analyst rank, and media tone are labeled as such and never silently converted into factual world state.
- Current data is never backfilled into a historical decision timestamp unless the source proves it was available then.
- Owner-hard repository rules remain authoritative.
- No Stage 1 v2 product feature may land until this plan's final gate is `GO`.
- Never weaken, skip, xfail, or delete a failing test merely to obtain green.
- Every runtime claim must include the exact command and observed exit code.

## Review Focus

1. **Publication precedes receipt:** a world-state event published at T1 but received at T2 must project with `Observation.available_at == T2`, because it was not knowable to ICARUS before receipt even if the source published earlier.
2. **Walk-forward overlap:** later folds must not reuse all observations from earlier folds and call that independent forward evidence; each evaluation fold must use its own forward interval.
3. **Execution boundary drift:** adding research modules must never create imports/calls into Pulse, broker/order, bridge-execution, subprocess, or raw network execution surfaces.
4. **Revision replay:** an older historical revision must remain visible at its historical cutoff, while a later revision supersedes it only after both publication and receipt make it available.
5. **Duplicate-source certainty:** two observations relayed by distinct vendors from the same upstream source must not be treated as independent confirmations; Stage 0 must at minimum identify this as an unresolved Stage 1 capability-registry requirement rather than silently claiming the foundation solves it.

---

## Scope decomposition

The v2 design contains multiple independent subsystems. They will be implemented through separate plans.

This plan covers only:

**Stage 0 — Foundation Verification and Remediation**

Later plans, written only after Stage 0 returns `GO`:

1. Stage 1 — Source Capability Registry + Provenance DAG + Search-Aware Trial Ledger
2. Stage 2 — Confidence Decomposition + Calibration + Abstention + Staleness
3. Stage 3 — Negative Knowledge + Stronger Novelty + Search-Aware Statistics
4. Stage 4 — Regime/Changepoint + Causal Validation
5. Stage 5 — Authorized Domain Adapters
6. Stage 6 — Proof-Carrying Candidates + Shadow Integration Governor

No later-stage file is created by this plan.

## File Map

**Create**
- `tests_engine/test_omnivision_stage0_boundaries.py` — durable execution-separation and forbidden-dependency tests.
- `tests_engine/test_omnivision_stage0_temporal.py` — late-receipt/revision replay regressions that specifically audit the foundation's point-in-time semantics.
- `docs/audits/2026-09-24-omnivision-v2-stage0-audit.md` — exact 16-lane audit evidence, commands, exit codes, findings, fixes, residual risks, and final verdict.

**Modify only if a failing test proves the defect**
- `icarus_engine/omnivision/contracts.py` — correct projected availability semantics.
- `icarus_engine/omnivision/falsification.py` — correct forward-fold semantics.
- `tests_engine/test_omnivision_contracts.py`
- `tests_engine/test_omnivision_falsification.py`
- `tests_engine/test_omnivision_integration.py`
- `tests_engine/test_world_state.py`
- `tests_engine/test_advisory.py`

**Modify at final checkpoint**
- `.icarus_loop/state.json` — exact results, findings, remediation commits, plugin/reviewer evidence, and Stage 1 eligibility.

**Forbidden**
- `icarus_engine/strategy/pulse.py`
- live broker/order modules
- live bridge execution configuration
- production strategy inputs

## Knowledge delta by path

### Batch A — Runtime truth
- Code: none unless runtime failures prove a defect.
- Tests: existing `tests_engine` only.
- Docs: `docs/audits/2026-09-24-omnivision-v2-stage0-audit.md` begins with environment/baseline evidence.
- State: `.icarus_loop/state.json` updated only after the full Stage 0 gate.
- Skills/rules/context/memory: none; no reusable repository procedure is introduced yet.

### Batch B — Temporal/statistical remediation
- Code: `icarus_engine/omnivision/contracts.py`, `icarus_engine/omnivision/falsification.py` only if tests fail as predicted.
- Tests: Stage 0 temporal/falsification regression tests.
- Docs: audit report finding/remediation sections.
- Rules: no new repository rule; the spec already defines the invariant.
- Context/memory: audit report + final loop checkpoint carry the durable decision.

### Batch C — Boundary/audit proof
- Tests: `tests_engine/test_omnivision_stage0_boundaries.py`.
- Docs: completed Stage 0 audit report.
- State: final `.icarus_loop/state.json` go/no-go checkpoint.
- Routers/skills: none; no new repeatable user workflow is being introduced.

## Assumptions

- Python 3.10 or newer is available. Invalidated by an execution environment below the `pyproject.toml` floor.
- `pytest` is available or can be installed through the repository's `dev` extra in an isolated development environment. Invalidated if package installation is unavailable.
- No GitHub Actions workflow currently provides authoritative CI for this branch; GitHub code search returned no workflow/action configuration. Invalidated if a branch-local workflow is discovered during execution.
- The current branch remains the source of truth. Invalidated by concurrent repository changes touching Stage 0 files, which require a fresh delta audit before proceeding.
- Stage 0 may repair foundation defects but may not implement Source Capability Registry, Provenance DAG, Trial Ledger, calibration, regimes, adapters, or other v2 feature expansion.

---

### Task 1: Establish the Executable Baseline

**Files:**
- Read: `pyproject.toml`
- Read: all existing `icarus_engine/omnivision/*.py`
- Read: `icarus_engine/world_state.py`
- Read: `icarus_engine/advisory.py`
- Read: existing `tests_engine/test_omnivision_*.py`
- Create: `docs/audits/2026-09-24-omnivision-v2-stage0-audit.md`

**Interfaces:**
- Consumes: current feature branch exactly as checked out.
- Produces: baseline environment record and unmodified test-suite result. No product-code changes.

- [ ] **Step 1: Record environment and branch identity**

Run:

```bash
python --version
git branch --show-current
git rev-parse HEAD
git status --short
```

Expected:
- Python reports `>=3.10`.
- branch is `codex/exotic-research-loop`.
- working tree is clean before implementation begins.

Record exact output in the audit report.

- [ ] **Step 2: Compile the affected Python surface before pytest**

Run:

```bash
python -m compileall -q   icarus_engine/world_state.py   icarus_engine/advisory.py   icarus_engine/omnivision   tests_engine
```

Expected exit code: `0`.

A syntax/import compilation failure is a blocking Stage 0 finding.

- [ ] **Step 3: Run the narrow foundation suite without editing code**

Run:

```bash
python -m pytest   tests_engine/test_world_state.py   tests_engine/test_omnivision_contracts.py   tests_engine/test_omnivision_bridge.py   tests_engine/test_omnivision_hypotheses.py   tests_engine/test_omnivision_novelty.py   tests_engine/test_omnivision_falsification.py   tests_engine/test_omnivision_candidates.py   tests_engine/test_omnivision_integration.py   tests_engine/test_advisory.py   tests_engine/test_research.py   -q
```

Record:
- command;
- exit code;
- passed/failed/error counts;
- every failing test name;
- first causal traceback for each unique failure class.

Do not fix anything yet.

- [ ] **Step 4: Run the full existing engine suite without editing code**

Run:

```bash
python -m pytest tests_engine -q
```

Record the same evidence.

- [ ] **Step 5: Run import/package smoke checks**

Run:

```bash
python - <<'PY'
from icarus_engine.advisory import AdvisoryLedger
from icarus_engine.world_state import Observation, Transmission, WorldStateGraph
from icarus_engine.omnivision.contracts import WorldEvent, observation_from_event
from icarus_engine.omnivision.ledger_bridge import ledger_observations
from icarus_engine.omnivision.hypotheses import Hypothesis, forge_hypotheses
from icarus_engine.omnivision.novelty import screen_novelty
from icarus_engine.omnivision.falsification import aligned_pairs, placebo_shift_test, walk_forward_correlation
from icarus_engine.omnivision.candidates import build_candidate
print("omnivision-import-smoke: ok")
PY
```

Expected stdout: `omnivision-import-smoke: ok`.

- [ ] **Step 6: Classify the baseline**

Audit status must be exactly one of:

- `BASELINE_GREEN`
- `BASELINE_FAILING_EXISTING`
- `BASELINE_ENVIRONMENT_BLOCKED`

Do not call the foundation verified yet.

- [ ] **Step 7: Commit the initial audit evidence**

```bash
git add docs/audits/2026-09-24-omnivision-v2-stage0-audit.md
git commit -m "Codex: record OMNIVISION v2 Stage 0 baseline"
```

---

### Task 2: Audit and Repair Publication-vs-Receipt Availability

**Files:**
- Create: `tests_engine/test_omnivision_stage0_temporal.py`
- Modify if RED proves defect: `icarus_engine/omnivision/contracts.py`
- Regression: `tests_engine/test_omnivision_contracts.py`, `tests_engine/test_omnivision_integration.py`

**Interfaces:**
- Consumes: accepted `AdvisoryLedger` world-state event dictionaries.
- Produces: `Observation.available_at` equal to the earliest timestamp at which ICARUS could actually know the event, i.e. `max(published_at, received_at)` for published evidence and `received_at` for first-observed evidence.

- [ ] **Step 1: Write the late-receipt failing test**

```python
from icarus_engine.omnivision.contracts import observation_from_event


def test_published_event_is_not_available_before_receipt():
    event = {
        "event_type": "world_state",
        "source": "provider",
        "domain": "macro",
        "entity": "GLOBAL",
        "source_url": "https://provider.example/event",
        "observed_at": "2026-09-24T12:00:00+00:00",
        "published_at": "2026-09-24T12:05:00+00:00",
        "received_at": "2026-09-24T12:20:00+00:00",
        "confidence": 0.9,
        "values": {"x": 1.0},
        "event_id": "a" * 64,
    }
    observation = observation_from_event(event, "x")
    assert observation.available_at == 1790252400
```

The exact epoch in the assertion must be generated once from the ISO timestamp during test authoring if this literal does not match; do not guess an epoch to make the test green.

Preferred test form avoids a magic epoch:

```python
from datetime import datetime

expected = int(datetime.fromisoformat(event["received_at"]).timestamp())
assert observation.available_at == expected
```

- [ ] **Step 2: Add a graph replay test proving the leak would matter**

```python
from datetime import datetime
from icarus_engine.world_state import WorldStateGraph

published = int(datetime.fromisoformat(event["published_at"]).timestamp())
received = int(datetime.fromisoformat(event["received_at"]).timestamp())
observation = observation_from_event(event, "x")
graph = WorldStateGraph([observation])

assert graph.as_of(published + 1) == ()
assert len(graph.as_of(received)) == 1
```

- [ ] **Step 3: Run only the new tests and confirm RED if the audit hypothesis is correct**

```bash
python -m pytest tests_engine/test_omnivision_stage0_temporal.py -q
```

Expected before remediation: the published-event availability test fails because current projection prefers `published_at`.

If it unexpectedly passes, record `AUDIT_HYPOTHESIS_NOT_REPRODUCED` and do not edit production code.

- [ ] **Step 4: Implement the minimal availability correction only if RED reproduced**

Replace the availability choice in `observation_from_event()` with:

```python
published = event.get("published_at")
received = event.get("received_at")
received_ts = _timestamp(received, "received_at") if received is not None else None

if published is not None:
    published_ts = _timestamp(published, "published_at")
    if received_ts is None:
        raise ValueError("received_at is required for ledger-backed evidence")
    available = max(published_ts, received_ts)
elif received_ts is not None:
    available = received_ts
else:
    raise ValueError("event availability is unknown")
```

This is intentionally conservative: accepted external evidence cannot be knowable to ICARUS before receipt.

- [ ] **Step 5: Add revision replay regression**

Use `AdvisoryLedger` with:
- revision v1 published before T1 and received at T1;
- revision v2 published before T2 and received at T2;
- historical query between T1 and T2 returns v1 only;
- query at T2 returns v2;
- projected observations preserve the corresponding receipt-aware `available_at`.

- [ ] **Step 6: Run scoped temporal/provenance regressions**

```bash
python -m pytest   tests_engine/test_omnivision_stage0_temporal.py   tests_engine/test_omnivision_contracts.py   tests_engine/test_omnivision_bridge.py   tests_engine/test_omnivision_integration.py   tests_engine/test_advisory.py   -q
```

Expected: PASS.

- [ ] **Step 7: Update audit report finding**

Record:
- hypothesis;
- RED evidence;
- root cause;
- minimal fix;
- regression command/exit code;
- reviewer disposition.

- [ ] **Step 8: Commit**

```bash
git add   icarus_engine/omnivision/contracts.py   tests_engine/test_omnivision_stage0_temporal.py   tests_engine/test_omnivision_contracts.py   tests_engine/test_omnivision_integration.py   docs/audits/2026-09-24-omnivision-v2-stage0-audit.md
git commit -m "Codex: enforce receipt-aware OMNIVISION availability"
```

If production code was not changed because the hypothesis did not reproduce, commit only the tests/audit evidence with a truthful message.

---

### Task 3: Audit and Repair Walk-Forward Fold Independence

**Files:**
- Modify: `tests_engine/test_omnivision_falsification.py`
- Modify if RED proves defect: `icarus_engine/omnivision/falsification.py`
- Regression: `tests_engine/test_omnivision_integration.py`

**Interfaces:**
- Existing:
  - `aligned_pairs(feature_rows, outcome_rows, *, decision_cutoff, lag_seconds) -> list[tuple[float, float]]`
  - `walk_forward_correlation(..., cutoffs, lag_seconds, min_pairs=20) -> dict`
- Planned minimal extension:
  - `aligned_pairs(..., observed_after: int | None = None) -> list[tuple[float, float]]`
- Semantics:
  - `observed_after=None`: current as-of behavior.
  - `observed_after=N`: include only feature observations with `observed_at > N`.
  - walk-forward fold 0 uses all eligible observations through cutoff 0.
  - fold N>0 evaluates only observations strictly after cutoff N-1 and available by cutoff N.

- [ ] **Step 1: Replace the cumulative-window assumption with an independence test**

Add:

```python
def test_walk_forward_folds_do_not_reuse_prior_fold_observations():
    features = [(i, i, float(i)) for i in range(1, 101)]
    outcomes = [(i + 1, i + 1, float(i)) for i in range(1, 101)]

    out = walk_forward_correlation(
        features,
        outcomes,
        cutoffs=(40, 70, 100),
        lag_seconds=1,
        min_pairs=20,
    )

    assert [fold["pairs"] for fold in out["folds"]] == [39, 29, 29]
```

Also assert every qualified fold reports its explicit interval:

```python
assert out["folds"][0]["observed_after"] is None
assert out["folds"][0]["cutoff"] == 40
assert out["folds"][1]["observed_after"] == 40
assert out["folds"][2]["observed_after"] == 70
```

- [ ] **Step 2: Run the specific test and confirm RED**

```bash
python -m pytest   tests_engine/test_omnivision_falsification.py::test_walk_forward_folds_do_not_reuse_prior_fold_observations   -q
```

Expected before remediation: FAIL because current folds are cumulative.

If the test does not fail, record why and do not edit the implementation.

- [ ] **Step 3: Extend `aligned_pairs` minimally**

Add optional keyword:

```python
def aligned_pairs(
    feature_rows,
    outcome_rows,
    *,
    decision_cutoff: int,
    lag_seconds: int,
    observed_after: int | None = None,
):
    if observed_after is not None and (type(observed_after) is not int or observed_after < 0):
        raise ValueError("observed_after must be a non-negative integer or None")

    # existing validation...

    for observed in sorted(features):
        if observed_after is not None and observed <= observed_after:
            continue
        # existing exact-lag and availability logic...
```

- [ ] **Step 4: Change walk-forward to disjoint forward evaluation windows**

Inside `walk_forward_correlation()`:

```python
previous_cutoff = None
for cutoff in cutoffs:
    pairs = aligned_pairs(
        feature_rows,
        outcome_rows,
        decision_cutoff=cutoff,
        lag_seconds=lag_seconds,
        observed_after=previous_cutoff,
    )
    # existing correlation/status logic...
    fold = {
        "observed_after": previous_cutoff,
        "cutoff": cutoff,
        "pairs": len(pairs),
        "correlation": corr,
        "status": status,
    }
    # append / qualify...
    previous_cutoff = cutoff
```

Require strictly increasing cutoffs:

```python
if any(left >= right for left, right in zip(cutoffs, cutoffs[1:])):
    raise ValueError("cutoffs must be strictly increasing")
```

- [ ] **Step 5: Add leakage guards for the new window**

Tests must prove:
- a feature observed before/equal to `observed_after` is excluded;
- a feature observed after the boundary but received after the fold cutoff is excluded;
- an outcome received after the fold cutoff is excluded;
- a duplicated observation timestamp still rejects rather than selecting a revision;
- unsorted/non-increasing cutoffs reject.

- [ ] **Step 6: Update integration fixture if needed**

The integration test's synthetic series must still produce three qualified forward folds. Keep the test deterministic; change only sample length/cutoffs if the new disjoint windows make the existing minimum pair threshold impossible.

- [ ] **Step 7: Run falsification + integration regressions**

```bash
python -m pytest   tests_engine/test_omnivision_falsification.py   tests_engine/test_omnivision_integration.py   -q
```

Expected: PASS.

- [ ] **Step 8: Record the semantic correction and commit**

```bash
git add   icarus_engine/omnivision/falsification.py   tests_engine/test_omnivision_falsification.py   tests_engine/test_omnivision_integration.py   docs/audits/2026-09-24-omnivision-v2-stage0-audit.md
git commit -m "Codex: make OMNIVISION forward folds non-overlapping"
```

---

### Task 4: Add Durable Execution-Separation and Forbidden-Dependency Tests

**Files:**
- Create: `tests_engine/test_omnivision_stage0_boundaries.py`
- Read only: `icarus_engine/omnivision/*.py`, `icarus_engine/world_state.py`

**Interfaces:**
- Consumes: Python source AST for the research-only surface.
- Produces: executable regression proof that research modules do not import/call forbidden execution/network/process surfaces and never authorize execution.

- [ ] **Step 1: Write the boundary test**

```python
import ast
from pathlib import Path

RESEARCH_FILES = [
    Path("icarus_engine/world_state.py"),
    *sorted(Path("icarus_engine/omnivision").glob("*.py")),
]

FORBIDDEN_IMPORT_PREFIXES = (
    "icarus_bridge",
    "icarus_engine.strategy.pulse",
    "subprocess",
    "socket",
    "requests",
    "httpx",
)

FORBIDDEN_CALL_NAMES = {
    "place_order",
    "submit_order",
    "execute_trade",
    "system",
    "popen",
}


def test_research_surface_has_no_forbidden_execution_dependencies():
    findings = []
    for path in RESEARCH_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(FORBIDDEN_IMPORT_PREFIXES):
                        findings.append(f"{path}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.startswith(FORBIDDEN_IMPORT_PREFIXES):
                    findings.append(f"{path}: from {module}")
            elif isinstance(node, ast.Call):
                name = None
                if isinstance(node.func, ast.Name):
                    name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    name = node.func.attr
                if name in FORBIDDEN_CALL_NAMES:
                    findings.append(f"{path}: call {name}")
    assert findings == []
```

Do not forbid `urllib.parse`; it is used only for URL parsing. Any future raw network transport must be explicitly audited instead of hidden by a broad name exemption.

- [ ] **Step 2: Add execution-authority invariant test**

```python
from icarus_engine.omnivision.candidates import build_candidate


def test_research_candidate_api_exposes_no_execution_authorization_override():
    # use the existing qualified hypothesis fixture pattern
    # build a passing research candidate
    artifact = build_candidate(
        hypothesis=qualified_hypothesis(),
        novelty={"status": "novel"},
        placebo={"status": "complete", "passed": True},
        walk_forward={"passed": True},
        dataset_hash="a" * 64,
        known_failure_modes=("source_stale",),
        rollback_conditions=("walk_forward_sign_breaks",),
    )
    assert artifact["execution_authorized"] is False
```

Reuse/import a local helper in this test file rather than depending on another test module.

- [ ] **Step 3: Run the boundary test**

```bash
python -m pytest tests_engine/test_omnivision_stage0_boundaries.py -q
```

Expected: PASS. Any failure is load-bearing and blocks Stage 0.

- [ ] **Step 4: Run a Git diff boundary check**

```bash
git diff main...HEAD --   icarus_engine/strategy/pulse.py   icarus_bridge
```

Record exact output. Stage 0 requires no OMNIVISION-caused execution-path mutation.

- [ ] **Step 5: Record and commit**

```bash
git add   tests_engine/test_omnivision_stage0_boundaries.py   docs/audits/2026-09-24-omnivision-v2-stage0-audit.md
git commit -m "Codex: lock OMNIVISION research execution boundaries"
```

---

### Task 5: Complete the Provenance, Contradiction, and Revision Audit

**Files:**
- Modify if needed: `tests_engine/test_world_state.py`
- Modify if needed: `tests_engine/test_advisory.py`
- Modify if needed: `tests_engine/test_omnivision_bridge.py`
- Modify if needed: `tests_engine/test_omnivision_integration.py`
- Product code only if a newly written RED test proves a defect.

**Interfaces:**
- Consumes: ledger event IDs, source/revision identities, bridge projection, world-state contradiction/inference.
- Produces: executable evidence that ledger-native IDs and source disagreement survive the entire foundation path.

- [ ] **Step 1: Add/confirm immutable evidence-ID propagation test**

The test path must prove:

```python
saved = ledger.ingest_event(world_event(), now=NOW)
rows = ledger_observations(ledger, "NQ", iso(NOW))
assert rows[0].evidence_id == saved["event_id"]
```

Then feed the observation into a transmission and assert the latent estimate's `evidence_ids` contains exactly that ledger event ID.

- [ ] **Step 2: Add/confirm cross-source disagreement survives inference**

Use two sources for the same entity/variable with opposite values and unique ledger event IDs. Assert:

```python
result = graph.infer("target", decision_at)
assert set(result["evidence_ids"]) == {left_event_id, right_event_id}
assert result["confidence"] < max(left_confidence, right_confidence)
```

- [ ] **Step 3: Audit revision ordering at identical publication/receipt times**

Use the existing insertion-order behavior in `AdvisoryLedger` and verify historical queries remain deterministic. If this behavior is not documented in the audit report, record it as a foundation rule:

> when publication and receipt timestamps tie for revisions of one source/source_event_id, insertion order resolves the later revision.

Do not change semantics without a failing correctness test.

- [ ] **Step 4: Record duplicate-upstream limitation**

Stage 0 does not have the Source Capability Registry required to know that vendor A and vendor B relay the same upstream feed.

Record this as:

`RESIDUAL_STAGE1_REQUIRED — duplicate-upstream independence cannot yet be proven.`

It does not block Stage 0 if current logic preserves sources separately and does not claim upstream independence.

- [ ] **Step 5: Run provenance suite**

```bash
python -m pytest   tests_engine/test_world_state.py   tests_engine/test_advisory.py   tests_engine/test_omnivision_bridge.py   tests_engine/test_omnivision_integration.py   -q
```

Expected: PASS after any proven remediation.

- [ ] **Step 6: Commit only if tests/docs changed**

```bash
git add   tests_engine/test_world_state.py   tests_engine/test_advisory.py   tests_engine/test_omnivision_bridge.py   tests_engine/test_omnivision_integration.py   docs/audits/2026-09-24-omnivision-v2-stage0-audit.md
git commit -m "Codex: strengthen OMNIVISION provenance audit"
```

---

### Task 6: Execute the 16-Lane Extreme Audit

**Files:**
- Modify: `docs/audits/2026-09-24-omnivision-v2-stage0-audit.md`

**Interfaces:**
- Consumes: code, tests, runtime results, diffs, spec, owner-hard constraints.
- Produces: one row per audit lane with evidence, severity, finding status, remediation, and residual risk.

- [ ] **Step 1: Populate the audit matrix**

Use this exact header:

```markdown
| # | Lane | Evidence inspected | Verdict | Severity | Finding / proof | Remediation | Residual risk |
|---:|---|---|---|---|---|---|---|
```

Required lanes:

1. architecture/interface
2. security/trust boundary
3. point-in-time/temporal leakage
4. provenance/revision
5. statistical/search bias
6. calibration/uncertainty
7. causal claims
8. contradiction handling
9. source-health/quota behavior
10. negative-control/relevance
11. adversarial robustness
12. test quality/mutation resistance
13. performance/complexity
14. backwards compatibility
15. execution separation
16. documentation/resumability

Verdict vocabulary:

- `PASS`
- `FIXED_AND_PASS`
- `RESIDUAL_STAGE1_REQUIRED`
- `BLOCKING_FAIL`
- `NOT_APPLICABLE_FOUNDATION`

Do not use `PASS` without named evidence.

- [ ] **Step 2: Architecture/interface audit**

Trace:

```text
WorldEvent
 -> AdvisoryLedger.ingest_event
 -> AdvisoryLedger.events_as_of
 -> ledger_observations
 -> WorldStateGraph
 -> forge_hypotheses
 -> screen_novelty
 -> placebo_shift_test / walk_forward_correlation
 -> build_candidate
```

Confirm actual names/signatures match tests and spec. Record any contract mismatch.

- [ ] **Step 3: Security/trust-boundary audit**

Inspect source validation, strict JSON, URL host allowlist, signed replay protection, secret-storage tests, separate research DB protection, and the Task 4 AST boundary test.

- [ ] **Step 4: Statistical/search-bias audit**

Stage 0 is expected to report:

`RESIDUAL_STAGE1_REQUIRED`

for search multiplicity because the search-aware trial ledger is a Stage 1 feature. Confirm foundation code does not claim that this correction already exists.

- [ ] **Step 5: Calibration and causal-claims audits**

These are expected to be `NOT_APPLICABLE_FOUNDATION` or `RESIDUAL_STAGE1_REQUIRED`, because the foundation emits no calibrated probability layer and no causal-identification engine. Confirm no docs falsely claim otherwise.

- [ ] **Step 6: Source-health/relevance audits**

Confirm external connector observations live only in the v2 design/state evidence and are not silently wired into foundation product code. Confirm the Cheat Database negative control did not become an accepted market source.

- [ ] **Step 7: Adversarial/test-quality audit**

Inventory existing hostile JSON, future-time, bad URL, replay, wrong hash/model, duplicate response, tamper, and concurrent-ingest tests.

Add tests only for uncovered foundation behavior; do not manufacture tests for Stage 1 features.

- [ ] **Step 8: Performance/complexity audit**

Run:

```bash
python -m pytest tests_engine -q --durations=20
```

Record the 20 slowest tests and total runtime. Any serious regression must be investigated before `GO`.

For deterministic micro-complexity checks, inspect:
- `WorldStateGraph.contradictions` pairwise behavior;
- novelty timestamp alignment;
- SQLite event query/revision behavior.

Record complexity as engineering evidence; do not claim benchmark-grade performance without benchmark data.

- [ ] **Step 9: Backwards-compatibility audit**

Run the complete `tests_engine` suite after all remediation. Compare branch diff against `main` and identify all files outside OMNIVISION/audit/state paths. Any unrelated failure or unrelated mutation must be explained before `GO`.

- [ ] **Step 10: Documentation/resumability audit**

A fresh reviewer must be able to identify from repository files alone:

- current objective;
- spec;
- plan;
- exact test results;
- unresolved findings;
- last implementation commit;
- next action;
- execution authority state.

If any item requires this conversation to reconstruct, Stage 0 is not resumable.

- [ ] **Step 11: Commit the completed audit matrix**

```bash
git add docs/audits/2026-09-24-omnivision-v2-stage0-audit.md
git commit -m "Codex: complete OMNIVISION v2 Stage 0 audit matrix"
```

---

### Task 7: Run the Final Scoped Gate Once

**Files:**
- No product changes allowed during this task.
- If it fails, return to the owning earlier task and repair there; then rerun only affected checks before returning here.

**Interfaces:**
- Consumes: accumulated Stage 0 branch.
- Produces: final executable verification evidence.

- [ ] **Step 1: Compile all affected code**

```bash
python -m compileall -q icarus_engine tests_engine
```

Expected: exit `0`.

- [ ] **Step 2: Run all engine tests**

```bash
python -m pytest tests_engine -q
```

Expected: exit `0`.

- [ ] **Step 3: Run duration visibility pass only if the previous command passed**

```bash
python -m pytest tests_engine -q --durations=20
```

Expected: exit `0`.

- [ ] **Step 4: Run import smoke**

Use the exact Task 1 import-smoke command.

Expected: `omnivision-import-smoke: ok`.

- [ ] **Step 5: Confirm forbidden paths**

```bash
git diff main...HEAD --   icarus_engine/strategy/pulse.py   icarus_bridge
```

Expected: no Stage 0-caused diff.

- [ ] **Step 6: Inspect full branch delta**

```bash
git diff --stat main...HEAD
git status --short
```

Expected:
- no unexplained files;
- clean working tree after final commits.

- [ ] **Step 7: If repository GitHub Actions exists, inspect latest run**

If no workflow exists, record:

`CI: not configured / no workflow discovered; local execution evidence is authoritative for Stage 0.`

Do not invent CI.

- [ ] **Step 8: Independent whole-branch review**

Use a fresh reviewer when the harness supports it. Review focus:

- temporal semantics;
- provenance/revision;
- walk-forward semantics;
- execution separation;
- test validity;
- spec/plan conformance.

Verdict must be one of:
- `SHIP_STAGE0_GO`
- `FIX_FIRST`
- `RETHINK`

Any `FIX_FIRST` or `RETHINK` blocks Task 8 until resolved.

---

### Task 8: Emit the Stage 0 Go/No-Go Checkpoint

**Files:**
- Modify: `docs/audits/2026-09-24-omnivision-v2-stage0-audit.md`
- Modify: `.icarus_loop/state.json`

**Interfaces:**
- Consumes: exact final commands/results and independent review verdict.
- Produces: durable binary Stage 1 eligibility.

- [ ] **Step 1: Compute verdict**

`GO` only when all are true:

- compile gate passed;
- scoped and full tests passed;
- temporal audit passed or was fixed and passed;
- provenance/revision audit passed;
- execution separation passed;
- no blocking audit finding remains;
- independent review is `SHIP_STAGE0_GO`;
- working tree is clean;
- verification evidence is written to the audit report.

Otherwise verdict is `NO_GO`.

- [ ] **Step 2: Write final audit summary**

The audit report ends with:

```markdown
## Stage 0 Final Verdict

Verdict: GO | NO_GO
Final commit: <sha>
Python: <version>
Compile: <command> — exit <code>
Full tests: <command> — exit <code> — <count summary>
Review: <verdict>
Blocking findings: <none or exact IDs>
Residual Stage 1 requirements: <exact list>
Execution authorized: false
Next permitted action: <Stage 1 plan | continue remediation>
```

No placeholder may remain in the committed report; substitute observed values.

- [ ] **Step 3: Update loop state**

If `GO`:

```json
{
  "active_build": {
    "phase": "v2_stage0_verified",
    "status": "ready_for_stage1_plan"
  }
}
```

If `NO_GO`:

```json
{
  "active_build": {
    "phase": "v2_stage0_remediation",
    "status": "blocked"
  }
}
```

Persist exact test commands/results, audit finding IDs, remediation commits, review evidence, and next action.

- [ ] **Step 4: Update delta pointer**

Set `last_processed_commit` to the exact final Stage 0 implementation/audit commit that exists before the checkpoint commit.

- [ ] **Step 5: Commit the checkpoint**

```bash
git add   docs/audits/2026-09-24-omnivision-v2-stage0-audit.md   .icarus_loop/state.json
git commit -m "Codex: checkpoint OMNIVISION v2 Stage 0 verdict"
```

- [ ] **Step 6: Stop**

If `GO`, the next cycle may write the **Stage 1 Source Capability Registry + Provenance DAG + Trial Ledger** implementation plan.

Do not implement Stage 1 in this plan.

---

## Audit Finding IDs

Use stable IDs in the report/state:

- `S0-TIME-001` — publication-vs-receipt availability
- `S0-STAT-001` — cumulative walk-forward fold reuse
- `S0-BOUNDARY-001` — forbidden execution dependency
- `S0-PROV-001` — evidence/revision identity failure
- `S0-TEST-001` — test-quality or regression gap
- `S0-PERF-001` — material performance regression
- `S0-DOC-001` — resumability/documentation gap

New findings increment the relevant prefix.

## Review/agent policy during execution

The user has already selected the highest-compute/higher-scrutiny method.

Execution method is therefore preserved as **Subagent-driven** when the harness exposes compatible independent workers.

For each remediation task:

1. fresh implementer context;
2. scoped tests;
3. fresh reviewer context;
4. repair reviewer findings before moving on.

At the end:

5. fresh whole-branch reviewer;
6. primary integrates the verdict and writes the go/no-go checkpoint.

If subagent dispatch is unavailable, record the capability limitation and use the most rigorous available native fallback. Never claim a child/reviewer ran without lifecycle evidence.

## Plan Self-Review

### Spec coverage

- Existing foundation runtime verification: Tasks 1 and 7.
- Package/import compatibility: Tasks 1 and 7.
- Temporal leakage: Task 2.
- Provenance/revision: Tasks 2 and 5.
- Statistical honesty of current foundation: Task 3 and Task 6.
- Execution separation: Task 4 and Task 7.
- Extreme 16-lane audit: Task 6.
- Exact verification/checkpoint: Tasks 7 and 8.
- No Stage 1 feature code before gate: global constraints and Task 8 stop condition.
- GitHub resumability: Tasks 6 and 8.

The Source Capability Registry, Provenance DAG, Trial Ledger, calibration, abstention, negative-knowledge system, regime/causal layers, adapters, and integration governor are intentionally deferred to later stage-specific plans after Stage 0 `GO`.

### Placeholder scan

No `TBD`, `TODO`, `FIXME`, `implement later`, generic “add error handling,” or “similar to Task” placeholders are permitted.

Angle-bracket tokens in the Task 8 report template are instructions to the executing worker and must be replaced with observed values before the audit report is committed. They are not allowed to survive execution.

### Type consistency

- `observation_from_event(event: Mapping, variable: str) -> Observation` remains the projection interface.
- `Observation.available_at` remains an integer epoch timestamp.
- `aligned_pairs(..., observed_after: int | None = None) -> list[tuple[float, float]]` is the only planned API extension.
- `walk_forward_correlation(...) -> dict` remains API-compatible at the outer call level; fold dictionaries gain `observed_after`.
- candidate APIs remain unchanged.

### Review Focus coverage

1. Publication-before-receipt: Task 2 tests.
2. Forward-fold reuse: Task 3 tests.
3. Execution boundary drift: Task 4 AST regression + Task 7 diff.
4. Revision replay: Tasks 2 and 5.
5. Duplicate-upstream certainty: Task 5 records the honest Stage 1 limitation and prevents a false Stage 0 claim.

### Final plan ruling

This plan is intentionally narrower than the full v2 design. That is required by the spec's own hard gate: first prove and repair the foundation, then plan the new control-plane subsystems.
