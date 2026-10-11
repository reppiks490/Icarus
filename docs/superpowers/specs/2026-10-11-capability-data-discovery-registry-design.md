# ICARUS Capability & Data Discovery Registry — Three-Catalog Federation Design

Status: **Design specification — approved in conversation, pending written-spec review before implementation plan**

Repository: `reppiks490/Icarus`  
Design base: `0bf06e98c9fbda627116578f8686a178e6837d68`  
Date: 2026-10-11  
Authority: research/shadow only  
Production auto-promotion: **forbidden**

## 1. Purpose

Build one durable **ICARUS Capability & Data Discovery Registry** that continuously mines, normalizes, deduplicates, qualifies, empirically evaluates, and selectively promotes useful sources/capabilities discovered from all three user-selected catalogs:

1. `cporter202/API-mega-list`
2. `cporter202/scraping-apis-for-devs`
3. `cporter202/ai-agent-tools`

The catalogs are discovery universes, **not trusted production dependencies**. Their entries must never become live data sources, model inputs, execution inputs, or installed agent dependencies merely because they appear in a list.

The system turns the catalogs into a governed funnel:

```text
catalog discovery
  -> immutable provenance snapshot
  -> normalization
  -> classification
  -> duplicate-family resolution
  -> access/policy/schema/latency/reliability qualification
  -> historical-depth and point-in-time checks
  -> alpha/research hypothesis
  -> out-of-sample empirical evaluation
  -> shadow operation
  -> explicit promotion decision
  -> continuing health/drift review
```

The objective is not to maximize source count. The objective is to maximize **independent, lawful, point-in-time information gain per unit of latency, cost, instability, redundancy, and operational risk**.

## 2. Existing ICARUS boundary

This design extends the canonical `reppiks490/Icarus` repository. `reppiks490/Icarus-engine` remains a revision-pinned research/automation satellite and is not a second production integration root.

The canonical repository already contains a resumable provider acquisition plane:

- `config/provider_endpoint_catalog.json`
- `tools/provider_exhaustive_collection.py`
- `tests/test_provider_exhaustive_collection.py`
- `.github/workflows/provider-exhaustive-collection.yml`
- `automation_intelligence/provider_collection_v1/`

That plane currently drives admitted providers including Massive, Twelve Data, FMP, EODHD, Tiingo, Intrinio, Quiver, FRED, Alpaca, Bybit and Tickstream.

**The new registry must federate and extend this machinery, not duplicate it.** Existing provider operations and their receipts become high-quality qualification evidence inside the registry. The existing provider collector retains ownership of exhaustive endpoint acquisition for providers it already admits.

The registry also integrates with, but does not reimplement:

- **Continuous Learning Fabric** — empirical prediction/outcome, chronological evaluation, source-quality evidence, drift and calibration.
- **APEX Ω** — world-model evidence, economic state, information-gain ranking, evidence ancestry and epistemic governance.
- **Adaptive Brain / research qualification surfaces** — candidate/evidence qualification and shadow routing where present on the running revision.
- **Performance Proof / Champion-Challenger / DAEDALUS / AEGIS** — empirical proof, comparable shadow evaluation, scientific validation and adversarial falsification.

Catalog metadata is never APEX `observed` market evidence. A catalog record says only that a capability/source was advertised or listed at a pinned upstream revision.

## 3. Source-universe policy

### 3.1 `cporter202/API-mega-list`

Treat as the broadest candidate universe. Its category directories include agents, AI, automation, business, developer tools, e-commerce, integrations, jobs, lead generation, MCP servers, news, real estate, social media, travel, video and other domains.

Primary ICARUS opportunities:

- derivatives/positioning candidates;
- SEC/corporate-event sources;
- macro/public-data sources;
- news/geopolitical sources;
- social/search attention sources;
- supply-chain/procurement sources;
- weather/event sources;
- jobs/labor-demand sources;
- e-commerce/pricing/demand sources;
- real-estate/housing sources;
- travel/activity sources;
- agent/MCP/developer capability discovery.

Every listed entry is imported as `DISCOVERED`; none is assumed accessible, lawful for the intended use, stable, affordable, or incrementally useful.

### 3.2 `cporter202/scraping-apis-for-devs`

Treat as the focused public-web/Apify acquisition and alternative-data candidate universe. The current catalog snapshot previously inspected contains 2,622 deduplicated entries across 17 categories, including news, social-media, agents, automation, MCP servers, jobs, e-commerce, real estate and travel.

Primary ICARUS opportunities:

- narrative/news breadth;
- X/Reddit/YouTube/TikTok/public-social sensing;
- generic search/RAG/browser fallbacks;
- real-economy nowcasting inputs;
- specialist web-source discovery.

Scraper/browser actors receive a stricter policy, reliability and source-truth burden than official/licensed APIs.

### 3.3 `cporter202/ai-agent-tools`

Treat as a **capability/tool discovery catalog**, not as a market-data catalog and not as an autonomous-agent framework to import wholesale.

Primary ICARUS opportunities:

- research tooling discovery;
- coding/analysis capability discovery;
- model/tool alternatives;
- document/research workflow improvements;
- replacement/challenger capability scouting.

Entries from this catalog default to `capability_only=true` unless independent evidence establishes a legitimate data-source role.

## 4. Non-goals and hard exclusions

The subsystem must not:

- install or activate every listed tool/API/actor;
- purchase subscriptions, credits or metered calls without a separately configured approved budget;
- bypass paywalls, authentication, robots/access controls, licensing restrictions or technical restrictions;
- collect private/hidden user data merely because a third-party actor advertises that ability;
- treat scraped content as licensed redistribution rights;
- treat opaque third-party directional predictions as ground truth;
- invent bid/ask, order flow, depth, open interest, liquidation, funding, basis, exchange flow or any other field not actually supplied by the qualified source;
- silently infer event time from retrieval time;
- infer point-in-time historical availability from a present-day page;
- auto-promote a source/model to production or execution authority;
- modify broker/order/sizing/strategy state;
- allow catalog freshness or star count to substitute for empirical validation.

Questionable entries are retained as auditable rejected/quarantined candidates when useful for provenance; they are not silently deleted and rediscovered later.

## 5. High-level architecture

```text
                    THREE EXTERNAL CATALOGS
          API-mega-list | scraping list | AI tools
                           |
                           v
                 CATALOG SNAPSHOT LAYER
        upstream repo + commit + path + content hash
                           |
                           v
                    IMPORTER ADAPTERS
         parse -> normalize -> preserve raw provenance
                           |
                           v
                 CANONICAL REGISTRY STORE
          candidates / endpoints / capabilities / lineage
                           |
             +-------------+--------------+
             |                            |
             v                            v
        DEDUPLICATION                POLICY GATE
   exact + structural + semantic    access/license/ToS
             |                            |
             +-------------+--------------+
                           v
                QUALIFICATION ENGINE
 access -> schema -> latency -> reliability -> depth -> PIT
                           |
                           v
                  RESEARCH HYPOTHESES
        narrative / world / market / capability value
                           |
                           v
             EMPIRICAL / MARGINAL-VALUE ENGINE
       chronological OOS + cost + redundancy + stability
                           |
                           v
                    SHADOW ROUTING
               no production/execution authority
                           |
                           v
             EXPLICIT PROMOTION / DEMOTION LOG
```

The registry itself is metadata/control-plane infrastructure. Actual source data remains owned by the appropriate acquisition/data lane.

## 6. Repository decomposition

Planned implementation boundary:

```text
icarus_engine/discovery_registry/
    __init__.py
    contracts.py
    normalize.py
    importers.py
    dedupe.py
    policy.py
    qualification.py
    scoring.py
    store.py
    federation.py
    features.py
    service.py

tools/catalog_registry_ingest.py
config/catalog_registry_sources.json

automation_intelligence/catalog_registry_v1/
    snapshots/
    cycles/
    latest/

docs/icarus/CAPABILITY_DATA_DISCOVERY_REGISTRY.md

tests_engine/test_discovery_registry_*.py
tests/test_catalog_registry_ingest.py
```

Expected integration-only modifications may include:

```text
icarus_engine/research_service.py
icarus_engine/server.py
icarus_engine/dashboard.html
icarus_bridge/mcp_server.py
.github/workflows/catalog-registry-refresh.yml
README.md
```

The implementation plan must verify the exact current paths before editing. Existing provider collector internals should change only where a narrow reusable interface is required.

## 7. Canonical catalog snapshot contract

Every import run pins upstream state before parsing:

```text
catalog_id
upstream_repo
upstream_commit
upstream_path
retrieved_at
content_sha256
parser_revision
entry_count_raw
entry_count_normalized
parse_failures
```

Rules:

1. No mutable `main` reference may serve as historical provenance after ingest; exact upstream commit is mandatory.
2. A re-run of the same upstream commit/parser revision is idempotent.
3. Parser changes create a new parse revision without rewriting old provenance.
4. Missing or malformed entries are recorded as parse failures; they are not silently dropped.
5. Catalog descriptions are untrusted metadata, not evidence that advertised functionality works.
6. Sponsored/featured placement is retained only as provenance metadata; it cannot improve source quality or promotion score.

## 8. Canonical candidate contract

Each normalized candidate has a stable content-derived identity and preserves all source catalogs that mention it.

Required fields:

```text
candidate_id
canonical_name
provider_name
capability_kind
data_class
asset_classes[]
source_class
protocols[]
endpoint_or_tool_url
upstream_catalog_refs[]
upstream_entry_hashes[]
description
capability_only
challenger_only
auth_type
license_state
tos_state
policy_state
estimated_cost_model
budget_required
event_time_support
retrieval_time_support
historical_depth
refresh_frequency
schema_fingerprint
schema_stability
source_quality
reliability
latency_ms
freshness
leakage_risk
duplicate_group_id
predictive_value
marginal_information_score
qualification_state
disposition
first_seen_at
last_seen_at
last_verified_at
staleness_reason
metadata
```

Unknown values remain `null`/`UNKNOWN`; they are not filled with optimistic defaults.

### 8.1 `source_class`

Finite values:

```text
licensed_feed
official_public_api
official_public_file
public_structured_page
public_unstructured_page
third_party_api
scraper_actor
browser_agent
llm_extractor
mcp_capability
ai_tool
research_tool
unknown
```

The class controls the minimum evidence burden. A scraper or browser agent never inherits the authority of an official API simply because both expose similar fields.

### 8.2 `data_class`

At minimum:

```text
market_price
market_microstructure
derivatives_positioning
fundamental
corporate_event
macro
rates_credit
news
geopolitical
social
search_attention
regulatory
supply_chain
procurement
weather
labor
consumer_ecommerce
housing_real_estate
travel_mobility
crypto_chain
research_document
software_capability
other
```

A candidate may occupy multiple asset classes, but every harvested field must preserve its actual semantic meaning.

## 9. Qualification state machine

The normal forward path is exactly:

```text
DISCOVERED
-> ACCESS_TESTED
-> SCHEMA_PROFILED
-> LICENSE_TOS_CHECKED
-> LATENCY_TESTED
-> RELIABILITY_TESTED
-> DUPLICATE_CHECKED
-> HISTORICAL_DEPTH_TESTED
-> ALPHA_HYPOTHESIS_DEFINED
-> POINT_IN_TIME_BACKTESTED
-> SHADOW_MODE
-> PRODUCTION
```

`PRODUCTION` means an explicitly authorized production **data/capability source**, never automatic trading authority.

A separate disposition field captures exceptional state without corrupting lifecycle history:

```text
ACTIVE
QUARANTINED
REJECTED
STALE
DEMOTED
RETIRED
```

Rules:

- lifecycle transitions are append-only events;
- a later failure does not erase earlier evidence;
- promotion requires every preceding hard gate or an explicitly documented equivalent proof;
- policy failure can immediately set `REJECTED`/`QUARANTINED`;
- staleness can demote a formerly qualified source;
- no code path may jump `DISCOVERED` directly to `PRODUCTION`;
- production promotion requires an explicit promotion decision record; it is never inferred from score alone.

## 10. Acquisition hierarchy

When multiple lawful mechanisms can obtain equivalent information, prefer:

```text
1. licensed/direct feed
2. official public API/file
3. structured public webpage
4. generic crawler
5. browser agent
6. LLM-assisted structured extraction
```

The hierarchy is a preference, not a license to crawl. Every tier remains subject to policy/access checks.

Lower tiers require stronger schema-drift, source-truth, reproducibility and reliability evidence. LLM extraction must retain the source bytes/text hash and extraction schema/version so a result can be replayed and audited.

## 11. Existing provider federation

For a candidate matching an operation/provider already represented by `config/provider_endpoint_catalog.json`:

1. link the registry candidate to the existing provider/operation ID;
2. ingest provider-collection receipts as access/reliability/latency/schema evidence;
3. do not create a second downloader;
4. preserve endpoint-specific entitlement failures (`401`, `403`, quota, unsupported transport, etc.) as qualification evidence;
5. keep discovery completeness distinct from acquisition completeness.

The registry therefore expands the universe while the existing exhaustive collector remains the acquisition engine for already-admitted structured providers.

## 12. Deduplication and evidence ancestry

Deduplication is non-destructive. Entries are clustered into `duplicate_group_id` families using progressively weaker evidence:

1. exact normalized URL/tool ID;
2. exact provider + endpoint/capability;
3. canonical domain + route/resource identity;
4. normalized name/description fingerprints;
5. semantic similarity only as a candidate link requiring confirmation.

The registry keeps all upstream references even when multiple catalog entries describe the same underlying source.

APEX evidence ancestry must treat repackaged access to the same underlying dataset/source as shared ancestry. Five wrappers around the same underlying website are not five independent confirmations.

## 13. Policy, licensing and safety gate

`LICENSE_TOS_CHECKED` is a hard gate, not a guessed label.

Finite policy states:

```text
UNKNOWN
REVIEW_REQUIRED
ALLOWED_RESEARCH
ALLOWED_PRODUCTION_DATA
RESTRICTED
REJECTED
```

Automatic checks may identify obvious risk signals, but uncertainty must remain `UNKNOWN` or `REVIEW_REQUIRED` rather than auto-allow.

Immediate rejection/quarantine examples include:

- advertised paywall/subscription bypass;
- hidden/private-user extraction without a lawful explicit basis;
- credential/token harvesting;
- circumvention of access controls;
- content whose intended use would breach explicit licensing/redistribution restrictions;
- malware/spyware or unsafe automation behavior.

No secret may be stored in registry records, source snapshots, logs or committed artifacts.

## 14. Cost and budget governance

Every candidate records a cost model when known:

```text
free
subscription
per_request
per_result
compute_metered
unknown
```

`budget_required=true` whenever testing can create monetary cost beyond an already approved existing service entitlement.

The registry may rank paid candidates, but must not purchase, subscribe, or initiate unbounded metered workloads automatically. Cost estimates must be separated from measured cost.

## 15. Time and point-in-time truth

Every data-bearing source must distinguish:

```text
event_time      — when the real-world event occurred
published_time  — when the source says it became public, when available
received_time   — when ICARUS actually received it
retrieval_time  — when the fetch happened
calculated_time — when ICARUS derived a feature
```

Historical point-in-time validation requires defensible evidence that a value/content version was available by the simulated decision boundary. Present-day pages cannot be backfilled as though their current content had always been known.

For APEX historical reads, both source event/publication semantics and actual receipt/as-of constraints remain fail-closed.

## 16. Empirical scoring

Descriptive score dimensions include:

```text
quality
latency
cost
coverage
uptime
freshness
timestamp_integrity
historical_depth
schema_stability
policy_compatibility
leakage_risk
redundancy
predictive_value
marginal_information_score
```

A missing empirical score stays missing.

The primary decision quantity is **marginal information**, not standalone accuracy or popularity. Conceptually:

```text
MIS = delta_OOS_objective
      - redundancy_penalty
      - instability_penalty
      - cost_penalty
      - latency_penalty
      - leakage/policy_penalty
```

No fixed universal weights are hard-coded by this design. Weights/thresholds must be calibrated and versioned per research objective during implementation/empirical work.

`delta_OOS_objective` must compare against the current ICARUS information set, not against an empty baseline. A source that predicts well but adds no incremental information is redundant.

## 17. Opaque prediction/model sources

A source that emits a directional forecast, score, confidence or trade call without reproducible underlying methodology is imported with:

```text
challenger_only=true
```

Its output may enter a benchmark/challenger study, but:

- it is never labeled observed market truth;
- it cannot originate a trade;
- it cannot override price/market evidence;
- its predictive contribution must survive chronological point-in-time OOS tests;
- its information value must be measured after controlling for ICARUS's existing features;
- it remains removable without breaking the strategy core.

## 18. Exogenous world-model lanes

Qualified sources feed domain-specific research lanes rather than one undifferentiated feature soup.

### 18.1 Narrative / news / geopolitical lane

Candidate derived features include:

- narrative velocity;
- narrative acceleration;
- novelty;
- source disagreement;
- first-source vs echo-source propagation;
- entity/asset linkage;
- credibility-weighted tone;
- cross-source confirmation;
- narrative half-life.

### 18.2 Social / search-attention lane

Candidate derived features include:

```text
Attention Shock
Narrative Dispersion
Information Propagation Speed
Crowd Saturation
Influence-Weighted Sentiment
Narrative Reversal
Asset-Narrative Lead/Lag
```

These are derived/reconstructed features with explicit ancestry. Account/source influence weights must be earned from historical evidence rather than follower count alone.

### 18.3 Real-economy nowcasting lane

Jobs, e-commerce, real-estate and travel sources may produce point-in-time regional/category primitives such as hiring intensity, wage postings, discount intensity, product availability, listing inventory, rent/price changes, travel pricing and activity.

Potential latent research states include:

```text
ConsumerDemand_t
LaborTightness_t
HousingStress_t
DiscretionarySpending_t
InflationPressure_t
EconomicMomentum_t
```

These are reconstructed/inferred macro states, never raw observations. Their dependencies and uncertainty must be preserved into APEX.

### 18.4 Research/capability lane

AI-agent/dev/research tools are evaluated for capability gain:

- can the tool obtain information ICARUS cannot currently obtain?
- can it reduce latency/cost/failure rate?
- can it improve code/research verification?
- does it duplicate an installed capability?
- is it reproducible and auditable enough for the intended role?

A useful tool may be promoted as a research capability without ever becoming a market-data source.

## 19. Cross-domain contradiction engine

The highest-value target is not merely more features. The registry enables APEX to compare independently qualified domain states and detect disagreement such as:

```text
real-economy deterioration
+ rising risk/geopolitical narrative velocity
+ tightening/loosening rates-credit state
+ market price expansion
+ extreme retail/social optimism
```

Such disagreement becomes an auditable **cross-domain state contradiction**, preserving each domain's evidence and confidence rather than averaging them into a single sentiment scalar.

Contradictions are research hypotheses, not automatic trade signals.

## 20. Importer behavior

Each upstream catalog gets an independent importer with a common output contract.

Requirements:

- deterministic for a pinned upstream commit;
- idempotent;
- preserves category, URL, name, description and source path;
- records malformed rows;
- normalizes tracking/referral parameters out of identity while preserving the original URL in provenance;
- does not execute, install or call discovered services during catalog import;
- supports fixture-driven offline tests;
- never treats README marketing copy as verified capability.

Catalog import and source qualification are separate jobs. This prevents a giant catalog refresh from accidentally triggering tens of thousands of network probes.

## 21. Qualification scheduler

Qualification work is queue-based and budgeted.

Priority is driven by:

```text
estimated information value
x relevance to ICARUS assets/world model
x independence from existing sources
x policy confidence
x expected reliability
/ expected cost+latency+failure-surface
```

The queue must prevent one giant catalog from starving smaller high-value sources.

Suggested job classes:

```text
catalog_refresh
policy_review
access_probe
schema_probe
latency_probe
reliability_probe
historical_depth_probe
point_in_time_audit
shadow_evaluation
staleness_recheck
```

Every job is retry-safe and records bounded failure reasons.

## 22. Staleness and source drift

The registry distinguishes:

- catalog staleness;
- endpoint/tool disappearance;
- auth/entitlement change;
- schema drift;
- latency degradation;
- reliability degradation;
- data-quality degradation;
- policy/license change;
- predictive/marginal-value decay.

A production-qualified data source can be automatically **demoted from eligibility** on hard health/policy failures, but the registry cannot auto-authorize a replacement into production. Replacement promotion still requires the explicit promotion gate.

## 23. Persistence and audit model

Primary durable metadata store:

```text
research/capability_registry.sqlite3
```

Use SQLite WAL, append-only event tables for lifecycle/promotion decisions, and immutable upstream snapshot identity.

Expected logical tables:

```text
catalog_snapshots
catalog_entries
candidates
candidate_catalog_links
endpoints
capabilities
duplicate_groups
duplicate_members
qualification_events
policy_reviews
schema_profiles
health_observations
historical_depth_observations
research_hypotheses
empirical_evaluations
shadow_runs
promotion_decisions
source_relationships
```

Public/committed automation artifacts contain summaries/receipts only. Raw licensed/provider payloads remain subject to the existing secure/archive policy and must not be committed merely to make the registry reproducible.

## 24. API / MCP / UI surface

Read-only authenticated HTTP surface should expose bounded summaries:

```text
GET /api/discovery-registry
GET /api/discovery-registry/candidates
GET /api/discovery-registry/candidate/{id}
GET /api/discovery-registry/health
GET /api/discovery-registry/duplicates
GET /api/discovery-registry/evaluations
```

Research/admin mutations may include:

```text
POST /admin/discovery-registry/import
POST /admin/discovery-registry/qualify
POST /admin/discovery-registry/recheck
POST /admin/discovery-registry/policy-decision
POST /admin/discovery-registry/promotion-decision
```

Mutations must authenticate before parsing large bodies and accept strict bounded JSON.

Equivalent MCP tools may expose the same research operations, but no registry MCP tool may call broker/order/control endpoints.

The dashboard should provide one **DISCOVERY / SOURCES** surface showing:

- catalog freshness and pinned revisions;
- candidate counts by domain/state;
- duplicate-family counts;
- qualification funnel;
- policy rejection/quarantine reasons;
- source health/latency/schema drift;
- measured cost;
- marginal-information ranking;
- shadow/production-qualified sources;
- stale/demoted sources;
- unresolved evidence gaps.

## 25. Testing contract

The implementation must be test-first and default to **no network** in unit/CI tests.

Required test families:

1. **Importer fixtures** — all three catalog formats parse deterministically.
2. **Normalization invariants** — identities stable across harmless URL/text formatting changes.
3. **Provenance** — exact upstream repo/commit/path/hash always preserved.
4. **Idempotency** — repeated import of same snapshot produces no duplicate state.
5. **Deduplication** — exact and structural duplicates cluster without deleting provenance.
6. **Lifecycle** — illegal state jumps fail closed.
7. **Policy gate** — unknown/restricted/rejected policy cannot promote.
8. **Cost gate** — metered candidate cannot run without explicit budget entitlement.
9. **Secret hygiene** — secrets never persist in catalog/qualification records.
10. **Schema drift** — incompatible schema change creates an event and eligibility downgrade.
11. **Point-in-time** — future/current-only information cannot leak into historical evaluation.
12. **Opaque challenger** — challenger-only source cannot gain execution/production decision authority.
13. **Marginal value** — redundant source cannot be rewarded for duplicating an existing signal.
14. **APEX ancestry** — wrappers over same source remain one effective evidence family.
15. **Provider federation** — existing provider receipt links without creating duplicate downloader jobs.
16. **Demotion** — hard health/policy failure removes eligibility while preserving history.
17. **Authority invariants** — `execution_authorized=false` and `production_decision_authorized=false` remain immutable through research paths.
18. **Dashboard/MCP/API** — bounded/authenticated and absence renders as unknown/unavailable, never zero.

Network integration tests, when added, must be separately opt-in and budget bounded.

## 26. Rollout phases

### Phase 0 — registry kernel

Implement contracts, SQLite store, immutable snapshots, three importers, normalization, duplicate families, lifecycle and policy model. Import all three catalogs into `DISCOVERED` metadata state only.

### Phase 1 — existing-provider federation

Link registry candidates to the current endpoint catalog/provider collection receipts. Build access/schema/latency/reliability evidence adapters without duplicating acquisition.

### Phase 2 — qualification engine

Add bounded queueing, policy/cost gates, schema and historical-depth probes, staleness and source-health tracking.

### Phase 3 — exogenous research lanes

Promote selected lawful high-value sources into shadow ingestion for narrative, social/search and real-economy research features, preserving event/receipt time and evidence ancestry.

### Phase 4 — empirical marginal-value evaluation

Run chronological point-in-time experiments against ICARUS's existing information set. Record positive and negative results. Measure incremental value after cost, latency, instability and redundancy.

### Phase 5 — explicit source promotion

Allow only sources that satisfy all required gates to receive a production-data/capability promotion decision. No source promotion changes strategy or execution authority automatically.

### Phase 6 — continuous discovery/evolution

Refresh upstream catalog snapshots, detect new/removed entries, retest stale candidates, demote degraded sources and continually rank the next best qualification experiments by expected information gain.

## 27. Initial qualification priority

The registry imports **everything**, but qualification order should favor ICARUS-relevant information families:

1. official/structured market, derivatives, SEC/regulatory, macro/rates and corporate-event sources not already covered;
2. high-quality news/geopolitical sources;
3. search/Reddit/X/YouTube/public-social sources with defensible timestamps;
4. jobs/labor, e-commerce, real-estate and travel sources for economic nowcasting;
5. supply-chain/procurement/weather/event sources;
6. MCP/browser/RAG capabilities that close a real acquisition gap;
7. research/developer/AI tools that demonstrably improve ICARUS research capability;
8. low-independence, opaque or expensive sources only when an explicit hypothesis justifies testing them.

This is prioritization of qualification work, not cherry-picking the import universe.

## 28. Success criteria

The subsystem is successful when all of the following are true:

- all three upstream catalogs can be reproducibly imported at pinned revisions;
- every imported candidate has durable provenance and a deterministic identity;
- duplicate wrappers do not masquerade as independent sources;
- the existing provider collector is reused rather than duplicated;
- every source's lifecycle and disposition are auditable;
- risky/unknown-policy sources fail closed;
- paid testing cannot spend without explicit budget authority;
- point-in-time semantics prevent historical leakage;
- opaque prediction products remain challengers only;
- exogenous features preserve source ancestry and uncertainty;
- ICARUS can quantify incremental/marginal information rather than raw source count;
- negative results and rejected sources remain durable to prevent repeated wasted work;
- source health/drift can demote eligibility without silently replacing it;
- no research path changes broker/order/sizing/strategy state;
- `execution_authorized=false` and `production_decision_authorized=false` remain invariant unless a separate, explicitly governed future authority change is made outside this subsystem.

## 29. Explicit design decisions

1. **One registry, three catalogs.** Do not build separate long-lived catalog systems.
2. **Import everything; qualify selectively.** Completeness applies to discovery metadata, not unbounded network execution.
3. **Federate existing acquisition.** The current exhaustive-provider system remains authoritative for its admitted providers.
4. **Provenance first.** Upstream commit/path/hash is mandatory before candidate use.
5. **Non-destructive dedupe.** Collapse independence, not history.
6. **Policy before probing.** Access/license/ToS uncertainty fails closed.
7. **Point-in-time before alpha claims.** No historical availability proof, no backtest authority.
8. **Marginal information over popularity.** Source count, stars and marketing claims are not value.
9. **Shadow before production.** Empirical survival is required.
10. **No automatic production promotion.** Scores can recommend; they cannot authorize.
11. **APEX receives qualified evidence, not catalog marketing.** Metadata and observations remain separate truth classes.
12. **Capability tools and data sources share a registry but retain distinct semantics.** A coding assistant is not market evidence.

## 30. Implementation-plan boundary

This specification is intentionally one architecture with staged delivery. The implementation plan should decompose work into small test-first tasks, with Phase 0 and Phase 1 landing before any broad external probing.

No implementation task may broaden authority beyond this document. If implementation discovers an interface conflict that would require changing broker execution, strategy semantics, authority flags, or the existing provider collector's safety boundaries, stop and return to design review rather than working around the invariant.
