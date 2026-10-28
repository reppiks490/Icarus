# RD-Agent local chat + embedding model plan admission (offline)

**Research-only candidate.** This is a proposal review for a separately provisioned Windows/WSL2 host, not a model installer, RD-Agent integration runtime, local-machine inspection, execution grant, credential reader, or confirmation of model compatibility. It is additive and does not change ICARUS strategy, Brain, broker, paper execution, UI, provider collectors, schedules or model training.

## Workflow and authority

On the **actual owner WSL2 environment**, after separately confirming the existing workspace is safe to inspect, produce a preflight with the already isolated module from draft ICARUS PR #486:

```bash
python -m icarus_engine.external_rd_agent_preflight --workspace . > host-preflight.json
python -m icarus_engine.external_rd_agent_model_guard --preflight host-preflight.json --plan proposed-model-plan.json
```

The first command only inventories available host RAM/cgroup limits and free disk. The second command **only parses two bounded JSON files**. Neither command installs a package, downloads weights, calls a model API, opens a socket, probes a GPU, trains a model, or modifies RD-Agent settings. Do not run the preflight on a GitHub Actions runner and claim that its readout describes the owner PC.

A plan is a JSON object with these exact keys (illustrative values, **not discovered owner hardware or installed models**):

```json
{
  "schema_version": "icarus-rdagent-local-model-plan-v1",
  "target": "WSL2",
  "concurrent_requests": 1,
  "chat": {"model_id": "local-chat", "endpoint": "http://127.0.0.1:11434/v1", "estimated_memory_bytes": 5368709120},
  "embedding": {"model_id": "local-embed", "endpoint": "http://[::1]:11434/v1", "estimated_memory_bytes": 2147483648},
  "estimated_peak_memory_bytes": 10737418240,
  "required_free_disk_bytes": 16106127360
}
```

Model IDs, endpoints, model footprints, and storage estimates are operator-supplied **hypotheses**, not detected facts. The guard accepts only numeric IPv4 `127.0.0.1` or IPv6 `::1` HTTP `/v1` endpoints with explicit ports; no DNS, public/private LAN address, credentials in URL, query parameters, TLS claims, or other paths. These checks prevent a plan from silently selecting remote endpoints; they do not verify whether a local server is running, which process owns the port, or whether it forwards requests off-host. Both chat and embedding models must have positive explicit memory estimates; the combined peak must include at least 2 GiB of overhead, and an additional 2 GiB of measured free RAM and 5 GiB of disk must remain. The host preflight must report a non-constrained WSL2 environment, at least 12 GiB effective free RAM and 25 GiB free disk. Concurrency must be one.

A structural pass emits `STRUCTURALLY_PLAUSIBLE_NOT_VERIFIED`, **never** `READY`, `VERIFIED`, `TRAINING_APPROVED`, or `EXECUTION_AUTHORIZED`. All runtime, entitlement, compatibility and model-weight verification flags remain false. A rejection prints only fixed reason codes, not input fields, URLs, model names, secrets or paths. Files larger than 64 KiB, symlinks, duplicate JSON keys and nonfinite values are refused. This does not substitute for independent RD-Agent version/config inspection, weights provenance/license, GPU/CPU throughput, actual peak RAM monitoring, embedding dimension validation, or a separately authorized localhost smoke test on the actual host.

## Test evidence and remaining gates

Synthetic offline regression fixtures cover loopback URL tricks, userinfo/query secret attempts, mismatched WSL2 identity, boolean/invalid memory inputs, missing overhead, insufficient RAM/disk, concurrency, JSON duplication and symlink inputs. These tests validate guard behavior only. Hosted Actions must be inspected at the exact PR head. No licensed data, provider calls, model execution, real fills or hardware attestation are produced. Keep the PR draft pending independent review, owner-host readback, native RD-Agent compatibility and explicit separate execution approval.

Coordination: independent of draft external quant fabric PR #486 and existing catalog/HFT/Nautilus/Brain/UI drafts. Report to Icarus Prime via the canonical `icarus-owner-actions` PLAN/HANDOFF records; do not interrupt its held paper restart or change its automation schedules.
