"""Dashboard + JSON API for the engine (standard library only).

  GET  /                          dashboard (open /?asset=NQ for a single-asset tab)
  GET  /status/public             portfolio + every asset's strategy state
  GET  /api/chart/<SYM>?n=240     bars, overlays (RATE line, TP/SL, VWAP, Kalman), fills
  GET  /api/trades/<SYM>          closed trades (this run: history + live)
  GET  /api/inputs/<SYM>          effective inputs, their sources, and per-input metadata
  GET  /api/input-meta            every input: label, group, kind, default, range, options, tooltip
  GET  /api/presets               presets/*.json (name + _meta)
  GET  /api/assets                asset registry (what can be added)
  GET  /api/commands              the command list the dashboard palette renders
  GET  /api/export/<SYM>.csv      the asset's trade list as CSV
  GET  /api/golive                paper≠live integrity (Grok). Never arms a broker.
  GET  /api/agent                 Field Agent recipes + paste-packs (Grok). Never executes. Never arms a broker.
  GET  /api/system/audit          latest local GitHub/MCP repository + CI audit snapshot
  GET  /api/integrity             export checklist, corpus, repairs, and MCP change receipts
  GET  /api/engine-control        authenticated registered engine/subsystem control snapshot
  GET  /api/brain                 adaptive multi-agent brain, subsystem fabric, regimes, learning and shadow candidates
  GET  /api/possibility           ICARUS Psi latent pressure, counterfactual price, future-space diagnostics
  GET  /api/possibility/evidence  durable Psi external-evidence ledger and causal as-of selection
  GET  /api/chronofold            ICARUS Xi causal spacetime, multiverse, geometry, GNC and uncertainty
  GET  /api/commissioning         append-only Chronofold prediction ledger, calibration, ablation and promotion gate
  POST /admin/pause | /admin/resume        {"asset": "NQ"} or all          (Bearer token)
  POST /admin/flatten                      {"confirm": true, "asset"?: "NQ"}
  POST /admin/inputs                       {"asset": "NQ"|"*", "values": {...}, "chart": {...}, "persist": true}  → re-warm
  POST /admin/inputs/reset                 {"asset": "NQ"}  (deletes inputs.<SYM>.json, re-warm)
  POST /admin/preset                       {"asset": "NQ", "preset": "NQ-10m-original"|null}
  POST /admin/assets/add                   {"symbol": "GC", "tf": "20", "preset"?: ...}
  POST /admin/assets/remove                {"symbol": "GC"}
  POST /admin/system/audit                 {"audit": {...}}  local diagnostic state only; never changes trading
  POST /admin/system/event                 {"event": {...}}  append important MCP repair/audit/evolution event
  POST /admin/system/loop                  {"loop": {...}}   upsert one loop durability receipt/status
  POST /admin/integrity/event              fully-provenanced, idempotent MCP audit receipt; never changes trading
  POST /admin/brain/event                  append evidence-backed learning/agent/subsystem/candidate event; shadow only
  POST /admin/possibility/evidence          provenance-labelled gamma/basis/CTA/liquidation/rebalance research inputs
  POST /admin/parallax/decision/current      atomically capture current Psi vote and PARALLAX decision
  POST /admin/rewarm                       {"asset": "NQ"}
  POST /admin/engine-control               typed registered operator command with audit receipt
"""
from __future__ import annotations

import hmac
import json
import os
import re
import sys
import time
import threading
from contextlib import ExitStack
from dataclasses import replace
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict
from urllib.parse import parse_qs, urlparse

from . import brand
from .assets import REGISTRY, apply_chart_config, chart_capabilities, parse_spec, pin_config, resolve, validate_chart_config
from .backtest import JOBS, start_job
from .parity import compare_lists, engine_trades_from_rows, read_tv_trades_text
from .golive import report as golive_report
from .agent import report as agent_report
from .briefing import report as briefing_report
from .runtime import Portfolio, _clean, _read_json, apply_spec_meta, preset_path
from .strategy.meta import load_meta
from .advisory import MAX_BODY_BYTES, strict_json
from .research_service import ResearchWorkspace
from .system_audit import (
    LoopIntelligenceSync,
    append_system_event,
    load_repository_audit,
    save_repository_audit,
    upsert_loop_status,
)
from .integrity import integrity_snapshot, record_integrity_event
from .brain import REQUIRED_CANDIDATE_GATES, SUBSYSTEMS, brain_snapshot, record_brain_event
from .brain_sync import BrainRemoteSync
from .research_brain_sync import BrainResearchSync
from .evolution_sync import EvolutionRemoteSync
from .evidence_lab_sync import EvidenceLabRemoteSync
from .code_provenance import local_code_provenance
from .parallax import ParallaxStore
from .dreamstate import DreamstateLab
from .possibility import PossibilityEngine
from .performance_proof import PerformanceProofStore
from .latency_telemetry import LatencyTelemetry
from .source_reliability import SourceReliabilityStore
from .qualification_receipts import (
    QualificationReceiptStore,
    build_shadow_promotion_event,
    build_shadow_revocation_event,
)
from .autopilot import TacticalAutopilot
from .engine_control import ControlAction, EngineControlPlane
from .mcp_control import MCPControlPlane
from .chronofold import ChronofoldEngine
from .commissioning import CommissioningEngine
from .pantheon import PantheonKernel, subsystem_context
from .sibyl import SibylEngine
from .apex import ApexKernel
from .ascendancy.capabilities import capability_snapshot
from .ascendancy.archive import GenomeArchive
from .ascendancy.frontier import build_frontier
from .ascendancy.genome import compile_genome, normalize_genome
from .ascendancy.foundry import CandidateFoundry
from .ascendancy.unknowns import UnknownUnknownLab
from .ascendancy.mechanisms import MechanismLab
from .ascendancy.invention import InventionLab, to_foundry_candidate
from .ascendancy.contribution import ContributionLab
from .ascendancy.evaluator import EvaluatorCascade


def _no_json_constants(name: str):
    raise ValueError(f"{name} is not allowed")


def _json_default(obj: Any) -> Any:
    item = getattr(obj, "item", None)
    if callable(item):
        try:
            obj = item()
        except Exception:
            return str(obj)
    if isinstance(obj, float):
        return None if obj != obj or obj in (float("inf"), float("-inf")) else obj
    return str(obj)


def dumps_safe(obj: Any) -> bytes:
    """Never raise. Empty reply is what made the dashboard say ENGINE UNREACHABLE."""
    try:
        return json.dumps(_clean(obj), allow_nan=False, default=_json_default).encode("utf-8")
    except Exception as ex:
        sys.stderr.write(f"icarus json dump failed: {type(ex).__name__}: {ex}\n")
        return json.dumps({"ok": False, "detail": f"json: {type(ex).__name__}: {ex}"}).encode("utf-8")


def _current_parallax_payload(possibility: Any, body: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any]]:
    """Capture a Psi vote before stamping a new PARALLAX decision.

    Present-time only. Historical decisions must carry their already-captured
    subsystem votes and use /admin/parallax/decision.
    """
    payload = dict(body)
    allowed = {
        "schema_version", "decision_id", "asset", "action", "regime",
        "source_commit", "context", "subsystem_votes", "branches", "observed_at",
    }
    unknown = set(payload) - allowed
    if unknown:
        raise ValueError("unsupported current PARALLAX fields: " + ", ".join(sorted(unknown)))
    if payload.get("observed_at") not in (None, ""):
        raise ValueError("current decision capture owns observed_at; use /admin/parallax/decision for historical records")
    votes = payload.get("subsystem_votes", {})
    if not isinstance(votes, dict):
        raise ValueError("subsystem_votes must be an object")
    if "psi" in votes:
        raise ValueError("current decision capture owns the psi vote")
    asset = str(payload.get("asset") or "").strip().upper()
    if not asset:
        raise ValueError("asset is required")

    psi_vote = possibility.parallax_vote(asset)
    if not isinstance(psi_vote, dict):
        raise ValueError("Psi vote must be an object")
    captured = datetime.now(timezone.utc)
    generated_at = str(psi_vote.get("generated_at") or "").strip()
    if generated_at:
        try:
            generated = datetime.fromisoformat(generated_at.replace("Z", "+00:00")).astimezone(timezone.utc)
        except ValueError as ex:
            raise ValueError("Psi vote generated_at is invalid") from ex
        if generated > captured:
            raise ValueError("Psi vote generated_at cannot follow PARALLAX decision capture")

    merged_votes = dict(votes)
    merged_votes["psi"] = psi_vote
    payload["subsystem_votes"] = merged_votes
    payload["asset"] = asset
    payload["observed_at"] = captured.isoformat().replace("+00:00", "Z")
    return payload, psi_vote


def _reason(body: Dict[str, Any], default: str = "manual") -> str:
    """Free text that ends up in the journal: printable, short."""
    return re.sub(r"[^\w .:()/-]", "", str(body.get("reason", default)))[:40] or default

COMMANDS = [
    {"id": "backtest", "label": "Backtest (Strategy Tester)", "desc": "Run the strategy on the cached bars with any preset / inputs / fill mode and read TradingView's Strategy Tester numbers.", "scope": "asset", "danger": False},
    {"id": "pause", "label": "Pause entries", "desc": "No new entries on the selected asset (or all). Exits keep running.", "scope": "asset|all", "danger": False},
    {"id": "resume", "label": "Resume entries", "desc": "Lift a pause.", "scope": "asset|all", "danger": False},
    {"id": "flatten", "label": "Flatten", "desc": "Close every open paper position now, at the last price.", "scope": "asset|all", "danger": True},
    {"id": "rewarm", "label": "Re-warm", "desc": "Rebuild the asset's engine from the cached history (after editing inputs).", "scope": "asset", "danger": False},
    {"id": "inputs", "label": "Edit inputs", "desc": "Open the Inputs tab for the asset.", "scope": "asset", "danger": False},
    {"id": "preset", "label": "Apply preset", "desc": "Load one of the presets/ configurations onto the asset and re-warm.", "scope": "asset", "danger": False},
    {"id": "reset-inputs", "label": "Reset asset overrides", "desc": "Delete inputs.<SYM>.json so the asset falls back to the preset.", "scope": "asset", "danger": True},
    {"id": "add-asset", "label": "Add asset", "desc": "Start a new asset (NQ ES YM GC SI PL PA BTCF MBT BTC ETH SOL …).", "scope": "all", "danger": False},
    {"id": "remove-asset", "label": "Remove asset", "desc": "Stop and drop an asset from the engine.", "scope": "asset", "danger": True},
    {"id": "export", "label": "Export trades CSV", "desc": "Download the asset's trade list (TradingView-like columns).", "scope": "asset", "danger": False},
    {"id": "open-tab", "label": "Open in its own tab", "desc": "Full-screen view of one asset in a new browser tab.", "scope": "asset", "danger": False},
    {"id": "golive", "label": "Go-live integrity", "desc": "Paper ≠ live. Tape identity, warmup P&L, RTH, QQQ≠NQ. Never arms a broker.", "scope": "all", "danger": False},
    {"id": "agent", "label": "Field Agent", "desc": "Copy plant recipes and Claude/ChatGPT paste-packs. Does not execute. Never arms a broker.", "scope": "all", "danger": False},
]


def serve(port: Portfolio, http_port: int = 8791, token: str = "icarus", start: bool = True):
    html_path = Path(__file__).parent / "dashboard.html"
    meta = load_meta()
    research = ResearchWorkspace(port)
    loop_intelligence_sync = LoopIntelligenceSync(port.base_dir)
    brain_remote_sync = BrainRemoteSync(port.base_dir)
    brain_research_sync = BrainResearchSync(port.base_dir)
    evolution_remote_sync = EvolutionRemoteSync(port.base_dir)
    evidence_lab_sync = EvidenceLabRemoteSync(port.base_dir)
    possibility = PossibilityEngine(port)
    performance_proof = PerformanceProofStore(port.base_dir)
    latency_telemetry = LatencyTelemetry()
    source_reliability = SourceReliabilityStore(port.base_dir)
    qualification_receipts = QualificationReceiptStore(port.base_dir, REQUIRED_CANDIDATE_GATES)
    # Bind one collector to the existing live runners; Portfolio.make_runner
    # propagates the same sink to assets added later.
    port.latency_telemetry = latency_telemetry
    for runner in port.runner_list():
        runner.latency_telemetry = latency_telemetry
    autopilot = TacticalAutopilot(port)
    parallax = ParallaxStore(port.base_dir)
    dreamstate = DreamstateLab(port.base_dir, parallax=parallax)
    ascendancy_archive = GenomeArchive(port.base_dir)
    ascendancy_foundry = CandidateFoundry(port.base_dir)
    ascendancy_unknowns = UnknownUnknownLab(port.base_dir)
    ascendancy_mechanisms = MechanismLab(port.base_dir)
    ascendancy_inventions = InventionLab(port.base_dir)
    ascendancy_contribution = ContributionLab(port.base_dir)
    ascendancy_evaluator = EvaluatorCascade(port.base_dir)
    mcp_control = MCPControlPlane(port.base_dir)
    chronofold = ChronofoldEngine(port, possibility=possibility)
    commissioning = CommissioningEngine(port.base_dir, port, chronofold)
    pantheon = PantheonKernel(port.base_dir)
    sibyl = SibylEngine(port.base_dir)
    learning = research.learning
    apex = ApexKernel(
        port.base_dir,
        possibility=possibility.status,
        chronofold=chronofold.status,
        pantheon=pantheon.snapshot,
        parallax=parallax.snapshot,
        dreamstate=dreamstate.snapshot,
        sibyl=sibyl.snapshot,
        learning=learning.snapshot,
    )
    learning.bind_native(
        sibyl=sibyl,
        commissioning=commissioning,
        parallax=parallax,
        dreamstate=dreamstate,
        pantheon=pantheon,
        apex=apex,
        possibility=possibility,
        chronofold=chronofold,
        performance_proof=performance_proof,
        source_reliability=source_reliability,
    )

    def _qualification_sync(candidate_id: str, source_repo: str, source_commit: str) -> dict[str, Any]:
        status = qualification_receipts.candidate_status(candidate_id, source_repo, source_commit)
        snapshot = brain_snapshot(port.base_dir)
        candidate = next(
            (
                row for row in snapshot.get("candidates", [])
                if row.get("candidate_id") == candidate_id
                and row.get("source_repo") == source_repo
                and row.get("source_commit") == source_commit
            ),
            None,
        )
        transition = None
        if candidate is not None:
            if status.get("qualification_ready") is True and candidate.get("stage") in {"validated", "qualified_shadow"}:
                transition = record_brain_event(port.base_dir, build_shadow_promotion_event(candidate, status))
            elif status.get("qualification_ready") is not True and candidate.get("stage") == "qualified_shadow":
                transition = record_brain_event(port.base_dir, build_shadow_revocation_event(candidate, status))
        return {
            "qualification": status,
            "candidate_found": candidate is not None,
            "transition": transition,
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    def _ascendancy_snapshot() -> Dict[str, Any]:
        archive = ascendancy_archive.snapshot()
        return {
            "archive": archive,
            "frontier": build_frontier(archive),
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    def _ascendancy_trading_control_fingerprint():
        # Deliberately excludes prices/P&L/warmup counters because those may
        # evolve concurrently. This boundary watches state ASCENDANCY must
        # never mutate: global pause intent, runner membership/order, and
        # per-runner entry-pause controls.
        return (
            bool(port.paused),
            tuple(port.order),
            tuple(
                (
                    str(getattr(r, "symbol", "")),
                    bool(getattr(r, "paused", False)),
                )
                for r in port.runner_list()
            ),
        )

    def _ascendancy_research_mutation(call):
        before = _ascendancy_trading_control_fingerprint()
        result = call()
        after = _ascendancy_trading_control_fingerprint()
        if after != before:
            raise RuntimeError(
                "ASCENDANCY research boundary changed trading-control state; refusing success"
            )
        out = dict(result) if isinstance(result, dict) else {"result": result}
        out["trading_state_unchanged"] = True
        out["execution_authorized"] = False
        out["production_decision_authorized"] = False
        return out

    def _ascendancy_register_genome(body: Dict[str, Any]) -> Dict[str, Any]:
        # Compile first. Invalid/unknown topology must not leave a persisted
        # genome behind.
        normalized = normalize_genome(body)
        available = {
            str(row.get("id") or "").strip()
            for row in SUBSYSTEMS
            if isinstance(row, dict) and str(row.get("id") or "").strip()
        }
        # The Adaptive Brain registry is intentionally not the complete
        # runtime-service registry. Keep server-native research engines explicit
        # so a genome can compose them without falsely treating them as foreign.
        available.update({
            "chronofold",
            "commissioning",
            "research",
            "autopilot",
            "performance-proof",
            "source-reliability",
            "latency-telemetry",
            "mcp-control",
        })
        compiled = compile_genome(
            normalized,
            available_native_subsystems=available,
        )
        registered = ascendancy_archive.register(normalized)
        compile_receipt = ascendancy_archive.record_compile(compiled)
        return {
            "genome": registered["genome"],
            "compile_receipt": compile_receipt["compile_receipt"],
            "idempotent": bool(registered["idempotent"] and compile_receipt["idempotent"]),
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    def _ascendancy_record_mechanism(body: Dict[str, Any]) -> Dict[str, Any]:
        candidate_id = str(body.get("candidate_id") or "").strip()
        foundry = ascendancy_foundry.snapshot()
        candidate = next(
            (
                row for row in foundry.get("candidates", [])
                if isinstance(row, dict) and str(row.get("candidate_id") or "") == candidate_id
            ),
            None,
        )
        if candidate is None:
            raise ValueError("unknown candidate_id in ASCENDANCY Candidate Foundry")
        expected_contract = str(
            (candidate.get("evaluation_contract") or {}).get("contract_hash") or ""
        )
        if str(body.get("evaluation_contract_hash") or "") != expected_contract:
            raise ValueError("mechanism experiment evaluation contract does not match candidate")
        if str(body.get("source_repo") or "") != str(candidate.get("source_repo") or ""):
            raise ValueError("mechanism experiment source_repo does not match candidate")
        if str(body.get("source_commit") or "") != str(candidate.get("source_commit") or ""):
            raise ValueError("mechanism experiment source_commit does not match candidate")
        return ascendancy_mechanisms.record(body)

    def _ascendancy_record_contribution(body: Dict[str, Any]) -> Dict[str, Any]:
        contributor_kind = str(body.get("contributor_kind") or "").strip().lower()
        contributor_id = str(body.get("contributor_id") or "").strip()
        if contributor_kind == "candidate":
            foundry = ascendancy_foundry.snapshot()
            candidate = next(
                (
                    row for row in foundry.get("candidates", [])
                    if isinstance(row, dict)
                    and str(row.get("candidate_id") or "") == contributor_id
                ),
                None,
            )
            if candidate is None:
                raise ValueError("unknown candidate_id in ASCENDANCY Candidate Foundry")
            expected_contract = str(
                (candidate.get("evaluation_contract") or {}).get("contract_hash") or ""
            )
            if str(body.get("evaluation_contract_hash") or "") != expected_contract:
                raise ValueError(
                    "contribution observation evaluation contract does not match candidate"
                )
            if str(body.get("source_repo") or "") != str(candidate.get("source_repo") or ""):
                raise ValueError("contribution observation source_repo does not match candidate")
            if str(body.get("source_commit") or "") != str(candidate.get("source_commit") or ""):
                raise ValueError("contribution observation source_commit does not match candidate")
        return ascendancy_contribution.record(body)

    def _ascendancy_register_evaluator_candidate(body: Dict[str, Any]) -> Dict[str, Any]:
        candidate_id = str(body.get("candidate_id") or "").strip()
        foundry = ascendancy_foundry.snapshot()
        candidate = next(
            (
                row for row in foundry.get("candidates", [])
                if isinstance(row, dict)
                and str(row.get("candidate_id") or "") == candidate_id
            ),
            None,
        )
        if candidate is None:
            raise ValueError("unknown candidate_id in ASCENDANCY Candidate Foundry")
        return ascendancy_evaluator.register_candidate(candidate)

    def _ascendancy_invention_to_candidate(body: Dict[str, Any]) -> Dict[str, Any]:
        blueprint_id = str(body.get("blueprint_id") or "").strip()
        if not blueprint_id:
            raise ValueError("blueprint_id is required")
        invention_state = ascendancy_inventions.snapshot()
        blueprint = next(
            (
                row for row in invention_state.get("blueprints", [])
                if isinstance(row, dict) and str(row.get("blueprint_id") or "") == blueprint_id
            ),
            None,
        )
        if blueprint is None:
            raise ValueError("unknown invention blueprint_id")
        payload = to_foundry_candidate(blueprint)
        return ascendancy_foundry.register(payload)

    def _control_runner(target: str):
        try:
            key = resolve(target or "").symbol
        except ValueError as ex:
            raise ValueError(f"unknown asset {target}") from ex
        runner = port.runners.get(key)
        if runner is None:
            raise ValueError(f"unknown running asset {target}")
        return runner

    def _run_all_assets(operation: str, fn):
        results = {}
        errors = {}
        for runner in list(port.runner_list()):
            try:
                results[runner.symbol] = fn(runner)
            except Exception as ex:
                errors[runner.symbol] = f"{type(ex).__name__}: {ex}"[:800]
        if errors:
            raise RuntimeError(
                f"{operation} partial failure; completed={sorted(results)} errors={errors}"
            )
        return results

    def _pause_all(payload):
        # Global pause is desired/default state. Set it before touching runners so
        # a concurrently added asset cannot start accepting entries.
        port.paused = True
        port.journal.log("WARN", f"PAUSE ALL requested: {payload['reason']}")
        results = _run_all_assets("pause_all", lambda runner: runner.set_paused(True))
        return {"paused": sorted(results), "global_pause_intent": True}

    def _resume_all(payload):
        # Resume is likewise a global intent. Individual runners may still fail
        # closed (for example activation quarantine); those failures are reported.
        port.paused = False
        port.journal.log("INFO", f"RESUME ALL requested: {payload['reason']}")
        results = _run_all_assets("resume_all", lambda runner: runner.set_paused(False))
        return {"resumed": sorted(results), "global_pause_intent": False}

    def _flatten_all(payload):
        closed = _run_all_assets(
            "flatten_all",
            lambda runner: runner.flatten(payload["reason"]),
        )
        return {"closed": closed, "total": sum(closed.values())}

    def _asset_pause(payload):
        runner = _control_runner(payload["target"])
        runner.set_paused(True)
        return {"asset": runner.symbol, "paused": True}

    def _asset_resume(payload):
        runner = _control_runner(payload["target"])
        runner.set_paused(False)
        return {"asset": runner.symbol, "paused": False}

    def _asset_flatten(payload):
        runner = _control_runner(payload["target"])
        return {"asset": runner.symbol, "closed": runner.flatten(payload["reason"])}

    def _asset_rewarm(payload):
        runner = _control_runner(payload["target"])
        port.rewarm_asset(runner.symbol)
        return {"asset": runner.symbol, "rewarmed": True}

    def _asset_remove(payload):
        runner = _control_runner(payload["target"])
        ok = port.remove_asset(runner.symbol)
        if not ok:
            raise ValueError(f"asset {runner.symbol} could not be removed")
        return {"asset": runner.symbol, "removed": True}

    def _asset_apply_config(payload):
        runner = _control_runner(payload["target"])
        args = payload["args"]
        allowed = {"values", "chart", "persist", "preset"}
        extra = set(args) - allowed
        if extra:
            raise ValueError(f"unknown asset configuration fields: {sorted(extra)}")
        values = args.get("values")
        if values is not None and not isinstance(values, dict):
            raise ValueError("values must be an object")
        chart = validate_chart_config(args.get("chart"))
        persist = args.get("persist", True)
        if type(persist) is not bool:
            raise ValueError("persist must be boolean")
        kwargs = {}
        if "preset" in args:
            raw_preset = args.get("preset")
            if raw_preset is not None and not isinstance(raw_preset, str):
                raise ValueError("preset must be a string or null")
            preset = (raw_preset or "").strip() or None
            if preset and not os.path.exists(preset_path(port.base_dir, preset)):
                raise ValueError(f"preset {preset} not found")
            kwargs["preset"] = preset
        rebuilt = port.rewarm_asset(
            runner.symbol,
            values,
            persist,
            chart=chart,
            **kwargs,
        )
        return {
            "asset": rebuilt.symbol,
            "rewarmed": True,
            "persisted": persist,
            "chart": chart or None,
            "preset": port.preset_for(rebuilt),
        }

    def _asset_reset_config(payload):
        runner = _control_runner(payload["target"])
        rebuilt = port.rewarm_asset(runner.symbol, reset=True)
        return {
            "asset": rebuilt.symbol,
            "rewarmed": True,
            "asset_overrides_reset": True,
        }

    def _asset_add(payload):
        target = payload["target"]
        args = payload["args"]
        allowed = {"tf", "preset", "chart_type", "fill_on", "security_source"}
        extra = set(args) - allowed
        if extra:
            raise ValueError(f"unknown asset-add fields: {sorted(extra)}")
        running = port.runner_list()
        default_tf = str(args.get("tf") or (running[0].spec.chart_tf if running else "20"))
        spec = parse_spec(target, default_tf)
        if args.get("tf") not in (None, "") and "@" not in target:
            spec = pin_config(spec, "timeframe")
        chart = {
            k: args[k]
            for k in ("chart_type", "fill_on", "security_source")
            if args.get(k) not in (None, "")
        }
        if chart:
            spec = apply_chart_config(spec, validate_chart_config(chart), pin=True)
        if args.get("preset"):
            name = str(args["preset"])
            if not os.path.exists(preset_path(port.base_dir, name)):
                raise ValueError(f"preset {name} not found")
            spec.preset = name
        runner = port.add_asset(spec)
        return {"asset": runner.symbol, "added": True, "timeframe": spec.chart_tf}

    def _syncers():
        return {
            "loop_intelligence": loop_intelligence_sync,
            "brain_remote": brain_remote_sync,
            "brain_research": brain_research_sync,
            "evolution": evolution_remote_sync,
            "evidence_lab": evidence_lab_sync,
        }

    def _sync_all(_payload):
        results = {}
        errors = {}
        for name, syncer in _syncers().items():
            try:
                results[name] = syncer.sync_once()
            except Exception as ex:
                errors[name] = f"{type(ex).__name__}: {ex}"[:800]
        if errors:
            raise RuntimeError(
                f"sync_all partial failure; completed={sorted(results)} errors={errors}"
            )
        return results

    def _run_sync_lifecycle(operation: str, method: str):
        results = {}
        errors = {}
        for name, syncer in _syncers().items():
            try:
                getattr(syncer, method)()
                results[name] = operation
            except Exception as ex:
                errors[name] = f"{type(ex).__name__}: {ex}"[:800]
        if errors:
            raise RuntimeError(
                f"{operation} sync partial failure; completed={sorted(results)} errors={errors}"
            )
        return results

    def _start_all_syncs(_payload):
        return _run_sync_lifecycle("started", "start")

    def _stop_all_syncs(_payload):
        return _run_sync_lifecycle("stopped", "close")

    def _control_args(payload, *, allowed=None, required=()):
        args = payload.get("args") or {}
        if not isinstance(args, dict):
            raise ValueError("args must be an object")
        if allowed is not None:
            extra = set(args) - set(allowed)
            if extra:
                raise ValueError(f"unknown action args: {sorted(extra)}")
        missing = [key for key in required if key not in args]
        if missing:
            raise ValueError(f"missing required action args: {missing}")
        return dict(args)

    def _backtests_snapshot():
        rows = []
        for job_id, job in list(JOBS.items())[-200:]:
            params = job.get("params") or {}
            rows.append({
                "id": job_id,
                "status": job.get("status"),
                "progress": job.get("progress"),
                "started": job.get("started"),
                "finished": job.get("finished"),
                "error": job.get("error"),
                "asset": params.get("asset"),
            })
        return {"count": len(rows), "jobs": rows}

    def _backtest_start_control(payload):
        from .backtest import validate_backtest_params
        runner = _control_runner(payload["target"])
        if not runner.warm:
            raise ValueError(f"{runner.symbol} is still warming up")
        allowed = {
            "preset", "fill_on", "chart_type", "timeframe", "security_source",
            "session", "slippage_ticks", "commission", "capital", "leverage",
            "window_start", "window_end", "inputs",
        }
        args = _control_args(payload, allowed=allowed)
        params = validate_backtest_params(args)
        params["asset"] = runner.symbol
        if "preset" in params and not os.path.exists(preset_path(port.base_dir, params["preset"])):
            raise ValueError(f"preset {params['preset']} not found")
        job_id = start_job(port, params)
        return {"job": job_id, "asset": runner.symbol, "started": True}

    def _backtest_compare_control(payload):
        job_id = payload["target"]
        job = JOBS.get(job_id)
        if not job or job.get("status") != "done":
            raise ValueError("unknown or unfinished backtest job")
        args = _control_args(payload, allowed={"csv", "tol"}, required=("csv",))
        text = str(args["csv"])
        if not text.strip():
            raise ValueError("csv text required")
        tol = args.get("tol", 1)
        if isinstance(tol, bool) or not isinstance(tol, (int, float, str)):
            raise ValueError("tol must be a positive integer")
        try:
            tol = int(tol)
        except (ValueError, OverflowError):
            raise ValueError("tol must be a positive integer") from None
        if tol < 1:
            raise ValueError("tol must be a positive integer")
        tv = read_tv_trades_text(text)
        eng = engine_trades_from_rows(job["result"]["trades"])
        report = compare_lists(
            eng,
            tv,
            int(job["result"]["config"]["tf"]) * 60,
            tol,
        )
        return {"job": job_id, "report": report}

    def _market_mbo_snapshot_control(payload):
        runner = _control_runner(payload["target"])
        args = _control_args(payload, allowed={"timeout"})
        if not hasattr(runner.feed, "mbo_snapshot"):
            raise ValueError(f"{type(runner.feed).__name__} does not expose MBO snapshots")
        timeout = max(0.1, min(30.0, float(args.get("timeout", 5.0))))
        rows = runner.feed.mbo_snapshot(runner.spec.ticker, timeout=timeout)
        return {
            "asset": runner.symbol,
            "provider": type(runner.feed).__name__.lower(),
            "schema": "mbo",
            "snapshot": rows,
        }

    def _research_start_control(payload):
        args = _control_args(payload, allowed={"grid", "windows", "policy"}, required=("grid", "windows"))
        return research.start({"asset": payload["target"], **args})

    def _research_propose_control(payload):
        args = _control_args(payload, allowed={"evidence_ids", "rationale"}, required=("evidence_ids", "rationale"))
        return research.propose_study({"job": payload["target"], **args})

    def _research_analysis_control(payload):
        args = _control_args(payload, allowed={"evidence_ids", "rationale", "apply"}, required=("evidence_ids", "rationale"))
        return research.analysis.start({"job": payload["target"], **args})

    def _research_activate_control(payload):
        args = _control_args(payload, allowed={"operation_id"}, required=("operation_id",))
        return research.activate({"proposal_id": payload["target"], "operation_id": args["operation_id"]})

    def _research_rollback_control(payload):
        args = _control_args(payload, allowed={"operation_id"}, required=("operation_id",))
        return research.rollback({"asset": payload["target"], "operation_id": args["operation_id"]})

    def _research_collect_control(payload):
        args = _control_args(payload, allowed={"options"})
        return research.market_sources.collect(payload["target"], args.get("options"))

    def _parallax_decision_control(payload):
        args = _control_args(payload)
        if not args.get("source_commit"):
            provenance = local_code_provenance()
            if not provenance.get("candidate_revision_eligible") or not provenance.get("commit"):
                raise ValueError("exact clean ICARUS code provenance is required when source_commit is omitted")
            args["source_commit"] = provenance["commit"]
        return parallax.record_decision(args)

    def _parallax_outcome_control(payload):
        args = _control_args(payload)
        result = parallax.record_outcome(args)
        try:
            result["dreamstate_refresh"] = dreamstate.refresh().get("refresh", {})
        except Exception as ex:
            port.journal.log("WARN", f"DREAMSTATE rescreen after PARALLAX outcome: {type(ex).__name__}: {ex}")
            result["dreamstate_refresh"] = {
                "status": "degraded",
                "error": f"{type(ex).__name__}: {ex}",
                "outcome_committed": True,
            }
        return result

    def _dreamstate_evaluate_control(payload):
        args = _control_args(payload, allowed={"validation", "evidence"}, required=("validation",))
        return dreamstate.evaluate(payload["target"], args)

    def _dreamstate_retire_control(payload):
        args = _control_args(payload, allowed={"reason"}, required=("reason",))
        return dreamstate.retire(payload["target"], args["reason"])

    def _possibility_evidence_control(payload):
        args = _control_args(
            payload,
            allowed={"values", "source", "observed_at", "ttl_seconds"},
            required=("values", "source"),
        )
        if not isinstance(args["values"], dict):
            raise ValueError("values must be an object")
        return possibility.ingest_external(
            payload["target"],
            args["values"],
            source=args["source"],
            observed_at=args.get("observed_at"),
            ttl_seconds=args.get("ttl_seconds", 300.0),
        )

    def _system_audit_control(payload):
        args = _control_args(payload)
        current = load_repository_audit(port.base_dir)
        merged = dict(args)
        # Root Control may update the repository/CI snapshot, but it must never
        # erase the durable command/event/loop receipts that prove prior actions.
        for key in ("events", "loops"):
            incoming = merged.get(key, [])
            if incoming is None:
                incoming = []
            if not isinstance(incoming, list):
                raise ValueError(f"{key} must be an array")
            existing = current.get(key, [])
            combined = []
            seen = set()
            for row in [*incoming, *existing]:
                if not isinstance(row, dict):
                    raise ValueError(f"{key} entries must be objects")
                ident = str(row.get("id") or "")
                fingerprint = ident or json.dumps(row, sort_keys=True, separators=(",", ":"), allow_nan=False)
                if fingerprint in seen:
                    continue
                seen.add(fingerprint)
                combined.append(row)
            merged[key] = combined[:200 if key == "events" else 32]
        if "loop_sync" not in merged and isinstance(current.get("loop_sync"), dict):
            merged["loop_sync"] = current["loop_sync"]
        return save_repository_audit(port.base_dir, merged)

    def _system_event_control(payload):
        args = _control_args(payload)
        return append_system_event(port.base_dir, args)

    def _system_loop_control(payload):
        args = _control_args(payload)
        return upsert_loop_status(port.base_dir, args)

    def _integrity_event_control(payload):
        args = _control_args(payload)
        provenance_keys = ("source_repo", "source_branch", "source_commit")
        supplied = [key in args for key in provenance_keys]
        if any(supplied) and not all(supplied):
            raise ValueError("source_repo, source_branch and source_commit must be supplied together")
        if not any(supplied):
            provenance = local_code_provenance()
            if not provenance.get("candidate_revision_eligible") or not provenance.get("commit"):
                raise ValueError(
                    "exact clean ICARUS code provenance is required when integrity provenance is omitted"
                )
            args["source_repo"] = provenance["repository"]
            args["source_branch"] = "local-clean-checkout"
            args["source_commit"] = provenance["commit"]
        return record_integrity_event(port.base_dir, args)

    def _brain_event_control(payload):
        args = _control_args(payload)
        return record_brain_event(port.base_dir, args)

    def _commissioning_capture_control(payload):
        return commissioning.capture(payload["target"], force=True)

    def _commissioning_settle_asset_control(payload):
        return commissioning.settle_ready(payload["target"])

    control = EngineControlPlane(
        port.base_dir,
        snapshotters={
            "portfolio": port.status,
            "research": research.operator_status,
            "repository_audit": lambda: load_repository_audit(port.base_dir),
            "integrity": lambda: integrity_snapshot(port.base_dir),
            "mcp_repository": lambda: mcp_control.status(200),
            "brain_remote_sync": brain_remote_sync.status,
            "brain_research_sync": brain_research_sync.status,
            "evolution_sync": evolution_remote_sync.status,
            "autopilot": autopilot.status,
            "parallax": parallax.status,
            "dreamstate": dreamstate.status,
            "possibility": possibility.status,
            "pantheon": pantheon.snapshot,
            "sibyl": sibyl.snapshot,
            "chronofold": chronofold.status,
            "commissioning": commissioning.status,
            "backtests": _backtests_snapshot,
            "code_provenance": local_code_provenance,
            "go_live": lambda: golive_report(port),
        },
        actions={
            action.action_id: action
            for action in (
                ControlAction("engine.pause_all", "Pause all entries", "Engine", "Pause new entries on every running asset; exits remain active.", _pause_all),
                ControlAction("engine.resume_all", "Resume all entries", "Engine", "Resume new entries on every running asset.", _resume_all),
                ControlAction("engine.flatten_all", "Flatten all paper positions", "Engine", "Immediately close every open local paper position.", _flatten_all, danger=True, confirmation="FLATTEN ALL PAPER POSITIONS"),

                ControlAction("asset.add", "Add asset", "Assets", "Add and warm a registered asset.", _asset_add, target="asset",
                              args_example={"tf": "20", "chart_type": "Candles"}),
                ControlAction("asset.pause", "Pause asset", "Assets", "Pause new entries for one running asset.", _asset_pause, target="asset"),
                ControlAction("asset.resume", "Resume asset", "Assets", "Resume new entries for one running asset.", _asset_resume, target="asset"),
                ControlAction("asset.rewarm", "Re-warm asset", "Assets", "Rebuild one asset from cached history.", _asset_rewarm, target="asset"),
                ControlAction("asset.apply_config", "Apply asset configuration", "Assets", "Apply input/chart/preset configuration through ICARUS's atomic re-warm path.", _asset_apply_config, target="asset",
                              args_example={"values": {}, "chart": {"chart_type": "Candles"}, "persist": True}),
                ControlAction("asset.reset_config", "Reset asset overrides", "Assets", "Remove per-asset configuration overrides and atomically re-warm the asset.", _asset_reset_config, danger=True, confirmation="RESET ASSET CONFIG", target="asset"),
                ControlAction("asset.flatten", "Flatten asset", "Assets", "Close the selected asset's open paper position.", _asset_flatten, danger=True, confirmation="FLATTEN PAPER POSITION", target="asset"),
                ControlAction("asset.remove", "Remove asset", "Assets", "Stop and remove one running asset.", _asset_remove, danger=True, confirmation="REMOVE ASSET", target="asset"),

                ControlAction("market.mbo_snapshot", "Capture MBO snapshot", "Market Data", "Request one bounded market-by-order snapshot from the selected running asset's provider.", _market_mbo_snapshot_control, target="asset",
                              args_example={"timeout": 5.0}),
                ControlAction("backtest.start", "Start backtest", "Backtest", "Start a Strategy Tester-compatible backtest against the selected asset's cached tape.", _backtest_start_control, target="asset",
                              args_example={"timeframe": "20", "session": "rth"}),
                ControlAction("backtest.compare", "Compare backtest to TradingView CSV", "Backtest", "Compare a completed ICARUS backtest job against pasted TradingView List-of-Trades CSV.", _backtest_compare_control, target="job",
                              args_example={"csv": "Trade #,Type,Date/Time,Signal,Price,Contracts\n", "tol": 1}),

                ControlAction("sync.loop_intelligence", "Sync loop intelligence", "Intelligence", "Refresh verified automation-loop receipts now.", lambda _: loop_intelligence_sync.sync_once()),
                ControlAction("sync.brain_remote", "Sync Adaptive Brain remote evidence", "Intelligence", "Pull the latest verified Adaptive Brain repository evidence.", lambda _: brain_remote_sync.sync_once()),
                ControlAction("sync.brain_research", "Sync research into Adaptive Brain", "Intelligence", "Refresh research-to-brain evidence now.", lambda _: brain_research_sync.sync_once()),
                ControlAction("sync.evolution", "Sync MCP evolution evidence", "Intelligence", "Refresh repository-native MCP repair/audit/evolution evidence.", lambda _: evolution_remote_sync.sync_once()),
                ControlAction("sync.evidence_lab", "Sync CSV Evidence Lab", "Intelligence", "Refresh verified Advanced CSV durability/evidence receipts from the active CSV Evidence Lab repository.", lambda _: evidence_lab_sync.sync_once()),
                ControlAction("sync.all", "Sync all intelligence planes", "Intelligence", "Run all registered intelligence synchronizers once.", _sync_all),
                ControlAction("sync.start_all", "Start all intelligence sync loops", "Intelligence", "Start all registered background intelligence synchronizers.", _start_all_syncs),
                ControlAction("sync.stop_all", "Stop all intelligence sync loops", "Intelligence", "Stop all registered background intelligence synchronizers.", _stop_all_syncs, danger=True, confirmation="STOP ALL INTELLIGENCE SYNCS"),

                ControlAction("autopilot.configure", "Configure Tactical Autopilot", "Autopilot", "Update bounded Autopilot configuration.", lambda p: autopilot.configure(p["args"]),
                              args_example={"enabled": True, "assets": ["NQ"], "cadence_seconds": 15, "robustness_windows": 3}),
                ControlAction("autopilot.start", "Start Tactical Autopilot", "Autopilot", "Enable and start the Tactical Autopilot background loop.", lambda _: autopilot.start()),
                ControlAction("autopilot.stop", "Stop Tactical Autopilot", "Autopilot", "Disable the Tactical Autopilot background loop.", lambda _: autopilot.stop()),
                ControlAction("autopilot.step", "Run one Tactical Autopilot cycle", "Autopilot", "Run exactly one Tactical Autopilot research cycle.", lambda _: autopilot.cycle_once()),
                ControlAction("autopilot.reset", "Reset Tactical Autopilot", "Autopilot", "Clear Tactical Autopilot runtime state and leave it disabled.", lambda _: autopilot.reset(), danger=True, confirmation="RESET AUTOPILOT"),

                ControlAction("research.start", "Start research study", "Research", "Launch one bounded study on the selected asset.", _research_start_control, target="asset",
                              args_example={"grid": {}, "windows": {"train_start": 0, "train_end": 1, "validation_start": 2, "validation_end": 3, "holdout_start": 4, "holdout_end": 5}}),
                ControlAction("research.cancel", "Cancel research job", "Research", "Request cancellation of the active research study by job id.", lambda p: research.cancel(p["target"]), target="job"),
                ControlAction("research.propose", "Create research proposal", "Research", "Create a proposal from a qualified study and bound evidence.", _research_propose_control, target="job",
                              args_example={"evidence_ids": ["current-evidence-id"], "rationale": "operator review"}),
                ControlAction("research.export", "Export qualified proposal", "Research", "Export one qualified proposal artifact for further paper evaluation.", lambda p: research.export(p["target"]), target="proposal"),
                ControlAction("research.analysis", "Start specialist analysis", "Research", "Start specialist analysis bound to one qualified study and evidence set.", _research_analysis_control, target="job",
                              args_example={"evidence_ids": ["current-evidence-id"], "rationale": "operator review", "apply": False}),
                ControlAction("research.analysis_cancel", "Cancel specialist analysis", "Research", "Cancel a running specialist analysis job.", lambda p: research.analysis.journal.cancel(p["target"]), target="job"),
                ControlAction("research.activate", "Activate research candidate", "Research", "Apply a fully qualified research proposal to the paper engine through the activation boundary.", _research_activate_control, target="proposal",
                              danger=True, confirmation="ACTIVATE RESEARCH CANDIDATE", args_example={"operation_id": "operator-operation-id"}),
                ControlAction("research.rollback", "Roll back research activation", "Research", "Roll back the selected asset's current research activation.", _research_rollback_control, target="asset",
                              danger=True, confirmation="ROLL BACK RESEARCH ACTIVATION", args_example={"operation_id": "operator-operation-id"}),
                ControlAction("research.recover", "Recover asset research activation", "Research", "Recover the selected asset's research activation state.", lambda p: research.recover({"asset": p["target"]}), target="asset"),
                ControlAction("research.collect", "Collect research source", "Research", "Run one registered research-source collection operation.", _research_collect_control, target="source",
                              args_example={"options": {}}),
                ControlAction("research.configure_adaptation", "Configure adaptation scheduler", "Research", "Update bounded automatic research-adaptation settings.", lambda p: research.configure_adaptation(p["args"]),
                              args_example={"enabled": False}),
                ControlAction("research.configure_source_watch", "Configure source watch", "Research", "Update bounded research source-watch settings.", lambda p: research.configure_source_watch(p["args"]),
                              args_example={"enabled": False}),

                ControlAction("parallax.record_decision", "Record PARALLAX decision", "PARALLAX", "Record a causally timestamped PARALLAX decision and counterfactual branches.", _parallax_decision_control,
                              args_example={"asset": "NQ", "action": "abstain", "observed_at": "2026-10-01T00:00:00Z", "regime": "unknown", "context": {}, "subsystem_votes": {}}),
                ControlAction("parallax.record_outcome", "Record PARALLAX outcome", "PARALLAX", "Record an observed branch outcome and trigger DREAMSTATE re-screening.", _parallax_outcome_control,
                              args_example={"decision_id": "decision-id", "label": "actual", "utility": 0.0, "metrics": {}, "evidence": []}),
                ControlAction("dreamstate.refresh", "Refresh DREAMSTATE", "DREAMSTATE", "Re-screen PARALLAX counterfactual evidence into DREAMSTATE candidates.", lambda p: dreamstate.refresh((p["args"] or {}).get("min_samples", 5)),
                              args_example={"min_samples": 5}),
                ControlAction("dreamstate.evaluate", "Evaluate DREAMSTATE candidate", "DREAMSTATE", "Apply explicit validation-gate evidence to one candidate.", _dreamstate_evaluate_control, target="candidate",
                              args_example={"validation": {"causal_time": True}, "evidence": ["operator-reviewed evidence"]}),
                ControlAction("dreamstate.retire", "Retire DREAMSTATE candidate", "DREAMSTATE", "Retire one candidate with a durable reason.", _dreamstate_retire_control, target="candidate",
                              danger=True, confirmation="RETIRE DREAMSTATE CANDIDATE", args_example={"reason": "operator decision"}),

                ControlAction("possibility.ingest_evidence", "Ingest ICARUS Psi evidence", "Possibility", "Inject provenance-labelled bounded external possibility-force evidence for research only.", _possibility_evidence_control, target="asset",
                              args_example={"values": {"gamma_pressure": {"value": 0.0, "confidence": 1.0}}, "source": "operator", "ttl_seconds": 300.0}),

                ControlAction("commissioning.capture", "Freeze Chronofold forecast", "Commissioning", "Append one immutable pre-outcome Chronofold forecast receipt for the selected asset.", _commissioning_capture_control, target="asset"),
                ControlAction("commissioning.settle_asset", "Settle ready forecasts for asset", "Commissioning", "Append outcomes for selected-asset forecasts whose target Chronon has been reached.", _commissioning_settle_asset_control, target="asset"),
                ControlAction("commissioning.settle_all", "Settle all ready forecasts", "Commissioning", "Append outcomes for every forecast whose target Chronon has been reached.", lambda _: commissioning.settle_ready()),
                ControlAction("commissioning.tick", "Run scientific commissioning cycle", "Commissioning", "Capture eligible shadow forecasts and settle ready outcomes once.", lambda _: commissioning.tick()),
                ControlAction("commissioning.start", "Start scientific commissioning loop", "Commissioning", "Start the append-only shadow commissioning sampler.", lambda _: (commissioning.start_background() or commissioning.status())),
                ControlAction("commissioning.stop", "Stop scientific commissioning loop", "Commissioning", "Stop only the shadow commissioning sampler; trading authority is unaffected.", lambda _: (commissioning.close() or commissioning.status())),

                ControlAction("system.record_audit", "Update repository audit snapshot", "Observability", "Update the System Intelligence repository/CI snapshot while preserving durable event and loop receipts.", _system_audit_control,
                              danger=True, confirmation="UPDATE SYSTEM AUDIT SNAPSHOT", args_example={"status": "unknown", "source": "operator-root-control"}),
                ControlAction("system.record_event", "Record System Intelligence event", "Observability", "Append one durable system repair/audit/integration event.", _system_event_control,
                              args_example={"id": "event-id", "kind": "audit", "severity": "info", "title": "Operator event", "detail": "details", "recorded_at": "2026-10-01T00:00:00Z", "repository": "reppiks490/Icarus", "ref": "manual"}),
                ControlAction("system.upsert_loop", "Upsert automation-loop status", "Observability", "Write one durable automation-loop status receipt into System Intelligence.", _system_loop_control,
                              args_example={"id": "loop-id", "title": "Loop", "status": "active"}),
                ControlAction("integrity.record_event", "Record Data Integrity event", "Observability", "Append one provenance-labelled integrity/MCP receipt.", _integrity_event_control,
                              args_example={"kind": "audit", "area": "operator-control", "summary": "operator integrity event", "status": "observed", "severity": "info", "verification": "operator observation", "interface_effect": "visible in Data Integrity and Root Control", "evidence": []}),
                ControlAction("brain.record_event", "Record Adaptive Brain event", "Observability", "Append one evidence-backed brain/subsystem/candidate event.", _brain_event_control,
                              args_example={"kind": "learning", "subject": "operator-control", "summary": "operator brain event", "status": "observed", "evidence": []}),
            )
        },
    )

    class H(BaseHTTPRequestHandler):
        server_version = "icarus"
        sys_version = ""
        timeout = 30                                              # idle connections must not hold a thread forever

        def log_message(self, *a: Any) -> None:  # quiet
            pass

        def _send(self, code: int, body: bytes, ctype: str = "application/json", extra: Dict[str, str] | None = None) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith("text") else ""))
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-src https://www.youtube-nocookie.com; frame-ancestors 'none'")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, code: int, obj: Any) -> None:
            self._send(code, dumps_safe(obj))

        def _host_ok(self) -> bool:
            """Loopback only: a DNS-rebinding page carries its own hostname in Host."""
            host = self.headers.get("Host", "").rsplit(":", 1)[0].strip("[]").lower()
            return host in ("127.0.0.1", "localhost", "::1")

        def _auth(self) -> bool:
            scheme, _, tok = self.headers.get("Authorization", "").partition(" ")
            return bool(token) and scheme.lower() == "bearer" and hmac.compare_digest(tok, token)

        def _int(self, q: Dict[str, Any], key: str, default: int, lo: int, hi: int) -> int:
            try:
                return max(lo, min(hi, int(q.get(key, [default])[0])))
            except (TypeError, ValueError):
                return default

        def _runner(self, sym: str):
            try:
                key = resolve(sym or "").symbol
            except ValueError:
                return None
            return port.runners.get(key)

        def do_GET(self) -> None:  # noqa: N802
            if not self._host_ok():
                return self._json(403, {"detail": "bad host"})
            p = urlparse(self.path)
            q = parse_qs(p.query)
            if p.path == "/":
                return self._send(200, brand.render(html_path.read_bytes()), "text/html")
            if p.path == "/research-ui.js":
                return self._send(200, (html_path.parent / "research-ui.js").read_bytes(), "text/javascript")
            if p.path == "/sources-ui.js":
                return self._send(200, (html_path.parent / "sources-ui.js").read_bytes(), "text/javascript")
            if p.path == "/market-data-ui.js":
                return self._send(200, (html_path.parent / "market-data-ui.js").read_bytes(), "text/javascript")
            if p.path == "/integrity-ui.js":
                return self._send(200, (html_path.parent / "integrity-ui.js").read_bytes(), "text/javascript")
            if p.path == "/engine-control-ui.js":
                return self._send(200, (html_path.parent / "engine-control-ui.js").read_bytes(), "text/javascript")
            if p.path == "/autopilot-ui.js":
                return self._send(200, (html_path.parent / "autopilot-ui.js").read_bytes(), "text/javascript")
            if p.path == "/brain-ui.js":
                return self._send(200, (html_path.parent / "brain-ui.js").read_bytes(), "text/javascript")
            if p.path == "/evolution-ui.js":
                return self._send(200, (html_path.parent / "evolution-ui.js").read_bytes(), "text/javascript")
            if p.path == "/parallax-ui.js":
                return self._send(200, (html_path.parent / "parallax-ui.js").read_bytes(), "text/javascript")
            if p.path == "/possibility-ui.js":
                return self._send(200, (html_path.parent / "possibility-ui.js").read_bytes(), "text/javascript")
            if p.path == "/pantheon-ui.js":
                return self._send(200, (html_path.parent / "pantheon-ui.js").read_bytes(), "text/javascript")
            if p.path == "/sibyl-ui.js":
                return self._send(200, (html_path.parent / "sibyl-ui.js").read_bytes(), "text/javascript")
            if p.path == "/apex-ui.js":
                return self._send(200, (html_path.parent / "apex-ui.js").read_bytes(), "text/javascript")
            if p.path == "/ascendancy-ui.js":
                return self._send(200, (html_path.parent / "ascendancy-ui.js").read_bytes(), "text/javascript")
            if p.path == "/learning-ui.js":
                return self._send(200, (html_path.parent / "learning-ui.js").read_bytes(), "text/javascript")
            if p.path == "/chronofold-ui.js":
                return self._send(200, (html_path.parent / "chronofold-ui.js").read_bytes(), "text/javascript")
            if p.path == "/commissioning-ui.js":
                return self._send(200, (html_path.parent / "commissioning-ui.js").read_bytes(), "text/javascript")
            if p.path in ("/experience-ui.js", "/experience-ui.css"):
                ctype = "text/javascript" if p.path.endswith(".js") else "text/css"
                return self._send(200, (html_path.parent / p.path[1:]).read_bytes(), ctype)
            if p.path == "/healthz":
                return self._json(200, {"ok": True, "assets": list(port.order), "warm": all(r.warm for r in port.runners.values()) if port.runners else False})
            if p.path == "/status/public":
                try:
                    return self._json(200, port.status())
                except Exception as ex:
                    sys.stderr.write(f"status/public failed: {type(ex).__name__}: {ex}\n")
                    return self._json(500, {"ok": False, "detail": f"{type(ex).__name__}: {ex}", "assets": []})
            if p.path == "/api/ascendancy/capabilities":
                if not self._auth():
                    return self._json(401, {"detail": "bad admin token"})
                return self._json(200, capability_snapshot())
            if p.path == "/api/ascendancy/genomes":
                if not self._auth():
                    return self._json(401, {"detail": "bad admin token"})
                try:
                    return self._json(200, _ascendancy_snapshot())
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
                except Exception as ex:
                    port.journal.log("WARN", f"ASCENDANCY genome snapshot: {type(ex).__name__}: {ex}")
                    return self._json(500, {"detail": f"{type(ex).__name__}: {ex}"})
            if p.path == "/api/ascendancy/candidates":
                if not self._auth():
                    return self._json(401, {"detail": "bad admin token"})
                try:
                    return self._json(200, ascendancy_foundry.snapshot())
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
                except Exception as ex:
                    port.journal.log("WARN", f"ASCENDANCY foundry snapshot: {type(ex).__name__}: {ex}")
                    return self._json(500, {"detail": f"{type(ex).__name__}: {ex}"})
            if p.path == "/api/ascendancy/unknowns":
                if not self._auth():
                    return self._json(401, {"detail": "bad admin token"})
                try:
                    return self._json(200, ascendancy_unknowns.snapshot())
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
                except Exception as ex:
                    port.journal.log("WARN", f"ASCENDANCY unknown snapshot: {type(ex).__name__}: {ex}")
                    return self._json(500, {"detail": f"{type(ex).__name__}: {ex}"})
            if p.path == "/api/ascendancy/mechanisms":
                if not self._auth():
                    return self._json(401, {"detail": "bad admin token"})
                try:
                    return self._json(200, ascendancy_mechanisms.snapshot())
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
                except Exception as ex:
                    port.journal.log("WARN", f"ASCENDANCY mechanism snapshot: {type(ex).__name__}: {ex}")
                    return self._json(500, {"detail": f"{type(ex).__name__}: {ex}"})
            if p.path == "/api/ascendancy/inventions":
                if not self._auth():
                    return self._json(401, {"detail": "bad admin token"})
                try:
                    return self._json(200, ascendancy_inventions.snapshot())
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
                except Exception as ex:
                    port.journal.log("WARN", f"ASCENDANCY invention snapshot: {type(ex).__name__}: {ex}")
                    return self._json(500, {"detail": f"{type(ex).__name__}: {ex}"})
            if p.path == "/api/ascendancy/contributions":
                if not self._auth():
                    return self._json(401, {"detail": "bad admin token"})
                try:
                    return self._json(200, ascendancy_contribution.snapshot())
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
                except Exception as ex:
                    port.journal.log("WARN", f"ASCENDANCY contribution snapshot: {type(ex).__name__}: {ex}")
                    return self._json(500, {"detail": f"{type(ex).__name__}: {ex}"})
            if p.path == "/api/ascendancy/evaluator":
                if not self._auth():
                    return self._json(401, {"detail": "bad admin token"})
                try:
                    return self._json(200, ascendancy_evaluator.snapshot())
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
                except Exception as ex:
                    port.journal.log("WARN", f"ASCENDANCY evaluator snapshot: {type(ex).__name__}: {ex}")
                    return self._json(500, {"detail": f"{type(ex).__name__}: {ex}"})
            if p.path == "/api/golive":
                return self._json(200, golive_report(port))
            if p.path == "/api/agent":
                return self._json(200, agent_report())
            if p.path == "/api/briefing":
                return self._json(200, briefing_report())
            if p.path == "/api/system/audit":
                return self._json(200, load_repository_audit(port.base_dir))
            if p.path == "/api/integrity":
                if not self._auth():
                    return self._json(401, {"detail": "bad admin token"})
                return self._json(200, integrity_snapshot(port.base_dir))
            if p.path == "/api/evolution":
                if not self._auth():
                    return self._json(401, {"detail": "bad admin token"})
                return self._json(200, evolution_remote_sync.status())
            if p.path == "/api/evidence-lab":
                if not self._auth():
                    return self._json(401, {"detail": "bad admin token"})
                return self._json(200, evidence_lab_sync.status())
            if p.path == "/api/engine-control":
                if not self._auth():
                    return self._json(401, {"detail": "bad admin token"})
                return self._json(200, control.status())
            if p.path == "/api/autopilot":
                if not self._auth():
                    return self._json(401, {"detail": "bad admin token"})
                return self._json(200, autopilot.status())
            if p.path == "/api/parallax":
                if not self._auth():
                    return self._json(401, {"detail": "bad admin token"})
                try:
                    return self._json(200, parallax.snapshot())
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/api/dreamstate":
                if not self._auth():
                    return self._json(401, {"detail": "bad admin token"})
                try:
                    return self._json(200, dreamstate.snapshot())
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/api/possibility/evidence":
                if not self._auth():
                    return self._json(401, {"detail": "bad admin token"})
                try:
                    include_expired = str(q.get("include_expired", ["false"])[0]).strip().lower() in {"1", "true", "yes", "on"}
                    return self._json(200, possibility.evidence_snapshot(
                        q.get("asset", [""])[0],
                        limit=int(q.get("limit", ["100"])[0]),
                        include_expired=include_expired,
                        as_of=q.get("as_of", [None])[0],
                    ))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/api/possibility":
                if not self._auth():
                    return self._json(401, {"detail": "bad admin token"})
                try:
                    return self._json(200, possibility.snapshot(q.get("asset", [""])[0]))
                except Exception as ex:
                    port.journal.log("WARN", f"possibility snapshot: {type(ex).__name__}: {ex}")
                    return self._json(500, {"detail": f"{type(ex).__name__}: {ex}"})
            if p.path == "/api/pantheon":
                if not self._auth():
                    return self._json(401, {"detail": "bad admin token"})
                try:
                    return self._json(200, pantheon.snapshot())
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/api/learning":
                if not self._auth():
                    return self._json(401, {"detail": "bad admin token"})
                return self._json(200, learning.snapshot())
            if p.path == "/api/learning/health":
                if not self._auth():
                    return self._json(401, {"detail": "bad admin token"})
                return self._json(200, learning.health())
            if p.path == "/api/learning/experience":
                if not self._auth():
                    return self._json(401, {"detail": "bad admin token"})
                return self._json(200, learning.experience_state())
            if p.path == "/api/learning/scorecards":
                if not self._auth():
                    return self._json(401, {"detail": "bad admin token"})
                return self._json(200, {"scorecards": learning.scorecards(), "execution_authorized": False, "production_decision_authorized": False})
            if p.path == "/api/learning/datasets":
                if not self._auth():
                    return self._json(401, {"detail": "bad admin token"})
                return self._json(200, {"datasets": learning.datasets(), "training_runs": learning.training_runs(), "execution_authorized": False, "production_decision_authorized": False})
            apex_read_routes = {
                "/api/apex": None,
                "/api/apex/participants": "participants",
                "/api/apex/crowdhunt": "crowdhunt",
                "/api/apex/forces": "forces",
                "/api/apex/cascades": "cascades",
                "/api/apex/causality": "causality",
                "/api/apex/worlds": "worlds",
                "/api/apex/epistemics": "epistemics",
                "/api/apex/self": "self",
                "/api/apex/conscience": "conscience",
            }
            if p.path in apex_read_routes:
                if not self._auth():
                    return self._json(401, {"detail": "bad admin token"})
                try:
                    state = apex.snapshot(
                        as_of=q.get("as_of", [None])[0],
                        asset=q.get("asset", [None])[0],
                    )
                    key = apex_read_routes[p.path]
                    return self._json(200, state if key is None else state[key])
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
                except Exception as ex:
                    port.journal.log("WARN", f"APEX snapshot: {type(ex).__name__}: {ex}")
                    return self._json(500, {"detail": f"{type(ex).__name__}: {ex}"})
            if p.path == "/api/sibyl":
                if not self._auth():
                    return self._json(401, {"detail": "bad admin token"})
                try:
                    try:
                        market_state = port.status()
                    except Exception:
                        market_state = {}
                    try:
                        parallax_state = parallax.snapshot()
                    except Exception:
                        parallax_state = {}
                    try:
                        dreamstate_state = dreamstate.snapshot()
                    except Exception:
                        dreamstate_state = {}
                    try:
                        brain_state = brain_snapshot(
                            port.base_dir,
                            proof_status=performance_proof.snapshot(),
                            latency_status=latency_telemetry.snapshot(),
                        )
                    except Exception:
                        brain_state = {}
                    return self._json(200, sibyl.snapshot(
                        q.get("asset", [None])[0],
                        market_status=market_state,
                        parallax_state=parallax_state,
                        dreamstate_state=dreamstate_state,
                        brain_state=brain_state,
                    ))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/api/chronofold":
                if not self._auth():
                    return self._json(401, {"detail": "bad admin token"})
                try:
                    return self._json(200, chronofold.snapshot(q.get("asset", [""])[0]))
                except Exception as ex:
                    port.journal.log("WARN", f"chronofold snapshot: {type(ex).__name__}: {ex}")
                    return self._json(500, {"detail": f"{type(ex).__name__}: {ex}"})
            if p.path == "/api/commissioning":
                if not self._auth():
                    return self._json(401, {"detail": "bad admin token"})
                try:
                    return self._json(200, commissioning.status(q.get("asset", [""])[0]))
                except Exception as ex:
                    port.journal.log("WARN", f"commissioning snapshot: {type(ex).__name__}: {ex}")
                    return self._json(500, {"detail": f"{type(ex).__name__}: {ex}"})
            if p.path == "/api/performance-proof":
                if not self._auth():
                    return self._json(401, {"detail": "bad admin token"})
                return self._json(200, performance_proof.snapshot())
            if p.path == "/api/performance-proof/pending":
                if not self._auth():
                    return self._json(401, {"detail": "bad admin token"})
                try:
                    return self._json(200, performance_proof.pending_settlements(
                        as_of=q.get("as_of", [None])[0],
                        limit=int(q.get("limit", ["100"])[0]),
                    ))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/api/latency":
                if not self._auth():
                    return self._json(401, {"detail": "bad admin token"})
                return self._json(200, latency_telemetry.snapshot())
            if p.path == "/api/source-reliability":
                if not self._auth():
                    return self._json(401, {"detail": "bad admin token"})
                return self._json(200, source_reliability.snapshot())
            if p.path == "/api/qualification-receipts":
                if not self._auth():
                    return self._json(401, {"detail": "bad admin token"})
                return self._json(200, qualification_receipts.snapshot())
            if p.path == "/api/brain":
                if not self._auth():
                    return self._json(401, {"detail": "bad admin token"})
                try:
                    market = port.status()
                except Exception:
                    market = {}
                try:
                    research_state = research.status()
                except Exception:
                    research_state = {}
                return self._json(200, brain_snapshot(
                    port.base_dir,
                    market_status=market,
                    research_status=research_state,
                    system_audit=load_repository_audit(port.base_dir),
                    integrity=integrity_snapshot(port.base_dir),
                    remote_sync=brain_remote_sync.status(),
                    research_sync=brain_research_sync.status(),
                    evidence_lab_sync=evidence_lab_sync.status(),
                    proof_status=performance_proof.snapshot(),
                    latency_status=latency_telemetry.snapshot(),
                    source_reliability=source_reliability.snapshot(),
                    qualification_receipts=qualification_receipts.snapshot(),
                ))
            if p.path == "/api/input-meta":
                return self._json(200, meta)
            if p.path.startswith("/api/research"):
                if not self._auth():
                    return self._json(401, {"detail": "bad admin token"})
                try:
                    if p.path == "/api/research":
                        return self._json(200, research.status())
                    if p.path == "/api/research/adaptation":
                        return self._json(200, research.adaptation.status())
                    if p.path == "/api/research/source-watch":
                        return self._json(200, research.source_watch.status())
                    if p.path == "/api/research/events":
                        return self._json(200, research.events(q.get("asset", [""])[0]))
                    if p.path == "/api/research/analysis":
                        return self._json(200, research.analysis.status())
                    if p.path.startswith("/api/research/analysis/"):
                        return self._json(200, research.analysis.job(p.path.rsplit("/", 1)[1]))
                    if p.path == "/api/research/activation":
                        return self._json(200, research.activation.status())
                    if p.path == "/api/research/sources":
                        return self._json(200, research.market_sources.status())
                    if p.path == "/api/research/records":
                        return self._json(200, research.market_sources.records(kind=q.get("kind", ["asset"])[0],
                            asset=q.get("asset", [None])[0], cik=q.get("cik", [None])[0],
                            limit=int(q.get("limit", ["100"])[0])))
                    if p.path.startswith("/api/research/jobs/"):
                        return self._json(200, research.job(p.path.rsplit("/", 1)[1]))
                    if p.path.startswith("/api/research/proposals/"):
                        return self._json(200, research.ledger.get_proposal(p.path.rsplit("/", 1)[1]))
                except (ValueError, TypeError, KeyError) as ex:
                    return self._json(400, {"detail": str(ex)})
                return self._json(404, {"detail": "unknown research resource"})
            if p.path == "/api/presets":
                out = []
                pdir = os.path.join(port.base_dir, "presets")
                if os.path.isdir(pdir):
                    for f in sorted(os.listdir(pdir)):
                        if f.endswith(".json"):
                            d = _read_json(os.path.join(pdir, f))
                            out.append({"name": f[:-5], "meta": d.get("_meta", {}), "count": len([k for k in d if not k.startswith("_")])})
                return self._json(200, out)
            if p.path == "/api/assets":
                return self._json(200, {"registry": [{
                                            "symbol": s.symbol, "name": s.name, "feed": s.feed, "calendar": s.calendar,
                                            "mintick": s.mintick, "multiplier": s.multiplier, "kind": s.kind,
                                            "continuous_symbol": s.tv_symbol if s.kind == "futures" else None,
                                            "provider_symbol": s.ticker,
                                            "contract_policy": "continuous_only" if s.kind == "futures" else "not_applicable",
                                        } for s in REGISTRY.values()],
                                        "running": list(port.order), "chart_capabilities": chart_capabilities()})
            if p.path == "/api/commands":
                return self._json(200, COMMANDS)
            if p.path.startswith("/api/export/"):
                r = self._runner(p.path.rsplit("/", 1)[1].replace(".csv", ""))
                if not r:
                    return self._json(404, {"error": "unknown asset"})
                return self._send(200, r.export_csv().encode("utf-8"), "text/csv", {"Content-Disposition": f'attachment; filename="{r.symbol}_trades.csv"'})
            if p.path.startswith("/api/chart/"):
                r = self._runner(p.path.rsplit("/", 1)[1])
                if not r:
                    return self._json(404, {"error": "unknown asset"})
                return self._json(200, r.chart(self._int(q, "n", 240, 20, 800)))
            if p.path.startswith("/api/trades/"):
                r = self._runner(p.path.rsplit("/", 1)[1])
                if not r:
                    return self._json(404, {"error": "unknown asset"})
                return self._json(200, r.trades(self._int(q, "limit", 100, 1, 2000)))
            if p.path.startswith("/api/market-data/"):
                rest = p.path[len("/api/market-data/"):]
                parts = [x for x in rest.split("/") if x]
                if len(parts) != 2:
                    return self._json(404, {"error": "market-data route is /api/market-data/<asset>/<capabilities|ticks|depth>"})
                r = self._runner(parts[0])
                if not r:
                    return self._json(404, {"error": "unknown asset"})
                kind = parts[1]
                feed = r.feed
                if kind == "capabilities":
                    caps = feed.capabilities() if hasattr(feed, "capabilities") else {}
                    metadata = feed.meta(r.spec.ticker) if hasattr(feed, "meta") else {}
                    return self._json(200, {"asset": r.symbol, "provider": type(feed).__name__.lower(),
                                            "capabilities": caps, "metadata": metadata})
                if kind == "ticks":
                    if not hasattr(feed, "trades"):
                        return self._json(409, {"error": f"{type(feed).__name__} does not expose trade ticks"})
                    limit = self._int(q, "limit", 1000, 1, 10000)
                    since = self._int(q, "since_ts", 0, 0, 4_294_967_295)
                    try:
                        rows = feed.trades(r.spec.ticker, since_ts=(since or None), limit=limit)
                    except ValueError as ex:
                        return self._json(400, {"error": str(ex)})
                    except Exception as ex:
                        port.journal.log("WARN", f"market-data ticks {r.symbol}: {type(ex).__name__}: {ex}")
                        return self._json(502, {"error": f"{type(ex).__name__}: {ex}"})
                    return self._json(200, {"asset": r.symbol, "provider": type(feed).__name__.lower(),
                                            "ticks": [vars(x) if hasattr(x, "__dict__") else x for x in rows]})
                if kind == "depth":
                    if not hasattr(feed, "depth_events"):
                        return self._json(409, {"error": f"{type(feed).__name__} does not expose order-book depth"})
                    schema = str(q.get("schema", ["mbp-10"])[0]).strip().lower()
                    if schema not in ("mbp-10", "mbo"):
                        return self._json(400, {"error": "schema must be mbp-10 or mbo"})
                    limit = self._int(q, "limit", 1000, 1, 10000)
                    try:
                        rows = feed.depth_events(r.spec.ticker, schema=schema, limit=limit)
                    except ValueError as ex:
                        return self._json(400, {"error": str(ex)})
                    except Exception as ex:
                        port.journal.log("WARN", f"market-data depth {r.symbol}: {type(ex).__name__}: {ex}")
                        return self._json(502, {"error": f"{type(ex).__name__}: {ex}"})
                    return self._json(200, {"asset": r.symbol, "provider": type(feed).__name__.lower(),
                                            "schema": schema, "events": rows})
                return self._json(404, {"error": "unknown market-data resource"})
            if p.path.startswith("/api/backtest/"):
                rest = p.path[len("/api/backtest/"):]
                job_id, _, tail = rest.partition("/")
                job = JOBS.get(job_id)
                if not job:
                    return self._json(404, {"error": "unknown backtest job"})
                if tail == "trades.csv":
                    if job["status"] != "done":
                        return self._json(409, {"error": "not finished"})
                    return self._send(200, job["result"]["csv"].encode("utf-8"), "text/csv",
                                      {"Content-Disposition": f'attachment; filename="backtest_{job["result"]["asset"]}_{job_id}.csv"'})
                out = {k: job[k] for k in ("id", "status", "progress", "started", "params", "error")}
                out["finished"] = job.get("finished")
                if job["status"] == "done" and q.get("full", ["1"])[0] != "0":
                    out["result"] = {k: v for k, v in job["result"].items() if k != "csv"}
                return self._json(200, out)
            if p.path.startswith("/api/inputs/"):
                r = self._runner(p.path.rsplit("/", 1)[1])
                if not r:
                    return self._json(404, {"error": "unknown asset"})
                over = _read_json(os.path.join(port.base_dir, f"inputs.{r.symbol}.json"))
                return self._json(200, {"asset": r.symbol, "effective": r.inputs.to_dict(), "base": r.inputs_base.to_dict(), "sources": r.cfg.sources,
                                        "overrides": {k: v for k, v in over.items() if not k.startswith("_")}, "preset": r.cfg.preset, "pts_scale": r.pts_scale,
                                        "instrument": {
                                            "kind": r.spec.kind,
                                            "continuous_symbol": r.spec.tv_symbol if r.spec.kind == "futures" else None,
                                            "provider_symbol": r.spec.ticker,
                                            "contract_policy": "continuous_only" if r.spec.kind == "futures" else "not_applicable",
                                        },
                                        "chart": {"timeframe": r.spec.chart_tf, "chart_type": r.spec.chart_type,
                                                  "fill_on": r.spec.fill_on, "security_source": r.spec.security_source},
                                        "chart_capabilities": r.chart_capability_view()})
            self._json(404, {"error": "not found"})

        def _drain_body(self) -> None:
            # Claude (Opus 5.5) 2026-09-27. Answering before the body is read and then closing makes the OS reset
            # the connection, and the client can lose the answer (WinError 10053, 3 in 500 requests). Every early
            # POST rejection discards the body unparsed; never more than MAX_BODY_BYTES, bounded by the timeout.
            try:
                n = int(self.headers.get("Content-Length", "0") or 0)
            except ValueError:
                return
            if 0 < n <= MAX_BODY_BYTES and not self.headers.get("Transfer-Encoding"):
                self.rfile.read(n)

        def do_POST(self) -> None:  # noqa: N802
            if not self._host_ok():
                self._drain_body()
                return self._json(403, {"detail": "bad host"})
            p = urlparse(self.path)
            if p.path == "/research/events":
                secret = os.environ.get("ICARUS_INGEST_SECRET", "")
                if not secret:
                    self._drain_body()
                    return self._json(503, {"detail": "event receiver is not configured"})
                if not self.headers.get("X-Icarus-Signature") or not self.headers.get("X-Icarus-Timestamp"):
                    self._drain_body()
                    return self._json(401, {"detail": "signed event required"})
                try:
                    n = int(self.headers.get("Content-Length", "0"))
                    if not 0 < n <= MAX_BODY_BYTES or self.headers.get("Transfer-Encoding"):
                        return self._json(413, {"detail": "invalid event body length"})
                    event = research.ledger.ingest_signed_event(self.rfile.read(n), self.headers["X-Icarus-Timestamp"],
                                                                self.headers["X-Icarus-Signature"], secret)
                    return self._json(200, {"ok": True, "event_id": event["event_id"], "execution_authorized": False})
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if not p.path.startswith("/admin/"):
                self._drain_body()
                return self._json(404, {"error": "not found"})
            if not self._auth():                                  # authenticate BEFORE parsing any body
                self._drain_body()                                # discard it unread, or the 401 can be lost
                return self._json(401, {"detail": "bad admin token"})
            try:
                n = int(self.headers.get("Content-Length", "0") or 0)
            except ValueError:
                return self._json(400, {"detail": "bad Content-Length"})
            if n < 0 or n > (1 << 20):
                return self._json(413, {"detail": "body too large"})
            raw = self.rfile.read(n) if n else b""
            try:
                body = strict_json(raw) if p.path.startswith(("/admin/research/", "/admin/integrity/", "/admin/parallax/", "/admin/dreamstate/", "/admin/possibility/", "/admin/autopilot/", "/admin/engine-control", "/admin/pantheon/", "/admin/sibyl/", "/admin/apex/", "/admin/learning/", "/admin/qualification-receipts/", "/admin/ascendancy/")) else (json.loads(raw, parse_constant=_no_json_constants) if raw else {})
            except ValueError as ex:
                return self._json(400, {"detail": f"bad JSON body: {ex}"})
            if not isinstance(body, dict):
                return self._json(400, {"detail": "JSON body must be an object"})
            if p.path == "/admin/learning/config":
                try:
                    return self._json(200, research.configure_learning(body))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/admin/learning/tick":
                try:
                    return self._json(200, learning.run_cycle())
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/admin/learning/prediction":
                try:
                    return self._json(200, learning.record_prediction(body))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/admin/learning/outcome":
                try:
                    return self._json(200, learning.record_outcome(body))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/admin/learning/scan":
                try:
                    return self._json(200, learning.scan_history())
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/admin/learning/backfill":
                try:
                    dataset_id = body.get("dataset_id")
                    slots = body.get("slots")
                    if slots is not None and not isinstance(slots, list):
                        raise ValueError("slots must be a list")
                    return self._json(200, learning.backfill_dataset(dataset_id, slots=slots))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/admin/apex/evidence":
                try:
                    return self._json(200, apex.ingest_evidence(body, enforce_local_receipt=True))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/admin/apex/outcome":
                try:
                    return self._json(200, apex.record_outcome(body))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/admin/apex/model-observation":
                try:
                    return self._json(200, apex.record_model_observation(body))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/admin/apex/experiment":
                try:
                    return self._json(200, apex.propose_experiment(body))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/admin/engine-control":
                try:
                    return self._json(200, control.run(body))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
                except Exception as ex:
                    port.journal.log(
                        "ERROR",
                        f"Engine Control request failed: {type(ex).__name__}: {ex}",
                    )
                    return self._json(
                        500,
                        {"detail": f"{type(ex).__name__}: {ex}"},
                    )
            if p.path == "/admin/ascendancy/genome":
                try:
                    return self._json(200, _ascendancy_research_mutation(
                        lambda: _ascendancy_register_genome(body)
                    ))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
                except Exception as ex:
                    port.journal.log("ERROR", f"ASCENDANCY genome register: {type(ex).__name__}: {ex}")
                    return self._json(500, {"detail": f"{type(ex).__name__}: {ex}"})
            if p.path == "/admin/ascendancy/genome-evaluation":
                try:
                    return self._json(200, _ascendancy_research_mutation(
                        lambda: ascendancy_archive.record_evaluation(body)
                    ))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
                except Exception as ex:
                    port.journal.log("ERROR", f"ASCENDANCY genome evaluation: {type(ex).__name__}: {ex}")
                    return self._json(500, {"detail": f"{type(ex).__name__}: {ex}"})
            if p.path == "/admin/ascendancy/genome-retire":
                try:
                    return self._json(200, _ascendancy_research_mutation(
                        lambda: ascendancy_archive.retire(
                            body.get("genome_id"), body.get("reason")
                        )
                    ))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
                except Exception as ex:
                    port.journal.log("ERROR", f"ASCENDANCY genome retire: {type(ex).__name__}: {ex}")
                    return self._json(500, {"detail": f"{type(ex).__name__}: {ex}"})
            if p.path == "/admin/ascendancy/candidate":
                try:
                    return self._json(200, _ascendancy_research_mutation(
                        lambda: ascendancy_foundry.register(body)
                    ))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
                except Exception as ex:
                    port.journal.log("ERROR", f"ASCENDANCY candidate register: {type(ex).__name__}: {ex}")
                    return self._json(500, {"detail": f"{type(ex).__name__}: {ex}"})
            if p.path == "/admin/ascendancy/candidate-stage":
                try:
                    return self._json(200, _ascendancy_research_mutation(
                        lambda: ascendancy_foundry.advance(
                            body.get("candidate_id"), body.get("stage"), body.get("reason")
                        )
                    ))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
                except Exception as ex:
                    port.journal.log("ERROR", f"ASCENDANCY candidate stage: {type(ex).__name__}: {ex}")
                    return self._json(500, {"detail": f"{type(ex).__name__}: {ex}"})
            if p.path == "/admin/ascendancy/candidate-reject":
                try:
                    return self._json(200, _ascendancy_research_mutation(
                        lambda: ascendancy_foundry.reject(
                            body.get("candidate_id"), body.get("reason")
                        )
                    ))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
                except Exception as ex:
                    port.journal.log("ERROR", f"ASCENDANCY candidate reject: {type(ex).__name__}: {ex}")
                    return self._json(500, {"detail": f"{type(ex).__name__}: {ex}"})
            if p.path == "/admin/ascendancy/candidate-retire":
                try:
                    return self._json(200, _ascendancy_research_mutation(
                        lambda: ascendancy_foundry.retire(
                            body.get("candidate_id"), body.get("reason")
                        )
                    ))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
                except Exception as ex:
                    port.journal.log("ERROR", f"ASCENDANCY candidate retire: {type(ex).__name__}: {ex}")
                    return self._json(500, {"detail": f"{type(ex).__name__}: {ex}"})
            if p.path == "/admin/ascendancy/unknown-event":
                try:
                    return self._json(200, _ascendancy_research_mutation(
                        lambda: ascendancy_unknowns.record_event(body)
                    ))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
                except Exception as ex:
                    port.journal.log("ERROR", f"ASCENDANCY unknown event: {type(ex).__name__}: {ex}")
                    return self._json(500, {"detail": f"{type(ex).__name__}: {ex}"})
            if p.path == "/admin/ascendancy/unknown-explanation":
                try:
                    return self._json(200, _ascendancy_research_mutation(
                        lambda: ascendancy_unknowns.record_explanation_test(body)
                    ))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
                except Exception as ex:
                    port.journal.log("ERROR", f"ASCENDANCY unknown explanation: {type(ex).__name__}: {ex}")
                    return self._json(500, {"detail": f"{type(ex).__name__}: {ex}"})
            if p.path == "/admin/ascendancy/unknown-link-candidate":
                try:
                    return self._json(200, _ascendancy_research_mutation(
                        lambda: ascendancy_unknowns.link_candidate(
                            body.get("phenomenon_signature"),
                            body.get("candidate_id"),
                            body.get("rationale"),
                        )
                    ))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
                except Exception as ex:
                    port.journal.log("ERROR", f"ASCENDANCY unknown candidate link: {type(ex).__name__}: {ex}")
                    return self._json(500, {"detail": f"{type(ex).__name__}: {ex}"})
            if p.path == "/admin/ascendancy/mechanism-experiment":
                try:
                    return self._json(200, _ascendancy_research_mutation(
                        lambda: _ascendancy_record_mechanism(body)
                    ))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
                except Exception as ex:
                    port.journal.log("ERROR", f"ASCENDANCY mechanism experiment: {type(ex).__name__}: {ex}")
                    return self._json(500, {"detail": f"{type(ex).__name__}: {ex}"})
            if p.path == "/admin/ascendancy/contribution-observation":
                try:
                    return self._json(200, _ascendancy_research_mutation(
                        lambda: _ascendancy_record_contribution(body)
                    ))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
                except Exception as ex:
                    port.journal.log("ERROR", f"ASCENDANCY contribution observation: {type(ex).__name__}: {ex}")
                    return self._json(500, {"detail": f"{type(ex).__name__}: {ex}"})
            if p.path == "/admin/ascendancy/evaluator-register":
                try:
                    return self._json(200, _ascendancy_research_mutation(
                        lambda: _ascendancy_register_evaluator_candidate(body)
                    ))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
                except Exception as ex:
                    port.journal.log("ERROR", f"ASCENDANCY evaluator register: {type(ex).__name__}: {ex}")
                    return self._json(500, {"detail": f"{type(ex).__name__}: {ex}"})
            if p.path == "/admin/ascendancy/evaluator-receipt":
                try:
                    return self._json(200, _ascendancy_research_mutation(
                        lambda: ascendancy_evaluator.record(body)
                    ))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
                except Exception as ex:
                    port.journal.log("ERROR", f"ASCENDANCY evaluator receipt: {type(ex).__name__}: {ex}")
                    return self._json(500, {"detail": f"{type(ex).__name__}: {ex}"})
            if p.path == "/admin/ascendancy/invention-generate":
                try:
                    return self._json(200, _ascendancy_research_mutation(
                        lambda: ascendancy_inventions.generate(body)
                    ))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
                except Exception as ex:
                    port.journal.log("ERROR", f"ASCENDANCY invention generate: {type(ex).__name__}: {ex}")
                    return self._json(500, {"detail": f"{type(ex).__name__}: {ex}"})
            if p.path == "/admin/ascendancy/invention-to-candidate":
                try:
                    return self._json(200, _ascendancy_research_mutation(
                        lambda: _ascendancy_invention_to_candidate(body)
                    ))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
                except Exception as ex:
                    port.journal.log("ERROR", f"ASCENDANCY invention handoff: {type(ex).__name__}: {ex}")
                    return self._json(500, {"detail": f"{type(ex).__name__}: {ex}"})
            if p.path == "/admin/learning/config":
                try:
                    return self._json(200, research.configure_learning(body))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/admin/learning/tick":
                try:
                    return self._json(200, learning.run_cycle())
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/admin/learning/prediction":
                try:
                    return self._json(200, learning.record_prediction(body))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/admin/learning/outcome":
                try:
                    return self._json(200, learning.record_outcome(body))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/admin/learning/scan":
                try:
                    return self._json(200, learning.scan_history())
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/admin/learning/backfill":
                try:
                    dataset_id = body.get("dataset_id")
                    slots = body.get("slots")
                    if slots is not None and not isinstance(slots, list):
                        raise ValueError("slots must be a list")
                    return self._json(200, learning.backfill_dataset(dataset_id, slots=slots))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/admin/apex/evidence":
                try:
                    return self._json(200, apex.ingest_evidence(body, enforce_local_receipt=True))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/admin/apex/outcome":
                try:
                    return self._json(200, apex.record_outcome(body))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/admin/apex/model-observation":
                try:
                    return self._json(200, apex.record_model_observation(body))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/admin/apex/experiment":
                try:
                    return self._json(200, apex.propose_experiment(body))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/admin/engine-control":
                try:
                    return self._json(200, control.run(body))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
                except Exception as ex:
                    port.journal.log(
                        "ERROR",
                        f"Engine Control request failed: {type(ex).__name__}: {ex}",
                    )
                    return self._json(
                        500,
                        {"detail": f"{type(ex).__name__}: {ex}"},
                    )
            if p.path == "/admin/system/audit":
                try:
                    audit = save_repository_audit(port.base_dir, body.get("audit", body))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
                return self._json(200, {"ok": True, "audit": audit, "note": "system intelligence snapshot recorded"})
            if p.path == "/admin/system/event":
                try:
                    audit = append_system_event(port.base_dir, body.get("event", body))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
                return self._json(200, {"ok": True, "audit": audit, "note": "system intelligence event recorded"})
            if p.path == "/admin/system/loop":
                try:
                    audit = upsert_loop_status(port.base_dir, body.get("loop", body))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
                return self._json(200, {"ok": True, "audit": audit, "note": "loop status recorded"})
            if p.path == "/admin/integrity/event":
                try:
                    return self._json(200, record_integrity_event(port.base_dir, body))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/admin/brain/event":
                try:
                    return self._json(200, record_brain_event(port.base_dir, body))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/admin/qualification-receipts/record":
                try:
                    result = qualification_receipts.record(body)
                    sync = _qualification_sync(
                        str(body.get("candidate_id") or ""),
                        str(body.get("candidate_source_repo") or ""),
                        str(body.get("candidate_source_commit") or ""),
                    )
                    return self._json(200, {"ok": True, "receipt": result, **sync})
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/admin/qualification-receipts/sync":
                try:
                    allowed = {"candidate_id", "candidate_source_repo", "candidate_source_commit"}
                    if set(body) != allowed:
                        raise ValueError("qualification sync requires exactly candidate_id, candidate_source_repo, candidate_source_commit")
                    result = _qualification_sync(
                        str(body["candidate_id"]),
                        str(body["candidate_source_repo"]),
                        str(body["candidate_source_commit"]),
                    )
                    if result["candidate_found"] is not True:
                        return self._json(404, {
                            "detail": "candidate revision is not present in the Adaptive Brain journal",
                            **result,
                        })
                    return self._json(200, {"ok": True, **result})
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/admin/source-reliability/observation":
                try:
                    return self._json(200, source_reliability.record_observation(body))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/admin/performance-proof/forecast":
                try:
                    return self._json(200, performance_proof.register_forecast(body))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/admin/performance-proof/outcome":
                try:
                    return self._json(200, performance_proof.record_outcome(body))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/admin/performance-proof/replay":
                try:
                    return self._json(200, performance_proof.record_replay(body))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/admin/autopilot/config":
                try:
                    return self._json(200, autopilot.configure(body))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/admin/autopilot/start":
                return self._json(200, autopilot.start())
            if p.path == "/admin/autopilot/stop":
                return self._json(200, autopilot.stop())
            if p.path == "/admin/autopilot/step":
                try:
                    return self._json(200, autopilot.cycle_once())
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/admin/autopilot/reset":
                if body.get("confirm") is not True:
                    return self._json(400, {"detail": "pass {\"confirm\": true}"})
                return self._json(200, autopilot.reset())
            if p.path == "/admin/possibility/evidence":
                try:
                    allowed = {"asset", "values", "source", "observed_at", "ttl_seconds"}
                    if set(body) - allowed or not {"asset", "values", "source"} <= set(body):
                        raise ValueError("possibility evidence requires asset, values, source and optional observed_at/ttl_seconds")
                    if not isinstance(body.get("values"), dict):
                        raise ValueError("values must be an object")
                    return self._json(200, possibility.ingest_external(
                        body["asset"], body["values"], source=body["source"],
                        observed_at=body.get("observed_at"), ttl_seconds=body.get("ttl_seconds", 300.0),
                    ))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/admin/parallax/decision/current":
                try:
                    payload, psi_vote = _current_parallax_payload(possibility, body)
                    if not payload.get("source_commit"):
                        provenance = local_code_provenance()
                        if not provenance.get("candidate_revision_eligible") or not provenance.get("commit"):
                            raise ValueError("exact clean ICARUS code provenance is required when source_commit is omitted")
                        payload["source_commit"] = provenance["commit"]
                    result = parallax.record_decision(payload)
                    result["capture_mode"] = "atomic_current"
                    result["captured_psi_vote"] = psi_vote
                    return self._json(200, result)
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/admin/sibyl/evidence":
                try:
                    payload = dict(body)
                    if not payload.get("source_commit"):
                        provenance = local_code_provenance()
                        if not provenance.get("candidate_revision_eligible") or not provenance.get("commit"):
                            raise ValueError("exact clean ICARUS code provenance is required when source_commit is omitted")
                        payload["source_commit"] = provenance["commit"]
                    return self._json(200, sibyl.record_evidence(payload))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/admin/sibyl/forecast":
                try:
                    payload = dict(body)
                    if not payload.get("source_commit"):
                        provenance = local_code_provenance()
                        if not provenance.get("candidate_revision_eligible") or not provenance.get("commit"):
                            raise ValueError("exact clean ICARUS code provenance is required when source_commit is omitted")
                        payload["source_commit"] = provenance["commit"]
                    try:
                        market_state = port.status()
                    except Exception:
                        market_state = {}
                    return self._json(200, sibyl.record_forecast(payload, market_status=market_state))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/admin/sibyl/outcome":
                try:
                    return self._json(200, sibyl.record_outcome(body))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/admin/sibyl/scenario":
                try:
                    try:
                        market_state = port.status()
                    except Exception:
                        market_state = {}
                    return self._json(200, sibyl.scenario(body, market_status=market_state))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/admin/pantheon/veritas":
                try:
                    return self._json(200, pantheon.record_veritas_reconciliation(body))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/admin/pantheon/claim":
                try:
                    return self._json(200, pantheon.record_agent_claim(body))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/admin/pantheon/observe":
                try:
                    payload = dict(body)
                    if not payload.get("source_commit"):
                        provenance = local_code_provenance()
                        if not provenance.get("candidate_revision_eligible") or not provenance.get("commit"):
                            raise ValueError("exact clean ICARUS code provenance is required when source_commit is omitted")
                        payload["source_commit"] = provenance["commit"]
                    existing_outputs = payload.get("subsystem_outputs", {})
                    if existing_outputs is None:
                        existing_outputs = {}
                    if not isinstance(existing_outputs, dict):
                        raise ValueError("subsystem_outputs must be an object")
                    signals = payload.get("signals", {})
                    if not isinstance(signals, dict):
                        raise ValueError("signals must be an object")
                    signals = dict(signals)
                    claimed_lineage = signals.pop("engine_evidence_lineage", None)
                    apex_lineage = {
                        "schema_version": "icarus-apex-engine-lineage-v1",
                        "status": "UNAVAILABLE",
                        "reason": "engine_evidence_ids not supplied",
                        "engine_evidence_lineage": {},
                        "engine_support": {},
                        "claimed_lineage_present": claimed_lineage is not None,
                        "lineage_owner": "APEX_EVIDENCE_ANCESTRY",
                        "execution_authorized": False,
                        "production_decision_authorized": False,
                    }
                    if "engine_evidence_ids" in signals:
                        apex_lineage = apex.resolve_engine_evidence_lineage(
                            signals["engine_evidence_ids"],
                            as_of=payload.get("observed_at"),
                        )
                        apex_lineage["claimed_lineage_present"] = claimed_lineage is not None
                        # Only APEX-verified roots may drive ECHO on the network path.
                        # Caller-provided lineage labels are audit-only and never
                        # become evidence-independence input.
                        signals["engine_evidence_lineage"] = apex_lineage["engine_evidence_lineage"]
                    payload["signals"] = signals
                    psi_state = None
                    try:
                        psi_state = possibility.snapshot(payload.get("asset", ""))
                    except Exception as ex:
                        port.journal.log("WARN", f"PANTHEON Psi adapter: {type(ex).__name__}: {ex}")
                    payload["subsystem_outputs"] = subsystem_context(
                        parallax.snapshot(limit=12),
                        dreamstate.snapshot(limit=20),
                        psi_snapshot=psi_state,
                        existing=existing_outputs,
                    )
                    # Reserved, server-owned provenance slot. Always overwrite caller data.
                    payload["subsystem_outputs"]["apex_lineage"] = apex_lineage
                    result = pantheon.record_observation(payload)
                    result["apex_lineage_bridge"] = apex_lineage
                    bridge = {"attempted": 0, "accepted": [], "errors": []}
                    try:
                        analysis = result.get("analysis") if isinstance(result, dict) else {}
                        exports = analysis.get("exports") if isinstance(analysis, dict) else {}
                        candidates = exports.get("sibyl_evidence") if isinstance(exports, dict) else []
                        if not isinstance(candidates, list):
                            raise ValueError("PANTHEON sibyl_evidence export must be a list")
                        for candidate in candidates:
                            bridge["attempted"] += 1
                            try:
                                saved = sibyl.record_pantheon_export(candidate)
                                bridge["accepted"].append(saved["evidence_id"])
                            except Exception as ex:
                                detail = f"{type(ex).__name__}: {ex}"[:800]
                                bridge["errors"].append(detail)
                                port.journal.log("WARN", f"PANTHEON→SIBYL bridge: {detail}")
                    except Exception as ex:
                        detail = f"{type(ex).__name__}: {ex}"[:800]
                        bridge["errors"].append(detail)
                        port.journal.log("WARN", f"PANTHEON→SIBYL bridge: {detail}")
                    result["sibyl_bridge"] = bridge
                    return self._json(200, result)
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/admin/parallax/decision":
                try:
                    payload = dict(body)
                    # Do not inject a fresh Psi snapshot into a decision after the
                    # caller's observed_at. Any Psi vote must be captured causally
                    # at that decision instant and supplied explicitly.
                    if not payload.get("source_commit"):
                        provenance = local_code_provenance()
                        if not provenance.get("candidate_revision_eligible") or not provenance.get("commit"):
                            raise ValueError("exact clean ICARUS code provenance is required when source_commit is omitted")
                        payload["source_commit"] = provenance["commit"]
                    return self._json(200, parallax.record_decision(payload))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/admin/parallax/outcome":
                try:
                    result = parallax.record_outcome(body)
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
                try:
                    result["dreamstate_refresh"] = dreamstate.refresh().get("refresh", {})
                except Exception as ex:
                    port.journal.log("WARN", f"DREAMSTATE rescreen after PARALLAX outcome: {type(ex).__name__}: {ex}")
                    result["dreamstate_refresh"] = {
                        "status": "degraded",
                        "error": f"{type(ex).__name__}: {ex}",
                        "outcome_committed": True,
                    }
                return self._json(200, result)
            if p.path == "/admin/dreamstate/refresh":
                try:
                    return self._json(200, dreamstate.refresh(body.get("min_samples", 5)))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/admin/dreamstate/evaluate":
                try:
                    return self._json(200, dreamstate.evaluate(body.get("candidate_id"), body))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            if p.path == "/admin/dreamstate/retire":
                try:
                    return self._json(200, dreamstate.retire(body.get("candidate_id"), body.get("reason")))
                except (ValueError, TypeError) as ex:
                    return self._json(400, {"detail": str(ex)})
            asset = str(body.get("asset") or body.get("symbol") or "").upper()
            # Add is the one admin route whose subject is intentionally not already
            # running. Do not reject it through the generic runner lookup.
            adding_asset = p.path == "/admin/assets/add"
            targets = [] if adding_asset else (
                [self._runner(asset)] if asset and asset != "*" else list(port.runner_list())
            )
            if not adding_asset and asset and asset != "*" and targets == [None]:
                return self._json(404, {"detail": f"unknown asset {asset}"})
            try:
                if p.path == "/admin/research/studies":
                    return self._json(200, research.start(body))
                if p.path == "/admin/research/adaptation":
                    return self._json(200, research.configure_adaptation(body))
                if p.path == "/admin/research/source-watch":
                    return self._json(200, research.configure_source_watch(body))
                if p.path == "/admin/research/cancel":
                    return self._json(200, research.cancel(body.get("job")))
                if p.path == "/admin/research/proposals":
                    return self._json(200, research.propose_study(body))
                if p.path == "/admin/research/export":
                    candidate = research.export(body.get("proposal_id"))
                    return self._json(200, candidate)
                if p.path == "/admin/research/analysis":
                    return self._json(200, research.analysis.start(body))
                if p.path == "/admin/research/analysis/cancel":
                    if set(body) != {"id"}:
                        raise ValueError("analysis cancellation requires id only")
                    return self._json(200, research.analysis.journal.cancel(body["id"]))
                if p.path == "/admin/research/activate":
                    return self._json(200, research.activate(body))
                if p.path == "/admin/research/rollback":
                    return self._json(200, research.rollback(body))
                if p.path == "/admin/research/recover":
                    return self._json(200, research.recover(body))
                if p.path == "/admin/research/collect":
                    if not {"source"} <= set(body) or set(body) - {"source", "options"}:
                        raise ValueError("collection requires source and optional options")
                    return self._json(200, research.market_sources.collect(body["source"], body.get("options")))
                if p.path == "/admin/pause":
                    reason = _reason(body)
                    if not asset or asset == "*":
                        port.paused = True
                        port.journal.log("WARN", f"PAUSE ALL requested: {reason}")
                        results = _run_all_assets("pause_all", lambda r: r.set_paused(True))
                        return self._json(200, {
                            "ok": True, "note": "paused all - no new entries",
                            "paused": sorted(results), "global_pause_intent": True,
                        })
                    for r in targets:
                        r.set_paused(True)
                    port.journal.log("WARN", f"PAUSED {asset}: {reason}")
                    return self._json(200, {"ok": True, "note": f"paused {asset} - no new entries"})
                if p.path == "/admin/resume":
                    if not asset or asset == "*":
                        port.paused = False
                        port.journal.log("INFO", "RESUME ALL requested")
                        results = _run_all_assets("resume_all", lambda r: r.set_paused(False))
                        return self._json(200, {
                            "ok": True, "note": "resumed all",
                            "resumed": sorted(results), "global_pause_intent": False,
                        })
                    for r in targets:
                        r.set_paused(False)
                    port.journal.log("INFO", f"RESUMED {asset}")
                    return self._json(200, {"ok": True, "note": f"resumed {asset}"})
                if p.path == "/admin/flatten":
                    if not body.get("confirm"):
                        return self._json(400, {"detail": "pass {\"confirm\": true}"})
                    reason = _reason(body, "dashboard")
                    if not asset or asset == "*":
                        closed = _run_all_assets("flatten_all", lambda r: r.flatten(reason))
                    else:
                        closed = {r.symbol: r.flatten(reason) for r in targets}
                    return self._json(200, {"ok": True, "closed": closed, "note": f"flattened {sum(closed.values())} position(s)"})
                if p.path == "/admin/market-data/mbo-snapshot":
                    if len(targets) != 1 or targets[0] is None:
                        raise ValueError("MBO snapshot requires exactly one running asset")
                    r = targets[0]
                    if not hasattr(r.feed, "mbo_snapshot"):
                        return self._json(409, {"error": f"{type(r.feed).__name__} does not expose MBO snapshots"})
                    timeout = max(0.1, min(30.0, float(body.get("timeout", 5.0))))
                    try:
                        rows = r.feed.mbo_snapshot(r.spec.ticker, timeout=timeout)
                    except TimeoutError as ex:
                        port.journal.log("WARN", f"market-data MBO snapshot {r.symbol}: {ex}")
                        return self._json(504, {"error": str(ex)})
                    except ValueError as ex:
                        return self._json(400, {"error": str(ex)})
                    except Exception as ex:
                        port.journal.log("WARN", f"market-data MBO snapshot {r.symbol}: {type(ex).__name__}: {ex}")
                        return self._json(502, {"error": f"{type(ex).__name__}: {ex}"})
                    return self._json(200, {"asset": r.symbol, "provider": type(r.feed).__name__.lower(),
                                            "schema": "mbo", "snapshot": rows})
                if p.path in ("/admin/inputs", "/admin/inputs/reset", "/admin/preset", "/admin/rewarm"):
                    from .runtime import resolve_inputs as _resolve
                    vals = body.get("values", {}) if p.path == "/admin/inputs" else None
                    if vals is not None and not isinstance(vals, dict):
                        raise ValueError("values must be an object")
                    chart = validate_chart_config(body.get("chart")) if p.path == "/admin/inputs" else {}
                    kwargs = {}
                    if p.path == "/admin/preset":
                        name = body.get("preset") or None
                        if name and not os.path.exists(preset_path(port.base_dir, str(name))):
                            return self._json(404, {"detail": f"preset {name} not found"})
                        kwargs["preset"] = name
                    reset = p.path == "/admin/inputs/reset"
                    with ExitStack() as locks:
                        # Hold every target from preflight through replay: no fill
                        # may race between acceptance and a later worker thread.
                        for r in sorted(targets, key=lambda r: r.symbol):
                            locks.enter_context(r.lock)
                            r.ensure_configurable()
                        # Preflight the entire batch before the first asset is persisted/replayed.
                        for r in targets:
                            sp = replace(r.cfg.base_spec or r.spec)
                            sp.preset = r.spec.preset
                            name = port.preset_for(r)
                            if "preset" in kwargs:
                                sp.preset = kwargs["preset"]
                                name = kwargs["preset"] or port.preset
                            inp, meta, _ = _resolve(sp, port.base_dir, port.profile, name, vals,
                                                   skip_asset_overrides=reset)
                            sp = apply_spec_meta(sp, meta)
                            sp = apply_chart_config(sp, chart)
                            r.ensure_cached_timeframes(inp)
                            r.ensure_cached_chart_timeframe(sp.chart_tf)
                        equity_epoch_before = port.equity_epoch
                        snapshots = {}
                        for r in targets:
                            override_path = os.path.join(port.base_dir, f"inputs.{r.symbol}.json")
                            snapshots[r.symbol] = {
                                "runtime": r.configuration_snapshot(),
                                "override_path": override_path,
                                "override_bytes": (Path(override_path).read_bytes() if os.path.exists(override_path) else None),
                            }
                        applied = []
                        try:
                            for r in targets:
                                port.rewarm_asset(r.symbol, vals, bool(body.get("persist", True)) if vals is not None else False,
                                                  reset=reset, chart=chart, **kwargs)
                                applied.append(r)
                        except Exception as apply_ex:
                            port.equity_epoch = equity_epoch_before
                            rollback_errors = []
                            for r in reversed(applied):
                                snap = snapshots[r.symbol]
                                try:
                                    pth = snap["override_path"]
                                    raw_before = snap["override_bytes"]
                                    if raw_before is None:
                                        if os.path.exists(pth):
                                            os.remove(pth)
                                    else:
                                        tmp = pth + ".batch-rollback.tmp"
                                        Path(tmp).write_bytes(raw_before)
                                        os.replace(tmp, pth)
                                    r.restore_configuration_snapshot(snap["runtime"])
                                except Exception as rollback_ex:
                                    rollback_errors.append(f"{r.symbol}: {type(rollback_ex).__name__}: {rollback_ex}")
                            if rollback_errors:
                                raise RuntimeError(
                                    f"batch configuration failed ({type(apply_ex).__name__}: {apply_ex}); "
                                    f"rollback incomplete: {'; '.join(rollback_errors)}"
                                ) from apply_ex
                            raise
                        # One successful batch = one paper-engine epoch. All runners were rebuilt.
                        cutover = time.time()
                        for r in targets:
                            r.live_from_ts = int(cutover)
                            r.live_closed_start = len(r.em.closed)
                        port.equity_epoch = cutover
                    done = [r.symbol for r in targets]
                    return self._json(200, {"ok": True, "note": f"configuration applied and re-warmed {done}", "assets": done,
                                            "chart": chart or None})
                if p.path == "/admin/assets/add":
                    tok = str(body.get("symbol", "")).strip()
                    if not tok:
                        return self._json(400, {"detail": "symbol required"})
                    running = port.runner_list()
                    default_tf = str(body.get("tf") or (running[0].spec.chart_tf if running else "20"))
                    spec = parse_spec(tok, default_tf)
                    if body.get("tf") not in (None, "") and "@" not in tok:
                        spec = pin_config(spec, "timeframe")
                    spec = apply_chart_config(spec, {k: body[k] for k in ("chart_type", "fill_on", "security_source") if body.get(k) not in (None, "")}, pin=True)
                    if body.get("preset"):
                        name = str(body["preset"])
                        if not os.path.exists(preset_path(port.base_dir, name)):
                            return self._json(404, {"detail": f"preset {name} not found"})
                        spec.preset = name
                    r = port.add_asset(spec)
                    return self._json(200, {"ok": True, "note": f"{r.symbol} added ({spec.name}, {spec.chart_tf}m); warming up", "asset": r.symbol})
                if p.path == "/admin/assets/remove":
                    ok = port.remove_asset(str(body.get("symbol", "")))
                    return self._json(200 if ok else 404, {"ok": ok, "note": f"{body.get('symbol')} {'removed' if ok else 'not found'}"})
                if p.path == "/admin/backtest":
                    from .backtest import validate_backtest_params
                    r = self._runner(asset)
                    if not r:
                        return self._json(404, {"detail": f"unknown asset {asset}"})
                    if not r.warm:
                        return self._json(409, {"detail": f"{r.symbol} is still warming up"})
                    fields = ("preset", "fill_on", "chart_type", "timeframe", "security_source", "session",
                              "slippage_ticks", "commission", "capital", "leverage", "window_start", "window_end", "inputs")
                    params = validate_backtest_params({k: body[k] for k in fields if k in body})
                    params["asset"] = r.symbol
                    if "preset" in params and not os.path.exists(preset_path(port.base_dir, params["preset"])):
                        return self._json(404, {"detail": f"preset {params['preset']} not found"})
                    job_id = start_job(port, params)
                    return self._json(200, {"ok": True, "job": job_id, "note": f"backtest {r.symbol} started"})
                if p.path == "/admin/backtest/compare":
                    job = JOBS.get(str(body.get("job", "")))
                    if not job or job["status"] != "done":
                        return self._json(404, {"detail": "unknown or unfinished backtest job"})
                    text = str(body.get("csv", ""))
                    if not text.strip():
                        return self._json(400, {"detail": "csv text required"})
                    tv = read_tv_trades_text(text)
                    eng = engine_trades_from_rows(job["result"]["trades"])
                    rep_ = compare_lists(eng, tv, int(job["result"]["config"]["tf"]) * 60, int(body.get("tol", 1) or 1))
                    return self._json(200, {"ok": True, "report": rep_})
            except (ValueError, TypeError) as ex:
                return self._json(400, {"detail": str(ex)})
            except Exception as ex:
                port.journal.log("ERROR", f"admin {p.path}: {type(ex).__name__}: {ex}")
                return self._json(500, {"detail": f"{type(ex).__name__}: {ex}"})
            self._json(404, {"error": "not found"})

    class ResearchHTTPServer(ThreadingHTTPServer):
        def serve_forever(self, poll_interval=.5):
            background = bool(getattr(self, "background_workers_enabled", True))
            if background:
                research.start_background()
                autopilot.start_background()
                loop_intelligence_sync.start()
                brain_remote_sync.start()
                brain_research_sync.start()
                evolution_remote_sync.start()
                evidence_lab_sync.start()
                commissioning.start_background()
            try:
                return super().serve_forever(poll_interval)
            finally:
                if background:
                    autopilot.close()
                    evidence_lab_sync.close()
                    evolution_remote_sync.close()
                    brain_research_sync.close()
                    brain_remote_sync.close()
                    loop_intelligence_sync.close()
                    commissioning.close()
                    research.close()

        def server_close(self):
            autopilot.close()
            evidence_lab_sync.close()
            evolution_remote_sync.close()
            brain_research_sync.close()
            brain_remote_sync.close()
            loop_intelligence_sync.close()
            commissioning.close()
            research.close()
            return super().server_close()

    srv = ResearchHTTPServer(("127.0.0.1", http_port), H)
    srv.research = research
    srv.loop_intelligence_sync = loop_intelligence_sync
    srv.brain_remote_sync = brain_remote_sync
    srv.brain_research_sync = brain_research_sync
    srv.evolution_remote_sync = evolution_remote_sync
    srv.evidence_lab_sync = evidence_lab_sync
    srv.possibility = possibility
    srv.performance_proof = performance_proof
    srv.latency_telemetry = latency_telemetry
    srv.source_reliability = source_reliability
    srv.qualification_receipts = qualification_receipts
    srv.autopilot = autopilot
    srv.pantheon = pantheon
    srv.sibyl = sibyl
    srv.apex = apex
    srv.ascendancy_archive = ascendancy_archive
    srv.ascendancy_foundry = ascendancy_foundry
    srv.ascendancy_unknowns = ascendancy_unknowns
    srv.ascendancy_mechanisms = ascendancy_mechanisms
    srv.ascendancy_inventions = ascendancy_inventions
    srv.ascendancy_contribution = ascendancy_contribution
    srv.ascendancy_evaluator = ascendancy_evaluator
    srv.learning = learning
    srv.chronofold = chronofold
    srv.commissioning = commissioning
    srv.daemon_threads = True
    srv.background_workers_enabled = bool(start)
    if not start:
        return srv
    srv.serve_forever()
