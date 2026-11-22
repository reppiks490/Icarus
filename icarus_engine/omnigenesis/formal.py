"""Phase 10: mathematically checkable finite-automaton safety certificates.

Symbolically evaluates all pairs of primitive numeric guards over finite
IEEE-754 inputs, constructing explicit witness values for overlapping rules.
This proves transition *uniqueness* for the typed primitive guard language;
it cannot prove trading profitability, future-data provenance, or liveness.
"""
from __future__ import annotations

import math
import sys
from collections import deque
from typing import Any, Mapping

from .contracts import identity

_OPERATIONS = {
    "gte": lambda x, t: x >= t,
    "gt": lambda x, t: x > t,
    "lte": lambda x, t: x <= t,
    "lt": lambda x, t: x < t,
    "eq": lambda x, t: x == t,
    "neq": lambda x, t: x != t,
}


def _candidate_witnesses(first: float, second: float) -> list[float]:
    # Equality can only change at a guard threshold. For strict inequalities
    # the immediate representable float on either side is sufficient to cover
    # each connected interval for finite Python float inputs.
    test = [0.0, -sys.float_info.max, sys.float_info.max,
            first, second]
    for t in (first, second):
        test.extend((math.nextafter(t, -math.inf),
                     math.nextafter(t, math.inf)))
    return sorted({x for x in test if math.isfinite(x)})


def guard_collision(a: Mapping[str, Any], b: Mapping[str, Any]) -> dict | None:
    """Return an exact floating-point counterexample for ambiguous transitions."""
    if a["from"] != b["from"] or a["feature"] != b["feature"]:
        return None
    op_a, op_b = a["op"], b["op"]
    if op_a not in _OPERATIONS or op_b not in _OPERATIONS:
        raise ValueError("unrecognized guard operator")
    ta, tb = float(a["threshold"]), float(b["threshold"])
    if not math.isfinite(ta) or not math.isfinite(tb):
        raise ValueError("nonfinite guard threshold")
    for value in _candidate_witnesses(ta, tb):
        if _OPERATIONS[op_a](value, ta) and _OPERATIONS[op_b](value, tb):
            return {
                "from": a["from"],
                "feature": a["feature"],
                "feature_value": value,
                "first_to": a["to"],
                "second_to": b["to"],
            }
    return None


def check_guards(transitions: list[Mapping[str, Any]]) -> list[dict]:
    """Proof-by-complete-threshold partition for single-feature typed guards."""
    if not isinstance(transitions, list) or len(transitions) > 256:
        raise ValueError("invalid transition set")
    witnesses = []
    for i, a in enumerate(transitions):
        for b in transitions[i+1:]:
            collision = guard_collision(a, b)
            if collision is not None:
                witnesses.append(collision)
    return witnesses


def formal_certificate(program: Mapping[str, Any]) -> dict:
    """Verify graph reachability, terminal absorption and guard uniqueness.

    Proves structural properties only of an integrity-bound compiled automaton.
    'Reachable terminal' is existential; it is NOT a guarantee a market event
    will occur, nor that nonterminal looping is impossible.
    """
    if (not isinstance(program, Mapping) or
            program.get("schema_version") != "icarus-omnigenesis-automaton-v1"):
        raise ValueError("uncompiled program")
    expected = identity({k: v for k, v in program.items() if k != "program_id"})
    if program.get("program_id") != expected:
        raise ValueError("tampered program")
    states = program["states"]
    transitions = program["transitions"]
    terminal = set(program["terminal_states"])
    if len(states) > 64 or len(transitions) > 256:
        raise ValueError("resource limit")
    if any(t["from"] in terminal for t in transitions):
        raise ValueError("terminal state is not absorbing")
    overlaps = check_guards(transitions)
    paths = {program["initial"]: []}
    todo = deque([program["initial"]])
    while todo:
        origin = todo.popleft()
        for t in transitions:
            if t["from"] != origin or t["to"] in paths:
                continue
            paths[t["to"]] = paths[origin] + [{
                "from": t["from"], "to": t["to"],
                "feature": t["feature"], "op": t["op"],
                "threshold": t["threshold"]
            }]
            todo.append(t["to"])
    certificate = {
        "schema_version": "icarus-omnigenesis-formal-v1",
        "program_id": expected,
        "deterministic_for_all_finite_features": not overlaps,
        "all_states_reachable": len(paths) == len(states),
        "terminal_absorbing": all(t["from"] not in terminal for t in transitions),
        "every_terminal_reachable": terminal.issubset(paths),
        "reachable_terminal_paths": {
            state: paths.get(state, []) for state in sorted(terminal)
        },
        "ambiguity_counterexamples": overlaps,
        "liveness_proven": False,
        "feature_provenance_proven": False,
        "trading_edge_proven": False,
        "execution_authorized": False,
    }
    certificate["certificate_id"] = identity(certificate)
    return certificate
