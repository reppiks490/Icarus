"""Catalog-aware source adapter for read-only A200 history qualification probes."""
from __future__ import annotations

import time

from .bar_receipts import BarBatchReceipt, make_bar_batch_receipt
from .feeds.yahoo import Yahoo
from .market_universe import snapshot
from .pine.timeframe import Bar


class MarketUniverseAdapter:
    """Resolve a candidate only through its declared provider mapping.

    Returned bars are evidence inputs, not runtime activation. This adapter
    deliberately leaves entitlement and session validation unknown unless a
    future trusted source integration supplies those attestations.
    """

    def __init__(self, yahoo: Yahoo | None = None):
        catalog = snapshot()
        self.catalog_id = catalog["catalog_id"]
        self._instruments = {row["instrument_id"]: row for row in catalog["instruments"]}
        self.yahoo = yahoo or Yahoo()

    def fetch_history(self, instrument_id: str, interval_seconds: int,
                      start_ts: int, end_ts: int) -> tuple[list[Bar], BarBatchReceipt]:
        row = self._instruments.get(instrument_id)
        if row is None:
            raise ValueError(f"unknown A200 instrument ID: {instrument_id}")
        candidates = [mapping for mapping in row["provider_symbol_candidates"]
                      if mapping.get("provider") == "yahoo"]
        if len(candidates) != 1:
            raise ValueError(f"A200 instrument {instrument_id} has no unique Yahoo symbol candidate")
        mapping = candidates[0]
        if mapping.get("mapping_status") != "UNVERIFIED":
            raise ValueError("A200 adapter requires an explicitly declared Yahoo mapping state")
        symbol = mapping["symbol"]
        if interval_seconds not in Yahoo.GRANULARITIES:
            raise ValueError(f"Yahoo does not support {interval_seconds}-second intervals")

        fetched_at_ns = time.time_ns()
        bars = self.yahoo.candles(symbol, interval_seconds, start_ts, end_ts)
        metadata = self.yahoo.meta(symbol)
        received_at_ns = time.time_ns()
        observed_symbol = metadata.get("symbol") or metadata.get("provider_symbol")
        checked, receipt = make_bar_batch_receipt(
            instrument_id=instrument_id,
            provider="yahoo",
            expected_provider_symbol=symbol,
            observed_provider_symbol=observed_symbol,
            interval_seconds=interval_seconds,
            requested_start_ts=start_ts,
            requested_end_ts=end_ts,
            bars=bars,
            fetched_at_ns=fetched_at_ns,
            received_at_ns=received_at_ns,
            entitlement_status="UNKNOWN",
            session_validation_status="UNKNOWN",
            provider_mapping_status=mapping["mapping_status"],
        )
        return checked, receipt
