"""Local research workspace shared by HTTP and offline tooling.

Provider workflows and paper activation have separate authenticated operations.
HTTP event ingest cannot approve, and a study cannot mutate the live portfolio.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
import re
import threading
import time
import uuid
from dataclasses import asdict

from .advisory import AdvisoryLedger, strict_json, canonical_hash, _iso, _now
from .backtest import freeze_replay_port, run_backtest
from .research import Policy, Windows, digest, run_search
from .code_provenance import local_code_provenance
from .runtime import validate_values

DEFAULT_SOURCES = {
    "cftc": ["publicreporting.cftc.gov", "www.cftc.gov"],
    "fred": ["fred.stlouisfed.org", "api.stlouisfed.org"],
    "bls": ["www.bls.gov", "api.bls.gov"], "bea": ["www.bea.gov", "apps.bea.gov"],
    "federal-reserve": ["www.federalreserve.gov"],
    "sec": ["www.sec.gov", "data.sec.gov"],
    "coinbase": ["api.exchange.coinbase.com"],
    "yahoo-dxy": ["query1.finance.yahoo.com"],
}


def _champion_input_grid(champion_inputs, current_inputs, *, chart_type=None, session=None,
                         current_chart_type=None, current_session=None):
    """Represent an exact champion input snapshot as a one point study grid."""
    if not isinstance(champion_inputs, dict) or not isinstance(current_inputs, dict):
        raise ValueError("champion input snapshot must be an object")
    if set(champion_inputs) != set(current_inputs):
        raise ValueError("champion input snapshot does not match the current Pine input schema")
    if (chart_type is not None and current_chart_type is not None
            and chart_type != current_chart_type):
        raise ValueError("champion chart context differs from current runtime context")
    if (session is not None and current_session is not None
            and session != current_session):
        raise ValueError("champion session context differs from current runtime context")
    validate_values(champion_inputs)
    grid = {name: [value] for name, value in champion_inputs.items()
            if value != current_inputs[name]}
    if not grid:
        raise ValueError("champion has no changed inputs to qualify")
    from .research import _grid
    _grid(grid)
    return grid


class ResearchWorkspace:
    def __init__(self, port):
        self.port = port
        self.root = Path(port.base_dir) / "research"
        self._ledger = None
        self._lock = threading.RLock()
        self._jobs = {}
        self._active = None
        self._stop = threading.Event()
        self._analysis = None
        self._activation = None
        self._market_sources = None
        self._market_context = None
        self._adaptation = None
        self._source_watch = None
        self._learning = None

    @property
    def source_watch(self):
        with self._lock:
            if self._source_watch is None:
                from .source_watch import SourceWatch
                self._source_watch = SourceWatch(self.market_sources)
            return self._source_watch

    def configure_source_watch(self, partial):
        status = self.source_watch.configure(partial)
        return self.source_watch.start() if status["config"]["enabled"] else self.source_watch.stop()

    @property
    def learning(self):
        with self._lock:
            if self._learning is None:
                from .learning_fabric import LearningFabric
                self._learning = LearningFabric(self.port.base_dir, port=self.port)
            return self._learning

    def configure_learning(self, partial):
        status = self.learning.configure(partial)
        return self.learning.start_background() if status["config"]["enabled"] else self.learning.stop()

    @property
    def adaptation(self):
        with self._lock:
            if self._adaptation is None:
                from .adaptation import AdaptationScheduler
                self._adaptation = AdaptationScheduler(self)
            return self._adaptation

    def configure_adaptation(self, partial):
        status = self.adaptation.configure(partial)
        if status["config"]["enabled"]:
            return self.adaptation.start()
        return self.adaptation.stop(cancel=True)

    def start_background(self):
        # Resume persisted research workers. Public SourceWatch defaults to bounded
        # automatic collection; an explicit saved disable remains respected.
        self.learning.start_background()
        if (self.root / "adaptation.json").exists() and self.adaptation.status()["config"]["enabled"]:
            self.adaptation.start()
        if self.source_watch.status()["config"]["enabled"]:
            self.source_watch.start()

    def close(self):
        if self._learning is not None:
            self._learning.close()
        if self._adaptation is not None:
            self._adaptation.stop(cancel=True)
        self._stop.set()
        if self._source_watch is not None:
            self._source_watch.stop()
        if self._analysis is not None:
            self._analysis.stop()

    @property
    def analysis(self):
        with self._lock:
            if self._analysis is None:
                from .orchestration import AnalysisService
                self._analysis = AnalysisService(self)
            return self._analysis

    @property
    def activation(self):
        with self._lock:
            if self._activation is None:
                from .activation import ActivationStore
                self._activation = ActivationStore(self.root / "activation")
            return self._activation

    @property
    def market_sources(self):
        with self._lock:
            if self._market_sources is None:
                from .market_sources import MarketSources
                self._market_sources = MarketSources(self.root, self.ledger)
            return self._market_sources

    @property
    def market_context(self):
        with self._lock:
            if self._market_context is None:
                from .research_context import MarketContextStore
                self._market_context = MarketContextStore()
            return self._market_context

    @property
    def ledger(self):
        with self._lock:
            if self._ledger is None:
                self.root.mkdir(exist_ok=True)
                path = Path(self.port.base_dir) / "research-sources.json"
                sources = strict_json(path.read_bytes()) if path.exists() else DEFAULT_SOURCES
                self._ledger = AdvisoryLedger(self.root / "advisory.sqlite3", allowed_sources=sources)
            return self._ledger

    def operator_status(self):
        """Read-only root-panel status that never instantiates lazy research services."""
        with self._lock:
            jobs = [
                {k: j.get(k) for k in ("id", "status", "asset", "started", "finished", "error")}
                for j in self._jobs.values()
            ]
            active = self._active
            initialized = {
                "ledger": self._ledger is not None,
                "analysis": self._analysis is not None,
                "activation": self._activation is not None,
                "market_sources": self._market_sources is not None,
                "adaptation": self._adaptation is not None,
                "source_watch": self._source_watch is not None,
                "learning": self._learning is not None,
            }
        assets = []
        for r in self.port.runner_list():
            with r.lock:
                assets.append({
                    "asset": r.symbol,
                    "warm": r.warm,
                    "cached_subbars": len(r.subbars),
                    "timeframe_minutes": r.chart_minutes,
                })
        return {
            "schema_version": "icarus-research-operator-status-v1",
            "status": "ready",
            "active_job": active,
            "jobs": jobs,
            "assets": assets,
            "initialized_services": initialized,
            "execution_authorized": False,
        }

    def status(self, *, nonblocking=False):
        with self._lock:
            jobs = [{k: j.get(k) for k in ("id", "status", "asset", "started", "finished", "error")}
                    for j in self._jobs.values()]
        assets = []
        for r in self.port.runner_list():
            if nonblocking:
                view = r.summary(nonblocking=True)
                assets.append({"asset": view["symbol"], "cached_subbars": view.get("cached_subbars"),
                               "warm": view["warm"], "timeframe_minutes": view["tf"],
                               "configuration_changes_require_flat": True,
                               **{key: view.get(key) for key in (
                                   "view_cached", "view_stale", "view_captured_at", "view_age", "rewarming")}})
                continue
            with r.lock:
                assets.append({"asset": r.symbol, "cached_subbars": len(r.subbars), "warm": r.warm,
                               "timeframe_minutes": r.chart_minutes,
                               "configuration_changes_require_flat": True})
        adaptation = self.adaptation.status(nonblocking=True) if nonblocking else self.adaptation.status()
        return {"mode": "qualified paper adaptation", "execution_authorized": False, "assets": assets,
                "ledger": self.ledger.status(nonblocking=nonblocking), "jobs": jobs,
                "analysis": self.analysis.status(nonblocking=nonblocking),
                "activation": self.activation.status(nonblocking=nonblocking),
                "adaptation": adaptation,
                "learning": self.learning.status(nonblocking=nonblocking),
                "capabilities": {"zapier_receiver_configured": bool(os.environ.get("ICARUS_INGEST_SECRET")),
                                 "zapier_connected": False, "sp_global_connected": False,
                                 "licensed_tick_feed_connected": False,
                                 "offline_tick_seconds_footprint": True,
                                 "zero_cost_study_only_incubation": True,
                                 "automatic_input_application": True,
                                 "automatic_application_requires_qualified_dual_review": True,
                                 "continuous_outcome_learning": True,
                                 "historical_replay_learning": True},
                "note": "Study-only incubation can run without paid review calls and can only preserve unreviewed candidates. API keys configure review clients; a configured client is not a verified connection."}

    def _save(self, job):
        directory = self.root / "studies"
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / (job["id"] + ".json")
        temp = path.with_suffix(".tmp")
        temp.write_text(json.dumps(job, sort_keys=True, indent=2, allow_nan=False), encoding="utf-8")
        os.replace(temp, path)

    def events(self, asset):
        if asset not in self.port.runners:
            raise ValueError("unknown running asset")
        as_of = _iso(_now())
        rows = self.ledger.events_as_of(asset, as_of)
        return {"asset": asset, "as_of": as_of, "events": rows[:32],
                "available_count": len(rows), "execution_authorized": False}

    def job(self, job_id):
        if not isinstance(job_id, str) or not re.fullmatch(r"[0-9a-f]{16}", job_id):
            raise ValueError("invalid study id")
        with self._lock:
            if job_id in self._jobs:
                return json.loads(json.dumps(self._jobs[job_id]))
        path = self.root / "studies" / (job_id + ".json")
        if not path.is_file():
            raise ValueError("unknown study")
        saved = json.loads(path.read_text(encoding="utf-8"))
        if saved["status"] == "running":
            saved["status"] = "interrupted"
            saved["error"] = "No worker for this saved study in the current process; partial evidence only."
        return saved

    def cancel(self, job_id):
        with self._lock:
            if self._active != job_id:
                raise ValueError("study is not running in this process")
            self._stop.set()
        return {"ok": True, "note": "Cancellation requested; the current replay will finish first."}

    def fingerprints(self, asset, through=None):
        frozen = freeze_replay_port(self.port, asset)
        src = frozen.runners[asset]
        if through is not None:
            src.subbars = tuple((b, m) for b, m in src.subbars if b.ts + m * 60 <= through)
            src.deep = {m: tuple((b, sub) for b, sub in rows if b.ts + sub * 60 <= through)
                        for m, rows in src.deep.items()}
        dataset_hash = digest({"subbars": [(asdict(b), m) for b, m in src.subbars],
                               "deep": {str(k): [(asdict(b), m) for b, m in rows] for k, rows in src.deep.items()}})
        baseline = {"spec": asdict(src.spec), "base_inputs": src.inputs_base.to_dict(),
                    "replay_config": asdict(src.cfg), "pts_scale": src.pts_scale, "mintick": src.mintick}
        return frozen, dataset_hash, digest(baseline), baseline

    def export(self, proposal_id):
        proposal = self.ledger.get_proposal(proposal_id)
        candidate = proposal["candidate"]
        validation = candidate.get("validation", {})
        job = self._qualified_job(validation.get("study_id"))
        base_validation = {k: v for k, v in validation.items() if k != "analysis"}
        if (base_validation != self._validation(job) or candidate["inputs"] != job["result"]["selected"]
                or candidate["asset"] != job["asset"]
                or candidate["baseline_hash"] != job["baseline_hash"]
                or candidate["dataset_hash"] != job["dataset_hash"]):
            raise ValueError("proposal does not match its qualified study")
        asset = candidate["asset"]
        if asset not in self.port.runners:
            raise ValueError("candidate asset is no longer running")
        if "analysis" in validation:
            workflow = self._validate_analysis(validation["analysis"])
            request = workflow["request"]["request"]
            expected = {"job": job["id"], "evidence_ids": candidate["evidence_ids"],
                        "rationale": candidate["rationale"], "apply": request.get("apply")}
            actual = {**request, "evidence_ids": sorted(request.get("evidence_ids", []))}
            if actual != expected or canonical_hash(self.analysis_context(expected)) != validation["analysis"]["context_hash"]:
                raise ValueError("specialist analysis is not bound to this exact study and evidence")
        _, dataset_hash, baseline_hash, _ = self.fingerprints(asset, job.get("data_cutoff"))
        artifact = self.ledger.export_candidate(proposal_id, baseline_hash, dataset_hash)
        return {**artifact, "research_qualified": True, "study_id": job["id"],
                "note": "Qualified for further paper evaluation; no configuration was applied."}

    def _qualified_job(self, job_id):
        job = self.job(job_id)
        result = job.get("result") or {}
        if (job["status"] != "complete" or result.get("status") != "complete"
                or result.get("research_qualified") is not True or not result.get("selected")):
            raise ValueError("a completed, qualified study is required")
        if result["manifest"]["dataset_hash"] != job["dataset_hash"] or result["manifest"]["baseline_hash"] != job["baseline_hash"]:
            raise ValueError("study fingerprint mismatch")
        return job

    @staticmethod
    def _validation(job):
        result = job["result"]
        validation = {"study_id": job["id"], "study_hash": result["study_hash"],
                      "result_hash": digest(result), "research_qualified": True,
                      "policy": result["manifest"]["policy"], "holdout": result["holdout"]}
        if job.get("promotion_source"):
            validation["promotion_source"] = job["promotion_source"]
        return validation

    def propose_study(self, body):
        if type(body) is not dict or set(body) != {"job", "evidence_ids", "rationale"}:
            raise ValueError("proposal requires job, evidence_ids and rationale only")
        job = self._qualified_job(body["job"])
        _, dataset_hash, baseline_hash, _ = self.fingerprints(job["asset"], job.get("data_cutoff"))
        if dataset_hash != job["dataset_hash"] or baseline_hash != job["baseline_hash"]:
            raise ValueError("current baseline or dataset differs from study")
        now = _now()
        return self.ledger.propose({"schema_version": 1, "asset": job["asset"],
            "inputs": job["result"]["selected"], "baseline_hash": baseline_hash,
            "dataset_hash": dataset_hash, "evidence_ids": body["evidence_ids"],
            "decision_at": _iso(now), "expires_at": _iso(now + 3600), "rationale": body["rationale"],
            "validation": self._validation(job)})

    def analysis_context(self, body):
        job = self._qualified_job(body.get("job"))
        _, dataset_hash, baseline_hash, _ = self.fingerprints(job["asset"], job.get("data_cutoff"))
        if (dataset_hash, baseline_hash) != (job["dataset_hash"], job["baseline_hash"]):
            raise ValueError("study source or baseline changed")
        ids = body.get("evidence_ids")
        if type(ids) is not list or not 1 <= len(ids) <= 32 or len(set(map(str, ids))) != len(ids):
            raise ValueError("analysis requires 1 to 32 unique current evidence IDs")
        events = {e["event_id"]: e for e in self.ledger.events_as_of(job["asset"], _iso(_now()))}
        if any(ident not in events for ident in ids):
            raise ValueError("analysis evidence is unavailable or stale")
        rationale = body.get("rationale")
        if type(rationale) is not str or not 1 <= len(rationale) <= 8000:
            raise ValueError("analysis rationale must be a bounded string")
        result = job["result"]
        stress = result.get("stress", {})
        selected_trial = next((trial for trial in result["trials"] if trial["inputs"] == result["selected"]), {})
        return {"asset": job["asset"], "selected": result["selected"],
                "baseline": job["baseline"], "validation": self._validation(job),
                "comparisons": {"baseline": result.get("baseline"),
                    "candidate_train": selected_trial.get("train"), "candidate_validation": selected_trial.get("validation"),
                    "paired_train_validation": selected_trial.get("paired_comparison"),
                    "holdout_comparison": result.get("holdout_comparison"),
                    "stress": {k: stress.get(k) for k in ("status", "costs", "baseline", "holdout", "holdout_comparison")},
                    "qualification_reasons": result.get("qualification_reasons"),
                    "selection": result.get("selection")},
                "evidence": [events[ident] for ident in sorted(ids)], "rationale": rationale,
                "requested_paper_activation": body.get("apply", False)}

    def _validate_analysis(self, bundle):
        from .orchestration import ROLES
        if type(bundle) is not dict or set(bundle) != {"context_hash", "roles", "workflow_id"}:
            raise ValueError("invalid analysis bundle")
        workflow = self.analysis.journal.get(bundle["workflow_id"])
        if workflow["request"]["context_hash"] != bundle["context_hash"]:
            raise ValueError("analysis context mismatch")
        stages = {s["stage"]: s for s in workflow["stages"]}
        if set(bundle["roles"]) != set(ROLES):
            raise ValueError("all independent specialist analyses are required")
        for role in ROLES:
            stage = stages.get(role)
            report = bundle["roles"][role]
            if not stage or stage["status"] != "complete" or stage["result"] != report or report.get("decision") != "recommend":
                raise ValueError("specialist analysis is incomplete or rejected")
        return workflow

    def propose_analysis(self, request, bundle):
        workflow = self._validate_analysis(bundle)
        context = self.analysis_context(request)
        if canonical_hash(context) != bundle["context_hash"] or workflow["request"]["request"] != request:
            raise ValueError("analysis evidence or request changed")
        # Build from the deterministic study, not caller-authored model claims.
        base = self.propose_study({k: request[k] for k in ("job", "evidence_ids", "rationale")})
        candidate = dict(base["candidate"])
        candidate.pop("evidence_hash", None)
        candidate["validation"] = {**candidate["validation"], "analysis": bundle}
        return self.ledger.propose(candidate)

    def activate(self, body):
        if type(body) is not dict or set(body) != {"proposal_id", "operation_id"}:
            raise ValueError("activation requires proposal_id and operation_id only")
        artifact = self.export(body["proposal_id"])
        if "analysis" not in artifact["candidate"].get("validation", {}):
            raise ValueError("paper activation requires the full specialist analysis workflow")
        version = self.activation.register(artifact)
        return self.activation.activate(version["version_id"], body["operation_id"], self._activation_boundary())

    def _activation_boundary(self):
        from .activation_runtime import ActivationRuntime
        def verify(artifact):
            current = self.export(artifact["candidate_hash"])
            if current != artifact:
                raise ValueError("activation artifact changed")
            return current
        def fingerprints(asset, candidate):
            job = self._qualified_job(candidate["validation"]["study_id"])
            return self.fingerprints(asset, job.get("data_cutoff"))
        return ActivationRuntime(self.port, verify, fingerprints).boundary

    def rollback(self, body):
        if type(body) is not dict or set(body) != {"asset", "operation_id"}:
            raise ValueError("rollback requires asset and operation_id only")
        return self.activation.rollback(body["asset"], body["operation_id"], self._activation_boundary())

    def recover(self, body):
        if type(body) is not dict or set(body) != {"asset"}:
            raise ValueError("recovery requires asset only")
        return self.activation.recover(body["asset"], self._activation_boundary())

    def start(self, body, *, promotion=None):
        if not {"asset", "grid", "windows"} <= set(body):
            raise ValueError("study requires asset, grid and windows")
        if set(body) - {"asset", "grid", "windows", "policy"}:
            raise ValueError("unknown study fields")
        asset = str(body.get("asset", "")).upper()
        if asset not in self.port.runners:
            raise ValueError("unknown asset")
        if not self.port.runners[asset].warm:
            raise ValueError("asset is still warming")
        windows = Windows(**body["windows"])
        policy = Policy(**body.get("policy", {}))
        grid = json.loads(json.dumps(body["grid"], allow_nan=False))
        # Fail malformed/oversized candidate lists before starting a thread.
        from .research import _grid
        _grid(grid)
        # Never hold the workspace lock while acquiring runner locks: activation
        # holds the store/runner locks and then reads this workspace's study.
        frozen, dataset_hash, baseline_hash, baseline = self.fingerprints(asset, windows.holdout_end)
        src = frozen.runners[asset]
        if not src.subbars:
            raise ValueError("asset has no cached bars")
        earliest = min(b.ts for b, _ in src.subbars)
        latest = max(b.ts + minutes * 60 for b, minutes in src.subbars)
        if windows.train_start < earliest or windows.holdout_end > latest:
            raise ValueError("study windows exceed the frozen cached data range")
        with self.port.runners[asset].lock:
            raw_state = self.port.runners[asset].state if isinstance(self.port.runners[asset].state, dict) else {}
            regime_score = raw_state.get("rate_regime")
            if isinstance(regime_score, bool) or not isinstance(regime_score, (int, float)):
                regime_score = None
            regime_context = {
                "label": str(raw_state.get("rate_regime_str") or "UNCLASSIFIED"),
                "regime_score": regime_score,
                "observed_market_ts": raw_state.get("ts"),
            }
        provenance = local_code_provenance()
        with self._lock:
            if self._active is not None:
                raise ValueError("one research study may run at a time")
            job_id = uuid.uuid4().hex[:16]
            job = {"id": job_id, "status": "running", "asset": asset, "started": time.time(),
                   "dataset_hash": dataset_hash, "baseline_hash": baseline_hash,
                   "data_cutoff": windows.holdout_end,
                   "source_repo": provenance["repository"],
                   "source_commit": provenance["commit"],
                   "source_revision_status": provenance["status"],
                   "source_revision_eligible": provenance["candidate_revision_eligible"],
                   "regime_context": regime_context,
                   "baseline": baseline, "result": None, "error": None}
            if promotion is not None:
                if type(promotion) is not dict or set(promotion) != {"promotion_source", "evidence_ids", "rationale"}:
                    raise ValueError("invalid internal champion promotion metadata")
                job.update(promotion)
            self._save(job)
            self._active, self._stop = job_id, threading.Event()
            self._jobs[job_id] = job
            if len(self._jobs) > 16:
                for old in list(self._jobs)[:-16]:
                    del self._jobs[old]

        def checkpoint(result):
            with self._lock:
                job["result"] = result
                self._save(job)

        def work():
            try:
                evaluate = lambda patch, start, end: run_backtest(frozen, asset, inputs=patch, fill_on="real",
                                                                 window_start=start, window_end=end)
                result = run_search(asset, grid, windows, evaluate, dataset_hash=dataset_hash,
                                    baseline_hash=baseline_hash, holdout_ledger=str(self.root / "holdouts.sqlite3"),
                                    policy=policy, checkpoint=checkpoint, cancelled=self._stop.is_set,
                                    stress_evaluate=lambda patch, start, end, **costs: run_backtest(
                                        frozen, asset, inputs=patch, fill_on="real", window_start=start, window_end=end, **costs))
                with self._lock:
                    job["result"], job["status"] = result, result["status"]
                    job["finished"] = time.time()
                    # Publish a complete terminal record in one atomic replacement.
                    # A reader must never observe terminal status without its finish time.
                    self._save(job)
            except Exception as ex:
                with self._lock:
                    job["status"], job["error"] = "error", f"{type(ex).__name__}: {ex}"
                    job["finished"] = time.time()
                    self._save(job)
            finally:
                with self._lock:
                    self._active = None
        threading.Thread(target=work, daemon=True, name=f"research-{job_id}").start()
        return {"ok": True, "job": job_id, "note": "Bounded research started on a frozen copy; inputs remain unchanged."}

    def start_champion_study(self, body, champion):
        """Re-test one exact shadow champion through the normal research gates."""
        if type(body) is not dict or set(body) != {"asset", "champion_id"}:
            raise ValueError("champion study requires asset and champion_id only")
        asset = str(body["asset"]).upper()
        if asset not in self.port.runners or not isinstance(champion, dict):
            raise ValueError("unknown asset or champion")
        if champion.get("asset") != asset or champion.get("id") != body["champion_id"]:
            raise ValueError("champion is stale or does not match the requested asset")
        runner = self.port.runners[asset]
        with runner.lock:
            if not runner.warm:
                raise ValueError("asset is still warming")
            current_inputs = runner.inputs.to_dict()
            current_chart_type = runner.spec.chart_type
            current_session = runner.spec.session
            champ_chart = champion.get("chart_type") or current_chart_type
            champ_session = champion.get("session") or current_session
            grid = _champion_input_grid(champion.get("inputs"), current_inputs,
                chart_type=champ_chart, session=champ_session,
                current_chart_type=current_chart_type, current_session=current_session)
            config = self.adaptation.status()["config"]
            minutes = runner.chart_minutes
            from .pine.timeframe import Aggregator
            agg = Aggregator(minutes, runner.cal.bucket_start, runner.cal.bucket_end)
            bars = []
            for bar, sub_minutes in runner.subbars:
                if runner.cal.intraday_open(bar.ts) and minutes % sub_minutes == 0:
                    bars.extend(agg.push(bar, sub_minutes))
            raw_state = runner.state if isinstance(runner.state, dict) else {}
            regime_score = raw_state.get("rate_regime")
            if (isinstance(regime_score, bool) or not isinstance(regime_score, (int, float))
                    or not math.isfinite(float(regime_score))):
                regime_score = None
            observed_market_ts = raw_state.get("ts")
            if type(observed_market_ts) not in (int, float) or not math.isfinite(float(observed_market_ts)):
                observed_market_ts = None
            live_regime = {"label": str(raw_state.get("rate_regime_str") or "UNCLASSIFIED"),
                           "score": regime_score, "observed_market_ts": observed_market_ts}
        train, validation, holdout = (config["train_bars"], config["validation_bars"], config["holdout_bars"])
        total = train + validation + holdout + 2
        if len(bars) < total:
            raise ValueError(f"champion qualification needs {total} closed chart bars; have {len(bars)}")
        bars = bars[-total:]
        cal = runner.cal
        windows = Windows(bars[0].ts, cal.bucket_end(bars[train - 1].ts, minutes),
                          bars[train + 1].ts, cal.bucket_end(bars[train + validation].ts, minutes),
                          bars[train + validation + 2].ts, cal.bucket_end(bars[-1].ts, minutes))
        if windows.holdout_start <= self.adaptation._watermark(self.root / "holdouts.sqlite3", asset):
            raise ValueError("champion qualification needs a fresh, unseen holdout interval")
        evidence = self.ledger.events_as_of(asset, _iso(_now()))
        if not evidence:
            raise ValueError("champion qualification requires fresh source evidence for this asset")
        request = {"asset": asset, "grid": grid, "windows": asdict(windows),
                   "policy": config["policy"]}
        promotion = {
            "promotion_source": {
                "kind": "tactical_autopilot_champion", "champion_id": champion["id"],
                "champion_tested_at": champion.get("tested_at"),
                "champion_regime": champion.get("regime_context", {"label": "UNKNOWN"}),
                "study_regime": live_regime,
            },
            "evidence_ids": [event["event_id"] for event in evidence[:config["max_evidence"]]],
            "rationale": f"Fresh bounded qualification of Tactical Autopilot champion {champion['id']}",
        }
        response = self.start(request, promotion=promotion)
        return {**response, "champion_id": champion["id"],
                "next_step": "await qualification, then specialist review and proposal; this does not activate inputs"}
