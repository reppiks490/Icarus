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
