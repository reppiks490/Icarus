# External quant research catalog — read-only quarantine auditor

**Status:** isolated research metadata contract only, stacked on draft Icarus PR #486. No provider calls, dataset downloads, live/paper broker changes, training, model promotion, Brain ingestion or UI integration. The auditor checks caller-provided artifact bytes and metadata; it cannot independently prove that a source commit, license, rights, or market data are authentic.

## Offline contract

Prepare an isolated local directory containing `catalog.json` and already-authorized artifacts. The catalog must have exactly these top-level keys:

```json
{
  "schema_version": "icarus-external-quant-catalog-v1",
  "producer_repository": "reppiks490/Icarus",
  "producer_revision": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "artifacts": [{
    "artifact_id": "independent-raw-contract-candidate",
    "path": "research/contract-bars.csv",
    "sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "size_bytes": 1234,
    "source_repository": "microsoft/qlib",
    "source_revision": "cccccccccccccccccccccccccccccccccccccccc",
    "license_id": "MIT",
    "rights_verified": false,
    "source_authenticity_verified": false,
    "holdout_approved": false,
    "execution_authorized": false
  }]
}
```

**The values above are placeholders, not an actual inventory or verification receipt.** All four authority flags must be exactly `false`, not absent or truthy. A license label is a claim requiring independent legal/usage review, not permission to copy, redistribute or train on third-party data. The `source_repository` and `source_revision` identify the declared external code or producer; the catalog does not clone or execute it. Every artifact is hashed in full, without sample caps. Unsafe/hidden/absolute/traversal paths, symlinks, duplicate identifiers/paths/JSON keys, wrong sizes or hashes, invalid commit IDs, and unknown schema fields are rejected. Keep proprietary vendor payloads outside public Git and only under approved local/vault paths.

Run using an independently established, immutable producer identity:

```bash
python -m icarus_engine.external_quant_catalog \
  --root /authorized/quarantined/catalog \
  --producer-repository reppiks490/Icarus \
  --producer-revision <FULL_40_CHARACTER_GIT_COMMIT>
```

This emits a metadata-only JSON receipt with artifact count, bytes fully rechecked, distinct declared source revisions and the manifest hash. Every receipt is `research_admission=QUARANTINED`, `authority_granted=NONE`, `training_approved=false`, `execution_authorized=false`, `entitlement_verified=false`, `source_authenticity_verified=false` regardless of a successful hash check. Nothing is written. A structural check is not a data-licensing, completeness, timeliness, as-of, holdout, or broker-fill validation.

## Evidence and next gates

Offline tests use **synthetic temporary files** exclusively. No downloaded local Windows/WSL2 repositories, vendor dataset, real Qlib dump, RD-Agent chat/embedding endpoint, HFTBacktest queue, Nautilus instrument, or broker was accessed. Before linking this to Brain/gauges or Qlib, independently inventory actual external repository URLs, exact revisions and license texts, authenticate source/data rights, validate canonical evidence records, and require explicit research admission with separate holdout approvals. Never convert the quarantine receipt into strategy or execution authority. This module is intentionally standalone until those gates exist.
