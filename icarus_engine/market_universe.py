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
HYBRID_PROBE_PATH = Path(__file__).resolve().with_name("a200-hybrid-history-probe.json")


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


def source_probe_results_digest(results: list[Mapping[str, Any]]) -> str:
    encoded = json.dumps(results, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def source_probe_counts(results: list[Mapping[str, Any]]) -> dict[str, int]:
    return {
        "response_received_count": sum(row.get("probe_status") == "RESPONSE_RECEIVED" for row in results),
        "no_bars_count": sum(row.get("probe_status") == "NO_BARS" for row in results),
        "error_count": sum(row.get("probe_status") == "ERROR" for row in results),
        "provider_symbol_match_count": sum(row.get("provider_symbol_match_status") == "MATCHED" for row in results),
        "canonical_identity_verified_count": sum(row.get("canonical_identity_status") == "VERIFIED" for row in results),
        "entitlement_verified_count": sum(row.get("entitlement_status") == "VERIFIED" for row in results),
        "historical_bars_qualified_count": sum(row.get("historical_bars_qualified") is True for row in results),
    }


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
        "hybrid_probe": load_hybrid_probe_report(),
    }


def load_hybrid_probe_report() -> dict[str, Any]:
    """Load and validate the provider-separated, non-price hybrid probe ledger."""
    if not HYBRID_PROBE_PATH.exists():
        return {"status": "NOT_RUN", "results": []}
    try:
        report = json.loads(HYBRID_PROBE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as ex:
        return {"status": "UNAVAILABLE", "error": type(ex).__name__, "results": []}
    if not isinstance(report, dict) or report.get("schema_version") != "icarus.market-universe.hybrid-probe.v1":
        return {"status": "INVALID", "results": []}
    catalog = _load()
    if (report.get("catalog_id") != catalog.get("catalog_id")
            or report.get("catalog_snapshot_sha256") != catalog_evidence_digest(catalog)
            or report.get("probe_implementation") != "tools.probe_a200_hybrid.v1"
            or report.get("raw_ohlcv_persisted") is not False):
        return {"status": "INVALID", "results": []}
    results = report.get("results")
    requested, completed = report.get("requested_instrument_count"), report.get("completed_result_count")
    window = report.get("window")
    if (not isinstance(results, list) or any(not isinstance(row, dict) for row in results)
            or type(requested) is not int or requested < 0 or requested > EXPECTED_INSTRUMENT_COUNT
            or type(completed) is not int or completed != len(results)
            or not isinstance(window, dict) or type(window.get("start_ts")) is not int
            or type(window.get("end_ts")) is not int or window["start_ts"] >= window["end_ts"]):
        return {"status": "INVALID", "results": []}
    if report.get("results_sha256") != source_probe_results_digest(results):
        return {"status": "INVALID", "results": []}
    if any(row.get("requested_start_ts") != window["start_ts"]
           or row.get("requested_end_ts") != window["end_ts"] for row in results):
        return {"status": "INVALID", "results": []}
    actual_counts: dict[str, int] = {}
    catalog_rows = {row["instrument_id"]: row for row in catalog["instruments"]}
    expected_pairs = {
        (row["instrument_id"], mapping["provider"])
        for row in catalog["instruments"][:requested]
        for mapping in row.get("provider_symbol_candidates", [])
    }
    seen = set()
    max_age = 0
    now = datetime.now(timezone.utc)
    for result in results:
        instrument_id, provider = result.get("instrument_id"), result.get("provider")
        key = (instrument_id, provider)
        instrument = catalog_rows.get(instrument_id)
        mappings = [item for item in (instrument or {}).get("provider_symbol_candidates", [])
                    if item.get("provider") == provider]
        if (key in seen or not instrument or len(mappings) != 1
                or result.get("provider_symbol_candidate") != mappings[0].get("symbol")
                or result.get("provider_mapping_status") != mappings[0].get("mapping_status")
                or result.get("probe_status") not in ("NOT_CONFIGURED", "RESPONSE_RECEIVED", "NO_BARS", "ERROR")):
            return {"status": "INVALID", "results": []}
        seen.add(key)
        count_key = f"{provider.lower()}_{result['probe_status'].lower()}_count"
        actual_counts[count_key] = actual_counts.get(count_key, 0) + 1
        try:
            observed = datetime.fromisoformat(str(result["probe_started_at"]).replace("Z", "+00:00"))
            age = int((now - observed).total_seconds())
        except (KeyError, TypeError, ValueError):
            return {"status": "INVALID", "results": []}
        if age < 0:
            return {"status": "INVALID", "results": []}
        max_age = max(max_age, age)
    if report.get("counts") != actual_counts or seen != expected_pairs:
        return {"status": "INVALID", "results": []}
    try:
        updated = datetime.fromisoformat(str(report.get("probe_updated_at", "")).replace("Z", "+00:00"))
        report_age = int((now - updated).total_seconds())
    except (TypeError, ValueError):
        return {"status": "INVALID", "results": []}
    if report_age < 0:
        return {"status": "INVALID", "results": []}
    age_seconds = max(report_age, max_age)
    status = "STALE" if age_seconds > 86400 else ("CURRENT" if requested == EXPECTED_INSTRUMENT_COUNT else "PARTIAL")
    safe_fields = ("instrument_id", "provider", "provider_symbol_candidate", "probe_status",
                   "provider_symbol_match_status", "canonical_identity_status", "row_count",
                   "entitlement_status", "session_validation_status", "historical_bars_qualified",
                   "error_type", "error_code")
    return {"status": status, "probe_updated_at": report.get("probe_updated_at"),
            "window": window,
            "age_seconds": age_seconds, "requested_instrument_count": requested,
            "completed_result_count": completed, "counts": actual_counts,
            "authority": {"pulse_enabled": False, "strategy_qualified": False,
                          "execution_authorized": False},
            "raw_ohlcv_persisted": False,
            "results": [{key: row[key] for key in safe_fields if key in row} for row in results]}


def load_source_probe_report() -> dict[str, Any]:
    """Read the non-price A200 probe ledger and label its freshness explicitly."""
    if not PROBE_PATH.exists():
        return {"status": "NOT_RUN", "provider": "yahoo", "results": []}
    try:
        report = json.loads(PROBE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as ex:
        return {"status": "UNAVAILABLE", "provider": "yahoo", "error": type(ex).__name__, "results": []}
    if not isinstance(report, dict):
        return {"status": "INVALID", "provider": "yahoo", "results": []}
    raw_results = report.get("results")
    if not isinstance(raw_results, list) or any(not isinstance(row, dict) for row in raw_results):
        return {"status": "INVALID", "provider": "yahoo", "results": []}
    if report.get("schema_version") != "icarus.market-universe.source-probe.v3":
        return {"status": "INVALID", "provider": "yahoo", "results": []}
    catalog = _load()
    if report.get("catalog_id") != catalog.get("catalog_id") or report.get("probe_provider") != "yahoo":
        return {"status": "INVALID", "provider": "yahoo", "results": []}
    window = report.get("window")
    if (not isinstance(window, dict) or type(window.get("start_ts")) is not int
            or type(window.get("end_ts")) is not int or window["start_ts"] >= window["end_ts"]):
        return {"status": "INVALID", "provider": "yahoo", "results": []}
    if (report.get("catalog_snapshot_sha256") != catalog_evidence_digest(catalog)
            or report.get("probe_implementation") != "tools.probe_a200_yahoo.v3"
            or report.get("calendar_schedule_version") != "nyse-rth-2026-2028.v1"):
        return {"status": "INVALID", "provider": "yahoo", "results": []}
    now = datetime.now(timezone.utc)
    try:
        updated = datetime.fromisoformat(str(report.get("probe_updated_at", "")).replace("Z", "+00:00"))
        age_seconds = int((now - updated).total_seconds())
    except (TypeError, ValueError):
        age_seconds = None
    completed, requested = report.get("completed_count", 0), report.get("requested_count", 0)
    if (type(completed) is not int or type(requested) is not int or completed < 0
            or requested < 0 or completed > requested):
        return {"status": "INVALID", "provider": "yahoo", "results": []}
    if age_seconds is None or age_seconds < 0:
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
        for row in raw_results
    ]
    result_ids = [row.get("instrument_id") for row in results]
    catalog_rows = {row.get("instrument_id"): row for row in catalog.get("instruments", [])}
    catalog_ids = set(catalog_rows)
    if (len(results) != completed or len(set(result_ids)) != len(result_ids)
            or not set(result_ids).issubset(catalog_ids) or report.get("raw_ohlcv_persisted") is not False):
        return {"status": "INVALID", "provider": "yahoo", "results": []}
    if len(raw_results) != completed:
        return {"status": "INVALID", "provider": "yahoo", "results": []}
    if (report.get("results_sha256") != source_probe_results_digest(raw_results)
            or report.get("counts") != source_probe_counts(raw_results)):
        return {"status": "INVALID", "provider": "yahoo", "results": []}
    if any(row.get("probe_status") not in ("RESPONSE_RECEIVED", "NO_BARS", "ERROR")
           for row in raw_results):
        return {"status": "INVALID", "provider": "yahoo", "results": []}
    result_ages = []
    for row in raw_results:
        try:
            observed = datetime.fromisoformat(str(row.get("probe_started_at", "")).replace("Z", "+00:00"))
            result_age = int((now - observed).total_seconds())
        except (TypeError, ValueError):
            return {"status": "INVALID", "provider": "yahoo", "results": []}
        if result_age < 0:
            return {"status": "INVALID", "provider": "yahoo", "results": []}
        result_ages.append(result_age)
    for result in report.get("results", []):
        mappings = [candidate for candidate in catalog_rows[result["instrument_id"]].get("provider_symbol_candidates", [])
                    if candidate.get("provider") == "yahoo"]
        if (len(mappings) != 1 or result.get("provider") != "yahoo"
                or result.get("provider_symbol_candidate") != mappings[0].get("symbol")
                or result.get("provider_mapping_status") != mappings[0].get("mapping_status")):
            return {"status": "INVALID", "provider": "yahoo", "results": []}
    age_seconds = max([age_seconds, *result_ages])
    if age_seconds > 86400:
        status = "STALE"
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
