# Qwen3.6 27B Sovereign-tier acquisition and integration

Owner authorization: download and integrate Qwen3.6, selecting the previously discussed 27B IQ2_XS quantization. Scope: existing UMBRA × ICARUS research foundation; no replacement of active workloads or default models. Date: 2026-11-24 local.

## Exact source

- Model: Qwen/Qwen3.6-27B, Apache-2.0 (https://huggingface.co/Qwen/Qwen3.6-27B).
- Quantizer: bartowski; https://huggingface.co/bartowski/Qwen_Qwen3.6-27B-GGUF/blob/main/Qwen_Qwen3.6-27B-IQ2_XS.gguf
- Published artifact size: 10.20 GB. Published SHA-256: f3a6aaf277afa192fc92b0654ebd4a344b70078d8d36c3b651c5018019aec973. This is the published checksum, not a local downloaded-file measurement.
- Ollama exact requested tag: hf.co/bartowski/Qwen_Qwen3.6-27B-GGUF:IQ2_XS. Do not substitute the much larger default qwen3.6 tag. GGUF is highly compressed and may lose reasoning quality. Installed runtime/version compatibility remains unverified.

## Acquisition status: BLOCKED, not installed by this session

Desktop Commander device NQMoney_Machine listed online. Submitted a guarded command to verify at least 17,500,000,000 free bytes on C:, refuse non-C: custom model storage without separate review, check Ollama version, pull the exact HF tag and list the installed models. Call 5c0d22bb-b38e-4266-967d-014ae103acc0 returned terminal failure: PowerShell did not answer the blocked-command safety check in 15 seconds; nothing ran. No download, disk measurement, local install, inference, environment change or service restart confirmed. Do not circumvent command safety. Latest previous verified disk free was 24.60 GB, not a current measurement. The 40 GB additional cleanup is still incomplete. Check for existing partial/download state and available physical disk before reissuing the acquisition once the device is responsive. Preserve pending models and active workloads.

Owner-approved acquisition command after preflight:
```powershell
ollama pull hf.co/bartowski/Qwen_Qwen3.6-27B-GGUF:IQ2_XS
ollama list
```
A successful pull alone is not qualification. Inspect exact model manifest digest and actual blob; require expected weight SHA-256 and manifest linkage. If Ollama import or tag normalization differs, investigate rather than weakening the gates. Do not automatically install a newer runtime, unload other models or download a larger variant.

## Integration delivered in draft PR #506

- tests_engine/test_sovereign_review.py, test commit 251af7a3bdfd5e340f405cb71c32f8f664eca487, exact Git blob c14b93f493dafb76352c8a9b3e1e79b3a1da48da.
- icarus_engine/umbra_lab/sovereign_review.py, implementation commit 299e8315115ac47072a1de3f553d78fb47989028, exact Git blob 2deeb9cc1cdcd4adec9f2f02bbd250e58d3b6a27. Uses existing Ollama loopback request and physical-memory telemetry; independent opt-in CLI, not added to default mixed fleet, no downloads or automatic eviction.
- agent-federation-registry.json, commit b6e28b1bcc91805085cf0c9f83ba32f06285c136: candidate escalation for Q01–Q06 role families, status acquisition_blocked_unqualified; all existing 40 identities and their current preferences preserved. No claim of trained new agents.
- Fail closed on missing model, digest mismatch, invalid telemetry, any resident Ollama model, mismatched local manifest/blob SHA256, or insufficient available RAM. Solo qualification, 1.8 GB reserve plus estimated 2 GiB overhead; approximate minimum available RAM at 10.2 GB tag size is 14,147,483,648 bytes. Actual memory can be larger and unrelated load can race between checks; this is not OS-enforced isolation. Current machine total previously 16,906,256,384 bytes; current available RAM unverified. Model will often defer.
- Probe by default, explicit --run required for a single bounded research inference with thinking enabled, 1024 context, 256 output token limit, two threads, temperature zero, seed 42, keep_alive zero. Existing request timeout 100 s may be too short on CPU. Advisory result stays unqualified. No live trading, tool execution, agent training or automatic promotion.

## Verification and continuation

RED in isolated Linux Python fixture: expected missing sovereign_review module. GREEN: 7/7 focused tests passed using actual code, including memory boundary, resident-model refusal, exact model/digest, invalid telemetry, bounded inference body and synthetic manifest/blob tampering. Committed Git blob hashes matched tested local file hashes. Full repository tests, Windows execution, actual artifact verification and model inference not performed. Test command: python -m unittest discover -s tests_engine -p test_sovereign_review.py -v.

Once acquisition is verified, in a trusted checkout of this branch, use the exact installed manifest SHA-256 and a new receipt path (parent directory must exist):
```powershell
python -m icarus_engine.umbra_lab.sovereign_review --digest VERIFIED_MANIFEST_SHA256 --output sovereign-probe-001.jsonl
```
Only when probe passes and owner workload capacity remains safe, add --run with a different receipt filename. Require independent evaluation of reasoning, coding, math and causal/statistical correctness against existing Qwen3 8B and other models; record speed, peak physical RAM, post-run RAM, quality and truncation. No promotion until verified. Never lower the owner reserve to force a load. Keep the model disabled in automatic scheduling until this qualification is passed. No scheduled Codex, no live deployment, no merge to main in this task.

## Owner-selected paging-file option B — follow-up

Owner authorizes Windows paging-file capacity adjustment followed by acquisition only after sufficient physical RAM is established. Read-only preflight call 8f4c884e-a2a7-4b64-9ad8-4edb607c5958 requested current automatic management, allocated/peak/used page file, configured bounds, physical/virtual memory and drive space. It failed before execution because PowerShell did not answer Desktop Commander's blocked-command safety check in 15 seconds. No configuration, RAM, disk, process or model state was changed by this attempt. Do not bypass that check. Page-file growth increases commit capacity, not installed physical RAM; paging cannot guarantee the 14.15 GB physical admission requirement and can severely slow inference or trading workloads. Do not disable automatic management, reduce an existing page file, reserve a fixed 32 GB, or reboot blindly. First obtain actual page-file usage, commit headroom, free disk, privileges and physical memory; prefer system-managed paging when adequate. Preserve sufficient disk for the 10.20 GB model plus margin (17.5 GB pre-pull threshold) after any growth. Confirm whether a restart is required and preserve/checkpoint workloads before any restart. Recheck available physical RAM independently; defer if the reserve gate cannot pass. No acquisition until the owner's prerequisite is verified. Earlier GitHub integration remains disabled by default.
