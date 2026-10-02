# ASCENDANCY Open-Ended Genome Lab Implementation Plan

**Goal:** Make ICARUS architecture itself a bounded, reproducible research object that can be generated, mutated, compiled into isolated research plans, archived with lineage, evaluated under immutable contracts, and visualized in the ASCENDANCY dashboard.

**Research inputs:** The design incorporates open-ended archive/stepping-stone ideas from Darwin Gödel Machine, CORAL, AutoDiscovery, AlphaEvolve/FunSearch, and quality-diversity/MAP-Elites literature, while preserving ICARUS's stricter causal/protected-validation boundaries.

## Core rules
- Research/shadow only.
- No broker credentials, live order placement, production strategy replacement, or live sizing authority.
- Architecture mutation is data first; arbitrary source-code mutation is not required for ordinary genome experiments.
- Every genome has exact code provenance, parents, mutation history, falsifiers, and resource budgets.
- Compilation is deterministic and fail-closed.
- Evaluator definitions are independent of the candidate and immutable during an evaluation.
- Structural novelty is not predictive edge.
- Diversity is preserved so unusual stepping stones are not killed merely for lacking immediate global dominance.
- Missing evidence remains UNMEASURED/UNAVAILABLE.

## Task 1 — Genome contract and deterministic compiler

Create:
- icarus_engine/ascendancy/genome.py
- tests_engine/test_ascendancy_genome.py

Implement:
- normalize_genome()
- genome_id()
- compile_genome()

Genome fields:
- source_repo
- source_commit (exact 40-char Git SHA)
- parent_genome_ids
- nodes
- edges
- mutation
- falsifiers
- resource_budget
- evaluation_contract

Node kinds:
- native
- foreign_lens
- generated
- hybrid

Compiler requirements:
- unique node ids
- valid source/target edges
- no self loops
- DAG topology for compiled research runtime
- native nodes must be registered
- foreign/generated/hybrid nodes require an explicit adapter id and isolation=true
- deterministic topological layers
- deterministic runtime hash
- no execution/production authority

TDD:
1. commit failing tests;
2. verify RED on Linux;
3. implement;
4. verify GREEN on Linux and Windows.

## Task 2 — Persistent open-ended archive

Create:
- icarus_engine/ascendancy/archive.py

Extend tests:
- tests_engine/test_ascendancy_genome.py

SQLite WAL archive stores:
- genomes
- parent/child lineage
- compile receipts
- evaluations
- behavior descriptors / niches
- objective contract identity
- evidence
- retirement/rejection reasons

Implement:
- GenomeArchive.register()
- GenomeArchive.record_compile()
- GenomeArchive.record_evaluation()
- GenomeArchive.retire()
- GenomeArchive.snapshot()

Archive rules:
- idempotent genome registration
- append-only evaluation receipts
- parent ids cannot be silently rewritten
- objective-contract mismatch blocks comparison
- nonfinite metrics rejected
- no automatic production promotion
- lineage survives retirement

## Task 3 — Quality-diversity and search frontier

Create:
- icarus_engine/ascendancy/frontier.py

Implement:
- Pareto dominance under explicit max/min objective directions
- novelty descriptors
- exact niche identity
- nondominated frontier per evaluation contract
- niche representatives / stepping stones
- parent sampling metadata only; no autonomous code mutation yet

The archive must preserve:
- high-quality global candidates
- diverse niche candidates
- failed but informative stepping stones
- parentage of later successful descendants

No candidate may be called superior unless the compared metrics share the same immutable evaluation contract.

## Task 4 — Authenticated server surface

Modify:
- icarus_engine/server.py
- tests_engine/test_ascendancy_genome.py

Add:
- GET /api/ascendancy/genomes
- POST /admin/ascendancy/genome
- POST /admin/ascendancy/genome-evaluation
- POST /admin/ascendancy/genome-retire

POST routes mutate research state only and must prove that paper/live trading state is unchanged.

## Task 5 — ASCENDANCY dashboard evolution surface

Modify:
- icarus_engine/ascendancy-ui.js
- tests_engine/test_dashboard_js.py

Add visible sections:
- Architecture Genome
- Search Frontier
- Evolution Lineage
- Diversity / niches
- Compile blockers
- Evaluator contract
- Resource budget
- Parent/child ancestry
- Current frontier
- rejected / retired / stepping-stone state
- explicit research-only authority

No metric may render missing data as zero.

## Task 6 — Adaptive Brain registration and docs

Modify:
- icarus_engine/brain.py
- tests_engine/test_brain.py
- docs/icarus/ASCENDANCY_CAPABILITY_ORCHESTRATOR.md

Create:
- docs/icarus/ASCENDANCY_GENOME_LAB.md

Register:
- ascendancy-genome-lab, owner omega

## Task 7 — Full verification

- exact-head Linux full tests
- exact-head Windows ASCENDANCY + dashboard + brain tests
- deterministic compile replay test
- code review against ASCENDANCY spec
- compare against latest main before integration
- no merge to main until the integration branch is refreshed from the then-current main

## Follow-on slice

After the genome lab is green:
- Candidate Foundry
- Mechanism Extractor
- Unknown-Unknown Engine
- Invention Engine
- autonomous research scheduler
- evaluator cascade / resource economy
- foreign-lens descendants
- objective-evolution research behind a second-order validation boundary
