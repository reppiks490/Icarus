"""Read-only catalog and qualification counts for the 200 equity candidates.

Catalog membership is not provider connectivity, usable bar history, Pulse
readiness, strategy qualification, or execution authority.
"""
from __future__ import annotations

from importlib.resources import files
import json
import re
from typing import Any, Mapping

SCHEMA = "icarus.market-universe.catalog.v1"
_HEX = re.compile(r"^[0-9a-f]{64}$")


def _load() -> dict[str, Any]:
    resource = files("icarus_engine").joinpath("market-universe-200.json")
    return json.loads(resource.read_text(encoding="utf-8"))


def validate_catalog(catalog: Mapping[str, Any]) -> dict[str, Any]:
    if catalog.get("schema_version") != SCHEMA:
        raise ValueError("unsupported market universe catalog schema")
    instruments = catalog.get("instruments")
    if not isinstance(instruments, list) or not instruments:
        raise ValueError("market universe catalog must contain instruments")
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
        "entitlement_verified_count": sum(row["entitlement"] == "VERIFIED" for row in rows),
        "source_connected_count": sum(row["source_connection"] == "VERIFIED" for row in rows),
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
    }
