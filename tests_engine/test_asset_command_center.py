from __future__ import annotations

from icarus_engine.asset_command_center import (
    build_all_asset_command_states,
    build_asset_command_state,
)
from icarus_engine.futures_catalog import FUTURES_PRODUCTS
from icarus_engine.system_index import build_system_index


def _verified_provider_state():
    return {
        root: {
            "qualification": "verified",
            "verified_access": True,
            "fresh": True,
            "evidence_id": f"test:{root}",
        }
        for root in FUTURES_PRODUCTS
    }


def test_asset_command_center_has_one_backend_state_per_futures_root():
    states = build_all_asset_command_states()
    assert set(states) == set(FUTURES_PRODUCTS)
    for root, state in states.items():
        assert state.root == root
        assert state.visible is True
        assert state.live_authorized is False
        assert state.live_tradeable is False
        assert state.stats["trade_count"] == 0
        assert state.stats["realized_pnl"] == 0.0
        assert state.stats["unrealized_pnl"] == 0.0


def test_default_state_is_fail_closed_when_market_data_is_not_verified():
    for root, state in build_all_asset_command_states().items():
        assert state.simulated_paper_tradeable is False
        assert any("provider" in blocker.lower() or "data" in blocker.lower() for blocker in state.blockers)


def test_verified_data_alone_does_not_make_structural_root_simulated_paper_ready():
    index = build_system_index(provider_state=_verified_provider_state())
    state = build_asset_command_state("NQ", index=index)
    assert state.structural_execution_qualified is True
    assert state.simulated_paper_tradeable is False
    assert state.broker_paper_tradeable is False
    assert state.live_tradeable is False
    assert any("risk controls" in blocker.lower() for blocker in state.blockers)
    assert any("state/journal" in blocker.lower() for blocker in state.blockers)


def test_simulated_paper_readiness_requires_risk_and_state_capability():
    index = build_system_index(provider_state=_verified_provider_state())
    state = build_asset_command_state(
        "NQ",
        index=index,
        runtime={"risk_controls_ready": True, "state_journal_ready": True},
    )
    assert state.structural_execution_qualified is True
    assert state.risk_controls_ready is True
    assert state.state_journal_ready is True
    assert state.simulated_paper_tradeable is True
    assert state.broker_paper_tradeable is False
    assert state.live_tradeable is False
    assert any("broker" in blocker.lower() for blocker in state.blockers)


def test_newly_expanded_root_is_structurally_qualified_but_broker_paper_still_fails_closed():
    index = build_system_index(provider_state=_verified_provider_state())
    state = build_asset_command_state(
        "CL",
        index=index,
        runtime={"risk_controls_ready": True, "state_journal_ready": True},
    )
    assert state.structural_execution_qualified is True
    assert state.simulated_paper_tradeable is True
    assert state.broker_paper_tradeable is False
    assert state.live_tradeable is False
    assert any("broker" in blocker.lower() for blocker in state.blockers)


def test_runtime_statistics_are_data_only_and_do_not_change_authorization():
    index = build_system_index(provider_state=_verified_provider_state())
    runtime = {
        "position": 2,
        "average_entry": 20123.5,
        "last_price": 20140.0,
        "realized_pnl": 125.0,
        "unrealized_pnl": 660.0,
        "trade_count": 7,
        "wins": 5,
        "losses": 2,
        "profit_factor": 2.4,
        "max_drawdown": 180.0,
        "regime": "trend_high_vol",
        "regime_confidence": 0.81,
    }
    state = build_asset_command_state("NQ", index=index, runtime=runtime)
    assert state.stats["position"] == 2
    assert state.stats["trade_count"] == 7
    assert state.stats["regime"] == "trend_high_vol"
    assert state.stats["regime_confidence"] == 0.81
    assert state.live_authorized is False
    assert state.live_tradeable is False
