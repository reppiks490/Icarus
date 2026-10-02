# ASCENDANCY Capability Orchestrator

## Purpose

The Capability Orchestrator is ASCENDANCY's truth boundary for external and internal capabilities. It answers four separate questions without conflating them:

1. What capability is declared?
2. Was that capability actually observed in the current audit?
3. What evidence may ICARUS legitimately claim from it?
4. What is explicitly forbidden to infer or authorize?

Tool presence is never treated as market truth, and provider availability is never treated as trading authority.

## Machine-readable sources

- `icarus_engine/ascendancy/capability_catalog.json` — stable provider/evidence contracts.
- `icarus_engine/ascendancy/capability_audit_2026-10-02.json` — point-in-time external capability probe.
- `icarus_engine/ascendancy/capabilities.py` — deterministic merged snapshot.
- `GET /api/ascendancy/capabilities` — authenticated read-only runtime surface.
- `icarus_engine/ascendancy-ui.js` — operator dashboard.

The audit file deliberately contains no connector credentials, tokens, session identifiers, account balances, or private account metadata.

## Current audit boundary

Observed working in the 2026-10-02 probe:
GitHub, Superpowers, Akinator, Astral Orchestrator skill contract, Adaptive Codex Orchestrator skill contract, Baton Pass skill contract, Agent Reach skill contract, Firecrawl, Parallel Search, Transcriptor, Figma, Prompt Perfect, Massive, Twelve Data, FMP, Bybit, Blockscout, Bigdata.com, The Fly, Zacks, and StackerScan.

Observed blocked:
- **Scite — BLOCKED_SUBSCRIPTION:** MCP access requires an eligible paid plan or active trial.
- **U.S. Gold Bureau — BLOCKED_NETWORK_POLICY:** the connector rejected the current environment under its IP allowlist policy.

Blockscout also reported that its connector requires PRO API-key authorization beginning 2026-10-08. That is a future access dependency, not a current market observation.

These states are audit evidence, not permanent health claims. A future runtime health service may supersede them with causal live checks.

## Market-data truth boundaries

- **Massive:** futures trades, quotes, snapshots, contracts and market-status endpoints were discoverable. Do not infer data classes an endpoint did not supply.
- **Twelve Data:** authenticated market-data connection was verified. Per-endpoint observations remain subject to their own contracts.
- **FMP:** commodity/futures symbol discovery, economics, filings, fundamentals and quote families are research/data capabilities, not authenticated exchange microstructure.
- **Bybit:** public crypto price, kline, order-book, funding and instrument-spec data may be used when returned. This connector does not receive account or order-placement authority.
- **Blockscout:** on-chain transactions, transfers, contracts and wallet/chain state are on-chain context. They are not exchange order flow or an exchange order book.
- **Bigdata.com / The Fly / Zacks:** financial documents, news, events, estimates and research are contextual evidence. They do not become hidden market microstructure.
- **Metals spot providers:** spot observations do not become futures order flow.

## Research and engineering capabilities

- **Superpowers** governs TDD, debugging, implementation planning, review and verification.
- **Akinator** governs repository knowledge, architecture memory, documentation and drift.
- **Astral / Adaptive Codex orchestration** are available as orchestration skill contracts; actual worker-dispatch availability is runtime-dependent.
- **Baton Pass** preserves cross-agent/session handoff state.
- **Agent Reach / Firecrawl / Parallel Search** provide independent public-research paths.
- **Transcriptor** turns supported public media into inspectable metadata/transcript/frame evidence.
- **Prompt Perfect** is a prompt-governance capability, not a market-data source.
- **Figma** is the design/diagram surface. The ASCENDANCY capability architecture diagram was generated during this audit.

## Dashboard contract

The ASCENDANCY tab exposes:

- total provider count;
- verified, blocked and unprobed counts;
- provider category;
- observed audit status and degradation reason;
- claims allowed;
- forbidden inferences;
- authority domain;
- audit timestamp and point-in-time warning;
- explicit `execution_authorized=false`;
- explicit `production_decision_authorized=false`.

Blocked capabilities remain visible so the operator can distinguish “not observed” from “observed unavailable.”

## Authority

The Capability Orchestrator may route research and data requests according to declared contracts. It does not grant broker permissions, production strategy mutation, live position control, or permission to convert inferred/unavailable data into observations.

Any later capability-routing engine must preserve this fail-closed contract.
