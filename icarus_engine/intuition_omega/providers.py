"""Permission-aware mega-provider intake gate for Intuition Ω.

This is an adapter contract and source registry, NOT a scraper, API client,
credentials manager, entitlement claim, or assertion that any feed is active.
Only previously authorized research observations may enter. Existing collectors
remain the owners of acquisition, archives, licensing, and provider quotas.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import math
from typing import Iterable

from .contracts import Scope, Situation, check_sha, nonempty, positive, timestamp


# Capability categories are proposed uses, not assertions of user entitlement.
PROVIDER_DOMAINS = {
    "databento": ("futures", "microstructure", "depth", "historical"),
    "tiingo": ("equities", "prices", "news", "fx"),
    "fmp": ("fundamentals", "events", "equities", "macro"),
    "eodhd": ("equities", "prices", "corporate_actions"),
    "fred": ("macro", "vintages"), "alfred": ("macro", "vintages"),
    "cftc": ("positioning", "cot"), "sec_edgar": ("filings", "ownership"),
    "us_treasury": ("yield_curve", "rates", "fiscal"),
    "federal_reserve": ("macro", "central_bank"),
    "bls": ("labor", "inflation", "macro"),
    "bea": ("gdp", "income", "macro"), "census": ("economic_activity",),
    "eia": ("energy", "inventory", "macro"),
    "noaa": ("weather", "energy", "agriculture"),
    "usda": ("agriculture", "crop", "wasde"),
    "finra": ("short_volume", "market_activity"),
    "nasdaq_data_link": ("financial_datasets",),
    "cboe": ("volatility", "options"),
    "cme": ("futures", "options", "microstructure"),
    "nasdaq": ("equities", "microstructure"),
    "opra": ("options", "trades", "quotes"),
    "alpaca": ("market_data", "equities"),
    "massive": ("equities", "options", "prices"),
    "intrinio": ("fundamentals", "market_data"),
    "twelve_data": ("prices", "market_data"),
    "quiver": ("policy", "ownership", "alternative"),
    "bybit": ("crypto", "derivatives", "funding", "oi"),
    "coingecko": ("crypto", "market_activity"),
    "blockscout": ("blockchain", "onchain"),
    "binance": ("crypto", "trades", "derivatives"),
    "kraken": ("crypto", "trades"),
    "zacks": ("estimates", "fundamentals"),
    "tickerlayer": ("prices", "market_data"),
    "factorweave": ("factor_data", "equities"),
    "economist_graphs": ("politics", "macro"),
    "exum": ("crypto", "market_structure"),
    "unusual_whales": ("options", "flow", "ownership"),
    "exa": ("research", "documents"), "tavily": ("research", "documents"),
    "parallel_search": ("research", "documents"),
    "firecrawl": ("research", "documents"),
    "datablue": ("research", "documents"),
    "consensus": ("research", "papers"),
    "scite": ("research", "citation_context"),
    "tick_stream": ("market_data", "ticks"),
}

VINTAGE_DOMAINS = frozenset({
    "fred", "alfred", "bls", "bea", "census", "eia", "federal_reserve",
    "us_treasury", "usda", "cftc", "fmp",
})


@dataclass(frozen=True)
class FeedObservation:
    """Explicit semantics prevent turning a proxy into observed order flow."""
    provider: str
    dataset_id: str
    feature_name: str
    feature_value: float
    observed_at: str
    received_at: str
    local_receipt_at: str
    source_commit: str
    source_record_id: str
    root_family: str
    evidence_kind: str  # observed/derived/reconstructed/inferred/unavailable
    vintage_id: str | None
    granularity: str
    entitlement_verified: bool
    research_use_authorized: bool
    quality_checked: bool

    def __post_init__(self) -> None:
        if self.provider not in PROVIDER_DOMAINS:
            raise ValueError("provider not registered")
        for field in ("dataset_id", "feature_name", "source_record_id", "root_family"):
            nonempty(getattr(self, field), field)
        check_sha(self.source_commit)
        if self.evidence_kind not in ("observed", "derived", "reconstructed", "inferred", "unavailable"):
            raise ValueError("unsupported evidence kind")
        if self.granularity not in ("tick", "order_book", "bar", "daily", "periodic", "event", "text"):
            raise ValueError("unknown data granularity")
        if isinstance(self.feature_value, bool) or not isinstance(self.feature_value, (int, float)) or not math.isfinite(float(self.feature_value)):
            raise ValueError("feature must be a finite number")
        obs = timestamp(self.observed_at, "observed_at")
        received = timestamp(self.received_at, "received_at")
        local = timestamp(self.local_receipt_at, "local_receipt_at")
        if received < obs:
            raise ValueError("receipt cannot precede observation")
        if local < received:
            raise ValueError("local engine receipt cannot precede source receipt")
        if self.provider in VINTAGE_DOMAINS and not self.vintage_id:
            raise ValueError("macro/positioning data requires explicit vintage/release id")
        if self.vintage_id is not None:
            nonempty(self.vintage_id, "vintage_id")
        if self.evidence_kind == "unavailable":
            raise ValueError("unavailable data cannot create numeric features")
        if not all((type(self.entitlement_verified) is bool,
                    type(self.research_use_authorized) is bool,
                    type(self.quality_checked) is bool)):
            raise ValueError("verification flags must be boolean")

    @property
    def is_admitted(self) -> bool:
        return self.entitlement_verified and self.research_use_authorized and self.quality_checked


def assemble_situation(
    *, case_id: str, scope: Scope, observed_at: str, as_of: str,
    source_commit: str, observations: Iterable[FeedObservation],
    max_age_seconds: dict[str, float],
) -> dict:
    """Fuse only explicitly verified, contemporaneously knowable numeric data.

    Model feature contracts must be version-locked outside this function.
    No silent backward fill, cross-venue substitution, or invented microstructure.
    """
    cutoff = timestamp(as_of, "as_of")
    event = timestamp(observed_at, "observed_at")
    if cutoff < event:
        raise ValueError("forecast cannot precede situation event")
    check_sha(source_commit)
    features: dict[str, float] = {}
    refs: list[str] = []
    admitted: list[dict] = []
    rejected: list[dict] = []
    families: set[str] = set()
    for obs in observations:
        key = f"{obs.provider}:{obs.feature_name}"
        issue = None
        age = (cutoff-timestamp(obs.observed_at, "observed_at")).total_seconds()
        max_age = max_age_seconds.get(obs.provider)
        if not obs.is_admitted:
            issue = "entitlement_rights_or_quality_unverified"
        elif max_age is None:
            issue = "no_committed_freshness_policy"
        elif positive(max_age, f"age.{obs.provider}") < age:
            issue = "stale"
        elif age < 0 or timestamp(obs.received_at, "received_at") > cutoff or timestamp(obs.local_receipt_at, "local_receipt_at") > cutoff:
            issue = "not_yet_known_at_forecast_time"
        elif key in features:
            issue = "duplicate_feature_requires_explicit_selection"
        if issue:
            rejected.append({"feature": key, "reason": issue})
            continue
        features[key] = float(obs.feature_value)
        refs.append(f"{obs.provider}:{obs.dataset_id}:{obs.source_record_id}:{obs.source_commit}")
        families.add(obs.root_family)
        admitted.append({"feature": key, "kind": obs.evidence_kind,
                         "granularity": obs.granularity, "vintage_id": obs.vintage_id})
    if not features:
        return {"status": "ABSTAIN", "reason": "no_authorized_point_in_time_features",
                "rejected": rejected, "admitted": admitted,
                "execution_authorized": False, "production_decision_authorized": False}
    situation = Situation(case_id, scope, observed_at, as_of, source_commit,
                          features, tuple(refs))
    return {
        "status": "RESEARCH_INPUT", "situation": situation,
        "admitted": admitted, "rejected": rejected,
        "effective_source_families": sorted(families),
        "execution_authorized": False, "production_decision_authorized": False,
    }
