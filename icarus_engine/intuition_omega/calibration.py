"""Prospective truth ledger, proper scores, calibration, drift and honest abstention.

This module measures *already emitted* forecasts against *subsequently*
settled labels. It does not treat retrospectively fitted predictions as live
proof and never adjusts trading/sizing/production state.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import sqlite3

from .contracts import Scope, authority, check_sha, nonempty, probability, timestamp


def _iso(t: str) -> str:
    return timestamp(t, "timestamp").isoformat()


@dataclass(frozen=True)
class Forecast:
    forecast_id: str
    producer: str
    scope: Scope
    issued_at: str
    maturity_at: str
    received_at: str
    probability: float
    source_commit: str
    evidence_ids: tuple[str, ...]
    session_id: str

    def __post_init__(self) -> None:
        for field in ("forecast_id", "producer", "session_id"):
            nonempty(getattr(self, field), field)
        check_sha(self.source_commit)
        probability(self.probability, "probability")
        issued = timestamp(self.issued_at, "issued_at")
        received = timestamp(self.received_at, "received_at")
        mature = timestamp(self.maturity_at, "maturity_at")
        if received < issued or mature <= received:
            raise ValueError("forecast receipt/maturity violates event time")
        if not self.evidence_ids:
            raise ValueError("forecast requires source evidence")
        for evidence in self.evidence_ids:
            nonempty(evidence, "evidence")


@dataclass(frozen=True)
class Resolution:
    forecast_id: str
    observed_at: str
    received_at: str
    label: int
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        nonempty(self.forecast_id, "forecast_id")
        if type(self.label) is not int or self.label not in (0, 1):
            raise ValueError("binary outcome required")
        if timestamp(self.received_at, "received_at") < timestamp(self.observed_at, "observed_at"):
            raise ValueError("outcome received before observed")
        if not self.evidence_ids:
            raise ValueError("outcome must have evidence")


def _json(value: dict) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


class ForecastLedger:
    """Durable immutable forecast/settlement pairing. No backdated network ingress."""
    def __init__(self, path: str | Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(str(path))
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute("CREATE TABLE IF NOT EXISTS forecasts "
                         "(id TEXT PRIMARY KEY, producer TEXT, issued TEXT, "
                         "received TEXT, body TEXT NOT NULL, digest TEXT NOT NULL)")
        self._db.execute("CREATE TABLE IF NOT EXISTS resolutions "
                         "(id TEXT PRIMARY KEY, observed TEXT, received TEXT, "
                         "body TEXT NOT NULL, digest TEXT NOT NULL)")
        self._db.execute("CREATE INDEX IF NOT EXISTS idx_forecasts_producer ON forecasts(producer, issued)")
        self._db.commit()

    def close(self) -> None:
        self._db.close()

    def commit(self, forecast: Forecast) -> bool:
        body = asdict(forecast)
        body["issued_at"], body["maturity_at"], body["received_at"] = map(
            _iso, (forecast.issued_at, forecast.maturity_at, forecast.received_at))
        raw = _json(body)
        digest = hashlib.sha256(raw.encode()).hexdigest()
        with self._db:
            current = self._db.execute("SELECT digest FROM forecasts WHERE id=?", (forecast.forecast_id,)).fetchone()
            if current:
                if current[0] != digest:
                    raise ValueError("forecast identity collision")
                return False
            self._db.execute("INSERT INTO forecasts VALUES (?,?,?,?,?,?)", (
                forecast.forecast_id, forecast.producer, _iso(forecast.issued_at),
                _iso(forecast.received_at), raw, digest))
        return True

    def settle(self, resolution: Resolution) -> bool:
        row = self._db.execute("SELECT body,digest FROM forecasts WHERE id=?", (resolution.forecast_id,)).fetchone()
        if row is None:
            raise ValueError("unknown forecast")
        if hashlib.sha256(row[0].encode()).hexdigest() != row[1]:
            raise ValueError("forecast integrity failure")
        forecast = json.loads(row[0])
        if timestamp(resolution.observed_at, "observed_at") < timestamp(forecast["maturity_at"], "maturity_at"):
            raise ValueError("premature resolution")
        if timestamp(resolution.received_at, "received_at") < timestamp(forecast["received_at"], "forecast.received_at"):
            raise ValueError("resolution predates forecast receipt")
        body = asdict(resolution)
        body["observed_at"], body["received_at"] = _iso(resolution.observed_at), _iso(resolution.received_at)
        raw = _json(body)
        digest = hashlib.sha256(raw.encode()).hexdigest()
        with self._db:
            current = self._db.execute("SELECT digest FROM resolutions WHERE id=?", (resolution.forecast_id,)).fetchone()
            if current:
                if current[0] != digest:
                    raise ValueError("immutable resolution collision")
                return False
            self._db.execute("INSERT INTO resolutions VALUES (?,?,?,?,?)", (
                resolution.forecast_id, _iso(resolution.observed_at),
                _iso(resolution.received_at), raw, digest))
        return True

    def rows(self, *, producer: str, scope: Scope, as_of: str, source_commit: str | None = None) -> list[tuple[Forecast, Resolution]]:
        if source_commit is not None:
            check_sha(source_commit)
        boundary = _iso(as_of)
        records: list[tuple[Forecast, Resolution]] = []
        query = self._db.execute(
            "SELECT f.body,f.digest,r.body,r.digest,"
            "f.id,f.producer,f.issued,f.received,r.id,r.observed,r.received FROM forecasts f "
            "JOIN resolutions r ON r.id=f.id "
            "WHERE f.producer=? AND f.issued<=? AND f.received<=? "
            "AND r.observed<=? AND r.received<=? ORDER BY f.issued,f.id",
            (producer, boundary, boundary, boundary, boundary))
        for f_raw, f_sha, r_raw, r_sha, *indexes in query:
            if hashlib.sha256(f_raw.encode()).hexdigest() != f_sha or hashlib.sha256(r_raw.encode()).hexdigest() != r_sha:
                raise ValueError("calibration ledger digest mismatch")
            f_obj, r_obj = json.loads(f_raw), json.loads(r_raw)
            f_obj["scope"] = Scope(**f_obj["scope"])
            f_obj["evidence_ids"] = tuple(f_obj["evidence_ids"])
            r_obj["evidence_ids"] = tuple(r_obj["evidence_ids"])
            f, r = Forecast(**f_obj), Resolution(**r_obj)
            expected = (
                f.forecast_id, f.producer, _iso(f.issued_at), _iso(f.received_at),
                r.forecast_id, _iso(r.observed_at), _iso(r.received_at),
            )
            if tuple(indexes) != expected or f.forecast_id != r.forecast_id:
                raise ValueError("calibration ledger index/body integrity failure")
            cutoff = timestamp(as_of, "as_of")
            if (f.producer != producer
                    or timestamp(f.issued_at, "issued_at") > cutoff
                    or timestamp(f.received_at, "received_at") > cutoff
                    or timestamp(r.observed_at, "observed_at") > cutoff
                    or timestamp(r.received_at, "received_at") > cutoff
                    or timestamp(r.observed_at, "observed_at") < timestamp(f.maturity_at, "maturity_at")
                    or timestamp(r.received_at, "received_at") < timestamp(f.received_at, "received_at")):
                raise ValueError("calibration ledger as-of integrity failure")
            if (f.scope == scope and (source_commit is None or f.source_commit == source_commit)
                    and timestamp(f.maturity_at, "maturity_at") <= timestamp(as_of, "as_of")):
                records.append((f, r))
        if source_commit is None and len({f.source_commit for f, _ in records}) > 1:
            raise ValueError("mixed model revisions require an explicit source_commit")
        # Overlapping label horizons share outcomes and cannot count as
        # independent proof. A deterministic earliest-first purge is applied.
        chosen: list[tuple[Forecast, Resolution]] = []
        last_maturity: datetime | None = None
        for f, r in records:
            start = timestamp(f.issued_at, "issued_at")
            if last_maturity is not None and start < last_maturity:
                continue
            chosen.append((f, r))
            last_maturity = timestamp(f.maturity_at, "maturity_at")
        return chosen


def _ece(rows: list[tuple[float, int]]) -> float:
    """Tie-preserving, approximately equal-population ECE, diagnostic only."""
    if not rows:
        return 0.0
    sorted_rows = sorted(rows)
    groups: list[tuple[float, int, int]] = []
    for p, y in sorted_rows:
        if groups and groups[-1][0] == p:
            probability_value, n, wins = groups[-1]
            groups[-1] = (probability_value, n+1, wins+y)
        else:
            groups.append((p, 1, y))
    bins = min(10, len(groups), max(1, math.ceil(math.sqrt(len(rows)))))
    target = len(rows)/bins
    buckets: list[list[tuple[float, int, int]]] = [[]]
    count = 0
    for group in groups:
        if len(buckets) < bins and count >= target and buckets[-1]:
            buckets.append([])
            count = 0
        buckets[-1].append(group)
        count += group[1]
    total = len(rows)
    error = 0.0
    for bucket in buckets:
        n = sum(x[1] for x in bucket)
        predicted = sum(x[0]*x[1] for x in bucket)/n
        actual = sum(x[2] for x in bucket)/n
        error += (n/total)*abs(predicted-actual)
    return error


def calibration_report(
    ledger: ForecastLedger, *, producer: str, scope: Scope, as_of: str,
    minimum_episodes: int = 60, minimum_sessions: int = 20,
    baseline_probability: float | None = None,
    source_commit: str | None = None,
) -> dict:
    """Metrics apply only to prior, mature, non-overlapping forecasts."""
    if type(minimum_episodes) is not int or minimum_episodes < 30:
        raise ValueError("minimum_episodes must be >=30")
    if type(minimum_sessions) is not int or minimum_sessions < 10:
        raise ValueError("minimum_sessions must be >=10")
    if baseline_probability is not None:
        probability(baseline_probability, "baseline_probability")
    pairs = ledger.rows(producer=producer, scope=scope, as_of=as_of, source_commit=source_commit)
    data = [(f.probability, r.label) for f, r in pairs]
    sessions = len({f.session_id for f, _ in pairs})
    result = {
        "schema_version": "icarus-intuition-calibration-v1",
        "producer": producer, "scope": asdict(scope), "as_of": _iso(as_of),
        "source_commit": source_commit or (pairs[0][0].source_commit if pairs else None),
        "status": "UNMEASURED", "sample_count": len(data),
        "independent_sessions": sessions, "brier": None,
        "log_loss": None, "ece": None, "brier_skill_vs_locked_baseline": None,
        "drift_state": "UNMEASURED", "reason": "insufficient_mature_forecasts",
        **authority(),
    }
    if len(data) < minimum_episodes or sessions < minimum_sessions:
        return result
    n = len(data)
    brier = math.fsum((p-y)**2 for p, y in data)/n
    ll = -math.fsum(y*math.log(max(1e-12,p))+(1-y)*math.log(max(1e-12,1-p)) for p, y in data)/n
    result.update(brier=brier, log_loss=ll, ece=_ece(data))
    if baseline_probability is not None:
        baseline_brier = math.fsum((baseline_probability-y)**2 for _, y in data)/n
        result["brier_skill_vs_locked_baseline"] = (1-brier/baseline_brier) if baseline_brier > 0 else None
    half = n//2
    previous = math.fsum((p-y)**2 for p, y in data[:half])/half
    recent = math.fsum((p-y)**2 for p, y in data[half:])/(n-half)
    # Flag meaningful deterioration, never automatically refit/promote.
    drift = recent > previous + 0.05
    result["drift_state"] = "DRIFT_SUSPECTED" if drift else "NO_LARGE_SHIFT_DETECTED"
    result["status"] = "DEGRADED" if drift else "MEASURED"
    result["reason"] = "brier_deterioration" if drift else "empirical_diagnostics_only"
    return result
