"""Leakage-aware, chronological analogue research evaluation.

A test label cannot enter memory before its outcome's recorded receipt time.
The final fold is frozen: its labels never train its own predictions.
This is a framework; it does not imply historical data has been loaded or that
an actual edge has been established.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence
import math

from .contracts import Episode, Scope, authority, timestamp
from .episodic import AnaloguePolicy, AnalogueReasoner, EpisodicStore


@dataclass(frozen=True)
class EvaluationPolicy:
    folds: int = 5
    minimum_test_episodes: int = 30
    strict_frozen_final_fold: bool = True

    def __post_init__(self) -> None:
        if type(self.folds) is not int or self.folds < 3:
            raise ValueError("need at least 3 chronological evaluation folds")
        if type(self.minimum_test_episodes) is not int or self.minimum_test_episodes < 30:
            raise ValueError("test fold must contain at least 30 episodes")


def walkforward_analogue_evaluation(
    episodes: Sequence[Episode], *,
    policy: AnaloguePolicy,
    evaluation: EvaluationPolicy = EvaluationPolicy(),
) -> dict:
    """One untouched final fold, earlier folds chronological/prequential.

    Training memory uses only label outcomes received before each decision.
    No shuffled data, future feature normalization, implicit price mapping,
    synthetic-to-real trade fill substitution or production model promotion.
    """
    if not episodes:
        raise ValueError("no empirical episodes")
    records = sorted(episodes, key=lambda ep: (timestamp(ep.situation.observed_at, "observed_at"),
                                               ep.situation.case_id))
    if len({ep.situation.case_id for ep in records}) != len(records):
        raise ValueError("duplicate event identities")
    scope: Scope = records[0].situation.scope
    if any(ep.situation.scope != scope for ep in records):
        raise ValueError("mixed scope, label, regime or execution basis")
    if any(set(ep.situation.features) != set(policy.scales) for ep in records):
        raise ValueError("training-serving feature contract mismatch")
    n = len(records)
    block = n // (evaluation.folds + 1)
    if block < max(evaluation.minimum_test_episodes, policy.min_independent_episodes):
        return {
            "status": "INSUFFICIENT_DATA", "required_minimum": max(
                evaluation.minimum_test_episodes, policy.min_independent_episodes
            ) * (evaluation.folds+1),
            "available_episodes": n, "folds": [],
            **authority(),
        }
    reports: list[dict] = []
    for fold in range(evaluation.folds):
        begin = block * (fold+1)
        end = n if fold == evaluation.folds-1 else block*(fold+2)
        training = records[:begin]
        testing = records[begin:end]
        cutoff = timestamp(testing[0].situation.received_at, "first_test_asof")
        store = EpisodicStore(":memory:")
        loaded: set[str] = set()
        # Previously matured episodes can enter model memory, regardless of
        # whether they were in chronological training or earlier test folds.
        # The last fold is frozen for protected final assessment.
        eligible_sources = training if evaluation.strict_frozen_final_fold and fold == evaluation.folds-1 else records[:end]
        errors = []
        scores = []
        abstain = 0
        for episode in testing:
            moment = timestamp(episode.situation.received_at, "test_asof")
            for prior in eligible_sources:
                pid = prior.situation.case_id
                if pid in loaded or pid == episode.situation.case_id:
                    continue
                if timestamp(prior.situation.observed_at, "observed_at") >= timestamp(episode.situation.observed_at, "observed_at"):
                    continue
                if timestamp(prior.outcome_received_at, "outcome_received_at") > moment:
                    continue
                store.add(prior)
                loaded.add(pid)
            result = AnalogueReasoner(store, policy).infer(episode.situation)
            if result["status"] != "RESEARCH_HYPOTHESIS":
                abstain += 1
                continue
            # The offline test label is accessed only after the forecast has
            # been produced. We do not claim it was a live forecast.
            p = result["empirical_hit_rate"]
            scores.append((p - episode.outcome)**2)
            errors.append((0.5 - episode.outcome)**2)
        store.close()
        evaluated = len(scores)
        report = {
            "fold": fold+1, "frozen": evaluation.strict_frozen_final_fold and fold == evaluation.folds-1,
            "train_window_episodes": len(training), "test_window_episodes": len(testing),
            "evaluated": evaluated, "abstained": abstain, "coverage": evaluated/len(testing),
            "brier": math.fsum(scores)/evaluated if evaluated else None,
            "baseline_brier_same_predictions": math.fsum(errors)/evaluated if evaluated else None,
            "status": "MEASURED_RESEARCH_ONLY" if evaluated >= evaluation.minimum_test_episodes else "INSUFFICIENT_EVALUATED_TEST_EVENTS",
        }
        reports.append(report)
    return {
        "schema_version": "icarus-intuition-walkforward-v1",
        "status": "EVALUATED_RESEARCH_ONLY" if all(r["status"] == "MEASURED_RESEARCH_ONLY" for r in reports) else "INCOMPLETE_EVIDENCE",
        "scope": {
            "asset": scope.asset, "venue": scope.venue, "chart": scope.chart,
            "execution_basis": scope.execution_basis, "regime": scope.regime,
            "target": scope.target, "feature_schema": scope.feature_schema,
        },
        "folds": reports,
        "warnings": [
            "These are retrospective research replays, not verified live or prospective calibration.",
            "Fixed 0.5 baseline is illustrative; compare against locked incumbent and venue-aware costs.",
            "No evidence of profitability is established by this evaluator.",
        ],
        **authority(),
    }
