"""Evidence-gated champion/challenger selection for ICARUS shadow routing.

This module never promotes production or execution authority. It ranks only
comparable, fully-settled research/shadow candidates and exposes exact blockers.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

DEFAULT_MIN_SETTLED = 30
DEFAULT_Z = 1.959963984540054


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    return float(value)


def _int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    return int(value)


def wilson_interval(successes: int, total: int, z: float = DEFAULT_Z) -> tuple[float, float]:
    """Wilson score interval for a Bernoulli success proportion."""
    successes = _int(successes, "successes")
    total = _int(total, "total")
    z = _finite(z, "z")
    if total <= 0:
        raise ValueError("total must be > 0")
    if not 0 <= successes <= total:
        raise ValueError("successes must satisfy 0 <= successes <= total")
    if z <= 0:
        raise ValueError("z must be > 0")

    phat = successes / total
    z2 = z * z
    denom = 1.0 + z2 / total
    center = (phat + z2 / (2.0 * total)) / denom
    radius = (
        z
        * math.sqrt((phat * (1.0 - phat) / total) + (z2 / (4.0 * total * total)))
        / denom
    )
    return max(0.0, center - radius), min(1.0, center + radius)


@dataclass(frozen=True)
class TournamentCandidate:
    candidate_id: str
    asset: str
    regime: str
    success_definition: str
    horizon_seconds: int
    settled: int
    successes: int
    success_rate: float
    brier_score: float | None
    lower_95: float
    upper_95: float


def _candidate(row: Mapping[str, Any], min_settled: int) -> tuple[TournamentCandidate | None, list[str]]:
    blockers: list[str] = []

    candidate_id = str(row.get("candidate_id") or "").strip()
    asset = str(row.get("asset") or "").strip().upper()
    regime = str(row.get("regime") or "").strip()
    success_definition = str(row.get("success_definition") or "").strip()
    horizon = row.get("horizon_seconds")
    settled = row.get("settled")
    successes = row.get("successes")
    rate = row.get("success_rate")
    brier = row.get("brier_score")

    if not candidate_id:
        blockers.append("candidate_id missing")
    if not asset:
        blockers.append("asset missing")
    if not regime:
        blockers.append("regime missing")
    if not success_definition:
        blockers.append("success_definition missing")
    if isinstance(horizon, bool) or not isinstance(horizon, int) or horizon <= 0:
        blockers.append("horizon_seconds invalid")
    if isinstance(settled, bool) or not isinstance(settled, int) or settled < min_settled:
        blockers.append(f"settled sample below minimum {min_settled}")
    if isinstance(successes, bool) or not isinstance(successes, int):
        blockers.append("successes invalid")
    elif isinstance(settled, int) and not 0 <= successes <= settled:
        blockers.append("successes outside [0, settled]")
    if isinstance(rate, bool) or not isinstance(rate, (int, float)) or not math.isfinite(rate) or not 0.0 <= float(rate) <= 1.0:
        blockers.append("success_rate invalid")
    if brier is not None and (
        isinstance(brier, bool) or not isinstance(brier, (int, float)) or not math.isfinite(brier) or float(brier) < 0.0
    ):
        blockers.append("brier_score invalid")
    if row.get("closed_regime_sample") is not True:
        blockers.append("regime sample not closed")
    if row.get("outcome_coverage") != 1.0:
        blockers.append("outcome coverage is not 100%")

    if blockers:
        return None, blockers

    lower, upper = wilson_interval(int(successes), int(settled))
    return TournamentCandidate(
        candidate_id=candidate_id,
        asset=asset,
        regime=regime,
        success_definition=success_definition,
        horizon_seconds=int(horizon),
        settled=int(settled),
        successes=int(successes),
        success_rate=float(rate),
        brier_score=None if brier is None else float(brier),
        lower_95=lower,
        upper_95=upper,
    ), []


def select_shadow_champion(
    rows: Iterable[Mapping[str, Any]],
    *,
    incumbent_id: str | None = None,
    min_settled: int = DEFAULT_MIN_SETTLED,
    min_lower_bound_improvement: float = 0.01,
) -> dict[str, Any]:
    """Select one evidence-qualified shadow champion from a comparable scope.

    Scope is exact: asset + regime + success definition + horizon. Mixed scopes
    fail closed rather than being pooled. Hysteresis keeps an incumbent unless
    the challenger's lower confidence bound clears the incumbent's by the
    configured margin.
    """
    if isinstance(min_settled, bool) or not isinstance(min_settled, int) or min_settled < 10:
        raise ValueError("min_settled must be an integer >= 10")
    margin = _finite(min_lower_bound_improvement, "min_lower_bound_improvement")
    if margin < 0.0 or margin > 1.0:
        raise ValueError("min_lower_bound_improvement must be within [0,1]")

    accepted: list[TournamentCandidate] = []
    rejected: list[dict[str, Any]] = []
    scopes: set[tuple[str, str, str, int]] = set()

    for row in rows:
        candidate, blockers = _candidate(row, min_settled)
        if candidate is None:
            rejected.append({
                "candidate_id": str(row.get("candidate_id") or ""),
                "blockers": blockers,
            })
            continue
        accepted.append(candidate)
        scopes.add((candidate.asset, candidate.regime, candidate.success_definition, candidate.horizon_seconds))

    if not accepted:
        return {
            "status": "NO_ELIGIBLE_CANDIDATES",
            "shadow_champion": None,
            "eligible": [],
            "rejected": rejected,
            "scope": None,
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    if len(scopes) != 1:
        return {
            "status": "MIXED_SCOPE_BLOCKED",
            "shadow_champion": None,
            "eligible": [],
            "rejected": rejected,
            "scope_count": len(scopes),
            "execution_authorized": False,
            "production_decision_authorized": False,
        }

    accepted.sort(
        key=lambda c: (
            -c.lower_95,
            c.brier_score if c.brier_score is not None else float("inf"),
            -c.settled,
            c.candidate_id,
        )
    )
    challenger = accepted[0]
    incumbent = next((c for c in accepted if c.candidate_id == incumbent_id), None) if incumbent_id else None

    selected = challenger
    decision = "BEST_EVIDENCE_SELECTED"
    if incumbent is not None and challenger.candidate_id != incumbent.candidate_id:
        if challenger.lower_95 < incumbent.lower_95 + margin:
            selected = incumbent
            decision = "INCUMBENT_RETAINED_BY_HYSTERESIS"
        else:
            decision = "CHALLENGER_SUPERSEDES_INCUMBENT"

    scope = next(iter(scopes))
    return {
        "status": "SHADOW_CHAMPION_SELECTED",
        "selection_mode": "EMPIRICAL_SHADOW_ONLY",
        "decision": decision,
        "shadow_champion": selected.candidate_id,
        "scope": {
            "asset": scope[0],
            "regime": scope[1],
            "success_definition": scope[2],
            "horizon_seconds": scope[3],
        },
        "eligible": [
            {
                "candidate_id": c.candidate_id,
                "settled": c.settled,
                "successes": c.successes,
                "success_rate": c.success_rate,
                "lower_95": c.lower_95,
                "upper_95": c.upper_95,
                "brier_score": c.brier_score,
            }
            for c in accepted
        ],
        "rejected": rejected,
        "execution_authorized": False,
        "production_decision_authorized": False,
        "rule": "Evidence-qualified shadow selection only; no production or broker authority.",
    }
