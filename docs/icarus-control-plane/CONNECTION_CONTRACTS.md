# ICARUS Connection Contracts

This document defines the minimum handshake required before another ICARUS subsystem, sibling repository, agent, or external data provider may connect to the shared research/control fabric.

## Universal connection envelope

Every connected producer MUST expose enough information to populate:

```text
component_id
canonical_repository
immutable_revision
schema_version
responsibility
owned_inputs
owned_outputs
event_time_semantics
observation_time_semantics
available_at_semantics
ingested_at_semantics
revision_semantics
source_identity
provenance_identity
uncertainty_semantics
failure_semantics
deterministic_replay_contract
execution_authorized=false
```

Missing load-bearing fields => connection state `UNVERIFIED`.

## Evidence envelope

External evidence must retain:

```text
evidence_id
provider_id
source_record_id
asset
instrument
contract
venue
observation_type
value
unit
event_time
source_timestamp
available_at
observed_at
ingested_at
revision
quality_flags
synthetic
authority_class
upstream_source_ids
provenance_hash
```

Instrument identity is never collapsed merely for convenience:
- GC futures != MGC futures != XAU/USD != gold spot != GLD
- BTC/USD spot != BTCUSDT perpetual != CME BTC futures

## Connection states

```text
UNVERIFIED
SPECIFIED
CONNECTED_RESEARCH_ONLY
VERIFIED_FOR_INTEGRATION
BLOCKED
INVALIDATED
```

No state grants order execution.

## AION -> ICARUS / OMNIVISION

AION may supply time/identity/replay evidence only when source/gap history integrity is verifiable.
Required:
- source identity
- event/publish/availability/ingestion clocks
- immutable revisions
- gap/recovery state
- replay cutoffs
- evidence tier
- integrity-chain status

Open blocker:
- replay-significant `source_gap_history` must participate in deterministic integrity verification.

## DAEDALUS -> OMNIVISION

DAEDALUS may supply research candidates/evidence only when protected exposure lineage survives dataset descendants.
Required:
- stable `source_lineage_id`
- immutable snapshot SHA
- protocol hash
- train/validation/holdout boundaries
- prior protected exposure references
- search/trial family identity
- costs/slippage assumptions where applicable

Open blocker:
- append-only descendants must not recycle previously exposed protected observations into development evidence.

## ARGUS -> ICARUS

Current canonical implementation unavailable.
Do not infer responsibilities beyond preserved evidence.
Admission requires:
- canonical repo/revision
- source-manifest identity separate from event hashes
- venue/representation semantics
- sequence/gap/recovery state
- evidence-tier restrictions
- tests rejecting ambiguous provenance

## ATHENA -> ICARUS

Current canonical implementation unavailable.
Admission requires:
- canonical repo/revision
- contributor lineage for every uncertainty-relevant aggregate
- explicit abstention semantics
- proof that degraded/incomplete evidence never increases authority

## NEXUS / ORACLE -> ICARUS

No canonical repository was discovered in the latest installed-repository search.
No adapter should be invented from names alone.
Connection requires canonical repository, immutable revision, responsibility, I/O contracts, timing/provenance, uncertainty, replay, and regression evidence.

## OMNIVISION Stage 1

Stage 1 is the planned governance layer:
- immutable source capability versions
- provenance DAG
- search-aware trial ledger
- governed evidence gateway

It MUST remain provider-agnostic during Stage 1.
Provider adapters belong later, after the control plane is executable and verified.

## Market-data vintage -> OMNIVISION provenance

PR #19 supplies a useful raw observation/revision ledger.
Before it becomes a load-bearing provenance root, add:
- deterministic cryptographic integrity verification
- authenticated head/chain state
- explicit full-history as-of reconstruction
- tamper regressions
- stable linkage from canonical history rows to recorded vintage observations

## Control receipts -> all agents

The S1->S5 control-receipt chain may coordinate authority/maturity only.
It must never:
- fabricate evidence,
- grant trading authority,
- bypass missing provenance,
- override canonical repo evidence,
- count duplicate summaries as independent replication.

## Provider admission

A provider is admitted only after a versioned capability record exists:
- access class
- auth/entitlement
- health
- quota/rate state
- timing semantics
- revision semantics
- cost/reliability
- allowed assets/entities
- forbidden uses
- upstream-source identity
- relevance class

Installed != reachable != entitled != relevant != independent != authoritative.
