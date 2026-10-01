# ICARUS Adaptive Brain Fabric

This integration is the control/observability foundation for continuous multi-agent learning. It is intentionally **not** a claim of guaranteed profitability, omniscience, omnipresence, or autonomous broker authority.

## Runtime split

- **Hot path (target <=25 ms, measured not assumed):** consume already-qualified inputs/candidates, read current regime, apply uncertainty/risk/abstention, emit a shadow/decision-state result. No training.
- **Near-real-time:** microstructure/source health and incremental state.
- **Online adaptation (seconds):** robust baselines, calibration/drift/OOD monitors.
- **Research/falsification (minutes-hours):** training, ablations, costs, multiple testing, holdout, independent verification.
- **Scheduled retraining (hourly/daily/event-triggered):** heavy candidate refresh and rollback packages.

Training is never allowed to destabilize the latency-critical path.

## Five custom agents

1. OMEGA Fusion Core — supervisory reconciliation; owns ATHENA, JANUS, INFRASTRUCTURE, HELIOS PRIME.
2. Macro Shock Sentinel — macro/event state and provider routing; owns ORACLE and SUPERMESH-X.
3. Flow Velocity Engine — microstructure and causal data fabric; owns ARGUS and NEXUS.
4. AION PRIME Quant Scientist — causal memory/research evolution; owns AION, ASCENSION, PROMETHEUS.
5. DAEDALUS PRIME Systems Auditor — scientific validation/adversarial assurance; owns DAEDALUS and AEGIS.

## Candidate promotion

A candidate is only **shadow-route eligible** after all of these are verified: causal time, provenance, OOS, protected holdout, multiple-testing control, costs/slippage/latency, ablation, calibration, OOD/drift, deterministic replay, and independent verification. Even then:

- production_decision_authorized=false
- execution_authorized=false

The Adaptive Brain may select a regime specialist for shadow evaluation. It cannot silently change the production strategy or place an order.

## Continuous custom-agent ingestion

The five cloud automations persist material results as immutable `icarus-mcp-event-v1` files in `reppiks490/Icarus-engine/automation_intelligence/mcp_interface/events/`. The local engine's `BrainRemoteSync` polls that repository plane and accepts an event only when:

- the source is one of the five custom-agent source identities,
- `execution_authorized=false` is explicit,
- the downloaded bytes reproduce the exact Git blob SHA advertised by GitHub,
- the event is converted to an idempotent local Adaptive Brain event.

Recognized nested subsystem findings such as ARGUS/NEXUS are also projected into subsystem state. Unknown MCP sources are ignored rather than silently treated as brain evidence. Network/sync failure cannot crash the trading engine. The default poll interval is 60 seconds when a GitHub token is available and 300 seconds otherwise.

This closes the cloud-to-local evidence path without giving a cloud agent production or broker authority.

## Continuous local research learning

Completed bounded ICARUS research studies are continuously scanned into the Brain without changing production behavior. New studies capture the exact clean ICARUS Git revision at study start when it can be proven. A research-qualified study becomes a `validated` candidate, **not** a `qualified_shadow` candidate.

The local research workflow may truthfully establish dataset/baseline provenance, disjoint train/validation evidence, protected holdout consumption, and stressed commission/slippage evidence. It does not by itself establish feature-level causal correctness, latency realism, multiple-testing control, ablation sufficiency, calibration, OOD/drift robustness, deterministic rerun equality, or independent verification. Those gates remain UNKNOWN/closed until separate evidence exists.

No-candidate, failed, timed-out, cancelled, and interrupted studies are also retained as durable learning so the system does not repeatedly rediscover the same failed research path. A dirty or unknown code revision cannot mint a Brain candidate.

## Truthful operator metrics

The panel shows measured values only. A missing success rate is rendered as UNMEASURED. Latency targets are labeled targets until instrumentation supplies actual distributions. Learning is evidenced by durable events and before/after validation state, not by an unsupported claim that the model "self-learned."
