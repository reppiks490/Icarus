"""Independent-expert reconciliation with explicit disagreement and abstention.

Fusion is research-only; the weighted consensus is *not* automatically
calibrated even when contributing forecasts have individual scorecards.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Mapping, Sequence

from .contracts import Scope, authority, check_sha, nonempty, probability, timestamp


@dataclass(frozen=True)
class ExpertClaim:
    producer: str
    scope: Scope
    issued_at: str
    received_at: str
    source_commit: str
    predicted_probability: float
    independent_roots: tuple[str, ...]
    scorecard: Mapping[str, object]
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        nonempty(self.producer, "producer")
        check_sha(self.source_commit)
        probability(self.predicted_probability, "predicted_probability")
        if timestamp(self.received_at, "received_at") < timestamp(self.issued_at, "issued_at"):
            raise ValueError("claim received before emission")
        if not self.independent_roots or not self.evidence_ids:
            raise ValueError("root ancestry and evidence mandatory")
        if len(self.independent_roots) != len(set(self.independent_roots)):
            raise ValueError("duplicate roots")
        for root in self.independent_roots:
            nonempty(root, "root")
        for evidence in self.evidence_ids:
            nonempty(evidence, "evidence")


def reconcile_experts(
    claims: Sequence[ExpertClaim], *, scope: Scope, as_of: str,
    min_forecasts: int = 60, min_sessions: int = 20,
    max_spread: float = 0.30,
) -> dict:
    """Prequalified opinions grouped by genuinely independent root ancestry.

    The scorecards must come from the held-out, matured ForecastLedger and be
    committed before the claims. Never fabricate probabilities or scorecards
    from utility or subjective agent confidence.
    """
    if type(min_forecasts) is not int or min_forecasts < 30:
        raise ValueError("min_forecasts must be >=30")
    if type(min_sessions) is not int or min_sessions < 10:
        raise ValueError("min_sessions must be >=10")
    if not 0 < max_spread <= 1:
        raise ValueError("invalid spread threshold")
    as_of_dt = timestamp(as_of, "as_of")
    candidates = []
    exclusions = []
    for c in claims:
        reason = None
        report = c.scorecard
        if c.scope != scope:
            reason = "scope_mismatch"
        elif timestamp(c.received_at, "received_at") > as_of_dt:
            reason = "claim_not_yet_received"
        elif report.get("scope") != asdict(scope) or report.get("producer") != c.producer:
            reason = "scorecard_identity_mismatch"
        elif report.get("status") != "MEASURED" or report.get("drift_state") != "NO_LARGE_SHIFT_DETECTED":
            reason = "unqualified_or_drifted_model"
        elif type(report.get("sample_count")) is not int or report["sample_count"] < min_forecasts:
            reason = "insufficient_mature_forecasts"
        elif type(report.get("independent_sessions")) is not int or report["independent_sessions"] < min_sessions:
            reason = "insufficient_independent_sessions"
        else:
            try:
                score_at = timestamp(report["as_of"], "scorecard.as_of")
                brier = probability(report["brier"], "scorecard.brier")
            except (KeyError, ValueError, TypeError):
                reason = "scorecard_missing_trustworthy_metrics"
            else:
                if score_at > timestamp(c.issued_at, "issued_at"):
                    reason = "scorecard_from_future"
                elif brier >= 0.25:  # conservative screen, NOT scientific promotion rule
                    reason = "uncompetitive_brier"
                else:
                    candidates.append((brier, c))
        if reason:
            exclusions.append({"producer": c.producer, "reason": reason})
    candidates.sort(key=lambda x: (x[0], x[1].producer))
    accepted = []
    occupied_roots: set[str] = set()
    occupied_producers: set[str] = set()
    for brier, candidate in candidates:
        roots = set(candidate.independent_roots)
        if occupied_roots.intersection(roots) or candidate.producer in occupied_producers:
            exclusions.append({"producer": candidate.producer, "reason": "shared_ancestry_or_duplicate_model"})
            continue
        accepted.append((brier, candidate))
        occupied_roots.update(roots)
        occupied_producers.add(candidate.producer)
    output = {
        "schema_version": "icarus-intuition-expert-consensus-v1",
        "status": "ABSTAIN", "reason": "insufficient_independent_experts",
        "as_of": as_of_dt.isoformat(), "scope": asdict(scope),
        "models_admitted": [c.producer for _, c in accepted],
        "models_rejected": exclusions,
        "independent_root_count": len(occupied_roots),
        "consensus": None, "disagreement": None,
        "calibration_status": "NOT_MEASURED_FOR_ENSEMBLE",
        **authority(),
    }
    if len(accepted) < 2:
        return output
    spread = max(c.predicted_probability for _, c in accepted) - min(c.predicted_probability for _, c in accepted)
    output["disagreement"] = spread
    if spread > max_spread:
        output["reason"] = "material_expert_disagreement"
        return output
    weights = [1/max(0.01, brier) for brier, _ in accepted]
    sw = math.fsum(weights)
    if max(weights)/sw > 0.65:
        output["reason"] = "one_expert_dominates"
        return output
    output["consensus"] = math.fsum(w*c.predicted_probability for w, (_, c) in zip(weights, accepted))/sw
    output["status"] = "RESEARCH_CONSENSUS_UNCALIBRATED"
    output["reason"] = "independent_prior_verified_experts;ensemble_needs_own_prequential_calibration"
    return output


@dataclass(frozen=True)
class FalsifiableHypothesis:
    """Only candidate questions; no invented likelihood or implied causal proof."""
    hypothesis_id: str
    scope: Scope
    proposition: str
    supporting_evidence: tuple[str, ...]
    contradicting_evidence: tuple[str, ...]
    falsifier: str
    evaluation_horizon_seconds: int

    def __post_init__(self) -> None:
        for attr in ("hypothesis_id", "proposition", "falsifier"):
            nonempty(getattr(self, attr), attr)
        if type(self.evaluation_horizon_seconds) is not int or self.evaluation_horizon_seconds < 1:
            raise ValueError("hypothesis requires test horizon")
        if not self.supporting_evidence:
            raise ValueError("hypothesis must have observed or source-backed support")
        if set(self.supporting_evidence) & set(self.contradicting_evidence):
            raise ValueError("same evidence cannot support and contradict unchanged claim")


def hypothesis_report(items: Sequence[FalsifiableHypothesis]) -> dict:
    return {
        "status": "RESEARCH_ONLY",
        "hypotheses": [
            {
                "id": item.hypothesis_id,
                "scope": asdict(item.scope),
                "proposition": item.proposition,
                "supporting_evidence": list(item.supporting_evidence),
                "contradicting_evidence": list(item.contradicting_evidence),
                "falsifier": item.falsifier,
                "evaluation_horizon_seconds": item.evaluation_horizon_seconds,
                "estimated_probability": None,
                "causal_status": "NOT_ESTABLISHED",
            } for item in items
        ],
        **authority(),
    }
