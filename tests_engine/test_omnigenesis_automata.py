"""Phase 4 safe state-machine compiler and replay tests."""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone

import pytest

from icarus_engine.omnigenesis.automata import (
    compile_automaton, replay_automaton
)


def machine():
    return {
        "name": "sweep_reclaim",
        "states": ["WAIT", "SWEEP", "RECLAIMED", "INVALIDATED"],
        "initial": "WAIT",
        "terminal_states": ["RECLAIMED", "INVALIDATED"],
        "transitions": [
            {"from": "WAIT", "to": "SWEEP", "feature": "sweep_depth",
             "op": "gte", "threshold": 1.0},
            {"from": "SWEEP", "to": "RECLAIMED", "feature": "reclaim_score",
             "op": "gte", "threshold": 0.7},
            {"from": "SWEEP", "to": "INVALIDATED", "feature": "reclaim_score",
             "op": "lt", "threshold": 0.2},
        ],
    }


def observations():
    t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return [
        {"record_id": f"m_{i}", "observed_at": (
            t + timedelta(minutes=i, seconds=-2)).isoformat(),
         "received_at": (t + timedelta(minutes=i, seconds=-1)).isoformat(),
         "decision_at": (t + timedelta(minutes=i)).isoformat(),
         "features": f}
        for i, f in enumerate([
            {"sweep_depth": 0.4},
            {"sweep_depth": 1.2},
            {"reclaim_score": 0.5},
            {"reclaim_score": 0.85},
            {"reclaim_score": 0.01},
        ])
    ]


def test_state_transitions_and_terminal_absorption():
    program = compile_automaton(machine())
    result = replay_automaton(program, observations())
    assert [x["state"] for x in result["trace"]] == [
        "WAIT", "SWEEP", "SWEEP", "RECLAIMED", "RECLAIMED"
    ]
    assert result["terminal"] is True
    assert result["authority"]["execution_authorized"] is False
    assert result["replay_id"] == replay_automaton(program, observations())["replay_id"]


def test_prefix_invariance_no_future_access():
    program = compile_automaton(machine())
    rows = observations()
    prefix = replay_automaton(program, rows[:3])["trace"]
    complete = replay_automaton(program, rows)["trace"]
    assert prefix == complete[:3]
    altered = copy.deepcopy(rows)
    altered[-1]["features"]["reclaim_score"] = -100
    assert replay_automaton(program, altered)["trace"][:3] == prefix


def test_transition_ambiguity_fails_closed():
    spec = machine()
    spec["transitions"].append({
        "from": "SWEEP", "to": "INVALIDATED",
        "feature": "reclaim_score", "op": "gte", "threshold": 0.7
    })
    program = compile_automaton(spec)
    with pytest.raises(ValueError, match="ambiguous"):
        replay_automaton(program, observations())


def test_future_timestamp_rejected():
    rows = observations()
    rows[0]["observed_at"] = "2027-01-01T00:00:00Z"
    with pytest.raises(ValueError, match="future information"):
        replay_automaton(compile_automaton(machine()), rows)


def test_nonmonotone_timestamps_rejected():
    rows = observations()
    rows[1]["decision_at"] = rows[0]["decision_at"]
    rows[1]["received_at"] = rows[0]["received_at"]
    rows[1]["observed_at"] = rows[0]["observed_at"]
    with pytest.raises(ValueError, match="non-increasing"):
        replay_automaton(compile_automaton(machine()), rows)


def test_unreachable_and_terminal_outgoing_rejected():
    spec = machine()
    spec["states"].append("IMPOSSIBLE")
    with pytest.raises(ValueError, match="unreachable"):
        compile_automaton(spec)
    spec = machine()
    spec["transitions"].append({
        "from": "RECLAIMED", "to": "SWEEP",
        "feature": "value", "op": "gt", "threshold": 0,
    })
    with pytest.raises(ValueError, match="absorbing"):
        compile_automaton(spec)


def test_reject_future_target_feature_and_tampering():
    spec = machine()
    spec["transitions"][0]["feature"] = "outcome"
    with pytest.raises(ValueError, match="future/target"):
        compile_automaton(spec)
    program = compile_automaton(machine())
    program["transitions"][0]["threshold"] = 0.1
    with pytest.raises(ValueError, match="tampered"):
        replay_automaton(program, observations())


def test_reject_arbitrary_code_and_unknown_ops():
    spec = machine()
    spec["transitions"][0]["op"] = "__import__"
    with pytest.raises(ValueError, match="unsupported"):
        compile_automaton(spec)
    spec = machine()
    spec["transitions"][0]["feature"] = "price;import os"
    with pytest.raises(ValueError, match="invalid feature"):
        compile_automaton(spec)
