# Official DBN parser fixtures

Source commit, immutable URLs, Git blob IDs and SHA-256 hashes are in manifest.json. LICENSE is the upstream Apache2 license. Four tiny official fixtures were downloaded from databento/dbn, verified against their Git blob hashes, then decoded with the already-installed Databento SDK and normalized through Icarus Databento._event_record / _ohlcv_record. All8 records decoded and normalized; results are in adapter-validation.json.

These are parser compatibility fixtures, including DBN v3, not a historical corpus, complete book, current quote source or provider entitlement. They do not enter runtime history, warmup, paper signals or execution. Raw DBN bytes retain the original metadata and nanosecond fields; normalized observations preserve Icarus's existing event contract.

Reproduce from the candidate root with its configured interpreter and Databento optional dependency: `python docs/recovery/cloud-audit-20261026/external-fixtures/databento-dbn/validate.py`. The command verifies every pinned file hash before decoding and makes no network requests.
