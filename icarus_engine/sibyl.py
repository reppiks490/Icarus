"""SIBYL Omega probabilistic future-lightcone synthesis engine.

SIBYL fuses timestamped, provenance-bearing research evidence into a bounded
multi-horizon distribution over reachable market states. It deliberately does
not claim deterministic foresight and has no production-decision, sizing,
broker, or execution authority.

The engine is designed around seven invariants:
1. evidence is immutable, provenance-bound and filtered strictly as-of synthesis time;
2. correlated sources are collapsed by evidence domain before consensus;
3. deterministic replay never depends on wall-clock time after an as-of timestamp is fixed;
4. historical forecasts require an explicit price available at forecast time;
5. outcomes cannot score before their requested horizon matures;
6. PANTHEON evidence enters only through the identified structural-constraint gate;
7. counterfactual scenarios never mutate the evidence ledger.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

SCHEMA_VERSION = "icarus-sibyl-v1"
EVIDENCE_SCHEMA = "icarus-sibyl-evidence-v1"
FORECAST_SCHEMA = "icarus-sibyl-forecast-v1"
OUTCOME_SCHEMA = "icarus-sibyl-outcome-v1"
DEFAULT_HORIZONS = (60, 300, 900, 3600, 14400)
MAX_EVIDENCE = 512
PANTHEON_SOURCE = "pantheon-ananke"
PANTHEON_DOMAIN = "structural_constraints"
_LOCK = threading.RLock()


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _finite(value: Any, field: str, lo: float | None = None, hi: float | None = None) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError) as ex:
        raise ValueError(f"{field} must be numeric") from ex
    if not math.isfinite(out):
        raise ValueError(f"{field} must be finite")
    if lo is not None and out < lo:
        raise ValueError(f"{field} must be >= {lo}")
    if hi is not None and out > hi:
        raise ValueError(f"{field} must be <= {hi}")
    return out


def _integer(value: Any, field: str, lo: int, hi: int) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer")
    try:
        out = int(value)
    except (TypeError, ValueError) as ex:
        raise ValueError(f"{field} must be an integer") from ex
    if out < lo or out > hi:
        raise ValueError(f"{field} must be between {lo} and {hi}")
    return out


def _text(value: Any, field: str, limit: int, *, required: bool = True) -> str:
    if value is None and not required:
        return ""
    if not isinstance(value, str):
        raise ValueError(f"{field} must be a string")
    out = value.strip()
    if required and not out:
        raise ValueError(f"{field} is required")
    if len(out) > limit:
        raise ValueError(f"{field} exceeds {limit} characters")
    return out


def _timestamp(value: Any, field: str = "observed_at", *, allow_future_seconds: float = 5.0) -> str:
    raw = _text(value, field, 80)
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as ex:
        raise ValueError(f"{field} must be RFC3339/ISO-8601") from ex
    if dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError(f"{field} must include an explicit timezone")
    dt = dt.astimezone(timezone.utc)
    if (dt - datetime.now(timezone.utc)).total_seconds() > allow_future_seconds:
        raise ValueError(f"{field} cannot be in the future")
    return dt.isoformat().replace("+00:00", "Z")


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _json(value: Any, field: str, max_bytes: int = 262144) -> str:
    try:
        raw = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as ex:
        raise ValueError(f"{field} must be finite JSON") from ex
    if len(raw.encode("utf-8")) > max_bytes:
        raise ValueError(f"{field} exceeds {max_bytes} bytes")
    return raw


def _git_sha(value: Any) -> str:
    raw = _text(value, "source_commit", 40).lower()
    if len(raw) != 40 or any(c not in "0123456789abcdef" for c in raw):
        raise ValueError("source_commit must be a 40-character git SHA")
    return raw


def _asset(value: Any) -> str:
    raw = _text(value, "asset", 24).upper()
    if any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for c in raw):
        raise ValueError("asset contains unsupported characters")
    return raw


def _softmax(values: Iterable[float]) -> list[float]:
    vals = [float(v) for v in values]
    m = max(vals)
    ex = [math.exp(v - m) for v in vals]
    z = sum(ex) or 1.0
    return [v / z for v in ex]


def _entropy(probs: Iterable[float]) -> float:
    p = [max(0.0, float(x)) for x in probs]
    raw = -sum(x * math.log(x) for x in p if x > 0.0)
    return raw / math.log(max(2, len(p)))


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _market_asset(market_status: Mapping[str, Any] | None, asset: str) -> Mapping[str, Any] | None:
    if not isinstance(market_status, Mapping):
        return None
    rows = market_status.get("assets")
    if not isinstance(rows, list):
        return None
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        keys = {
            str(row.get("symbol") or "").upper(),
            str(row.get("continuous_symbol") or "").upper(),
        }
        if asset in keys:
            return row
    return None


class SibylEngine:
    """Durable probabilistic future-state synthesizer."""

    def __init__(self, base_dir: str | os.PathLike[str]):
        self.base_dir = Path(base_dir)
        self.db_path = self.base_dir / "research" / "sibyl.sqlite3"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self) -> None:
        with _LOCK, self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS evidence (
                    evidence_id TEXT PRIMARY KEY,
                    asset TEXT NOT NULL,
                    source TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    direction REAL NOT NULL,
                    magnitude REAL NOT NULL,
                    confidence REAL NOT NULL,
                    horizon_seconds INTEGER NOT NULL,
                    target_price REAL,
                    invalidation_price REAL,
                    source_commit TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_sibyl_evidence_asset_time
                    ON evidence(asset, observed_at DESC);

                CREATE TABLE IF NOT EXISTS forecasts (
                    forecast_id TEXT PRIMARY KEY,
                    asset TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    current_price REAL NOT NULL,
                    volatility_pct REAL NOT NULL,
                    source_commit TEXT NOT NULL,
                    forecast_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_sibyl_forecasts_asset_time
                    ON forecasts(asset, observed_at DESC);

                CREATE TABLE IF NOT EXISTS outcomes (
                    forecast_id TEXT NOT NULL,
                    horizon_seconds INTEGER NOT NULL,
                    observed_at TEXT NOT NULL,
                    realized_price REAL NOT NULL,
                    realized_class TEXT NOT NULL,
                    brier REAL NOT NULL,
                    evidence_json TEXT NOT NULL,
                    recorded_at TEXT NOT NULL,
                    PRIMARY KEY(forecast_id, horizon_seconds),
                    FOREIGN KEY(forecast_id) REFERENCES forecasts(forecast_id)
                );
                """
            )


    def record_evidence(self, body: Mapping[str, Any]) -> dict[str, Any]:
        """Record generic evidence; native PANTHEON evidence uses its dedicated gate."""
        return self._record_evidence(body, allow_reserved_source=False)

    def _record_evidence(
        self,
        body: Mapping[str, Any],
        *,
        allow_reserved_source: bool,
    ) -> dict[str, Any]:
        if not isinstance(body, Mapping):
            raise ValueError("evidence must be an object")
        asset = _asset(body.get("asset"))
        source = _text(body.get("source"), "source", 64).lower()
        domain = _text(body.get("domain"), "domain", 64).lower()
        if source == PANTHEON_SOURCE and not allow_reserved_source:
            raise ValueError("pantheon-ananke is reserved for native PANTHEON structural-evidence ingestion")
        observed_at = _timestamp(body.get("observed_at"))
        direction = _finite(body.get("direction"), "direction", -1.0, 1.0)
        magnitude = _finite(body.get("magnitude", 1.0), "magnitude", 0.0, 4.0)
        confidence = _finite(body.get("confidence"), "confidence", 0.0, 1.0)
        horizon = _integer(body.get("horizon_seconds"), "horizon_seconds", 1, 604800)
        target = body.get("target_price")
        invalidation = body.get("invalidation_price")
        target_price = None if target is None else _finite(target, "target_price", 0.0)
        invalidation_price = None if invalidation is None else _finite(invalidation, "invalidation_price", 0.0)
        source_commit = _git_sha(body.get("source_commit"))
        payload = body.get("payload", {})
        payload_json = _json(payload, "payload")
        semantic = {
            "schema_version": EVIDENCE_SCHEMA,
            "asset": asset,
            "source": source,
            "domain": domain,
            "observed_at": observed_at,
            "direction": direction,
            "magnitude": magnitude,
            "confidence": confidence,
            "horizon_seconds": horizon,
            "target_price": target_price,
            "invalidation_price": invalidation_price,
            "source_commit": source_commit,
            "payload": json.loads(payload_json),
        }
        evidence_id = _sha(_json(semantic, "semantic"))
        row = (
            evidence_id, asset, source, domain, observed_at, direction, magnitude,
            confidence, horizon, target_price, invalidation_price, source_commit,
            payload_json, _utc_now(),
        )
        with _LOCK, self._connect() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO evidence
                   (evidence_id, asset, source, domain, observed_at, direction, magnitude,
                    confidence, horizon_seconds, target_price, invalidation_price,
                    source_commit, payload_json, recorded_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                row,
            )
            saved = conn.execute("SELECT * FROM evidence WHERE evidence_id=?", (evidence_id,)).fetchone()
        return self._evidence_dict(saved)

    def record_pantheon_exports(self, observation: Mapping[str, Any]) -> dict[str, Any]:
        """Ingest only native PANTHEON/ANANKE structural-constraint exports.

        Caller-supplied evidence cannot reserve the pantheon-ananke source name.
        This adapter revalidates identity, chronology, provenance and authority
        even though the producer already applies its own export gate.
        """
        if not isinstance(observation, Mapping):
            raise ValueError("PANTHEON observation must be an object")
        observation_id = _text(observation.get("observation_id"), "observation_id", 96)
        asset = _asset(observation.get("asset"))
        observed_at = _timestamp(observation.get("observed_at"))
        source_commit = _git_sha(observation.get("source_commit"))
        analysis = observation.get("analysis")
        if not isinstance(analysis, Mapping):
            raise ValueError("PANTHEON analysis is required")
        exports = analysis.get("exports")
        if not isinstance(exports, Mapping):
            return {
                "accepted": 0,
                "rejected": [],
                "evidence": [],
                "contract": "pantheon-identified-structural-only",
                "execution_authorized": False,
                "production_decision_authorized": False,
            }
        candidates = exports.get("sibyl_evidence", [])
        if candidates is None:
            candidates = []
        if not isinstance(candidates, list) or len(candidates) > 8:
            raise ValueError("PANTHEON sibyl_evidence export must be a list with at most 8 items")

        accepted: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        authority_false = (
            "execution_authorized",
            "production_decision_authorized",
            "broker_authorized",
            "sizing_authorized",
            "automatic_production_promotion",
        )
        for index, raw in enumerate(candidates):
            if not isinstance(raw, Mapping):
                rejected.append({"index": index, "reason": "candidate must be an object"})
                continue
            try:
                candidate_asset = _asset(raw.get("asset"))
                candidate_source = _text(raw.get("source"), "source", 64).lower()
                candidate_domain = _text(raw.get("domain"), "domain", 64).lower()
                candidate_time = _timestamp(raw.get("observed_at"))
                candidate_commit = _git_sha(raw.get("source_commit"))
                direction = _finite(raw.get("direction"), "direction", -1.0, 1.0)
                magnitude = _finite(raw.get("magnitude", 1.0), "magnitude", 0.0, 4.0)
                confidence = _finite(raw.get("confidence"), "confidence", 0.0, 1.0)
                horizon = _integer(raw.get("horizon_seconds"), "horizon_seconds", 1, 604800)
            except (TypeError, ValueError) as ex:
                rejected.append({"index": index, "reason": str(ex)})
                continue

            payload = raw.get("payload")
            auth = payload.get("authority") if isinstance(payload, Mapping) else None
            reason = None
            if candidate_source != PANTHEON_SOURCE:
                reason = "source must be pantheon-ananke"
            elif candidate_domain != PANTHEON_DOMAIN:
                reason = "domain must be structural_constraints"
            elif candidate_asset != asset:
                reason = "candidate asset must match PANTHEON observation"
            elif candidate_time != observed_at:
                reason = "candidate observed_at must match PANTHEON observation"
            elif candidate_commit != source_commit:
                reason = "candidate source_commit must match PANTHEON observation"
            elif abs(direction) < 0.05:
                reason = "direction is below the identified structural threshold"
            elif confidence < 0.10:
                reason = "confidence is below the PANTHEON export threshold"
            elif not isinstance(payload, Mapping) or payload.get("producer") != "PANTHEON/ANANKE":
                reason = "producer must be PANTHEON/ANANKE"
            elif not isinstance(auth, Mapping) or auth.get("shadow_only") is not True:
                reason = "PANTHEON authority block is missing shadow_only"
            elif any(auth.get(key) is not False for key in authority_false):
                reason = "PANTHEON evidence must carry zero execution/production authority"

            if reason is not None:
                rejected.append({"index": index, "reason": reason})
                continue

            clean_payload = dict(payload)
            clean_payload["pantheon_observation_id"] = observation_id
            clean_payload["ingestion_contract"] = "identified-structural-only"
            evidence = self._record_evidence(
                {
                    "asset": asset,
                    "source": PANTHEON_SOURCE,
                    "domain": PANTHEON_DOMAIN,
                    "observed_at": observed_at,
                    "direction": direction,
                    "magnitude": magnitude,
                    "confidence": confidence,
                    "horizon_seconds": horizon,
                    "source_commit": source_commit,
                    "payload": clean_payload,
                },
                allow_reserved_source=True,
            )
            accepted.append(evidence)

        return {
            "accepted": len(accepted),
            "rejected": rejected,
            "evidence": accepted,
            "contract": "pantheon-identified-structural-only",
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    @staticmethod
    def _evidence_dict(row: sqlite3.Row | None) -> dict[str, Any]:
        if row is None:
            raise ValueError("evidence record not found")
        return {
            "schema_version": EVIDENCE_SCHEMA,
            "evidence_id": row["evidence_id"],
            "asset": row["asset"],
            "source": row["source"],
            "domain": row["domain"],
            "observed_at": row["observed_at"],
            "direction": row["direction"],
            "magnitude": row["magnitude"],
            "confidence": row["confidence"],
            "horizon_seconds": row["horizon_seconds"],
            "target_price": row["target_price"],
            "invalidation_price": row["invalidation_price"],
            "source_commit": row["source_commit"],
            "payload": json.loads(row["payload_json"]),
            "recorded_at": row["recorded_at"],
        }


    def _evidence(
        self,
        asset: str,
        limit: int = MAX_EVIDENCE,
        *,
        as_of: str | datetime | None = None,
    ) -> list[dict[str, Any]]:
        bounded = max(1, min(MAX_EVIDENCE, int(limit)))
        with self._connect() as conn:
            if as_of is None:
                rows = conn.execute(
                    """SELECT * FROM evidence
                       WHERE asset=?
                       ORDER BY julianday(observed_at) DESC, evidence_id DESC
                       LIMIT ?""",
                    (asset, bounded),
                ).fetchall()
            else:
                cutoff = (
                    as_of.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
                    if isinstance(as_of, datetime)
                    else _timestamp(as_of, "as_of")
                )
                rows = conn.execute(
                    """SELECT * FROM evidence
                       WHERE asset=? AND julianday(observed_at) <= julianday(?)
                       ORDER BY julianday(observed_at) DESC, evidence_id DESC
                       LIMIT ?""",
                    (asset, cutoff, bounded),
                ).fetchall()
        return [self._evidence_dict(row) for row in rows]

    @staticmethod

    def _revision_isolate(evidence: list[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
        """Keep only the newest as-of code revision for each named source."""
        latest: dict[str, tuple[datetime, str]] = {}
        for e in evidence:
            source = str(e.get("source") or "")
            commit = str(e.get("source_commit") or "")
            observed = _parse_time(str(e.get("observed_at")))
            key = (observed, commit)
            current = latest.get(source)
            if current is None or key > current:
                latest[source] = key
        return [
            e for e in evidence
            if latest.get(str(e.get("source") or ""), (None, None))[1] == str(e.get("source_commit") or "")
        ]

    @staticmethod
    def _horizon_weight(e: Mapping[str, Any], horizon: int, now: datetime) -> float:
        observed = _parse_time(str(e["observed_at"]))
        age = max(0.0, (now - observed).total_seconds())
        fresh_window = max(60.0, min(21600.0, float(horizon) * 2.0))
        freshness = math.exp(-age / fresh_window)
        eh = max(1.0, float(e["horizon_seconds"]))
        mismatch = abs(math.log((horizon + 1.0) / (eh + 1.0)))
        horizon_fit = math.exp(-0.85 * mismatch)
        return float(e["confidence"]) * freshness * horizon_fit


    def _fuse_horizon(
        self,
        evidence: list[Mapping[str, Any]],
        horizon: int,
        current_price: float | None,
        volatility_pct: float,
        *,
        as_of: datetime,
    ) -> dict[str, Any]:
        domains: dict[str, dict[str, list[tuple[float, float]]]] = {}
        contributing = 0
        for e in evidence:
            observed = _parse_time(str(e["observed_at"]))
            if observed > as_of:
                continue
            w = self._horizon_weight(e, horizon, as_of)
            if w <= 0.002:
                continue
            signal = float(e["direction"]) * float(e["magnitude"])
            domain = str(e["domain"])
            source = str(e["source"])
            domains.setdefault(domain, {}).setdefault(source, []).append((signal, w))
            contributing += 1

        domain_rows = []
        for domain, source_map in sorted(domains.items()):
            source_rows = []
            for source, rows in sorted(source_map.items()):
                total_w = sum(w for _, w in rows)
                if total_w <= 0:
                    continue
                source_score = sum(signal * w for signal, w in rows) / total_w
                source_weight = min(1.0, max(w for _, w in rows))
                source_rows.append((source, source_score, source_weight))
            if not source_rows:
                continue
            denom = sum(weight for _, _, weight in source_rows)
            score = sum(source_score * weight for _, source_score, weight in source_rows) / max(1e-12, denom)
            domain_weight = max(weight for _, _, weight in source_rows)
            domain_rows.append({
                "domain": domain,
                "score": score,
                "weight": domain_weight,
                "source_count": len(source_rows),
            })

        if domain_rows:
            denom = sum(r["weight"] for r in domain_rows)
            score = sum(r["score"] * r["weight"] for r in domain_rows) / max(1e-12, denom)
            mean_domain_weight = denom / len(domain_rows)
        else:
            score = 0.0
            mean_domain_weight = 0.0

        score = max(-2.0, min(2.0, score))
        coverage = _clamp((len(domain_rows) / 4.0) * mean_domain_weight)
        up_logit = 2.15 * score
        down_logit = -2.15 * score
        flat_logit = 0.55 - 1.05 * abs(score) + 0.35 * (1.0 - coverage)
        p_up, p_flat, p_down = _softmax((up_logit, flat_logit, down_logit))
        ent = _entropy((p_up, p_flat, p_down))
        convergence = _clamp(1.0 - ent)
        sample_strength = _clamp(contributing / 10.0)
        collapse_score = _clamp(convergence * (0.35 + 0.65 * coverage) * (0.55 + 0.45 * sample_strength))
        directional_split = _clamp(4.0 * p_up * p_down)
        bifurcation_score = _clamp(directional_split * (1.0 - p_flat) * (0.45 + 0.55 * coverage))
        probs = {"up": p_up, "rotation": p_flat, "down": p_down}
        dominant = max(probs, key=probs.get)
        collapse_detected = bool(
            len(domain_rows) >= 3
            and coverage >= 0.48
            and probs[dominant] >= 0.67
            and ent <= 0.72
        )

        band = None
        if current_price is not None and current_price > 0:
            scale = max(0.25, math.sqrt(max(1.0, horizon) / 300.0))
            vol = max(0.00005, volatility_pct) * scale
            drift = max(-0.025, min(0.025, score * vol * 0.95))
            center = current_price * (1.0 + drift)
            width = current_price * vol * (0.70 + 0.55 * ent)
            band = {
                "low": max(0.0, center - width),
                "mid": center,
                "high": center + width,
                "volatility_pct": vol,
            }

        return {
            "horizon_seconds": horizon,
            "probabilities": probs,
            "dominant_basin": dominant,
            "entropy": ent,
            "convergence": convergence,
            "coverage": coverage,
            "collapse_score": collapse_score,
            "collapse_detected": collapse_detected,
            "bifurcation_score": bifurcation_score,
            "domain_count": len(domain_rows),
            "contributing_evidence": contributing,
            "domain_fusion": domain_rows,
            "reachable_band": band,
        }

    @staticmethod

    def _cluster_levels(
        evidence: list[Mapping[str, Any]],
        field: str,
        current_price: float | None,
        *,
        as_of: datetime,
        limit: int = 6,
    ) -> list[dict[str, Any]]:
        points: list[tuple[float, float, str]] = []
        for e in evidence:
            value = e.get(field)
            if value is None:
                continue
            try:
                price = float(value)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(price) or price <= 0:
                continue
            observed = _parse_time(str(e["observed_at"]))
            if observed > as_of:
                continue
            age = max(0.0, (as_of - observed).total_seconds())
            freshness = math.exp(-age / max(300.0, float(e["horizon_seconds"]) * 2.0))
            weight = float(e["confidence"]) * max(0.05, float(e["magnitude"])) * freshness
            points.append((price, weight, str(e["source"])))
        if not points:
            return []
        points.sort(key=lambda x: x[0])
        basis = current_price if current_price and current_price > 0 else points[len(points) // 2][0]
        tol = max(0.01, basis * 0.0015)
        clusters: list[list[tuple[float, float, str]]] = []
        for point in points:
            if not clusters:
                clusters.append([point])
                continue
            center = sum(p * w for p, w, _ in clusters[-1]) / max(1e-12, sum(w for _, w, _ in clusters[-1]))
            if abs(point[0] - center) <= tol:
                clusters[-1].append(point)
            else:
                clusters.append([point])
        out = []
        for rows in clusters:
            total = sum(w for _, w, _ in rows)
            level = sum(p * w for p, w, _ in rows) / max(1e-12, total)
            out.append({
                "price": level,
                "mass": total,
                "sources": sorted({source for _, _, source in rows}),
                "distance_pct": None if not current_price else (level / current_price - 1.0) * 100.0,
            })
        out.sort(key=lambda x: x["mass"], reverse=True)
        return out[:limit]

    @staticmethod
    def _world_forks(horizon_rows: list[Mapping[str, Any]], limit: int = 12) -> dict[str, Any]:
        """Beam-search coherent basin sequences across horizons.

        These are structured summaries of the marginal horizon distributions,
        not claims that individual paths are independent or exhaustive.
        """
        beam: list[tuple[list[dict[str, Any]], float, str | None]] = [([], 1.0, None)]
        for row in horizon_rows:
            probs = row.get("probabilities") or {}
            expanded: list[tuple[list[dict[str, Any]], float, str]] = []
            for states, weight, previous in beam:
                for basin in ("up", "rotation", "down"):
                    p = max(0.0, float(probs.get(basin, 0.0)))
                    if p <= 0:
                        continue
                    if previous is None or previous == basin:
                        transition = 1.0
                    elif "rotation" in (previous, basin):
                        transition = 0.86
                    else:
                        transition = 0.62
                    expanded.append(
                        (
                            states + [{
                                "horizon_seconds": int(row["horizon_seconds"]),
                                "basin": basin,
                                "marginal_probability": p,
                            }],
                            weight * p * transition,
                            basin,
                        )
                    )
            expanded.sort(key=lambda x: x[1], reverse=True)
            beam = expanded[: max(limit * 4, 24)]

        top = beam[:limit]
        retained = sum(weight for _, weight, _ in top)
        worlds = []
        for rank, (states, weight, terminal) in enumerate(top, 1):
            normalized = weight / retained if retained > 0 else 0.0
            signature = ">".join(str(x["basin"])[0].upper() for x in states)
            worlds.append({
                "rank": rank,
                "signature": signature,
                "states": states,
                "terminal_basin": terminal,
                "relative_weight": normalized,
                "raw_weight": weight,
            })
        return {
            "worlds": worlds,
            "retained_raw_weight": retained,
            "normalization": "relative across retained beam paths; not exhaustive joint probability mass",
        }

    @staticmethod
    def _gravity_field(
        attractors: list[Mapping[str, Any]],
        invalidations: list[Mapping[str, Any]],
        current_price: float | None,
        volatility_pct: float,
    ) -> dict[str, Any]:
        if current_price is None or current_price <= 0 or (not attractors and not invalidations):
            return {"available": False, "points": [], "equilibrium_price": None}
        span = current_price * max(0.002, min(0.08, volatility_pct * 3.0))
        soft = max(1e-9, 0.0005)
        raw_points = []
        for i in range(17):
            price = current_price - span + (2.0 * span * i / 16.0)
            force = 0.0
            for row in attractors:
                delta = (float(row["price"]) - price) / current_price
                mass = min(5.0, max(0.0, float(row.get("mass") or 0.0)))
                force += mass * delta / (delta * delta + soft * soft)
            for row in invalidations:
                delta = (float(row["price"]) - price) / current_price
                mass = min(5.0, max(0.0, float(row.get("mass") or 0.0)))
                force -= mass * delta / (delta * delta + soft * soft)
            raw_points.append((price, force))
        scale = max((abs(force) for _, force in raw_points), default=0.0) or 1.0
        points = [{"price": price, "force": force / scale} for price, force in raw_points]
        equilibrium = min(raw_points, key=lambda x: abs(x[1]))[0] if raw_points else None
        return {
            "available": True,
            "points": points,
            "equilibrium_price": equilibrium,
            "strongest_attractor": attractors[0] if attractors else None,
            "strongest_invalidation": invalidations[0] if invalidations else None,
            "force_scale": "normalized to [-1, 1] across the displayed local price grid",
        }

    @staticmethod
    def _causal_delay_radar(evidence: list[Mapping[str, Any]], limit: int = 32) -> list[dict[str, Any]]:
        rows = []
        for e in evidence:
            payload = e.get("payload")
            if not isinstance(payload, Mapping):
                continue
            edges = payload.get("causal_edges")
            if not isinstance(edges, list):
                continue
            for edge in edges[:32]:
                if not isinstance(edge, Mapping):
                    continue
                try:
                    lag = float(edge.get("lag_ms"))
                    confidence = float(edge.get("confidence", 1.0)) * float(e.get("confidence", 0.0))
                except (TypeError, ValueError):
                    continue
                if not math.isfinite(lag) or lag < 0 or lag > 86_400_000:
                    continue
                if not math.isfinite(confidence):
                    continue
                source_node = str(edge.get("from") or "").strip()[:64]
                target_node = str(edge.get("to") or "").strip()[:64]
                if not source_node or not target_node:
                    continue
                rows.append({
                    "publisher": str(e.get("source") or ""),
                    "domain": str(e.get("domain") or ""),
                    "from": source_node,
                    "to": target_node,
                    "lag_ms": lag,
                    "relation": str(edge.get("relation") or "reported")[:32],
                    "confidence": _clamp(confidence),
                    "observed_at": str(e.get("observed_at") or ""),
                    "source_commit": str(e.get("source_commit") or ""),
                })
        rows.sort(key=lambda x: (x["confidence"], x["observed_at"]), reverse=True)
        return rows[:limit]

    @staticmethod
    def _forward_surface(evidence: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
        per_key: dict[tuple[int, str], list[tuple[dict[str, float], float]]] = {}
        fields = ("expected_return", "implied_vol", "skew", "tail_up", "tail_down")
        for e in evidence:
            payload = e.get("payload")
            if not isinstance(payload, Mapping):
                continue
            surface = payload.get("forward_surface")
            entries: list[Mapping[str, Any]] = []
            if isinstance(surface, list):
                entries = [x for x in surface if isinstance(x, Mapping)]
            elif isinstance(surface, Mapping):
                for key, value in surface.items():
                    if isinstance(value, Mapping):
                        row = dict(value)
                        row.setdefault("horizon_seconds", key)
                        entries.append(row)
            for row in entries[:64]:
                try:
                    horizon = int(row.get("horizon_seconds"))
                except (TypeError, ValueError):
                    continue
                if horizon < 1 or horizon > 604800:
                    continue
                values: dict[str, float] = {}
                for field in fields:
                    if row.get(field) is None:
                        continue
                    try:
                        value = float(row[field])
                    except (TypeError, ValueError):
                        continue
                    if math.isfinite(value):
                        values[field] = value
                if not values:
                    continue
                key = (horizon, str(e.get("source") or ""))
                per_key.setdefault(key, []).append((values, float(e.get("confidence") or 0.0)))

        per_horizon: dict[int, list[tuple[dict[str, float], float, str]]] = {}
        for (horizon, source), rows in per_key.items():
            source_weight = max((max(0.0, min(1.0, w)) for _, w in rows), default=0.0)
            merged: dict[str, float] = {}
            for field in fields:
                vals = [(v[field], max(0.0, w)) for v, w in rows if field in v]
                if vals:
                    denom = sum(w for _, w in vals) or float(len(vals))
                    merged[field] = sum(value * (w if w > 0 else 1.0) for value, w in vals) / (
                        sum((w if w > 0 else 1.0) for _, w in vals) or 1.0
                    )
            if merged:
                per_horizon.setdefault(horizon, []).append((merged, source_weight, source))

        out = []
        for horizon, sources in sorted(per_horizon.items()):
            row: dict[str, Any] = {
                "horizon_seconds": horizon,
                "sources": sorted(source for _, _, source in sources),
            }
            for field in fields:
                vals = [(values[field], weight) for values, weight, _ in sources if field in values]
                if vals:
                    denom = sum(weight for _, weight in vals) or float(len(vals))
                    row[field] = sum(value * (weight if weight > 0 else 1.0) for value, weight in vals) / (
                        sum((weight if weight > 0 else 1.0) for _, weight in vals) or 1.0
                    )
            out.append(row)
        return out


    def _build(
        self,
        asset: str,
        *,
        current_price: float | None,
        volatility_pct: float,
        evidence: list[Mapping[str, Any]],
        horizons: Iterable[int] = DEFAULT_HORIZONS,
        context: Mapping[str, Any] | None = None,
        counterfactual: bool = False,
        as_of: str | datetime,
    ) -> dict[str, Any]:
        as_of_dt = (
            as_of.astimezone(timezone.utc)
            if isinstance(as_of, datetime)
            else _parse_time(_timestamp(as_of, "as_of"))
        )
        generated_at = as_of_dt.isoformat().replace("+00:00", "Z")
        horizon_rows = [
            self._fuse_horizon(
                evidence,
                _integer(h, "horizon_seconds", 1, 604800),
                current_price,
                volatility_pct,
                as_of=as_of_dt,
            )
            for h in horizons
        ]
        strongest = max(horizon_rows, key=lambda x: x["collapse_score"]) if horizon_rows else None
        fracture = max(horizon_rows, key=lambda x: x["bifurcation_score"]) if horizon_rows else None
        domains = sorted({str(e["domain"]) for e in evidence})
        sources = sorted({str(e["source"]) for e in evidence})
        attractors = self._cluster_levels(evidence, "target_price", current_price, as_of=as_of_dt)
        invalidations = self._cluster_levels(evidence, "invalidation_price", current_price, as_of=as_of_dt)
        return {
            "schema_version": SCHEMA_VERSION,
            "asset": asset,
            "generated_at": generated_at,
            "as_of": generated_at,
            "counterfactual": counterfactual,
            "current_price": current_price,
            "volatility_pct": volatility_pct,
            "evidence": {
                "count": len(evidence),
                "sources": sources,
                "domains": domains,
                "distinct_domain_count": len(domains),
                "correlation_guard": "sources are collapsed by evidence domain before cross-domain consensus",
                "as_of_cutoff_inclusive": True,
            },
            "horizons": horizon_rows,
            "temporal_collapse": strongest,
            "temporal_fracture": fracture,
            "future_world_forks": self._world_forks(horizon_rows),
            "attractors": attractors,
            "repulsion_or_invalidation": invalidations,
            "liquidity_gravity_field": self._gravity_field(attractors, invalidations, current_price, volatility_pct),
            "causal_delay_radar": self._causal_delay_radar(evidence),
            "derivatives_forward_surface": self._forward_surface(evidence),
            "context": dict(context or {}),
            "truth_contract": {
                "wall_clock_free_after_as_of_is_fixed": True,
                "historical_forecast_price_must_be_explicit": True,
                "basin_probabilities_are_heuristic_until_calibrated": True,
                "future_evidence_is_excluded": True,
                "pantheon_ingestion_is_structural_only": True,
            },
            "authority": {
                "research_only": True,
                "shadow_only": True,
                "production_decision_authorized": False,
                "execution_authorized": False,
                "automatic_order_routing": False,
                "deterministic_foresight_claim": False,
            },
        }


    def snapshot(
        self,
        asset: str | None = None,
        *,
        market_status: Mapping[str, Any] | None = None,
        parallax_state: Mapping[str, Any] | None = None,
        dreamstate_state: Mapping[str, Any] | None = None,
        brain_state: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        as_of = _timestamp(_utc_now(), "as_of")
        chosen = _asset(asset) if asset else ""
        if not chosen and isinstance(market_status, Mapping):
            rows = market_status.get("assets")
            if isinstance(rows, list) and rows:
                first = rows[0] if isinstance(rows[0], Mapping) else {}
                raw = first.get("symbol") or first.get("continuous_symbol")
                if raw:
                    chosen = _asset(raw)
        if not chosen:
            with self._connect() as conn:
                row = conn.execute(
                    """SELECT asset FROM evidence
                       WHERE julianday(observed_at) <= julianday(?)
                       ORDER BY julianday(observed_at) DESC, evidence_id DESC LIMIT 1""",
                    (as_of,),
                ).fetchone()
            chosen = str(row["asset"]) if row else "NQ"

        market_row = _market_asset(market_status, chosen)
        price = None
        if isinstance(market_row, Mapping) and market_row.get("price") is not None:
            try:
                px = float(market_row["price"])
                price = px if math.isfinite(px) and px > 0 else None
            except (TypeError, ValueError):
                pass

        ledger_evidence = self._evidence(chosen, as_of=as_of)
        evidence = list(self._revision_isolate(ledger_evidence))
        volatility = 0.0025
        vol_candidates = []
        for e in evidence[:64]:
            payload = e.get("payload")
            if isinstance(payload, Mapping) and payload.get("volatility_pct") is not None:
                try:
                    v = float(payload["volatility_pct"])
                    if math.isfinite(v) and 0.00001 <= v <= 0.25:
                        vol_candidates.append(v)
                except (TypeError, ValueError):
                    pass
        if vol_candidates:
            vol_candidates.sort()
            volatility = vol_candidates[len(vol_candidates) // 2]

        context = {
            "parallax": {
                "available": isinstance(parallax_state, Mapping),
                "decision_count": ((parallax_state or {}).get("counts") or {}).get("decisions", 0)
                if isinstance((parallax_state or {}).get("counts"), Mapping) else 0,
            },
            "dreamstate": {
                "available": isinstance(dreamstate_state, Mapping),
                "candidate_count": len((dreamstate_state or {}).get("candidates", []) or [])
                if isinstance((dreamstate_state or {}).get("candidates", []), list) else 0,
            },
            "adaptive_brain": {
                "available": isinstance(brain_state, Mapping),
                "subsystem_count": (((brain_state or {}).get("architecture") or {}).get("subsystem_count"))
                if isinstance((brain_state or {}).get("architecture"), Mapping) else None,
            },
            "integration_rule": "context is visible but cannot become directional evidence unless a subsystem publishes through the SIBYL evidence contract",
        }
        built = self._build(
            chosen,
            current_price=price,
            volatility_pct=volatility,
            evidence=evidence,
            context=context,
            as_of=as_of,
        )
        built["evidence"]["ledger_count"] = len(ledger_evidence)
        built["evidence"]["revision_guard"] = "only the newest source_commit visible at as_of per named source participates"
        built["calibration"] = self.calibration(chosen)
        built["recent_forecasts"] = self.recent_forecasts(chosen, limit=12)
        return built


    def record_forecast(
        self,
        body: Mapping[str, Any],
        *,
        market_status: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(body, Mapping):
            raise ValueError("forecast must be an object")
        asset = _asset(body.get("asset"))
        observed_at = _timestamp(body.get("observed_at", _utc_now()))
        source_commit = _git_sha(body.get("source_commit"))
        if body.get("current_price") is None:
            raise ValueError("current_price is required and must be the price available at forecast observed_at")
        current_price = _finite(body.get("current_price"), "current_price", 0.0000001)
        volatility = _finite(body.get("volatility_pct", 0.0025), "volatility_pct", 0.00001, 0.25)
        horizons = body.get("horizons", DEFAULT_HORIZONS)
        if not isinstance(horizons, (list, tuple)) or not horizons:
            raise ValueError("horizons must be a non-empty list")
        parsed_horizons = sorted({_integer(x, "horizon_seconds", 1, 604800) for x in horizons})
        evidence = list(self._revision_isolate(self._evidence(asset, as_of=observed_at)))
        built = self._build(
            asset,
            current_price=current_price,
            volatility_pct=volatility,
            evidence=evidence,
            horizons=parsed_horizons,
            as_of=observed_at,
            context={"price_provenance": "explicit_as_of_input"},
        )
        semantic = {
            "schema_version": FORECAST_SCHEMA,
            "asset": asset,
            "observed_at": observed_at,
            "current_price": current_price,
            "volatility_pct": volatility,
            "source_commit": source_commit,
            "horizons": parsed_horizons,
            "evidence_ids": [e["evidence_id"] for e in evidence],
            "forecast": built,
        }
        forecast_id = _sha(_json(semantic, "forecast semantic"))
        with _LOCK, self._connect() as conn:
            conn.execute(
                """INSERT OR IGNORE INTO forecasts
                   (forecast_id, asset, observed_at, current_price, volatility_pct,
                    source_commit, forecast_json, recorded_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    forecast_id, asset, observed_at, current_price, volatility,
                    source_commit, _json(built, "forecast"), _utc_now(),
                ),
            )
        return {
            "schema_version": FORECAST_SCHEMA,
            "forecast_id": forecast_id,
            "asset": asset,
            "observed_at": observed_at,
            "source_commit": source_commit,
            "evidence_cutoff_at": observed_at,
            "forecast": built,
            "execution_authorized": False,
            "production_decision_authorized": False,
        }


    def record_outcome(self, body: Mapping[str, Any]) -> dict[str, Any]:
        if not isinstance(body, Mapping):
            raise ValueError("outcome must be an object")
        forecast_id = _text(body.get("forecast_id"), "forecast_id", 64)
        horizon = _integer(body.get("horizon_seconds"), "horizon_seconds", 1, 604800)
        observed_at = _timestamp(body.get("observed_at"))
        realized_price = _finite(body.get("realized_price"), "realized_price", 0.0000001)
        evidence = body.get("evidence", [])
        if isinstance(evidence, str):
            evidence = [evidence]
        if not isinstance(evidence, list) or not evidence or len(evidence) > 64:
            raise ValueError("evidence must contain 1-64 items")
        evidence = [_text(item, "evidence item", 700) for item in evidence]
        evidence_json = _json(evidence, "evidence")
        with _LOCK, self._connect() as conn:
            row = conn.execute("SELECT * FROM forecasts WHERE forecast_id=?", (forecast_id,)).fetchone()
            if row is None:
                raise ValueError("unknown forecast_id")
            forecast = json.loads(row["forecast_json"])
            hrow = next((x for x in forecast.get("horizons", []) if int(x.get("horizon_seconds", -1)) == horizon), None)
            if hrow is None:
                raise ValueError("horizon_seconds was not part of this forecast")
            ftime = _parse_time(row["observed_at"])
            otime = _parse_time(observed_at)
            maturity_time = ftime + timedelta(seconds=horizon)
            if otime < maturity_time:
                raise ValueError("outcome cannot precede forecast horizon maturity")
            current_price = float(row["current_price"])
            vol = float(row["volatility_pct"])
            neutral = current_price * vol * 0.25 * max(0.25, math.sqrt(horizon / 300.0))
            delta = realized_price - current_price
            realized_class = "rotation" if abs(delta) <= neutral else ("up" if delta > 0 else "down")
            probs = hrow["probabilities"]
            targets = {
                "up": 1.0 if realized_class == "up" else 0.0,
                "rotation": 1.0 if realized_class == "rotation" else 0.0,
                "down": 1.0 if realized_class == "down" else 0.0,
            }
            brier = sum((float(probs[k]) - targets[k]) ** 2 for k in targets) / 3.0
            existing = conn.execute(
                "SELECT * FROM outcomes WHERE forecast_id=? AND horizon_seconds=?",
                (forecast_id, horizon),
            ).fetchone()
            if existing is not None:
                if (
                    existing["observed_at"] == observed_at
                    and abs(float(existing["realized_price"]) - realized_price) < 1e-12
                    and existing["evidence_json"] == evidence_json
                ):
                    return self._outcome_dict(existing)
                raise ValueError("outcome is immutable for forecast_id + horizon_seconds")
            conn.execute(
                """INSERT INTO outcomes
                   (forecast_id, horizon_seconds, observed_at, realized_price,
                    realized_class, brier, evidence_json, recorded_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    forecast_id, horizon, observed_at, realized_price,
                    realized_class, brier, evidence_json, _utc_now(),
                ),
            )
            saved = conn.execute(
                "SELECT * FROM outcomes WHERE forecast_id=? AND horizon_seconds=?",
                (forecast_id, horizon),
            ).fetchone()
        result = self._outcome_dict(saved)
        result["matured_at"] = maturity_time.isoformat().replace("+00:00", "Z")
        return result

    @staticmethod
    def _outcome_dict(row: sqlite3.Row | None) -> dict[str, Any]:
        if row is None:
            raise ValueError("outcome record not found")
        return {
            "schema_version": OUTCOME_SCHEMA,
            "forecast_id": row["forecast_id"],
            "horizon_seconds": row["horizon_seconds"],
            "observed_at": row["observed_at"],
            "realized_price": row["realized_price"],
            "realized_class": row["realized_class"],
            "brier": row["brier"],
            "evidence": json.loads(row["evidence_json"]),
            "recorded_at": row["recorded_at"],
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    def calibration(self, asset: str) -> dict[str, Any]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT o.horizon_seconds, o.brier, o.realized_class, f.forecast_json
                   FROM outcomes o JOIN forecasts f ON f.forecast_id=o.forecast_id
                   WHERE f.asset=? ORDER BY o.recorded_at DESC LIMIT 1000""",
                (asset,),
            ).fetchall()
        by_h: dict[int, list[sqlite3.Row]] = {}
        for row in rows:
            by_h.setdefault(int(row["horizon_seconds"]), []).append(row)
        horizon_rows = []
        for horizon, group in sorted(by_h.items()):
            hits = 0
            confidence = []
            for row in group:
                forecast = json.loads(row["forecast_json"])
                hrow = next(x for x in forecast["horizons"] if int(x["horizon_seconds"]) == horizon)
                probs = hrow["probabilities"]
                dominant = max(probs, key=probs.get)
                hits += int(dominant == row["realized_class"])
                confidence.append(float(probs[dominant]))
            horizon_rows.append({
                "horizon_seconds": horizon,
                "n": len(group),
                "mean_brier": sum(float(r["brier"]) for r in group) / len(group),
                "dominant_hit_rate": hits / len(group),
                "mean_dominant_confidence": sum(confidence) / len(confidence),
            })
        return {
            "outcome_count": len(rows),
            "horizons": horizon_rows,
            "status": "measured" if rows else "unmeasured",
            "rule": "forecast confidence is descriptive until supported by observed calibration outcomes",
        }

    def recent_forecasts(self, asset: str, limit: int = 12) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM forecasts WHERE asset=? ORDER BY observed_at DESC LIMIT ?",
                (asset, max(1, min(50, int(limit)))),
            ).fetchall()
        out = []
        for row in rows:
            forecast = json.loads(row["forecast_json"])
            collapse = forecast.get("temporal_collapse") or {}
            out.append({
                "forecast_id": row["forecast_id"],
                "observed_at": row["observed_at"],
                "source_commit": row["source_commit"],
                "dominant_basin": collapse.get("dominant_basin"),
                "collapse_score": collapse.get("collapse_score"),
                "collapse_detected": collapse.get("collapse_detected"),
            })
        return out


    def scenario(
        self,
        body: Mapping[str, Any],
        *,
        market_status: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(body, Mapping):
            raise ValueError("scenario must be an object")
        asset = _asset(body.get("asset"))
        explicit_as_of = body.get("observed_at") is not None
        as_of = _timestamp(body.get("observed_at", _utc_now()), "observed_at")
        market_row = _market_asset(market_status, asset)
        raw_price = body.get("current_price")
        if raw_price is None and explicit_as_of:
            raise ValueError("current_price is required when scenario observed_at is supplied")
        if raw_price is None and isinstance(market_row, Mapping):
            raw_price = market_row.get("price")
        price = None if raw_price is None else _finite(raw_price, "current_price", 0.0000001)
        volatility = _finite(body.get("volatility_pct", 0.0025), "volatility_pct", 0.00001, 0.25)
        interventions = body.get("interventions", [])
        if not isinstance(interventions, list) or not interventions:
            raise ValueError("interventions must be a non-empty list")
        if len(interventions) > 32:
            raise ValueError("at most 32 interventions are allowed")

        evidence: list[dict[str, Any]] = [
            dict(e) for e in self._revision_isolate(self._evidence(asset, as_of=as_of))
        ]
        for i, raw in enumerate(interventions):
            if not isinstance(raw, Mapping):
                raise ValueError("each intervention must be an object")
            direction = _finite(raw.get("direction"), f"interventions[{i}].direction", -1.0, 1.0)
            magnitude = _finite(raw.get("magnitude", 1.0), f"interventions[{i}].magnitude", 0.0, 4.0)
            confidence = _finite(raw.get("confidence", 1.0), f"interventions[{i}].confidence", 0.0, 1.0)
            horizon = _integer(raw.get("horizon_seconds", 300), f"interventions[{i}].horizon_seconds", 1, 604800)
            domain = _text(raw.get("domain", f"counterfactual-{i}"), f"interventions[{i}].domain", 64).lower()
            source = _text(raw.get("source", "counterfactual"), f"interventions[{i}].source", 64).lower()
            target = raw.get("target_price")
            invalidation = raw.get("invalidation_price")
            evidence.append({
                "evidence_id": f"counterfactual:{i}",
                "asset": asset,
                "source": source,
                "domain": domain,
                "observed_at": as_of,
                "direction": direction,
                "magnitude": magnitude,
                "confidence": confidence,
                "horizon_seconds": horizon,
                "target_price": None if target is None else _finite(target, "target_price", 0.0),
                "invalidation_price": None if invalidation is None else _finite(invalidation, "invalidation_price", 0.0),
                "source_commit": "0" * 40,
                "payload": {"counterfactual": True},
            })
        evidence = [dict(e) for e in self._revision_isolate(evidence)]
        horizons = body.get("horizons", DEFAULT_HORIZONS)
        if not isinstance(horizons, (list, tuple)) or not horizons:
            raise ValueError("horizons must be a non-empty list")
        return self._build(
            asset,
            current_price=price,
            volatility_pct=volatility,
            evidence=evidence,
            horizons=horizons,
            context={"intervention_count": len(interventions), "scenario_as_of": as_of},
            counterfactual=True,
            as_of=as_of,
        )

