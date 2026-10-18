"""ICARUS Intuition Ω: research-only, abstaining, point-in-time market cognition.

No module in this package has broker, order, execution, model promotion, or
production-strategy authority.
"""
from .contracts import Episode, Scope, Situation, authority
from .episodic import AnaloguePolicy, AnalogueReasoner, EpisodicStore
from .calibration import Forecast, ForecastLedger, Resolution, calibration_report
from .providers import FeedObservation, PROVIDER_DOMAINS, assemble_situation

__all__ = [
    "Episode", "Scope", "Situation", "authority",
    "AnaloguePolicy", "AnalogueReasoner", "EpisodicStore",
    "Forecast", "ForecastLedger", "Resolution", "calibration_report",
    "FeedObservation", "PROVIDER_DOMAINS", "assemble_situation",
]
