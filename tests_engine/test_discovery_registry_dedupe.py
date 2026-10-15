"""Synthetic structural-identity oracles; no market evidence or semantic merges."""
import hashlib
from itertools import permutations

import pytest

from icarus_engine.discovery_registry.contracts import Candidate
from icarus_engine.discovery_registry.dedupe import DuplicateResolver, duplicate_keys


def candidate(url, *, name="News API", catalog_ref="api-mega-list", **kwargs):
    # Preserve separate observations, even when their normalized service identity agrees.
    digest = hashlib.sha256((catalog_ref + "\0" + name + "\0" + url).encode()).hexdigest()
    return Candidate.minimum(
        candidate_id=digest, canonical_name=name, endpoint_or_tool_url=url,
        upstream_catalog_refs=(catalog_ref,), **kwargs,
    )


def test_referral_wrappers_share_one_duplicate_family():
    records = [candidate("https://apify.com/acme/tool?fpr=a"),
               candidate("https://apify.com/acme/tool?fpr=b&utm_source=x")]
    group, = DuplicateResolver().resolve(records)
    assert group.member_ids == tuple(sorted(c.candidate_id for c in records))
    assert group.evidence_level == "EXACT_IDENTITY_URL"
    assert group.effective_independent_count == 1
    assert group.group_id == hashlib.sha256(
        "\0".join((group.evidence_level, *group.member_ids)).encode()
    ).hexdigest()


def test_same_name_on_different_domains_does_not_auto_merge():
    assert DuplicateResolver().resolve([
        candidate("https://a.example/tool"), candidate("https://b.example/tool")
    ]) == ()


def test_duplicate_group_keeps_every_candidate_and_catalog_reference():
    a = candidate("https://apify.com/acme/tool?fpr=a", catalog_ref="api-mega-list")
    b = candidate("https://apify.com/acme/tool?fpr=b", catalog_ref="scraping-apis-for-devs")
    before = (a.to_dict(), b.to_dict())
    group, = DuplicateResolver().resolve([a, b])
    assert set(group.member_ids) == {a.candidate_id, b.candidate_id}
    assert group.catalog_refs == ("api-mega-list", "scraping-apis-for-devs")
    assert (a.to_dict(), b.to_dict()) == before
    assert group.to_dict()["execution_authorized"] is False


def test_groups_are_deterministic_for_order_and_repeated_inputs():
    records = [candidate("https://example.com/tool?ref=a"),
               candidate("https://example.com/tool?ref=b"),
               candidate("https://other.example/tool")]
    expected = DuplicateResolver().resolve(records)
    for ordering in permutations(records):
        assert DuplicateResolver().resolve([*ordering, ordering[0]]) == expected


def test_meaningful_queries_and_provider_namespaces_are_not_collapsed():
    assert DuplicateResolver().resolve([
        candidate("https://example.com/prices?symbol=NQ", provider_name="Example", capability_kind="prices"),
        candidate("https://example.com/prices?symbol=ES", provider_name="Example", capability_kind="prices"),
    ]) == ()
    assert DuplicateResolver().resolve([
        candidate("https://apify.com/a/news", name="A News"),
        candidate("https://apify.com/b/news", name="B News"),
    ]) == ()


def test_structural_keys_expose_evidence_not_semantic_similarity():
    record = candidate("https://example.com/news", provider_name="Example", capability_kind="news")
    assert {level for level, _ in duplicate_keys(record)} == {
        "EXACT_IDENTITY_URL", "PROVIDER_CAPABILITY", "DOMAIN_PATH", "NORMALIZED_NAME_DOMAIN"
    }
    assert DuplicateResolver().resolve([
        candidate("https://example.com/a", name="Headline finder"),
        candidate("https://example.com/b", name="News search"),
    ]) == ()


def test_conflicting_records_with_same_id_are_rejected():
    a = candidate("https://example.com/a")
    b = Candidate.minimum(candidate_id=a.candidate_id, canonical_name="Other",
                          endpoint_or_tool_url="https://example.com/b")
    with pytest.raises(ValueError, match="identity conflict"):
        DuplicateResolver().resolve([a, b])
