# Historical projection continuation — 2026-10-03

Continues existing PR #301 at adcacfd6480d754b1e933f96ea91fccff9c39300.
Integrates canonical main 00ce67618afb7fc379b561e56bdc35d89eb0b96e,
including qualified Spine #308 and governor #302. No parallel projection verifier
or governor implementation was introduced.

The test merge retains both original projection-substitution regressions and
main's prior-packet acknowledgement regressions. Dashboard wording preserves
historical evidence classifications and packet-source verification while adding
separate source-derived projection proof.

Independent review found a source-semantics gap: verified pinned source blobs
could claim RUN_CORE execution authority, root/core trading authority or invalid
flow collection semantics and still receive projection proof. Four regressions
reproduced GREEN for these invalid source documents before the fix. Live-source
and pinned-source verification now share those semantic guards; invalid packets
degrade with zero projection proof while unrelated research events remain usable.
No execution, production or candidate-evidence authority is granted.

Qualification: 125 targeted tests across Brain, remote sync, dashboard and
canonical federation acceptance passed. Independent re-review found no remaining
Critical/Important defect in the reviewed seam.

The actual workflow script also verified four historical source projections
against exact Git blobs at the cached peer snapshot, with its test clock anchored
to that packet's observed_at. This is historical content/contract verification,
not proof of current freshness. Running the same gate at the actual current time
correctly rejected the cached packet beyond the existing 1800-second threshold.
No production freshness guard was weakened. Exact-head hosted tests and current
peer qualification remain required before merge; the producer's refresh workflow
is already active and is not duplicated here.

Remaining handoff boundaries: scientific experiment execution/outcomes, verified
comparability/native source adapters, F4D3 reconstruction from attributable data,
direct ARGUS research intake into DAEDALUS, full-archive stress evidence and the
user-instance Windows/UI qualification. ARGUS driver CI coverage is prepared in
private repository PR #49; its hosted jobs failed before runner assignment and
remain unqualified. Open subsystem contract/federation work retains its owners.
