from __future__ import annotations

import json


def test_missing_diagnostics_are_unknown():
    from icarus_engine.apex.criticality import criticality_state
    out=criticality_state(liquidity={},reflexivity={},volatility_evidence={},participant_concentration={},cross_asset_evidence={})
    assert out["state"]=="UNKNOWN"


def test_one_extreme_signal_does_not_force_critical():
    from icarus_engine.apex.criticality import criticality_state
    out=criticality_state(liquidity={"fragility":0.99},reflexivity={},volatility_evidence={},participant_concentration={},cross_asset_evidence={})
    assert out["state"] not in {"CRITICAL","CASCADE"}


def test_multiple_independent_stress_diagnostics_can_reach_critical():
    from icarus_engine.apex.criticality import criticality_state
    out=criticality_state(liquidity={"fragility":0.9},reflexivity={"gain":0.9},volatility_evidence={"expansion":0.85},participant_concentration={"concentration":0.8},cross_asset_evidence={"synchronization":0.75})
    assert out["state"]=="CRITICAL"
    json.dumps(out,allow_nan=False)


def test_contradictory_damping_prevents_over_escalation():
    from icarus_engine.apex.criticality import criticality_state
    out=criticality_state(liquidity={"fragility":0.9,"resilience":0.95},reflexivity={"gain":0.9,"damping":0.9},volatility_evidence={"expansion":0.85},participant_concentration={"concentration":0.8},cross_asset_evidence={"synchronization":0.75})
    assert out["state"] != "CASCADE"
