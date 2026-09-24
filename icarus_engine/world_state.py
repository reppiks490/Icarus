"""Research-only world-state graph for ICARUS.

Turns heterogeneous, authorized observations into auditable latent-state hypotheses.
It never creates market observations, never calls a broker, and never authorizes execution.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
import json
import math
from typing import Iterable, Mapping


def _canon(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _hash(value) -> str:
    return sha256(_canon(value).encode()).hexdigest()


def _finite(value, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be finite")
    return float(value)


@dataclass(frozen=True)
class Observation:
    source: str
    domain: str
    entity: str
    variable: str
    value: float
    observed_at: int
    available_at: int
    confidence: float
    provenance: str

    def __post_init__(self):
        for name in ("source", "domain", "entity", "variable", "provenance"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be non-empty")
        _finite(self.value, "value")
        if type(self.observed_at) is not int or type(self.available_at) is not int:
            raise ValueError("timestamps must be integer epoch seconds")
        if self.available_at < self.observed_at:
            raise ValueError("available_at cannot precede observed_at")
        c = _finite(self.confidence, "confidence")
        if not 0.0 <= c <= 1.0:
            raise ValueError("confidence must be in [0,1]")

    @property
    def id(self) -> str:
        return _hash(asdict(self))


@dataclass(frozen=True)
class Transmission:
    cause_variable: str
    effect_variable: str
    lag_seconds: int
    direction: int
    strength: float
    confidence: float
    mechanism: str

    def __post_init__(self):
        if self.direction not in (-1, 1):
            raise ValueError("direction must be -1 or +1")
        if type(self.lag_seconds) is not int or self.lag_seconds < 0:
            raise ValueError("lag_seconds must be >= 0")
        for name in ("strength", "confidence"):
            x = _finite(getattr(self, name), name)
            if not 0.0 <= x <= 1.0:
                raise ValueError(f"{name} must be in [0,1]")
        if not self.mechanism.strip():
            raise ValueError("mechanism is required")


class WorldStateGraph:
    """Small deterministic kernel; storage/transport stays outside this module."""

    def __init__(self, observations: Iterable[Observation] = (), transmissions: Iterable[Transmission] = ()):
        self.observations = tuple(observations)
        self.transmissions = tuple(transmissions)

    def as_of(self, ts: int) -> tuple[Observation, ...]:
        if type(ts) is not int:
            raise ValueError("ts must be an integer epoch second")
        return tuple(o for o in self.observations if o.available_at <= ts)

    def latest(self, ts: int) -> dict[tuple[str, str], Observation]:
        out: dict[tuple[str, str], Observation] = {}
        for obs in self.as_of(ts):
            key = (obs.entity, obs.variable)
            prior = out.get(key)
            if prior is None or (obs.available_at, obs.id) > (prior.available_at, prior.id):
                out[key] = obs
        return out

    def coverage(self, required_variables: Iterable[str], ts: int) -> dict:
        required = sorted(set(required_variables))
        present = {o.variable for o in self.as_of(ts)}
        missing = [v for v in required if v not in present]
        ratio = 1.0 if not required else (len(required) - len(missing)) / len(required)
        return {"required": required, "missing": missing, "coverage": ratio}

    def contradictions(self, ts: int, tolerance: float = 0.0) -> list[dict]:
        """Find same-variable observations whose signed normalized values disagree.

        This intentionally does not decide which source is correct.
        """
        tolerance = _finite(tolerance, "tolerance")
        if tolerance < 0:
            raise ValueError("tolerance must be >= 0")
        buckets: dict[tuple[str, str], list[Observation]] = {}
        for obs in self.as_of(ts):
            buckets.setdefault((obs.entity, obs.variable), []).append(obs)
        out = []
        for key, rows in sorted(buckets.items()):
            rows = sorted(rows, key=lambda o: (o.available_at, o.id))
            for i, left in enumerate(rows):
                for right in rows[i + 1:]:
                    if left.source == right.source:
                        continue
                    delta = abs(left.value - right.value)
                    if delta > tolerance and left.value * right.value < 0:
                        out.append({
                            "entity": key[0], "variable": key[1],
                            "left_id": left.id, "right_id": right.id,
                            "delta": delta,
                            "confidence_floor": min(left.confidence, right.confidence),
                        })
        return out

    def infer(self, target_variable: str, ts: int) -> dict:
        """Estimate a latent target from explicit causal/transmission edges.

        Returns uncertainty metadata instead of pretending an inferred value was observed.
        """
        latest = self.latest(ts)
        contributions = []
        for edge in self.transmissions:
            if edge.effect_variable != target_variable:
                continue
            candidates = [
                obs for (_, variable), obs in latest.items()
                if variable == edge.cause_variable and obs.available_at + edge.lag_seconds <= ts
            ]
            for obs in candidates:
                weight = edge.strength * edge.confidence * obs.confidence
                contributions.append((obs.value * edge.direction, weight, obs.id, edge.mechanism))
        denom = sum(weight for _, weight, _, _ in contributions)
        if denom <= 0:
            return {
                "target_variable": target_variable,
                "status": "unobserved_unresolved",
                "estimate": None,
                "confidence": 0.0,
                "evidence_ids": [],
                "mechanisms": [],
            }
        estimate = sum(value * weight for value, weight, _, _ in contributions) / denom
        concentration = min(1.0, denom / max(1, len(contributions)))
        dispersion = sum(weight * abs(value - estimate) for value, weight, _, _ in contributions) / denom
        confidence = concentration / (1.0 + dispersion)
        return {
            "target_variable": target_variable,
            "status": "latent_estimate",
            "estimate": estimate,
            "confidence": confidence,
            "evidence_ids": sorted({eid for _, _, eid, _ in contributions}),
            "mechanisms": sorted({m for _, _, _, m in contributions}),
        }

    def gap_map(self, required_variables: Iterable[str], ts: int) -> dict:
        cov = self.coverage(required_variables, ts)
        inferred, unresolved = {}, []
        for variable in cov["missing"]:
            result = self.infer(variable, ts)
            if result["status"] == "latent_estimate":
                inferred[variable] = result
            else:
                unresolved.append(variable)
        return {
            "coverage": cov,
            "latent": inferred,
            "unresolved": unresolved,
            "contradictions": self.contradictions(ts),
            "execution_authorized": False,
        }
