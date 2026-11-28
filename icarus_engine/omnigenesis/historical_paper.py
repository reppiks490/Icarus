"""Phase 21: causality-audited paper replay of operator-supplied historical bars.

This does not connect to data providers, brokers or external networks. A file
author can forge both bar data and the expected SHA-256: hash agreement is
content identity, not vendor authenticity. All fills and P&L are *modelled*
at historical bar openings, not observed exchange orders, quotes, or profits.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

from .contracts import canonical_bytes, identity, utc
from .paper_harness import _execution, _risk, _simulate, _strategy

_AUTHORITY = {"research_only": True, "execution_authorized": False,
              "production_decision_authorized": False, "auto_promote": False}
_SCHEMA = "icarus-omnigenesis-historical-paper-v1"
_MAIN_FIELDS = {"schema_version", "evidence", "bars", "strategy",
                "execution", "risk"}
_EVIDENCE_FIELDS = {"asset", "source_commit", "provider",
                    "license_reference", "captured_at", "declared_sha256"}
_BAR_FIELDS = {"bar_id", "opened_at", "closed_at", "received_at",
               "open_ticks", "high_ticks", "low_ticks", "close_ticks"}
_ASSET = re.compile(r"^[A-Z0-9._-]{1,24}$")
_SHA40 = re.compile(r"^[0-9a-f]{40}$")
_SHA64 = re.compile(r"^[0-9a-f]{64}$")


def _name(value: Any, field: str, limit: int = 128) -> str:
    if (not isinstance(value, str) or not 1 <= len(value) <= limit
            or not value.isprintable()):
        raise ValueError("invalid " + field)
    return value


def _tick(value: Any, name: str) -> int:
    if type(value) is not int or not 1 <= value <= 10**12:
        raise ValueError("invalid positive integer " + name)
    return value


def run_historical_paper_replay(spec: Mapping[str, Any]) -> dict:
    """Only explicit as-of data can influence hypothetical subsequent fills.

    Bar-close decisions are available at received_at, not closed_at.
    A scheduled entry may be delayed past its requested latency to the
    earliest opening strictly AFTER the decision's receipt timestamp.
    Close-triggered risk exits obey the same rule. If no such opening
    remains, the last-close settlement is an *unfillable* model quote.
    """
    if not isinstance(spec, Mapping) or set(spec) != _MAIN_FIELDS:
        raise ValueError("invalid historical-paper schema")
    if spec["schema_version"] != _SCHEMA:
        raise ValueError("unsupported historical-paper version")
    if len(canonical_bytes(spec)) > 1_000_000:
        raise ValueError("historical-paper input too large")
    evidence = spec["evidence"]
    if not isinstance(evidence, Mapping) or set(evidence) != _EVIDENCE_FIELDS:
        raise ValueError("invalid declared evidence contract")
    asset = evidence["asset"]
    if not isinstance(asset, str) or not _ASSET.fullmatch(asset):
        raise ValueError("invalid asset")
    if (not isinstance(evidence["source_commit"], str)
            or not _SHA40.fullmatch(evidence["source_commit"])):
        raise ValueError("invalid caller-declared source commit")
    _name(evidence["provider"], "provider")
    _name(evidence["license_reference"], "license_reference")
    if (not isinstance(evidence["declared_sha256"], str)
            or not _SHA64.fullmatch(evidence["declared_sha256"])):
        raise ValueError("invalid caller-declared SHA-256")
    captured = utc(evidence["captured_at"])
    bars = spec["bars"]
    if not isinstance(bars, list) or not 100 <= len(bars) <= 2048:
        raise ValueError("historical replay requires 100-2048 explicit bars")
    strategy = _strategy(spec["strategy"])
    execution = _execution(spec["execution"])
    risk = _risk(spec["risk"])
    last_close = last_received = last_open = None
    observed_ids = set()
    normalized = []
    open_clock = []
    received_clock = []
    for bar in bars:
        if not isinstance(bar, Mapping) or set(bar) != _BAR_FIELDS:
            raise ValueError("invalid historical bar fields")
        ident = _name(bar["bar_id"], "bar_id")
        if ident in observed_ids:
            raise ValueError("duplicate bar ID")
        observed_ids.add(ident)
        opened = utc(bar["opened_at"])
        closed = utc(bar["closed_at"])
        received = utc(bar["received_at"])
        if not opened < closed <= received <= captured:
            raise ValueError("bar not available as-of received or after capture")
        if last_open is not None and opened <= last_open:
            raise ValueError("non-increasing historical open clock")
        if last_close is not None and opened < last_close:
            raise ValueError("overlapping historical bar intervals")
        if last_received is not None and received <= last_received:
            raise ValueError("out-of-order historical receipt clock")
        o, h, l, c = (_tick(bar[k], k) for k in
                      ("open_ticks", "high_ticks", "low_ticks", "close_ticks"))
        if not l <= o <= h or not l <= c <= h:
            raise ValueError("inconsistent historical OHLC")
        normalized.append({"bar_id": ident,
                           # The signal is available only at this receipt,
                           # never at the earlier exchange/bar-close clock.
                           "observed_at": received.isoformat(),
                           "open_ticks": o, "high_ticks": h,
                           "low_ticks": l, "close_ticks": c})
        open_clock.append(opened)
        received_clock.append(received)
        last_open, last_close, last_received = opened, closed, received
    digest = identity({"bars": bars})
    if digest != evidence["declared_sha256"]:
        raise ValueError("declared historical bars SHA-256 mismatch")
    run = _simulate(
        normalized, strategy, execution, risk,
        causal_clock={"opened_at": open_clock, "received_at": received_clock},
    )
    fills = run.pop("fills")
    decisions = run.pop("decisions")
    # The model may forcibly mark a position flat at the final close even
    # if there was no subsequent causal opening. Such "settlement" cannot
    # be interpreted as a trade or a realizable close.
    unfillable_final = run["unfilled_causal_risk_exit"]
    result = {
        "schema_version": _SCHEMA,
        "evidence_kind": "OPERATOR_CLAIMED_BARS_HYPOTHETICAL_FILLS",
        "authority": dict(_AUTHORITY),
        "source_authenticity_verified": False,
        "provider_license_verified": False,
        "source_commit_verified": False,
        "actual_exchange_fills_verified": False,
        "profitability_verified": False,
        "production_qualified": False,
        "broker_order_count": 0,
        "asset": asset, "bar_count": len(bars),
        "caller_declared_commit": evidence["source_commit"],
        "caller_declared_provider": evidence["provider"],
        "caller_declared_license_reference": evidence["license_reference"],
        "capture_cutoff_at": captured.isoformat(),
        "first_opened_at": open_clock[0].isoformat(),
        "last_received_at": received_clock[-1].isoformat(),
        "bars_sha256": digest,
        "configuration": {
            "strategy": strategy, "execution": execution, "risk": risk,
        },
        "decisions_and_modelled_fills_sha256": identity({
            "decisions": decisions, "fills": fills,
        }),
        "modeled_results": run,
        "stale_market_events_rejected": True,
        "latency_adjusted_to_receipt_clock": True,
        "unfillable_last_risk_exit": unfillable_final,
        "terminal_settlement_is_model_quote": True,
        "limitations": [
            "operator-supplied hash and license claims are not source attestations",
            "historical open is not an executable quote or guaranteed venue fill",
            "no market-by-order depth, queue, partial fills, funding or margins",
            "bar-close decisions use received_at rather than exchange clock",
            "risk triggers may wait multiple bars for the first causal opening",
            "forced final close is a hypothetical valuation, not an executed exit",
            "no live order API, production strategy promotion or real profit claim",
        ],
    }
    result["receipt_id"] = identity(result)
    return result
