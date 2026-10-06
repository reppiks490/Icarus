from __future__ import annotations

import json
import re
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "coordination" / "manifests" / "provider-registry.yaml"
SCHEMA = ROOT / "coordination" / "schemas" / "external-evidence.schema.json"

APPROVED_PROVIDER_IDS = {
    "databento", "fmp", "eodhd", "tiingo", "unusual_whales", "intrinio",
    "sec_edgar", "ny_fed", "us_treasury", "cftc_tff", "eia", "fred_alfred",
    "quiver", "tick_stream", "bybit", "deribit", "binance", "kraken",
    "coinbase", "iqfeed", "rithmic", "cqg",
}
REQUIRED_PROVIDER_FIELDS = {
    "id", "name", "domain", "role", "source_class", "capabilities",
    "credential_names", "configuration_names", "cadence_class",
    "licensing_policy", "raw_retention_policy", "direct_execution_authority",
}
ALLOWED_HEALTH_STATES = {
    "OK", "DEGRADED", "STALE", "UNCONFIGURED", "DISABLED",
    "PLAN_LIMITED", "ENTITLEMENT_REQUIRED", "CONFIGURATION_BLOCKED", "ERROR",
}


def _registry() -> dict:
    with REGISTRY.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    assert isinstance(data, dict)
    return data


def _schema() -> dict:
    with SCHEMA.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _valid_record() -> dict:
    return {
        "schema_version": "icarus.external-evidence/1",
        "evidence_id": "ev_0123456789abcdef",
        "source_id": "src_0123456789abcdef",
        "provider_id": "fred_alfred",
        "dataset": "CPIAUCSL",
        "instrument": None,
        "venue": None,
        "source_event_time": "2026-09-01T00:00:00Z",
        "source_publication_time": "2026-09-11T12:30:00Z",
        "source_available_at": "2026-09-11T12:30:00Z",
        "retrieved_at": "2026-10-06T15:00:00Z",
        "ingested_at": "2026-10-06T15:00:01Z",
        "revision_id": "2026-09-11",
        "vintage_id": "2026-09-11",
        "raw_artifact_sha256": "a" * 64,
        "canonical_sha256": "b" * 64,
        "ingest_batch_id": "batch_20261006T150000Z",
        "quality_flags": [],
        "lineage_parents": [],
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


def test_registry_covers_every_approved_source_with_static_capabilities_only():
    reg = _registry()
    providers = reg["providers"]
    ids = [p["id"] for p in providers]
    assert len(ids) == len(set(ids)), "provider IDs must be unique"
    assert APPROVED_PROVIDER_IDS <= set(ids)
    assert set(reg["health_model"]["states"]) == ALLOWED_HEALTH_STATES

    env_name = re.compile(r"^[A-Z][A-Z0-9_]*$")
    for provider in providers:
        assert REQUIRED_PROVIDER_FIELDS <= set(provider), provider.get("name")
        assert provider["direct_execution_authority"] is False
        assert isinstance(provider["capabilities"], list) and provider["capabilities"]
        assert provider["cadence_class"]
        assert provider["licensing_policy"]
        assert provider["raw_retention_policy"]
        assert "status" not in provider and "health" not in provider and "last_success" not in provider
        for name in provider["credential_names"] + provider["configuration_names"]:
            assert env_name.fullmatch(name), (provider["id"], name)


def test_external_evidence_schema_requires_point_in_time_provenance_and_false_authority():
    schema = _schema()
    Draft202012Validator.check_schema(schema)
    required = set(schema["required"])
    assert {
        "source_id", "provider_id", "dataset", "instrument", "venue",
        "source_event_time", "source_publication_time", "source_available_at",
        "retrieved_at", "ingested_at", "revision_id", "vintage_id",
        "raw_artifact_sha256", "canonical_sha256", "ingest_batch_id",
        "quality_flags", "lineage_parents", "execution_authorized",
        "production_decision_authorized",
    } <= required
    assert schema["properties"]["execution_authorized"]["const"] is False
    assert schema["properties"]["production_decision_authorized"]["const"] is False


def test_external_evidence_schema_rejects_authority_escalation_and_missing_provenance():
    validator = Draft202012Validator(_schema())
    good = _valid_record()
    assert list(validator.iter_errors(good)) == []

    escalated = dict(good, execution_authorized=True)
    assert list(validator.iter_errors(escalated))

    for missing in ("source_id", "provider_id", "raw_artifact_sha256", "canonical_sha256"):
        bad = dict(good)
        bad.pop(missing)
        assert list(validator.iter_errors(bad)), missing
