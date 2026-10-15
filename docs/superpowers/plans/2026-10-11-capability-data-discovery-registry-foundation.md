# ICARUS Capability & Data Discovery Registry Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the durable registry kernel, deterministic import path for all three approved discovery catalogs, non-destructive duplicate/policy handling, and read-only federation with ICARUS's existing exhaustive-provider acquisition evidence.

**Architecture:** The foundation is a metadata/control-plane subsystem under `icarus_engine/discovery_registry/` backed by SQLite WAL at `research/capability_registry.sqlite3`. Catalog network retrieval is isolated in `tools/catalog_registry_ingest.py`; the engine package imports already-fetched pinned content and never performs catalog network calls. Existing `provider_exhaustive_collection` remains the only acquisition engine for providers it already owns; federation reads its catalog/receipts and records links/evidence without creating downloader jobs.

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

## Spec Coverage Boundary

This is **Plan 1** of the approved architecture. It fully implements the design's registry kernel, catalog snapshot/provenance contract, candidate contract foundation, importers, lifecycle foundation, non-destructive dedupe, fail-closed policy defaults, persistence, existing-provider federation, and rollout Phases 0-1. It deliberately does not implement live source probes, empirical alpha scoring, exogenous feature lanes, HTTP/MCP/UI, or production promotion; those independent subsystems are assigned to the three deferred plans at the end of this document.

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

No `server.py`, dashboard, MCP, exogenous feature, alpha/backtest, or production-promotion changes belong in this foundation plan.

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

- [ ] **Step 1: Write the failing contract tests**

```python
def test_catalog_snapshot_requires_pinned_commit_and_content_hash():
    with pytest.raises(ValueError):
        CatalogSnapshot(
            catalog_id="api-mega-list",
            upstream_repo="cporter202/API-mega-list",
            upstream_commit="main",
            upstream_path="README.md",
            content_sha256="x",
            retrieved_at="2026-10-11T00:00:00Z",
            parser_revision="v1",
        )


def test_authority_is_permanently_false():
    candidate = Candidate.minimum(
        candidate_id="a" * 64,
        canonical_name="Example",
        endpoint_or_tool_url="https://example.com",
    )
    assert candidate.execution_authorized is False
    assert candidate.production_decision_authorized is False


def test_illegal_lifecycle_jump_fails_closed():
    with pytest.raises(ValueError):
        assert_transition(QualificationState.DISCOVERED, QualificationState.PRODUCTION)


def test_numeric_quality_rejects_bool_nan_and_inf():
    for value in (True, float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError):
            Candidate.minimum(
                candidate_id="b" * 64,
                canonical_name="Bad numeric",
                endpoint_or_tool_url="https://example.com/x",
                source_quality=value,
            )
```

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
- Consumes `SourceClass`, `DataClass`, `Candidate` from Task 1.
- Produces `NormalizedURL(original_url: str, identity_url: str, domain: str)`.
- Produces `normalize_url(url: str) -> NormalizedURL`.
- Produces `normalize_name(name: str) -> str`.
- Produces `canonical_provider_name(name: str, domain: str) -> str`.
- Produces `candidate_identity(*, canonical_name: str, identity_url: str, capability_kind: str) -> str` returning full lowercase SHA-256 hex.
- Produces `classify_data_class(category: str, description: str) -> tuple[DataClass, ...]`; uncertain entries return `(DataClass.OTHER,)` rather than invented specificity.

- [ ] **Step 1: Write the failing normalization tests**

```python
def test_normalize_url_drops_only_known_tracking_parameters():
    got = normalize_url("https://apify.com/acme/tool?fpr=abc&symbol=NQ&utm_source=x#top")
    assert got.identity_url == "https://apify.com/acme/tool?symbol=NQ"
    assert got.original_url.endswith("#top")


def test_tracking_variants_have_same_identity():
    a = normalize_url("https://apify.com/acme/tool?fpr=a")
    b = normalize_url("https://apify.com/acme/tool?fpr=b&utm_campaign=c")
    assert a.identity_url == b.identity_url


def test_meaningful_query_parameter_is_preserved():
    got = normalize_url("HTTPS://EXAMPLE.COM:443/path?symbol=NQ&ref=x")
    assert got.identity_url == "https://example.com/path?symbol=NQ"


def test_non_http_url_fails_closed():
    with pytest.raises(ValueError):
        normalize_url("javascript:alert(1)")
```

Known identity-only tracking keys are exactly: `fpr`, `ref`, `referrer`, `utm_source`, `utm_medium`, `utm_campaign`, `utm_term`, `utm_content`.

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests_engine/test_discovery_registry_normalize.py -q`

Expected: FAIL because normalization functions do not exist.

- [ ] **Step 3: Implement normalization**

Use `urllib.parse` and `unicodedata`. Lowercase scheme/host, remove default ports, remove fragments from identity, sort retained query pairs, strip leading decorative Unicode symbols from normalized names, and preserve original URL verbatim.

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
  - `pragma_journal_mode() -> str`
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

Initial schema: `catalog_snapshots`, `catalog_entries`, `candidates`, `candidate_catalog_links`, `duplicate_groups`, `duplicate_members`, `qualification_events`, `policy_reviews`, `provider_links`.

- [ ] **Step 1: Write the failing store tests**

```python
def test_store_uses_wal_and_is_idempotent(tmp_path):
    store = RegistryStore(tmp_path)
    assert store.pragma_journal_mode() == "wal"
    snap = snapshot_fixture(snapshot_id="s1", content_sha256="1" * 64)
    store.record_snapshot(snap)
    store.record_snapshot(snap)
    assert store.summary()["catalog_snapshots"] == 1


def test_conflicting_same_snapshot_identity_fails(tmp_path):
    store = RegistryStore(tmp_path)
    store.record_snapshot(snapshot_fixture(snapshot_id="s1", content_sha256="1" * 64))
    with pytest.raises(ValueError):
        store.record_snapshot(snapshot_fixture(snapshot_id="s1", content_sha256="2" * 64))


def test_transition_history_is_append_only(tmp_path):
    store = seeded_candidate_store(tmp_path)
    store.record_transition(event_fixture(QualificationState.DISCOVERED, QualificationState.ACCESS_TESTED))
    assert store.candidate("c" * 64).qualification_state is QualificationState.ACCESS_TESTED
    assert store.summary()["qualification_events"] == 1
    with pytest.raises(ValueError):
        store.record_transition(event_fixture(QualificationState.ACCESS_TESTED, QualificationState.PRODUCTION))
    assert store.summary()["qualification_events"] == 1
```

Also reopen the store in a second `RegistryStore(tmp_path)` and assert the candidate and authority-false values persist.

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests_engine/test_discovery_registry_store.py -q`

Expected: FAIL because `RegistryStore` does not exist.

- [ ] **Step 3: Implement store schema and methods**

Use foreign keys, WAL, `json.dumps(..., allow_nan=False, sort_keys=True)`, and unique constraints that make retries idempotent. `record_transition` validates old state and appends the event + updates current state in one transaction.

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

API Mega List and Scraping APIs support Markdown tables of `API Name | Description` plus nearest heading/category. AI Agent Tools supports Markdown bullets of `[Name](url) - description` plus nearest heading/category. All preserve source path and raw-row SHA-256.

- [ ] **Step 1: Create representative offline fixtures and failing tests**

Fixtures contain an Apify `?fpr=` row, two referral variants of one underlying URL, an escaped `\|` in a description, one malformed row, one explicit paywall-bypass description, one AI-tools bullet, and a sponsored/featured heading.

```python
def test_all_three_importers_produce_entries(fixtures):
    assert len(parse_api_mega_list(snapshot("api-mega-list"), fixtures.api_mega).entries) == 4
    assert len(parse_scraping_apis(snapshot("scraping-apis-for-devs"), fixtures.scraping).entries) == 3
    assert len(parse_ai_agent_tools(snapshot("ai-agent-tools"), fixtures.ai_tools).entries) == 2


def test_malformed_rows_are_reported(fixtures):
    result = parse_api_mega_list(snapshot("api-mega-list"), fixtures.api_mega)
    assert result.raw_count == 5
    assert len(result.parse_failures) == 1
    assert result.parse_failures[0]["reason"] == "MALFORMED_CATALOG_ROW"


def test_escaped_pipe_stays_inside_description(fixtures):
    result = parse_api_mega_list(snapshot("api-mega-list"), fixtures.api_mega)
    row = next(item for item in result.entries if item.canonical_name == "Pipe Example")
    assert "A | B" in row.description


def test_parser_is_deterministic_for_same_snapshot_and_text(fixtures):
    a = parse_scraping_apis(snapshot("scraping-apis-for-devs"), fixtures.scraping)
    b = parse_scraping_apis(snapshot("scraping-apis-for-devs"), fixtures.scraping)
    assert a == b
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests_engine/test_discovery_registry_importers.py -q`

Expected: FAIL because importer functions do not exist.

- [ ] **Step 3: Implement parsers**

Do not add a Markdown dependency. Use bounded line scanning and explicit link/table patterns. Never execute links or infer advertised capability truth. Parser output keeps source order; entry IDs are content-derived.

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
- Consumes `CatalogEntry`, `PolicyDecision`, `PolicyState`, `SourceClass`.
- Produces `class PolicyTriage` with:
  - `classify_source(entry: CatalogEntry) -> SourceClass`
  - `evaluate(entry: CatalogEntry) -> PolicyDecision`
  - `candidate_defaults(entry: CatalogEntry, *, catalog_id: str) -> dict[str, object]`

Rules:

- `apify.com/...` defaults to `SCRAPER_ACTOR` unless description/name explicitly identifies an MCP-only capability, then `MCP_CAPABILITY`.
- `ai-agent-tools` entries default `capability_only=True` and `AI_TOOL`, except an explicitly named MCP/server GitHub project may classify `MCP_CAPABILITY`.
- ordinary imported entries default `REVIEW_REQUIRED`.
- automatic triage may set `REJECTED` only for explicit circumvention/credential/malware language; it may never auto-set `ALLOWED_PRODUCTION_DATA`.
- exact rejection patterns cover `bypass ... paywall`, `bypass ... subscription`, `steal|harvest ... credential|token|password`, and explicit malware/spyware claims.

- [ ] **Step 1: Write the failing policy tests**

```python
def test_explicit_circumvention_is_rejected():
    decision = PolicyTriage().evaluate(entry(description="Bypass Bloomberg paywall and extract premium content"))
    assert decision.policy_state is PolicyState.REJECTED
    assert decision.reason_code == "EXPLICIT_ACCESS_CONTROL_CIRCUMVENTION"


def test_ordinary_scraper_is_review_required_not_auto_allowed():
    decision = PolicyTriage().evaluate(entry(url="https://apify.com/acme/news", description="Extract public news headlines"))
    assert decision.policy_state is PolicyState.REVIEW_REQUIRED
    assert PolicyTriage().classify_source(entry(url="https://apify.com/acme/news")) is SourceClass.SCRAPER_ACTOR


def test_ai_tools_default_to_capability_only():
    defaults = PolicyTriage().candidate_defaults(entry(url="https://example.com/ai", description="Coding assistant"), catalog_id="ai-agent-tools")
    assert defaults["capability_only"] is True
    assert defaults["source_class"] is SourceClass.AI_TOOL


def test_marketing_claims_do_not_auto_allow():
    for phrase in ("free official API", "best real-time feed", "no login required"):
        assert PolicyTriage().evaluate(entry(description=phrase)).policy_state is PolicyState.REVIEW_REQUIRED
```

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
- Produces `duplicate_keys(candidate: Candidate) -> tuple[tuple[str, str], ...]` with evidence levels `EXACT_IDENTITY_URL`, `PROVIDER_CAPABILITY`, `DOMAIN_PATH`, `NORMALIZED_NAME_DOMAIN`.
- Semantic similarity is not auto-merged in this foundation plan.

- [ ] **Step 1: Write the failing dedupe tests**

```python
def test_referral_wrappers_share_one_duplicate_family():
    candidates = [candidate("https://apify.com/acme/tool?fpr=a"), candidate("https://apify.com/acme/tool?fpr=b")]
    groups = DuplicateResolver().resolve(candidates)
    assert len(groups) == 1
    assert set(groups[0].member_ids) == {c.candidate_id for c in candidates}


def test_same_name_on_different_domains_does_not_auto_merge():
    candidates = [candidate("https://a.example/tool", name="News API"), candidate("https://b.example/tool", name="News API")]
    assert DuplicateResolver().resolve(candidates) == ()


def test_duplicate_group_keeps_every_candidate_and_catalog_reference():
    a = candidate("https://apify.com/acme/tool?fpr=a", catalog_ref="api-mega-list")
    b = candidate("https://apify.com/acme/tool?fpr=b", catalog_ref="scraping-apis-for-devs")
    group = DuplicateResolver().resolve([a, b])[0]
    assert group.effective_independent_count == 1
    assert set(group.member_ids) == {a.candidate_id, b.candidate_id}
```

Assert group ID equals SHA-256 of the evidence level plus sorted member IDs.

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
  - `DiscoveryRegistryService(base_dir: Path)`
  - `import_snapshot(snapshot: CatalogSnapshot, text: str, *, importer_name: str) -> ImportSummary`
  - `snapshot() -> dict[str, object]`
  - `close() -> None`
- Produces immutable `ImportSummary(catalog_id, snapshot_id, raw_count, imported_entries, unique_candidates, duplicate_groups, rejected, review_required, parse_failures)`.

Pipeline order is fixed:

```text
parse -> normalize -> build DISCOVERED candidates -> policy triage
-> persist snapshot/entries/candidate links/policy -> resolve duplicate families -> persist groups
```

- [ ] **Step 1: Write the failing service tests**

```python
def test_import_snapshot_is_idempotent(tmp_path, api_mega_text):
    service = DiscoveryRegistryService(tmp_path)
    first = service.import_snapshot(snapshot("api-mega-list"), api_mega_text, importer_name="api_mega")
    second = service.import_snapshot(snapshot("api-mega-list"), api_mega_text, importer_name="api_mega")
    assert first == second
    assert service.snapshot()["catalog_snapshots"] == 1


def test_service_preserves_provenance_while_collapsing_duplicate_independence(tmp_path, duplicated_text):
    service = DiscoveryRegistryService(tmp_path)
    summary = service.import_snapshot(snapshot("api-mega-list"), duplicated_text, importer_name="api_mega")
    assert summary.imported_entries == 2
    assert summary.duplicate_groups == 1
    assert len(service.store.candidates()) == 2


def test_service_outputs_authority_false(tmp_path, api_mega_text):
    service = DiscoveryRegistryService(tmp_path)
    service.import_snapshot(snapshot("api-mega-list"), api_mega_text, importer_name="api_mega")
    state = service.snapshot()
    assert state["execution_authorized"] is False
    assert state["production_decision_authorized"] is False


def test_sponsored_placement_does_not_change_quality_or_policy(tmp_path, sponsored_pair_text):
    service = DiscoveryRegistryService(tmp_path)
    service.import_snapshot(snapshot("api-mega-list"), sponsored_pair_text, importer_name="api_mega")
    candidates = service.store.candidates()
    assert {c.source_quality for c in candidates} == {None}
    assert {c.policy_state for c in candidates} == {PolicyState.REVIEW_REQUIRED}
```

Also assert an explicitly rejected catalog entry remains queryable rather than being omitted.

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests_engine/test_discovery_registry_service.py -q`

Expected: FAIL because the service does not exist.

- [ ] **Step 3: Implement the service**

No network call may exist anywhere under `icarus_engine/discovery_registry`. `ImportSummary` counts come from persisted state for the exact snapshot.

- [ ] **Step 4: Run foundation tests**

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

- repository IDs match `^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$`;
- commit is 40-hex before raw fetch;
- source path is relative and contains no `..`;
- ref resolution uses GitHub API; file fetch uses `raw.githubusercontent.com/{repo}/{commit}/{path}`;
- maximum catalog file is `20_000_000` bytes; read one byte beyond and fail `CATALOG_PAYLOAD_LIMIT`;
- user agent is `ICARUS-catalog-registry/1`;
- no credential environment variable is read.

Local replay cache: `.catalog_registry_cache/raw/<catalog_id>/<commit>/<content_sha256>.md.gz`; add `.catalog_registry_cache/` to `.gitignore`.

Bounded committed receipts:

```text
automation_intelligence/catalog_registry_v1/cycles/<run_id>/receipt.json
automation_intelligence/catalog_registry_v1/latest/<catalog_id>.json
```

Receipts contain snapshot provenance, counts, policy/dedupe counts, errors, authority false, `chatgpt_tokens_used=0`, and `paid_model_calls=0`; never raw catalog rows.

- [ ] **Step 1: Write the failing fetch/CLI tests using a fake client**

```python
def test_fetch_uses_resolved_commit_not_mutable_ref(tmp_path):
    client = FakeClient(resolved="a" * 40, payload=b"# Catalog\n")
    run(tmp_path, run_id="r1", catalog_ids=["api-mega-list"], client=client)
    assert client.fetch_calls == [("cporter202/API-mega-list", "a" * 40, "README.md")]


def test_fetch_rejects_payload_over_limit():
    client = FakeClient(resolved="a" * 40, payload=b"x" * 20_000_001)
    with pytest.raises(CatalogFetchError, match="CATALOG_PAYLOAD_LIMIT"):
        client.fetch_text("cporter202/API-mega-list", "a" * 40, "README.md")


def test_receipt_contains_no_raw_rows_or_secrets(tmp_path):
    client = FakeClient(resolved="a" * 40, payload=b"# X\n| API Name | Description |\n|---|---|\n| [A](https://example.com) | SECRET_SENTINEL |\n")
    result = run(tmp_path, run_id="r1", catalog_ids=["api-mega-list"], client=client)
    receipt = json.loads((tmp_path / result["receipt_path"]).read_text())
    assert "SECRET_SENTINEL" not in json.dumps(receipt)
    assert receipt["execution_authorized"] is False


def test_same_commit_and_content_reuses_snapshot_identity(tmp_path):
    client = FakeClient(resolved="a" * 40, payload=b"# Catalog\n")
    first = run(tmp_path, run_id="r1", catalog_ids=["api-mega-list"], client=client)
    second = run(tmp_path, run_id="r2", catalog_ids=["api-mega-list"], client=client)
    assert first["catalogs"]["api-mega-list"]["snapshot_id"] == second["catalogs"]["api-mega-list"]["snapshot_id"]
```

Also assert a failed fetch writes a failed cycle receipt but does not overwrite the last successful `latest/<catalog>.json`.

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests/test_catalog_registry_ingest.py -q`

Expected: FAIL because tool/config do not exist.

- [ ] **Step 3: Implement config, client, run function, cache, receipts, and CLI**

Resolve exact commit first, fetch by commit, compute SHA-256 on raw bytes, gzip the public snapshot into ignored local cache, then call `DiscoveryRegistryService.import_snapshot`. Never pass mutable `main` into a snapshot contract.

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
- Produces exact `PROVIDER_DOMAINS` mapping:

```python
{
    "massive": ("api.massive.com", "massive.com", "polygon.io"),
    "twelve": ("api.twelvedata.com", "twelvedata.com"),
    "fmp": ("financialmodelingprep.com",),
    "eodhd": ("eodhd.com",),
    "tiingo": ("api.tiingo.com", "tiingo.com"),
    "intrinio": ("api-v2.intrinio.com", "intrinio.com"),
    "quiver": ("api.quiverquant.com", "quiverquant.com"),
    "fred": ("api.stlouisfed.org", "fred.stlouisfed.org", "stlouisfed.org"),
    "alpaca": ("data.alpaca.markets", "alpaca.markets"),
    "bybit": ("api.bybit.com", "bybit.com"),
    "tickstream": ("api.tick-stream.xyz", "tick-stream.xyz"),
}
```

- Produces `class ProviderFederator`:
  - `ProviderFederator(endpoint_catalog_path: Path, latest_dir: Path, *, now: Callable[[], datetime] | None = None)`
  - `links_for(candidates: Iterable[Candidate]) -> tuple[ProviderLink, ...]`
  - `evidence_events(links: Iterable[ProviderLink]) -> tuple[QualificationEvent, ...]`
- Add `DiscoveryRegistryService.federate_existing_providers(endpoint_catalog_path: Path, latest_dir: Path) -> dict[str, object]`.

Matching order:

1. normalized candidate domain maps exactly to an admitted provider domain;
2. canonical provider name maps to the admitted provider name;
3. otherwise no link.

Federation may link one provider-level candidate to many existing operation IDs, but it never imports/calls `tools.provider_exhaustive_collection` as an acquisition function, never creates a job, and never performs provider HTTP I/O.

Receipt semantics:

- matching provider entry + valid `completed_at_utc` are required;
- older than 6 hours -> `STALE_PROVIDER_EVIDENCE`, no lifecycle advance;
- `COLLECTED_PARTIAL` with at least one collected page, or `substantive_work_performed=true` with at least one collected page -> may transition `DISCOVERED -> ACCESS_TESTED`;
- `BLOCKED_MISSING_CREDENTIAL`, `BLOCKED_AUTHENTICATION`, `QUOTA_OR_RATE_LIMIT_PAUSED`, malformed receipts, or denied-only evidence -> link/blocker only, no transition;
- foundation federation can never advance beyond `ACCESS_TESTED`.

- [ ] **Step 1: Write the failing federation tests**

```python
def test_existing_provider_candidate_links_without_downloader_call(tmp_path, monkeypatch):
    candidate = provider_candidate("https://api.twelvedata.com/time_series")
    write_provider_catalog(tmp_path, provider="twelve", operation_id="twelve:get:/time_series")
    write_provider_receipt(tmp_path, provider="twelve", status="COLLECTED_PARTIAL", collected_pages=1, age_minutes=5)
    federator = ProviderFederator(provider_catalog(tmp_path), provider_latest(tmp_path))
    links = federator.links_for([candidate])
    assert {link.operation_id for link in links} == {"twelve:get:/time_series"}


def test_positive_recent_receipt_can_advance_only_to_access_tested(tmp_path):
    link = provider_link_fixture(status="COLLECTED_PARTIAL", collected_pages=1, age_minutes=5)
    events = ProviderFederator(provider_catalog(tmp_path), provider_latest(tmp_path)).evidence_events([link])
    assert [event.new_state for event in events] == [QualificationState.ACCESS_TESTED]


def test_malformed_or_stale_provider_receipt_cannot_advance_candidate(tmp_path):
    for receipt in ("{bad json", provider_receipt_json(status="COLLECTED_PARTIAL", collected_pages=1, age_hours=7)):
        write_raw_latest(tmp_path, "twelve", receipt)
        federator = ProviderFederator(provider_catalog(tmp_path), provider_latest(tmp_path))
        assert federator.evidence_events(federator.links_for([provider_candidate("https://twelvedata.com")])) == ()


def test_blocked_credentials_are_evidence_not_success(tmp_path):
    write_provider_receipt(tmp_path, provider="twelve", status="BLOCKED_MISSING_CREDENTIAL", collected_pages=0, age_minutes=5)
    federator = ProviderFederator(provider_catalog(tmp_path), provider_latest(tmp_path))
    links = federator.links_for([provider_candidate("https://twelvedata.com")])
    assert links[0].status == "BLOCKED_MISSING_CREDENTIAL"
    assert federator.evidence_events(links) == ()
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests_engine/test_discovery_registry_federation.py -q`

Expected: FAIL because federation does not exist.

- [ ] **Step 3: Implement read-only federation**

Provider receipt evidence stores exact local path + SHA-256 in `ProviderLink.metadata`. Do not import encrypted/raw provider payloads into the registry.

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
- Schedule: daily `37 4 * * *` plus `workflow_dispatch`.
- Permissions: `contents: write` only.
- Python: `3.11`.
- Test before import: `python -m pytest tests/test_catalog_registry_ingest.py tests_engine/test_discovery_registry_*.py -q`.
- Restore/save `.catalog_registry_cache` and `research/capability_registry.sqlite3` with `catalog-registry-v1-` restore prefix.
- Run ID: `catalog-registry-${{ github.run_id }}-${{ github.run_attempt }}`.
- Execute `python -m tools.catalog_registry_ingest --catalog all --run-id "$RUN_ID"`.
- Upload cycle receipt only as an Actions artifact; do not upload raw cached README snapshots.
- Git-stage allowlist:
  - `automation_intelligence/catalog_registry_v1/cycles/$RUN_ID/`
  - `automation_intelligence/catalog_registry_v1/latest/*.json`
- Commit: `research: refresh discovery catalogs $RUN_ID [skip ci]`.
- Rebase/push retry mirrors the provider workflow and aborts on out-of-scope staged files.

- [ ] **Step 1: Add failing workflow-contract tests**

Tests read `.github/workflows/catalog-registry-refresh.yml` as text and assert all of:

```python
assert "37 4 * * *" in workflow
assert "--catalog all" in workflow
assert workflow.index("pytest") < workflow.index("catalog_registry_ingest")
assert "secrets." not in workflow
assert ".catalog_registry_cache" not in staged_paths(workflow)
assert "research/capability_registry.sqlite3" not in staged_paths(workflow)
assert "automation_intelligence/catalog_registry_v1/cycles/$RUN_ID" in workflow
assert "automation_intelligence/catalog_registry_v1/latest" in workflow
assert "chatgpt" not in workflow.lower()
```

`staged_paths()` in the test helper extracts arguments to `git add` lines only, so cache mentions in Actions cache configuration do not cause a false failure.

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest tests/test_catalog_registry_ingest.py -q`

Expected: FAIL because workflow is absent.

- [ ] **Step 3: Implement workflow**

Use `actions/checkout@v4`, `actions/setup-python@v5`, `actions/cache/restore@v4`, `actions/cache/save@v4`, `actions/upload-artifact@v4`. No other third-party action.

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
- Modify: `tests_engine/test_discovery_registry_service.py`

**Interfaces:**
- Documentation describes implemented foundation behavior only.
- It states that catalog presence is not qualification, policy is fail-closed, provider federation is read-only, registry is research/shadow only, and this phase has no API/MCP/UI or external source probes.
- Commands:

```bash
python -m tools.catalog_registry_ingest --catalog all --run-id manual-YYYYMMDD
python -m pytest tests_engine/test_discovery_registry_*.py -q
python -m pytest tests/test_catalog_registry_ingest.py tests/test_provider_exhaustive_collection.py -q
```

- [ ] **Step 1: Add the failing documentation test**

```python
def test_foundation_doc_states_authority_and_scope():
    text = Path("docs/icarus/CAPABILITY_DATA_DISCOVERY_REGISTRY.md").read_text()
    assert "execution_authorized=false" in text
    assert "production_decision_authorized=false" in text
    assert "DISCOVERED does not mean qualified" in text
    assert "provider federation is read-only" in text.lower()
    assert "does not expose HTTP, MCP, or dashboard surfaces yet" in text
```

- [ ] **Step 2: Run test and verify failure**

Run: `python -m pytest tests_engine/test_discovery_registry_service.py -q`

Expected: FAIL because documentation does not exist.

- [ ] **Step 3: Write documentation and README link**

Do not claim live catalog import success until an actual workflow/manual run produces receipts. Do not claim source qualification, alpha, shadow performance, or production readiness.

- [ ] **Step 4: Run targeted and repository regression suites**

Run:

```bash
python -m pytest tests_engine/test_discovery_registry_*.py -q
python -m pytest tests/test_catalog_registry_ingest.py tests/test_provider_exhaustive_collection.py -q
python -m pytest tests_engine -q
```

Expected: all PASS.

- [ ] **Step 5: Run static safety checks**

Run this Python check instead of shell-regex quoting:

```bash
python - <<'PY'
from pathlib import Path
paths = list(Path('icarus_engine/discovery_registry').rglob('*.py')) + [Path('tools/catalog_registry_ingest.py'), Path('.github/workflows/catalog-registry-refresh.yml')]
text = '\n'.join(p.read_text() for p in paths)
assert 'execution_authorized=True' not in text
assert 'production_decision_authorized=True' not in text
for secret_name in ('MASSIVE_API_KEY','TWELVE_DATA_API_KEY','FMP_API_KEY','INTRINIO_API_KEY','ALPACA_SECRET_KEY'):
    assert secret_name not in text
print('registry safety scan: PASS')
PY
```

Expected: `registry safety scan: PASS`.

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
- [ ] The CLI fetches public catalog content with no credentials and bounded payload size.
- [ ] Existing provider receipts link read-only; no duplicate provider request is made.
- [ ] Provider blocker/stale evidence never becomes success.
- [ ] Registry/receipts expose `execution_authorized=false` and `production_decision_authorized=false`.
- [ ] No raw catalog file or registry SQLite DB is staged by scheduled workflow.
- [ ] Existing provider collector regression remains green.
- [ ] Full `tests_engine` regression remains green.

## Deferred Plans Required to Complete the Approved Architecture

After this foundation lands, create these separate plans in order:

1. **Qualification & Source-Health Plan** — queueing, manual policy decisions, schema/latency/reliability/historical-depth probes, cost/budget gates, staleness/demotion.
2. **Exogenous Intelligence & Empirical Value Plan** — narrative/social/search/real-economy lanes, point-in-time data contracts, chronological OOS experiments, redundancy/marginal-information scoring, APEX ancestry/world-state integration.
3. **Operator Surface & Promotion Plan** — authenticated HTTP/MCP surfaces, DISCOVERY/SOURCES dashboard, shadow evaluation status, explicit promotion/demotion decision UI/API, continuing health review.

No deferred plan may weaken the authority or safety invariants fixed by this foundation and the approved spec.
