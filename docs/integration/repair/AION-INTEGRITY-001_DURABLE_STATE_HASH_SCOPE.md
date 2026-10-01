# AION-INTEGRITY-001 — durable-state tamper-evidence scope

Pinned AION revision: `12a7cb8ef99e84ce50b766db0aea1592b3906f80`.

## Observed controls

The pinned store:
- canonicalizes and hashes source manifests;
- chains each event hash to the previous event hash;
- recomputes that chain in `verify_chain()`;
- enforces immutable SQLite rows for events, source-gap history, predictions, and settlements through no-update/no-delete triggers;
- freezes prediction evidence via event/gap ledger cutoffs and a frame hash.

## Scope gap

`verify_chain()` verifies source manifests and the `events` ledger. Separate durable state in `source_gap_history`, `predictions`, and `settlements` is not included in that same cryptographic chain. Immutability triggers prevent ordinary SQL update/delete operations but do not, by themselves, establish end-to-end tamper-evident provenance equivalent to a hash chain.

## Required design decision

Choose an explicit integrity model before implementation. Acceptable directions include:

1. one global append-only integrity ledger that commits events, gap transitions, predictions, and settlements in deterministic canonical order; or
2. independent typed hash chains for each durable family plus a signed/hashed checkpoint binding their heads; or
3. another design with equivalent deterministic verification and replay semantics.

The design must preserve:
- existing event hashes or provide an explicit versioned migration;
- deterministic replay and frozen-frame reconstruction;
- as-of semantics and gap cutoffs;
- idempotency and immutable prediction IDs;
- fail-closed verification on corruption;
- `execution_authorized=false`.

## Required tests

- mutate a prediction/settlement/gap-history record through a low-level test seam and verify the integrity verifier detects it;
- verify legitimate append-only operations retain deterministic head hashes;
- verify frozen prediction frames still reconstruct identically;
- verify legacy DB handling is explicit (version/migration/rejection), never silently reinterpreted.

## Current status

Confirmed integrity-scope finding. New architecture is DESIGN_AWAITING_APPROVAL; no AION source mutation is included here.
