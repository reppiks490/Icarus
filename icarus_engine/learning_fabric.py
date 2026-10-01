"""Continuous research-learning fabric for ICARUS.

The fabric joins historical replay, live prediction maturity, native research
outcomes, and empirical calibration without granting production or execution
authority.  It is deliberately an evidence/learning plane, not a trading loop.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import os
from pathlib import Path
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

from .champion_challenger import wilson_interval
from .trainers.integrity import inspect_ohlc
from .trainers.run import train_file, train_xgb_file


_SCHEMA = "icarus-learning-fabric-v1"
_DEFAULT_CONFIG = {
    "enabled": True,
    "cycle_seconds": 60,
    "history_scan_seconds": 3600,
    "max_backfills_per_cycle": 1,
    "auto_train_slots": ["logit"],
    "history_roots": ["history", "history/drop", "research/imports"],
    "harvest_native": True,
    "settle_live_prices": True,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_time(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a timestamp string")
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as ex:
        raise ValueError(f"{field} must be ISO-8601") from ex
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone")
    return dt.astimezone(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _finite(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be numeric")
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"{field} must be finite")
    return out


def _probability(value: Any, field: str = "probability") -> float:
    out = _finite(value, field)
    if not 0.0 <= out <= 1.0:
        raise ValueError(f"{field} must be in [0,1]")
    return out


def _text(value: Any, field: str, limit: int = 256) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} is required")
    out = value.strip()
    if len(out) > limit:
        raise ValueError(f"{field} exceeds {limit} characters")
    return out


def _git_sha(value: Any) -> str:
    out = _text(value, "source_commit", 40).lower()
    if len(out) != 40 or any(ch not in "0123456789abcdef" for ch in out):
        raise ValueError("source_commit must be an exact 40-character Git SHA")
    return out


def _json(value: Any, field: str, *, max_bytes: int = 262144) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as ex:
        raise ValueError(f"{field} must be finite JSON") from ex
    if len(raw.encode("utf-8")) > max_bytes:
        raise ValueError(f"{field} exceeds {max_bytes} bytes")
    return raw


def _sha(value: Any) -> str:
    return hashlib.sha256(_json(value, "semantic").encode("utf-8")).hexdigest()


def _authority() -> dict[str, bool]:
    return {
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


class LearningFabric:
    """Durable cross-subsystem outcome and calibration fabric."""

    def __init__(self, base_dir: str | os.PathLike[str], *, port: Any | None = None):
        self.base_dir = Path(base_dir).resolve()
        self.root = self.base_dir / "research"
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "learning.sqlite3"
        self.config_path = self.root / "learning.json"
        self.port = port
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._native: dict[str, Any] = {}
        self._last_history_scan = 0.0
        self._conn = sqlite3.connect(self.path, timeout=30.0, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._init_schema()
        self._config = self._load_config()

    def _init_schema(self) -> None:
        with self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS predictions (
                    prediction_id TEXT PRIMARY KEY,
                    producer TEXT NOT NULL,
                    asset TEXT NOT NULL,
                    target TEXT NOT NULL,
                    prediction_json TEXT NOT NULL,
                    probability REAL NOT NULL,
                    probabilities_json TEXT NOT NULL,
                    reference_value REAL,
                    emitted_at TEXT NOT NULL,
                    emitted_ts REAL NOT NULL,
                    resolves_at TEXT NOT NULL,
                    resolves_ts REAL NOT NULL,
                    horizon_seconds INTEGER NOT NULL,
                    regime TEXT NOT NULL,
                    source_commit TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    semantic_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_learning_prediction_maturity
                    ON predictions(asset, resolves_ts);
                CREATE INDEX IF NOT EXISTS idx_learning_prediction_scope
                    ON predictions(producer, asset, regime, horizon_seconds, target);

                CREATE TABLE IF NOT EXISTS outcomes (
                    prediction_id TEXT PRIMARY KEY REFERENCES predictions(prediction_id),
                    observed_at TEXT NOT NULL,
                    observed_ts REAL NOT NULL,
                    actual_json TEXT NOT NULL,
                    success INTEGER,
                    brier REAL,
                    absolute_error REAL,
                    evidence_json TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    semantic_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS datasets (
                    dataset_id TEXT PRIMARY KEY,
                    raw_sha256 TEXT NOT NULL UNIQUE,
                    canonical_rows_sha256 TEXT,
                    path TEXT NOT NULL,
                    asset TEXT NOT NULL,
                    chart_type TEXT NOT NULL,
                    schema_name TEXT NOT NULL,
                    artifact_class TEXT NOT NULL,
                    rows INTEGER NOT NULL,
                    first_timestamp REAL,
                    last_timestamp REAL,
                    manifest_json TEXT NOT NULL,
                    discovered_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS dataset_paths (
                    dataset_id TEXT NOT NULL REFERENCES datasets(dataset_id),
                    path TEXT NOT NULL,
                    first_seen TEXT NOT NULL,
                    PRIMARY KEY(dataset_id, path)
                );

                CREATE TABLE IF NOT EXISTS training_runs (
                    run_id TEXT PRIMARY KEY,
                    dataset_id TEXT NOT NULL REFERENCES datasets(dataset_id),
                    slot TEXT NOT NULL,
                    report_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(dataset_id, slot)
                );

                CREATE TABLE IF NOT EXISTS experiences (
                    experience_id TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    source_record_id TEXT NOT NULL,
                    asset TEXT NOT NULL,
                    direction TEXT NOT NULL,
                    entry_at TEXT NOT NULL,
                    entry_ts REAL NOT NULL,
                    exit_at TEXT NOT NULL,
                    exit_ts REAL NOT NULL,
                    qty REAL NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL NOT NULL,
                    pnl REAL NOT NULL,
                    profitable INTEGER NOT NULL CHECK(profitable IN (0,1)),
                    metadata_json TEXT NOT NULL,
                    semantic_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    UNIQUE(source, source_record_id)
                );
                CREATE INDEX IF NOT EXISTS idx_learning_experience_scope
                    ON experiences(source, asset, exit_ts);

                CREATE TABLE IF NOT EXISTS cycles (
                    cycle_id TEXT PRIMARY KEY,
                    started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    summary_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS harvest_cursors (
                    adapter TEXT PRIMARY KEY,
                    cursor_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS service_health (
                    service TEXT PRIMARY KEY,
                    attempts INTEGER NOT NULL,
                    completed INTEGER NOT NULL,
                    ok_cycles INTEGER NOT NULL,
                    partial_cycles INTEGER NOT NULL,
                    failures INTEGER NOT NULL,
                    consecutive_failures INTEGER NOT NULL,
                    consecutive_partial INTEGER NOT NULL,
                    last_attempt_at TEXT,
                    last_completed_at TEXT,
                    last_ok_at TEXT,
                    last_partial_at TEXT,
                    last_failure_at TEXT,
                    last_error TEXT,
                    updated_at TEXT NOT NULL
                );
                INSERT OR IGNORE INTO service_health(
                    service,attempts,completed,ok_cycles,partial_cycles,failures,
                    consecutive_failures,consecutive_partial,last_attempt_at,
                    last_completed_at,last_ok_at,last_partial_at,last_failure_at,
                    last_error,updated_at
                ) VALUES('learning',0,0,0,0,0,0,0,NULL,NULL,NULL,NULL,NULL,NULL,'1970-01-01T00:00:00Z');
                """
            )

    def _load_config(self) -> dict[str, Any]:
        if not self.config_path.exists():
            return dict(_DEFAULT_CONFIG)
        try:
            body = json.loads(self.config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as ex:
            raise ValueError(f"learning config is unreadable: {ex}") from ex
        if not isinstance(body, dict):
            raise ValueError("learning config must be an object")
        return self._validated_config({**_DEFAULT_CONFIG, **body})

    @staticmethod
    def _validated_config(body: Mapping[str, Any]) -> dict[str, Any]:
        allowed = set(_DEFAULT_CONFIG)
        unknown = set(body) - allowed
        if unknown:
            raise ValueError("unsupported learning config fields: " + ", ".join(sorted(unknown)))
        out = dict(_DEFAULT_CONFIG)
        out.update(body)
        if type(out["enabled"]) is not bool:
            raise ValueError("enabled must be boolean")
        for name, lo, hi in (
            ("cycle_seconds", 5, 86400),
            ("history_scan_seconds", 30, 604800),
            ("max_backfills_per_cycle", 0, 32),
        ):
            value = out[name]
            if isinstance(value, bool) or not isinstance(value, int) or not lo <= value <= hi:
                raise ValueError(f"{name} must be an integer in [{lo},{hi}]")
        if type(out["harvest_native"]) is not bool or type(out["settle_live_prices"]) is not bool:
            raise ValueError("harvest_native and settle_live_prices must be boolean")
        slots = out["auto_train_slots"]
        if not isinstance(slots, list) or len(slots) > 4:
            raise ValueError("auto_train_slots must be a list with at most 4 items")
        allowed_slots = {"logit", "xgb", "regime"}
        clean_slots = []
        for raw in slots:
            slot = str(raw).strip().lower()
            if slot not in allowed_slots:
                raise ValueError(f"unsupported auto-train slot {slot}")
            if slot not in clean_slots:
                clean_slots.append(slot)
        roots = out["history_roots"]
        if not isinstance(roots, list) or not 1 <= len(roots) <= 8:
            raise ValueError("history_roots must contain 1-8 paths")
        clean_roots = []
        for raw in roots:
            value = str(raw or "").strip()
            if not value or Path(value).is_absolute() or ".." in Path(value).parts:
                raise ValueError("history_roots must be relative paths within the ICARUS root")
            clean_roots.append(value)
        out["auto_train_slots"] = clean_slots
        out["history_roots"] = clean_roots
        return out

    def _record_health_attempt(self) -> None:
        now = _utc_now()
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE service_health SET attempts=attempts+1,last_attempt_at=?,updated_at=? WHERE service='learning'",
                (now, now),
            )

    def _record_health_result(self, status: str) -> None:
        now = _utc_now()
        normalized = str(status or "").strip().lower()
        with self._lock, self._conn:
            if normalized == "ok":
                self._conn.execute(
                    """UPDATE service_health SET
                       completed=completed+1,ok_cycles=ok_cycles+1,
                       consecutive_failures=0,consecutive_partial=0,
                       last_completed_at=?,last_ok_at=?,last_error=NULL,updated_at=?
                       WHERE service='learning'""",
                    (now, now, now),
                )
            else:
                self._conn.execute(
                    """UPDATE service_health SET
                       completed=completed+1,partial_cycles=partial_cycles+1,
                       consecutive_failures=0,consecutive_partial=consecutive_partial+1,
                       last_completed_at=?,last_partial_at=?,updated_at=?
                       WHERE service='learning'""",
                    (now, now, now),
                )

    def _record_health_failure(self, ex: BaseException) -> None:
        now = _utc_now()
        error = f"{type(ex).__name__}: {ex}"[:1000]
        with self._lock, self._conn:
            self._conn.execute(
                """UPDATE service_health SET
                   failures=failures+1,consecutive_failures=consecutive_failures+1,
                   consecutive_partial=0,last_failure_at=?,last_error=?,updated_at=?
                   WHERE service='learning'""",
                (now, error, now),
            )

    def run_cycle(self) -> dict[str, Any]:
        """Run one observable learning cycle with durable service-health accounting."""
        self._record_health_attempt()
        try:
            result = self.tick()
        except BaseException as ex:
            self._record_health_failure(ex)
            raise
        self._record_health_result(str(result.get("status") or "partial"))
        return result

    def _backlog_state(self) -> dict[str, int]:
        pending_predictions = int(self._conn.execute(
            """SELECT COUNT(*) FROM predictions p
               WHERE NOT EXISTS (SELECT 1 FROM outcomes o WHERE o.prediction_id=p.prediction_id)"""
        ).fetchone()[0])
        configured_slots = list(self._config.get("auto_train_slots") or [])
        untrained_ohlc = 0
        if configured_slots:
            rows = self._conn.execute(
                "SELECT dataset_id FROM datasets WHERE artifact_class='ohlc'"
            ).fetchall()
            for row in rows:
                did = row["dataset_id"]
                present = {
                    x["slot"] for x in self._conn.execute(
                        "SELECT slot FROM training_runs WHERE dataset_id=?", (did,)
                    ).fetchall()
                }
                if any(slot not in present for slot in configured_slots):
                    untrained_ohlc += 1
        unimported_trade_lists = int(self._conn.execute(
            """SELECT COUNT(*) FROM datasets d
               WHERE d.artifact_class='trade_list'
               AND NOT EXISTS (
                   SELECT 1 FROM training_runs t
                   WHERE t.dataset_id=d.dataset_id AND t.slot='trade_experience'
               )"""
        ).fetchone()[0])
        return {
            "pending_predictions": pending_predictions,
            "untrained_ohlc_datasets": untrained_ohlc,
            "unimported_trade_lists": unimported_trade_lists,
        }

    def health(self) -> dict[str, Any]:
        row = self._conn.execute(
            "SELECT * FROM service_health WHERE service='learning'"
        ).fetchone()
        if row is None:
            raise RuntimeError("learning service health row is missing")
        now = _parse_time(_utc_now(), "now")
        last_completed = row["last_completed_at"]
        stale_after = max(180, int(self._config["cycle_seconds"]) * 3)
        stale = False
        age_seconds = None
        if last_completed:
            age_seconds = max(0.0, (now - _parse_time(last_completed, "last_completed_at")).total_seconds())
            stale = bool(self._config["enabled"] and age_seconds > stale_after)
        attempts = int(row["attempts"])
        if stale:
            status = "STALE"
        elif int(row["consecutive_failures"]) > 0 or int(row["consecutive_partial"]) > 0:
            status = "DEGRADED"
        elif attempts == 0:
            status = "WARMING"
        else:
            status = "HEALTHY"
        return {
            "schema_version": "icarus-learning-health-v1",
            "status": status,
            "enabled": bool(self._config["enabled"]),
            "background_running": bool(self._thread and self._thread.is_alive()),
            "attempts": attempts,
            "completed": int(row["completed"]),
            "ok_cycles": int(row["ok_cycles"]),
            "partial_cycles": int(row["partial_cycles"]),
            "failures": int(row["failures"]),
            "consecutive_failures": int(row["consecutive_failures"]),
            "consecutive_partial": int(row["consecutive_partial"]),
            "last_attempt_at": row["last_attempt_at"],
            "last_completed_at": last_completed,
            "last_ok_at": row["last_ok_at"],
            "last_partial_at": row["last_partial_at"],
            "last_failure_at": row["last_failure_at"],
            "last_error": row["last_error"],
            "age_since_completion_seconds": age_seconds,
            "stale_after_seconds": stale_after,
            "stale": stale,
            "backlog": self._backlog_state(),
            **_authority(),
        }

    def configure(self, partial: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(partial, Mapping):
            raise ValueError("learning config patch must be an object")
        config = self._validated_config({**self._config, **dict(partial)})
        temp = self.config_path.with_suffix(".tmp")
        temp.write_text(json.dumps(config, sort_keys=True, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        os.replace(temp, self.config_path)
        self._config = config
        return self.status()

    def bind_native(self, **engines: Any) -> None:
        allowed = {"sibyl", "commissioning", "parallax", "dreamstate", "pantheon", "apex", "possibility", "chronofold", "performance_proof", "source_reliability"}
        unknown = set(engines) - allowed
        if unknown:
            raise ValueError("unsupported native learning adapters: " + ", ".join(sorted(unknown)))
        self._native.update({k: v for k, v in engines.items() if v is not None})

    @staticmethod
    def _normalize_prediction(body: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(body, Mapping):
            raise ValueError("prediction must be an object")
        producer = _text(body.get("producer"), "producer", 96).lower()
        asset = _text(body.get("asset"), "asset", 32).upper()
        target = _text(body.get("target"), "target", 32).lower()
        if target not in {"direction", "class", "numeric", "event"}:
            raise ValueError("target must be direction, class, numeric, or event")
        emitted = _parse_time(body.get("emitted_at"), "emitted_at")
        horizon = body.get("horizon_seconds")
        if isinstance(horizon, bool) or not isinstance(horizon, int) or not 1 <= horizon <= 31_536_000:
            raise ValueError("horizon_seconds must be an integer in [1,31536000]")
        resolves = emitted + timedelta(seconds=horizon)
        source_commit = _git_sha(body.get("source_commit"))
        regime = str(body.get("regime") or "unknown").strip().lower() or "unknown"
        if len(regime) > 128:
            raise ValueError("regime exceeds 128 characters")
        evidence = body.get("evidence_ids", [])
        if not isinstance(evidence, list) or len(evidence) > 128:
            raise ValueError("evidence_ids must be a list with at most 128 items")
        evidence = [str(x).strip() for x in evidence if str(x).strip()]
        if len(set(evidence)) != len(evidence):
            raise ValueError("evidence_ids must be unique")
        metadata = body.get("metadata", {})
        if not isinstance(metadata, Mapping):
            raise ValueError("metadata must be an object")
        metadata = dict(metadata)
        _json(metadata, "metadata")

        prediction = body.get("prediction")
        probs_raw = body.get("probabilities")
        probabilities: dict[str, float] = {}
        if target == "class":
            if not isinstance(probs_raw, Mapping) or len(probs_raw) < 2:
                raise ValueError("class predictions require probabilities")
            for key, value in probs_raw.items():
                label = _text(str(key), "class label", 64).lower()
                probabilities[label] = _probability(value, f"probabilities.{label}")
            total = sum(probabilities.values())
            if total <= 0:
                raise ValueError("class probabilities require positive mass")
            probabilities = {k: v / total for k, v in probabilities.items()}
            pred_text = _text(str(prediction), "prediction", 64).lower()
            if pred_text not in probabilities:
                raise ValueError("prediction must name a class in probabilities")
            probability = probabilities[pred_text]
            normalized_prediction: Any = pred_text
        elif target in {"direction", "event"}:
            probability = _probability(body.get("probability"))
            if target == "direction":
                pred_text = _text(str(prediction), "prediction", 16).lower()
                aliases = {"long": "up", "buy": "up", "short": "down", "sell": "down"}
                pred_text = aliases.get(pred_text, pred_text)
                if pred_text not in {"up", "down", "flat"}:
                    raise ValueError("direction prediction must be up, down, or flat")
                normalized_prediction = pred_text
            else:
                if type(prediction) is not bool:
                    raise ValueError("event prediction must be boolean")
                normalized_prediction = prediction
        else:
            probability = _probability(body.get("probability", 0.5))
            normalized_prediction = _finite(prediction, "prediction")

        reference = body.get("reference_value")
        reference_value = None if reference is None else _finite(reference, "reference_value")
        if target == "direction" and reference_value is None:
            raise ValueError("direction prediction requires reference_value")

        semantic = {
            "schema_version": "icarus-learning-prediction-v1",
            "producer": producer,
            "asset": asset,
            "target": target,
            "prediction": normalized_prediction,
            "probability": probability,
            "probabilities": probabilities,
            "reference_value": reference_value,
            "emitted_at": _iso(emitted),
            "resolves_at": _iso(resolves),
            "horizon_seconds": horizon,
            "regime": regime,
            "source_commit": source_commit,
            "evidence_ids": evidence,
            "metadata": metadata,
            **_authority(),
        }
        prediction_id = "learn-" + _sha(semantic)
        return {**semantic, "prediction_id": prediction_id}

    def record_prediction(self, body: Mapping[str, Any]) -> dict[str, Any]:
        pred = self._normalize_prediction(body)
        semantic = {k: v for k, v in pred.items() if k != "prediction_id"}
        raw = _json(semantic, "prediction")
        with self._lock, self._conn:
            cur = self._conn.execute(
                """INSERT OR IGNORE INTO predictions(
                   prediction_id,producer,asset,target,prediction_json,probability,
                   probabilities_json,reference_value,emitted_at,emitted_ts,resolves_at,
                   resolves_ts,horizon_seconds,regime,source_commit,evidence_json,
                   metadata_json,semantic_json,recorded_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    pred["prediction_id"], pred["producer"], pred["asset"], pred["target"],
                    _json(pred["prediction"], "prediction.value"), pred["probability"],
                    _json(pred["probabilities"], "probabilities"), pred["reference_value"],
                    pred["emitted_at"], _parse_time(pred["emitted_at"], "emitted_at").timestamp(),
                    pred["resolves_at"], _parse_time(pred["resolves_at"], "resolves_at").timestamp(),
                    pred["horizon_seconds"], pred["regime"], pred["source_commit"],
                    _json(pred["evidence_ids"], "evidence_ids"), _json(pred["metadata"], "metadata"),
                    raw, _utc_now(),
                ),
            )
        return {"ok": True, "idempotent": cur.rowcount == 0, "prediction": pred, **_authority()}

    def _prediction_row(self, prediction_id: str) -> tuple[sqlite3.Row, dict[str, Any]]:
        pid = _text(prediction_id, "prediction_id", 96)
        row = self._conn.execute("SELECT * FROM predictions WHERE prediction_id=?", (pid,)).fetchone()
        if row is None:
            raise ValueError("unknown prediction_id")
        semantic = json.loads(row["semantic_json"])
        return row, {**semantic, "prediction_id": pid}

    @staticmethod
    def _score(pred: Mapping[str, Any], actual: Any) -> tuple[bool | None, float | None, float | None]:
        target = pred["target"]
        if target == "direction":
            actual_value = _finite(actual, "actual_value")
            ref = float(pred["reference_value"])
            tolerance = float((pred.get("metadata") or {}).get("flat_tolerance", 0.0) or 0.0)
            actual_class = "flat" if abs(actual_value - ref) <= tolerance else ("up" if actual_value > ref else "down")
            success = actual_class == pred["prediction"]
            y = 1.0 if success else 0.0
            brier = (float(pred["probability"]) - y) ** 2
            return success, brier, abs(actual_value - ref)
        if target == "class":
            actual_class = _text(str(actual), "actual_value", 64).lower()
            probs = pred.get("probabilities") or {}
            if actual_class not in probs:
                raise ValueError("actual class is outside prediction classes")
            success = actual_class == pred["prediction"]
            brier = sum((float(prob) - (1.0 if label == actual_class else 0.0)) ** 2 for label, prob in probs.items()) / len(probs)
            return success, brier, None
        if target == "event":
            if type(actual) is not bool:
                raise ValueError("actual_value must be boolean for event predictions")
            success = bool(actual) == bool(pred["prediction"])
            y = 1.0 if actual else 0.0
            prob_true = float(pred["probability"]) if pred["prediction"] is True else 1.0 - float(pred["probability"])
            return success, (prob_true - y) ** 2, None
        actual_value = _finite(actual, "actual_value")
        predicted = float(pred["prediction"])
        return None, None, abs(predicted - actual_value)

    def record_outcome(self, body: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(body, Mapping):
            raise ValueError("outcome must be an object")
        row, pred = self._prediction_row(body.get("prediction_id"))
        observed = _parse_time(body.get("observed_at"), "observed_at")
        if observed.timestamp() + 1e-9 < float(row["resolves_ts"]):
            raise ValueError("outcome cannot precede prediction maturity")
        actual = body.get("actual_value")
        success, brier, absolute_error = self._score(pred, actual)
        evidence = body.get("evidence", [])
        if not isinstance(evidence, list) or len(evidence) > 128:
            raise ValueError("evidence must be a list with at most 128 items")
        evidence = [str(x).strip() for x in evidence if str(x).strip()]
        metadata = body.get("metadata", {})
        if not isinstance(metadata, Mapping):
            raise ValueError("metadata must be an object")
        semantic = {
            "prediction_id": pred["prediction_id"],
            "observed_at": _iso(observed),
            "actual_value": actual,
            "success": success,
            "brier": brier,
            "absolute_error": absolute_error,
            "evidence": evidence,
            "metadata": dict(metadata),
            **_authority(),
        }
        raw = _json(semantic, "outcome")
        with self._lock, self._conn:
            existing = self._conn.execute("SELECT semantic_json FROM outcomes WHERE prediction_id=?", (pred["prediction_id"],)).fetchone()
            if existing is not None:
                prior = json.loads(existing["semantic_json"])
                if prior == semantic:
                    return {"ok": True, "idempotent": True, "outcome": prior, **_authority()}
                raise ValueError("outcome is immutable for prediction_id")
            self._conn.execute(
                """INSERT INTO outcomes(prediction_id,observed_at,observed_ts,actual_json,
                   success,brier,absolute_error,evidence_json,metadata_json,semantic_json,recorded_at)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    pred["prediction_id"], semantic["observed_at"], observed.timestamp(),
                    _json(actual, "actual_value"), None if success is None else int(success),
                    brier, absolute_error, _json(evidence, "evidence"),
                    _json(dict(metadata), "metadata"), raw, _utc_now(),
                ),
            )
        return {"ok": True, "idempotent": False, "outcome": semantic, **_authority()}

    def outcome(self, prediction_id: str) -> dict[str, Any] | None:
        pid = _text(prediction_id, "prediction_id", 96)
        row = self._conn.execute("SELECT semantic_json FROM outcomes WHERE prediction_id=?", (pid,)).fetchone()
        return None if row is None else json.loads(row["semantic_json"])

    def observe_price(self, asset: str, observed_at: str, price: float, *, evidence: Sequence[str] | None = None) -> dict[str, Any]:
        symbol = _text(asset, "asset", 32).upper()
        observed = _parse_time(observed_at, "observed_at")
        px = _finite(price, "price")
        if px <= 0:
            raise ValueError("price must be positive")
        with self._lock:
            rows = self._conn.execute(
                """SELECT prediction_id FROM predictions
                   WHERE asset=? AND target IN ('direction','numeric') AND resolves_ts<=?
                   AND prediction_id NOT IN (SELECT prediction_id FROM outcomes)
                   ORDER BY resolves_ts,prediction_id""",
                (symbol, observed.timestamp()),
            ).fetchall()
        ids = []
        errors = {}
        for row in rows:
            pid = row["prediction_id"]
            try:
                self.record_outcome({
                    "prediction_id": pid,
                    "observed_at": _iso(observed),
                    "actual_value": px,
                    "evidence": list(evidence or []),
                    "metadata": {"settled_by": "observed_price"},
                })
                ids.append(pid)
            except Exception as ex:
                errors[pid] = f"{type(ex).__name__}: {ex}"[:500]
        return {"settled": len(ids), "prediction_ids": ids, "errors": errors, **_authority()}

    def record_experience(self, body: Mapping[str, Any]) -> dict[str, Any]:
        """Record one immutable realized trade experience.

        Experience is outcome memory, not a forecast and not evidence that a
        strategy will continue to perform. It can inform research but cannot
        authorize production or execution.
        """
        if not isinstance(body, Mapping):
            raise ValueError("experience must be an object")
        source = _text(body.get("source"), "source", 64).lower()
        source_record_id = _text(body.get("source_record_id"), "source_record_id", 256)
        asset = _text(body.get("asset"), "asset", 32).upper()
        direction = _text(body.get("direction"), "direction", 16).lower()
        if direction not in {"long", "short"}:
            raise ValueError("direction must be long or short")
        entry = _parse_time(body.get("entry_at"), "entry_at")
        exit_at = _parse_time(body.get("exit_at"), "exit_at")
        if exit_at < entry:
            raise ValueError("exit_at cannot precede entry_at")
        qty = _finite(body.get("qty"), "qty")
        entry_price = _finite(body.get("entry_price"), "entry_price")
        exit_price = _finite(body.get("exit_price"), "exit_price")
        pnl = _finite(body.get("pnl"), "pnl")
        if qty <= 0:
            raise ValueError("qty must be positive")
        if entry_price <= 0 or exit_price <= 0:
            raise ValueError("entry_price and exit_price must be positive")
        metadata = body.get("metadata", {})
        if not isinstance(metadata, Mapping):
            raise ValueError("metadata must be an object")
        semantic = {
            "schema_version": "icarus-learning-experience-v1",
            "source": source,
            "source_record_id": source_record_id,
            "asset": asset,
            "direction": direction,
            "entry_at": _iso(entry),
            "exit_at": _iso(exit_at),
            "qty": qty,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "pnl": pnl,
            "profitable": pnl > 0.0,
            "metadata": dict(metadata),
            **_authority(),
        }
        raw = _json(semantic, "experience")
        experience_id = "exp-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()
        with self._lock, self._conn:
            prior = self._conn.execute(
                "SELECT experience_id,semantic_json FROM experiences WHERE source=? AND source_record_id=?",
                (source, source_record_id),
            ).fetchone()
            if prior is not None:
                existing = json.loads(prior["semantic_json"])
                if existing == semantic:
                    return {
                        "ok": True, "idempotent": True,
                        "experience": {**existing, "experience_id": prior["experience_id"]},
                        **_authority(),
                    }
                raise ValueError("experience is immutable for source/source_record_id")
            self._conn.execute(
                """INSERT INTO experiences(
                   experience_id,source,source_record_id,asset,direction,entry_at,entry_ts,
                   exit_at,exit_ts,qty,entry_price,exit_price,pnl,profitable,metadata_json,
                   semantic_json,recorded_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    experience_id, source, source_record_id, asset, direction,
                    semantic["entry_at"], entry.timestamp(), semantic["exit_at"], exit_at.timestamp(),
                    qty, entry_price, exit_price, pnl, int(pnl > 0.0),
                    _json(dict(metadata), "experience metadata"), raw, _utc_now(),
                ),
            )
        return {
            "ok": True, "idempotent": False,
            "experience": {**semantic, "experience_id": experience_id},
            **_authority(),
        }

    def experience_summary(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT source,asset,direction,entry_at,exit_at,pnl FROM experiences "
            "ORDER BY source,asset,exit_ts,experience_id"
        ).fetchall()
        groups: dict[tuple[str, str], list[sqlite3.Row]] = {}
        for row in rows:
            groups.setdefault((row["source"], row["asset"]), []).append(row)
        out = []
        for (source, asset), group in sorted(groups.items()):
            pnls = [float(row["pnl"]) for row in group]
            wins = sum(1 for value in pnls if value > 0)
            losses = sum(1 for value in pnls if value < 0)
            breakeven = len(pnls) - wins - losses
            gross_profit = sum(value for value in pnls if value > 0)
            gross_loss = sum(value for value in pnls if value < 0)
            long_count = sum(1 for row in group if row["direction"] == "long")
            short_count = sum(1 for row in group if row["direction"] == "short")
            direction = "long" if long_count and not short_count else ("short" if short_count and not long_count else "mixed")
            out.append({
                "source": source,
                "asset": asset,
                "direction": direction,
                "long_count": long_count,
                "short_count": short_count,
                "count": len(pnls),
                "wins": wins,
                "losses": losses,
                "breakeven": breakeven,
                "win_rate": wins / len(pnls) if pnls else None,
                "net_pnl": sum(pnls),
                "average_pnl": sum(pnls) / len(pnls) if pnls else None,
                "gross_profit": gross_profit,
                "gross_loss": gross_loss,
                "profit_factor": (gross_profit / abs(gross_loss)) if gross_loss < 0 else None,
                "first_entry_at": min(row["entry_at"] for row in group),
                "last_exit_at": max(row["exit_at"] for row in group),
                "status": "MEASURED" if len(pnls) >= 30 else "EARLY",
                **_authority(),
            })
        return out

    def experience_state(self) -> dict[str, Any]:
        count = int(self._conn.execute("SELECT COUNT(*) FROM experiences").fetchone()[0])
        return {
            "schema_version": "icarus-learning-experience-state-v1",
            "count": count,
            "summary": self.experience_summary(),
            "rule": "Realized trade experience is descriptive outcome memory, not forecast calibration or a future-performance guarantee.",
            **_authority(),
        }

    def scorecards(self) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """SELECT p.*,o.success,o.brier,o.absolute_error
               FROM predictions p JOIN outcomes o ON o.prediction_id=p.prediction_id
               ORDER BY p.producer,p.asset,p.regime,p.horizon_seconds,p.target"""
        ).fetchall()
        groups: dict[tuple[str, str, str, int, str], list[sqlite3.Row]] = {}
        for row in rows:
            key = (row["producer"], row["asset"], row["regime"], int(row["horizon_seconds"]), row["target"])
            groups.setdefault(key, []).append(row)
        cards = []
        for (producer, asset, regime, horizon, target), group in sorted(groups.items()):
            settled = len(group)
            classified = [r for r in group if r["success"] is not None]
            successes = sum(int(r["success"]) for r in classified)
            hit_rate = successes / len(classified) if classified else None
            briers = [float(r["brier"]) for r in group if r["brier"] is not None]
            mean_brier = sum(briers) / len(briers) if briers else None
            mean_confidence = sum(float(r["probability"]) for r in group) / settled
            calibration_gap = None if hit_rate is None else abs(mean_confidence - hit_rate)
            errors = [float(r["absolute_error"]) for r in group if r["absolute_error"] is not None]
            interval = wilson_interval(successes, len(classified)) if classified else (None, None)
            cards.append({
                "producer": producer,
                "asset": asset,
                "regime": regime,
                "horizon_seconds": horizon,
                "target": target,
                "settled": settled,
                "successes": successes,
                "hit_rate": hit_rate,
                "wilson_95": list(interval) if classified else None,
                "mean_confidence": mean_confidence,
                "mean_brier": mean_brier,
                "calibration_gap": calibration_gap,
                "mean_absolute_error": sum(errors) / len(errors) if errors else None,
                "status": "MEASURED" if settled >= 30 else "EARLY",
                **_authority(),
            })
        return cards

    @staticmethod
    def _infer_asset(path: Path) -> str:
        name = path.name.upper()
        for symbol in ("MNQ", "NQ", "MES", "ES", "MGC", "GC", "SI", "BTC"):
            if symbol in name:
                return symbol
        return "UNKNOWN"

    @staticmethod
    def _infer_chart_type(path: Path) -> str:
        name = path.name.lower()
        if "renko" in name:
            return "renko"
        if "heikin" in name or "_ha" in name or "-ha" in name:
            return "heikin_ashi"
        for minutes in ("1", "2", "5", "10", "15", "20", "30", "60"):
            if f"{minutes}m" in name or f", {minutes}(" in name or f", {minutes}." in name:
                return f"{minutes}m"
        return "minutes"

    @staticmethod
    def _manifest_symbol(value: Any) -> str:
        raw = str(value or "").strip().upper()
        if ":" in raw:
            raw = raw.split(":")[-1]
        raw = raw.replace("!", "")
        if raw.endswith("1"):
            raw = raw[:-1]
        for known in ("MNQ", "NQ", "MES", "ES", "MGC", "GC", "SI", "BTC", "ETH", "SOL"):
            if raw.startswith(known):
                return known
        return raw or "UNKNOWN"

    @staticmethod
    def _manifest_timeframe(value: Any) -> str | None:
        raw = str(value or "").strip().lower()
        if not raw:
            return None
        import re
        match = re.fullmatch(r"(\d+)\s*minutes?", raw)
        if match:
            return f"{int(match.group(1))}m"
        match = re.fullmatch(r"(\d+)\s*hours?", raw)
        if match:
            return f"{int(match.group(1))}h"
        return raw.replace(" ", "_")

    def _intake_manifest_catalog(self) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
        by_hash: dict[str, dict[str, str]] = {}
        by_name: dict[str, dict[str, str]] = {}
        candidates: set[Path] = set()
        for rel in self._config["history_roots"]:
            root = (self.base_dir / rel).resolve()
            if root.exists():
                candidates.update(root.rglob("EXPORT_INTAKE_MANIFEST.csv"))
                parent = root.parent / "EXPORT_INTAKE_MANIFEST.csv"
                if parent.is_file():
                    candidates.add(parent)
        direct = self.base_dir / "EXPORT_INTAKE_MANIFEST.csv"
        if direct.is_file():
            candidates.add(direct)
        for path in sorted(candidates):
            try:
                with path.open("r", encoding="utf-8-sig", newline="") as fh:
                    for row in csv.DictReader(fh):
                        if not isinstance(row, dict):
                            continue
                        clean = {str(k): str(v or "").strip() for k, v in row.items()}
                        sha = clean.get("sha256", "").lower()
                        if len(sha) == 64:
                            by_hash[sha] = clean
                        names = [clean.get("canonical_filename", "")]
                        names.extend(x.strip() for x in clean.get("all_observed_filenames", "").split("|"))
                        for name in names:
                            if name:
                                by_name[name] = clean
            except (OSError, UnicodeDecodeError, csv.Error):
                continue
        return by_hash, by_name

    def register_dataset(
        self,
        path: str | os.PathLike[str],
        *,
        asset: str | None = None,
        chart_type: str | None = None,
        schema: str = "ohlc",
        intake: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        source = Path(path).resolve()
        if not source.is_file():
            raise ValueError(f"dataset not found: {source}")
        raw = source.read_bytes()
        raw_sha = hashlib.sha256(raw).hexdigest()
        artifact_class = "csv"
        manifest: dict[str, Any]
        rows = 0
        first = last = None
        canonical = None
        try:
            bars, manifest = inspect_ohlc(source)
            artifact_class = "ohlc"
            rows = int(manifest["rows_total"])
            first = manifest.get("first_ts")
            last = manifest.get("last_ts")
            canonical = manifest.get("canonical_rows_sha256")
        except (ValueError, OSError, UnicodeDecodeError):
            try:
                with source.open("r", encoding="utf-8-sig", newline="") as fh:
                    reader = csv.reader(fh)
                    header = next(reader, [])
                    rows = sum(1 for _ in reader)
                lowered = {str(x).strip().lower() for x in header}
                artifact_class = "trade_list" if {"trade number", "type", "date and time"} <= lowered else "csv"
                manifest = {"raw_sha256": raw_sha, "rows_total": rows, "header": header, "status": "catalogued"}
            except (OSError, UnicodeDecodeError, csv.Error) as ex:
                raise ValueError(f"dataset cannot be catalogued: {ex}") from ex

        intake_clean = dict(intake or {})
        if intake_clean:
            _json(intake_clean, "intake manifest")
            manifest["intake"] = intake_clean
        symbol = _text(
            asset or (self._manifest_symbol(intake_clean.get("symbol")) if intake_clean.get("symbol") else self._infer_asset(source)),
            "asset",
            32,
        ).upper()
        chart = _text(
            chart_type or self._manifest_timeframe(intake_clean.get("timeframe")) or self._infer_chart_type(source),
            "chart_type",
            64,
        )
        dataset_id = "ds-" + raw_sha
        now = _utc_now()
        with self._lock, self._conn:
            existing = self._conn.execute("SELECT * FROM datasets WHERE raw_sha256=?", (raw_sha,)).fetchone()
            idempotent = existing is not None
            if existing is None:
                self._conn.execute(
                    """INSERT INTO datasets(dataset_id,raw_sha256,canonical_rows_sha256,path,asset,
                       chart_type,schema_name,artifact_class,rows,first_timestamp,last_timestamp,
                       manifest_json,discovered_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        dataset_id, raw_sha, canonical, str(source), symbol, chart, str(schema),
                        artifact_class, rows, first, last, _json(manifest, "manifest"), now,
                    ),
                )
            else:
                dataset_id = existing["dataset_id"]
            self._conn.execute(
                "INSERT OR IGNORE INTO dataset_paths(dataset_id,path,first_seen) VALUES(?,?,?)",
                (dataset_id, str(source), now),
            )
        dataset = self.dataset(dataset_id)
        return {"ok": True, "idempotent": idempotent, "dataset": dataset, **_authority()}

    def dataset(self, dataset_id: str) -> dict[str, Any]:
        did = _text(dataset_id, "dataset_id", 80)
        row = self._conn.execute("SELECT * FROM datasets WHERE dataset_id=?", (did,)).fetchone()
        if row is None:
            raise ValueError("unknown dataset_id")
        return {
            "dataset_id": row["dataset_id"],
            "raw_sha256": row["raw_sha256"],
            "canonical_rows_sha256": row["canonical_rows_sha256"],
            "path": row["path"],
            "asset": row["asset"],
            "chart_type": row["chart_type"],
            "schema": row["schema_name"],
            "artifact_class": row["artifact_class"],
            "rows": row["rows"],
            "first_timestamp": row["first_timestamp"],
            "last_timestamp": row["last_timestamp"],
            "manifest": json.loads(row["manifest_json"]),
            "discovered_at": row["discovered_at"],
            **_authority(),
        }

    def scan_history(self) -> dict[str, Any]:
        seen = 0
        registered = 0
        errors = {}
        roots = []
        dataset_ids: list[str] = []
        by_hash, by_name = self._intake_manifest_catalog()
        for rel in self._config["history_roots"]:
            root = (self.base_dir / rel).resolve()
            try:
                root.relative_to(self.base_dir)
            except ValueError:
                continue
            roots.append(str(root))
            if not root.exists():
                continue
            for path in sorted(root.rglob("*.csv")):
                if not path.is_file() or path.name == "EXPORT_INTAKE_MANIFEST.csv":
                    continue
                seen += 1
                try:
                    raw_sha = hashlib.sha256(path.read_bytes()).hexdigest()
                    intake = by_hash.get(raw_sha) or by_name.get(path.name)
                    intake_payload = None
                    asset = chart = None
                    if intake:
                        intake_payload = dict(intake)
                        intake_payload["manifest_sha256"] = str(intake.get("sha256") or raw_sha).lower()
                        asset = self._manifest_symbol(intake.get("symbol"))
                        chart = self._manifest_timeframe(intake.get("timeframe"))
                    result = self.register_dataset(path, asset=asset, chart_type=chart, intake=intake_payload)
                    dataset_ids.append(result["dataset"]["dataset_id"])
                    registered += int(not result["idempotent"])
                except Exception as ex:
                    errors[str(path)] = f"{type(ex).__name__}: {ex}"[:500]
        self._last_history_scan = time.time()
        unique = int(self._conn.execute("SELECT COUNT(*) FROM datasets").fetchone()[0])
        return {
            "files_seen": seen,
            "new_datasets": registered,
            "unique_datasets": unique,
            "dataset_ids": sorted(set(dataset_ids)),
            "roots": roots,
            "intake_manifest_entries": len(by_hash),
            "errors": errors,
            **_authority(),
        }

    def _import_trade_list_dataset(self, dataset: Mapping[str, Any]) -> dict[str, Any]:
        dataset_id = str(dataset["dataset_id"])
        slot = "trade_experience"
        existing = self._conn.execute(
            "SELECT * FROM training_runs WHERE dataset_id=? AND slot=?",
            (dataset_id, slot),
        ).fetchone()
        if existing is not None:
            report = json.loads(existing["report_json"])
            return {
                "dataset_id": dataset_id,
                "status": "complete",
                "runs": [{"run_id": existing["run_id"], "slot": slot, "idempotent": True, "report": report}],
                **_authority(),
            }

        from .parity import read_tv_trades
        trades = read_tv_trades(str(dataset["path"]))
        imported = 0
        complete = 0
        errors: dict[str, str] = {}
        for trade in trades:
            pieces = list(trade.get("pieces") or [])
            if not pieces or any(piece.get("ts") is None for piece in pieces):
                continue
            record_key = f"{dataset_id}:{trade.get('no')}:{trade.get('entry_ts')}:{trade.get('dir')}:{trade.get('entry_px')}"
            try:
                qty = float(trade.get("qty") or 0.0)
                exit_qty = sum(float(piece.get("qty") or 0.0) for piece in pieces)
                if qty <= 0 or exit_qty <= 0:
                    raise ValueError("trade quantity must be positive")
                exit_price = sum(float(piece["px"]) * float(piece.get("qty") or 0.0) for piece in pieces) / exit_qty
                pnl = sum(float(piece.get("pnl") or 0.0) for piece in pieces)
                entry_ts = int(trade["entry_ts"])
                exit_ts = max(int(piece["ts"]) for piece in pieces)
                result = self.record_experience({
                    "source": "historical_trade_list",
                    "source_record_id": record_key,
                    "asset": dataset["asset"],
                    "direction": "long" if int(trade["dir"]) > 0 else "short",
                    "entry_at": _iso(datetime.fromtimestamp(entry_ts, tz=timezone.utc)),
                    "exit_at": _iso(datetime.fromtimestamp(exit_ts, tz=timezone.utc)),
                    "qty": qty,
                    "entry_price": float(trade["entry_px"]),
                    "exit_price": exit_price,
                    "pnl": pnl,
                    "metadata": {
                        "dataset_id": dataset_id,
                        "dataset_sha256": dataset["raw_sha256"],
                        "trade_number": trade.get("no"),
                        "entry_signal": trade.get("entry_sig"),
                        "exit_signals": [piece.get("sig") for piece in pieces],
                        "time_quality": "UNVERIFIED_TIMEZONE",
                        "time_interpretation": "TradingView export parsed with parity UTC compatibility; do not infer session/regime until timezone is independently bound.",
                    },
                })
                complete += 1
                imported += int(not result["idempotent"])
            except Exception as ex:
                errors[record_key] = f"{type(ex).__name__}: {ex}"[:500]

        report = {
            "status": "imported" if not errors else "partial",
            "artifact_class": "trade_list",
            "experience_count": complete,
            "new_experiences": imported,
            "time_quality": "UNVERIFIED_TIMEZONE",
            "errors": errors,
            **_authority(),
        }
        run_id = "train-" + hashlib.sha256(f"{dataset_id}|{slot}".encode()).hexdigest()
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO training_runs(run_id,dataset_id,slot,report_json,status,created_at) VALUES(?,?,?,?,?,?)",
                (run_id, dataset_id, slot, _json(report, "trade experience report"), report["status"], _utc_now()),
            )
        return {
            "dataset_id": dataset_id,
            "status": "complete" if not errors else "partial",
            "runs": [{"run_id": run_id, "slot": slot, "idempotent": False, "report": report}],
            **_authority(),
        }

    def backfill_dataset(self, dataset_id: str, *, slots: Sequence[str] | None = None) -> dict[str, Any]:
        dataset = self.dataset(dataset_id)
        if dataset["artifact_class"] == "trade_list":
            return self._import_trade_list_dataset(dataset)
        if dataset["artifact_class"] != "ohlc":
            return {"dataset_id": dataset_id, "status": "skipped", "reason": "dataset is neither OHLC nor trade-list experience", "runs": [], **_authority()}
        requested = list(slots if slots is not None else self._config["auto_train_slots"])
        runs = []
        for raw_slot in requested:
            slot = str(raw_slot).strip().lower()
            if slot not in {"logit", "xgb", "regime"}:
                raise ValueError(f"unsupported backfill slot {slot}")
            existing = self._conn.execute(
                "SELECT * FROM training_runs WHERE dataset_id=? AND slot=?", (dataset_id, slot)
            ).fetchone()
            if existing is not None:
                report = json.loads(existing["report_json"])
                runs.append({"run_id": existing["run_id"], "slot": slot, "idempotent": True, "report": report})
                continue
            path = Path(dataset["path"])
            if slot == "logit":
                report = train_file(path, dataset["chart_type"], dataset["schema"], dataset["asset"])
            elif slot == "xgb":
                report = train_xgb_file(path, dataset["chart_type"], dataset["schema"], dataset["asset"])
            else:
                from .trainers.regime_slot import train as train_regime
                report = train_regime(path, dataset["asset"])
            run_id = "train-" + hashlib.sha256(f"{dataset_id}|{slot}".encode()).hexdigest()
            with self._lock, self._conn:
                self._conn.execute(
                    "INSERT OR IGNORE INTO training_runs(run_id,dataset_id,slot,report_json,status,created_at) VALUES(?,?,?,?,?,?)",
                    (run_id, dataset_id, slot, _json(report, "training report"), str(report.get("status") or "unknown"), _utc_now()),
                )
            runs.append({"run_id": run_id, "slot": slot, "idempotent": False, "report": report})
        return {"dataset_id": dataset_id, "status": "complete", "runs": runs, **_authority()}

    def datasets(self) -> list[dict[str, Any]]:
        rows = self._conn.execute("SELECT dataset_id FROM datasets ORDER BY discovered_at,dataset_id").fetchall()
        return [self.dataset(row["dataset_id"]) for row in rows]

    def training_runs(self) -> list[dict[str, Any]]:
        rows = self._conn.execute("SELECT * FROM training_runs ORDER BY created_at,run_id").fetchall()
        return [
            {
                "run_id": row["run_id"],
                "dataset_id": row["dataset_id"],
                "slot": row["slot"],
                "status": row["status"],
                "report": json.loads(row["report_json"]),
                "created_at": row["created_at"],
                **_authority(),
            }
            for row in rows
        ]

    def _harvest_sibyl(self) -> dict[str, Any]:
        path = self.root / "sibyl.sqlite3"
        if not path.is_file():
            return {"status": "unavailable", "forecasts_imported": 0, "outcomes_imported": 0}
        con = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        forecasts_imported = outcomes_imported = 0
        try:
            forecasts = con.execute("SELECT * FROM forecasts ORDER BY observed_at, forecast_id").fetchall()
            outcomes = con.execute("SELECT * FROM outcomes ORDER BY observed_at, forecast_id, horizon_seconds").fetchall()
        finally:
            con.close()
        mapping: dict[tuple[str, int], str] = {}
        for row in forecasts:
            payload = json.loads(row["forecast_json"])
            collapse = payload.get("temporal_collapse") if isinstance(payload.get("temporal_collapse"), Mapping) else {}
            regime = str(collapse.get("dominant_basin") or "unknown").lower()
            for hrow in payload.get("horizons", []) or []:
                if not isinstance(hrow, Mapping):
                    continue
                horizon = int(hrow.get("horizon_seconds") or 0)
                probs = hrow.get("probabilities")
                if horizon <= 0 or not isinstance(probs, Mapping) or not probs:
                    continue
                normalized = {str(k).lower(): float(v) for k, v in probs.items()}
                dominant = max(normalized, key=normalized.get)
                result = self.record_prediction({
                    "producer": "sibyl",
                    "asset": row["asset"],
                    "target": "class",
                    "prediction": dominant,
                    "probabilities": normalized,
                    "reference_value": row["current_price"],
                    "emitted_at": row["observed_at"],
                    "horizon_seconds": horizon,
                    "regime": regime,
                    "evidence_ids": [f"sibyl:{row['forecast_id']}"],
                    "source_commit": row["source_commit"],
                    "metadata": {
                        "native_forecast_id": row["forecast_id"],
                        "native_engine": "sibyl",
                        "volatility_pct": row["volatility_pct"],
                    },
                })
                mapping[(row["forecast_id"], horizon)] = result["prediction"]["prediction_id"]
                forecasts_imported += int(not result["idempotent"])
        for row in outcomes:
            pid = mapping.get((row["forecast_id"], int(row["horizon_seconds"])))
            if not pid:
                continue
            result = self.record_outcome({
                "prediction_id": pid,
                "observed_at": row["observed_at"],
                "actual_value": str(row["realized_class"]).lower(),
                "evidence": json.loads(row["evidence_json"]),
                "metadata": {"native_brier": row["brier"], "native_engine": "sibyl"},
            })
            outcomes_imported += int(not result["idempotent"])
        return {"status": "ok", "forecasts_imported": forecasts_imported, "outcomes_imported": outcomes_imported}

    def _harvest_cursor(self, adapter: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT cursor_json FROM harvest_cursors WHERE adapter=?",
            (adapter,),
        ).fetchone()
        if row is None:
            return None
        value = json.loads(row["cursor_json"])
        return value if isinstance(value, dict) else None

    def _set_harvest_cursor(self, adapter: str, cursor: Mapping[str, Any]) -> None:
        payload = dict(cursor)
        _json(payload, "harvest cursor")
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO harvest_cursors(adapter,cursor_json,updated_at) VALUES(?,?,?) "
                "ON CONFLICT(adapter) DO UPDATE SET cursor_json=excluded.cursor_json, updated_at=excluded.updated_at",
                (adapter, _json(payload, "harvest cursor"), _utc_now()),
            )

    def _harvest_performance_proof(self) -> dict[str, Any]:
        """Incrementally fuse immutable proof outcomes into the common ledger."""
        engine = self._native.get("performance_proof")
        if engine is None or not hasattr(engine, "settled_records"):
            return {"status": "unavailable", "forecasts_imported": 0, "outcomes_imported": 0}
        cursor = self._harvest_cursor("performance_proof")
        request: dict[str, Any] = {"limit": 1000}
        if cursor:
            request["after_observed_at"] = cursor.get("observed_at")
            request["after_forecast_id"] = cursor.get("forecast_id")
        try:
            export = engine.settled_records(**request)
        except Exception as ex:
            return {
                "status": "degraded",
                "forecasts_imported": 0,
                "outcomes_imported": 0,
                "cursor": cursor,
                "error": f"{type(ex).__name__}: {ex}"[:500],
            }

        forecasts_imported = 0
        outcomes_imported = 0
        processed = 0
        errors: dict[str, str] = {}
        last_success = cursor
        for row in export.get("items", []) if isinstance(export, Mapping) else []:
            if not isinstance(row, Mapping):
                continue
            native_id = str(row.get("forecast_id") or "")
            try:
                decision = _parse_time(row.get("decision_at"), "decision_at")
                maturity = _parse_time(row.get("matures_at"), "matures_at")
                horizon = int((maturity - decision).total_seconds())
                if horizon <= 0:
                    raise ValueError("performance-proof horizon must be positive")
                candidate_id = _text(row.get("candidate_id"), "candidate_id", 180)
                candidate_token = hashlib.sha256(candidate_id.encode("utf-8")).hexdigest()[:16]
                prediction = self.record_prediction({
                    "producer": f"performance-proof:{candidate_token}",
                    "asset": row.get("asset"),
                    "target": "event",
                    "prediction": True,
                    "probability": row.get("probability_success"),
                    "emitted_at": _iso(decision),
                    "horizon_seconds": horizon,
                    "regime": str(row.get("regime") or "unknown").lower(),
                    "evidence_ids": [
                        f"performance-proof:{native_id}",
                        f"dataset:{row.get('dataset_hash')}",
                        f"evidence:{row.get('evidence_hash')}",
                    ],
                    "source_commit": row.get("source_commit"),
                    "metadata": {
                        "native_engine": "performance_proof",
                        "native_forecast_id": native_id,
                        "candidate_id": candidate_id,
                        "success_definition": row.get("success_definition"),
                        "source_repo": row.get("source_repo"),
                    },
                })
                forecasts_imported += int(not prediction["idempotent"])
                outcome = self.record_outcome({
                    "prediction_id": prediction["prediction"]["prediction_id"],
                    "observed_at": row.get("observed_at"),
                    "actual_value": bool(row.get("success")),
                    "evidence": [f"performance-proof-outcome:{row.get('outcome_hash')}"],
                    "metadata": {
                        "native_engine": "performance_proof",
                        "native_forecast_id": native_id,
                        "realized_value": row.get("realized_value"),
                        "source": row.get("source"),
                    },
                })
                outcomes_imported += int(not outcome["idempotent"])
                processed += 1
                last_success = {
                    "observed_at": row.get("observed_at"),
                    "forecast_id": native_id,
                }
            except Exception as ex:
                errors[native_id or "unknown"] = f"{type(ex).__name__}: {ex}"[:500]
                break

        if last_success and last_success != cursor:
            self._set_harvest_cursor("performance_proof", last_success)
        available = int(export.get("total") or 0) if isinstance(export, Mapping) else 0
        return {
            "status": "ok" if not errors else "partial",
            "forecasts_imported": forecasts_imported,
            "outcomes_imported": outcomes_imported,
            "processed": processed,
            "settled_available_after_cursor": available,
            "backlog_remaining": max(0, available - processed),
            "cursor": last_success,
            "batch_limit": 1000,
            "errors": errors,
        }

    def _harvest_source_reliability(self) -> dict[str, Any]:
        """Surface observed source quality without pretending it is model accuracy."""
        engine = self._native.get("source_reliability")
        if engine is None or not hasattr(engine, "snapshot"):
            return {"status": "unavailable", "observation_count": 0, "source_stream_count": 0, "sources": []}
        try:
            snap = engine.snapshot()
            return {
                "status": "ok",
                "observation_count": int(snap.get("observation_count") or 0),
                "source_stream_count": int(snap.get("source_stream_count") or 0),
                "sources": list(snap.get("sources") or []),
                "rule": snap.get("rule"),
            }
        except Exception as ex:
            return {
                "status": "degraded",
                "observation_count": 0,
                "source_stream_count": 0,
                "sources": [],
                "error": f"{type(ex).__name__}: {ex}"[:500],
            }

    def _harvest_commissioning_metrics(self) -> dict[str, Any]:
        engine = self._native.get("commissioning")
        if engine is None:
            return {"status": "unavailable"}
        try:
            status = engine.status()
            return {
                "status": "ok",
                "settled_predictions": (status.get("metrics") or {}).get("settled_predictions"),
                "metrics": status.get("metrics"),
                "promotion_gate": status.get("promotion_gate"),
            }
        except Exception as ex:
            return {"status": "degraded", "error": f"{type(ex).__name__}: {ex}"[:500]}

    def _harvest_snapshot_metric(self, name: str) -> dict[str, Any]:
        engine = self._native.get(name)
        if engine is None:
            return {"status": "unavailable"}
        try:
            snapshot = engine.snapshot() if hasattr(engine, "snapshot") else engine.status()
            return {"status": "ok", "snapshot": snapshot}
        except Exception as ex:
            return {"status": "degraded", "error": f"{type(ex).__name__}: {ex}"[:500]}

    def harvest_native(self) -> dict[str, Any]:
        out = {"sibyl": self._harvest_sibyl()}
        out["performance_proof"] = self._harvest_performance_proof()
        out["source_reliability"] = self._harvest_source_reliability()
        out["commissioning"] = self._harvest_commissioning_metrics()
        for name in ("parallax", "dreamstate", "pantheon"):
            metric = self._harvest_snapshot_metric(name)
            if metric.get("status") == "ok":
                snapshot = metric.pop("snapshot")
                if name == "parallax":
                    metric.update({
                        "decisions": ((snapshot.get("counts") or {}).get("decisions")),
                        "observed_outcomes": ((snapshot.get("counts") or {}).get("observed_outcomes")),
                        "regret": snapshot.get("regret"),
                    })
                elif name == "dreamstate":
                    metric.update({"stages": snapshot.get("stages"), "families": snapshot.get("families")})
                else:
                    metric.update({"counts": snapshot.get("counts"), "ecology": snapshot.get("ecology")})
            out[name] = metric
        out.update(_authority())
        return out

    def _harvest_runtime_experience(self) -> dict[str, Any]:
        if self.port is None or not hasattr(self.port, "runner_list"):
            return {"status": "unavailable", "imported": 0, "eligible": 0, **_authority()}
        imported = 0
        eligible = 0
        skipped_open = 0
        skipped_warmup = 0
        skipped_no_live_boundary = 0
        errors: dict[str, str] = {}
        for runner in list(self.port.runner_list()):
            symbol = str(getattr(runner, "symbol", "") or "").strip().upper()
            em = getattr(runner, "em", None)
            if not symbol or em is None:
                continue
            raw_live_from = getattr(runner, "live_from_ts", None)
            if raw_live_from is None:
                skipped_no_live_boundary += 1
                continue
            live_from = float(raw_live_from)
            closed_all = list(getattr(em, "closed", []) or [])
            live_closed_start = int(getattr(runner, "live_closed_start", 0) or 0)
            live_closed_start = max(0, min(live_closed_start, len(closed_all)))
            live_closed = closed_all[live_closed_start:]
            skipped_warmup += live_closed_start
            open_keys = {
                (
                    str(getattr(row, "entry_id", "")),
                    int(getattr(row, "entry_ts", 0) or 0),
                    int(getattr(row, "direction", 0) or 0),
                    round(float(getattr(row, "entry_price", 0.0) or 0.0), 10),
                )
                for row in list(getattr(em, "open", []) or [])
            }
            groups: dict[tuple[Any, ...], list[Any]] = {}
            for row in live_closed:
                key = (
                    str(getattr(row, "entry_id", "")),
                    int(getattr(row, "entry_ts", 0) or 0),
                    int(getattr(row, "direction", 0) or 0),
                    round(float(getattr(row, "entry_price", 0.0) or 0.0), 10),
                    int(getattr(row, "lot_id", 0) or 0),
                )
                groups.setdefault(key, []).append(row)
            for key, pieces in groups.items():
                entry_id, entry_ts, direction, entry_price, lot_id = key
                if key[:4] in open_keys:
                    skipped_open += 1
                    continue
                exit_ts = max(int(getattr(piece, "exit_ts", 0) or 0) for piece in pieces)
                if exit_ts < live_from:
                    skipped_warmup += 1
                    continue
                source_record_id = f"{symbol}:{entry_ts}:{entry_id}:{lot_id}:{direction}:{entry_price}"
                try:
                    qty = sum(float(getattr(piece, "qty", 0.0) or 0.0) for piece in pieces)
                    if qty <= 0:
                        raise ValueError("closed live-sim position has no positive quantity")
                    exit_price = sum(
                        float(getattr(piece, "exit_price", 0.0) or 0.0) * float(getattr(piece, "qty", 0.0) or 0.0)
                        for piece in pieces
                    ) / qty
                    pnl = sum(float(getattr(piece, "profit", 0.0) or 0.0) for piece in pieces)
                    result = self.record_experience({
                        "source": "runtime_live_sim",
                        "source_record_id": source_record_id,
                        "asset": symbol,
                        "direction": "long" if direction > 0 else "short",
                        "entry_at": _iso(datetime.fromtimestamp(entry_ts, tz=timezone.utc)),
                        "exit_at": _iso(datetime.fromtimestamp(exit_ts, tz=timezone.utc)),
                        "qty": qty,
                        "entry_price": entry_price,
                        "exit_price": exit_price,
                        "pnl": pnl,
                        "metadata": {
                            "entry_id": entry_id,
                            "lot_id": lot_id,
                            "entry_qty": max(int(getattr(piece, "entry_qty", 0) or 0) for piece in pieces),
                            "exit_comments": [str(getattr(piece, "exit_comment", "") or "") for piece in pieces],
                            "exit_kinds": [str(getattr(piece, "exit_kind", "") or "") for piece in pieces],
                            "time_quality": "OBSERVED_UNIX_EVENT_TIME",
                            "live_from_ts": live_from,
                        },
                    })
                    eligible += 1
                    imported += int(not result["idempotent"])
                except Exception as ex:
                    errors[source_record_id] = f"{type(ex).__name__}: {ex}"[:500]
        return {
            "status": "ok" if not errors else "partial",
            "imported": imported,
            "eligible": eligible,
            "skipped_open": skipped_open,
            "skipped_warmup": skipped_warmup,
            "skipped_no_live_boundary": skipped_no_live_boundary,
            "errors": errors,
            **_authority(),
        }

    def _observe_portfolio(self) -> dict[str, Any]:
        if self.port is None or not self._config["settle_live_prices"]:
            return {"status": "unavailable", "assets": {}}
        try:
            status = self.port.status()
        except Exception as ex:
            return {"status": "degraded", "error": f"{type(ex).__name__}: {ex}"[:500], "assets": {}}
        now = _utc_now()
        assets = {}
        for row in status.get("assets", []) if isinstance(status, Mapping) else []:
            if not isinstance(row, Mapping):
                continue
            symbol = str(row.get("symbol") or "").strip().upper()
            raw = row.get("price")
            if not symbol or isinstance(raw, bool) or not isinstance(raw, (int, float)) or not math.isfinite(float(raw)) or float(raw) <= 0:
                continue
            assets[symbol] = self.observe_price(symbol, now, float(raw), evidence=["portfolio:observed-price"])
        return {"status": "ok", "assets": assets}

    def _next_trade_experience(self, limit: int) -> list[str]:
        if limit <= 0:
            return []
        rows = self._conn.execute(
            """SELECT d.dataset_id FROM datasets d
               WHERE d.artifact_class='trade_list'
               AND NOT EXISTS (
                   SELECT 1 FROM training_runs t
                   WHERE t.dataset_id=d.dataset_id AND t.slot='trade_experience'
               )
               ORDER BY d.discovered_at,d.dataset_id LIMIT ?""",
            (limit,),
        ).fetchall()
        return [row["dataset_id"] for row in rows]

    def _next_untrained(self, limit: int) -> list[str]:
        if limit <= 0 or not self._config["auto_train_slots"]:
            return []
        slots = self._config["auto_train_slots"]
        placeholders = ",".join("?" for _ in slots)
        rows = self._conn.execute(
            f"""SELECT d.dataset_id FROM datasets d
                WHERE d.artifact_class='ohlc'
                AND EXISTS (
                    SELECT 1 FROM (SELECT ? AS slot {''.join(' UNION ALL SELECT ?' for _ in slots[1:])}) wanted
                    WHERE NOT EXISTS (
                        SELECT 1 FROM training_runs t
                        WHERE t.dataset_id=d.dataset_id AND t.slot=wanted.slot
                    )
                )
                ORDER BY d.discovered_at,d.dataset_id LIMIT ?""",
            [*slots, limit],
        ).fetchall()
        return [r["dataset_id"] for r in rows]

    def _publish_apex_credibility(self, cards: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
        apex = self._native.get("apex")
        if apex is None or not hasattr(apex, "store") or not hasattr(apex.store, "record_model_credibility"):
            return {"status": "unavailable", "published": 0}
        published = 0
        errors = {}
        as_of = _utc_now()
        for card in cards:
            try:
                brier = card.get("mean_brier")
                gap = card.get("calibration_gap")
                hit = card.get("hit_rate")
                if brier is not None:
                    score = max(0.0, min(1.0, (1.0 - float(brier)) * (1.0 - float(gap or 0.0))))
                elif hit is not None:
                    score = max(0.0, min(1.0, float(hit)))
                else:
                    continue
                model_id = "learning:{producer}:{asset}:{regime}:{horizon_seconds}:{target}".format(**card)
                apex.store.record_model_credibility({
                    "model_id": model_id,
                    "as_of": as_of,
                    "score": score,
                    "status": card.get("status") or "UNMEASURED",
                    "sample_count": card.get("settled"),
                    "hit_rate": hit,
                    "mean_brier": brier,
                    "calibration_gap": gap,
                    "source": "continuous-learning-fabric",
                    **_authority(),
                })
                published += 1
            except Exception as ex:
                errors[str(card.get("producer") or "unknown")] = f"{type(ex).__name__}: {ex}"[:500]
        return {"status": "ok" if not errors else "partial", "published": published, "errors": errors}

    def tick(self) -> dict[str, Any]:
        started = _utc_now()
        errors = {}
        summary: dict[str, Any] = {}
        try:
            summary["settlement"] = self._observe_portfolio()
        except Exception as ex:
            errors["settlement"] = f"{type(ex).__name__}: {ex}"[:500]
        try:
            summary["experience"] = {"runtime": self._harvest_runtime_experience()}
        except Exception as ex:
            errors["experience"] = f"{type(ex).__name__}: {ex}"[:500]
        if self._config["harvest_native"]:
            try:
                summary["native"] = self.harvest_native()
            except Exception as ex:
                errors["native"] = f"{type(ex).__name__}: {ex}"[:500]
        now = time.time()
        if now - self._last_history_scan >= self._config["history_scan_seconds"]:
            try:
                summary["history"] = self.scan_history()
            except Exception as ex:
                errors["history"] = f"{type(ex).__name__}: {ex}"[:500]
        runs = []
        try:
            batch_limit = self._config["max_backfills_per_cycle"]
            for dataset_id in self._next_trade_experience(batch_limit):
                runs.append(self.backfill_dataset(dataset_id))
            for dataset_id in self._next_untrained(batch_limit):
                runs.append(self.backfill_dataset(dataset_id))
            summary["backfills"] = runs
        except Exception as ex:
            errors["backfill"] = f"{type(ex).__name__}: {ex}"[:500]
        summary["scorecards"] = self.scorecards()
        summary["apex_feedback"] = self._publish_apex_credibility(summary["scorecards"])
        finished = _utc_now()
        status = "partial" if errors else "ok"
        record = {
            "schema_version": "icarus-learning-cycle-v1",
            "started_at": started,
            "finished_at": finished,
            "status": status,
            "summary": summary,
            "errors": errors,
            **_authority(),
        }
        cycle_id = "cycle-" + _sha(record)
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR IGNORE INTO cycles(cycle_id,started_at,finished_at,status,summary_json) VALUES(?,?,?,?,?)",
                (cycle_id, started, finished, status, _json(record, "cycle")),
            )
        return {**record, "cycle_id": cycle_id}

    def _loop(self) -> None:
        while not self._stop.is_set():
            if self._config["enabled"]:
                try:
                    self.run_cycle()
                except Exception:
                    pass
            if self._stop.wait(self._config["cycle_seconds"]):
                break

    def start_background(self) -> dict[str, Any]:
        if not self._config["enabled"]:
            return self.status()
        with self._lock:
            if self._thread and self._thread.is_alive():
                return self.status()
            self._stop.clear()
            self._thread = threading.Thread(target=self._loop, name="icarus-learning-fabric", daemon=True)
            self._thread.start()
        return self.status()

    def stop(self) -> dict[str, Any]:
        self._stop.set()
        thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=max(1.0, min(5.0, self._config["cycle_seconds"] + 0.5)))
        return self.status()

    close = stop

    def snapshot(self) -> dict[str, Any]:
        dataset_count = int(self._conn.execute("SELECT COUNT(*) FROM datasets").fetchone()[0])
        train_count = int(self._conn.execute("SELECT COUNT(*) FROM training_runs").fetchone()[0])
        prediction_count = int(self._conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0])
        outcome_count = int(self._conn.execute("SELECT COUNT(*) FROM outcomes").fetchone()[0])
        experience_count = int(self._conn.execute("SELECT COUNT(*) FROM experiences").fetchone()[0])
        cycle_count = int(self._conn.execute("SELECT COUNT(*) FROM cycles").fetchone()[0])
        last_cycle = self._conn.execute("SELECT summary_json FROM cycles ORDER BY finished_at DESC LIMIT 1").fetchone()
        return {
            "schema_version": _SCHEMA,
            "status": "LEARNING" if outcome_count or train_count or experience_count else "WARMING",
            "config": dict(self._config),
            "datasets": {"count": dataset_count},
            "training": {"run_count": train_count},
            "predictions": {"count": prediction_count, "settled": outcome_count, "pending": max(0, prediction_count-outcome_count)},
            "health": self.health(),
            "experiences": self.experience_state(),
            "scorecards": self.scorecards(),
            "coverage": {
                "historical_trainers": "protected_replay",
                "historical_trade_lists": "immutable_realized_experience",
                "runtime_trade_outcomes": "fully_closed_live_sim_experience",
                "sibyl": "native_prediction_outcome",
                "performance_proof": "native_immutable_forecast_outcome",
                "source_reliability": "native_observed_quality_context",
                "commissioning_chronofold": "native_metrics_and_existing_outcomes",
                "parallax": "native_regret_metrics",
                "dreamstate": "native_candidate_lifecycle",
                "pantheon": "native_research_metrics",
                "apex": "empirical_credibility_feedback",
                "possibility": "forecast_contract_required",
                "chronofold": "calibrated_via_commissioning",
            },
            "cycles": {"count": cycle_count, "latest": None if last_cycle is None else json.loads(last_cycle["summary_json"])},
            "authority": {
                "research_only": True,
                "automatic_production_promotion": False,
                "automatic_execution": False,
            },
            **_authority(),
        }

    def status(self) -> dict[str, Any]:
        snap = self.snapshot()
        snap["background"] = {
            "running": bool(self._thread and self._thread.is_alive()),
            "cycle_seconds": self._config["cycle_seconds"],
            "last_history_scan_epoch": self._last_history_scan or None,
        }
        return snap
