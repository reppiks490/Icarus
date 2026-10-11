from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .contracts import DataClass


_TRACKING_KEYS = frozenset(
    {
        "fpr",
        "ref",
        "referrer",
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
    }
)


@dataclass(frozen=True, slots=True)
class NormalizedURL:
    original_url: str
    identity_url: str
    domain: str


def normalize_url(url: str) -> NormalizedURL:
    if not isinstance(url, str) or not url.strip():
        raise ValueError("URL must be a non-empty string")

    original = url
    parsed = urlsplit(url.strip())
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("only absolute http(s) URLs are supported")

    host = parsed.hostname.lower().rstrip(".")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("invalid URL port") from exc

    include_port = port is not None and not (
        (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    )
    display_host = f"[{host}]" if ":" in host and not host.startswith("[") else host
    netloc = f"{display_host}:{port}" if include_port else display_host

    retained = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.casefold() not in _TRACKING_KEYS
    ]
    retained.sort(key=lambda item: (item[0], item[1]))
    query = urlencode(retained, doseq=True)
    identity = urlunsplit((scheme, netloc, parsed.path or "", query, ""))
    domain = host[4:] if host.startswith("www.") else host
    return NormalizedURL(original_url=original, identity_url=identity, domain=domain)


def normalize_name(name: str) -> str:
    if not isinstance(name, str):
        raise ValueError("name must be a string")
    value = unicodedata.normalize("NFKC", name).strip()
    while value and unicodedata.category(value[0]).startswith("S"):
        value = value[1:].lstrip()
    return re.sub(r"\s+", " ", value).strip()


def canonical_provider_name(name: str, domain: str) -> str:
    normalized = normalize_name(name)
    if normalized:
        return normalized
    if not isinstance(domain, str) or not domain.strip():
        raise ValueError("provider name or domain is required")
    value = domain.strip().lower().rstrip(".")
    return value[4:] if value.startswith("www.") else value


def candidate_identity(*, canonical_name: str, identity_url: str, capability_kind: str) -> str:
    normalized_name = normalize_name(canonical_name).casefold()
    normalized_kind = normalize_name(capability_kind).casefold()
    if not normalized_name or not identity_url or not normalized_kind:
        raise ValueError("candidate identity components must be non-empty")
    material = "\0".join((normalized_name, identity_url, normalized_kind))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def classify_data_class(category: str, description: str) -> tuple[DataClass, ...]:
    text = f"{category or ''} {description or ''}".casefold()
    matches: list[DataClass] = []

    rules: tuple[tuple[DataClass, tuple[str, ...]], ...] = (
        (DataClass.MARKET_MICROSTRUCTURE, ("order book", "bid/ask", "market depth", "level 2", "level ii")),
        (
            DataClass.DERIVATIVES_POSITIONING,
            (
                "cftc",
                "commitment of traders",
                "futures positioning",
                "open interest",
                "funding rate",
                "liquidation",
                "implied volatility",
                "options flow",
            ),
        ),
        (DataClass.CORPORATE_EVENT, ("sec filing", "edgar", "8-k", "10-k", "10-q", "form 4", "13f", "13d", "13g", "earnings transcript")),
        (DataClass.FUNDAMENTAL, ("financial statement", "balance sheet", "income statement", "cash flow", "fundamental")),
        (DataClass.MACRO, ("fred", "economic data", "cpi", "inflation", "gdp", "payroll", "unemployment")),
        (DataClass.RATES_CREDIT, ("interest rate", "yield curve", "treasury yield", "credit spread", "bond yield")),
        (DataClass.GEOPOLITICAL, ("geopolitical", "sanctions", "conflict", "war risk")),
        (DataClass.NEWS, ("news", "headline", "press release")),
        (DataClass.SOCIAL, ("reddit", "twitter", "x.com", "social media", "social sentiment")),
        (DataClass.SEARCH_ATTENTION, ("google trends", "search trend", "search interest", "trending searches")),
        (DataClass.REGULATORY, ("regulatory", "regulator", "enforcement", "court filing", "litigation")),
        (DataClass.SUPPLY_CHAIN, ("supply chain", "shipping", "port congestion", "freight", "bill of lading")),
        (DataClass.PROCUREMENT, ("procurement", "government contract", "tender", "usaspend", "sam.gov")),
        (DataClass.WEATHER, ("weather", "climate", "metar", "forecast", "wildfire")),
        (DataClass.LABOR, ("job posting", "hiring", "layoff", "employment", "wage", "labor")),
        (DataClass.CONSUMER_ECOMMERCE, ("e-commerce", "ecommerce", "shopping", "product price", "best seller", "inventory")),
        (DataClass.HOUSING_REAL_ESTATE, ("real estate", "housing", "rent", "foreclosure", "property listing")),
        (DataClass.TRAVEL_MOBILITY, ("travel", "flight", "hotel", "airbnb", "mobility", "aircraft")),
        (DataClass.CRYPTO_CHAIN, ("on-chain", "blockchain", "wallet", "token flow", "defi")),
        (DataClass.RESEARCH_DOCUMENT, ("research paper", "scholarly", "patent", "citation", "clinical trial")),
        (DataClass.MARKET_PRICE, ("ohlcv", "stock quote", "market price", "price history", "forex quote")),
        (DataClass.SOFTWARE_CAPABILITY, ("mcp server", "developer tool", "coding assistant", "ai tool")),
    )

    for data_class, needles in rules:
        if any(needle in text for needle in needles):
            matches.append(data_class)

    if not matches:
        return (DataClass.OTHER,)
    return tuple(dict.fromkeys(matches))


__all__ = [
    "NormalizedURL",
    "candidate_identity",
    "canonical_provider_name",
    "classify_data_class",
    "normalize_name",
    "normalize_url",
]
