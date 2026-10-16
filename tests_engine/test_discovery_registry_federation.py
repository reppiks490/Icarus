"""Existing collector receipts only; source access is never initiated here."""
from datetime import datetime, timedelta, timezone
import hashlib
import json

import pytest

from icarus_engine.discovery_registry.contracts import Candidate, QualificationState
from icarus_engine.discovery_registry.federation import ProviderFederator
from icarus_engine.discovery_registry.service import DiscoveryRegistryService


NOW = datetime(2026, 10, 11, 21, 20, tzinfo=timezone.utc)


def candidate(url="https://api.twelvedata.com/time_series", **kwargs):
    return Candidate.minimum(candidate_id=hashlib.sha256(url.encode()).hexdigest(),
                             canonical_name="Twelve Data", endpoint_or_tool_url=url, **kwargs)


def files(tmp_path, *, status="COLLECTED_PARTIAL", pages=1, age=timedelta(minutes=5), **entry_extra):
    tmp_path.mkdir(parents=True, exist_ok=True)
    catalog = tmp_path / "catalog.json"
    catalog.write_text(json.dumps({"operations": [
        {"provider": "twelve", "id": "twelve:get:/time_series", "method": "GET", "path": "/time_series"},
        {"provider": "twelve", "id": "twelve:get:/quote", "method": "GET", "path": "/quote"},
        {"provider": "fred", "id": "fred:get:/series", "method": "GET", "path": "/series"},
    ]}))
    latest = tmp_path / "latest"
    latest.mkdir(parents=True, exist_ok=True)
    receipt = {"completed_at_utc": (NOW - age).isoformat(), "providers": {"twelve": {
        "status": status, "collected_pages": pages, "substantive_work_performed": pages != 0, **entry_extra}}}
    (latest / "twelve.json").write_text(json.dumps(receipt))
    return catalog, latest


def federator(paths):
    return ProviderFederator(*paths, now=lambda: NOW)


def test_existing_provider_links_without_network_or_downloader_call(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("federation attempted provider network I/O")
    import urllib.request
    import socket
    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    paths = files(tmp_path)
    links = federator(paths).links_for([candidate()])
    assert {link.operation_id for link in links} == {"twelve:get:/time_series"}
    raw = (paths[1] / "twelve.json").read_bytes()
    assert all(link.status == "COLLECTED_PARTIAL" for link in links)
    assert all(link.metadata["receipt_sha256"] == hashlib.sha256(raw).hexdigest() for link in links)
    assert all(link.metadata["receipt_path"] == str(paths[1] / "twelve.json") for link in links)
    assert links[0].metadata["operation_path_match"] == "EXACT"
    assert links[0].metadata["operation_verified"] is False


def test_openapi_path_parameter_matches_one_candidate_segment(tmp_path):
    catalog, latest = files(tmp_path, verified_operations=["twelve:get:/aggs/{ticker}"])
    payload = json.loads(catalog.read_text())
    payload["operations"].append({"provider": "twelve", "id": "twelve:get:/aggs/{ticker}",
                                  "method": "GET", "path": "/aggs/{ticker}"})
    catalog.write_text(json.dumps(payload))
    f = federator((catalog, latest))
    links = f.links_for([candidate("https://api.twelvedata.com/aggs/AAPL")])
    assert len(links) == 1
    assert links[0].metadata["operation_path_match"] == "TEMPLATE"
    assert len(f.evidence_events(links)) == 1


def test_openapi_path_parameter_does_not_match_multiple_segments(tmp_path):
    catalog, latest = files(tmp_path, verified_operations=["twelve:get:/aggs/{ticker}"])
    payload = json.loads(catalog.read_text())
    payload["operations"].append({"provider": "twelve", "id": "twelve:get:/aggs/{ticker}",
                                  "method": "GET", "path": "/aggs/{ticker}"})
    catalog.write_text(json.dumps(payload))
    f = federator((catalog, latest))
    assert f.links_for([candidate("https://api.twelvedata.com/aggs/AAPL/extra")]) == ()


def test_provider_aggregate_without_operation_proof_does_not_advance_candidate(tmp_path):
    f = federator(files(tmp_path))
    events = f.evidence_events(f.links_for([candidate()]))
    assert events == ()


def test_positive_operation_specific_receipt_produces_access_event(tmp_path):
    f = federator(files(tmp_path, verified_operations=["twelve:get:/time_series"]))
    events = f.evidence_events(f.links_for([candidate()]))
    assert len(events) == 1
    assert events[0].old_state is QualificationState.DISCOVERED
    assert events[0].new_state is QualificationState.ACCESS_TESTED
    assert events[0].to_dict()["execution_authorized"] is False
    assert events[0].metadata["operation_id"] == "twelve:get:/time_series"


def test_matching_operation_blocker_or_non_substantive_work_never_advances(tmp_path):
    blocked = federator(files(tmp_path / "blocked", verified_operations=["twelve:get:/time_series"],
                              blocked=[{"operation": "twelve:get:/time_series", "failure_code": "403"}]))
    assert blocked.evidence_events(blocked.links_for([candidate()])) == ()
    non_substantive = federator(files(tmp_path / "empty", substantive_work_performed=False,
                                      verified_operations=["twelve:get:/time_series"]))
    assert non_substantive.evidence_events(non_substantive.links_for([candidate()])) == ()


def test_candidate_endpoint_links_only_matching_operation_path(tmp_path):
    f = federator(files(tmp_path, verified_operations=["twelve:get:/quote"]))
    candidate_links = f.links_for([candidate("https://api.twelvedata.com/time_series")])
    assert [link.operation_id for link in candidate_links] == ["twelve:get:/time_series"]
    assert f.evidence_events(candidate_links) == ()
    quote = candidate("https://api.twelvedata.com/quote")
    quote_links = f.links_for([quote])
    assert [link.operation_id for link in quote_links] == ["twelve:get:/quote"]
    assert len(f.evidence_events(quote_links)) == 1


def test_candidate_endpoint_does_not_match_a_distinct_trailing_slash_route(tmp_path):
    f = federator(files(tmp_path, verified_operations=["twelve:get:/time_series"]))

    trailing_slash = candidate("https://api.twelvedata.com/time_series/")

    assert f.links_for([trailing_slash]) == ()
    assert f.evidence_events(f.links_for([trailing_slash])) == ()


def test_unrelated_endpoint_path_has_no_provider_operation_links(tmp_path):
    f = federator(files(tmp_path, verified_operations=["twelve:get:/time_series"]))
    assert f.links_for([candidate("https://api.twelvedata.com/unrelated")]) == ()


@pytest.mark.parametrize("status,pages,extra", [
    ("BLOCKED_MISSING_CREDENTIAL", 0, {}), ("BLOCKED_AUTHENTICATION", 1, {}),
    ("QUOTA_OR_RATE_LIMIT_PAUSED", 1, {}), ("COLLECTED_PARTIAL", 0, {}),
    ("COLLECTED_PARTIAL", True, {}), ("COLLECTED_PARTIAL", -1, {}),
    ("UNRECOGNIZED_SUCCESS", 1, {}),
])
def test_blockers_and_malformed_page_counts_never_become_success(tmp_path, status, pages, extra):
    f = federator(files(tmp_path, status=status, pages=pages, **extra))
    assert f.evidence_events(f.links_for([candidate()])) == ()


@pytest.mark.parametrize("age", [timedelta(hours=7), timedelta(minutes=-1)])
def test_stale_or_future_receipts_cannot_advance(tmp_path, age):
    f = federator(files(tmp_path, age=age))
    links = f.links_for([candidate()])
    assert f.evidence_events(links) == ()
    assert links[0].status in {"STALE_PROVIDER_EVIDENCE", "MALFORMED_PROVIDER_EVIDENCE"}


@pytest.mark.parametrize("raw", ["{bad json", "{}", "null", '{"providers": {"fred": {}}}',
    '{"completed_at_utc":"2026-10-11T21:00:00", "providers": {"twelve": {"status":"COLLECTED_PARTIAL", "collected_pages":1}}}'])
def test_malformed_or_wrong_provider_receipt_is_only_a_blocker(tmp_path, raw):
    paths = files(tmp_path)
    (paths[1] / "twelve.json").write_text(raw)
    f = federator(paths)
    assert f.evidence_events(f.links_for([candidate()])) == ()


def test_receipt_mutation_between_link_and_event_is_detected(tmp_path):
    paths = files(tmp_path)
    f = federator(paths)
    links = f.links_for([candidate()])
    (paths[1] / "twelve.json").write_text("{}")
    assert f.evidence_events(links) == ()


def test_blocker_added_after_link_creation_prevents_qualification(tmp_path):
    paths = files(tmp_path, verified_operations=["twelve:get:/time_series"])
    f = federator(paths)
    links = f.links_for([candidate()])
    receipt_path = paths[1] / "twelve.json"
    receipt = json.loads(receipt_path.read_text())
    receipt["providers"]["twelve"]["blocked"] = [
        {"operation": "twelve:get:/time_series", "failure_code": "403"}
    ]
    receipt_path.write_text(json.dumps(receipt))
    assert f.evidence_events(links) == ()


def test_exact_domain_and_provider_name_only_not_fuzzy_or_host_suffix(tmp_path):
    f = federator(files(tmp_path))
    bad = Candidate.minimum(candidate_id="a" * 64, canonical_name="Twelve Data scraper",
                            endpoint_or_tool_url="https://twelvedata.com.evil.example/news")
    assert f.links_for([bad]) == ()
    # Matching a provider's name can establish a link, not access on another transport.
    wrapper = candidate("https://apify.com/acme/twelve")
    links = f.links_for([wrapper])
    assert links == ()


def test_service_federation_is_idempotent_and_preserves_qualification(tmp_path):
    catalog, latest = files(tmp_path, age=timedelta(0),
                             verified_operations=["twelve:get:/time_series"])
    # Use actual now for the service's clock and a fresh receipt.
    receipt = json.loads((latest / "twelve.json").read_text())
    receipt["completed_at_utc"] = datetime.now(timezone.utc).isoformat()
    (latest / "twelve.json").write_text(json.dumps(receipt))
    service = DiscoveryRegistryService(tmp_path)
    service.store.upsert_candidates([candidate()])
    first = service.federate_existing_providers(catalog, latest)
    second = service.federate_existing_providers(catalog, latest)
    assert first["events_recorded"] == 1 and second["events_recorded"] == 0
    assert service.store.candidate(candidate().candidate_id).qualification_state is QualificationState.ACCESS_TESTED
    assert service.snapshot()["qualification_events"] == 1
    assert service.snapshot()["provider_links"] == 1
    assert first["execution_authorized"] is False
    service.close()


@pytest.mark.parametrize("url", ["http://api.twelvedata.com/unrelated", "https://api.twelvedata.com:8443/unrelated",
                               "https://www.api.twelvedata.com/unrelated"])
def test_provider_hostname_does_not_prove_another_transport(tmp_path, url):
    f = federator(files(tmp_path))
    links = f.links_for([candidate(url)])
    assert links == ()
    assert f.evidence_events(links) == ()


def test_operation_denials_remain_separate_from_provider_aggregate(tmp_path):
    f = federator(files(tmp_path, blocked=[{"operation": "twelve:get:/time_series", "failure_code": "403",
                                         "message": "SECRET_SENTINEL"}]))
    links = {link.operation_id: link for link in f.links_for([candidate()])}
    assert links["twelve:get:/time_series"].metadata["operation_blockers"] == ["403"]
    assert "SECRET_SENTINEL" not in str([link.to_dict() for link in links.values()])
    assert f.evidence_events(tuple(links.values())) == ()
