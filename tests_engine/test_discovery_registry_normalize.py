from __future__ import annotations

import pytest

from icarus_engine.discovery_registry.normalize import normalize_url


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
