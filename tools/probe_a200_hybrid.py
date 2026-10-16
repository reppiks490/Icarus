#!/usr/bin/env python3
"""Read-only, per-provider A200 availability probe; never stores raw bars."""
from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import time

from icarus_engine.market_universe import catalog_evidence_digest, snapshot, source_probe_results_digest
from icarus_engine.market_universe_adapter import MarketUniverseAdapter

DEFAULT_OUT = Path("reports/a200-hybrid-history-probe.json")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("probe dates must include a UTC offset")
    return parsed.astimezone(timezone.utc)


def _probe_one(adapter: MarketUniverseAdapter, instrument: dict, mapping: dict,
               start_ts: int, end_ts: int) -> dict:
    provider = mapping["provider"]
    row = {
        "instrument_id": instrument["instrument_id"],
        "provider": provider,
        "provider_symbol_candidate": mapping["symbol"],
        "provider_mapping_status": mapping["mapping_status"],
        "requested_start_ts": start_ts,
        "requested_end_ts": end_ts,
        "probe_started_at": _utc_now(),
    }
    if not adapter.source_configured(provider):
        row["probe_status"] = "NOT_CONFIGURED"
        row["error_code"] = "source_not_configured"
        return row
    try:
        bars, receipt = adapter.fetch_history(
            instrument["instrument_id"], 86400, start_ts, end_ts, provider=provider,
        )
        row.update({
            "probe_status": "RESPONSE_RECEIVED" if bars else "NO_BARS",
            "provider_symbol_match_status": receipt.provider_symbol_match_status,
            "canonical_identity_status": receipt.identity_status,
            "entitlement_status": receipt.entitlement_status,
            "session_validation_status": receipt.session_validation_status,
            "historical_bars_qualified": receipt.historical_bars_qualified,
            "row_count": receipt.row_count,
            "received_start_ts": receipt.received_start_ts,
            "received_end_ts": receipt.received_end_ts,
            "interval_gap_count": receipt.interval_gap_count,
            "timestamp_alignment_status": receipt.timestamp_alignment_status,
            "checksum_sha256": receipt.checksum_sha256,
            "receipt_id": receipt.receipt_id,
            "fetched_at_ns": receipt.fetched_at_ns,
            "received_at_ns": receipt.received_at_ns,
        })
    except Exception as exc:
        row.update({"probe_status": "ERROR", "error_type": type(exc).__name__,
                    "error_code": f"provider_error:{type(exc).__name__}"})
    return row


def run(*, limit: int = 1, start_ts: int, end_ts: int,
        out: Path = DEFAULT_OUT,
        pause_seconds: float = 0.25, adapter: MarketUniverseAdapter | None = None,
        providers: tuple[str, ...] | list[str] | None = None) -> dict:
    if type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError("limit must be between 1 and 200")
    if type(start_ts) is not int or type(end_ts) is not int or start_ts >= end_ts:
        raise ValueError("probe window must use integer UTC timestamps with start before end")
    if type(pause_seconds) not in (int, float) or not 0 <= pause_seconds <= 10:
        raise ValueError("pause_seconds must be between zero and ten")
    catalog = snapshot()
    results = []
    rows = catalog["instruments"][:limit]
    available_providers = tuple(dict.fromkeys(
        mapping.get("provider")
        for instrument in rows
        for mapping in instrument.get("provider_symbol_candidates", [])
        if isinstance(mapping.get("provider"), str) and mapping["provider"]
    ))
    if providers is None:
        selected_providers = ("yahoo",) if "yahoo" in available_providers else available_providers[:1]
    else:
        selected_providers = tuple(providers)
    if (not selected_providers
            or any(not isinstance(provider, str) or provider not in available_providers
                   for provider in selected_providers)
            or len(selected_providers) != len(set(selected_providers))):
        raise ValueError("providers must be a non-empty unique subset of catalog providers")
    selected_set = set(selected_providers)
    adapter = adapter or MarketUniverseAdapter(providers=selected_providers)
    for index, instrument in enumerate(rows, start=1):
        mappings = instrument.get("provider_symbol_candidates", [])
        seen = set()
        for mapping in mappings:
            provider = mapping.get("provider")
            if not isinstance(provider, str) or not provider or provider in seen:
                results.append({"instrument_id": instrument["instrument_id"],
                                "provider": str(provider or "unknown"), "probe_status": "ERROR",
                                "probe_started_at": _utc_now(),
                                "requested_start_ts": start_ts,
                                "requested_end_ts": end_ts,
                                "error_code": "invalid_provider_mapping"})
                continue
            seen.add(provider)
            if provider in selected_set:
                results.append(_probe_one(adapter, instrument, mapping, start_ts, end_ts))
            else:
                results.append({
                    "instrument_id": instrument["instrument_id"],
                    "provider": provider,
                    "provider_symbol_candidate": mapping.get("symbol"),
                    "provider_mapping_status": mapping.get("mapping_status"),
                    "requested_start_ts": start_ts,
                    "requested_end_ts": end_ts,
                    "probe_started_at": _utc_now(),
                    "probe_status": "NOT_REQUESTED",
                    "error_code": "provider_not_selected",
                })
        if pause_seconds and index < len(rows):
            time.sleep(pause_seconds)
    now = _utc_now()
    counts = {}
    for item in results:
        key = f"{item['provider'].lower()}_{item['probe_status'].lower()}_count"
        counts[key] = counts.get(key, 0) + 1
    report = {
        "schema_version": "icarus.market-universe.hybrid-probe.v1",
        "probe_implementation": "tools.probe_a200_hybrid.v1",
        "catalog_id": catalog["catalog_id"],
        "catalog_snapshot_sha256": catalog_evidence_digest(catalog),
        "probe_started_at": results[0].get("probe_started_at") if results else now,
        "probe_updated_at": now,
        "window": {"start_ts": start_ts, "end_ts": end_ts},
        "requested_instrument_count": len(rows),
        "requested_providers": list(selected_providers),
        "completed_result_count": len(results),
        "results_sha256": source_probe_results_digest(results),
        "counts": counts,
        "authority": {"pulse_enabled": False, "strategy_qualified": False,
                      "execution_authorized": False},
        "raw_ohlcv_persisted": False,
        "results": results,
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    temp = out.with_suffix(out.suffix + ".tmp")
    temp.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(out)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=1,
                        help="number of catalog instruments to probe (default: 1; max: 200)")
    parser.add_argument("--start", help="inclusive UTC ISO-8601 start (default: 14 days before end)")
    parser.add_argument("--end", help="exclusive UTC ISO-8601 end (default: current UTC time)")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help="report path; use the packaged path explicitly to publish API state")
    parser.add_argument("--pause-seconds", type=float, default=0.25)
    parser.add_argument("--providers", nargs="+", choices=("yahoo", "fmp"),
                        help="providers to request (default: Yahoo only; FMP requires explicit selection)")
    args = parser.parse_args()
    end_dt = _parse_utc(args.end) if args.end else datetime.now(timezone.utc).replace(microsecond=0)
    start_dt = _parse_utc(args.start) if args.start else end_dt - timedelta(days=14)
    start, end = int(start_dt.timestamp()), int(end_dt.timestamp())
    report = run(limit=args.limit, start_ts=start, end_ts=end, out=args.out,
                 pause_seconds=args.pause_seconds,
                 providers=tuple(args.providers) if args.providers else None)
    print(json.dumps({"completed": report["completed_result_count"],
                      "counts": report["counts"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
