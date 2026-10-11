# ICARUS Capability & Data Discovery Registry Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the durable registry kernel, deterministic import path for all three approved discovery catalogs, non-destructive duplicate/policy handling, and read-only federation with ICARUS's existing exhaustive-provider acquisition evidence.

**Architecture:** The foundation is a metadata/control-plane subsystem under `icarus_engine/discovery_registry/` backed by SQLite WAL at `research/capability_registry.sqlite3`. Catalog network retrieval is isolated in `tools/catalog_registry_ingest.py`; the engine package itself imports already-fetched pinned content and never performs catalog network calls. Existing `provider_exhaustive_collection` remains the only acquisition engine for providers it already owns; federation reads its catalog/receipts and records links/evidence without creating downloader jobs.

**Tech Stack:** Python 3.10+, standard library (`dataclasses`, `enum`, `hashlib`, `json`, `sqlite3`, `urllib`, `gzip`, `re`, `unicodedata`), pytest, GitHub Actions. No new runtime dependency.

**Spec:** `docs/superpowers/specs/2026-10-11-capability-data-discovery-registry-design.md`

## Global Constraints

- Canonical implementation repository: `reppiks490/Icarus`; `reppiks490/Icarus-engine` remains a research/automation satellite.
- Authority is research/shadow only: `execution_authorized=false` and `production_decision_authorized=false` on every registry output.
- Production auto-promotion is forbidden.
- Import the complete discovery metadata universe; do not automatically execute/install/call discovered services.
- Exact upstream repository, 40-hex commit, path, content SHA-256, parser revision, and retrieval time are mandatory snapshot provenance.
- Catalog descriptions are untrusted metadata, not verified capability or market evidence.
- Unknown license/ToS/policy state fails closed as `UNKNOWN` or `REVIEW_REQUIRED`; it never auto-allows production use.
- Do not purchase subscriptions, credits, or metered calls; this plan performs no source qualification probes beyond fetching the three public GitHub catalog files.
- Do not bypass paywalls, authentication, robots/access controls, licensing restrictions, or technical restrictions.
- Do not persist credentials, authorization headers, tokens, passwords, or secrets in registry rows, receipts, logs, or committed artifacts.
- Existing provider acquisition must be federated, never duplicated.
- Missing values remain `null`/`UNKNOWN`; booleans are not numbers; NaN/Inf are rejected.
- Unit/CI tests are offline by default. Network behavior is tested through injected fakes.
- Raw catalog snapshot bytes and the SQLite registry remain local/cache data; committed automation artifacts contain bounded summaries/receipts only.

## Review Focus

1. **Pinned-revision race:** if upstream `main` changes after ref resolution, the fetch must still use the resolved 40-hex commit; Task 8 pins this with `test_fetch_uses_resolved_commit_not_mutable_ref`.
2. **URL identity corruption:** tracking/referral parameters must collapse duplicates without deleting meaningful query parameters; Task 2 pins this with `test_normalize_url_drops_only_known_tracking_parameters`.
3. **Unsafe marketing copy:** an entry advertising paywall/auth/access-control bypass must never become allowed merely because the parser imported it; Task 5 pins this with `test_explicit_circumvention_is_rejected`.
4. **Malformed/stale provider evidence:** bad or old provider receipts must not advance qualification state; Task 9 pins this with `test_malformed_or_stale_provider_receipt_cannot_advance_candidate`.
5. **Large/malformed catalogs:** a multi-megabyte README and malformed Markdown rows must produce bounded parse failures rather than crash or silently drop the import; Tasks 4 and 8 pin this with `test_malformed_rows_are_reported` and `test_fetch_rejects_payload_over_limit`.

---

## File Structure Locked by This Plan

### New engine package

```text
icarus_engine/discovery_registry/
    __init__.py          public foundation exports only
    contracts.py         finite enums, immutable value objects, authority invariants, lifecycle rules
    normalize.py         URL/name/domain normalization and deterministic candidate identity
    importers.py         three catalog parsers over already-fetched pinned Markdown
    policy.py            deterministic fail-closed catalog triage; no ToS guessing
    dedupe.py            exact/structural duplicate families; non-destructive ancestry
    store.py             SQLite WAL schema and append-only persistence
    federation.py        read-only links to provider endpoint catalog + latest provider receipts
    service.py           offline orchestration of import -> normalize -> policy -> dedupe -> persist -> federate
```

### New/modified tool + config + automation

```text
config/catalog_registry_sources.json

tools/catalog_registry_ingest.py

tests/test_catalog_registry_ingest.py

automation_intelligence/catalog_registry_v1/   # generated bounded receipts/latest summaries
.github/workflows/catalog-registry-refresh.yml
.gitignore
```

### New engine tests/fixtures/docs

```text
tests_engine/fixtures/discovery_registry/api_mega.md
tests_engine/fixtures/discovery_registry/scraping_apis.md
tests_engine/fixtures/discovery_registry/ai_agent_tools.md

tests_engine/test_discovery_registry_contracts.py
tests_engine/test_discovery_registry_normalize.py
tests_engine/test_discovery_registry_store.py
tests_engine/test_discovery_registry_importers.py
tests_engine/test_discovery_registry_policy.py
tests_engine/test_discovery_registry_dedupe.py
tests_engine/test_discovery_registry_service.py
tests_engine/test_discovery_registry_federation.py

docs/icarus/CAPABILITY_DATA_DISCOVERY_REGISTRY.md
README.md
```

No `server.py`, dashboard, MCP, exogenous feature, alpha/backtest, or production-promotion changes belong in this foundation plan. Those are separate implementation plans after this foundation interface lands.

---

### Task 1: Finite Contracts, Authority Invariants, and Lifecycle

**Files:**
- Create: `icarus_engine/discovery_registry/__init__.py`
- Create: `icarus_engine/discovery_registry/contracts.py`
- Create: `tests_engine/test_discovery_registry_contracts.py`

**Interfaces:**
- Produces enums: `SourceClass`, `DataClass`, `PolicyState`, `CostModel`, `QualificationState`, `Disposition`.
- Produces immutable dataclasses: `CatalogSnapshot`, `CatalogEntry`, `Candidate`, `QualificationEvent`, `PolicyDecision`, `DuplicateGroup`, `ProviderLink`.
- Produces `validate_sha256(value: str) -> str`, `validate_commit_sha(value: str) -> str`, `utc_iso(value: str) -> str`.
- Produces `assert_transition(old: QualificationState, new: QualificationState) -> None`.
- Every serialization helper produced here includes `execution_authorized=False` and `production_decision_authorized=False` and rejects caller attempts to set either true.

- [ ] **Step 1: Write failing contract tests**

Add tests with these assertions:

```python
def test_catalog_snapshot_requires_pinned_commit_and_content_hash():
    with pytest.raises(ValueError):
        CatalogSnapshot(catalog_id="api-mega", upstream_repo="cporter202/API-mega-list", upstream_commit="main", upstream_path="README.md", content_sha256="x", retrieved_at="2026-10-11T00:00:00Z", parser_revision="v1")


def test_authority_is_permanently_false():
    candidate = Candidate.minimum(candidate_id="a" * 64, canonical_name="Example", endpoint_or_tool_url="https://example.com")
    assert candidate.execution_authorized is False
    assert candidate.production_decision_authorized is False


def test_illegal_lifecycle_jump_fails_closed():
    with pytest.raises(ValueError):
        assert_transition(QualificationState.DISCOVERED, QualificationState.PRODUCTION)
```

Also pin rejection of bool-as-number, NaN and Inf for numeric candidate quality fields.

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests_engine/test_discovery_registry_contracts.py -q`

Expected: FAIL because `icarus_engine.discovery_registry.contracts` does not exist.

- [ ] **Step 3: Implement the contracts**

Implement the finite values exactly from the approved spec. `QualificationState` order is:

```text
DISCOVERED
ACCESS_TESTED
SCHEMA_PROFILED
LICENSE_TOS_CHECKED
LATENCY_TESTED
RELIABILITY_TESTED
DUPLICATE_CHECKED
HISTORICAL_DEPTH_TESTED
ALPHA_HYPOTHESIS_DEFINED
POINT_IN_TIME_BACKTESTED
SHADOW_MODE
PRODUCTION
```

`Disposition` is `ACTIVE|QUARANTINED|REJECTED|STALE|DEMOTED|RETIRED`.

`Candidate.minimum(...)` creates only a `DISCOVERED`/`ACTIVE` research candidate with unknown nullable qualification fields. Do not invent defaults for empirical scores.

- [ ] **Step 4: Run tests and verify pass**

Run: `python -m pytest tests_engine/test_discovery_registry_contracts.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add icarus_engine/discovery_registry tests_engine/test_discovery_registry_contracts.py
git commit -m "feat: add discovery registry contracts"
```

---

### Task 2: Deterministic Normalization and Candidate Identity

**Files:**
- Create: `icarus_engine/discovery_registry/normalize.py`
- Create: `tests_engine/test_discovery_registry_normalize.py`

**Interfaces:**
- Consumes: `SourceClass`, `DataClass`, `Candidate` from Task 1.
- Produces `NormalizedURL(original_url: str, identity_url: str, domain: str)`.
- Produces `normalize_url(url: str) -> NormalizedURL`.
- Produces `normalize_name(name: str) -> str`.
- Produces `canonical_provider_name(name: str, domain: str) -> str`.
- Produces `candidate_identity(*, canonical_name: str, identity_url: str, capability_kind: str) -> str` returning full lowercase SHA-256 hex.
- Produces `classify_data_class(category: str, description: str) -> tuple[DataClass, ...]` using conservative category/keyword mapping; uncertain entries include `DataClass.OTHER` rather than invented specificity.

- [ ] **Step 1: Write failing normalization tests**

```python
def test_normalize_url_drops_only_known_tracking_parameters():
    got = normalize_url("https://apify.com/acme/tool?fpr=abc&symbol=NQ&utm_source=x#top")
    assert got.identity_url == "https://apify.com/acme/tool?symbol=NQ"
    assert got.original_url.endswith("#top")


def test_tracking_variants_have_same_identity():
    a = normalize_url("https://apify.com/acme/tool?fpr=a")
    b = normalize_url("https://apify.com/acme/tool?fpr=b&utm_campaign=c")
    assert a.identity_url == b.identity_url
```

Also test host/scheme lowercasing, default-port removal, fragment removal from identity, stable query sorting, Unicode/emoji cleanup in names, and preservation of meaningful query parameters.

Known identity-only tracking keys are exactly: `fpr`, `ref`, `referrer`, `utm_source`, `utm_medium`, `utm_campaign`, `utm_term`, `utm_content`.

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests_engine/test_discovery_registry_normalize.py -q`

Expected: FAIL because normalization functions do not exist.

- [ ] **Step 3: Implement normalization**

Use `urllib.parse` and `unicodedata`. Reject non-HTTP(S) catalog URLs as invalid candidates rather than coercing them. Preserve original URL verbatim for provenance.

- [ ] **Step 4: Run tests and verify pass**

Run: `python -m pytest tests_engine/test_discovery_registry_normalize.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add icarus_engine/discovery_registry/normalize.py tests_engine/test_discovery_registry_normalize.py
git commit -m "feat: normalize discovery candidates deterministically"
```

---

### Task 3: SQLite WAL Registry and Append-Only Audit State

**Files:**
- Create: `icarus_engine/discovery_registry/store.py`
- Create: `tests_engine/test_discovery_registry_store.py`

**Interfaces:**
- Consumes contracts from Task 1.
- Produces `class RegistryStore` with constructor `RegistryStore(base_dir: Path)` and database path `base_dir / "research" / "capability_registry.sqlite3"`.
- Produces methods:
  - `record_snapshot(snapshot: CatalogSnapshot) -> None`
  - `record_entries(snapshot_id: str, entries: Iterable[CatalogEntry]) -> int`
  - `upsert_candidates(candidates: Iterable[Candidate]) -> int`
  - `link_candidate(candidate_id: str, entry_id: str) -> None`
  - `record_policy(decision: PolicyDecision) -> None`
  - `record_transition(event: QualificationEvent) -> None`
  - `replace_duplicate_groups(groups: Iterable[DuplicateGroup]) -> None`
  - `record_provider_links(links: Iterable[ProviderLink]) -> int`
  - `candidate(candidate_id: str) -> Candidate | None`
  - `candidates() -> list[Candidate]`
  - `summary() -> dict[str, object]`
  - `close() -> None`

The initial schema contains: `catalog_snapshots`, `catalog_entries`, `candidates`, `candidate_catalog_links`, `duplicate_groups`, `duplicate_members`, `qualification_events`, `policy_reviews`, `provider_links`.

- [ ] **Step 1: Write failing store tests**

Pin:

```python
def test_store_uses_wal_and_is_idempotent(tmp_path):
    store = RegistryStore(tmp_path)
    assert store.pragma_journal_mode() == "wal"
    store.record_snapshot(snapshot_fixture())
    store.record_snapshot(snapshot_fixture())
    assert store.summary()["catalog_snapshots"] == 1


def test_conflicting_same_snapshot_identity_fails(tmp_path):
    ...


def test_transition_history_is_append_only(tmp_path):
    ...
```

Also assert reopening the store preserves rows and authority flags deserialize false.

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests_engine/test_discovery_registry_store.py -q`

Expected: FAIL because `RegistryStore` does not exist.

- [ ] **Step 3: Implement store schema and methods**

Use foreign keys, WAL, bounded JSON with `allow_nan=False`, deterministic JSON key ordering, and unique constraints that make retrying the same import idempotent. `record_transition` calls `assert_transition` against the candidate's current state before appending and updating current state in the same transaction.

- [ ] **Step 4: Run tests and verify pass**

Run: `python -m pytest tests_engine/test_discovery_registry_store.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add icarus_engine/discovery_registry/store.py tests_engine/test_discovery_registry_store.py
git commit -m "feat: persist discovery registry audit state"
```

---

### Task 4: Deterministic Parsers for All Three Catalogs

**Files:**
- Create: `icarus_engine/discovery_registry/importers.py`
- Create: `tests_engine/fixtures/discovery_registry/api_mega.md`
- Create: `tests_engine/fixtures/discovery_registry/scraping_apis.md`
- Create: `tests_engine/fixtures/discovery_registry/ai_agent_tools.md`
- Create: `tests_engine/test_discovery_registry_importers.py`

**Interfaces:**
- Consumes `CatalogSnapshot`, `CatalogEntry` and normalization from Tasks 1-2.
- Produces immutable `CatalogImportResult(entries: tuple[CatalogEntry, ...], raw_count: int, parse_failures: tuple[dict[str, str], ...])`.
- Produces:
  - `parse_api_mega_list(snapshot: CatalogSnapshot, text: str) -> CatalogImportResult`
  - `parse_scraping_apis(snapshot: CatalogSnapshot, text: str) -> CatalogImportResult`
  - `parse_ai_agent_tools(snapshot: CatalogSnapshot, text: str) -> CatalogImportResult`
  - `importer_for(name: str) -> Callable[[CatalogSnapshot, str], CatalogImportResult]`

API Mega List and Scraping APIs parsers support Markdown tables of `API Name | Description` plus nearest heading/category. AI Agent Tools supports Markdown bullet entries of `[Name](url) - description` plus nearest heading/category. All three preserve source path and raw-row hash.

- [ ] **Step 1: Create representative offline fixtures and failing tests**

Fixtures must include:

- an Apify table row with `?fpr=`;
- a duplicated underlying URL with a different referral parameter;
- a malformed table row;
- an explicit paywall-bypass description;
- an AI-tools bullet entry;
- a sponsored/featured heading so parser metadata can preserve placement without treating it as quality.

Tests include:

```python
def test_all_three_importers_produce_entries(): ...
def test_malformed_rows_are_reported(): ...
def test_ai_tools_entries_are_marked_capability_only_by_service_not_parser(): ...
def test_parser_is_deterministic_for_same_snapshot_and_text(): ...
```

Parser result order must be deterministic by source appearance, while entry IDs remain content-derived.

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests_engine/test_discovery_registry_importers.py -q`

Expected: FAIL because importer functions do not exist.

- [ ] **Step 3: Implement parsers**

Do not use a Markdown dependency. Use bounded line scanning and explicit link/table patterns. Escaped `\|` inside table cells must not split columns. Never execute links or infer advertised capability truth.

- [ ] **Step 4: Run tests and verify pass**

Run: `python -m pytest tests_engine/test_discovery_registry_importers.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add icarus_engine/discovery_registry/importers.py tests_engine/fixtures/discovery_registry tests_engine/test_discovery_registry_importers.py
git commit -m "feat: import three discovery catalogs offline"
```

---

### Task 5: Fail-Closed Policy Triage and Source Classification

**Files:**
- Create: `icarus_engine/discovery_registry/policy.py`
- Create: `tests_engine/test_discovery_registry_policy.py`

**Interfaces:**
- Consumes `CatalogEntry`, `Candidate`, `PolicyDecision`, `PolicyState`, `SourceClass`.
- Produces `class PolicyTriage` with:
  - `classify_source(entry: CatalogEntry) -> SourceClass`
  - `evaluate(entry: CatalogEntry) -> PolicyDecision`
  - `candidate_defaults(entry: CatalogEntry, *, catalog_id: str) -> dict[str, object]`

Rules:

- `apify.com/...` defaults to `SCRAPER_ACTOR` unless the description identifies an MCP-only capability, in which case `MCP_CAPABILITY`.
- entries from `ai-agent-tools` default `capability_only=True` and `SourceClass.AI_TOOL` unless the URL is itself a GitHub MCP/server project explicitly identified as such.
- ordinary imported entries default policy state `REVIEW_REQUIRED`.
- automatic triage may set `REJECTED` only for explicit circumvention/credential/malware language; it may never auto-set `ALLOWED_PRODUCTION_DATA`.
- exact rejection phrases/patterns cover `bypass ... paywall`, `bypass ... subscription`, `steal|harvest ... credential|token|password`, and explicit malware/spyware claims. Matching is case-insensitive and recorded with a machine-readable reason code.

- [ ] **Step 1: Write failing policy tests**

```python
def test_explicit_circumvention_is_rejected():
    decision = PolicyTriage().evaluate(entry(description="Bypass Bloomberg paywall and extract premium content"))
    assert decision.policy_state is PolicyState.REJECTED
    assert decision.reason_code == "EXPLICIT_ACCESS_CONTROL_CIRCUMVENTION"


def test_ordinary_scraper_is_review_required_not_auto_allowed(): ...
def test_ai_tools_default_to_capability_only(): ...
```

Also assert marketing labels like `free`, `official`, `best`, `real-time`, or `no login` do not by themselves produce an allowed policy state.

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests_engine/test_discovery_registry_policy.py -q`

Expected: FAIL because policy triage does not exist.

- [ ] **Step 3: Implement policy triage**

Keep the scanner deliberately narrow. Ambiguity remains `REVIEW_REQUIRED`; do not guess license/ToS.

- [ ] **Step 4: Run tests and verify pass**

Run: `python -m pytest tests_engine/test_discovery_registry_policy.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add icarus_engine/discovery_registry/policy.py tests_engine/test_discovery_registry_policy.py
git commit -m "feat: add fail closed catalog policy triage"
```

---

### Task 6: Non-Destructive Duplicate Families and Shared Ancestry

**Files:**
- Create: `icarus_engine/discovery_registry/dedupe.py`
- Create: `tests_engine/test_discovery_registry_dedupe.py`

**Interfaces:**
- Consumes normalized candidates from Tasks 1-2.
- Produces `class DuplicateResolver` with `resolve(candidates: Iterable[Candidate]) -> tuple[DuplicateGroup, ...]`.
- Produces `duplicate_keys(candidate: Candidate) -> tuple[tuple[str, str], ...]` with evidence levels:
  - `EXACT_IDENTITY_URL`
  - `PROVIDER_CAPABILITY`
  - `DOMAIN_PATH`
  - `NORMALIZED_NAME_DOMAIN`
- Semantic similarity is **not** auto-merged in this foundation plan. Ambiguous possible semantic duplicates remain separate candidates for later review.

- [ ] **Step 1: Write failing dedupe tests**

```python
def test_referral_wrappers_share_one_duplicate_family(): ...
def test_same_name_on_different_domains_does_not_auto_merge(): ...
def test_duplicate_group_keeps_every_candidate_and_catalog_reference(): ...
```

Assert deterministic group IDs derived from sorted member candidate IDs and evidence level.

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests_engine/test_discovery_registry_dedupe.py -q`

Expected: FAIL because duplicate resolver does not exist.

- [ ] **Step 3: Implement resolver**

Use deterministic union-find or equivalent over exact/structural keys. Never delete a candidate; groups collapse independence only.

- [ ] **Step 4: Run tests and verify pass**

Run: `python -m pytest tests_engine/test_discovery_registry_dedupe.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add icarus_engine/discovery_registry/dedupe.py tests_engine/test_discovery_registry_dedupe.py
git commit -m "feat: preserve duplicate source ancestry"
```

---

### Task 7: Offline Registry Service Pipeline

**Files:**
- Create: `icarus_engine/discovery_registry/service.py`
- Create: `tests_engine/test_discovery_registry_service.py`
- Modify: `icarus_engine/discovery_registry/__init__.py`

**Interfaces:**
- Consumes Tasks 1-6.
- Produces `class DiscoveryRegistryService`:
  - constructor `DiscoveryRegistryService(base_dir: Path)`
  - `import_snapshot(snapshot: CatalogSnapshot, text: str, *, importer_name: str) -> ImportSummary`
  - `snapshot() -> dict[str, object]`
  - `close() -> None`
- Produces immutable `ImportSummary(catalog_id, snapshot_id, raw_count, imported_entries, unique_candidates, duplicate_groups, rejected, review_required, parse_failures)`.

Pipeline order is fixed:

```text
parse -> normalize -> build DISCOVERED candidates -> policy triage
-> persist snapshot/entries/candidate links/policy -> resolve duplicate families -> persist groups
```

No network calls occur anywhere in `icarus_engine.discovery_registry`.

- [ ] **Step 1: Write failing end-to-end service tests**

Pin:

```python
def test_import_snapshot_is_idempotent(tmp_path, api_mega_text): ...
def test_service_preserves_all_catalog_provenance_while_collapsing_duplicate_independence(tmp_path): ...
def test_service_outputs_authority_false(tmp_path): ...
def test_sponsored_placement_does_not_change_quality_or_policy(tmp_path): ...
```

Also assert a rejected entry remains visible in candidates with disposition `REJECTED` or policy rejection state rather than being silently omitted.

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests_engine/test_discovery_registry_service.py -q`

Expected: FAIL because the service does not exist.

- [ ] **Step 3: Implement the service**

`ImportSummary` counts come from persisted state for that exact snapshot, not mutable in-memory counters that could diverge after retries.

- [ ] **Step 4: Run service + foundation tests**

Run: `python -m pytest tests_engine/test_discovery_registry_contracts.py tests_engine/test_discovery_registry_normalize.py tests_engine/test_discovery_registry_store.py tests_engine/test_discovery_registry_importers.py tests_engine/test_discovery_registry_policy.py tests_engine/test_discovery_registry_dedupe.py tests_engine/test_discovery_registry_service.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add icarus_engine/discovery_registry tests_engine/test_discovery_registry_service.py
git commit -m "feat: assemble offline discovery registry pipeline"
```

---

### Task 8: Pinned Public-GitHub Fetcher, Source Config, CLI, and Bounded Receipts

**Files:**
- Create: `config/catalog_registry_sources.json`
- Create: `tools/catalog_registry_ingest.py`
- Create: `tests/test_catalog_registry_ingest.py`
- Modify: `.gitignore`

**Interfaces:**
- Source config contains exactly three enabled entries:
  - `api-mega-list` -> `cporter202/API-mega-list`, `README.md`, importer `api_mega`, `capability_only=false`
  - `scraping-apis-for-devs` -> `cporter202/scraping-apis-for-devs`, `README.md`, importer `scraping_apis`, `capability_only=false`
  - `ai-agent-tools` -> `cporter202/ai-agent-tools`, `README.md`, importer `ai_agent_tools`, `capability_only=true`
- Produces `class GitHubPublicCatalogClient`:
  - `resolve_ref(repo: str, ref: str = "main") -> str`
  - `fetch_text(repo: str, commit: str, path: str) -> bytes`
- Produces `run(root: Path, *, run_id: str, catalog_ids: Sequence[str] | None = None, client: GitHubPublicCatalogClient | None = None) -> dict[str, object]`.
- CLI: `python -m tools.catalog_registry_ingest --run-id ID [--catalog all|CATALOG_ID] [--root PATH]`.

Network safety:

- repository IDs must match `^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$`;
- commit must be validated 40-hex before raw fetch;
- source path must be relative and contain no `..`;
- ref resolution uses GitHub API; file fetch uses `raw.githubusercontent.com/{repo}/{commit}/{path}`;
- maximum catalog file is `20_000_000` bytes; read one byte beyond and fail `CATALOG_PAYLOAD_LIMIT`;
- user agent is `ICARUS-catalog-registry/1`;
- no credentials are required or read from environment.

Local replay cache path is `.catalog_registry_cache/raw/<catalog_id>/<commit>/<content_sha256>.md.gz`; add `.catalog_registry_cache/` to `.gitignore`.

Bounded committed receipt paths:

```text
automation_intelligence/catalog_registry_v1/cycles/<run_id>/receipt.json
automation_intelligence/catalog_registry_v1/latest/<catalog_id>.json
```

Receipts contain snapshot provenance, counts, policy/dedupe counts, errors, authority false, `chatgpt_tokens_used=0`, and `paid_model_calls=0`; never raw catalog rows.

- [ ] **Step 1: Write failing fetch/CLI tests using a fake client**

```python
def test_fetch_uses_resolved_commit_not_mutable_ref(tmp_path):
    client = FakeClient(resolved="a" * 40, payload=b"# Catalog\n")
    run(tmp_path, run_id="r1", catalog_ids=["api-mega-list"], client=client)
    assert client.fetch_calls == [("cporter202/API-mega-list", "a" * 40, "README.md")]


def test_fetch_rejects_payload_over_limit(): ...
def test_receipt_contains_no_raw_rows_or_secrets(tmp_path): ...
def test_same_commit_and_content_reuses_local_snapshot_identity(tmp_path): ...
```

Also test failed fetch does not write a false successful latest receipt.

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests/test_catalog_registry_ingest.py -q`

Expected: FAIL because tool/config do not exist.

- [ ] **Step 3: Implement config, client, run function, cache, receipts, and CLI**

Resolve exact commit first, fetch by commit, compute SHA-256 on raw bytes, gzip the raw public snapshot into the ignored local cache, then call `DiscoveryRegistryService.import_snapshot`. Never pass mutable `main` into a snapshot contract.

- [ ] **Step 4: Run tests and verify pass**

Run: `python -m pytest tests/test_catalog_registry_ingest.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add config/catalog_registry_sources.json tools/catalog_registry_ingest.py tests/test_catalog_registry_ingest.py .gitignore
git commit -m "feat: ingest pinned public discovery catalogs"
```

---

### Task 9: Read-Only Federation With Existing Provider Acquisition Evidence

**Files:**
- Create: `icarus_engine/discovery_registry/federation.py`
- Create: `tests_engine/test_discovery_registry_federation.py`
- Modify: `icarus_engine/discovery_registry/service.py`

**Interfaces:**
- Consumes `config/provider_endpoint_catalog.json` and local files under `automation_intelligence/provider_collection_v1/latest/*.json`.
- Produces `PROVIDER_DOMAINS: dict[str, tuple[str, ...]]` for the current provider names: `massive`, `twelve`, `fmp`, `eodhd`, `tiingo`, `intrinio`, `quiver`, `fred`, `alpaca`, `bybit`, `tickstream`.
- Produces `class ProviderFederator`:
  - `ProviderFederator(endpoint_catalog_path: Path, latest_dir: Path, *, now: Callable[[], datetime] | None = None)`
  - `links_for(candidates: Iterable[Candidate]) -> tuple[ProviderLink, ...]`
  - `evidence_events(links: Iterable[ProviderLink]) -> tuple[QualificationEvent, ...]`
- Add service method `federate_existing_providers(endpoint_catalog_path: Path, latest_dir: Path) -> dict[str, object]`.

Matching order:

1. normalized candidate domain exactly maps to an admitted provider domain;
2. canonical provider name maps to an admitted provider alias;
3. otherwise no provider link.

Federation may link one provider-level candidate to many existing operation IDs, but it **never invokes** `tools.provider_exhaustive_collection`, never creates a job, and never performs a provider HTTP request.

Receipt semantics:

- receipt must parse as an object containing matching provider entry and `completed_at_utc`;
- receipt older than 6 hours is `STALE_PROVIDER_EVIDENCE` for live access state and cannot advance qualification;
- `COLLECTED_PARTIAL` or a receipt with `substantive_work_performed=true` and at least one collected page may produce an `ACCESS_TESTED` transition from `DISCOVERED`;
- `BLOCKED_MISSING_CREDENTIAL`, `BLOCKED_AUTHENTICATION`, `QUOTA_OR_RATE_LIMIT_PAUSED`, malformed receipts, or denied-only evidence record a blocker/link but do not advance lifecycle;
- no provider receipt can advance beyond `ACCESS_TESTED` in this foundation plan.

- [ ] **Step 1: Write failing federation tests**

```python
def test_existing_provider_candidate_links_without_downloader_call(tmp_path, monkeypatch): ...

def test_positive_recent_receipt_can_advance_only_to_access_tested(tmp_path): ...

def test_malformed_or_stale_provider_receipt_cannot_advance_candidate(tmp_path): ...

def test_blocked_credentials_are_evidence_not_success(tmp_path): ...
```

Monkeypatch any provider acquisition entry point to raise if called; federation tests must still pass.

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests_engine/test_discovery_registry_federation.py -q`

Expected: FAIL because federation does not exist.

- [ ] **Step 3: Implement read-only federation**

Provider receipt content remains evidence with exact local path + content hash in `ProviderLink.metadata`. Do not import encrypted/raw provider payloads into the registry.

- [ ] **Step 4: Run federation + existing provider collector regression**

Run:

```bash
python -m pytest tests_engine/test_discovery_registry_federation.py -q
python -m pytest tests/test_provider_exhaustive_collection.py -q
```

Expected: both PASS; existing provider acquisition behavior unchanged.

- [ ] **Step 5: Commit**

```bash
git add icarus_engine/discovery_registry/federation.py icarus_engine/discovery_registry/service.py tests_engine/test_discovery_registry_federation.py
git commit -m "feat: federate existing provider evidence into registry"
```

---

### Task 10: Autonomous Catalog Refresh Workflow With No ChatGPT Token Loop

**Files:**
- Create: `.github/workflows/catalog-registry-refresh.yml`
- Modify: `tests/test_catalog_registry_ingest.py`

**Interfaces:**
- Scheduled cadence: daily at `37 4 * * *` plus `workflow_dispatch`.
- Permissions: `contents: write` only.
- Python: `3.11`.
- Test before network import: `python -m pytest tests/test_catalog_registry_ingest.py tests_engine/test_discovery_registry_*.py -q`.
- Restore/save `.catalog_registry_cache` and `research/capability_registry.sqlite3` using Actions cache with `catalog-registry-v1-` restore prefix.
- Run ID: `catalog-registry-${{ github.run_id }}-${{ github.run_attempt }}`.
- Execute `python -m tools.catalog_registry_ingest --catalog all --run-id "$RUN_ID"`.
- Upload the run receipt as an Actions artifact; do not upload raw cached README snapshots.
- Git-stage allowlist is limited to:
  - `automation_intelligence/catalog_registry_v1/cycles/$RUN_ID/`
  - `automation_intelligence/catalog_registry_v1/latest/*.json`
- Commit message: `research: refresh discovery catalogs $RUN_ID [skip ci]`.
- Rebase/push retry loop mirrors the existing provider workflow and must fail instead of staging unrelated concurrent changes.

- [ ] **Step 1: Add workflow-contract tests**

In `tests/test_catalog_registry_ingest.py`, parse the YAML as text and assert:

- all three catalogs are reached through `--catalog all`;
- workflow does not reference secrets or API keys;
- workflow tests before ingest;
- workflow stages only registry receipt paths;
- workflow never stages `.catalog_registry_cache` or `research/capability_registry.sqlite3`;
- `chatgpt`/remote-model invocation commands are absent.

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests/test_catalog_registry_ingest.py -q`

Expected: FAIL because workflow is absent.

- [ ] **Step 3: Implement workflow**

Use `actions/checkout@v4`, `actions/setup-python@v5`, `actions/cache/restore@v4`, `actions/cache/save@v4`, and `actions/upload-artifact@v4`. No third-party action beyond those official GitHub actions.

- [ ] **Step 4: Run tests and verify pass**

Run: `python -m pytest tests/test_catalog_registry_ingest.py tests_engine/test_discovery_registry_*.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/catalog-registry-refresh.yml tests/test_catalog_registry_ingest.py
git commit -m "ci: refresh discovery catalogs autonomously"
```

---

### Task 11: Operator Documentation and Foundation Verification

**Files:**
- Create: `docs/icarus/CAPABILITY_DATA_DISCOVERY_REGISTRY.md`
- Modify: `README.md`

**Interfaces:**
- Documentation describes only implemented foundation behavior.
- Must state clearly that catalog presence is not qualification, that policy is fail-closed, that provider federation is read-only, that the registry is research/shadow only, and that this phase does not provide API/MCP/UI or external source probing.
- Document commands:

```bash
python -m tools.catalog_registry_ingest --catalog all --run-id manual-YYYYMMDD
python -m pytest tests_engine/test_discovery_registry_*.py -q
python -m pytest tests/test_catalog_registry_ingest.py tests/test_provider_exhaustive_collection.py -q
```

- [ ] **Step 1: Add documentation assertions**

Extend `tests_engine/test_discovery_registry_service.py` or add a small documentation test that asserts the doc contains the exact authority strings and explicitly labels `DISCOVERED` as unqualified.

- [ ] **Step 2: Run documentation test and verify failure**

Run: `python -m pytest tests_engine/test_discovery_registry_service.py -q`

Expected: FAIL until the documentation exists.

- [ ] **Step 3: Write foundation documentation and README link**

Do not claim live catalog import success until an actual workflow/manual run produces receipts. Do not claim source qualification, alpha, shadow performance, or production readiness in this phase.

- [ ] **Step 4: Run targeted and repository regression suites**

Run:

```bash
python -m pytest tests_engine/test_discovery_registry_*.py -q
python -m pytest tests/test_catalog_registry_ingest.py tests/test_provider_exhaustive_collection.py -q
python -m pytest tests_engine -q
```

Expected: all PASS.

- [ ] **Step 5: Static safety checks**

Run:

```bash
git grep -nE 'execution_authorized["'"']? *[:=] *True|production_decision_authorized["'"']? *[:=] *True' -- icarus_engine/discovery_registry tools/catalog_registry_ingest.py || true
git grep -nE 'API_KEY|SECRET_KEY|TOKEN|PASSWORD' -- icarus_engine/discovery_registry tools/catalog_registry_ingest.py .github/workflows/catalog-registry-refresh.yml || true
```

Expected: no authority-true assignments; no catalog-registry secret dependencies. A test fixture string may mention the word `token` only when proving rejection/scrubbing.

- [ ] **Step 6: Commit**

```bash
git add docs/icarus/CAPABILITY_DATA_DISCOVERY_REGISTRY.md README.md tests_engine/test_discovery_registry_service.py
git commit -m "docs: document discovery registry foundation"
```

---

## Final Foundation Acceptance Gate

Before this plan is declared complete:

- [ ] All three configured catalog repositories resolve to exact commits before content fetch.
- [ ] The same pinned snapshot imports idempotently.
- [ ] Every candidate retains upstream snapshot + entry provenance.
- [ ] Referral/tracking variants collapse into shared duplicate ancestry without deleting candidates.
- [ ] Explicit circumvention candidates are rejected/quarantined and remain auditable.
- [ ] Unknown policy never becomes allowed automatically.
- [ ] No catalog importer or engine registry module performs network I/O.
- [ ] The CLI can fetch public catalog content with no credentials and bounded payload size.
- [ ] Existing provider receipts link read-only; no duplicate provider request is made.
- [ ] Provider blocker/stale evidence never becomes success.
- [ ] Registry/receipts expose `execution_authorized=false` and `production_decision_authorized=false`.
- [ ] No raw catalog file or registry SQLite DB is staged by the scheduled workflow.
- [ ] Existing provider collector regression remains green.
- [ ] Full `tests_engine` regression remains green.

## Deferred Plans Required to Complete the Approved Architecture

This foundation intentionally establishes interfaces rather than mixing independent subsystems into one unreviewable implementation. After it lands, create separate plans in this order:

1. **Qualification & Source-Health Plan** — queueing, manual policy decisions, schema/latency/reliability/historical-depth probes, cost/budget gates, staleness/demotion.
2. **Exogenous Intelligence & Empirical Value Plan** — narrative/social/search/real-economy lanes, point-in-time data contracts, chronological OOS experiments, redundancy/marginal-information scoring, APEX ancestry/world-state integration.
3. **Operator Surface & Promotion Plan** — authenticated HTTP/MCP surfaces, DISCOVERY/SOURCES dashboard, shadow evaluation status, explicit promotion/demotion decision UI/API, continuing health review.

No deferred plan may weaken the authority or safety invariants fixed by this foundation and the approved spec.
