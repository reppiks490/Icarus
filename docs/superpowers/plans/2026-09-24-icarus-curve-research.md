# ICARUS Curve Research Plane — Implementation Plan

> Implementation method originally selected: Native/inline after subagent-driven was unavailable in chat.
> This file is the executable build contract. It does not claim implementation occurred.

**Goal:** Implement a deterministic, research-only, point-in-time GC futures-curve subsystem without strategy/runtime influence.

**Spec:** `docs/superpowers/specs/2026-09-24-icarus-curve-research-design.md`

## Global constraints
- `execution_authorized=false`.
- No Pulse/entry/exit/sizing/alert/broker mutation.
- No modification to existing NQ/ES/YM roll behavior.
- Explicit maturity contracts only.
- `available_at <= snapshot_asof` for every admissible observation.
- Contract metadata itself is point-in-time.
- Provider failure is explicit and fail-closed.
- No third-party Python dependency is required for Phase A.
- Deterministic tests do not use live internet.
- NaN/infinity are forbidden in canonical payloads.
- Provider agreement is quality evidence, not permission to average.
- Financing rates are normalized to decimal-per-year.
- Liquidity data without point-in-time provenance stays absent.
- Semantic synchronization policies are type-specific.
- Production integration remains out of scope.

## Review focus
1. historically dated but later-available records;
2. future contract-definition/listing leakage;
3. settlement/spot semantic skew;
4. provider disagreement and access failures;
5. strategy/runtime import isolation.

## File map
Create:
```
icarus_engine/curve_research/
    __init__.py
    errors.py
    models.py
    provenance.py
    contracts.py
    synchronize.py
    quality.py
    estimators.py
    experiment.py
```

Tests:
```
tests_engine/
    curve_test_support.py
    test_curve_models.py
    test_curve_provenance.py
    test_curve_contracts.py
    test_curve_synchronization.py
    test_curve_quality.py
    test_curve_estimators.py
    test_curve_experiment.py
    test_curve_isolation.py
    fixtures/curve_gc_2026_09_24.json
```

Do not modify initially:
`icarus_engine/runtime.py`,
`icarus_engine/contracts.py`,
`icarus_engine/strategy/pulse.py`,
`icarus_engine/emulator.py`.

---

## Task 1 — Immutable domain models and typed failures

### Produce
```python
PriceSemantic
SourceStatus
Observation
ContractDefinition
CurveLeg
FinancingPoint
CurveSnapshot
CurveResearchError
TemporalViolation
ContinuousContractError
ContractLifecycleViolation
InvalidCurveTopology
SynchronizationFailure
SourceDisagreement
UnsupportedContractType
SourceUnavailable
```

### RED tests
- Observation is frozen.
- nonfinite values rejected.
- `available_at < observed_at` rejected.
- positive price semantics reject zero/negative values.
- reference rates may be zero or negative.
- financing units must be `DECIMAL_PER_YEAR`.

### Corrected data model
`FinancingPoint` stores one authoritative `Observation`; `annual_rate`
is derived from `observation.value`.

Do not put naked volume/OI/spread floats into `CurveLeg` Phase A.

### Verify
`pytest tests_engine/test_curve_models.py -v`

---

## Task 2 — Canonical provenance and deterministic hashing

### Produce
```python
canonical_payload(value)
canonical_json(value)
canonical_digest(value)
```

Normalize dataclasses, enums, dates/times, tuples/lists, mapping order and finite floats.
Canonical JSON uses sorted keys, compact separators and `allow_nan=False`.

### RED tests
- mapping key order cannot change digest;
- date/tuple normalization deterministic;
- NaN/infinity rejected;
- one-byte semantic change changes digest.

### Verify
`pytest tests_engine/test_curve_provenance.py -v`

---

## Task 3 — Explicit contract validation

### Produce
```python
validate_contract(contract, *, root, asof)
ordered_contracts(contracts, *, root, asof)
```

### Required rules
Reject:
- `GC=F`, `GC1!` and continuous aliases;
- wrong root;
- non-`single` combo/spread contracts;
- inactive lifecycle;
- `definition_asof > snapshot_date`;
- `contract.available_at > snapshot_asof`;
- duplicate settlement maturity.

Return contracts sorted deterministically by settlement date then ticker.

### Verify
`pytest tests_engine/test_curve_contracts.py -v`

---

## Task 4 — Point-in-time snapshot construction

### Produce
`SyncPolicy` and `build_snapshot(...)`.

### Required behavior
- Build from explicit contracts + exact contract prices.
- Price records must be available by asof.
- Reject stale observations.
- Reject duplicate contract-price observations.
- Enforce accepted price semantics.
- Enforce minimum maturities.
- Synchronization policy is semantic-specific; do not use one universal skew.
- Spot and financing legs preserve their own admissibility rules.
- Financing observations must already be normalized to decimal-per-year.

### Critical RED test
A record with `observed_at < asof` but `available_at > asof` must fail.

### Verify
`pytest tests_engine/test_curve_synchronization.py -v`

---

## Task 5 — Source disagreement and curve quality

### Produce
```python
DisagreementState
SourceComparison
compare_source_values(...)
```

States:
`CONSISTENT, MINOR_DISLOCATION, MATERIAL_DISLOCATION`
plus semantic incomparability/staleness when needed.

### Rule
Initial implementation does **not** manufacture a blended consensus value.
The result reports disagreement only.

### RED tests
- material difference is surfaced;
- one source cannot claim consensus;
- semantically incomparable records fail comparison before numeric tolerance.

### Verify
`pytest tests_engine/test_curve_quality.py -v`

---

## Task 6 — Research-only curve estimators

### Produce
```python
raw_slope(snapshot, near=0, far=1)
annualized_log_slope(snapshot, near=0, far=1)
spot_basis(snapshot, leg=0)
annualized_log_basis(snapshot, leg=0)
financing_adjusted_log_basis(snapshot, leg=0, ...)
```

### Rules
- actual maturity distance drives annualization;
- spot is required for basis estimators;
- financing tenor mapping has an explicit maximum mismatch;
- financing-adjusted residual is **not** labeled convenience yield;
- estimator output carries no BUY/SELL semantics.

### Verify
`pytest tests_engine/test_curve_estimators.py -v`

---

## Task 7 — Deterministic GC fixture and test support

### Create
`tests_engine/curve_test_support.py` with:
```python
make_contract(...)
make_observation(...)
make_financing_point(...)
make_snapshot(...)
load_curve_fixture(...)
```

No production logic belongs in this file.

Create sanitized fixture:
`tests_engine/fixtures/curve_gc_2026_09_24.json`

The fixture may contain known contract metadata such as GCV6/GCX6/GCZ6 only when
source semantics and availability are explicit. Do not invent futures prices.

### RED tests
- identical frozen fixture -> identical digest;
- one revision/value change -> different digest.

### Verify
`pytest tests_engine/test_curve_provenance.py tests_engine/test_curve_synchronization.py -v`

---

## Task 8 — Research attempt envelope

### Produce
Immutable `CurveResearchReceipt` and `build_receipt(...)`.

Fields include:
```
cycle_id
execution_instance_id
claim_id
attempt_id
pinned_revision
source_set
snapshot_digest
estimator_id
data_sufficiency_status
estimator_validity_status
ablation_readiness_status
redundancy_status
multiple_testing_status
execution_authorized=false
```

Builder exposes no execution-authorization override.

### Verify
`pytest tests_engine/test_curve_experiment.py -v`

---

## Task 9 — Strategy/runtime isolation gate

Create `tests_engine/test_curve_isolation.py`.

### Required tests
- `runtime.py`, `emulator.py`, and `strategy/pulse.py` do not import
  `curve_research`;
- constructing a snapshot causes no engine/config/filesystem side effect;
- no broker/bridge/trading object is reachable from the curve package's public API.

### Verify
`pytest tests_engine/test_curve_isolation.py -v`

---

## Task 10 — Full verification

Run and read actual output:

```bash
pytest   tests_engine/test_curve_models.py   tests_engine/test_curve_provenance.py   tests_engine/test_curve_contracts.py   tests_engine/test_curve_synchronization.py   tests_engine/test_curve_quality.py   tests_engine/test_curve_estimators.py   tests_engine/test_curve_experiment.py   tests_engine/test_curve_isolation.py -v

pytest tests_engine/test_futures.py -v
pytest tests_engine/test_research.py -v
pytest tests_engine -q
python -m compileall -q icarus_engine
git diff --check
git grep -n "curve_research" --   icarus_engine/runtime.py   icarus_engine/emulator.py   icarus_engine/strategy
```

No completion claim is permitted without fresh command evidence.

## Post-implementation research gate
Implementation does not authorize carry.

Future experiment hierarchy:
```
M0 = null
M1 = own-price baseline
M2 = M1 + raw slope
M3 = M1 + annualized log slope
M4 = M1 + spot basis
M5 = current ICARUS
M6 = current ICARUS + preregistered curve family
```

Decision quantity: `Delta_OOS = M6 - M5`.

## Rollback
Because the subsystem is isolated, an eventual implementation commit must be revertable
without persistent strategy/broker migration.

## Definition of done
The infrastructure is complete only after fresh verification proves:
- immutable point-in-time objects;
- explicit-maturity/lifecycle/metadata availability enforcement;
- semantic synchronization;
- deterministic hashing/replay;
- no silent provider averaging;
- research-only estimators;
- fail-closed receipts;
- no Pulse/runtime dependency;
- existing futures/research/full engine suite green;
- compile and diff checks green;
- `execution_authorized=false`.

This definition does not claim profitability or production readiness.
