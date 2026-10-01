# On-chain / crypto intelligence collection handoff

SOURCE_LOOP=ONCHAIN_CRYPTO_EVENT_NARRATIVE_INTELLIGENCE
SOURCE_CHAT_OR_WORKSTREAM=ChatGPT Icarus collection-only on-chain/crypto intelligence loop
PRODUCER=ChatGPT GPT-5.6 Sol
CAPTURE_DATE=2026-09-28
PINNED_REPO_REVISION=f35705948be2040f3219fb87c10dff2193fcc003
POLICY_VERSION=collection-only-user-policy-2026-09-28
EXECUTION_AUTHORIZED=false

## 1. Purpose / original objective

Collect public, licensed, connected, or otherwise authorized on-chain, crypto-market,
alternative-data, event, security, issuer, regulatory, research, and narrative evidence
for the ICARUS ecosystem without coding, backtesting, optimization, scoring, ranking,
trade execution, wallet deanonymization, or downstream runtime mutation.

The loop preserves event time, first publication time, retrieval time, chain/network/venue
identity, revisions/corrections, source conflicts, duplicate narratives, access failures,
and source-specific semantics. Initial reports are preserved separately from later
corrections to prevent look-ahead leakage.

## 2. What was actually done

The collection loop repeatedly sampled and cross-checked:

- EVM chain tips and selected block details through Blockscout.
- Bitcoin public mempool / fee / block metadata through mempool.space, Blockstream,
  and BlockCypher.
- BTC/ETH/SOL spot, perpetual, funding, order-book, and short reaction-window data
  through Bybit plus cross-provider price observations from CoinGecko, TickerLayer,
  Twelve Data, and FMP where available.
- Global crypto market-cap / volume / dominance and stablecoin circulating-supply
  snapshots through CoinGecko.
- Primary and authoritative issuer/protocol/exchange/regulator/security material
  through Exa, Parallel Search, native web/search, SEC/CFTC issuer filings, and
  first-party protocol/exchange pages.
- Research-paper candidates through Firecrawl Research.
- Public YouTube search metadata through DataBlue.
- Corporate treasury filing deltas for Strategy and Bitmine through FMP SEC filing
  indexing.
- Provider capability/access failures and stale responses.

Latest verified collection window for this handoff:
2026-09-28 approximately 17:33-17:35 UTC.

## 3. Files/repo objects inspected

Repository selected:
- `reppiks490/Icarus`
- default branch: `main`
- pinned pre-write revision: `f35705948be2040f3219fb87c10dff2193fcc003`

Repository evidence inspected:
- `README.md`
- `ICARUS_LOOP_INDEX.md`
- `ASSURANCE_INDEX.md`
- `docs/icarus-control-plane/README.md`
- `docs/icarus/handoffs/INBOX_PROTOCOL.md`
- `docs/icarus/handoffs/inbox/README.md`

Repository deliberately rejected as the destination:
- `reppiks490/Icarus-engine`
- its README explicitly says: "STOP — this is the wrong repo" and points users to
  `reppiks490/Icarus`.

## 4. Verified findings

### 4.1 EVM chain state

Reconciliation state: COMPATIBLE

Fresh verified observations:

- Ethereum chain ID 1:
  - tip `26,077,475`
  - source timestamp `2026-09-28T17:34:23Z`
- Base chain ID 8453:
  - tip `51,913,765`
  - source timestamp `2026-09-28T17:34:37Z`
- Arbitrum One chain ID 42161:
  - tip `509,776,375`
  - source timestamp `2026-09-28T17:33:31Z`
- Optimism chain ID 10:
  - tip `157,509,014`
  - source timestamp `2026-09-28T17:33:25Z`
- Polygon chain ID 137:
  - tip `94,607,779`
  - source timestamp `2026-09-28T17:33:29Z`

Detailed Ethereum block:
- height `26,077,469`
- hash `0x07da89fc25b1dfb22ea4b7600ca7b178447b6e483648c1cd7e06a9fc95fe26f0`
- timestamp `2026-09-28T17:33:11Z`
- 368 transactions
- 1,942 internal transactions
- gas used 32,366,994 / 60,000,000 = 53.94499%
- base fee 1,963,495,085 wei/gas
- 3 blob transactions
- blob gas used 1,048,576
- 16 withdrawals
- Blockscout did not mark the block pending.

Base's first tip request in this pass returned an internal-server error; retry and final
verification succeeded. Preserve both facts.

### 4.2 Bitcoin native state

Reconciliation state: EVIDENCE_CONFLICT

Public providers exposed materially different mempool state:

- mempool.space: 83,323 unconfirmed transactions; about 43.37M vB
- Blockstream: 68,777 transactions; about 39.94M vB
- BlockCypher: `unconfirmed_count=8,872`

These values are NOT merged. They likely differ in provider/node/indexer state,
admission policy, timing, caching, and/or semantics.

BlockCypher's last collected chain snapshot was lagged relative to the main collection
window:
- height 969,024
- timestamp 2026-09-28T16:29:07Z
- therefore tagged STALE for canonical-tip use.

Blockstream fee-estimate snapshot previously collected:
- 1-2 blocks: 2.109 sat/vB
- 3 blocks: 1.904 sat/vB
- 4 blocks: 1.069 sat/vB
- 6 blocks: 0.325 sat/vB
- 144 blocks: 0.277 sat/vB
- 1008 blocks: 0.10 sat/vB

### 4.3 Multi-asset market / derivatives state

Reconciliation state: COMPATIBLE

Latest verified / near-window provider observations:

BTC:
- Bybit spot final verification: 83,886.60 USDT
- Bybit funding final verification: +0.0070%
- Bybit main-pull perpetual: 83,919.50 USDT
- CoinGecko final verification: 83,953 USD
- TickerLayer main-pull last: 83,955.55 USD
- FMP main-pull: 83,926.95 USD

ETH:
- Bybit spot main pull: 2,702.85 USDT
- Bybit perpetual: 2,701.91 USDT
- funding final verification: +0.0100%

SOL:
- Bybit spot main pull: 119.87 USDT
- Bybit perpetual: 119.820 USDT
- funding final verification: +0.0100%

No synthetic "true price" was created. Every value remains source/venue/timestamp specific.

### 4.4 Aggregate crypto / stablecoin state

Reconciliation state: COMPATIBLE

Final CoinGecko verification:
- total crypto market cap: approximately 2.88542T USD
- reported 24h volume: approximately 178.41B USD
- BTC dominance: approximately 58.260%
- ETH dominance: approximately 11.393%

Latest collected circulating supply fields:
- USDT: approximately 183.818816B
- USDC: approximately 74.843313B

Ethereum canonical contracts were independently resolved earlier in the loop:
- USDC: `0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48`, 6 decimals
- USDT: `0xdAC17F958D2ee523a2206206994597C13D831ec7`, 6 decimals

Global aggregate supply and Ethereum-contract supply are separate measurement objects.

### 4.5 Security / incident evidence

Reconciliation state: COMPATIBLE with revision history preserved

Bitget September 24 incident:
- initial affected-asset estimate: approximately 351.6M USD
- later revised estimate: approximately 387.5M USD
- initial and revised figures are both preserved
- Bitget states private keys and cold wallets were not compromised
- Mandiant and SlowMist were reported as supporting the investigation
- BTC withdrawals restored first on September 28
- ETH restoration scheduled for September 29 08:00 UTC
- USDT restoration scheduled for September 30 08:00 UTC
- broader restoration scheduled for October 2
- formal forensic/security report remained pending at the latest collected pass

Attacker identity remains UNVERIFIED. No deanonymization was attempted.

Historical primary security records also collected in the loop:
- Liquid / Blockstream consensus/security incident and recovery accounting
- Zano gateway vulnerability / chain rollback event
These remain separate historical event-time records and are not rewritten by later chain state.

### 4.6 Protocol / network-health evidence

Reconciliation state: COMPATIBLE

Solana primary engineering material collected:
- mainnet target slot time reduced to 250 ms
- published network-health study retained with validator/vote-latency cautions
- 200 ms stage treated as planned/cautionary rather than active

Base:
- Cobalt mainnet upgrade scheduled for September 30, 18:00-20:00 UTC
- pre-upgrade state should be sampled separately from post-upgrade state

Optimism and Polygon:
- direct chain-tip coverage added in the expanded loop
- no September 28 incident was elevated from secondary commentary without primary confirmation

### 4.7 Corporate treasury / issuer evidence

Reconciliation state: COMPATIBLE

Strategy:
- September 28 filing baseline: 847,666 BTC as of September 27
- later intra-day treasury quantities were not fabricated

Bitmine:
- September 28 filing baseline:
  - 6,001,302 ETH
  - 213 BTC
  - 5,067,309 ETH reported staked
- no later same-day filing superseded that baseline during collection

### 4.8 Tether / Circle evidence

Reconciliation state: COMPATIBLE when source attribution is retained

Primary Tether September 28 material collected:
- Tether stated approximately 550M USD of Iran-linked USDT had been frozen during 2026
  in actions involving wallets identified by U.S. authorities
- those figures remain Tether-attributed enforcement claims
- separate Tether/Shiga WDK collaboration for self-custodial finance was collected

Circle:
- transparency and product pages were collected
- cirBTC supply/product metadata was captured separately from native BTC
- Circle reserve page timestamps and extraction limitations were preserved

### 4.9 Research / narrative evidence

Reconciliation state: COMPATIBLE as research candidates only

Research candidates collected include:
- arXiv:2609.14481 — Quantifying Observable High-Frequency Swapping on Arbitrum
- arXiv:2609.28115 — No Place to Hide: protected-order-flow sandwich attacks
- arXiv:2605.23677 — AMP: Arc Multi-Proposer Protocol with Bounded Inclusion Guarantees
- arXiv:2508.04003 — Ethereum MEV transaction re-ordering

These are research-paper signals, not production facts.

Targeted DataBlue YouTube searches for the Bitget September 28 AMA and Solana 250 ms
engineering material returned zero indexed results. This is a provider-search result,
not proof that no video exists.

## 5. Hypotheses

- The mempool.space / Blockstream / BlockCypher Bitcoin mempool disagreement is probably
  driven by incompatible provider semantics, node/indexer state, caching, timing, and/or
  admission policies. This remains a hypothesis until provider definitions and timestamps
  are synchronized.
- Short bursts of near-full Ethereum blocks observed earlier in the loop may be transient.
  Rolling multi-block / multi-hour distributions are required before any congestion regime
  claim.
- CoinGecko stablecoin supply deltas may reflect real mint/burn activity, synchronization
  lag, or methodology changes. Chain-level issuer contract events are required before
  classifying aggregate deltas as issuance/redemption.

## 6. Rejected / failed attempts

Reconciliation state: BLOCKED or STALE as applicable

- Direct Bybit open-interest REST retrieval:
  provider transport failed.
- Binance Futures BTCUSDT open-interest endpoint:
  HTTP 451 through tested Firecrawl path.
- Massive derivatives discovery:
  relevant route required approval/login that was not available in the collection runtime.
- Tavily:
  relevant route required approval/login that was not available in the collection runtime.
- Scite:
  monthly MCP quota exhausted until 2026-10-01 UTC.
- Consensus:
  monthly search quota exhausted until 2026-10-01.
- FMP News:
  current subscription tier blocked crypto-news retrieval.
- Twelve Data:
  latest pass exceeded the provider's per-minute API-credit limit for requested BTC/ETH
  quote calls; those specific payloads were excluded from current-state verification.
- BNB Chain chain ID 56:
  unsupported by the Blockscout provider used.
- Base Blockscout:
  transient 500 on one request; subsequent retry succeeded.
- Base / Arbitrum detailed block endpoint:
  earlier 404 responses were preserved rather than filled with inferred values.
- Public YouTube search:
  targeted official AMA queries returned zero indexed results.

## 7. Open conflicts

- Bitcoin mempool provider counts are materially incompatible.
- Direct primary BTC/ETH/SOL open-interest and liquidation coverage is incomplete.
- Stablecoin aggregator supply deltas are not yet reconciled to issuer-chain mint/burn logs.
- Some secondary security/narrative stories contain attribution claims not confirmed by
  authoritative primary sources.
- Block/explorer tip state does not itself prove irreversible finality.
- Several provider/API timestamps lag the collection wall-clock and must remain source-specific.

## 8. Data / source limitations

- No private credentials, private personal data, restricted information, or deanonymization
  were sought.
- Wallet/address observations remain pseudonymous unless a primary public source already
  attributes them.
- Provider caching, quota limits, subscription tiers, unsupported chains, and HTTP failures
  are preserved as provenance.
- Market prices are not synchronized to an atomic cross-venue clock.
- No direct raw exchange liquidation tape was obtained.
- No direct canonical Bitcoin tip from two simultaneously live independent node APIs was
  established in the latest pass.
- No repo artifact claims that external ChatGPT automations are running.

## 9. Code changes actually made

None.

This handoff is documentation/evidence only. It does not modify:
- strategy code
- execution code
- broker/order permissions
- scoring or ranking logic
- models
- backtests
- runtime configuration

`EXECUTION_AUTHORIZED=false` remains unchanged.

## 10. Tests actually run

No code tests were applicable because no production/runtime code was changed.

Collection verification performed in the source workstream included fresh re-pulls of:
- Ethereum and Base Blockscout tips
- BTC Bybit spot/funding
- ETH and SOL Bybit funding
- CoinGecko global market state

Repository write verification must be done by reading back this exact file and the resulting
GitHub commit after creation.

## 11. Exact next action

1. Capture Bitget ETH-withdrawal restoration state at/after 2026-09-29 08:00 UTC.
2. Capture Base Cobalt pre-upgrade state immediately before 2026-09-30 18:00 UTC and a
   separately timestamped post-upgrade state.
3. Establish synchronized Bitcoin tip/mempool observations from at least two independent
   live node/provider APIs with documented semantics.
4. Obtain authorized primary BTC/ETH/SOL open-interest and liquidation data.
5. Collect chain-native USDC/USDT mint/burn event streams and bridge/cross-chain flow data.
6. Extend Ethereum rolling gas/blob/validator/staking state beyond isolated block samples.
7. Keep all new claims fail-closed for execution authority.

## 12. Artifact / file references

Repository target:
- `reppiks490/Icarus`

Canonical intake protocol:
- `ICARUS_LOOP_INDEX.md`
- `docs/icarus/handoffs/INBOX_PROTOCOL.md`
- `docs/icarus/handoffs/inbox/README.md`

This handoff path:
- `docs/icarus/handoffs/inbox/2026-09-28_onchain-crypto-intelligence_chatgpt.md`

Logical collection corpus identifiers represented by this handoff include:
- `ICARUS_ETH_TIP_26077475`
- `ICARUS_ETH_BLOCK_26077469`
- `ICARUS_BASE_TIP_51913765`
- `ICARUS_ARB_TIP_509776375`
- `ICARUS_OP_TIP_157509014`
- `ICARUS_POLYGON_TIP_94607779`
- `ICARUS_BTC_MEMPOOL_CONFLICT_V5`
- `ICARUS_MARKET_MULTI_ASSET_20260928T1734Z`
- `ICARUS_BYBIT_FUNDING_BTC_ETH_SOL_20260928T1734Z`
- `ICARUS_EVENT_PRIMARY_DELTA_20260928T1734Z`

This artifact adds durable evidence only. It does not increase trading authority.
