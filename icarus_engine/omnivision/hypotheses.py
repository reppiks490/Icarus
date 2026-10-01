"""Deterministic, research-only hypothesis generation for OMNIVISION."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re
from typing import Mapping

_HASH = re.compile(r"^[0-9a-f]{64}$")


def _canon(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


def _text(value, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{name} must be non-empty")
    return value


def _hash(value, name: str) -> str:
    if type(value) is not str or not _HASH.fullmatch(value):
        raise ValueError(f"{name} must be lowercase SHA-256")
    return value


@dataclass(frozen=True)
class Hypothesis:
    hypothesis_id: str
    kind: str
    asset: str
    target: str
    mechanism: str
    expected_lag_seconds: int
    horizon_seconds: int
    required_variables: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    falsification_rules: tuple[str, ...]
    eligible_regimes: tuple[str, ...]
    decision_at: int
    execution_authorized: bool = False

    def __post_init__(self):
        _hash(self.hypothesis_id, "hypothesis_id")
        if self.kind not in ("latent_gap", "contradiction"):
            raise ValueError("unsupported hypothesis kind")
        for name in ("asset", "target", "mechanism"):
            _text(getattr(self, name), name)
        for name in ("expected_lag_seconds", "horizon_seconds", "decision_at"):
            value = getattr(self, name)
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be a non-negative integer")
        for name in ("required_variables", "evidence_ids", "falsification_rules", "eligible_regimes"):
            value = getattr(self, name)
            if type(value) is not tuple or not value:
                raise ValueError(f"{name} must be a non-empty tuple")
        for variable in self.required_variables:
            _text(variable, "required variable")
        if len(set(self.evidence_ids)) != len(self.evidence_ids):
            raise ValueError("evidence_ids must be unique")
        for evidence_id in self.evidence_ids:
            _hash(evidence_id, "evidence_id")
        for rule in self.falsification_rules:
            _text(rule, "falsification rule")
        for regime in self.eligible_regimes:
            _text(regime, "eligible regime")
        if self.execution_authorized is not False:
            raise ValueError("hypotheses never authorize execution")


def _build(**values) -> Hypothesis:
    identity = {k: v for k, v in values.items() if k != "hypothesis_id"}
    return Hypothesis(hypothesis_id=_digest(identity), **identity)


def forge_hypotheses(gap_map: Mapping, *, asset: str, decision_at: int) -> tuple[Hypothesis, ...]:
    if not isinstance(gap_map, Mapping):
        raise ValueError("gap_map must be a mapping")
    _text(asset, "asset")
    if type(decision_at) is not int or decision_at < 0:
        raise ValueError("decision_at must be a non-negative integer")
    if gap_map.get("execution_authorized") is not False:
        raise ValueError("gap map must be research-only")

    out = []
    latent = gap_map.get("latent", {})
    if not isinstance(latent, Mapping):
        raise ValueError("latent must be a mapping")
    for target in sorted(latent):
        value = latent[target]
        if not isinstance(value, Mapping) or value.get("status") != "latent_estimate":
            continue
        evidence_ids = tuple(sorted(set(value.get("evidence_ids", ()))))
        mechanisms = tuple(sorted(set(value.get("mechanisms", ()))))
        if not evidence_ids or not mechanisms:
            continue
        out.append(_build(
            kind="latent_gap",
            asset=asset,
            target=_text(target, "target"),
            mechanism=" | ".join(mechanisms),
            expected_lag_seconds=0,
            horizon_seconds=0,
            required_variables=(target,),
            evidence_ids=evidence_ids,
            falsification_rules=("placebo_shift_must_not_match", "walk_forward_must_hold"),
            eligible_regimes=("all",),
            decision_at=decision_at,
            execution_authorized=False,
        ))

    contradictions = gap_map.get("contradictions", ())
    if not isinstance(contradictions, (list, tuple)):
        raise ValueError("contradictions must be a sequence")
    for item in contradictions:
        if not isinstance(item, Mapping):
            raise ValueError("contradiction must be a mapping")
        variable = _text(item.get("variable"), "variable")
        entity = _text(item.get("entity"), "entity")
        evidence_ids = tuple(sorted({_hash(item.get("left_id"), "left_id"),
                                     _hash(item.get("right_id"), "right_id")}))
        out.append(_build(
            kind="contradiction",
            asset=asset,
            target=variable,
            mechanism=f"cross_source_contradiction:{entity}:{variable}",
            expected_lag_seconds=0,
            horizon_seconds=0,
            required_variables=(variable,),
            evidence_ids=evidence_ids,
            falsification_rules=("source_disagreement_must_resolve_or_predict_distinct_outcomes",),
            eligible_regimes=("all",),
            decision_at=decision_at,
            execution_authorized=False,
        ))

    return tuple(sorted(out, key=lambda item: item.hypothesis_id))
