"""Durable source-reliability memory for ICARUS research/shadow evidence.

The tracker records causal-time source observations, derives transparent
freshness/completeness/agreement/revision metrics, and keeps exact immutable
observation identities. It never authorizes production decisions or execution.
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

_ALLOWED = {
    "source_id", "stream", "observed_at", "event_time", "retrieval_time",
    "expected_freshness_seconds", "complete", "agreement_bps",
    "agreement_tolerance_bps", "revision", "evidence_hash",
}


def _iso(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a timezone-aware ISO-8601 timestamp")
    try:
        dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as ex:
        raise ValueError(f"{name} must be a timezone-aware ISO-8601 timestamp") from ex
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _text(value: Any, name: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} is required")
    out = value.strip()
    if len(out) > limit:
        raise ValueError(f"{name} exceeds {limit} characters")
    return out


def _finite(value: Any, name: str, *, low: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    out = float(value)
    if low is not None and out < low:
        raise ValueError(f"{name} must be >= {low}")
    return out


def _sha64(value: Any, name: str) -> str:
    out = _text(value, name, 64).lower()
    if len(out) != 64 or any(ch not in "0123456789abcdef" for ch in out):
        raise ValueError(f"{name} must be an exact 64-character lowercase hex digest")
    return out


def _semantic_hash(value: Mapping[str, Any]) -> str:
    raw = json.dumps(dict(value), sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _beta_mean(passes: int, total: int) -> float | None:
    if total <= 0:
        return None
    return (passes + 1.0) / (total + 2.0)


class SourceReliabilityStore:
    """Append-only source-quality observations with transparent posterior metrics."""

    def __init__(self, base_dir: str | Path):
        self.root = Path(base_dir) / "audit"
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "source_reliability.sqlite3"
        self._lock = threading.RLock()
        with self._connect() as con:
            con.executescript(
                """
                CREATE TABLE IF NOT EXISTS observations (
                    observation_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    stream TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    event_time TEXT NOT NULL,
                    retrieval_time TEXT NOT NULL,
                    freshness_age_seconds REAL NOT NULL,
                    expected_freshness_seconds REAL NOT NULL,
                    fresh INTEGER NOT NULL CHECK(fresh IN (0,1)),
                    complete INTEGER NOT NULL CHECK(complete IN (0,1)),
                    agreement_bps REAL,
                    agreement_tolerance_bps REAL,
                    agreement_pass INTEGER CHECK(agreement_pass IN (0,1) OR agreement_pass IS NULL),
                    revision INTEGER NOT NULL CHECK(revision IN (0,1)),
                    evidence_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS source_reliability_scope
                    ON observations(source_id, stream, observed_at);
                """
            )

    def _connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(str(self.path), timeout=10)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA journal_mode=WAL")
        return con

    def record_observation(self, body: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(body, Mapping) or set(body) != _ALLOWED:
            raise ValueError("observation requires exactly: " + ", ".join(sorted(_ALLOWED)))

        source_id = _text(body["source_id"], "source_id", 160)
        stream = _text(body["stream"], "stream", 160)
        observed_at = _iso(body["observed_at"], "observed_at")
        event_time = _iso(body["event_time"], "event_time")
        retrieval_time = _iso(body["retrieval_time"], "retrieval_time")
        now = datetime.now(timezone.utc)
        if _dt(observed_at) > now or _dt(retrieval_time) > now:
            raise ValueError("observed_at and retrieval_time cannot be in the future")
        if _dt(event_time) > _dt(retrieval_time):
            raise ValueError("event_time cannot be later than retrieval_time")
        if _dt(observed_at) < _dt(retrieval_time):
            raise ValueError("observed_at cannot be earlier than retrieval_time")

        expected = _finite(body["expected_freshness_seconds"], "expected_freshness_seconds", low=0.000001)
        age = (_dt(retrieval_time) - _dt(event_time)).total_seconds()
        fresh = age <= expected

        if type(body["complete"]) is not bool:
            raise ValueError("complete must be Boolean")
        if type(body["revision"]) is not bool:
            raise ValueError("revision must be Boolean")

        agreement_bps = body["agreement_bps"]
        tolerance = body["agreement_tolerance_bps"]
        if (agreement_bps is None) != (tolerance is None):
            raise ValueError("agreement_bps and agreement_tolerance_bps must both be set or both be null")
        agreement_pass = None
        if agreement_bps is not None:
            agreement_bps = _finite(agreement_bps, "agreement_bps", low=0.0)
            tolerance = _finite(tolerance, "agreement_tolerance_bps", low=0.0)
            agreement_pass = agreement_bps <= tolerance

        semantic = {
            "source_id": source_id,
            "stream": stream,
            "observed_at": observed_at,
            "event_time": event_time,
            "retrieval_time": retrieval_time,
            "expected_freshness_seconds": expected,
            "complete": body["complete"],
            "agreement_bps": agreement_bps,
            "agreement_tolerance_bps": tolerance,
            "revision": body["revision"],
            "evidence_hash": _sha64(body["evidence_hash"], "evidence_hash"),
        }
        observation_id = _semantic_hash(semantic)
        created = now.isoformat().replace("+00:00", "Z")

        with self._lock, self._connect() as con:
            prior = con.execute(
                "SELECT observation_id FROM observations WHERE observation_id=?",
                (observation_id,),
            ).fetchone()
            if prior is None:
                con.execute(
                    "INSERT INTO observations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        observation_id, source_id, stream, observed_at, event_time,
                        retrieval_time, age, expected, 1 if fresh else 0,
                        1 if body["complete"] else 0, agreement_bps, tolerance,
                        None if agreement_pass is None else (1 if agreement_pass else 0),
                        1 if body["revision"] else 0, semantic["evidence_hash"], created,
                    ),
                )
                idempotent = False
            else:
                idempotent = True

        return {
            "ok": True,
            "observation_id": observation_id,
            "idempotent": idempotent,
            "fresh": fresh,
            "freshness_age_seconds": age,
            "agreement_pass": agreement_pass,
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    def snapshot(self) -> dict[str, Any]:
        with self._lock, self._connect() as con:
            rows = [dict(x) for x in con.execute(
                "SELECT * FROM observations ORDER BY observed_at, observation_id"
            ).fetchall()]

        groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for row in rows:
            groups.setdefault((row["source_id"], row["stream"]), []).append(row)

        sources = []
        for (source_id, stream), group in sorted(groups.items()):
            n = len(group)
            fresh_pass = sum(int(x["fresh"]) for x in group)
            complete_pass = sum(int(x["complete"]) for x in group)
            agreement_rows = [x for x in group if x["agreement_pass"] is not None]
            agreement_pass = sum(int(x["agreement_pass"]) for x in agreement_rows)
            revisions = sum(int(x["revision"]) for x in group)

            freshness_posterior = _beta_mean(fresh_pass, n)
            completeness_posterior = _beta_mean(complete_pass, n)
            agreement_posterior = _beta_mean(agreement_pass, len(agreement_rows))
            stability_posterior = _beta_mean(n - revisions, n)
            components = [
                x for x in (
                    freshness_posterior,
                    completeness_posterior,
                    agreement_posterior,
                    stability_posterior,
                )
                if x is not None
            ]
            reliability = (sum(components) / len(components)) if components else None
            latest = group[-1]
            sources.append({
                "source_id": source_id,
                "stream": stream,
                "sample_count": n,
                "agreement_sample_count": len(agreement_rows),
                "fresh_rate": fresh_pass / n,
                "complete_rate": complete_pass / n,
                "agreement_rate": (agreement_pass / len(agreement_rows)) if agreement_rows else None,
                "revision_rate": revisions / n,
                "freshness_posterior_mean": freshness_posterior,
                "completeness_posterior_mean": completeness_posterior,
                "agreement_posterior_mean": agreement_posterior,
                "stability_posterior_mean": stability_posterior,
                "reliability_posterior_mean": reliability,
                "measurement_status": "MEASURED" if n >= 20 else "LOW_SAMPLE",
                "latest_observed_at": latest["observed_at"],
                "latest_freshness_age_seconds": latest["freshness_age_seconds"],
            })

        return {
            "schema_version": "icarus-source-reliability-v1",
            "observation_count": len(rows),
            "source_stream_count": len(sources),
            "sources": sources,
            "execution_authorized": False,
            "production_decision_authorized": False,
            "rule": "Reliability is a transparent Beta-smoothed summary of observed freshness, completeness, independent agreement when available, and revision stability; it is not a guarantee of future correctness.",
        }
