# UMBRA Ω Reasoning Distillation Foundry

Status: design only, 2026-11-24. Owner requested documentation of reasoning-only compression and separately authorized immediate sequential acquisition of the three teacher candidates. Integrate with the existing federation in draft PR #506; no disconnected project.

## Scientific boundary and teacher candidates

Reasoning is distributed through model weights, not a separate complete capability file. Response distillation trains a smaller student on verified solutions; LoRA adjusts a compatible base; retrieval provides external evidence; quantization lowers precision. None guarantees all teacher capabilities. Do not claim training from downloaded weights, datasets or agent identities.

| Proposed teacher | Student target | Domain |
|---|---|---|
| Qwen3.6 27B IQ2_XS | 4B | General reasoning |
| OLMo 3.1 Think 32B IQ2_XS | 4B | Scientific discovery and independent challenge |
| Qwen3.6 35B-A3B IQ2_XS | 4B | Engineering and orchestration |
| Verified examples from all three | 8B | Multidisciplinary synthesis |
| Specialist accepted examples | 1.7B or smaller | Routing, retrieval, narrow tasks |

Student sizes are design targets, not existing checkpoints or proven equivalence. Teacher artifacts remain unverified locally; see QWEN36_MMAP_HANDOFF.md. Compare each against existing higher-precision Qwen3 8B/4B; extreme quantization may harm reasoning. Three teacher parameter counts are not one merged model.

## Mechanisms

1. Inventory existing distilled checkpoints and compatible pretrained adapters, exact provenance, rights, version, digest and size; e.g. DeepSeek-R1-Distill-Qwen-1.5B/7B (https://github.com/deepseek-ai/DeepSeek-R1). These are not distillations of the three selected teachers. Additional acquisitions require authorization.
2. Build independently verified reasoning bank: mathematical solutions, executable test evidence, causal counterexamples, verified derivations, scientific experiment records. Teacher outputs are candidates, not truth labels. Retrieval does not modify weights.
3. Train compact students by supervised response distillation; logit distillation separately requires compatible distributions/tokenizers. Do not assume Ollama supplies logits. GGUF inference files are not automatically suitable training checkpoints.
4. LoRA/QLoRA candidates: exact base/tokenizer architecture, target modules, rank, dtype and training format, versioned separate checkpoints. See https://huggingface.co/docs/peft/main/en/conceptual_guides/lora and https://arxiv.org/abs/2106.09685. Tens to hundreds of MB is a possible range, not a measured size. No arbitrary cross-family adapter reuse.
5. Evaluate pruning/expert pruning/quantization against untouched baseline; preserve original weights and rollback.

## Ten adapter labels and shared federation

LOGOS formal logic (Q02/Q06); AXIOM mathematics (Q03); AION causal/temporal (Q02/Q08); DAEDALUS engineering (Q01/Q04); MYRIAD experimentation (Q02/Q05); ORACLE probability (Q02/Q08); NEXUS cross-domain retrieval (Q07/Q08); PROMETHEUS algorithms (Q05); JANUS adversarial (Q06); UMBRA synthesis (Q01/Q09/Q10). Labels are proposals, not new implementations of the named subsystems.

Teacher/corpus access -> candidate examples -> deterministic/independent verification -> accepted reasoning bank -> training manifest -> student/adapter candidates -> protected evaluation -> Reality Court -> qualified POLYMIND routes -> existing 40 logical identities -> failure feedback. Preserve Q01–Q10 P/T/X/V role families, separate learner checkpoints, deterministic broker, task leases, independent evaluation, MYRIAD candidate lineage, AION/NEXUS causal evidence, UMBRA counterfactual simulations, ICARUS advisory-only boundaries. No automatic self-promotion or live execution.

Proposed corpus record: immutable example ID, task family, prompt, concise solution, verifiable answer, independent check results/versions, model/tokenizer digest, settings, source/license, timestamps and causal availability, split group, lineage, disposition/rejection reason, evidence hash. Training manifest: exact base, dataset digest/splits, adapter config, trainable parameter count, optimizer/seed, environment, sequence/batch/compute bounds, checkpoint lineage, metrics and recovery. Private content local; compact non-sensitive receipts in GitHub.

## Qualification and resource constraints

Deduplicate and group-split problem templates; preserve time ordering for finance; maintain untouched final holdout. Compare teacher, unadapted student, trained student, retrieval-only and deterministic-tool baseline. Grade arithmetic/symbolic results, code tests, causal ordering, statistical leakage, calibration, paired-world and book invariants. Measure accuracy, robustness, latency, peak physical RAM, disk and restart recovery; accept only independently demonstrated improvements with regression checks. Preserve failed candidates and dissent. No claims of profit or generalized equivalence.

Exact 1.8 GB physical RAM reserve unchanged. Current owner screenshot 5.5 GiB available on 16 GB DDR4 machine, iGPU, system-managed paging. Full 4B/8B training feasibility unestablished; inference memory budgets do not cover optimizer/gradients/activations. Start with retrieval and compact numerical learners; one bounded adapter pilot only after resource and compatibility checks. Remote compute/teacher APIs require specific authorization and cost/rights review. No scheduled Codex, no main merge, no trading mutation, no forced reboot.

## Continuation

1. Restore normal remote command execution, inspect actual model inventory, disk and memory. Verify three teacher downloads only if actually present, no duplicate pulls.
2. Inventory existing lightweight distillations/adapters and lawful corpus sources, compare retrieval/tool routes before spending capacity.
3. Test-first implement example schema, append-only evidence bank, deterministic graders, dedup/group-split checks and training receipts in existing branch.
4. Establish heldout baseline and pilot one compact specialist, measure resources, record failures. Train only when feasible and authorized; otherwise use qualified pretrained candidates or retrieval.
5. Compare student/adapter against teacher and unchanged base on independent tasks; promote via Court into existing registry only after measured gates, with rollback.
6. Record actual receipts and blockers in GitHub. No student or adapter has been trained or downloaded by this documentation; no new implementation tests run.

Read README.md, LEARNING_AGENT_FEDERATION.md, agent-federation-registry.json, QWEN36_SOVEREIGN.md and QWEN36_MMAP_HANDOFF.md before continuing. The design does not replace the owner's priority to acquire the three selected models sequentially.

## First implemented evidence-bank increment

Draft PR #506 now contains `icarus_engine/umbra_lab/distillation.py` (implementation commit d371fcf78ecd0307722d00d1d2c924ad5f939f3a, verified Git blob 3a08a42d1a883d6f627ddc4977dcc613380580c3) and `tests_engine/test_distillation.py` (test commit 088b8b605a020f25447334bf07b04baa22fc2eb6, verified blob a240f8e2dfc6a3739a381e8b85e1527321d9e613). Test-first RED: missing module; GREEN: 8 passed in 0.06s with Python 3.13 in isolated Linux fixture, using `python -m pytest tests_engine/test_distillation.py -q`. Exact Git blob hashes match both local files. Full repository suite, Windows execution and hosted CI not established.

Implemented exact rational multiplication/ratio grading and causal clock-prefix count, strict bounded answer parsing without expression execution, synthetic-only source/rights fields, duplicate identity and cross-split exact task/group guards, immutable-copy projections, accepted training-only deduplicated examples, split metrics, SHA256 hash-chain replay against an externally trusted head (detects mutation and truncation against that head). No teacher inference, actual learned weights, persistent transaction store, authentication, real-world rights verification or automatic federation promotion. Group labels are caller-provided, not a semantic near-duplicate detector; equivalent but differently encoded tasks can evade exact-task matching. Digest fields describe claimed provenance, not actual artifact verification. Metrics count response rows, not independent tasks. This is a bounded research foundation only. Next: deterministic trusted task generator with template-group allocation, independent hidden evaluator, robust semantic grouping, durable transactional store, run receipts and exact artifact qualification before expanding training. Preserve active workloads; local acquisition is independent of this code.

## Compact ML and deep learning fabric — implemented research pilot

Implementation `icarus_engine/umbra_lab/learning_fabric.py` commit 96d0e8c3f45e7b72b63a5710adffde6080d49ce8, exact tested blob dbfb4edd7257d8341ac2a63637aea821f75f3f55. Tests `tests_engine/test_umbra_distillation_learning.py` commit 5e931edc934d3e6e6b04e3eeec00a35aa629dcfd, exact tested blob f7cb0c463acfe38ef12b18f1f32b981173425f1d. The pre-existing large tests_engine/test_learning_fabric.py is untouched; a rejected create request was followed by a new distinct path and coordination update. Uses existing Bank; fit replays integrity chain, selects train-only rows for exact claimed model digest, rejects duplicate tasks and one-class labels, caps 4096 rows and 200 epochs. Eight bounded pre-answer task features; standard-library logistic regression (9 parameters), optional CPU PyTorch tanh MLP 8→16→8→1 (289 parameters), seeded initialization and Adam, JSON weights with strict dimensions/finite values/digest and independent pure-Python inference, training-dataset digest, evaluation accuracy/Brier/log loss. Scheduler plans dependency-safe waves, validates cycles, respects estimated 1.8 GB physical reserve and CPU-thread budget; it does not launch workers or enforce OS limits. Candidate status always synthetic; no live promotion.

RED: missing module. GREEN: 10 passed, 1.85 seconds, Python 3.13 / PyTorch 2.10.0+cpu, OMP_NUM_THREADS=1 MKL_NUM_THREADS=1, isolated Linux fixture with exact distillation.py Git blob 3a08a42d1a883d6f627ddc4977dcc613380580c3. Optional deep tests skip when Torch absent; no skips in this run. Reproduce with `python -m pytest tests_engine/test_umbra_distillation_learning.py -q` in trusted checkout with optional deep dependency installed. Nonlinear sign-interaction fixture: 64 train, 64 heldout, disjoint exact tasks and magnitude groups but same underlying synthetic rule. Linear accuracy 0.5, Brier 0.25, log loss 0.6931471805599453; deep accuracy 1.0, Brier 7.401372811316244e-7, log loss 0.0006722291392428674. Evaluation digest 66f58db4cb24340d9eb7eb1549ded64c5975dd6f38dcd2731f49f4f5fe4975c2. Linear checkpoint digest 7fd02ac7175ad231a76c232e1111932c9506cab9c0ba42529c3d349901e43964; deep 6c233711d69e2eec78bb5b7ef9e98135fc61409c570de6e2623603384ea8ac10. Checkpoints generated in isolated synthetic benchmark, not deployed or persisted as production weights. These metrics show ability to learn a toy interaction, not actual teacher quality, trading edge, or independent 40-agent competence.

Next: transactional persistent task/receipt store, authenticated external head, feature/provenance validation on real teacher outputs, time-aware calibration and grouped uncertainty, compact online update/drift detection and separate per-agent checkpoints, actual controlled scheduler execution with resource telemetry, adapters and distillation training only when qualified and authorized. Full repository suite, hosted CI and Windows qualification not yet established. No runtime change, paid calls, model loading, new downloads or live broker activation. Acquisition transcript independently still indicated first Qwen attempt at last read, no completed teacher established.
