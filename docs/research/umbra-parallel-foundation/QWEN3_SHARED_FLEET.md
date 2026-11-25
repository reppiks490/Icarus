# Qwen3 shared-weight specialist fleet — continuation architecture

**Expanded owner-required architecture:** [LEARNING_AGENT_FEDERATION.md](LEARNING_AGENT_FEDERATION.md) and [agent-federation-registry.json](agent-federation-registry.json) extend the ten roles to 40 logical identities (primary plus three replicas per role), with independent trainable ML components, checkpoint lineage, blind reproduction, heterogeneous challenge, deterministic coordination, and qualified execution backends beyond Ollama. The exact 1.8 GB available-RAM reserve and all earlier research/discovery gates remain mandatory. This is a design specification; none of the forty identities is claimed trained or running.

Date: 2026-11-24 local time. Owner asked whether ten separate Qwen3 models can operate at once and requested the entire discussion be documented. This is a design and benchmark specification, not evidence of ten live agents. It extends the owner instruction to use Ollama for continuation, run large and small models in parallel where possible, and retain at least 1,800,000,000 bytes of available physical RAM. Existing implementation and tests remain in PR #506. Historical discovery evidence is in PR #505.

## 1. Architecture decision

Do not create ten independent copies of the same neural-network weights. Distinguish:
- **Model artifact**: one locally installed model tag, exact digest and quantization; may share on-disk blobs with other tags.
- **Resident runner**: a loaded model and its runtime allocations. Ollama manages runners; do not infer one runner per agent.
- **Agent identity**: durable role, instructions, task state, bounded context, separate memory and evidence history. Ten identities can exist without ten resident models.
- **Inference request**: one active or queued generation for an identity. Parallel requests for a shared resident model can share weights, but require separate context/KV cache and other runtime resources.
- **Trained specialist**: separately qualified weights or adaptation. Role prompts alone do not constitute independent training.

Ten separately loaded Qwen3 8B copies are not feasible on the observed PC. Ten logical agents sharing a model are feasible as an orchestration design; ten simultaneous generation streams have not been demonstrated. A mixed-size fleet offers differentiated roles and scheduling flexibility. Actual parallel execution is conditional on runtime settings, memory, context length and CPU throughput. Prefer effective useful work per second, not maximum request count at the expense of reliability. The same design can scale to 100 or more logical identities, but that is not a claim of 100 independent trained agents or simultaneous inference.

## 2. Proposed ten-agent roster

| Agent ID | Shared installed model | Primary responsibility | Example output |
|---|---|---|---|
| Q01 | qwen3:8b | Master architect | Interface and dependency decisions |
| Q02 | qwen3:8b | Advanced scientific reasoning | Falsifiable hypotheses and experimental design |
| Q03 | qwen3:8b | Mathematical discovery | Candidate equations, dimensional checks and counterexamples |
| Q04 | qwen3:4b | Code engineering | Small candidate patches and test specifications |
| Q05 | qwen3:4b | Algorithm development | Numerical method alternatives and complexity analysis |
| Q06 | qwen3:4b | Adversarial verification | Negative tests and edge cases |
| Q07 | qwen3:1.7b | Repository analysis | Source-located capability summaries |
| Q08 | qwen3:1.7b | Data analysis | Schema/provenance checks and proposed experiments |
| Q09 | qwen3:0.6b | Task orchestration | Bounded routing and queue triage |
| Q10 | qwen3:0.6b | Documentation and memory | Compact evidence-linked handoff drafts |

All four base tags were observed installed. These role assignments are proposed, not validated skill rankings. A stronger model can review a smaller model's suggestion but cannot substitute for executable evidence or independent scientific validation. Smaller models may produce vague or incorrect answers; route deterministic calculations and validation to code. Existing non-Qwen models and embedding models remain available as alternative challengers or retrieval specialists; do not delete them automatically.

## 3. Resource evidence and constraints

Historical Windows readback on 2026-11-24:
- Total physical RAM: 16,906,256,384 bytes; integrated Intel UHD observed previously.
- Initial available RAM: 5,071,253,504 bytes; free disk: 11,235,975,168 bytes; no resident models at that instant.
- Later available RAM: 2,477,699,072 bytes; resident qwen2.5-coder:1.5b and qwen3:1.7b. Only 677,699,072 bytes above the owner reserve. Resident status is not proof of active generation, and ownership of those runners was not established.
- Owner reserve: exactly 1,800,000,000 decimal bytes, not 1.8 GiB. Never reduce it to force admission.

| Tag | Observed artifact size (bytes) | Observed digest |
|---|---:|---|
| qwen3:8b | 5,225,388,164 | 500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41 |
| qwen3:4b | 2,497,293,931 | 359d7dd4bcdab3d86b87d73ac27966f4dbb9f5efdfcc75d34a8764a09474fae7 |
| qwen3:1.7b | 1,359,293,444 | 8f68893c685c3ddff2aa3fffce2aa60a30bb2da65ca488b61fff134a4d1730e7 |
| qwen3:0.6b | 522,653,767 | 7df6b6e09427a769808717c0a93cadc4ae99ed4eb8bf5ca557c90846becea435 |
| hf.co/bartowski/Qwen_Qwen3-8B-GGUF:IQ2_M | 3,051,916,941 | 5d26994cc45b60adfa70b02a95cd947867fe33cf0447e9648a376ab075dc4a68 |

The four main tags total 9,604,629,306 logical artifact bytes before runtime memory. Ten separate 8B copies would nominally sum to 52,253,881,640 artifact bytes, before cache and runtime overhead. Neither figure is a measured inference allocation. The low-bit 8B variant is a candidate for a memory/quality tradeoff benchmark, not proven equivalent to the standard 8B. Recheck exact tag digests before use. Disk capacity alone does not solve RAM pressure.

### Runtime settings to investigate

Official Ollama FAQ: https://docs.ollama.com/faq
- OLLAMA_NUM_PARALLEL: concurrent requests supported per loaded model.
- OLLAMA_MAX_LOADED_MODELS: maximum simultaneous model runners, subject to available memory.
- OLLAMA_CONTEXT_LENGTH: context budget; also inspect per-request num_ctx.
- OLLAMA_FLASH_ATTENTION: possible attention-memory optimization, subject to backend compatibility.
- OLLAMA_KV_CACHE_TYPE: optional cache quantization where supported; benchmark quality and actual memory before enabling.

These are configuration candidates, not changed settings. Inspect installed Ollama version, service ownership, environment and actual behavior before proposing any restart. Do not override an active workload. Existing dispatcher ollama_review.py currently admits **distinct models only**, caps workers at four, estimates each model's artifact size + 1 GiB, uses num_ctx=1024, num_predict=112, two threads, keep_alive=0 and loopback API. It does NOT implement ten persistent identities or same-model parallel requests yet. Shared-weight scheduling needs a separate implementation and tests, not a claim that the current runner already supports it.

### Proposed memory admission

For a candidate wave, account for each unique resident/load-required model once, per-request context/KV cache, per-runner and execution overhead, plus measurement uncertainty. Use measured incremental working-set/physical available RAM where possible; avoid double-counting already-resident weights in a budget based on current available memory. Unknown cost is a reason to defer. Initial conservative estimates must be calibrated on the actual hardware. Check available physical RAM and Ollama /api/ps before and during waves, retain the owner reserve, stop admitting new tasks if reserve is threatened, and release only owned workloads safely. Do not guarantee a hard floor against unrelated OS activity. Do not terminate unrelated services. No daemon-wide restart or settings change without verifying ownership and coordinating active work.

## 4. Shared task and memory architecture

One shared continuation branch and durable task queue; no isolated chat-only state. The intended pipeline:
ICARUS/UMBRA task -> immutable task envelope -> dependency-aware scheduler -> resource admission -> Qwen3 agent identity -> shared Ollama runner -> bounded response receipt -> independent verification -> accepted/rejected evidence ledger -> next task/handoff.

Each agent owns a distinct context and memory namespace; model weights are shared, not conversation state. Build agent registry, stable task IDs, source and revision references, role/prompt version, per-task context budget, allowed input scope, dependencies, attempts, lease/expiry, idempotency, resource estimate, actual start/end and terminal status. Persist verified summaries and exact source references in GitHub; keep private raw data and larger receipts local. Retrieve only task-relevant context to reduce ChatGPT context consumption. Do not feed one agent's unverified answer as ground truth to the next. Use a shared evidence contract and independent cross-checks. Prefer structured output with an actionable test or source reference; reject generic/truncated or unsupported output. Model text never executes directly and cannot grant permissions, live trading authority, or deployment approval.

The existing 17-task queue is not ten persistent identities. Preserve its prior receipts:
- <USER_HOME>/projects/icarus-umbra-continuation/ollama-reviews-20261124-01.jsonl: original review wave, three observed responses too generic/truncated to accept; dispatcher stopped to replace memory policy.
- <USER_HOME>/projects/icarus-umbra-continuation/ollama-mixed-20261124-02.jsonl: revised run, all 17 assignments deferred because existing Ollama runners occupied memory. 12/12 focused foundation and admission tests passed at f0e70a139ce1d5324c673cf035c2ccb1374565a2. No new inference in revised run; full repository tests remain unverified.

## 5. Benchmark and implementation roadmap

1. Re-read the shared branch and owner coordination bus. Recheck free RAM, disk, active models, server version and installed digests; no new download or eviction. Establish baseline CPU and memory for active system.
2. Implement persistent ten-identity registry, reproducible task envelopes, restart recovery, lease/idempotency and fair priority scheduling with tests. Preserve pending queue and history.
3. Test one small model at one request, then two and four requests sharing the same tag. Use independent prompts/contexts; measure actual overlapping inference intervals, not merely submitted HTTP calls. Record available RAM minimum, peak process/runner memory where accessible, throughput, latency, token counts, failures and context lengths. Benchmark both correctness and useful output per unit time.
4. Test mixed-size waves only when admitted. Start with small models; add larger reviewer when headroom permits. Compare qwen3:8b with quantized 8B and 4B using the same fixed task suite and rubric. Escalate to larger models on hard tasks, not every task.
5. Increase concurrency toward ten only after prior levels meet the reserve, stability, fairness and answer-quality gates. Compare throughput against serial execution and actual completion rate. A queued ten-agent roster is valid even when only one or two generations can run. Stop escalating if RAM, CPU, latency, context isolation or correctness deteriorates. Do not fabricate ten concurrent streams.
6. Test adversarial memory pressure, missing tags, external resident runners, duplicate jobs, timeout and retry, crash/restart, cross-agent context leakage, malformed model output and stale evidence. Verify no unintended downloads, external network calls or live execution hooks. Require exact-head regression evidence and repeatable receipts before promotion.
7. Integrate qualified review receipts into UMBRA Reality Court and ICARUS research evidence without enabling brokerage actions. Keep numerical calculations and model qualification independent from LLM opinions. Continue all 275 discovery dispositions and twelve engineering lanes through the shared handoff.

## 6. OpenBB and storage tradeoff

The preceding discussion compared financial-data infrastructure against reasoning models. Preserve useful OpenBB capabilities, not necessarily every byte of an unmodified third-party checkout. OpenBB can standardize provider access and provide research inputs (market data, macro, fundamentals, news and economic events) through supported Python/API/MCP interfaces; coverage, provider access, licensing, point-in-time semantics and installed runtime must be verified. It does not automatically make paid data free. A local reasoning model is complementary, not a substitute for data or numerical evidence.

Measured OpenBB location: <SYNC_ROOT>/ICARUS-EXTERNAL-GITHUB/source/openbq-org__OpenBB, observed HEAD prefix 7df7d0c5592, 2,727,510,370 logical bytes including 2,548,201,158 Git bytes; non-Git 179,309,212. FinanceDatabase (14,972,388,862 total; 14,753,996,337 Git) and CCXT (9,649,798,427 total; 9,132,449,951 Git) are larger Git-storage investigation candidates. ClickHouse 12,814,580,661 logical bytes, STARNET 5,946,680,137. These are historical logical lengths, not verified reclaimable space. See PR #505 GIT_STORAGE_AUDIT.md and findings-locations.json. Preserve unique history, current working state and applicable license; no deletion, compaction or re-clone authorized by this document. Prefer a verified minimal OpenBB runtime/provider subset only after qualifying needed capabilities and preserving original checkout. Benchmark already installed Qwen3 8B before considering a new larger model. 32 GB and 64 GB RAM upgrades could expand capacity if hardware supports them; no upgrade or model purchase is prescribed.

## 7. Completion and status

This architecture is documented, not deployed. Current shared dispatcher remains unchanged by this documentation. No ten-stream benchmark, Ollama settings change, new installation, removal, runtime mutation, merge or live trading activation. Next agent must carry the ten-identity/shared-weight design forward alongside existing research lanes, record actual results, and explicitly disposition every previously discovered capability. Context savings come from durable evidence and bounded delegation, not from trusting unverified local answers.
