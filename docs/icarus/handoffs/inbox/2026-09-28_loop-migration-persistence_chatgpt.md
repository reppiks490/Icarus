# Loop Migration / Durable Persistence Architecture — historical loop handoff

SOURCE_LOOP=Loop Migration / Durable Persistence Architecture
PRODUCER=ChatGPT historical-loop migration
CAPTURE_DATE=2026-09-28
PINNED_REPO_REVISION=e3df09a02681f2605eff7c088bfcffc8cc5daac8
EXECUTION_AUTHORIZED=false
SENSITIVITY=PUBLIC_SAFE
CLASSIFICATION=NEW_WORKFLOW
SNAPSHOT_STATUS=MIGRATION_DIRECTIVE
OWNERSHIP=Repo-native continuity for all legitimate loops

## Primary objective
Remove historical ChatGPT conversations, individual models and individual machines as single points of continuity. Repository state, workflow definitions, event history, provenance and execution fabric become durable truth.

## Master recovery contract
For every legitimate loop recover:
- conversation exports and generated artifacts;
- repo commits and latest verified checkpoint;
- current/last prompt, enabled state and schedule where evidence exists;
- state capsule/handoff;
- ownership/dependencies/downstream consumers;
- overlaps/conflicts;
- recoverable missing runs;
- classification as independent worker, extension, sub-worker, workflow, specialized pipeline, shared capability, governance component, historical reference or duplicate/superseded implementation.

## Durable run contract
A productive run should:
1. assign deterministic RUN_ID;
2. load prior state/watermarks;
3. collect/build/validate;
4. write machine-readable artifact;
5. update the owned STATE_CAPSULE;
6. append immutable history;
7. commit/push;
8. re-read remote;
9. verify commit SHA/file state;
10. report REPO_WRITE=VERIFIED only with proof.

Failed auth/write:
- REPO_WRITE=BLOCKED;
- retain output for replay;
- never claim persistence.

## Repository-native target
For every legitimate persistent workflow, the master handoff calls for systems/<system>/spec/ containing mission, scope, ownership, operating rules, inputs/outputs, continuation/state/model/tool/routing/dependency/quality/persistence/replay policies.

This historical migration import does not itself instantiate or enable those autonomous workers.

## Safety / licensing
- never commit secrets/private keys/credentials/private personal data;
- PUBLIC repos accept only PUBLIC_SAFE summaries;
- raw licensed/proprietary data stays out unless redistribution rights are established;
- UNKNOWN_SENSITIVITY is fail-closed;
- prefer manifests, hashes, schemas and storage pointers for large/restricted datasets.

## Continuity rule
Paused loops are not automatically obsolete. Active loops are not automatically authoritative. Newer repo checkpoints may not be overwritten by older chat artifacts.

## Preservation boundary
This is durable historical state, not execution authorization. Repository evidence outranks chat summaries; sibling systems remain isolated; failed attempts and blockers remain evidence.
