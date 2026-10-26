import json
import hashlib

import pytest


def _store(data_dir=None):
    try:
        from icarus_engine.research_context import MarketContextStore
    except ModuleNotFoundError:
        pytest.fail("research market context is not implemented", pytrace=False)
    return MarketContextStore(data_dir)


def _bundle(root, csv_text):
    csv_path = root / "brent.csv"
    csv_path.write_text(csv_text, encoding="utf-8")
    (root / "manifest.json").write_text(json.dumps({
        "schema_version": "icarus.market-context.v1",
        "snapshot_at": "2026-10-26T00:00:00Z",
        "catalog": {"sources": [{
            "id": "eia-oil-prices", "name": "Brent and WTI spot prices",
            "source_url": "https://datahub.io/core/oil-prices",
            "reason": "EIA research context.",
            "status": "ACTIVE_RESEARCH_CONTEXT", "active_series": 1,
        }]},
        "datasets": [{
            "id": "eia-brent-daily",
            "name": "Brent crude spot",
            "filename": "brent.csv",
            "sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
            "unit": "USD/barrel",
            "frequency": "daily",
            "source": "U.S. Energy Information Administration",
            "source_url": "https://www.eia.gov/dnav/pet/pet_pri_spt_s1_d.htm",
            "snapshot_url": "https://datahub.io/core/oil-prices/r/brent-daily.csv",
            "upstream_license": "U.S. government data; public domain",
            "catalog_status": "ACTIVE_RESEARCH_CONTEXT",
        }],
    }), encoding="utf-8")


def test_context_preserves_missing_values_and_marks_old_snapshot_stale(tmp_path):
    _bundle(tmp_path, "Date,Price\n2026-10-19,61.25\n2026-10-20,\n")

    result = _store(tmp_path).snapshot(limit=2, now="2026-10-26T00:00:00Z")

    dataset = result["datasets"][0]
    assert dataset["latest_observation_at"] == "2026-10-19"
    assert dataset["latest_price"] == 61.25
    assert dataset["freshness"] == "STALE"
    assert dataset["missing_value_count"] == 1
    assert dataset["observations"] == [
        {"date": "2026-10-19", "price": 61.25, "quality_flags": []},
        {"date": "2026-10-20", "price": None, "quality_flags": ["missing_price"]},
    ]
    assert dataset["source"] == "U.S. Energy Information Administration"
    assert result["execution_authorized"] is False


def test_context_rejects_duplicate_or_unordered_dates(tmp_path):
    _bundle(tmp_path, "Date,Price\n2026-10-20,61.25\n2026-10-19,62\n")

    with pytest.raises(ValueError, match="strictly increasing"):
        _store(tmp_path).snapshot(now="2026-10-26T00:00:00Z")


def test_context_rejects_manifest_path_escape(tmp_path):
    _bundle(tmp_path, "Date,Price\n2026-10-20,61.25\n")
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    manifest["datasets"][0]["filename"] = "../outside.csv"
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))

    with pytest.raises(ValueError, match="filename"):
        _store(tmp_path).snapshot(now="2026-10-26T00:00:00Z")


def test_context_rejects_snapshot_bytes_that_do_not_match_the_manifest(tmp_path):
    _bundle(tmp_path, "Date,Price\n2026-10-20,61.25\n")
    (tmp_path / "brent.csv").write_text("Date,Price\n2026-10-20,62.25\n", encoding="utf-8")

    with pytest.raises(ValueError, match="SHA-256"):
        _store(tmp_path).snapshot(now="2026-10-26T00:00:00Z")


def test_context_preserves_negative_commodity_prices(tmp_path):
    _bundle(tmp_path, "Date,Price\n2020-04-20,-36.98\n")

    result = _store(tmp_path).snapshot(now="2020-04-20T00:00:00Z")

    assert result["datasets"][0]["latest_price"] == -36.98


def test_packaged_context_exposes_only_the_three_reviewed_eia_daily_series():
    result = _store().snapshot(limit=5, now="2026-10-26T00:00:00Z")

    assert [dataset["id"] for dataset in result["datasets"]] == [
        "eia-brent-daily", "eia-wti-daily", "eia-natural-gas-daily",
    ]
    assert all(dataset["catalog_status"] == "ACTIVE_RESEARCH_CONTEXT" for dataset in result["datasets"])
    assert all(dataset["freshness"] == "STALE" for dataset in result["datasets"])
    assert result["catalog"]["sources"] == 9
    assert result["catalog"]["active_series"] == 3
    assert result["catalog"]["quarantined_sources"] == 7
