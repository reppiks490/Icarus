from copy import deepcopy
import json

import pytest

import icarus_engine.market_universe as market_universe
from icarus_engine.market_universe import catalog_evidence_digest
from tools.a200_listing_crosswalk import _identity_digest


def _report():
    catalog = market_universe._load()
    rows = []
    for instrument in catalog["instruments"]:
        observed = {
            "venue": instrument["venue"], "symbol": instrument["display_symbol"],
            "name": instrument["name"], "instrument_type": instrument["instrument_type"],
            "depositary_ratio": instrument["depositary_ratio"],
        }
        rows.append({
            "instrument_id": instrument["instrument_id"], "expected": deepcopy(observed),
            "observed": observed, "status": "MATCHED", "identity_sha256": _identity_digest(observed),
        })
    return {
        "schema_version": "icarus.market-universe.listing-crosswalk.v1",
        "catalog_id": catalog["catalog_id"], "catalog_snapshot_sha256": catalog_evidence_digest(catalog),
        "retrieved_at": "2026-10-16T12:00:00Z", "qualification_scope": "public_listing_identity_only",
        "raw_market_data_persisted": False, "source_snapshots": {
            name: {
                "sha256": "a" * 64,
                "endpoint": f"https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=5000&sortColumn=marketCap&sortOrder=DESC&exchange={name.lower()}",
                "retrieved_at": "2026-10-16T12:00:00Z",
            } for name in ("NASDAQ", "NYSE", "AMEX")
        }, "requested_instrument_count": 200, "results": rows,
        "results_sha256": market_universe.source_probe_results_digest(rows),
    }


def test_crosswalk_reports_all_200_listing_identities_without_feed_qualification(monkeypatch, tmp_path):
    report = _report()
    path = tmp_path / "crosswalk.json"
    path.write_text(json.dumps(report))
    monkeypatch.setattr(market_universe, "LISTING_CROSSWALK_PATH", path)
    loaded = market_universe.load_listing_crosswalk_report()
    assert loaded["status"] == "CURRENT"
    assert loaded["matched_count"] == 200
    catalog = market_universe.snapshot()
    assert catalog["listing_crosswalk"]["matched_count"] == 200
    assert catalog["counts"]["source_connected_count"] == 0
    assert catalog["counts"]["entitlement_verified_count"] == 0
    assert catalog["counts"]["historical_bars_qualified_count"] == 0
    assert catalog["counts"]["live_bars_qualified_count"] == 0
    assert catalog["counts"]["pulse_enabled_count"] == 0
    assert catalog["counts"]["strategy_qualified_count"] == 0


@pytest.mark.parametrize("mutation", ["duplicate", "missing", "name", "type", "digest", "unknown"])
def test_crosswalk_fails_closed_on_invalid_identity_ledger(monkeypatch, tmp_path, mutation):
    report = _report()
    if mutation == "duplicate":
        report["results"][-1] = deepcopy(report["results"][0])
    elif mutation == "missing":
        report["results"].pop()
        report["requested_instrument_count"] = 199
        report["results_sha256"] = market_universe.source_probe_results_digest(report["results"])
    elif mutation == "name":
        report["results"][0]["observed"]["name"] += " altered"
        report["results"][0]["identity_sha256"] = _identity_digest(report["results"][0]["observed"])
        report["results_sha256"] = market_universe.source_probe_results_digest(report["results"])
    elif mutation == "type":
        report["results"][0]["observed"]["instrument_type"] = "ordinary_share"
        report["results"][0]["identity_sha256"] = _identity_digest(report["results"][0]["observed"])
        report["results_sha256"] = market_universe.source_probe_results_digest(report["results"])
    elif mutation == "digest":
        report["catalog_snapshot_sha256"] = "0" * 64
    elif mutation == "unknown":
        report["results"][0]["instrument_id"] = "unknown-id"
        report["results_sha256"] = market_universe.source_probe_results_digest(report["results"])
    path = tmp_path / "crosswalk.json"
    path.write_text(json.dumps(report))
    monkeypatch.setattr(market_universe, "LISTING_CROSSWALK_PATH", path)
    assert market_universe.load_listing_crosswalk_report()["status"] == "INVALID"


def test_crosswalk_detects_listing_mismatch_without_promoting_it(monkeypatch, tmp_path):
    report = _report()
    row = report["results"][0]
    row["status"] = "MISMATCH"
    row["observed"]["name"] += " amended"
    row["identity_sha256"] = _identity_digest(row["observed"])
    report["results_sha256"] = market_universe.source_probe_results_digest(report["results"])
    path = tmp_path / "crosswalk.json"
    path.write_text(json.dumps(report))
    monkeypatch.setattr(market_universe, "LISTING_CROSSWALK_PATH", path)
    loaded = market_universe.load_listing_crosswalk_report()
    assert loaded["status"] == "CURRENT"
    assert loaded["matched_count"] == 199


def test_crosswalk_is_stale_when_any_source_snapshot_is_older_than_24_hours(monkeypatch, tmp_path):
    report = _report()
    report["source_snapshots"]["NYSE"]["retrieved_at"] = "2026-10-14T12:00:00Z"
    path = tmp_path / "crosswalk.json"
    path.write_text(json.dumps(report))
    monkeypatch.setattr(market_universe, "LISTING_CROSSWALK_PATH", path)
    assert market_universe.load_listing_crosswalk_report()["status"] == "STALE"
