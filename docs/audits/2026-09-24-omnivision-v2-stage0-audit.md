# OMNIVISION v2 Stage 0 Audit

**Date:** 2026-09-24  
**Branch:** `codex/exotic-research-loop`  
**Spec:** `docs/superpowers/specs/2026-09-24-omnivision-epistemic-control-plane-v2-design.md`  
**Plan:** `docs/superpowers/plans/2026-09-24-omnivision-v2-stage0-verification-audit-remediation.md`  
**Verified implementation head:** `511814e1d4f4a2527abaa3b6e3472a66df666281`  
**Execution authorized:** `false`

## Evidence Summary

Stage 0 was executed as a test-first verification/remediation gate. No v2 Stage 1 source adapter or live-execution feature was added.

Authoritative final runtime evidence:

- OMNIVISION Stage 0 workflow run `36071102061`: **success**.
  - Python 3.10 job `107872003300`: success.
  - Python 3.11 job `107872003406`: success.
  - Python 3.12 job `107872003368`: success.
  - Python 3.13 job `107872003139`: success.
  - Each matrix job compiled `icarus_engine` and `tests_engine`, ran the focused OMNIVISION/advisory/research regressions, then ran the full `tests_engine` suite.
  - Python 3.11 additionally ran `python -m pytest tests_engine -q --durations=20`; it passed.
- Native repository workflow run `36071102460`: **success**.
  - Linux engine job `107872004852`: success.
  - Windows engine job `107872004666`: success.
- Final Python 3.11 duration evidence: slowest test was `tests_engine/test_futures.py::test_backtest_routes_end_to_end` at 1.35 seconds. No OMNIVISION test appeared in the slowest-20 list.
- Fresh Stage 0 delta review compared checkpoint `d18b6a360ae55cfc30b44cafc2412d3e92647b0b` to verified implementation head `511814e1d4f4a2527abaa3b6e3472a66df666281`.
- No independent child-review lifecycle tool was exposed by the active harness. Per the approved fallback, review used a fresh whole-delta reread plus two independent CI workflows; no child/reviewer run is claimed.

## Proven RED -> GREEN Findings

### S0-TIME-001 — publication vs receipt availability

**RED proof:** native workflow run `36069984480` showed evidence published at 105 but received at 120 projecting `available_at=105`; revision replay likewise projected 105 instead of receipt 110.

**Remediation:** commit `5f568f04f8d847fcdb923428cd6479d67a6cdf85` changed ledger-backed publication evidence to become available at `max(published_at, received_at)`. Commit `542bd0c7aeb0173e4de03dfe4055c9b1deac187c` aligned the stale publication-time assertion with the receipt-aware contract.

**Final proof:** run `36071102061` passes the focused temporal suite and full suite on Python 3.10–3.13.

Verdict: **FIXED_AND_PASS**

### S0-TIME-002 — sub-second receipt truncation

**RED proof:** workflow run `36071038827`, including Python 3.10 job `107871799459`, showed receipt time 120.5 projected to integer availability 120, which could expose evidence up to one second early.

**Remediation:** commit `511814e1d4f4a2527abaa3b6e3472a66df666281` changed integer availability conversion to conservative ceiling semantics.

**Final proof:** runs `36071102061` and `36071102460` both succeed.

Verdict: **FIXED_AND_PASS**

### S0-STAT-001 — cumulative walk-forward fold reuse

**RED proof:** Stage 0 run `36070248623` showed fold counts `[39, 69, 99]` instead of independent `[39, 29, 29]`, and descending cutoffs were accepted.

**Remediation:** commit `aa68dda8d134b7a1b634600647f508cb3cc4a472` added an `observed_after` boundary, non-overlapping forward evaluation intervals, and strictly increasing cutoff validation.

**Final proof:** run `36071102061` passes the focused falsification suite and full suite across Python 3.10–3.13.

Verdict: **FIXED_AND_PASS**

### S0-TEST-001 — CI root argument ordering

**Failure proof:** native run `36070314258` passed the Linux full engine suite and the Windows focused suite, then both jobs failed because `icarus_plant` defines `--root` as a global option but CI placed it after `setup`.

**Remediation:** commit `9ab347a489997541f7a1e476dc10e826e818e1ab` moved `--root` before the subcommand on Linux and Windows.

**Final proof:** native run `36071102460` succeeds on both operating systems.

Verdict: **FIXED_AND_PASS**

### S0-TEST-002 — Windows console encoding

**Failure proof:** after the argument-order correction, Windows job `107870287655` failed in `icarus_plant setup` with `UnicodeEncodeError` for the Unicode arrow. A dedicated CP1252 regression in commit `4e3d69d9c6fd7bd0fd109d683d977d1c97098681` reproduced the defect on Linux and Windows in run `36070749535`.

**Remediation:** commit `e80c6f8df3ca686c20db54a95dfa6ff6b95efdf6` replaced three console-facing Unicode arrows with ASCII `->`.

**Final proof:** native Linux/Windows run `36071102460` succeeds.

Verdict: **FIXED_AND_PASS**

## 16-Lane Extreme Audit

| # | Lane | Evidence inspected | Verdict | Severity | Finding / proof | Remediation | Residual risk |
|---:|---|---|---|---|---|---|---|
| 1 | architecture/interface | `WorldEvent -> AdvisoryLedger -> ledger_observations -> WorldStateGraph -> forge_hypotheses -> screen_novelty -> falsification -> build_candidate`; integration test; final matrix | PASS | — | Full research path is executable and deterministic under the current foundation contract. | None required in Stage 0. | Stage 1+ adds richer contracts without bypassing this path. |
| 2 | security/trust boundary | advisory hostile-input tests; HTTPS/source allowlist behavior; signed replay/tamper tests; Stage 0 AST boundary test | PASS | — | OMNIVISION research surface has no import/call dependency on Pulse, bridge execution, subprocess, raw sockets, requests/httpx, or order functions. | Added `test_omnivision_stage0_boundaries.py`. | Future adapters must remain behind authorized source contracts. |
| 3 | point-in-time/temporal leakage | RED/GREEN timing tests; revision replay; sub-second test | FIXED_AND_PASS | load-bearing | Publication-before-receipt and sub-second floor leakage were both proven and repaired. | Receipt-aware max plus conservative availability ceiling. | Future source-specific timestamp semantics must be declared in registry metadata. |
| 4 | provenance/revision | ledger event IDs; revision replay; bridge tests; contradiction integration test | PASS | — | Ledger-native evidence IDs survive bridge, graph, latent inference, hypothesis, and candidate path. Historical revisions remain point-in-time bounded. | Strengthened integration assertions. | Shared upstream feeds across nominally distinct vendors cannot yet be identified automatically. |
| 5 | statistical/search bias | walk-forward RED/GREEN evidence; placebo tests; novelty tests | RESIDUAL_STAGE1_REQUIRED | non-blocking by design | Forward folds are now disjoint and cutoffs ordered. Current foundation does not claim correction for research-search multiplicity. | Fold semantics fixed in Stage 0. | Search-aware trial ledger / multiple-hypothesis control remains mandatory before broad automated discovery. |
| 6 | calibration/uncertainty | `WorldStateGraph.infer`; confidence tests | RESIDUAL_STAGE1_REQUIRED | non-blocking by design | Current confidence is an explicit heuristic, not a calibrated probability. No calibration claim is made. | Preserve epistemic labels. | Stage 2 must add decomposed confidence, calibration, staleness, and abstention. |
| 7 | causal claims | `Transmission`, inference mechanism metadata, design spec | RESIDUAL_STAGE1_REQUIRED | non-blocking by design | Transmission edges are declared mechanisms; foundation does not claim causal identification. | No causal promotion added. | Stage 4 must add causal falsification / identification gates before stronger causal language. |
| 8 | contradiction handling | cross-source contradiction test and latent inference test | PASS | — | Opposite sources remain separately identified; inference preserves both event IDs, neutralizes equal/opposite evidence, and lowers confidence below individual source confidence. | Strengthened integration proof. | Stage 1 provenance DAG must detect common upstream ancestry. |
| 9 | source-health/quota behavior | current adapter surface and v2 spec | RESIDUAL_STAGE1_REQUIRED | non-blocking by design | Stage 0 intentionally wires no external provider into product code. | None in Stage 0. | Stage 1 Source Capability Registry must encode quotas, freshness, revisions, outage behavior, and fallback semantics before adapters are enabled. |
| 10 | negative-control/relevance | source policy, current product imports, user-tagged provider set | RESIDUAL_STAGE1_REQUIRED | non-blocking by design | Irrelevant or unclassified providers were not silently treated as market evidence; no tagged provider was auto-wired merely because it was available. | Capability selection stayed minimal. | Stage 1 registry must explicitly classify relevance, evidence class, and negative controls. |
| 11 | adversarial robustness | hostile JSON, URL, replay, hash/model, revision/future-time, duplicate observation, bad numeric/timestamp tests | PASS | — | Existing foundation rejects malformed, future-leaking, replayed, duplicated, and non-finite inputs across multiple layers. | Stage 0 added temporal/boundary regressions. | Adapter-specific adversarial cases arrive with each Stage 5 adapter. |
| 12 | test quality/mutation resistance | real RED -> GREEN sequences for timing, fold reuse, CLI argument order, console encoding; final full suites | FIXED_AND_PASS | — | Tests demonstrably killed real defects rather than merely asserting current implementation shape. | Added focused regressions and a four-version matrix. | Dedicated mutation-testing tooling is optional future hardening, not a Stage 0 blocker. |
| 13 | performance/complexity | Python 3.11 `--durations=20` in run `36071102061` | PASS | — | Slowest test 1.35s; no OMNIVISION test in slowest 20. No Stage 0 performance regression observed in CI. | Added duration visibility to Stage 0 workflow. | `WorldStateGraph.contradictions` is pairwise within buckets; large-scale adapter ingestion needs bounded/cached Stage 1+ design. |
| 14 | backwards compatibility | final native Linux/Windows workflow; Python 3.10–3.13 full suites; branch delta | PASS | — | Full engine tests pass across four Python versions; native Linux and Windows jobs pass. Stage 0 product edits are narrowly scoped. | Fixed pre-existing CI portability defects uncovered by the audit. | New Stage 1 interfaces must preserve current contracts or version them explicitly. |
| 15 | execution separation | AST boundary test; candidate/hypothesis authority tests; branch delta | PASS | load-bearing | Research modules do not import execution surfaces; candidate output is always `execution_authorized=false`; hypotheses reject `True`. Pulse was not changed by Stage 0. | Added executable boundary tests. | None permitted: this remains an owner-hard invariant. |
| 16 | documentation/resumability | approved spec; Stage 0 plan; this audit; `.icarus_loop/state.json`; GitHub commits/runs | PASS | — | Objective, implementation evidence, failures, fixes, residual gaps, and next action are reconstructable from the repository. | Audit plus final loop checkpoint. | State must continue to be updated delta-first each cycle. |

## Fresh Whole-Delta Review

Review focus:

1. **Temporal semantics:** receipt is authoritative for local knowability; publication cannot make evidence locally available earlier; fractional receipt times round availability forward.
2. **Provenance/revision:** ledger event IDs survive projection and inference; historical replay does not import later revisions.
3. **Walk-forward semantics:** fold boundaries are disjoint; cutoffs are strictly increasing; availability still gates each pair.
4. **Execution separation:** no Stage 0 path introduced broker/Pulse/order/process/network dependencies into OMNIVISION.
5. **Test validity:** the audit produced multiple independent RED states before fixes; final green is not based on deleted/weakened tests.
6. **Spec/plan conformance:** Stage 0 did not implement the Source Capability Registry, Trial Ledger, calibration layer, domain adapters, or integration governor prematurely.

**Reviewer capability note:** no independent child/subagent lifecycle tool was exposed by the active harness. The approved fallback was used: fresh whole-delta reread + GitHub compare + independent native and Stage 0 workflows. No unavailable reviewer is claimed.

**Review verdict:** `SHIP_STAGE0_GO`

## Residual Stage 1+ Requirements

These are explicit design-stage gaps, not hidden Stage 0 failures:

1. Source Capability Registry with access class, timing semantics, freshness, revisions, quota/outage policy, source-health state, and prohibited-use metadata.
2. Provenance DAG capable of representing common upstream ancestry so multiple vendors cannot masquerade as independent evidence.
3. Search-aware Trial Ledger with hypothesis-family identity and multiple-testing/search-budget controls.
4. Decomposed uncertainty, empirical calibration, staleness decay, and abstention.
5. Stronger novelty/redundancy tests beyond Pearson correlation.
6. Regime/changepoint and causal-validation layers.
7. Authorized domain adapters only after registry classification.
8. Proof-carrying candidate/governor layer that binds validation artifacts rather than trusting caller-supplied summary mappings.

## Stage 0 Final Verdict

**Verdict:** `GO`

**Verified implementation head:** `511814e1d4f4a2527abaa3b6e3472a66df666281`  
**Compile evidence:** `python -m compileall -q icarus_engine tests_engine` — success on Python 3.10, 3.11, 3.12, and 3.13 in run `36071102061`.  
**Focused regressions:** success on all four Python versions in run `36071102061`.  
**Full engine tests:** `python -m pytest tests_engine -q` — success on all four Python versions in run `36071102061`; native Linux job also success in run `36071102460`.  
**Windows:** native Windows job success in run `36071102460`.  
**Performance visibility:** `python -m pytest tests_engine -q --durations=20` — success on Python 3.11; slowest test 1.35s; no OMNIVISION test in slowest 20.  
**Review:** `SHIP_STAGE0_GO` using the documented native fallback because no independent child lifecycle tool was exposed.  
**Blocking findings:** none.  
**Execution authorized:** `false`.  
**Next permitted action:** write the Stage 1 Source Capability Registry + Provenance DAG + Search-Aware Trial Ledger implementation plan. Stage 1 implementation remains gated by that plan.
