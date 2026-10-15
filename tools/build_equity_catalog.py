#!/usr/bin/env python3
"""Build a candidate-only US equity listing catalog from Nasdaq's screener.

Market-cap values are used only to select a dated top-N snapshot and are
never written. The generated rows are catalog metadata, not source or entitlement
attestations and cannot enable Pulse.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import urllib.request
import uuid

EXCHANGES = ("nasdaq", "nyse", "amex")
URL = "https://api.nasdaq.com/api/screener/stocks?tableonly=true&limit=5000&sortColumn=marketCap&sortOrder=DESC&exchange={}"
NAMESPACE = uuid.UUID("67e7286d-4a5a-4a67-a938-722ce43ba4d9")
USER_AGENT = "ICARUS market universe catalog/1.0"
QUARANTINED = {
    "SPCX": "Nasdaq screener metadata conflicts with independently known issuer/listing status; verify before catalog inclusion",
}


def _fetch(exchange: str) -> tuple[dict, str]:
    req = urllib.request.Request(
        URL.format(exchange),
        headers={"User-Agent": USER_AGENT, "Accept": "application/json", "Origin": "https://www.nasdaq.com"},
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        raw = response.read(16 * 1024 * 1024 + 1)
    if len(raw) > 16 * 1024 * 1024:
        raise ValueError(f"{exchange} response exceeds 16 MiB")
    data = json.loads(raw)
    if data.get("status", {}).get("rCode") != 200:
        raise ValueError(f"{exchange} screener returned non-success status")
    table = data.get("data", {}).get("table", {})
    if not isinstance(table.get("rows"), list) or not isinstance(data.get("data", {}).get("totalrecords"), int):
        raise ValueError(f"{exchange} screener response has an unexpected schema")
    return data, hashlib.sha256(raw).hexdigest()


def _instrument_class(name: str) -> tuple[str, int | None] | None:
    lowered = name.lower()
    if any(re.search(pattern, lowered) for pattern in (
        r"\bpreferred\b", r"\bpfd\b", r"\bpreference shares?\b",
        r"\bwarrants?\b", r"\bunits?\b",
    )):
        return None
    if "american depositary shares" in lowered:
        ratio_match = re.search(
            r"representing\s+(one|two|three|four|five|six|seven|eight|nine|ten|\d+)"
            r"(?:\s+\((\d+)\))?\s+ordinary shares",
            lowered,
        )
        if not ratio_match:
            return "depositary_receipt", None
        words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                 "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
        value = ratio_match.group(2) or ratio_match.group(1)
        return "depositary_receipt", int(value) if value.isdigit() else words[value]
    if "ordinary shares" in lowered and "common stock" not in lowered:
        return "ordinary_share", None
    if "common stock" in lowered:
        return "common_stock", None
    return None


def build(limit: int = 200) -> dict:
    if type(limit) is not int or not 1 <= limit <= 2000:
        raise ValueError("limit must be between 1 and 2000")
    retrieved_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    ranked = []
    snapshots = {}
    excluded_symbols = {}
    excluded_class_count = 0
    for exchange in EXCHANGES:
        data, digest = _fetch(exchange)
        snapshots[exchange] = {
            "endpoint": URL.format(exchange), "sha256": digest,
            "retrieved_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "provider_as_of": data.get("data", {}).get("asof"),
            "source_row_count": len(data.get("data", {}).get("table", {}).get("rows", [])),
            "source_total_records": data.get("data", {}).get("totalrecords"),
        }
        rows = data.get("data", {}).get("table", {}).get("rows", [])
        for row in rows:
            name = str(row.get("name") or "").strip()
            symbol = str(row.get("symbol") or "").strip().upper()
            if not symbol or not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-^]*", symbol):
                continue
            lowered_name = name.lower()
            if symbol in QUARANTINED:
                excluded_symbols[symbol] = QUARANTINED[symbol]
                continue
            classification = _instrument_class(name)
            if classification is None:
                excluded_class_count += 1
                continue
            try:
                market_cap_rank_value = int(str(row.get("marketCap") or "0").replace(",", ""))
            except ValueError:
                continue
            if market_cap_rank_value <= 0:
                continue
            ranked.append((market_cap_rank_value, exchange.upper(), symbol, name))

    ranked.sort(key=lambda item: (-item[0], item[1], item[2]))
    unique = {}
    for _rank_value, exchange, symbol, name in ranked:
        unique.setdefault((exchange, symbol), name)
    selected = list(unique.items())[:limit]
    if len(selected) != limit:
        raise ValueError(f"only {len(selected)} unique common-equity listings available; expected {limit}")

    rows = []
    for rank, ((exchange, symbol), name) in enumerate(selected, start=1):
        listing_key = f"US:{exchange}:{symbol}"
        instrument_type, depositary_ratio = _instrument_class(name) or ("unknown", None)
        rows.append({
            "instrument_id": str(uuid.uuid5(NAMESPACE, listing_key)),
            "identity_basis": "provisional_exchange_listing_key",
            "identity_status": "PROVISIONAL",
            "display_symbol": symbol,
            "provider_symbol_candidates": [{
                "provider": "yahoo",
                "symbol": symbol.replace(".", "-"),
                "mapping_status": "UNVERIFIED",
                "role": "candidate_only",
            }],
            "name": name,
            "asset_class": "equity",
            "instrument_type": instrument_type,
            "depositary_ratio": depositary_ratio,
            "venue": exchange,
            "quote_currency": "USD",
            "timezone": "America/New_York",
            "calendar": "US_EQUITIES",
            "session_template": "US_EQUITIES_RTH",
            "minimum_price_increment": None,
            "share_lot_size": None,
            "point_value": None,
            "corporate_action_policy": "UNKNOWN",
            "source_connection": "UNVERIFIED",
            "historical_bars": "UNVERIFIED",
            "live_bars": "UNVERIFIED",
            "entitlement": "UNKNOWN",
            "terms_retention": "UNKNOWN",
            "pulse_enabled": False,
            "strategy_qualified": False,
            "catalog_rank_snapshot": rank,
        })

    return {
        "schema_version": "icarus.market-universe.catalog.v1",
        "catalog_id": "us-listed-common-equities-top-cap-snapshot",
        "retrieved_at": retrieved_at,
        "selection": {
            "universe": "Nasdaq, NYSE, and NYSE American-listed common stock, ordinary share, and depositary receipt rows; unsupported classes excluded",
            "selection": "top listings by screener-reported market capitalization at retrieval time",
            "count": limit,
            "market_cap_values_persisted": False,
            "excluded_symbols": excluded_symbols,
            "excluded_unsupported_instrument_rows": excluded_class_count,
        },
        "sources": snapshots,
        "counts": {
            "catalogued_count": len(rows),
            "source_connected_count": 0,
            "entitlement_verified_count": 0,
            "historical_bars_qualified_count": 0,
            "live_bars_qualified_count": 0,
            "pulse_enabled_count": 0,
            "strategy_qualified_count": 0,
        },
        "authority": {"execution_authorized": False, "production_decision_authorized": False},
        "instruments": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--out", type=Path, default=Path("icarus_engine/market-universe-200.json"))
    args = parser.parse_args()
    catalog = build(args.limit)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(catalog, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {len(catalog['instruments'])} catalog-only instruments to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
