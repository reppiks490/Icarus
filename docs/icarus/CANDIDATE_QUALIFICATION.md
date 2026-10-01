# Candidate Qualification Proof Ledger

ICARUS research candidates enter the Adaptive Brain as `validated`, not
`qualified_shadow`.  This is deliberate: local train/validation/holdout work
does not prove every promotion gate.

The qualification ledger is an append-only, hash-chained evidence layer bound to
the exact candidate ID, source repository, and 40-character source commit.
Receipts may pass or fail one gate. Later receipts supersede earlier state without
rewriting history, so new adverse evidence can revoke shadow eligibility.

A candidate becomes `qualified_shadow` only when all eleven gates are true:

- causal time
- provenance
- out-of-sample validation
- protected holdout
- multiple-testing discipline
- costs/slippage/latency realism
- ablation
- calibration
- OOD/drift robustness
- deterministic replay
- independent verification

Independent verification requires at least two distinct independent reviewers by
default, with the final independent-verification pass restricted to AEGIS,
ASCENSION, or DAEDALUS roles.

Qualification remains **shadow-only**.  The ledger cannot authorize a production
decision, mutate live strategy state, arm a broker, or place an order.
