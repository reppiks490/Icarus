from __future__ import annotations

import re

import pytest

from icarus_engine.discovery_registry.contracts import DataClass
from icarus_engine.discovery_registry.normalize import (
    candidate_identity,
    canonical_provider_name,
    classify_data_class,
    normalize_name,
    normalize_url,
)


@pytest.mark.parametrize("url", ["https://user:secret@example.com/data", "https://token@example.com/data",
    "https://example.com/data?api_key=SECRET_SENTINEL", "https://example.com/data?access_token=SECRET_SENTINEL"])
def test_credential_bearing_urls_are_rejected_not_persisted(url):
    with pytest.raises(ValueError, match="credential"):
        normalize_url(url)


def test_normalize_url_drops_only_known_tracking_parameters():
    got = normalize_url("https://apify.com/acme/tool?fpr=abc&symbol=NQ&utm_source=x#top")
    assert got.identity_url == "https://apify.com/acme/tool?symbol=NQ"
    assert got.original_url.endswith("#top")


def test_tracking_variants_have_same_identity():
    a = normalize_url("https://apify.com/acme/tool?fpr=a")
    b = normalize_url("https://apify.com/acme/tool?fpr=b&utm_campaign=c")
    assert a.identity_url == b.identity_url


def test_meaningful_query_parameter_is_preserved():
    got = normalize_url("HTTPS://EXAMPLE.COM:443/path?symbol=NQ&ref=x")
    assert got.identity_url == "https://example.com/path?symbol=NQ"


def test_non_http_url_fails_closed():
    with pytest.raises(ValueError):
        normalize_url("javascript:alert(1)")


def test_name_and_provider_normalization_are_deterministic():
    assert normalize_name(" 🚀  Yahoo   Finance ") == "Yahoo Finance"
    assert canonical_provider_name("", "www.example.com") == "example.com"


def test_candidate_identity_is_stable_full_sha256():
    first = candidate_identity(
        canonical_name="Example",
        identity_url="https://example.com/data?symbol=NQ",
        capability_kind="market-data",
    )
    second = candidate_identity(
        canonical_name="Example",
        identity_url="https://example.com/data?symbol=NQ",
        capability_kind="market-data",
    )
    assert first == second
    assert re.fullmatch(r"[0-9a-f]{64}", first)


def test_data_classification_fails_closed_to_other():
    assert classify_data_class("mystery", "opaque utility") == (DataClass.OTHER,)
    assert DataClass.DERIVATIVES_POSITIONING in classify_data_class(
        "finance", "CFTC futures positioning and commitment of traders data"
    )
