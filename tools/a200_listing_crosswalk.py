#!/usr/bin/env python3
"""Build a listing identity crosswalk from public exchange screener metadata.

Only exchange, symbol, name, instrument type, and depositary ratio are persisted
per listing. Screener ranking and quote fields are deliberately discarded.
This crosswalk says nothing about market data provider mapping or entitlement.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import urllib.request

from icarus_engine.market_universe import _load, catalog_evidence_digest
from tools.build_equity_catalog import EXCHANGES, URL, USER_AGENT, _instrument_class

SCHEMA = "icarus.market-universe.listing-crosswalk.v1"


def _fetch(exchange: str) -> tuple[dict, str]:
    request = urllib.request.Request(URL.format(exchange), headers={
        "User-Agent": USER_AGENT, "Accept": "application/json", "Origin": "https://www.nasdaq.com",
    })
    with urllib.request.urlopen(request, timeout=30) as response:
        raw = response.read(16 * 1024 * 1024 + 1)
    if len(raw) > 16 * 1024 * 1024:
        raise ValueError(f"{exchange} screener response exceeds 16 MiB")
    payload = json.loads(raw)
    if payload.get("status", {}).get("rCode") != 200:
        raise ValueError(f"{exchange} screener returned non-success status")
    rows = payload.get("data", {}).get("table", {}).get("rows")
    if not isinstance(rows, list):
        raise ValueError(f"{exchange} screener response has invalid rows")
    return payload, hashlib.sha256(raw).hexdigest()


def _identity_digest(identity: dict) -> str:
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def build(catalog: dict | None = None) -> dict:
    catalog = catalog or _load()
    catalog_digest = catalog_evidence_digest(catalog)
    retrieved = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    source_rows: dict[tuple[str, str], dict] = {}
    sources = {}
    for exchange in EXCHANGES:
        payload, digest = _fetch(exchange)
        sources[exchange.upper()] = {
            "endpoint": URL.format(exchange), "sha256": digest,
            "retrieved_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        }
        for raw_row in payload["data"]["table"]["rows"]:
            symbol = str(raw_row.get("symbol") or "").strip().upper()
            name = str(raw_row.get("name") or "").strip()
            classification = _instrument_class(name)
            if symbol and name and classification:
                source_rows[(exchange.upper(), symbol)] = {
                    "venue": exchange.upper(), "symbol": symbol, "name": name,
                    "instrument_type": classification[0], "depositary_ratio": classification[1],
                }
    results = []
    for row in catalog.get("instruments", []):
        key = (str(row.get("venue", "")).upper(), str(row.get("display_symbol", "")).upper())
        observed = source_rows.get(key)
        expected = {
            "venue": key[0], "symbol": key[1], "name": row.get("name"),
            "instrument_type": row.get("instrument_type"), "depositary_ratio": row.get("depositary_ratio"),
        }
        matched = observed == expected
        results.append({
            "instrument_id": row.get("instrument_id"), "expected": expected,
            "observed": observed, "status": "MATCHED" if matched else "MISMATCH",
            "identity_sha256": _identity_digest(observed) if observed else None,
        })
    return {
        "schema_version": SCHEMA, "catalog_id": catalog.get("catalog_id"),
        "catalog_snapshot_sha256": catalog_digest, "retrieved_at": retrieved,
        "source": "Nasdaq-operated public stock screener; identity metadata only",
        "source_snapshots": sources, "requested_instrument_count": len(catalog.get("instruments", [])),
        "results": results, "results_sha256": _identity_digest(results),
        "raw_market_data_persisted": False,
        "qualification_scope": "public_listing_identity_only",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("icarus_engine/a200-listing-crosswalk.json"))
    args = parser.parse_args()
    report = build()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    matched = sum(row["status"] == "MATCHED" for row in report["results"])
    print(f"wrote {matched}/{len(report['results'])} matched public listing identities to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
