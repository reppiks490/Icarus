# Capability & Data Discovery Registry — foundation

The registry imports discovery metadata from exactly `cporter202/API-mega-list`,
`cporter202/scraping-apis-for-devs` and `cporter202/ai-agent-tools`. It is an offline
engine plus a bounded public-GitHub intake CLI, not a source downloader or strategy.

**DISCOVERED does not mean qualified.** Catalog copy, sponsored placement and
passing software tests are not market evidence, source quality, point-in-time
coverage or alpha. Unknown license/ToS stays unknown; ordinary entries require
review. Explicit circumvention, credential-theft and malware claims are rejected
but remain auditable. AI-tools are capability-only; opaque predictions remain
challenger-only, never observed facts or trade instructions.

All outputs are research/shadow only: `execution_authorized=false` and
`production_decision_authorized=false`. No automatic production promotion,
broker/order/sizing changes, purchases, metered calls or discovered-service probes.
The foundation does not expose HTTP, MCP, or dashboard surfaces yet.

## Intake and replay

```bash
python -m tools.catalog_registry_ingest --catalog all --run-id manual-YYYYMMDD
python -m tools.catalog_registry_ingest --catalog api-mega-list --run-id manual-YYYYMMDD-api
```

Use unique run IDs; existing cycle receipts cannot be overwritten. `--root PATH`
selects the data directory. Configuration must match the three approved sources.
No provider credentials are read. Resolve an immutable 40-hex commit first, fetch
its README, reject files over 20,000,000 bytes. Redirects cannot escape the host
boundary. Snapshot provenance: repository, commit, path, raw SHA-256, parser
revision, UTC retrieval time and parse counts/failures.

Same pinned content/parser imports idempotently and preserves the first retrieval
time. A new parser revision creates a distinct parse identity. Hash mismatch writes
nothing; malformed rows/URLs produce hashed failure records. Imports are atomic:
a persistence fault rolls back the whole snapshot. SQLite uses WAL and foreign
keys; qualification events are append-only and transitions adjacent, never jumps.
Exact per-snapshot summaries are retained so later global family updates cannot
rewrite old receipts. Metadata replay cannot reset qualification or manual policy.

Separate observations keep candidate IDs, original URLs and all entry/snapshot
links. Referral/tracking variants share structural ancestry with one effective
independent lineage per family, without deleting records. Meaningful query
parameters remain distinct. Semantic similarity never auto-merges. Unchanged rows
in a new catalog commit add provenance links to existing candidates. Sponsored
headings cannot raise source quality or policy authority.

## Read-only provider federation

Provider federation is read-only. It reads the existing
`config/provider_endpoint_catalog.json` and local
`automation_intelligence/provider_collection_v1/latest/*.json`, not raw vendor
payloads. It never calls/imports the collector as an acquisition function, creates
jobs or makes provider HTTP requests.
The CLI invokes federation when its root contains the existing endpoint catalog;
absent evidence is explicit, not fabricated successful access.

```python
from pathlib import Path
from icarus_engine.discovery_registry import DiscoveryRegistryService

service = DiscoveryRegistryService(Path("."))
try:
    result = service.federate_existing_providers(
        Path("config/provider_endpoint_catalog.json"),
        Path("automation_intelligence/provider_collection_v1/latest"),
    )
finally:
    service.close()
```

Matches use exact admitted domains then exact canonical provider names, never
fuzzy or host-suffix matches. A link is retained only when the candidate URL path
matches the catalog operation path. Name-only wrappers and provider-level receipts
can preserve ancestry, but do not prove candidate access. Links retain exact receipt
path/SHA-256. Access evidence also requires the approved collector's HTTPS API
origin and effective port 443. Provider marketing domains retain ancestry links
but cannot borrow access evidence from the API host. HTTP, alternate ports and
non-admitted `www` variants cannot qualify. The origin allowlist in
`federation.py` matches the origins of
`tools/provider_exhaustive_collection.py:PROVIDERS`; a collector origin change
requires a reviewed update to this mapping.
Operation-specific blockers retain allowlisted reason codes without collector
messages, credentials or raw payloads. A provider-level positive receipt cannot erase
an operation's denial or establish its entitlement. Bytes are revalidated before an
event; malformed, wrong-provider, future, missing, more-than-six-hour-old,
credential/auth-blocked, quota-paused and denied-only evidence cannot advance.
`DISCOVERED -> ACCESS_TESTED` additionally requires `substantive_work_performed: true`
and an exact operation ID in the provider receipt's `verified_operations` list, with
no blocker for that operation. Aggregate page counts without that operation-level
success evidence remain links only. Rejected/restricted candidates do not advance.

For operations sharing a provider, method and path, required query examples that
distinguish their catalog descriptors must match exactly one occurrence in the
candidate URL. For example, a verified Bybit `category=spot` operation cannot
qualify `category=option`, a missing/empty category, or duplicate category fields.
An ID-qualified singleton still requires its declared query binding. Missing or
indistinguishable variant descriptors retain ancestry but cannot establish access.
Ordinary query values such as an asset symbol are not inferred to be variant
identifiers. Access remains operation-level evidence, not proof of every asset,
query combination, historical interval or entitlement.

Federation revision `registry-federation-v4` retains the API origin and query
bindings on new links/events and rejects legacy links lacking these checks.
Imports preserve immutable history: this change does not rewrite an earlier
`ACCESS_TESTED` event or demote an existing candidate automatically. Consumers
requiring current provenance must requalify historical v3 evidence under v4.

## Storage and safe receipts

| Location | Purpose | In git? |
|---|---|---|
| `research/capability_registry.sqlite3` | Registry and audit state | No |
| `.catalog_registry_cache/raw/<catalog>/<commit>/<sha256>.md.gz` | Pinned public README replay bytes | No |
| `automation_intelligence/catalog_registry_v1/cycles/<run-id>/receipt.json` | Immutable bounded cycle result | Yes, explicit allowlist |
| `automation_intelligence/catalog_registry_v1/latest/<catalog>.json` | Last successful summary | Yes, explicit allowlist |

Receipts contain provenance, counts, safe error codes, authority-false flags,
`chatgpt_tokens_used=0` and `paid_model_calls=0`; no raw rows/descriptions,
credentials or exception messages. Failed fetches leave successful latest files
untouched. Explicit credential-bearing URL/header/assignment content rejects the
catalog before raw-cache or registry persistence; only a safe failure code is
recorded. Detection is a conservative safeguard, not a guarantee that arbitrary
unlabeled strings can be recognized as secrets. Quoted assignments and common
key/token aliases are covered; generic public asset `token` parameters are not
treated as credentials. Existing gzip caches are bounded-decompressed and
hash-verified; pinned bytes repair corrupt caches atomically. A catalog with no
importable entries fails with `UNRECOGNIZED_CATALOG_FORMAT`, not a successful
empty refresh. Its hashed parse audit may remain locally, but no successful
latest receipt is written. Partial/failed cycles retain receipts and return
nonzero CLI status.

The CLI parser revision is `catalog-registry-v3`: balanced link targets/labels,
optional Markdown titles, featured linked headings and malformed one-cell table
rows are now handled without changing an old snapshot's parse identity.

## Refresh and verification

The proposed workflow runs at 04:37 UTC daily and supports manual dispatch on main
after review/merge. Publishing the draft does not activate it. It tests offline
before fetching, caches only local replay/closed DB state, uploads only the
bounded receipt, and stages only receipt/latest JSON. Out-of-scope staging aborts;
it never force-pushes or rebases shared history.

```bash
python -m pytest tests_engine/test_discovery_registry_*.py -q
python -m pytest tests/test_catalog_registry_ingest.py tests/test_provider_exhaustive_collection.py -q
python -m pytest tests_engine -q
```

Tests use offline synthetic/adversarial fixtures and injected fetchers. Passing
tests does not imply a live import, production readiness or market performance. Actual
retrieval success needs its pinned cycle receipt. Approved spec/plan and Atlas
execution/rulings are under `docs/superpowers/`. Qualification/source health,
point-in-time exogenous empirical evaluation, operator surfaces and explicit
promotion decisions remain separate future plans.
