"""Durable episodic memory and abstaining, point-in-time analogue inference.

No fitting occurs on unresolved outcomes, future-received data, mismatched label
definitions, HA synthetic fills when evaluating real fills, or overlapping labels.
Similarity is *not* probability: the interval is an empirical diagnostic.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sqlite3
from typing import Mapping

from .contracts import Episode, Scope, Situation, authority, feature_vector, positive, timestamp


def _iso(value: str) -> str:
    return timestamp(value, "timestamp").isoformat()


def _encode(episode: Episode) -> str:
    s = episode.situation
    payload = {
        "situation": {
            "case_id": s.case_id,
            "scope": asdict(s.scope),
            "observed_at": _iso(s.observed_at),
            "received_at": _iso(s.received_at),
            "source_commit": s.source_commit,
            "features": feature_vector(s.features),
            "evidence_ids": list(s.evidence_ids),
        },
        "maturity_at": _iso(episode.maturity_at),
        "outcome_received_at": _iso(episode.outcome_received_at),
        "outcome": episode.outcome,
        "source_dataset_id": episode.source_dataset_id,
        "session_id": episode.session_id,
        "root_family": episode.root_family,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _decode(raw: str) -> Episode:
    obj = json.loads(raw)
    s = obj["situation"]
    return Episode(
        Situation(s["case_id"], Scope(**s["scope"]), s["observed_at"],
                  s["received_at"], s["source_commit"], s["features"],
                  tuple(s["evidence_ids"])),
        obj["maturity_at"], obj["outcome_received_at"], obj["outcome"],
        obj["source_dataset_id"], obj["session_id"], obj["root_family"],
    )


class EpisodicStore:
    """Append-only SQLite WAL memory; no strategy, scheduler or broker hooks."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path))
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS episodes (
                case_id TEXT PRIMARY KEY, asset TEXT NOT NULL,
                observed_at TEXT NOT NULL, received_at TEXT NOT NULL,
                maturity_at TEXT NOT NULL, outcome_received_at TEXT NOT NULL,
                content TEXT NOT NULL, digest TEXT NOT NULL
            )
        """)
        self._conn.execute("CREATE INDEX IF NOT EXISTS idx_episodes_asof "
                           "ON episodes(asset, outcome_received_at, maturity_at)")
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def add(self, episode: Episode) -> bool:
        raw = _encode(episode)
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        row = self._conn.execute("SELECT digest FROM episodes WHERE case_id=?",
                                 (episode.situation.case_id,)).fetchone()
        if row:
            if row[0] != digest:
                raise ValueError("immutable case identity collision")
            return False
        with self._conn:
            self._conn.execute(
                "INSERT INTO episodes VALUES (?,?,?,?,?,?,?,?)",
                (episode.situation.case_id, episode.situation.scope.asset,
                 _iso(episode.situation.observed_at), _iso(episode.situation.received_at),
                 _iso(episode.maturity_at), _iso(episode.outcome_received_at), raw, digest),
            )
        return True

    def eligible(self, query: Situation) -> list[Episode]:
        """Only memory already observable at the *query receipt* boundary.

        Network intake must stamp received_at itself; callers of this trusted
        research API are responsible for authoritative input timestamps.
        """
        boundary = _iso(query.received_at)
        query_observed = _iso(query.observed_at)
        cases: list[Episode] = []
        rows = self._conn.execute(
            "SELECT content,digest FROM episodes WHERE asset=? "
            "AND observed_at<? AND received_at<=? "
            "AND maturity_at<=? AND outcome_received_at<=?",
            (query.scope.asset, query_observed, boundary, boundary, boundary),
        )
        for raw, digest in rows:
            if hashlib.sha256(raw.encode("utf-8")).hexdigest() != digest:
                raise ValueError("episode integrity failure")
            item = _decode(raw)
            # Full identity prevents confusing real vs synthetic fills, even
            # when the source market and chart look superficially identical.
            if item.situation.scope != query.scope or item.situation.source_commit != query.source_commit:
                continue
            if set(item.situation.features) != set(query.features):
                continue
            if item.situation.case_id == query.case_id:
                continue
            cases.append(item)
        return cases


def _wilson(hit_rate: float, n: float, z: float = 1.959963984540054) -> tuple[float, float]:
    # For weighted evidence n is conservative session/effective count; interval
    # is explicitly a heuristic diagnostic, NOT a coverage guarantee.
    if n <= 0:
        raise ValueError("no support for uncertainty interval")
    denom = 1 + z*z/n
    center = (hit_rate + z*z/(2*n)) / denom
    margin = z * math.sqrt((hit_rate*(1-hit_rate) + z*z/(4*n))/n) / denom
    return max(0.0, center-margin), min(1.0, center+margin)


@dataclass(frozen=True)
class AnaloguePolicy:
    """Precommitted feature scales/weights, fixed before held-out evaluation."""
    scales: Mapping[str, float]
    weights: Mapping[str, float]
    min_independent_episodes: int = 60
    min_sessions: int = 20
    max_distance: float = 2.0
    half_life_days: float = 90.0
    max_interval_width: float = 0.40

    def __post_init__(self) -> None:
        if not self.scales or set(self.scales) != set(self.weights):
            raise ValueError("feature scale/weight keys must match")
        for key, value in self.scales.items():
            positive(value, f"scale.{key}")
        for key, value in self.weights.items():
            positive(value, f"weight.{key}")
        if type(self.min_independent_episodes) is not int or self.min_independent_episodes < 30:
            raise ValueError("must require at least 30 independent episodes")
        if type(self.min_sessions) is not int or self.min_sessions < 10:
            raise ValueError("must require at least 10 independent sessions")
        positive(self.max_distance, "max_distance")
        positive(self.half_life_days, "half_life_days")
        if not 0 < self.max_interval_width <= 1:
            raise ValueError("max_interval_width outside (0, 1]")


def _overlaps(a: Episode, b: Episode) -> bool:
    sa, ea = timestamp(a.situation.observed_at, "start"), timestamp(a.maturity_at, "maturity")
    sb, eb = timestamp(b.situation.observed_at, "start"), timestamp(b.maturity_at, "maturity")
    return sa < eb and sb < ea


class AnalogueReasoner:
    def __init__(self, memory: EpisodicStore, policy: AnaloguePolicy):
        self.memory = memory
        self.policy = policy

    def infer(self, situation: Situation) -> dict:
        """A causal research diagnosis, never permission to place an order."""
        feature_vector(situation.features)
        if set(situation.features) != set(self.policy.scales):
            raise ValueError("unrecognized or missing feature schema keys")
        candidates: list[tuple[float, Episode, float]] = []
        asof = timestamp(situation.received_at, "received_at")
        total_weight = sum(self.policy.weights.values())
        for episode in self.memory.eligible(situation):
            squared = sum(
                self.policy.weights[k] *
                ((float(situation.features[k])-float(episode.situation.features[k]))
                 /self.policy.scales[k])**2
                for k in self.policy.scales
            ) / total_weight
            distance = math.sqrt(squared)
            if distance > self.policy.max_distance:
                continue
            age_days = max(0.0, (asof-timestamp(episode.maturity_at, "maturity_at")).total_seconds()/86400.0)
            weight = math.exp(-0.5*distance*distance) * 0.5**(age_days/self.policy.half_life_days)
            candidates.append((weight, episode, distance))
        candidates.sort(key=lambda item: (-item[0], item[1].situation.case_id))
        # All detected analogues remain inspectable; independent events only
        # contribute to inference. Greedy deduplication is fixed/deterministic.
        selected: list[tuple[float, Episode, float]] = []
        for proposal in candidates:
            if not any(_overlaps(proposal[1], chosen[1]) for chosen in selected):
                selected.append(proposal)
        sessions = {ep.session_id for _, ep, _ in selected}
        families = {ep.root_family for _, ep, _ in selected}
        support = {
            "raw_analogues": len(candidates), "independent_episodes": len(selected),
            "independent_sessions": len(sessions), "source_families": sorted(families),
            "overlap_purged": len(candidates)-len(selected),
        }
        result = {
            "schema_version": "icarus-intuition-omega-v1",
            "case_id": situation.case_id,
            "scope": asdict(situation.scope),
            "as_of": _iso(situation.received_at),
            "status": "ABSTAIN",
            "reason": "insufficient_independent_history",
            "empirical_hit_rate": None,
            "uncertainty_interval": None,
            "effective_weighted_n": 0.0,
            "support": support,
            "closest_case_ids": [ep.situation.case_id for _, ep, _ in selected[:8]],
            "uncertainty_semantics": "weighted descriptive Wilson heuristic; not a calibrated forward probability",
            **authority(),
        }
        if len(selected) < self.policy.min_independent_episodes or len(sessions) < self.policy.min_sessions:
            return result
        sw = math.fsum(w for w, _, _ in selected)
        sw2 = math.fsum(w*w for w, _, _ in selected)
        if sw <= 0 or sw2 <= 0:
            result["reason"] = "vanishing_similarity"
            return result
        neff = min(float(len(selected)), sw*sw/sw2)
        result["effective_weighted_n"] = neff
        if neff < self.policy.min_independent_episodes:
            result["reason"] = "low_effective_sample_size"
            return result
        rate = math.fsum(w*ep.outcome for w, ep, _ in selected)/sw
        lo, hi = _wilson(rate, min(neff, float(len(sessions))))
        result["empirical_hit_rate"] = rate
        result["uncertainty_interval"] = [lo, hi]
        if hi-lo > self.policy.max_interval_width:
            result["reason"] = "imprecise_interval"
            return result
        if min(dist for _, _, dist in selected) > self.policy.max_distance * 0.75:
            result["reason"] = "out_of_distribution"
            return result
        result["status"] = "RESEARCH_HYPOTHESIS"
        result["reason"] = "historical_analogue_supported_not_prospectively_calibrated"
        return result
