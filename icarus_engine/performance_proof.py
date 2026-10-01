"""Causal, append-only proof ledger for measured ICARUS adaptation performance.

This module can establish exact historical percentages only for a closed,
fully-settled sample whose forecast/outcome records are source-bound. It never
turns a historical 100% sample into a future guarantee and never grants
production or execution authority.
"""
from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

MIN_CLOSED_SAMPLE = 30
MIN_REGIME_SAMPLE = 12
MIN_REPLAY_SAMPLE = 10
_ALLOWED_FORECAST = {
    "candidate_id", "asset", "regime", "decision_at", "matures_at",
    "probability_success", "success_definition", "source_repo",
    "source_commit", "dataset_hash", "evidence_hash",
}
_ALLOWED_OUTCOME = {"forecast_id", "observed_at", "success", "realized_value", "outcome_hash", "source"}
_ALLOWED_REPLAY = {"subject", "source_commit", "input_hash", "first_output_hash", "second_output_hash", "observed_at"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as ex:
        raise ValueError(f"{name} must be an ISO-8601 timestamp") from ex
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _text(value: Any, name: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    value = value.strip()
    if len(value) > limit:
        raise ValueError(f"{name} exceeds {limit} characters")
    return value


def _sha(value: Any, name: str, length: int = 64) -> str:
    value = _text(value, name, length).lower()
    if len(value) != length or any(ch not in "0123456789abcdef" for ch in value):
        raise ValueError(f"{name} must be an exact {length}-character lowercase hex digest")
    return value


def _finite(value: Any, name: str, *, low: float | None = None, high: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    number = float(value)
    if low is not None and number < low:
        raise ValueError(f"{name} is below {low}")
    if high is not None and number > high:
        raise ValueError(f"{name} is above {high}")
    return number


def _semantic_hash(value: Mapping[str, Any]) -> str:
    raw = json.dumps(dict(value), sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class PerformanceProofStore:
    """Durable forecast/outcome/replay proof store.

    The ledger records research/shadow evidence only. Forecast identities are
    content-addressed. Outcomes are immutable and must occur after maturity.
    """

    def __init__(self, base_dir: str | Path):
        self.root = Path(base_dir) / "audit"
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "performance_proof.sqlite3"
        self._lock = threading.RLock()
        with self._connect() as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS forecasts (
                    forecast_id TEXT PRIMARY KEY,
                    candidate_id TEXT NOT NULL,
                    asset TEXT NOT NULL,
                    regime TEXT NOT NULL,
                    decision_at TEXT NOT NULL,
                    matures_at TEXT NOT NULL,
                    probability_success REAL NOT NULL CHECK(probability_success >= 0 AND probability_success <= 1),
                    success_definition TEXT NOT NULL,
                    source_repo TEXT NOT NULL,
                    source_commit TEXT NOT NULL,
                    dataset_hash TEXT NOT NULL,
                    evidence_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS outcomes (
                    forecast_id TEXT PRIMARY KEY REFERENCES forecasts(forecast_id),
                    observed_at TEXT NOT NULL,
                    success INTEGER NOT NULL CHECK(success IN (0,1)),
                    realized_value REAL,
                    outcome_hash TEXT NOT NULL,
                    source TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS replay_proofs (
                    proof_id TEXT PRIMARY KEY,
                    subject TEXT NOT NULL,
                    source_commit TEXT NOT NULL,
                    input_hash TEXT NOT NULL,
                    first_output_hash TEXT NOT NULL,
                    second_output_hash TEXT NOT NULL,
                    passed INTEGER NOT NULL CHECK(passed IN (0,1)),
                    observed_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS proof_forecast_scope
                    ON forecasts(asset, regime, candidate_id, matures_at);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.path), timeout=10)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        con.execute("PRAGMA journal_mode=WAL")
        return con

    def register_forecast(self, body: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(body, Mapping) or set(body) != _ALLOWED_FORECAST:
            raise ValueError("forecast requires exactly: " + ", ".join(sorted(_ALLOWED_FORECAST)))
        decision_at = _iso(body["decision_at"], "decision_at")
        matures_at = _iso(body["matures_at"], "matures_at")
        if _dt(matures_at) <= _dt(decision_at):
            raise ValueError("matures_at must be later than decision_at")
        if _dt(decision_at) > _now():
            raise ValueError("decision_at cannot be in the future")
        source_repo = _text(body["source_repo"], "source_repo", 180)
        if "/" not in source_repo:
            raise ValueError("source_repo must be owner/repository")
        semantic = {
            "candidate_id": _text(body["candidate_id"], "candidate_id", 180),
            "asset": _text(body["asset"], "asset", 32).upper(),
            "regime": _text(body["regime"], "regime", 120),
            "decision_at": decision_at,
            "matures_at": matures_at,
            "probability_success": _finite(body["probability_success"], "probability_success", low=0.0, high=1.0),
            "success_definition": _text(body["success_definition"], "success_definition", 500),
            "source_repo": source_repo,
            "source_commit": _sha(body["source_commit"], "source_commit", 40),
            "dataset_hash": _sha(body["dataset_hash"], "dataset_hash"),
            "evidence_hash": _sha(body["evidence_hash"], "evidence_hash"),
        }
        forecast_id = _semantic_hash(semantic)
        created = _now().isoformat().replace("+00:00", "Z")
        values = (forecast_id, semantic["candidate_id"], semantic["asset"], semantic["regime"],
                  decision_at, matures_at, semantic["probability_success"], semantic["success_definition"],
                  source_repo, semantic["source_commit"], semantic["dataset_hash"], semantic["evidence_hash"], created)
        with self._lock, self._connect() as con:
            prior = con.execute("SELECT * FROM forecasts WHERE forecast_id=?", (forecast_id,)).fetchone()
            if prior is None:
                con.execute(
                    "INSERT INTO forecasts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    values,
                )
                idempotent = False
            else:
                idempotent = True
        return {
            "ok": True,
            "forecast_id": forecast_id,
            "idempotent": idempotent,
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    def record_outcome(self, body: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(body, Mapping) or set(body) != _ALLOWED_OUTCOME:
            raise ValueError("outcome requires exactly: " + ", ".join(sorted(_ALLOWED_OUTCOME)))
        forecast_id = _sha(body["forecast_id"], "forecast_id")
        observed_at = _iso(body["observed_at"], "observed_at")
        if _dt(observed_at) > _now():
            raise ValueError("observed_at cannot be in the future")
        if type(body["success"]) is not bool:
            raise ValueError("success must be Boolean")
        realized = body["realized_value"]
        if realized is not None:
            realized = _finite(realized, "realized_value")
        outcome_hash = _sha(body["outcome_hash"], "outcome_hash")
        source = _text(body["source"], "source", 240)
        created = _now().isoformat().replace("+00:00", "Z")
        with self._lock, self._connect() as con:
            forecast = con.execute("SELECT * FROM forecasts WHERE forecast_id=?", (forecast_id,)).fetchone()
            if forecast is None:
                raise ValueError("unknown forecast_id")
            if _dt(observed_at) < _dt(forecast["matures_at"]):
                raise ValueError("outcome cannot be recorded before forecast maturity")
            prior = con.execute("SELECT * FROM outcomes WHERE forecast_id=?", (forecast_id,)).fetchone()
            semantic = (observed_at, 1 if body["success"] else 0, realized, outcome_hash, source)
            if prior is not None:
                existing = (prior["observed_at"], prior["success"], prior["realized_value"], prior["outcome_hash"], prior["source"])
                if existing != semantic:
                    raise ValueError("forecast outcome is immutable and conflicts with the stored outcome")
                idempotent = True
            else:
                con.execute("INSERT INTO outcomes VALUES (?,?,?,?,?,?,?)",
                            (forecast_id, observed_at, semantic[1], realized, outcome_hash, source, created))
                idempotent = False
        return {
            "ok": True,
            "forecast_id": forecast_id,
            "idempotent": idempotent,
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    def record_replay(self, body: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(body, Mapping) or set(body) != _ALLOWED_REPLAY:
            raise ValueError("replay proof requires exactly: " + ", ".join(sorted(_ALLOWED_REPLAY)))
        semantic = {
            "subject": _text(body["subject"], "subject", 240),
            "source_commit": _sha(body["source_commit"], "source_commit", 40),
            "input_hash": _sha(body["input_hash"], "input_hash"),
            "first_output_hash": _sha(body["first_output_hash"], "first_output_hash"),
            "second_output_hash": _sha(body["second_output_hash"], "second_output_hash"),
            "observed_at": _iso(body["observed_at"], "observed_at"),
        }
        if _dt(semantic["observed_at"]) > _now():
            raise ValueError("observed_at cannot be in the future")
        proof_id = _semantic_hash(semantic)
        passed = semantic["first_output_hash"] == semantic["second_output_hash"]
        created = _now().isoformat().replace("+00:00", "Z")
        with self._lock, self._connect() as con:
            prior = con.execute("SELECT proof_id FROM replay_proofs WHERE proof_id=?", (proof_id,)).fetchone()
            if prior is None:
                con.execute("INSERT INTO replay_proofs VALUES (?,?,?,?,?,?,?,?,?)",
                            (proof_id, semantic["subject"], semantic["source_commit"], semantic["input_hash"],
                             semantic["first_output_hash"], semantic["second_output_hash"], 1 if passed else 0,
                             semantic["observed_at"], created))
                idempotent = False
            else:
                idempotent = True
        return {
            "ok": True,
            "proof_id": proof_id,
            "passed": passed,
            "idempotent": idempotent,
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    @staticmethod
    def _calibration(rows: list[Mapping[str, Any]]) -> tuple[float | None, list[dict[str, Any]]]:
        if not rows:
            return None, []
        bins: list[list[Mapping[str, Any]]] = [[] for _ in range(10)]
        for row in rows:
            idx = min(9, int(float(row["probability_success"]) * 10.0))
            bins[idx].append(row)
        weighted = 0.0
        out = []
        for idx, group in enumerate(bins):
            if not group:
                continue
            mean_p = sum(float(x["probability_success"]) for x in group) / len(group)
            mean_y = sum(int(x["success"]) for x in group) / len(group)
            gap = abs(mean_p - mean_y)
            weighted += gap * len(group) / len(rows)
            out.append({"bin": idx, "n": len(group), "mean_probability": mean_p, "observed_rate": mean_y, "absolute_gap": gap})
        return weighted, out

    def snapshot(self, *, as_of: str | None = None) -> dict[str, Any]:
        cutoff = _iso(as_of, "as_of") if as_of is not None else _now().isoformat().replace("+00:00", "Z")
        with self._lock, self._connect() as con:
            matured = [dict(x) for x in con.execute(
                "SELECT f.*, o.observed_at, o.success, o.realized_value, o.outcome_hash, o.source "
                "FROM forecasts f LEFT JOIN outcomes o ON o.forecast_id=f.forecast_id "
                "WHERE f.matures_at <= ? ORDER BY f.matures_at, f.forecast_id", (cutoff,)
            ).fetchall()]
            pending = con.execute("SELECT COUNT(*) FROM forecasts WHERE matures_at > ?", (cutoff,)).fetchone()[0]
            replays = [dict(x) for x in con.execute("SELECT * FROM replay_proofs ORDER BY observed_at, proof_id").fetchall()]

        settled = [x for x in matured if x["observed_at"] is not None]
        successes = sum(int(x["success"]) for x in settled)
        outcome_coverage = (len(settled) / len(matured)) if matured else None
        success_rate = (successes / len(settled)) if settled else None
        brier = (
            sum((float(x["probability_success"]) - int(x["success"])) ** 2 for x in settled) / len(settled)
            if settled else None
        )
        ece, calibration = self._calibration(settled)
        scope_keys = {
            (
                row["asset"], row["regime"], row["success_definition"],
                int((_dt(row["matures_at"]) - _dt(row["decision_at"])).total_seconds()),
            )
            for row in matured
        }
        coherent_scope = len(scope_keys) == 1
        closed = len(matured) >= MIN_CLOSED_SAMPLE and len(settled) == len(matured) and coherent_scope
        historical_100 = bool(closed and successes == len(settled))

        groups: dict[tuple[str, str, str, str, int], dict[str, Any]] = {}
        for row in matured:
            horizon_seconds = int((_dt(row["matures_at"]) - _dt(row["decision_at"])).total_seconds())
            key = (row["asset"], row["regime"], row["candidate_id"], row["success_definition"], horizon_seconds)
            group = groups.setdefault(key, {"matured": 0, "settled": 0, "successes": 0, "brier_sum": 0.0})
            group["matured"] += 1
            if row["observed_at"] is not None:
                group["settled"] += 1
                group["successes"] += int(row["success"])
                group["brier_sum"] += (float(row["probability_success"]) - int(row["success"])) ** 2

        candidates = []
        for (asset, regime, candidate_id, success_definition, horizon_seconds), g in groups.items():
            rate = g["successes"] / g["settled"] if g["settled"] else None
            brier_g = g["brier_sum"] / g["settled"] if g["settled"] else None
            complete = g["matured"] >= MIN_REGIME_SAMPLE and g["settled"] == g["matured"]
            candidates.append({
                "asset": asset, "regime": regime, "candidate_id": candidate_id,
                "success_definition": success_definition, "horizon_seconds": horizon_seconds,
                "matured": g["matured"], "settled": g["settled"], "successes": g["successes"],
                "outcome_coverage": (g["settled"] / g["matured"]) if g["matured"] else None,
                "success_rate": rate, "brier_score": brier_g,
                "closed_regime_sample": complete,
            })

        champions = []
        scopes = sorted({(x["asset"], x["regime"], x["success_definition"], x["horizon_seconds"]) for x in candidates})
        for asset, regime, success_definition, horizon_seconds in scopes:
            eligible = [x for x in candidates if x["asset"] == asset and x["regime"] == regime and x["success_definition"] == success_definition and x["horizon_seconds"] == horizon_seconds and x["closed_regime_sample"]]
            eligible.sort(key=lambda x: (-(x["success_rate"] or 0.0), x["brier_score"] if x["brier_score"] is not None else 2.0, -x["settled"], x["candidate_id"]))
            champions.append({
                "asset": asset,
                "regime": regime,
                "success_definition": success_definition,
                "horizon_seconds": horizon_seconds,
                "shadow_champion": eligible[0]["candidate_id"] if eligible else None,
                "selection_mode": "EMPIRICAL_SHADOW_ONLY",
                "eligible_candidates": [x["candidate_id"] for x in eligible],
            })

        replay_passed = sum(int(x["passed"]) for x in replays)
        replay_rate = (replay_passed / len(replays)) if replays else None
        replay_100 = len(replays) >= MIN_REPLAY_SAMPLE and replay_passed == len(replays)

        return {
            "schema_version": "icarus-performance-proof-v1",
            "as_of": cutoff,
            "authority": {
                "research_authorized": True,
                "shadow_selection_authorized": True,
                "production_decision_authorized": False,
                "execution_authorized": False,
            },
            "metrics": {
                "matured_forecasts": len(matured),
                "settled_forecasts": len(settled),
                "pending_forecasts": int(pending),
                "successes": successes,
                "outcome_coverage": outcome_coverage,
                "success_rate": success_rate,
                "brier_score": brier,
                "expected_calibration_error": ece,
            },
            "closed_sample": {
                "minimum_required": MIN_CLOSED_SAMPLE,
                "complete": closed,
                "scope_coherent": coherent_scope,
                "scope_count": len(scope_keys),
                "historical_100_percent_established": historical_100,
                "claim": (
                    f"100% observed success established for this closed, fully-settled {len(settled)}-forecast sample."
                    if historical_100
                    else "100% observed success is not established for a closed qualifying sample."
                ),
                "future_guarantee": False,
                "generalization_claim": False,
            },
            "replay": {
                "proof_count": len(replays),
                "passed": replay_passed,
                "determinism_rate": replay_rate,
                "minimum_required": MIN_REPLAY_SAMPLE,
                "historical_100_percent_established": replay_100,
            },
            "calibration": calibration,
            "candidate_statistics": candidates,
            "regime_champions": champions,
            "execution_authorized": False,
            "production_decision_authorized": False,
            "rule": "A 100% value may be displayed only for the exact closed sample that proves it; it is never extrapolated into guaranteed future market success.",
        }
