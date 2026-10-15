"""Catalog-aware source adapter for read-only A200 history qualification probes."""
from __future__ import annotations

from dataclasses import dataclass
import os
import time

from .bar_receipts import BarBatchReceipt, make_bar_batch_receipt
from .feeds.yahoo import Yahoo
from .market_universe import snapshot
from .pine.timeframe import Bar
from .calendar import get_calendar


@dataclass(frozen=True)
class ProviderHistoryResult:
    provider: str
    bars: list[Bar] | None
    receipt: BarBatchReceipt | None
    error: str | None = None


class MarketUniverseAdapter:
    """Resolve a candidate only through its declared provider mapping.

    Returned bars are evidence inputs, not runtime activation. This adapter
    deliberately leaves entitlement and session validation unknown unless a
    future trusted source integration supplies those attestations.
    """

    def __init__(self, yahoo: Yahoo | None = None, fmp: object | None = None):
        catalog = snapshot()
        self.catalog_id = catalog["catalog_id"]
        self._instruments = {row["instrument_id"]: row for row in catalog["instruments"]}
        self.yahoo = yahoo or Yahoo()
        self._sources = {"yahoo": self.yahoo}
        if fmp is not None:
            self._sources["fmp"] = fmp
        elif os.environ.get("FMP_API_KEY"):
            from .feeds.fmp import FmpHistory
            self._sources["fmp"] = FmpHistory()

    def fetch_history(self, instrument_id: str, interval_seconds: int,
                      start_ts: int, end_ts: int, *, provider: str = "yahoo") -> tuple[list[Bar], BarBatchReceipt]:
        row = self._instruments.get(instrument_id)
        if row is None:
            raise ValueError(f"unknown A200 instrument ID: {instrument_id}")
        candidates = [mapping for mapping in row["provider_symbol_candidates"]
                      if mapping.get("provider") == provider]
        if len(candidates) != 1:
            raise ValueError(f"A200 instrument {instrument_id} has no unique {provider} symbol candidate")
        mapping = candidates[0]
        mapping_status = mapping.get("mapping_status")
        if mapping_status not in ("UNVERIFIED", "VERIFIED"):
            raise ValueError(f"A200 {provider} mapping must be explicitly UNVERIFIED or VERIFIED")
        symbol = mapping["symbol"]
        source = self._sources.get(provider)
        if source is None:
            raise RuntimeError(f"A200 {provider} history source is not configured")
        if interval_seconds not in source.GRANULARITIES:
            raise ValueError(f"{provider} does not support {interval_seconds}-second intervals")

        fetched_at_ns = time.time_ns()
        bars = source.candles(symbol, interval_seconds, start_ts, end_ts)
        metadata = source.meta(symbol)
        received_at_ns = time.time_ns()
        observed_symbol = metadata.get("symbol") or metadata.get("provider_symbol")
        # Schedule evidence is available only for dates in the published,
        # bounded exchange calendar. Older/out-of-range requests stay explicitly
        # unqualified instead of extrapolating session rules.
        expected = None
        alignment = None
        session_status = "UNKNOWN"
        try:
            calendar = get_calendar(row["calendar"])
            expected = calendar.expected_bar_timestamps(start_ts, end_ts, interval_seconds)
            alignment = lambda ts: calendar.is_aligned(ts, interval_seconds)
            session_status = "VERIFIED"
        except (KeyError, ValueError, TypeError):
            pass
        checked, receipt = make_bar_batch_receipt(
            instrument_id=instrument_id,
            provider=provider,
            expected_provider_symbol=symbol,
            observed_provider_symbol=observed_symbol,
            interval_seconds=interval_seconds,
            requested_start_ts=start_ts,
            requested_end_ts=end_ts,
            bars=bars,
            fetched_at_ns=fetched_at_ns,
            received_at_ns=received_at_ns,
            entitlement_status="UNKNOWN",
            session_validation_status=session_status,
            provider_mapping_status=mapping_status,
            alignment_validator=alignment,
            expected_bar_timestamps=expected,
        )
        return checked, receipt

    def fetch_hybrid_history(self, instrument_id: str, interval_seconds: int,
                             start_ts: int, end_ts: int) -> list[ProviderHistoryResult]:
        """Probe every declared source independently; never merge bars or hide failures."""
        row = self._instruments.get(instrument_id)
        if row is None:
            raise ValueError(f"unknown A200 instrument ID: {instrument_id}")
        results = []
        for mapping in row["provider_symbol_candidates"]:
            provider = str(mapping.get("provider") or "")
            if not provider:
                continue
            if provider not in self._sources:
                results.append(ProviderHistoryResult(provider, None, None, "source_not_configured"))
                continue
            try:
                bars, receipt = self.fetch_history(
                    instrument_id, interval_seconds, start_ts, end_ts, provider=provider,
                )
                results.append(ProviderHistoryResult(provider, bars, receipt))
            except Exception as exc:
                results.append(ProviderHistoryResult(provider, None, None, str(exc)))
        return results
