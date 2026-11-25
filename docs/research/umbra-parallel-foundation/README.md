# UMBRA × ICARUS — parallel construction continuation

Owner instruction: use the installed Ollama fleet for continuation, mixing large and small models concurrently whenever capacity permits, with at least 1.8 GB (1,800,000,000 bytes) estimated available physical RAM reserved. This supersedes the initial 1.5 GiB admission policy. No scheduled Codex, no live broker activation, no active runtime alteration, no downloads without authorization.

## Read first
- Complete historical discoveries and exact paths: [inventory PR #505](https://github.com/reppiks490/Icarus/pull/505), immutable snapshot 4674662ecb8c7e3eae4c57505591198bb9a43b85, docs/research/local-inventory-20261124/README.md and DEEP_DISCOVERIES.md.
- Current shared implementation branch: agent/umbra-parallel-foundation-20261124. All lanes must converge through versioned contracts in this branch; no hidden chat-only work.
- discovery-ledger.json tracks all 275 project locations, currently pending individual qualification. No project is integrated just because it appears in the ledger.
- Canonical coordination: reppiks490/icarus-owner-actions, session chatgpt-20261124-umbra-parallel-foundation. Its generated views were stale at inspection; avoid all unrelated paths and recheck live reservations.

## Construction status
Code in icarus_engine/umbra_lab:
- evidence.py: ordered causal prefix and canonical SHA256; in-memory forecast/settlement hash chain. Synthetic/historical/paper boundaries; not a persistent authenticated ledger.
- science.py: closed-interval purge and embargo, Brier score, mean-shift drift baseline (not calibrated ADWIN).
- world.py: deterministic paired-seed fixture and price-time book matching with integer ticks and quantity conservation. Not a calibrated exchange simulator.
- pipeline.py: deterministic shared synthetic research cycle. No trading authority.
- ollama_review.py: bounded loopback generation, concurrent distinct models, local append receipts, no external URLs, no model pulls, no generated code execution, no eviction of another Ollama workload.
- tests_engine/test_umbra_lab.py: nine core tests plus three mixed-size admission tests.
Original TDD RED b2489907e341b9104d654dd6ffea0727e69f522d failed on missing module. Initial GREEN at 26ac42fdaa5cf4d33507e9d851288aadeb637998: nine tests passed on Windows using isolated exact-source fixture, not full repository suite. Mixed fleet RED 197713ee6c37b017e43e703fc98ee49c8f0bc4f8: three expected failures; nine original tests passed. Mixed fleet implementation f0e70a139ce1d5324c673cf035c2ccb1374565a2: current verification job PID 31496 (read receipt; old PID identity may expire). Do not assume new tests pass until verified.

## Ollama continuation
Latest inventory: 14 installed tags, including 12 generation tags and two embedding tags. Windows physical RAM 16,906,256,384; available 5,071,253,504 at readback; free disk 11,235,975,168. No loaded models at that instant. These are snapshots. Model weights plus 1 GiB conservative overhead per distinct model; max four concurrent requests; largest feasible model first, then smaller models if remaining budget permits. Memory reserve is an estimated admission gate, not an OS-enforced guarantee. External loads may change memory mid-wave. Post-wave stop on observed reserve breach. Do not kill daemon or unrelated tasks. No claim of simultaneous resident models based only on concurrent requests.

Current queue: 17 bounded review assignments; generation candidates Qwen2.5-Coder 7B/1.5B, Qwen3 8B/4B/1.7B/0.6B, quantized Qwen3 8B, Phi4-mini, Granite3.3 2B, Granite4 350M, Gemma3 1B, DeepSeek R1 1.5B. Embedding-only tags not assigned generation. Larger models may be deferred if insufficient RAM. Do not resume paused downloads or lower reserve to force a model.
- Original worker run PID 37764, source fec8f798c9c5635defcbb41afca1deb1a8729a65, local <USER_HOME>/projects/icarus-umbra-continuation/ollama-reviews-20261124-01.jsonl. Three returned responses observed; generic or truncated, not accepted. Dispatcher stopped specifically to replace old reserve, daemon not terminated. No assertion about in-flight daemon request cancellation.
- Updated run PID 31496, local <USER_HOME>/projects/icarus-umbra-continuation/ollama-mixed-20261124-02.jsonl. It first runs all 12 focused tests, then starts model workers only on test success. Recheck actual output and local receipt before claiming completion.
- Re-run from a trusted checkout with python -m icarus_engine.umbra_lab.ollama_review --output NEW_UNIQUE_RECEIPT.jsonl. Existing receipts never overwritten. Inspect current Ollama tags/ps and RAM first. Keep output advisory, never execute model text or accept unsupported claims. Commit compact accepted/rejected evidence and pending IDs to GitHub, without secrets or raw market data. Model response does not prove independent validation. No automatic continuation beyond bounded jobs.

## Parallel engineering lanes (not completed)
1. Evidence fabric: bind capsule to instrument, representation, source version, strategy and model hashes; persistent tamper-evident ledger with trusted head, revision rules, atomicity and replay. Integrate NEXUS/AION in read-only research adapter.
2. Statistical court: independent holdout/purgedcv comparison, PBO/PSR/DSR, nested calibration and untouched final holdout.
3. Simulator: qualify ABIDES/HftBacktest/JAX-LOB against golden order sequences and authorized actual market replay. No claims of realistic fills from fixtures.
4. Stream recovery: Bytewax late events, watermark, idempotency, gaps; Feast feature contract.
5. Numerical models: qualify 14 pinned acquisition receipts, inference, rights and current package compatibility; resolve gplearn/sklearn conflict in isolated env.
6. MYRIAD: 190 FP16 files at last scan, exact receipts/training provenance, independent exams, compare to baselines.
7. Mathematical discovery: PySINDy, symbolic discovery, stability and falsification; no deterministic price law claims.
8. Quality diversity: pyribs behavior descriptors and qualified population archive.
9. Continual learning: River drift, TS2Vec, causal train-only features.
10. POLYMIND and Ollama: resource admission, role routing, review validation, resumable queue, receipt ingestion, shared task identities; integrate with UMBRA existing PR stack only after exact-head review.
11. Pulse and ICARUS: immutable original source, chart/fill provenance, independent shadow-only advisory output; no active runtime modifications.
12. Full discovery accounting, data/archive provenance, Git storage allocation analysis, third-party rights, observatory and end-to-end tests. Every location and recovered capability gets evidence-backed disposition. No cleanup without approval.

## Acceptance gates
All discoveries accounted for, no owned gaps silently ignored; source and runtime test evidence; shared contracts and exact versions; meaningful qualified capabilities rather than generated count inflation; independent holdout; no direct live authority. Current foundation is a first executable reference slice, not completed UMBRA financial simulation. Full suite and cross-repository integration not yet verified.
