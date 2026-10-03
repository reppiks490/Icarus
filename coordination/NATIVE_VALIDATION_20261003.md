# Native contract validation and domain-result handoff

## Scope and ownership

Continue the existing ASCENDANCY evaluator/governor rather than creating a second
scientific ledger. Open PRs #297, #296, #295 and #198 retain their existing lanes.
Private ARGUS #49 is reviewed but its hosted jobs still fail before assignment.
The user authorized autonomous implementation of the remaining integration work.

## Design

An independent fixed Python subprocess handles CONTRACT_VALIDATION only. No
candidate-supplied executable code is invoked. Its checks cover canonical
candidate/contract identity, declared falsifiers, observation declarations,
local source revision presence and source remote matching. A local Git object
and configured remote do not attest authorship or scientific validity.
Unavailable observations or unverifiable revision produce INCONCLUSIVE. Passing
these structural checks advances only to SMOKE_NULLS. It proves neither market
edge nor observation availability, and grants no qualification/trading authority.

The parent bounds each cycle's candidates and each child's elapsed time/input,
records measured elapsed time and evaluations with zero provider cost, and uses
the common no-console Windows launch options. A durable run intent prevents
concurrent duplicate execution. The completed result and exact evaluator receipt
are persisted before submission; restart resumes an unfinished submission using
the same receipt identity. An interrupted intent without a result remains visible
and requires review rather than silently re-running unaccounted work.
Rejected submissions are marked BLOCKED for review and do not monopolize the
bounded recovery queue; other completed PENDING receipts can still be accepted.

The service runs independently alongside the existing administrative autopilot.
Each cycle queries at most four eligible candidates through an indexed ledger
window; it does not load historical evaluator receipts. Each candidate's Git
checks and fixed child share a two-second deadline limited by its remaining
budget. Set `ICARUS_ASCENDANCY_NATIVE_VALIDATION=0` before starting the server to
disable automatic cycles; authenticated explicit cycles remain available.
Authenticated HTTP permits an explicit bounded cycle and status reads. The
dashboard shows actual runs, outcomes, submission state and unresolved intents.
It does not expose arbitrary commands, caller-supplied PASS results or higher
scientific stages through this worker.

The work-order board reads the existing accepted evaluator ledger. A receipt
must match the candidate's source, evaluation contract and stage; its semantic
identity is checked before projection. PASS or FAIL resolves that stage handoff,
while INCONCLUSIVE remains open. Claims alone never complete work. No new
completion authority or independent scientific evidence is minted by the board.

## Verification plan

Reproduce the board's hard-coded zero completion using accepted PASS/FAIL cases.
Exercise the real subprocess with valid local Git revision, unknown revision and
unavailable observation. Check replay/restart, pending-submission recovery,
interrupted intent, timeout, resource bounds and refusal of later stages. Exercise
authenticated HTTP and dashboard rendering, then independent review and exact
published-head Linux/Windows CI before merge.

Scientific replay/null testing, mechanisms, contribution, protected holdouts,
F4D3 reconstruction and direct DAEDALUS research intake remain subsequent tasks
requiring their own attributable inputs and independently validated outcomes.

## Implementation verification

Before the runtime reset, 66 native/evaluator/work-order/HTTP tests and 74
dashboard/intelligence tests passed. The resumed runtime has no pytest and blocks
package downloads from files.pythonhosted.org; no completed full-suite local run
is claimed. Fresh checks passed Python compilation, shipped JavaScript parsing,
and a real temporary Git checkout through authenticated HTTP, the actual child,
accepted evaluator receipt, completed work order and duplicate-free repeated
cycle. The shipped dashboard's Node behavior probe also passed rendering and
failed-fetch clearing. Exact published-head Linux and Windows CI remains the
full-suite gate. Existing owners #297/#296/#295/#198 remain untouched.
