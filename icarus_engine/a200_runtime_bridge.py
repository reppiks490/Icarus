"""Fail-closed boundary between A200 catalog history evidence and Pulse runtime.

This module deliberately does not create AssetSpec objects or register catalog
symbols. It carries provider receipts for audit and reports whether a batch meets
the evidence gates needed before a separate runtime integration may consume it.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Sequence

from .bar_receipts import BarBatchReceipt
from .pine.timeframe import Bar


@dataclass(frozen=True)
class A200RuntimeBatch:
    """A catalog-identified batch and its evidence; never runtime-authorized here."""

    instrument_id: str
    provider: str
    bars: tuple[Bar, ...]
    receipt: BarBatchReceipt

    def __post_init__(self) -> None:
        if not self.instrument_id or not self.provider:
            raise ValueError("A200 runtime batch requires instrument and provider identity")
        if not isinstance(self.receipt, BarBatchReceipt):
            raise TypeError("A200 runtime batch requires a BarBatchReceipt")
        if self.receipt.instrument_id != self.instrument_id or self.receipt.provider != self.provider:
            raise ValueError("A200 batch identity does not match its receipt")
        # Runtime callers can bypass annotations; canonicalize mutable sequences
        # before validating so later caller mutations cannot alter this batch.
        object.__setattr__(self, "bars", tuple(self.bars))
        if not self.bars or self.receipt.row_count != len(self.bars):
            raise ValueError("A200 batch bars must be non-empty and match receipt row count")
        encoded = json.dumps(
            [[int(row.ts), float(row.o), float(row.h), float(row.l), float(row.c), float(row.v)]
             for row in self.bars],
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
        if hashlib.sha256(encoded).hexdigest() != self.receipt.checksum_sha256:
            raise ValueError("A200 batch bars do not match the validated receipt checksum")

    @classmethod
    def from_history(cls, instrument_id: str, provider: str, bars: Sequence[Bar],
                     receipt: BarBatchReceipt) -> "A200RuntimeBatch":
        """Retain the exact validated history result without rewriting its receipt."""
        return cls(instrument_id, provider, tuple(bars), receipt)


@dataclass(frozen=True)
class A200RuntimeEligibility:
    eligible: bool
    reasons: tuple[str, ...]
    execution_authorized: bool = False


def assess_runtime_eligibility(batch: A200RuntimeBatch, *, canonical_identity_verified: bool,
                                live_feed_qualified: bool) -> A200RuntimeEligibility:
    """Check independent runtime gates; receipt evidence alone cannot assert policy facts."""
    receipt = batch.receipt
    reasons: list[str] = []
    if not canonical_identity_verified or receipt.identity_status != "VERIFIED":
        reasons.append("canonical_identity_unverified")
    if receipt.provider_mapping_status != "VERIFIED":
        reasons.append("provider_mapping_unverified")
    if receipt.entitlement_status != "VERIFIED":
        reasons.append("provider_entitlement_unverified")
    if not receipt.historical_bars_qualified:
        reasons.append("historical_bars_unqualified")
    if not live_feed_qualified:
        reasons.append("live_feed_unqualified")
    # The A200 catalog currently hard-disables execution authority. This boundary
    # only describes data eligibility and must never arm Pulse or a broker.
    return A200RuntimeEligibility(eligible=not reasons, reasons=tuple(reasons), execution_authorized=False)
