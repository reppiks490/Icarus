# ICARUS previous-loop migration import index

PINNED_REPO_REVISION=449aef107bb868d1f18ab7eddc2bf4c3398f783b
CAPTURE_DATE=2026-09-28
EXECUTION_AUTHORIZED=false
SENSITIVITY=PUBLIC_SAFE

This import preserves valuable prior ChatGPT loop/workflow state as immutable repo-native handoffs without flattening ownership.

## Seed inventory
Active-at-master-handoff collection loops:
1. AEGIS Corpus Collector
2. Advanced CSV Data Collector
3. Microstructure Sensor Grid
4. Macro Regime Data Grid

Paused/disabled-but-legitimate definitions:
5. Onchain Event Intelligence Grid
6. Icarus Build Loop
7. Infrastructure Loop Build
8. VECTOR ∞ Loop
9. AEGIS Challenger Forge
10. MASTER LOOP GOVERNOR
11. SuperMesh-X Evolution
12. ASCENSION ∞ Series
13. Advanced CSV Loop
14. Icarus Central Orchestration
15. PROMETHEUS Loop

Additional historical execution identity: JANUS run series inside Icarus Build.

Already durable and referenced rather than duplicated:
- on-chain handoff: docs/icarus/handoffs/inbox/2026-09-28_onchain-crypto-intelligence_chatgpt.md
- commit 64bc8196df6e6674995f1fbb04c7b3e91960e787
- current AEGIS repo path: docs/icarus/research/aegis_challenger_forge/
- recent AEGIS durable commit: 6b30a42cf92bc08d0e6fee2f92d8544ed62e6363
- recent Microstructure durable commit: f35705948be2040f3219fb87c10dff2193fcc003

## Rules
- one immutable first-pass handoff per source loop;
- repository evidence outranks chat summaries;
- preserve failures/negative evidence;
- collection/build/governance/orchestration remain distinct;
- raw licensed/private/secret data stays out of this public repo;
- scheduler timestamps are not proof of completion;
- REPO_WRITE=VERIFIED only after remote commit + read-back verification.
