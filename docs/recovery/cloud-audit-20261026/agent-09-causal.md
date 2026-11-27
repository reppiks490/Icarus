# 09 — Causal router readiness

Read-only source inspection; no tests, network, or repository edits. Applicable AGENTS and central coordination/state were consulted. Paths below are workspace-relative.

**Contract.** `icarus-causal-router/causal_router/engine.py:36–99` defines Policy: required `feature_names`, `reviewed`, `sources`; optional feedback/freshness/uncertainty/switch/score/drawdown/pending limits. Reviewed keys are `candidate@version`, records exactly `{evidence_digest,source_digest,asset,timeframe}`. Events require `{id,type,observed_at}` plus exactly:

- candidate: `candidate_id,version,evidence_digest,source_digest,asset,timeframe,feature_names,expires_at,split`.
- decision: `decided_at,asset,timeframe,source_digest,feature_names,features,event_time,available_at,split`.
- outcome: `event_time,decision_id,rewards,split,reward_basis`.
- revoke: `candidate`.

Epoch-millisecond clocks are chronological; decision time equals observation time; feature availability cannot exceed decision time. Features/rewards are finite [-1,1]; development/shadow only. Outcomes require strictly later maturity and exactly the frozen prediction candidate set, with `reward_basis=net_risk_units` (`engine.py:128–264`). Results carry `authority=research_only, execution_allowed=false`; decisions include selected candidate/null, reason, predictions and switch cost. Outcomes return learned count/decision ID. SQLite journals pin the policy hash, chain original events/results, replay on open, and accept exact retries (`journal.py:43–173`). CLI `run --policy --events --db --report` accepts ≤2MB policy and ≤1MB JSONL lines, emits digest/count/timing/summary; `demo` adds synthetic/non-market flags (`cli.py:41–115`).

**Consumers and useful dormant work.** Local Icarus Python/workflow searches found no router import, CLI invocation, or report consumer. Engine registers it solely as `SYNTHETIC_ASSURANCE_ONLY`, referencing workflow/AGENTS (`Icarus-engine/config/federated_repo_evidence.json:59–64`); its contract tests check registry labels, not ingestion (`tests/test_crossrepo_evidence_federation.py:11–39`). The actual learner, risk routing, failure reviews and journal are wired internally, yet unavailable to sibling research consumers. `docs/PLAN.md` package 6 explicitly defers real artifact adapters, corpus validation and ablations; stale next-task text still requests already-existing packages 1–5. This is deferred integration, not evidence of abandoned code.

**Actual defect / next fix.** `verify` checks only that the DB file exists (`cli.py:97–100`), then opens the initializing Session. An existing empty SQLite/zero-byte file receives new tables and policy witness (`journal.py:59–100`) and returns `verified_replay=true`. Add a verification-only, read-only open requiring existing schema/witness before replay; cover empty files and byte-identical preservation. Separately implement a versioned research adapter/receipt consumer before claiming runtime integration. Daily assurance produces synthetic assurance artifacts only, never market validation.
