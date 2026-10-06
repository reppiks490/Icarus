from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import urllib.request

from icarus_engine.external_data.pipeline import IngestPipeline
from icarus_engine.external_data.providers.icarus_engine_manifest import (
    DATABENTO_MANIFEST_SCHEMAS,
    IcarusEngineManifestBridge,
    ManifestDocument,
)
from icarus_engine.external_data.registry import ProviderRegistry
from icarus_engine.external_data.storage import EvidenceCatalog, RawArtifactStore


UTC = timezone.utc
FETCHED_AT = datetime(2026, 10, 6, 21, 0, tzinfo=UTC)
SOURCE_REPO = "reppiks490/Icarus-engine"
SOURCE_REF = "f9d247e0f9643a1546075fb5f7ffe159729c398a"


def _json_bytes(value) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _external_fabric() -> bytes:
    return _json_bytes(
        {
            "generated_at": "2026-10-06T20:00:00+00:00",
            "execution_authorized": False,
            "production_decision_authorized": False,
            "providers": {
                "eodhd": {
                    "provider": "eodhd",
                    "status": "ok",
                    "datasets": {
                        "eod_1y": {
                            "status": "ok",
                            "symbols": {
                                "NQ_PROXY": {
                                    "first": "2025-10-06T00:00:00+00:00",
                                    "last": "2026-10-05T00:00:00+00:00",
                                    "rows": 251,
                                    "return_pct": 12.5,
                                    "cache": {
                                        "bytes": 7000,
                                        "sha256": "a" * 64,
                                    },
                                }
                            },
                        }
                    },
                },
                "fmp": {
                    "provider": "fmp",
                    "status": "ok",
                    "datasets": {
                        "earnings_calendar": {
                            "status": "ok",
                            "rows": 29,
                            "cache": {"bytes": 589, "sha256": "b" * 64},
                        }
                    },
                },
                "tiingo": {
                    "provider": "tiingo",
                    "status": "ok",
                    "datasets": {
                        "eod": {
                            "status": "ok",
                            "symbols": {
                                "QQQ": {
                                    "first": "2008-01-02T00:00:00+00:00",
                                    "last": "2026-10-05T00:00:00+00:00",
                                    "rows": 4719,
                                    "total_return_pct": 1900.0,
                                    "cache": {
                                        "bytes": 250000,
                                        "sha256": "c" * 64,
                                    },
                                }
                            },
                        }
                    },
                },
            },
        }
    )


def _databento_manifest(schemas=("mbo", "mbp-10")) -> bytes:
    requests = []
    for index, schema in enumerate(schemas):
        requests.append(
            {
                "dataset": "GLBX.MDP3",
                "day": f"2026-10-{index + 1:02d}",
                "feature_bytes": 1000 + index,
                "feature_path": f"features/secondary/{schema}/nq/day.csv.gz",
                "feature_sha256": f"{index + 1:064x}",
                "request_performed": False,
                "root": "NQ",
                "schema": schema,
                "status": "cached",
                "symbol": "NQ.v.0",
            }
        )
    return _json_bytes(
        {
            "account": "secondary",
            "dataset": "GLBX.MDP3",
            "generated_at": "2026-10-06T20:23:47.976487+00:00",
            "execution_authorized": False,
            "production_decision_authorized": False,
            "raw_retention": "none; temporary DBN is hashed, reduced, and deleted",
            "requests": requests,
        }
    )


def _document(payload: bytes, path: str, kind: str) -> ManifestDocument:
    return ManifestDocument(
        payload=payload,
        kind=kind,
        source_repository=SOURCE_REPO,
        source_ref=SOURCE_REF,
        source_path=path,
        fetched_at=FETCHED_AT,
    )


def _run(tmp_path, documents):
    bridge = IcarusEngineManifestBridge(documents)
    registry = ProviderRegistry()
    registry.register(bridge)
    catalog = EvidenceCatalog(tmp_path / "external" / "catalog.sqlite3")
    pipeline = IngestPipeline(
        registry,
        RawArtifactStore(tmp_path / "external"),
        catalog,
        environment={},
    )
    receipt = pipeline.run_provider(bridge.descriptor.provider_id, FETCHED_AT)
    evidence = catalog.query_as_of(FETCHED_AT, provider_id=bridge.descriptor.provider_id)
    return bridge, receipt, evidence


def test_bridge_normalizes_existing_external_fabric_without_vendor_credentials(tmp_path):
    payload = _external_fabric()
    bridge, receipt, evidence = _run(
        tmp_path,
        [
            _document(
                payload,
                "automation_intelligence/cl_lab/external_data_fabric.json",
                "external_data_fabric",
            )
        ],
    )

    assert bridge.descriptor.credential_names == ()
    assert receipt.state == "OK"
    assert {item.data["upstream_provider"] for item in evidence} == {"eodhd", "fmp", "tiingo"}
    assert all(item.execution_authorized is False for item in evidence)
    assert all(item.production_decision_authorized is False for item in evidence)
    assert all(item.data["source_repository"] == SOURCE_REPO for item in evidence)
    assert all(item.data["source_ref"] == SOURCE_REF for item in evidence)
    assert all(item.data["manifest_fetched_at"] == FETCHED_AT.isoformat() for item in evidence)
    assert all(item.data["evidence_kind"] == "upstream_compact_manifest" for item in evidence)


def test_upstream_cache_hash_is_reference_not_central_raw_market_hash(tmp_path):
    payload = _external_fabric()
    _, receipt, evidence = _run(
        tmp_path,
        [_document(payload, "automation_intelligence/cl_lab/external_data_fabric.json", "external_data_fabric")],
    )

    manifest_hash = hashlib.sha256(payload).hexdigest()
    assert receipt.raw_artifact_sha256s == (manifest_hash,)
    eodhd = next(item for item in evidence if item.data["upstream_provider"] == "eodhd")
    assert eodhd.raw_artifact_sha256 == manifest_hash
    assert eodhd.data["upstream_cache_sha256"] == "a" * 64
    assert eodhd.data["upstream_cache_sha256"] != eodhd.raw_artifact_sha256
    assert eodhd.data["raw_market_payload_copied"] is False


def test_databento_depth_manifest_preserves_derived_feature_provenance_without_raw_rows(tmp_path):
    payload = _databento_manifest(("mbo", "mbp-10"))
    _, receipt, evidence = _run(
        tmp_path,
        [
            _document(
                payload,
                "automation_intelligence/cl_lab/databento_depth_corpus_index.json",
                "databento_corpus",
            )
        ],
    )

    assert receipt.state == "OK"
    assert {item.data["databento_schema"] for item in evidence} == {"mbo", "mbp-10"}
    assert all(item.data["evidence_kind"] == "upstream_derived_feature_manifest" for item in evidence)
    assert all(item.data["raw_market_payload_copied"] is False for item in evidence)
    assert all(item.data["upstream_raw_retention"].startswith("none;") for item in evidence)
    assert all(len(item.data["upstream_feature_sha256"]) == 64 for item in evidence)
    assert all("rows" not in item.data or not isinstance(item.data["rows"], list) for item in evidence)


def test_databento_manifest_parser_supports_all_approved_schema_capabilities(tmp_path):
    approved = {"mbo", "mbp-10", "tbbo", "trades", "statistics"}
    assert approved <= set(DATABENTO_MANIFEST_SCHEMAS)

    payload = _databento_manifest(tuple(sorted(approved)))
    _, receipt, evidence = _run(
        tmp_path,
        [_document(payload, "databento_manifest.json", "databento_corpus")],
    )

    assert receipt.state == "OK"
    assert {item.data["databento_schema"] for item in evidence} == approved


def test_bridge_never_calls_fmp_eodhd_tiingo_or_databento_vendor_endpoints(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("manifest bridge attempted an outbound vendor request")

    monkeypatch.setattr(urllib.request, "urlopen", forbidden)

    documents = [
        _document(_external_fabric(), "external_data_fabric.json", "external_data_fabric"),
        _document(_databento_manifest(), "databento_depth_corpus_index.json", "databento_corpus"),
    ]
    _, receipt, evidence = _run(tmp_path, documents)

    assert receipt.state == "OK"
    assert evidence


def test_manifest_generated_time_is_publication_time_and_fetch_time_is_retrieval_time(tmp_path):
    generated = datetime(2026, 10, 6, 20, 0, tzinfo=UTC)
    payload = _external_fabric()
    _, _, evidence = _run(
        tmp_path,
        [_document(payload, "external_data_fabric.json", "external_data_fabric")],
    )

    assert evidence
    for item in evidence:
        assert item.source_event_time is None
        assert item.source_publication_time == generated
        assert item.source_available_at == generated
        assert item.retrieved_at == FETCHED_AT
        assert item.data["source_path"] == "external_data_fabric.json"
