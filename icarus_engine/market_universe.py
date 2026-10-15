"""Read-only catalog and qualification counts for the 200 equity candidates.

Catalog membership is not provider connectivity, usable bar history, Pulse
readiness, strategy qualification, or execution authority.
"""
from __future__ import annotations

from importlib.resources import files
from datetime import datetime, timezone
import json
import hashlib
from pathlib import Path
import re
from typing import Any, Mapping

SCHEMA = "icarus.market-universe.catalog.v1"
EXPECTED_INSTRUMENT_COUNT = 200
_HEX = re.compile(r"^[0-9a-f]{64}$")
PROBE_PATH = Path(__file__).resolve().with_name("a200-yahoo-history-probe.json")


def _load() -> dict[str, Any]:
    resource = files("icarus_engine").joinpath("market-universe-200.json")
    return json.loads(resource.read_text(encoding="utf-8"))


def catalog_evidence_digest(catalog: Mapping[str, Any]) -> str:
    """Digest the catalog fields that determine instrument and provider identity."""
    payload = {
        "schema_version": catalog.get("schema_version"),
        "catalog_id": catalog.get("catalog_id"),
        "sources": catalog.get("sources"),
        "instruments": catalog.get("instruments"),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def validate_catalog(catalog: Mapping[str, Any]) -> dict[str, Any]:
    if catalog.get("schema_version") != SCHEMA:
        raise ValueError("unsupported market universe catalog schema")
    instruments = catalog.get("instruments")
    if not isinstance(instruments, list) or len(instruments) != EXPECTED_INSTRUMENT_COUNT:
        raise ValueError(f"market universe catalog must contain exactly {EXPECTED_INSTRUMENT_COUNT} instruments")
    ids, listings = set(), set()
    for row in instruments:
        if not isinstance(row, Mapping):
            raise ValueError("catalog instrument must be an object")
        instrument_id = row.get("instrument_id")
        if not isinstance(instrument_id, str) or not instrument_id:
            raise ValueError("catalog instrument needs an ID")
        if instrument_id in ids:
            raise ValueError(f"duplicate catalog instrument ID: {instrument_id}")
        ids.add(instrument_id)
        listing = (str(row.get("venue", "")).upper(), str(row.get("display_symbol", "")).upper())
        if not all(listing) or listing in listings:
            raise ValueError(f"invalid or duplicate listing identity: {listing}")
        listings.add(listing)
        if row.get("pulse_enabled") is not False or row.get("strategy_qualified") is not False:
            raise ValueError("candidate catalog rows must remain disabled and unqualified")
        if row.get("source_connection") not in ("UNVERIFIED", "VERIFIED"):
            raise ValueError(f"invalid source connection state for {instrument_id}")
        if row.get("historical_bars") not in ("UNVERIFIED", "QUALIFIED"):
            raise ValueError(f"invalid historical bars state for {instrument_id}")
        if row.get("live_bars") not in ("UNVERIFIED", "QUALIFIED"):
            raise ValueError(f"invalid live bars state for {instrument_id}")
    sources = catalog.get("sources")
    if not isinstance(sources, Mapping) or not sources:
        raise ValueError("catalog source provenance is required")
    for name, source in sources.items():
        if not isinstance(source, Mapping) or not _HEX.fullmatch(str(source.get("sha256", ""))):
            raise ValueError(f"invalid source snapshot digest for {name}")
    authority = catalog.get("authority")
    if not isinstance(authority, Mapping) or authority.get("execution_authorized") is not False:
        raise ValueError("catalog execution authority must remain false")
    if authority.get("production_decision_authorized") is not False:
        raise ValueError("catalog production decision authority must remain false")
    return {"instruments": instruments, "sources": sources}


def snapshot() -> dict[str, Any]:
    catalog = _load()
    validated = validate_catalog(catalog)
    rows = validated["instruments"]
    counts = {
        "catalogued_count": len(rows),
        "source_connected_count": sum(row["source_connection"] == "VERIFIED" for row in rows),
        "entitlement_verified_count": sum(row["entitlement"] == "VERIFIED" for row in rows),
        "historical_bars_qualified_count": sum(row["historical_bars"] == "QUALIFIED" for row in rows),
        "live_bars_qualified_count": sum(row["live_bars"] == "QUALIFIED" for row in rows),
        "pulse_enabled_count": sum(row["pulse_enabled"] is True for row in rows),
        "strategy_qualified_count": sum(row["strategy_qualified"] is True for row in rows),
    }
    declared = catalog.get("counts")
    if declared != counts:
        raise ValueError("market universe declared counts do not match catalog rows")
    return {
        "schema_version": catalog["schema_version"],
        "catalog_id": catalog["catalog_id"],
        "retrieved_at": catalog["retrieved_at"],
        "selection": catalog["selection"],
        "sources": dict(validated["sources"]),
        "counts": counts,
        "instruments": rows,
        "execution_authorized": False,
        "production_decision_authorized": False,
        "note": "Cataloged equity candidates are not connected, bar-qualified, Pulse-enabled, or strategy-qualified without separate source receipts and evidence.",
        "source_probe": load_source_probe_report(),
    }


def load_source_probe_report() -> dict[str, Any]:
    """Read the non-price A200 probe ledger and label its freshness explicitly."""
    if not PROBE_PATH.exists():
        return {"status": "NOT_RUN", "provider": "yahoo", "results": []}
    try:
        report = json.loads(PROBE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as ex:
        return {"status": "UNAVAILABLE", "provider": "yahoo", "error": type(ex).__name__, "results": []}
    if report.get("schema_version") != "icarus.market-universe.source-probe.v2":
        return {"status": "INVALID", "provider": "yahoo", "results": []}
    catalog = _load()
    if report.get("catalog_id") != catalog.get("catalog_id"):
        return {"status": "INVALID", "provider": "yahoo", "results": []}
    if (report.get("catalog_snapshot_sha256") != catalog_evidence_digest(catalog)
            or report.get("probe_implementation") != "tools.probe_a200_yahoo.v2"):
        return {"status": "INVALID", "provider": "yahoo", "results": []}
    now = datetime.now(timezone.utc)
    try:
        updated = datetime.fromisoformat(str(report.get("probe_updated_at", "")).replace("Z", "+00:00"))
        age_seconds = max(0, int((now - updated).total_seconds()))
    except (TypeError, ValueError):
        age_seconds = None
    completed, requested = report.get("completed_count", 0), report.get("requested_count", 0)
    if (type(completed) is not int or type(requested) is not int or completed < 0
            or requested < 0 or completed > requested):
        return {"status": "INVALID", "provider": "yahoo", "results": []}
    if age_seconds is None:
        status = "INVALID"
    elif age_seconds > 86400:
        status = "STALE"
    elif requested == len(catalog.get("instruments", [])) and completed == requested:
        status = "CURRENT"
    else:
        status = "PARTIAL"
    allowed_fields = (
        "instrument_id", "probe_status", "provider_symbol_match_status",
        "canonical_identity_status", "row_count", "received_start_ts",
        "received_end_ts", "checksum_sha256", "receipt_id", "error_type", "error",
    )
    results = [
        {key: row[key] for key in allowed_fields if key in row}
        for row in report.get("results", []) if isinstance(row, dict)
    ]
    result_ids = [row.get("instrument_id") for row in results]
    catalog_rows = {row.get("instrument_id"): row for row in catalog.get("instruments", [])}
    catalog_ids = set(catalog_rows)
    if (len(results) != completed or len(set(result_ids)) != len(result_ids)
            or not set(result_ids).issubset(catalog_ids) or report.get("raw_ohlcv_persisted") is not False):
        return {"status": "INVALID", "provider": "yahoo", "results": []}
    for result in report.get("results", []):
        mappings = [candidate for candidate in catalog_rows[result["instrument_id"]].get("provider_symbol_candidates", [])
                    if candidate.get("provider") == "yahoo"]
        if (len(mappings) != 1 or result.get("provider") != "yahoo"
                or result.get("provider_symbol_candidate") != mappings[0].get("symbol")
                or result.get("provider_mapping_status") != mappings[0].get("mapping_status")):
            return {"status": "INVALID", "provider": "yahoo", "results": []}
    return {
        "status": status,
        "provider": report.get("probe_provider", "yahoo"),
        "probe_updated_at": report.get("probe_updated_at"),
        "age_seconds": age_seconds,
        "requested_count": requested,
        "completed_count": completed,
        "counts": report.get("counts", {}),
        "authority": {"pulse_enabled": False, "strategy_qualified": False, "execution_authorized": False},
        "raw_ohlcv_persisted": False,
        "results": results,
    }
