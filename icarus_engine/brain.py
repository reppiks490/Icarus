"""ICARUS adaptive-brain observability and shadow-routing plane.

This module deliberately separates fast decision inference from slow learning and
training. It records evidence-backed learning/candidate events, exposes the full
multi-agent/subsystem fabric to the trader UI, and computes regime-specific
*shadow* candidate routes. It never grants production decision or broker authority.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

SCHEMA_VERSION = "icarus-adaptive-brain-v1"
_EVENT_SCHEMA = "icarus-brain-event-v1"
_EVENT_LOCK = threading.Lock()

AGENTS = (
    {
        "id": "omega",
        "title": "OMEGA Fusion Core",
        "job": "Supervise the fabric, reconcile cross-agent evidence/conflicts, and choose the highest-value safe integration target.",
        "owns": ["ATHENA", "JANUS", "INFRASTRUCTURE", "HELIOS PRIME"],
    },
    {
        "id": "macro",
        "title": "Macro Shock Sentinel",
        "job": "Continuously update causal macro/event context and provider/source routing without inventing shocks or unavailable data.",
        "owns": ["ORACLE", "SUPERMESH-X"],
    },
    {
        "id": "flow",
        "title": "Flow Velocity Engine",
        "job": "Measure authenticated microstructure/flow anomalies and maintain causal market-data identity, clocks, quality, replay, and source health.",
        "owns": ["ARGUS", "NEXUS", "DATA"],
    },
    {
        "id": "aion",
        "title": "AION PRIME Quant Scientist",
        "job": "Maintain causal market memory, evolve falsifiable research hypotheses, and independently evaluate trust/collision evidence.",
        "owns": ["AION", "ASCENSION", "PROMETHEUS", "PARALLAX", "DREAMSTATE", "PSI", "ML"],
    },
    {
        "id": "daedalus",
        "title": "DAEDALUS PRIME Systems Auditor",
        "job": "Run protected scientific validation and adversarial falsification for the entire fabric; never self-clear a defect.",
        "owns": ["DAEDALUS", "AEGIS", "PROVENANCE"],
    },
)

SUBSYSTEMS = (
    {"id": "icarus", "title": "ICARUS", "owner": "ICARUS", "job": "Deterministic production strategy semantics, paper execution state, and final execution boundary."},
    {"id": "nexus", "title": "NEXUS", "owner": "flow", "job": "Causal market-data fabric: identity, representation, clocks, quality, lineage, replay, OOD/source health."},
    {"id": "argus", "title": "ARGUS", "owner": "flow", "job": "Authenticated microstructure and execution-physics truth; separate true depth/trades from proxies."},
    {"id": "aion", "title": "AION", "owner": "aion", "job": "Durable as-of market memory, forecast/outcome history, evidence identity, and replay."},
    {"id": "athena", "title": "ATHENA", "owner": "omega", "job": "Supervisory world state, uncertainty aggregation, confidence, risk routing, abstention, and counterfactuals."},
    {"id": "daedalus", "title": "DAEDALUS", "owner": "daedalus", "job": "Protected scientific validation, holdout budgets, multiple-testing control, stress/ablation/drift, promotion discipline."},
    {"id": "aegis", "title": "AEGIS", "owner": "daedalus", "job": "Adversarial falsification for leakage, causal-time violations, OOD collapse, circular evidence, and weak oracles."},
    {"id": "oracle", "title": "ORACLE", "owner": "macro", "job": "Financial/research automation: causal financial state, falsifiable theses, information-value research, thesis health."},
    {"id": "prometheus", "title": "PROMETHEUS", "owner": "aion", "job": "Autonomous research evolution: mine disagreement, generate hypotheses, route experiments, preserve negative results."},
    {"id": "ascension", "title": "ASCENSION", "owner": "aion", "job": "Independent evaluator/trust/collision fabric for manifests, proofs, evidence, and sibling compatibility."},
    {"id": "janus", "title": "JANUS", "owner": "omega", "job": "Causal project twin for reconciliation, dependency-aware prioritization, proof-carrying evolution, and handoff memory."},
    {"id": "infrastructure", "title": "INFRASTRUCTURE", "owner": "omega", "job": "Runtime health, recovery, rollback, bounded-autonomy supervision, durability, and dependency/topology safety."},
    {"id": "helios-prime", "title": "HELIOS PRIME", "owner": "omega", "job": "Cross-system integration, source economy, sibling adapters, and meta-research/self-audit."},
    {"id": "supermesh-x", "title": "SUPERMESH-X", "owner": "macro", "job": "Capability/provider discovery, health/drift-aware routing, provenance, failover, and execution-contract boundaries."},
    {"id": "parallax", "title": "PARALLAX", "owner": "aion", "job": "Observed counterfactual twin ledger: immutable decision identity, paired replay, regret, branch coverage, subsystem ablation attribution, and reproducible alternative-path evidence."},
    {"id": "psi", "title": "ICARUS Ψ", "owner": "aion", "job": "Research-only latent-pressure and possibility engine: microstructure elasticity, dynamic leadership, counterfactual price, future-space entropy/collapse, phase boundaries, forced consensus, and fail-closed abstention."},
    {"id": "dreamstate", "title": "DREAMSTATE", "owner": "aion", "job": "Counterfactual-policy incubator: turn repeated statistically screened PARALLAX regret patterns into versioned hypotheses held behind the full protected validation gate stack."},
    {"id": "provenance", "title": "PROVENANCE", "owner": "daedalus", "job": "Exact code/data/artifact lineage, commit binding, receipt integrity, and proof-chain validation."},
    {"id": "ml", "title": "ML", "owner": "aion", "job": "Research-only model lifecycle, training evidence, calibration, drift/OOD state, reproducibility, and candidate packaging."},
    {"id": "data", "title": "DATA", "owner": "flow", "job": "Raw-source identity, availability-time truth, representation quality, freshness, and replay-safe market evidence."},
)

LATENCY_TIERS = (
    {
        "id": "hot",
        "title": "Hot decision path",
        "target": "<=25 ms target, measured not assumed",
        "job": "Feature read, regime lookup, already-qualified candidate inference, risk/abstention checks.",
        "training_allowed": False,
    },
    {
        "id": "near",
        "title": "Near-real-time evidence",
        "target": "25-250 ms target where feed/runtime supports it",
        "job": "Microstructure aggregation, source-health checks, incremental state updates.",
        "training_allowed": False,
    },
    {
        "id": "online",
        "title": "Online adaptation",
        "target": "1-10 s",
        "job": "Robust baselines, calibration monitors, drift/OOD detection, evidence accumulation.",
        "training_allowed": "bounded statistics only",
    },
    {
        "id": "research",
        "title": "Research / falsification",
        "target": "minutes-hours",
        "job": "Hypothesis generation, ablation, stress, independent verification, candidate training and qualification.",
        "training_allowed": True,
    },
    {
        "id": "retrain",
        "title": "Scheduled retraining",
        "target": "hourly/daily or event-triggered",
        "job": "Heavy retraining, walk-forward evaluation, protected holdout, regime-specialist refresh, rollback packaging.",
        "training_allowed": True,
    },
)

CANDIDATE_STAGES = {
    "discovered",
    "training",
    "validated",
    "qualified_shadow",
    "rejected",
    "retired",
}
REQUIRED_CANDIDATE_GATES = (
    "causal_time",
    "provenance",
    "oos",
    "protected_holdout",
    "multiple_testing",
    "costs_slippage_latency",
    "ablation",
    "calibration",
    "ood_drift",
    "deterministic_replay",
    "independent_verification",
)
_ALLOWED_KINDS = {
    "agent",
    "subsystem",
    "candidate",
    "regime",
    "learning",
    "source",
    "decision",
    "drift",
    "training",
    "evaluation",
}
_ALLOWED_STATUS = {
    "observed",
    "active",
    "verified",
    "qualified",
    "rejected",
    "blocked",
    "degraded",
    "retired",
    "unverified",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _text(value: Any, name: str, limit: int, *, required: bool = False) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    value = value.strip()
    if required and not value:
        raise ValueError(f"{name} is required")
    if len(value) > limit:
        raise ValueError(f"{name} exceeds {limit} characters")
    return value


def _json_value(value: Any, name: str, limit: int) -> Any:
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as ex:
        raise ValueError(f"{name} must be finite JSON") from ex
    if len(raw.encode("utf-8")) > limit:
        raise ValueError(f"{name} exceeds {limit} bytes")
    return value


def _journal_path(base_dir: str | os.PathLike[str]) -> Path:
    return Path(base_dir) / "audit" / "brain_events.jsonl"


def _event_semantic(body: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(body, Mapping):
        raise ValueError("brain event must be an object")

    kind = _text(body.get("kind"), "kind", 32, required=True).lower()
    status = _text(body.get("status", "observed"), "status", 32, required=True).lower()
    if kind not in _ALLOWED_KINDS:
        raise ValueError("unsupported brain event kind")
    if status not in _ALLOWED_STATUS:
        raise ValueError("unsupported brain event status")

    evidence = body.get("evidence", [])
    if isinstance(evidence, str):
        evidence = [evidence]
    if not isinstance(evidence, list) or len(evidence) > 32:
        raise ValueError("evidence must be a list with at most 32 items")
    evidence = [_text(x, "evidence item", 700, required=True) for x in evidence]

    semantic: dict[str, Any] = {
        "schema_version": _EVENT_SCHEMA,
        "kind": kind,
        "subject": _text(body.get("subject"), "subject", 160, required=True),
        "summary": _text(body.get("summary"), "summary", 2200, required=True),
        "status": status,
        "evidence": evidence,
        "details": _json_value(body.get("details", {}), "details", 32768),
        "execution_authorized": False,
        "production_decision_authorized": False,
    }

    if kind == "candidate":
        candidate_id = _text(body.get("candidate_id"), "candidate_id", 180, required=True)
        stage = _text(body.get("stage"), "stage", 40, required=True).lower()
        if stage not in CANDIDATE_STAGES:
            raise ValueError("unsupported candidate stage")

        regimes = body.get("regimes", [])
        if isinstance(regimes, str):
            regimes = [regimes]
        if not isinstance(regimes, list) or not regimes or len(regimes) > 24:
            raise ValueError("candidate regimes must be a non-empty list")
        regimes = [_text(x, "regime", 80, required=True) for x in regimes]

        metrics = body.get("metrics", {})
        if not isinstance(metrics, dict):
            raise ValueError("candidate metrics must be an object")
        metrics = _json_value(metrics, "metrics", 16384)

        validation = body.get("validation", {})
        if not isinstance(validation, dict):
            raise ValueError("candidate validation must be an object")
        normalized_validation: dict[str, bool | None] = {}
        for gate in REQUIRED_CANDIDATE_GATES:
            value = validation.get(gate)
            if value is not None and type(value) is not bool:
                raise ValueError(f"validation.{gate} must be boolean or null")
            normalized_validation[gate] = value

        source_repo = _text(body.get("source_repo"), "source_repo", 180, required=True)
        if "/" not in source_repo:
            raise ValueError("source_repo must be owner/repository")
        source_commit = _text(body.get("source_commit"), "source_commit", 40, required=True).lower()
        if len(source_commit) != 40 or any(c not in "0123456789abcdef" for c in source_commit):
            raise ValueError("source_commit must be an exact 40-character Git SHA")

        semantic.update(
            {
                "candidate_id": candidate_id,
                "stage": stage,
                "regimes": regimes,
                "metrics": metrics,
                "validation": normalized_validation,
                "source_repo": source_repo,
                "source_commit": source_commit,
            }
        )
    return semantic


def _event_id(semantic: Mapping[str, Any]) -> str:
    raw = json.dumps(dict(semantic), sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _stored_event(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("stored brain event must be an object")
    if raw.get("execution_authorized") is not False or raw.get("production_decision_authorized") is not False:
        raise ValueError("stored brain event cannot authorize production or execution")
    semantic = _event_semantic(raw)
    event_id = _text(raw.get("id"), "id", 64, required=True)
    if event_id != _event_id(semantic):
        raise ValueError("stored brain event id does not match semantic payload")
    out = dict(semantic)
    out["id"] = event_id
    out["recorded_at"] = _text(raw.get("recorded_at"), "recorded_at", 80, required=True)
    return out


def record_brain_event(base_dir: str | os.PathLike[str], body: Mapping[str, Any]) -> dict[str, Any]:
    """Append one idempotent learning/agent/subsystem/candidate event.

    Events can influence research/shadow routing only. They cannot authorize a
    production strategy change or broker action.
    """
    semantic = _event_semantic(body)
    event = dict(semantic)
    event["id"] = _event_id(semantic)
    event["recorded_at"] = _utc_now()

    path = _journal_path(base_dir)
    path.parent.mkdir(parents=True, exist_ok=True)
    with _EVENT_LOCK:
        if path.is_file():
            for line in path.read_text(encoding="utf-8").splitlines():
                try:
                    prior = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(prior, dict) and prior.get("id") == event["id"]:
                    stored = _stored_event(prior)
                    return {
                        "ok": True,
                        "idempotent": True,
                        "event": stored,
                        "execution_authorized": False,
                        "production_decision_authorized": False,
                        "note": "brain event already recorded; research/shadow authority only",
                    }
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    return {
        "ok": True,
        "idempotent": False,
        "event": event,
        "execution_authorized": False,
        "production_decision_authorized": False,
        "note": "brain event recorded; research/shadow authority only",
    }


def _read_events(base_dir: str | os.PathLike[str], limit: int = 1000) -> tuple[list[dict[str, Any]], int]:
    path = _journal_path(base_dir)
    if not path.is_file():
        return [], 0
    errors = 0
    rows: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return [], 1
    for line in lines[-max(limit * 2, limit):]:
        try:
            rows.append(_stored_event(json.loads(line)))
        except Exception:
            errors += 1
    rows.sort(key=lambda x: (str(x.get("recorded_at", "")), str(x.get("id", ""))))
    return rows[-limit:], errors


def candidate_gate(candidate: Mapping[str, Any]) -> tuple[bool, list[str]]:
    """Return shadow-routing eligibility and exact blockers."""
    blockers: list[str] = []
    if candidate.get("stage") != "qualified_shadow":
        blockers.append("stage is not qualified_shadow")
    validation = candidate.get("validation")
    if not isinstance(validation, Mapping):
        return False, ["validation evidence missing"]
    for gate in REQUIRED_CANDIDATE_GATES:
        if validation.get(gate) is not True:
            blockers.append(f"{gate} gate not verified")
    if candidate.get("execution_authorized") is not False:
        blockers.append("execution authority must remain false")
    if candidate.get("production_decision_authorized") is not False:
        blockers.append("production decision authority must remain false")
    return not blockers, blockers


def _latest_candidates(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in events:
        if row.get("kind") == "candidate":
            latest[str(row.get("candidate_id"))] = row
    out = []
    for row in latest.values():
        eligible, blockers = candidate_gate(row)
        item = dict(row)
        item["eligible_for_regime_swap"] = eligible
        item["gate_blockers"] = blockers
        out.append(item)
    out.sort(key=lambda x: (str(x.get("stage")), str(x.get("candidate_id"))))
    return out


def _market_regimes(market_status: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(market_status, Mapping):
        return []
    rows: list[dict[str, Any]] = []
    for asset in market_status.get("assets", []) or []:
        if not isinstance(asset, Mapping):
            continue
        state = asset.get("state") if isinstance(asset.get("state"), Mapping) else {}
        rows.append(
            {
                "asset": str(asset.get("symbol") or ""),
                "regime": state.get("rate_regime_str"),
                "confidence": state.get("rate_regime"),
                "bar_age_seconds": asset.get("bar_age"),
                "warm": bool(asset.get("warm")),
                "paused": bool(asset.get("paused")),
            }
        )
    return rows


def _parse_time(value: Any) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _agent_rows(events: list[dict[str, Any]], system_audit: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    audit_loops = {}
    if isinstance(system_audit, Mapping):
        for row in system_audit.get("loops", []) or []:
            if isinstance(row, Mapping):
                audit_loops[str(row.get("id") or "").lower()] = row
                audit_loops[str(row.get("title") or "").lower()] = row

    latest_event: dict[str, dict[str, Any]] = {}
    for row in events:
        if row.get("kind") == "agent":
            latest_event[str(row.get("subject") or "").lower()] = row

    out = []
    for agent in AGENTS:
        event = latest_event.get(agent["id"]) or latest_event.get(agent["title"].lower())
        loop = audit_loops.get(agent["id"]) or audit_loops.get(agent["title"].lower())
        status = "UNOBSERVED"
        detail = "No verified local runtime receipt has been ingested for this agent yet."
        recorded_at = ""
        if loop:
            status = str(loop.get("status") or "UNKNOWN")
            detail = str(loop.get("detail") or "")
            recorded_at = str(loop.get("recorded_at") or "")
        if event:
            status = str(event.get("status") or "observed").upper()
            detail = str(event.get("summary") or detail)
            recorded_at = str(event.get("recorded_at") or recorded_at)
        out.append({**agent, "status": status, "detail": detail, "recorded_at": recorded_at})
    return out


def _subsystem_rows(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in events:
        if row.get("kind") == "subsystem":
            latest[str(row.get("subject") or "").lower()] = row
    out = []
    for subsystem in SUBSYSTEMS:
        event = latest.get(subsystem["id"]) or latest.get(subsystem["title"].lower())
        out.append(
            {
                **subsystem,
                "status": str(event.get("status")).upper() if event else "REGISTERED",
                "detail": str(event.get("summary") or "") if event else "",
                "recorded_at": str(event.get("recorded_at") or "") if event else "",
            }
        )
    return out


def _research_incubator(research_status: Mapping[str, Any] | None) -> dict[str, Any]:
    """Summarize deterministic local candidate incubation without granting promotion authority."""
    if not isinstance(research_status, Mapping):
        return {
            "available": False,
            "proposal_count": 0,
            "review_required": 0,
            "approved": 0,
            "rejected_or_invalid": 0,
            "proposals": [],
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    ledger = research_status.get("ledger")
    proposals = ledger.get("proposals", []) if isinstance(ledger, Mapping) else []
    if not isinstance(proposals, list):
        proposals = []

    adaptation = research_status.get("adaptation")
    adaptation_assets = adaptation.get("assets", {}) if isinstance(adaptation, Mapping) else {}
    proposal_context: dict[str, dict[str, Any]] = {}
    if isinstance(adaptation_assets, Mapping):
        for asset, value in adaptation_assets.items():
            if not isinstance(value, Mapping):
                continue
            proposal_id = str(value.get("last_proposal") or "")
            if not proposal_id:
                continue
            proposal_context[proposal_id] = {
                "asset": str(asset),
                "review_mode": str(value.get("review_mode") or ""),
                "regime_context": dict(value.get("regime_context")) if isinstance(value.get("regime_context"), Mapping) else {},
                "scheduler_status": str(value.get("status") or ""),
            }

    state_counts: dict[str, int] = {}
    rows: list[dict[str, Any]] = []
    for proposal in proposals[:100]:
        if not isinstance(proposal, Mapping):
            continue
        state = str(proposal.get("state") or "unknown").lower()
        state_counts[state] = state_counts.get(state, 0) + 1
        candidate = proposal.get("candidate") if isinstance(proposal.get("candidate"), Mapping) else {}
        reviews = proposal.get("reviews") if isinstance(proposal.get("reviews"), list) else []
        inputs = candidate.get("inputs") if isinstance(candidate.get("inputs"), Mapping) else {}
        proposal_id = str(proposal.get("proposal_id") or "")
        context = proposal_context.get(proposal_id, {})
        rows.append(
            {
                "proposal_id": proposal_id,
                "asset": str(candidate.get("asset") or context.get("asset") or ""),
                "state": state,
                "decision_at": candidate.get("decision_at"),
                "expires_at": candidate.get("expires_at"),
                "review_count": len(reviews),
                "input_count": len(inputs),
                "inputs": dict(list(inputs.items())[:24]),
                "review_required": state in {"proposed", "advised"},
                "review_mode": context.get("review_mode"),
                "scheduler_status": context.get("scheduler_status"),
                "regime_context": context.get("regime_context", {}),
                "execution_authorized": False,
                "production_decision_authorized": False,
            }
        )

    return {
        "available": True,
        "proposal_count": len(rows),
        "state_counts": state_counts,
        "review_required": sum(1 for row in rows if row["review_required"]),
        "approved": state_counts.get("approved", 0),
        "rejected_or_invalid": (
            state_counts.get("rejected", 0)
            + state_counts.get("invalidated", 0)
            + state_counts.get("expired", 0)
        ),
        "proposals": rows,
        "execution_authorized": False,
        "production_decision_authorized": False,
        "rule": "Local study-only incubation may discover and preserve candidates, but independent review remains mandatory before any paper activation.",
    }


def brain_snapshot(
    base_dir: str | os.PathLike[str],
    *,
    market_status: Mapping[str, Any] | None = None,
    research_status: Mapping[str, Any] | None = None,
    system_audit: Mapping[str, Any] | None = None,
    integrity: Mapping[str, Any] | None = None,
    remote_sync: Mapping[str, Any] | None = None,
    research_sync: Mapping[str, Any] | None = None,
    limit: int = 1000,
) -> dict[str, Any]:
    """Build the operator brain state from measured local evidence only."""
    events, journal_errors = _read_events(base_dir, max(1, min(5000, int(limit))))
    candidates = _latest_candidates(events)
    regimes = _market_regimes(market_status)

    routes = []
    for regime in regimes:
        name = str(regime.get("regime") or "").strip().lower()
        eligible = []
        for candidate in candidates:
            if not candidate.get("eligible_for_regime_swap"):
                continue
            tags = [str(x).strip().lower() for x in candidate.get("regimes", [])]
            if "*" in tags or (name and name in tags):
                score = candidate.get("metrics", {}).get("validation_score")
                if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score):
                    score = None
                eligible.append({"candidate_id": candidate["candidate_id"], "validation_score": score})
        eligible.sort(key=lambda x: (x["validation_score"] is None, -(x["validation_score"] or 0.0), x["candidate_id"]))
        routes.append(
            {
                "asset": regime.get("asset"),
                "regime": regime.get("regime"),
                "eligible_shadow_candidates": eligible[:8],
                "selected_candidate": eligible[0]["candidate_id"] if eligible else None,
                "selection_mode": "SHADOW_ONLY",
            }
        )

    now = datetime.now(timezone.utc)
    last_hour = 0
    last_day = 0
    for row in events:
        ts = _parse_time(row.get("recorded_at"))
        if ts is None:
            continue
        age = now - ts
        if age <= timedelta(hours=1):
            last_hour += 1
        if age <= timedelta(hours=24):
            last_day += 1

    qualified = sum(1 for c in candidates if c.get("eligible_for_regime_swap"))
    rejected = sum(1 for c in candidates if c.get("stage") == "rejected")
    decided = qualified + rejected
    promotion_rate = (qualified / decided) if decided else None

    audit_events = len((system_audit or {}).get("events", []) or []) if isinstance(system_audit, Mapping) else 0
    integrity_events = len((integrity or {}).get("events", []) or []) if isinstance(integrity, Mapping) else 0
    incubator = _research_incubator(research_status)

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _utc_now(),
        "authority": {
            "research_authorized": True,
            "shadow_routing_authorized": True,
            "production_decision_authorized": False,
            "execution_authorized": False,
            "candidate_router": "SHADOW_ONLY",
        },
        "truth_contract": {
            "success_rate": None,
            "success_rate_status": "UNMEASURED_UNLESS_SUPPLIED_BY_VERIFIED_EVIDENCE",
            "omniscience_claim": False,
            "omnipresence_claim": False,
            "omnipotence_claim": False,
            "rule": "Display measured coverage, latency, calibration, drift and verified performance only; never convert aspiration into a factual metric.",
        },
        "architecture": {
            "agent_count": len(AGENTS),
            "subsystem_count": len(SUBSYSTEMS),
            "agents": _agent_rows(events, system_audit),
            "subsystems": _subsystem_rows(events),
            "latency_tiers": list(LATENCY_TIERS),
            "learning_loop": [
                "observe",
                "normalize/provenance",
                "hypothesize",
                "train/test",
                "falsify",
                "independent verification",
                "qualify/reject",
                "shadow route by regime",
                "monitor drift/outcomes",
                "rollback/retire",
                "learn from durable results",
            ],
        },
        "market": {
            "regimes": regimes,
            "asset_count": len(regimes),
            "market_status_present": isinstance(market_status, Mapping),
        },
        "candidates": candidates,
        "regime_routes": routes,
        "incubator": incubator,
        "remote_sync": dict(remote_sync) if isinstance(remote_sync, Mapping) else {
            "enabled": False,
            "status": "not_configured",
            "execution_authorized": False,
            "production_decision_authorized": False,
        },
        "research_sync": dict(research_sync) if isinstance(research_sync, Mapping) else {
            "enabled": False,
            "status": "not_configured",
            "execution_authorized": False,
            "production_decision_authorized": False,
        },
        "learning": {
            "brain_events_total": len(events),
            "brain_events_last_hour": last_hour,
            "brain_events_last_24h": last_day,
            "candidate_count": len(candidates),
            "qualified_shadow_candidates": qualified,
            "rejected_candidates": rejected,
            "qualified_share_of_decided": promotion_rate,
            "system_intelligence_events_visible": audit_events,
            "integrity_events_visible": integrity_events,
            "research_status_present": isinstance(research_status, Mapping),
            "incubator_proposals": incubator["proposal_count"],
            "incubator_review_required": incubator["review_required"],
            "journal_errors": journal_errors,
        },
        "candidate_gate": {
            "required_stage": "qualified_shadow",
            "required_validation": list(REQUIRED_CANDIDATE_GATES),
            "production_promotion": "NOT_AUTHORIZED_BY_THIS_PLANE",
        },
        "events": events[-200:],
    }
