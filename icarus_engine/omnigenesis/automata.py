"""Phase 4: bounded, inspectable, deterministic research state machines.

No Python expression evaluator and no execution controls. The language is a
small whitelist of numerical comparisons. Ambiguous transitions fail closed.
A complete replay produces an immutable trace that can be compared by prefix.
"""
from __future__ import annotations

import math
import re
from typing import Any, Mapping

from .contracts import identity, utc

_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,47}$")
_OPS = {"gte", "gt", "lte", "lt", "eq", "neq"}
_FORBIDDEN = {"label", "outcome", "target", "future", "next_price", "pnl"}
_AUTHORITY = {"research_only": True, "execution_authorized": False,
              "production_decision_authorized": False, "auto_promote": False}


def _symbol(s: Any, kind: str) -> str:
    if not isinstance(s, str) or not _NAME.fullmatch(s):
        raise ValueError(f"invalid {kind}")
    return s


def _numerical(x: Any, kind: str) -> float:
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        raise ValueError(f"{kind} must be finite numeric")
    result = float(x)
    if not math.isfinite(result):
        raise ValueError(f"{kind} must be finite numeric")
    return result


def _matches(op: str, feature: float, threshold: float) -> bool:
    return {
        "gte": lambda: feature >= threshold,
        "gt": lambda: feature > threshold,
        "lte": lambda: feature <= threshold,
        "lt": lambda: feature < threshold,
        "eq": lambda: feature == threshold,
        "neq": lambda: feature != threshold,
    }[op]()


def compile_automaton(spec: Mapping[str, Any]) -> dict:
    """Validate a finite automaton; reject unreachable and unsafe states."""
    if not isinstance(spec, Mapping) or set(spec) != {
        "name", "states", "initial", "terminal_states", "transitions"
    }:
        raise ValueError("invalid automaton schema")
    name = _symbol(spec["name"], "automaton name")
    states = spec["states"]
    terminal = spec["terminal_states"]
    raw = spec["transitions"]
    if (not isinstance(states, list) or not 2 <= len(states) <= 64
            or any(not isinstance(s, str) for s in states)):
        raise ValueError("2–64 states required")
    states = [_symbol(s, "state") for s in states]
    if len(set(states)) != len(states):
        raise ValueError("duplicate states")
    initial = _symbol(spec["initial"], "initial state")
    if initial not in states:
        raise ValueError("initial not in states")
    if (not isinstance(terminal, list) or not terminal
            or any(not isinstance(s, str) or s not in states for s in terminal)
            or len(set(terminal)) != len(terminal)):
        raise ValueError("invalid terminal_states")
    if initial in terminal:
        raise ValueError("initial state cannot be terminal")
    if not isinstance(raw, list) or not 1 <= len(raw) <= 256:
        raise ValueError("1–256 transitions required")
    edges = []
    unique = set()
    for t in raw:
        if not isinstance(t, Mapping) or set(t) != {
            "from", "to", "feature", "op", "threshold"
        }:
            raise ValueError("invalid transition schema")
        src, dst = t["from"], t["to"]
        if src not in states or dst not in states:
            raise ValueError("transition references unknown state")
        if src in terminal:
            raise ValueError("terminal states must be absorbing")
        feature = _symbol(t["feature"], "feature")
        if feature.lower() in _FORBIDDEN:
            raise ValueError("future/target feature names forbidden")
        op = t["op"]
        if op not in _OPS:
            raise ValueError("unsupported comparison operator")
        threshold = _numerical(t["threshold"], "threshold")
        key = (src, dst, feature, op, threshold)
        if key in unique:
            raise ValueError("duplicate transition")
        unique.add(key)
        edges.append({"from": src, "to": dst, "feature": feature,
                      "op": op, "threshold": threshold})
    # Reject contradictory guards at compile time, including rules testing
    # different features that can simultaneously appear in one event record.
    from .formal import check_guards
    overlap = check_guards(edges)
    if overlap:
        raise ValueError("ambiguous transitions; counterexample: " + str(overlap[0]))
    reached = {initial}
    while True:
        expanded = reached | {t["to"] for t in edges if t["from"] in reached}
        if expanded == reached:
            break
        reached = expanded
    if reached != set(states):
        raise ValueError("unreachable state detected")
    if not set(terminal).issubset(reached):
        raise ValueError("unreachable terminal state")
    program = {
        "schema_version": "icarus-omnigenesis-automaton-v1",
        "name": name,
        "states": states,
        "initial": initial,
        "terminal_states": terminal,
        "transitions": edges,
    }
    program["program_id"] = identity(program)
    return program


def replay_automaton(program: Mapping[str, Any],
                     observations: list[Mapping[str, Any]]) -> dict:
    """Run a compiled program over observed event rows, never real orders."""
    if not isinstance(program, Mapping) or program.get("schema_version") != (
        "icarus-omnigenesis-automaton-v1"
    ):
        raise ValueError("not a compiled automaton")
    pid = program.get("program_id")
    recomputed = identity({k: v for k, v in program.items()
                           if k != "program_id"})
    if pid != recomputed:
        raise ValueError("tampered automaton")
    if not isinstance(observations, list) or len(observations) > 100000:
        raise ValueError("observations must be a bounded list")
    state = program["initial"]
    trace = []
    previous_time = None
    for obs in observations:
        if not isinstance(obs, Mapping) or set(obs) != {
            "record_id", "observed_at", "received_at", "decision_at", "features"
        }:
            raise ValueError("invalid observation schema")
        rid = _symbol(obs["record_id"], "record_id")
        observed, received, decision = (utc(obs[k]) for k in
                                        ("observed_at", "received_at", "decision_at"))
        if not observed <= received <= decision:
            raise ValueError("future information in observation")
        if previous_time is not None and decision <= previous_time:
            raise ValueError("non-increasing decision time")
        previous_time = decision
        raw_features = obs["features"]
        if not isinstance(raw_features, Mapping) or len(raw_features) > 256:
            raise ValueError("invalid feature map")
        features = {}
        for key, value in raw_features.items():
            safe = _symbol(key, "feature name")
            if safe.lower() in _FORBIDDEN:
                raise ValueError("future/target feature names forbidden")
            features[safe] = _numerical(value, "feature")
        matches = [
            t for t in program["transitions"]
            if t["from"] == state and t["feature"] in features
            and _matches(t["op"], features[t["feature"]], t["threshold"])
        ]
        if len(matches) > 1:
            raise ValueError("ambiguous transitions: non-deterministic program")
        transition = matches[0] if matches else None
        if transition is not None:
            state = transition["to"]
        trace.append({
            "record_id": rid, "decision_at": decision.isoformat(),
            "state": state, "transition": (
                {"from": transition["from"], "to": transition["to"]}
                if transition else None
            ),
        })
    return {
        "schema_version": "icarus-omnigenesis-replay-v1",
        "program_id": pid,
        "authority": dict(_AUTHORITY),
        "final_state": state,
        "terminal": state in program["terminal_states"],
        "observation_count": len(observations),
        "trace": trace,
        "replay_id": identity({"program_id": pid, "trace": trace}),
    }
