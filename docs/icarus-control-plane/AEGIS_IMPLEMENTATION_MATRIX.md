# AEGIS Findings 019–030 — Repo-Addressable Implementation Matrix

Status meanings:
- **STRONG PARTIAL** — meaningful controls exist, but the full AEGIS invariant is not yet proven.
- **PARTIAL** — related controls exist; important assurance surfaces remain open.
- **OPEN** — no repository-native control was found that closes the finding.
- **CONTROL-PLANE IMPLEMENTED** — the new `icarus_control` layer directly addresses the structural portion; fresh scientific/release evidence is still separate.

This matrix is intentionally conservative. A nearby module is not treated as proof that the full finding is solved.

| Finding | Current repository anchors | Current status | Smallest decisive next work |
|---|---|---|---|
| 019 Numerical stability / threshold topology | `icarus_engine/runtime.py::validate_values`; `tests_engine/test_backtest_validation.py` rejects NaN/Inf and malformed windows; new strict control-plane canonicalization | PARTIAL | Inventory every empirical threshold/ranking cutoff used by qualification; classify HARD vs EMPIRICAL; add one-tick/epsilon sweeps and require authority non-increase under added uncertainty. |
| 020 Checkpoint / recovery equivalence | `icarus_engine/activation.py` has durable prepared operations, immutable versions, recovery-required state, snapshot/rollback; `tests_engine/test_frozen_replay.py` freezes replay inputs | STRONG PARTIAL | Add uninterrupted-vs-restart differential replay covering rolling indicators, MTF aggregators, activation overlays, pending state and journal output. |
| 021 Artifact identity / substitution | activation rows bind canonical hashes; backtests record source/effective/subbar/deep hashes; control receipts bind policy/schema and code subject | PARTIAL | Introduce a typed, domain-separated artifact identity for qualification-critical model/config/dataset/calendar/cost artifacts; mutation matrix must change identity for behaviorally relevant changes. |
| 022 Configuration/control-plane authority | versioned activation overlays; owner-hard constraints; new `icarus-control-v1` contract and stage maturity ceilings | CONTROL-PLANE IMPLEMENTED / ENGINE PARTIAL | Bind every authority-changing runtime config/default/env override to a qualified bundle; fuzz config mutations into FORBIDDEN / REPLAY / RECALIBRATE / REQUALIFY classes. |
| 023 Validator monoculture / oracle dependence | broad pytest suite; TradingView parity fixtures; frozen-replay property tests; new S4 oracle-origin fields | PARTIAL | Record oracle ancestry for critical tests and add mutation/fault injection for calendar, aggregation, cost, authority and provenance code; validator cloning must not increase evidence authority. |
| 024 Specification drift / requirement erosion | `SPEC.md` ↔ `icarus_engine/spec.py`; `tests_engine/test_spec.py`; `ASTRA_DO_NOT.md`; new versioned control contracts | STRONG PARTIAL | Create requirement IDs for immutable invariants and a Requirement→Implementation→Test trace table; deliberately remove one enforcement in mutation testing and require detection. |
| 025 Resource exhaustion / safe degradation | `icarus_engine/orchestration.py` has durable bounded jobs, token reservation, cancellation and no automatic retry; activation uses locks/timeouts | PARTIAL | Saturation/fault sweep for queue, SQLite lock, audit I/O, provider timeout and replay backlog; prove less available evidence never increases authority or silently changes population. |
| 026 Multi-timeframe aggregation leakage | `icarus_engine/pine/timeframe.py::Aggregator` distinguishes `forming` from completed bars, drops late already-closed sub-bars; `calendar.py`; frozen replay tests | STRONG PARTIAL | Make aggregate PARTIAL/FINAL + as-of/knowledge-time semantics explicit in artifacts; future-tail mutation and live-incremental vs historical-causal parity tests across all requested timeframes. |
| 027 Market-data revision / vintage integrity | `icarus_engine/feeds/bars.py` merges by bar-open timestamp and reloads on mtime; backtests hash frozen data | OPEN / PARTIAL SNAPSHOT HASHING | Preserve append-only observed revisions/corrections and dataset-vintage identity; a later vendor rewrite/backfill must not alter an earlier decision replay. Latest-only history must mark PIT replay UNVERIFIABLE. |
| 028 Computational-latency leakage | runtime records `scale_known_at`; orchestration records workflow/stage timing; no end-to-end decision deadline contract found | OPEN | Add analytical decision deadline + readiness envelope; stress p50/p95/p99 critical path; delayed mandatory evidence crossing deadline must become LATE and cannot retain authority. |
| 029 Training-serving skew | frozen `FEATURE_KEYS`/trainer spec; trainer dataset/model artifacts; runtime/Pine feature path; replay source/effective hashes | PARTIAL | Run the same causal event stream through offline/batch and live/incremental feature paths; compare presence, order, units, values, missingness, timestamps and preprocessing state. |
| 030 Multiple comparisons / research-process overfit | `icarus_engine/research.py` selects on train/validation only, records `total_combinations`, persists selection before holdout, prevents holdout reuse across dataset revisions and explicitly warns about many-variant overfit | STRONG PARTIAL | Extend exposure accounting across studies/agents/assets/timeframes/metrics, not only one study; add null-search benchmark and ensure redundant candidate expansion cannot manufacture authority. |

## Highest-value sequence after control-plane merge readiness

1. **Finding 027 — point-in-time/vintage integrity.** Historical vendor cleanup can invalidate every downstream empirical claim while leaving code/tests apparently clean.
2. **Finding 029 — offline/online feature parity.** Qualification is meaningless if deployed feature semantics differ.
3. **Finding 026 — causal MTF parity.** ICARUS relies heavily on cross-timeframe confirmation; this is a direct leakage surface.
4. **Finding 030 — research-process multiplicity.** Existing holdout discipline is useful, but adaptive cross-study exposure remains a selection channel.
5. **Finding 020 — recovery equivalence.** Existing activation recovery is strong enough to make an end-to-end differential harness practical.
6. **Finding 023 — independent oracle/mutation program.** Use this to prevent the preceding fixes from validating themselves.

## Existing controls that must not be weakened

- `execution_authorized=false`
- no synthetic bars as empirical evidence
- no invented trainer slots/features
- no Pulse rewrite
- fixed/frozen strategy specification unless owner-approved
- fail-closed provenance/qualification
- deterministic replay/canonicalization where declared
- holdout reuse prevention
- uncertainty cannot increase authority

## Release interpretation

The matrix is an engineering backlog, not a maturity score. A finding marked STRONG PARTIAL is still not VERIFIED_FOR_INTEGRATION. Only fresh pinned-revision evidence with an appropriate independent oracle may close an item.
