#!/usr/bin/env python3
"""Read-only Yahoo historical availability probe for the A200 candidate catalog.

The report stores response identity/status, time bounds, counts, and checksums;
it never stores raw OHLCV values and never upgrades entitlements or readiness.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time

from icarus_engine.market_universe import (
    catalog_evidence_digest, snapshot, source_probe_counts, source_probe_results_digest,
)
from icarus_engine.market_universe_adapter import MarketUniverseAdapter
from icarus_engine.feeds.yahoo import Yahoo


def _record(row: dict, adapter: MarketUniverseAdapter, start_ts: int, end_ts: int) -> dict:
    fetched_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    mapping = row["provider_symbol_candidates"][0]
    record = {
        "instrument_id": row["instrument_id"],
        "display_symbol": row["display_symbol"],
        "venue": row["venue"],
        "provider": "yahoo",
        "provider_symbol_candidate": mapping["symbol"],
        "provider_mapping_status": mapping["mapping_status"],
        "requested_interval_seconds": 86400,
        "requested_start_ts": start_ts,
        "requested_end_ts": end_ts,
        "probe_started_at": fetched_at,
    }
    try:
        bars, receipt = adapter.fetch_history(row["instrument_id"], 86400, start_ts, end_ts)
        record.update({
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
    except Exception as exc:  # per-symbol failures must not stop the 200-row sweep
        record.update({
            "probe_status": "ERROR",
            "error_type": type(exc).__name__,
            "error": f"provider_error:{type(exc).__name__}",
        })
    return record


def run(*, limit: int = 200, start_ts: int, end_ts: int,
        out: Path = Path("reports/a200-yahoo-history-probe.json"), pause_seconds: float = 0.25,
        resume: bool = True) -> dict:
    if type(limit) is not int or not 1 <= limit <= 200:
        raise ValueError("limit must be between 1 and 200")
    if type(start_ts) is not int or type(end_ts) is not int or start_ts >= end_ts:
        raise ValueError("probe window must use integer UTC timestamps with start before end")
    if type(pause_seconds) not in (float, int) or pause_seconds < 0 or pause_seconds > 10:
        raise ValueError("pause_seconds must be between zero and ten")

    catalog = snapshot()
    rows = catalog["instruments"][:limit]
    records_by_id = {}
    if resume and out.exists():
        try:
            prior = json.loads(out.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            prior = {}
        if not isinstance(prior, dict):
            prior = {}
        same_window = prior.get("window") == {"start_ts": start_ts, "end_ts": end_ts}
        prior_results = prior.get("results")
        reusable = (
            prior.get("schema_version") == "icarus.market-universe.source-probe.v3"
            and prior.get("catalog_id") == catalog["catalog_id"]
            and prior.get("catalog_snapshot_sha256") == catalog_evidence_digest(catalog)
            and prior.get("probe_implementation") == "tools.probe_a200_yahoo.v3"
            and prior.get("calendar_schedule_version") == "nyse-rth-2026-2028.v1"
            and isinstance(prior_results, list)
            and all(isinstance(row, dict) for row in prior_results)
            and prior.get("results_sha256") == source_probe_results_digest(prior_results)
            and prior.get("counts") == source_probe_counts(prior_results)
            and prior.get("raw_ohlcv_persisted") is False
            and same_window
        )
        if reusable:
            by_id = {row.get("instrument_id"): row for row in prior_results if isinstance(row, dict)}
            expected_ids = {row["instrument_id"] for row in rows}
            if (len(by_id) == len(prior_results) and set(by_id).issubset(expected_ids)
                    and all(_mapping_matches(by_id[key], catalog, key) for key in by_id)):
                records_by_id = by_id

    adapter = MarketUniverseAdapter(Yahoo(min_interval=0.0))
    for index, row in enumerate(rows, start=1):
        if row["instrument_id"] in records_by_id:
            continue
        records_by_id[row["instrument_id"]] = _record(row, adapter, start_ts, end_ts)
        report = _assemble(catalog, rows, start_ts, end_ts, records_by_id)
        out.parent.mkdir(parents=True, exist_ok=True)
        temp = out.with_suffix(out.suffix + ".tmp")
        temp.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temp.replace(out)
        status = records_by_id[row["instrument_id"]]["probe_status"]
        print(f"{index}/{len(rows)} {row['display_symbol']} {status}", flush=True)
        if pause_seconds:
            time.sleep(pause_seconds)
    return _assemble(catalog, rows, start_ts, end_ts, records_by_id)


def _assemble(catalog: dict, rows: list[dict], start_ts: int, end_ts: int,
              records_by_id: dict[str, dict]) -> dict:
    results = [records_by_id[row["instrument_id"]] for row in rows if row["instrument_id"] in records_by_id]
    return {
        "schema_version": "icarus.market-universe.source-probe.v3",
        "probe_implementation": "tools.probe_a200_yahoo.v3",
        "calendar_schedule_version": "nyse-rth-2026-2028.v1",
        "catalog_id": catalog["catalog_id"],
        "catalog_snapshot_sha256": catalog_evidence_digest(catalog),
        "catalog_retrieved_at": catalog["retrieved_at"],
        "probe_provider": "yahoo",
        "probe_started_at": results[0]["probe_started_at"] if results else None,
        "probe_updated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "window": {"start_ts": start_ts, "end_ts": end_ts},
        "requested_count": len(rows),
        "completed_count": len(results),
        "results_sha256": source_probe_results_digest(results),
        "counts": source_probe_counts(results),
        "authority": {"pulse_enabled": False, "strategy_qualified": False, "execution_authorized": False},
        "raw_ohlcv_persisted": False,
        "results": results,
    }


def _mapping_matches(result: dict, catalog: dict, instrument_id: str) -> bool:
    instrument = next((row for row in catalog["instruments"] if row["instrument_id"] == instrument_id), None)
    mappings = [candidate for candidate in (instrument or {}).get("provider_symbol_candidates", [])
                if candidate.get("provider") == "yahoo"]
    return (len(mappings) == 1 and result.get("provider") == "yahoo"
            and result.get("provider_symbol_candidate") == mappings[0].get("symbol")
            and result.get("provider_mapping_status") == mappings[0].get("mapping_status")
            and result.get("probe_status") in ("RESPONSE_RECEIVED", "NO_BARS", "ERROR"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--start", default="2026-10-01T00:00:00Z")
    parser.add_argument("--end", default="2026-10-15T00:00:00Z")
    parser.add_argument("--out", type=Path, default=Path("icarus_engine/a200-yahoo-history-probe.json"))
    parser.add_argument("--pause-seconds", type=float, default=0.25)
    parser.add_argument("--no-resume", action="store_true")
    args = parser.parse_args()
    start = int(datetime.fromisoformat(args.start.replace("Z", "+00:00")).timestamp())
    end = int(datetime.fromisoformat(args.end.replace("Z", "+00:00")).timestamp())
    result = run(limit=args.limit, start_ts=start, end_ts=end, out=args.out,
                 pause_seconds=args.pause_seconds, resume=not args.no_resume)
    print(json.dumps({"completed": result["completed_count"], "counts": result["counts"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
