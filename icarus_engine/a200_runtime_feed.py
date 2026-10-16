"""Fail-closed historical A200 admission into an isolated Pulse research runner.

This module is deliberately separate from live Portfolio assets. It consumes
historical provider batches only, creates an in-memory Pulse runner only after
catalog and receipt qualification, and never connects to a broker or grants
execution authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import hashlib
import json
import threading
import time
from typing import Any, Mapping, Sequence

from .bar_receipts import BarBatchReceipt, make_bar_batch_receipt
from .calendar import get_calendar
from .market_universe import snapshot
from .pine.timeframe import Bar


MAX_RECEIPT_AGE_NS = 15 * 60 * 1_000_000_000
MAX_FUTURE_SKEW_NS = 5 * 60 * 1_000_000_000


@dataclass(frozen=True)
class A200PulseAdmission:
    admitted: bool
    instrument_id: str
    symbol: str | None
    provider: str | None
    reasons: tuple[str, ...]
    receipt_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "admitted": self.admitted,
            "instrument_id": self.instrument_id,
            "symbol": self.symbol,
            "provider": self.provider,
            "reasons": list(self.reasons),
            "receipt_id": self.receipt_id,
            "execution_authorized": False,
            "live_authorized": False,
        }


def _positive_number(value: object) -> bool:
    try:
        return math.isfinite(float(value)) and float(value) > 0
    except (TypeError, ValueError, OverflowError):
        return False


def _catalog_row(catalog: Mapping[str, Any], instrument_id: str) -> Mapping[str, Any] | None:
    rows = catalog.get("instruments")
    if not isinstance(rows, list):
        return None
    matches = [row for row in rows if isinstance(row, Mapping) and row.get("instrument_id") == instrument_id]
    return matches[0] if len(matches) == 1 else None


def _listing_identity_is_current(catalog: Mapping[str, Any], row: Mapping[str, Any]) -> bool:
    crosswalk = catalog.get("listing_crosswalk")
    if not isinstance(crosswalk, Mapping) or crosswalk.get("status") != "CURRENT":
        return False
    results = crosswalk.get("results")
    if not isinstance(results, list):
        return False
    matches = [item for item in results if isinstance(item, Mapping)
               and item.get("instrument_id") == row.get("instrument_id")]
    if len(matches) != 1:
        return False
    item = matches[0]
    expected = item.get("expected")
    observed = item.get("observed")
    return bool(
        item.get("status") == "MATCHED"
        and isinstance(expected, Mapping)
        and isinstance(observed, Mapping)
        and expected.get("symbol") == str(row.get("display_symbol", "")).upper()
        and expected.get("venue") == str(row.get("venue", "")).upper()
        and observed == expected
    )


def _qualification_fingerprint(row: Mapping[str, Any], provider_mapping: Mapping[str, Any]) -> str:
    fields = (
        "instrument_id", "display_symbol", "name", "venue", "asset_class", "calendar", "timezone",
        "identity_status", "source_connection", "entitlement", "historical_bars", "pulse_enabled",
        "strategy_qualified", "minimum_price_increment", "point_value", "share_lot_size",
    )
    payload = {field: row.get(field) for field in fields}
    payload["provider_mapping"] = dict(provider_mapping)
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def _receipt_matches_bars(
    *, row: Mapping[str, Any], bars: Sequence[Bar], receipt: BarBatchReceipt,
    provider_mapping: Mapping[str, Any],
) -> bool:
    if receipt.schema_version != "icarus.bar-batch-receipt.v1":
        return False
    if receipt.execution_authorized is not False:
        return False
    if receipt.instrument_id != row.get("instrument_id"):
        return False
    if receipt.provider != provider_mapping.get("provider"):
        return False
    expected_symbol = provider_mapping.get("symbol")
    if not isinstance(expected_symbol, str) or not expected_symbol:
        return False
    if receipt.expected_provider_symbol.upper() != expected_symbol.upper():
        return False
    if receipt.observed_provider_symbol is None or receipt.observed_provider_symbol.upper() != expected_symbol.upper():
        return False
    if receipt.provider_symbol_match_status != "MATCHED" or receipt.provider_mapping_status != "VERIFIED":
        return False
    if receipt.identity_status != "VERIFIED" or receipt.entitlement_status != "VERIFIED":
        return False
    if receipt.session_validation_status != "VERIFIED" or receipt.bar_close_status != "VERIFIED":
        return False
    if receipt.timestamp_alignment_status != "VERIFIED" or receipt.gap_validation_status != "VERIFIED":
        return False
    if receipt.historical_bars_qualified is not True or receipt.interval_gap_count != 0:
        return False
    if receipt.calendar_timezone != row.get("timezone"):
        return False
    if not bars or len(bars) != receipt.row_count:
        return False
    try:
        calendar = get_calendar(str(row.get("calendar")))
        expected = calendar.expected_bar_timestamps(
            receipt.requested_start_ts, receipt.requested_end_ts, receipt.interval_seconds,
            max_bars=100_000,
        )
        rebuilt_bars, rebuilt = make_bar_batch_receipt(
            instrument_id=receipt.instrument_id,
            provider=receipt.provider,
            expected_provider_symbol=receipt.expected_provider_symbol,
            observed_provider_symbol=receipt.observed_provider_symbol,
            interval_seconds=receipt.interval_seconds,
            requested_start_ts=receipt.requested_start_ts,
            requested_end_ts=receipt.requested_end_ts,
            bars=bars,
            fetched_at_ns=receipt.fetched_at_ns,
            received_at_ns=receipt.received_at_ns,
            entitlement_status=receipt.entitlement_status,
            session_validation_status=receipt.session_validation_status,
            provider_mapping_status=receipt.provider_mapping_status,
            alignment_validator=lambda ts: calendar.is_aligned(ts, receipt.interval_seconds),
            expected_bar_timestamps=expected,
            calendar_timezone=calendar.timezone_name,
            bar_close_status=receipt.bar_close_status,
            timestamp_normalization=receipt.timestamp_normalization,
        )
    except (ValueError, TypeError, OverflowError):
        return False
    return rebuilt_bars == list(bars) and rebuilt == receipt


def qualify_a200_pulse_batch(
    instrument_id: str,
    bars: Sequence[Bar],
    receipt: BarBatchReceipt,
    *,
    now_ns: int | None = None,
) -> A200PulseAdmission:
    """Validate that one historical batch is eligible to enter Pulse research.

    Positive admission requires explicit catalog qualification, current public
    listing identity, a unique verified provider mapping, a fresh qualified bar
    receipt, and valid instrument economics. Current A200 catalog rows fail this
    gate by design.
    """
    reasons: list[str] = []
    catalog = snapshot()
    row = _catalog_row(catalog, str(instrument_id))
    if row is None:
        return A200PulseAdmission(False, str(instrument_id), None, None, ("UNKNOWN_INSTRUMENT",))
    symbol = str(row.get("display_symbol") or "") or None
    provider = receipt.provider if isinstance(receipt, BarBatchReceipt) else None

    if row.get("source_connection") != "VERIFIED":
        reasons.append("SOURCE_NOT_VERIFIED")
    if row.get("identity_status") != "VERIFIED" or not _listing_identity_is_current(catalog, row):
        reasons.append("IDENTITY_NOT_VERIFIED")
    if row.get("entitlement") != "VERIFIED":
        reasons.append("ENTITLEMENT_NOT_VERIFIED")
    if row.get("historical_bars") != "QUALIFIED":
        reasons.append("HISTORICAL_BARS_NOT_QUALIFIED")
    if row.get("pulse_enabled") is not True:
        reasons.append("PULSE_DISABLED")
    if row.get("strategy_qualified") is not True:
        reasons.append("STRATEGY_NOT_QUALIFIED")
    if not _positive_number(row.get("minimum_price_increment")):
        reasons.append("PRICE_INCREMENT_UNQUALIFIED")
    if not _positive_number(row.get("point_value")):
        reasons.append("POINT_VALUE_UNQUALIFIED")
    if not _positive_number(row.get("share_lot_size")):
        reasons.append("SHARE_LOT_SIZE_UNQUALIFIED")

    mappings = row.get("provider_symbol_candidates")
    mapping_matches = [candidate for candidate in mappings or []
                       if isinstance(candidate, Mapping) and candidate.get("provider") == provider]
    provider_mapping = mapping_matches[0] if len(mapping_matches) == 1 else None
    if provider_mapping is None or provider_mapping.get("mapping_status") != "VERIFIED":
        reasons.append("PROVIDER_MAPPING_NOT_VERIFIED")

    if not isinstance(receipt, BarBatchReceipt):
        reasons.append("RECEIPT_TYPE_INVALID")
    elif provider_mapping is not None and not _receipt_matches_bars(
            row=row, bars=bars, receipt=receipt, provider_mapping=provider_mapping):
        reasons.append("BAR_RECEIPT_INVALID_OR_UNQUALIFIED")
    if isinstance(receipt, BarBatchReceipt):
        clock = time.time_ns() if now_ns is None else now_ns
        age = clock - receipt.received_at_ns
        if age < -MAX_FUTURE_SKEW_NS:
            reasons.append("RECEIPT_FROM_FUTURE")
        elif age > MAX_RECEIPT_AGE_NS:
            reasons.append("RECEIPT_STALE")
        if receipt.received_at_ns < receipt.fetched_at_ns:
            reasons.append("RECEIPT_CLOCK_INVALID")

    deduplicated = tuple(dict.fromkeys(reasons))
    return A200PulseAdmission(
        not deduplicated, str(instrument_id), symbol, provider,
        deduplicated, receipt.receipt_id if isinstance(receipt, BarBatchReceipt) else None,
    )


class _ResearchOnlyPulse:
    """State needed by PulseStrategy without any order, fill, or broker surface."""
    def __init__(self):
        self.open: list[Any] = []
        self.closed: list[Any] = []
        self.fills: list[Any] = []
        self.netprofit = 0.0
        self.commands = 0

    def process_bar(self, *_args: Any, **_kwargs: Any) -> None:
        # Pulse decisions are evaluated on the closed bar, but research batches
        # never match commands into simulated positions or fills.
        return None

    def entry(self, *_args: Any, **_kwargs: Any) -> None:
        self.commands += 1

    def exit(self, *_args: Any, **_kwargs: Any) -> None:
        self.commands += 1

    def close(self, *_args: Any, **_kwargs: Any) -> None:
        self.commands += 1

    def cancel(self, *_args: Any, **_kwargs: Any) -> None:
        self.commands += 1


class A200PulseResearchRuntime:
    """Stateful historical Pulse consumer with no execution or network side effects."""

    def __init__(self, *, chart_minutes: int = 5):
        if type(chart_minutes) is not int or chart_minutes <= 0 or chart_minutes > 1440:
            raise ValueError("chart_minutes must be a positive integer no greater than one day")
        self.chart_minutes = chart_minutes
        self._sessions: dict[str, Any] = {}
        self._lock = threading.RLock()

    def ingest_history(
        self,
        instrument_id: str,
        bars: Sequence[Bar],
        receipt: BarBatchReceipt,
    ) -> dict[str, Any]:
        admission = qualify_a200_pulse_batch(instrument_id, bars, receipt)
        if not admission.admitted:
            return {"admission": admission.to_dict(), "processed_bars": 0, "pulse": None,
                    "research_only": True, "execution_authorized": False}
        if receipt.interval_seconds < 60 or receipt.interval_seconds % 60:
            rejected = A200PulseAdmission(
                False, instrument_id, admission.symbol, admission.provider,
                ("PULSE_REQUIRES_MINUTE_OR_COARSER_BARS",), receipt.receipt_id,
            )
            return {"admission": rejected.to_dict(), "processed_bars": 0, "pulse": None,
                    "research_only": True, "execution_authorized": False}
        sub_minutes = receipt.interval_seconds // 60
        if self.chart_minutes % sub_minutes:
            rejected = A200PulseAdmission(
                False, instrument_id, admission.symbol, admission.provider,
                ("BAR_INTERVAL_NOT_DIVISOR_OF_PULSE_CHART",), receipt.receipt_id,
            )
            return {"admission": rejected.to_dict(), "processed_bars": 0, "pulse": None,
                    "research_only": True, "execution_authorized": False}

        with self._lock:
            session = self._sessions.get(instrument_id)
            catalog = snapshot()
            current_row = _catalog_row(catalog, instrument_id)
            current_mapping = next((item for item in current_row.get("provider_symbol_candidates", [])
                                    if item.get("provider") == receipt.provider), None) if current_row else None
            if current_row is None or current_mapping is None:
                rejected = A200PulseAdmission(False, instrument_id, admission.symbol, admission.provider,
                                               ("RESEARCH_CATALOG_IDENTITY_MISSING",), receipt.receipt_id)
                return {"admission": rejected.to_dict(), "processed_bars": 0, "pulse": None,
                        "research_only": True, "execution_authorized": False}
            fingerprint = _qualification_fingerprint(current_row, current_mapping)
            if session is None:
                session = self._new_session(admission.symbol, receipt, self.chart_minutes, current_row,
                                            current_mapping, fingerprint)
                self._sessions[instrument_id] = session
            elif (session["provider"] != receipt.provider
                  or session["provider_symbol"] != receipt.expected_provider_symbol
                  or session["interval_seconds"] != receipt.interval_seconds
                  or session["qualification_fingerprint"] != fingerprint):
                rejected = A200PulseAdmission(False, instrument_id, admission.symbol, admission.provider,
                                               ("RESEARCH_SESSION_IDENTITY_OR_QUALIFICATION_CHANGED",), receipt.receipt_id)
                return {"admission": rejected.to_dict(), "processed_bars": 0, "pulse": None,
                        "research_only": True, "execution_authorized": False}
            runner = session["runner"]
            before = runner.last_sub_ts
            forward_bars = [bar for bar in bars if before is None or bar.ts > before]
            if before is not None and forward_bars:
                calendar = get_calendar(str(current_row["calendar"]))
                expected = calendar.expected_bar_timestamps(
                    before, forward_bars[-1].ts + receipt.interval_seconds,
                    receipt.interval_seconds, max_bars=100_000,
                )
                observed = [before, *(bar.ts for bar in forward_bars)]
                if expected != observed:
                    rejected = A200PulseAdmission(False, instrument_id, admission.symbol, admission.provider,
                                                   ("BATCH_NOT_CONTIGUOUS_WITH_PRIOR_HISTORY",), receipt.receipt_id)
                    return {"admission": rejected.to_dict(), "processed_bars": 0, "pulse": None,
                            "research_only": True, "execution_authorized": False}
            for bar in bars:
                runner.on_sub_bar(bar, sub_minutes, live=False, record=False)
            processed = len(forward_bars)
            state = dict(runner.state) if runner.state else None
            return {
                "admission": admission.to_dict(),
                "processed_bars": processed,
                "pulse": state,
                "last_bar_ts": runner.last_sub_ts,
                "bar_index": runner.bar_index,
                "strategy_commands_observed": session["emulator"].commands,
                "strategy_command_semantics": "signal-only; commands are discarded and cannot create fills",
                "research_only": True,
                "execution_authorized": False,
                "live_authorized": False,
            }

    def _new_session(self, symbol: str | None, receipt: BarBatchReceipt, chart_minutes: int,
                     row: Mapping[str, Any],
                     mapping: Mapping[str, Any], qualification_fingerprint: str) -> dict[str, Any]:
        if row is None or symbol is None:
            raise ValueError("qualified A200 instrument disappeared from the catalog")
        from .assets import AssetSpec
        from .runtime import AssetRunner, Journal, RunnerConfig
        from .strategy.inputs import Inputs

        spec = AssetSpec(
            symbol=symbol,
            name=str(row["name"]),
            feed="a200_research",
            ticker=str(mapping["symbol"]),
            calendar="us_equities",
            mintick=float(row["minimum_price_increment"]),
            multiplier=float(row["point_value"]),
            kind="equity",
            chart_tf=str(chart_minutes),
            chart_type="real",
            fill_on="real",
            session="rth",
        )
        emulator = _ResearchOnlyPulse()
        inputs = Inputs(point_value=spec.multiplier)
        strategy_runner = AssetRunner(
            RunnerConfig(spec=spec, inputs=inputs, warmup_bars=0, profile="nq"),
            Journal(":memory:"), {"a200_research": object()},
        )
        # AssetRunner normally owns an Emulator. Replace it with a command sink
        # before its first bar so Pulse calculations cannot make even simulated fills.
        strategy_runner.em = emulator
        return {
            "runner": strategy_runner,
            "emulator": emulator,
            "provider": receipt.provider,
            "provider_symbol": receipt.expected_provider_symbol,
            "interval_seconds": receipt.interval_seconds,
            "qualification_fingerprint": qualification_fingerprint,
        }

    def close(self) -> None:
        """Release in-memory runner journals when the owning Portfolio stops."""
        with self._lock:
            sessions = list(self._sessions.values())
            self._sessions.clear()
        for session in sessions:
            journal = session["runner"].journal
            journal.close()
