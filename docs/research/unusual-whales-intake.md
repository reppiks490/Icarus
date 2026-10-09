# Unusual Whales connector observation intake

The offline `icarus_engine.unusual_whales_intake.observe()` function connects an
exact connector response to ICARUS's native Brain learning journal. The native
`brain_snapshot()` consumer displays its compact source-integrity metadata. This
is an observation and audit boundary, with no HTTP transport, provider API key,
automatic scheduler, candidate admission, model training or broker action.

The [capability map](unusual-whales-capability-map.json) assigns the 100 exposed
connector tools exactly once across 19 families. Each family records useful
research scope, consumer boundaries, limitations, temporal requirements and
acceptance checks. Tool inventory coverage does not establish the complete
provider endpoint universe or account entitlement. Documentation, educational
answers, account preferences and workspace mutations are excluded from empirical
observation intake; their capabilities remain accounted for in the map.

The collector in `tools/provider_exhaustive_collection.py` uses repository REST
credentials and provider-specific encrypted licensing archives. Connector access
does not supply those credentials or permit adding Unusual Whales as a pretend
authenticated collector. This intake receives existing authorized connector
results through an explicit local call instead.

## Manifest and exact bytes

```python
from datetime import datetime, timezone
from pathlib import Path
from icarus_engine.brain import brain_snapshot
from icarus_engine.unusual_whales_intake import observe, resume_pending

# Existing authorized response bytes remain in the caller's private handling.
# The intake hashes these original bytes directly, without parsing/reformatting.
response = private_response_path.read_bytes()
manifest = {
    "observation_id": "uw-yield-curve-observation-001",
    "tool": "mcp__codex_apps__unusual_whales_get_yield_curve",
    "retrieved_at": actual_retrieval_timestamp,
    "parameters": {},
    "result_status": "OBSERVED",
}
runtime = Path(private_application_runtime_outside_git)
result = observe(runtime, response, manifest,
                 now=lambda: datetime.now(timezone.utc))
events = brain_snapshot(runtime)["events"]
```

The caller supplies actual tool identity, request parameters and retrieval clock.
The boundary cannot independently verify connector origin, response meaning or
the declared retrieval time; these remain explicitly caller-reported. It verifies
the exact response SHA-256 and size, finite bounded parameter metadata, aware
clocks, immutable observation identity, private persistence and native delivery.
Parameters are hashed in canonical JSON form and are never stored. Response bytes
are hashed in memory and are never copied into receipts or Brain events. An
optional `raw_sha256` manifest field must match the original bytes exactly.

Supported result states are `OBSERVED`, `EMPTY`, `DENIED`, `ERROR`,
`TRANSFORMED_ONLY` and `UNCLASSIFIED` (the default). Empty/chart-only responses stay
degraded, denial/error stays blocked, and unclassified responses stay unverified.
The caller's status classification is not a coverage or correctness certificate.
Optional `reported_row_count` is labeled caller-reported and unverified. Missing
values, entitlement, coverage and eligible-row denominators remain unknown.

Optional `source_observed_at` and `available_at` must be aware timestamps no later
than retrieval. Both remain `DECLARED_UNVERIFIED`; a source's historical date does
not prove when ICARUS could have known it. The intake never grants point-in-time
eligibility, candidate eligibility, production decision authority or execution
authority. It does not turn close-only prices, option prints or rendered charts
into replay-qualified OHLC bars. Future earnings/calendar occurrence dates belong
in the request/context, not in the source-observation generation clock.

## Private retention and recovery

Only `METADATA_ONLY` retention is supported. Retention, redistribution and training
rights remain `UNKNOWN`. Full raw retention requires a separately validated
rights witness and implementation; an asserted `LICENSED` field cannot activate
it. No raw payload, user account setting, storage identifier, credential or
request parameter value is written to the public capability map or native event.

The caller must choose a private application runtime outside a Git checkout.
Existing group/world-accessible runtime directories are rejected on POSIX. New
runtime and audit/intake directories use `0700`; the SQLite observation journal
and native Brain journal use `0600`. Symlinked database/audit directories or files,
and hard-linked journal/database files, are rejected. On Windows, the runtime
also needs owner-restricted filesystem ACLs; POSIX mode checks do not establish
Windows ACL privacy. The intake does not include any public publication step.

An observation is committed as `PENDING` in the private SQLite journal before the
native Brain append. A process-wide SQLite delivery transaction serializes intake
deliveries; the existing Brain API appends and fsyncs its idempotent event. Only
then does delivery become `DELIVERED`. A crash after the append leaves a pending
receipt; native event identity prevents a duplicate when resumed:

```python
recovered = resume_pending(runtime)
```

Reusing the same observation identity and semantic receipt is idempotent, including
after reopening the runtime. Different bytes, parameters, clocks, tool or status
under the same identity are rejected. A new actual retrieval uses a new identity;
these retrieval receipts do not establish independent underlying market evidence.

The synthetic regression suite tests exact-byte binding, no persisted raw/parameter
values, native Brain consumption, immutable conflicts, duplicate/reopen behavior,
failure before append and crash after append, concurrent retries, invalid clocks,
unknown rights/coverage/PIT, exclusion of non-empirical tools, private permissions
under a permissive umask and symlink escapes in both persistence planes.
