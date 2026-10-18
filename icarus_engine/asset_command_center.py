"""Backend-only asset command-center state for registry-driven dashboards.

This module deliberately contains no order submission logic.  It projects the
canonical capability index plus optional runtime statistics into one typed state
record per futures root.  UI surfaces consume these records; they do not create an
independent execution path.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional

from .futures_catalog import FUTURES_PRODUCTS
from .system_index import build_system_index


_DEFAULT_STATS: dict[str, Any] = {
    "position": 0.0,
    "average_entry": None,
    "last_price": None,
    "bid": None,
    "ask": None,
    "price_timestamp": None,
    "realized_pnl": 0.0,
    "unrealized_pnl": 0.0,
    "fees": 0.0,
    "slippage": 0.0,
    "trade_count": 0,
    "wins": 0,
    "losses": 0,
    "win_rate": None,
    "expectancy": None,
    "profit_factor": None,
    "max_drawdown": 0.0,
    "mae": None,
    "mfe": None,
    "average_holding_seconds": None,
    "rejected_orders": 0,
    "reconciliation_health": "unverified",
    "feed_health": "unverified",
    "brain_action": None,
    "brain_candidate": None,
    "regime": None,
    "regime_confidence": None,
}


@dataclass(frozen=True)
class AssetCommandState:
    root: str
    name: str
    exchange: str
    asset_class: str
    provider_symbol: str
    tv_symbol: str
    tick_size: float
    point_value: float
    tick_value: float
    full_root: str
    ratio_to_full: float
    visible: bool
    data_verified: bool
    data_fresh: bool
    structural_execution_qualified: bool
    risk_controls_ready: bool
    state_journal_ready: bool
    simulated_paper_tradeable: bool
    broker_paper_tradeable: bool
    live_authorized: bool
    live_tradeable: bool
    blockers: tuple[str, ...]
    stats: dict[str, Any]


def _unique_blockers(values: list[Optional[str]]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value:
            continue
        text = str(value).strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return tuple(result)


def build_asset_command_state(
    root: str,
    *,
    index: Optional[Mapping[str, Any]] = None,
    runtime: Optional[Mapping[str, Any]] = None,
) -> AssetCommandState:
    """Build one fail-closed, asset-centric dashboard state record."""
    key = str(root).strip().upper()
    if key not in FUTURES_PRODUCTS:
        raise ValueError(f"unknown canonical futures root {root!r}")
    system = dict(index or build_system_index())
    assets = system.get("assets") or {}
    if key not in assets:
        raise ValueError(f"system index does not contain futures root {key!r}")
    record = assets[key]
    identity = record["identity"]
    economics = record["economics"]
    data = record["data"]
    execution = record["execution"]
    broker = execution["broker"]

    data_verified = data.get("verified_access") is True
    data_fresh = data.get("fresh") is True
    # Static candidate availability supports research and discovery, but does
    # not make a root eligible for simulated paper execution. This state is an
    # execution-facing command surface and must honor the qualified resolver.
    structural = execution.get("execution_qualified") is True
    risk_controls_ready = runtime is not None and runtime.get("risk_controls_ready") is True
    state_journal_ready = runtime is not None and runtime.get("state_journal_ready") is True
    # The index cannot establish simulated-paper readiness without runtime
    # risk and journal evidence. The authoritative command state can derive
    # eligibility once all required evidence is present.
    paper_authorized = execution.get("simulated_paper_authorized") is True or bool(
        structural
        and system.get("owner_policy", {}).get("simulated_paper") == "allowed"
        and data_verified
        and data_fresh
        and risk_controls_ready
        and state_journal_ready
    )
    simulated_paper = bool(
        structural and paper_authorized and data_verified and data_fresh
        and risk_controls_ready and state_journal_ready
    )
    broker_paper = bool(
        execution.get("broker_paper_tradeable") is True
        and risk_controls_ready and state_journal_ready
    )

    blockers: list[Optional[str]] = []
    if not (data_verified and data_fresh):
        blockers.append(data.get("blocker") or "market data is not verified and fresh")
    if not structural:
        blockers.append(execution.get("execution_blocker") or "dated-contract resolver is not qualified")
    if not paper_authorized:
        blockers.append("simulated-paper authorization is not verified")
    if not risk_controls_ready:
        blockers.append("risk controls are not verified")
    if not state_journal_ready:
        blockers.append("state/journal capability is not verified")
    if not broker_paper:
        blockers.append(broker.get("blocker") or "broker-paper path is not verified")
    blockers.append("live execution is disabled by owner policy")

    stats = dict(_DEFAULT_STATS)
    if runtime:
        for name in stats:
            if name in runtime:
                stats[name] = runtime[name]

    return AssetCommandState(
        root=key,
        name=str(identity["name"]),
        exchange=str(identity["exchange"]),
        asset_class=str(identity["asset_class"]),
        provider_symbol=str(identity["provider_symbol"]),
        tv_symbol=str(identity["tv_symbol"]),
        tick_size=float(economics["tick_size"]),
        point_value=float(economics["point_value"]),
        tick_value=float(economics["tick_value"]),
        full_root=str(economics["full_root"]),
        ratio_to_full=float(economics["ratio_to_full"]),
        visible=True,
        data_verified=data_verified,
        data_fresh=data_fresh,
        structural_execution_qualified=structural,
        risk_controls_ready=risk_controls_ready,
        state_journal_ready=state_journal_ready,
        simulated_paper_tradeable=simulated_paper,
        broker_paper_tradeable=broker_paper,
        live_authorized=False,
        live_tradeable=False,
        blockers=_unique_blockers(blockers),
        stats=stats,
    )


def build_all_asset_command_states(
    *,
    index: Optional[Mapping[str, Any]] = None,
    runtime_by_root: Optional[Mapping[str, Mapping[str, Any]]] = None,
) -> dict[str, AssetCommandState]:
    """Build deterministic backend dashboard state for all canonical futures."""
    system = index or build_system_index()
    runtime = runtime_by_root or {}
    return {
        root: build_asset_command_state(root, index=system, runtime=runtime.get(root))
        for root in sorted(FUTURES_PRODUCTS)
    }
