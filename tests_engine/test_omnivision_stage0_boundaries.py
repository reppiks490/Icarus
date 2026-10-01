import ast
from pathlib import Path

from icarus_engine.omnivision.candidates import build_candidate
from icarus_engine.omnivision.hypotheses import Hypothesis


RESEARCH_FILES = [
    Path("icarus_engine/world_state.py"),
    *sorted(Path("icarus_engine/omnivision").glob("*.py")),
]

FORBIDDEN_IMPORT_PREFIXES = (
    "icarus_bridge",
    "icarus_engine.strategy.pulse",
    "subprocess",
    "socket",
    "requests",
    "httpx",
)

FORBIDDEN_CALL_NAMES = {
    "place_order",
    "submit_order",
    "execute_trade",
    "system",
    "popen",
}


def _qualified_hypothesis() -> Hypothesis:
    return Hypothesis(
        hypothesis_id="b" * 64,
        kind="latent_gap",
        asset="NQ",
        target="inflation_pressure",
        mechanism="freight-to-goods",
        expected_lag_seconds=0,
        horizon_seconds=0,
        required_variables=("inflation_pressure",),
        evidence_ids=("c" * 64,),
        falsification_rules=("placebo_shift_must_not_match", "walk_forward_must_hold"),
        eligible_regimes=("all",),
        decision_at=100,
    )


def test_research_surface_has_no_forbidden_execution_dependencies():
    findings = []
    for path in RESEARCH_FILES:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(FORBIDDEN_IMPORT_PREFIXES):
                        findings.append(f"{path}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.startswith(FORBIDDEN_IMPORT_PREFIXES):
                    findings.append(f"{path}: from {module}")
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    name = node.func.attr
                else:
                    name = None
                if name in FORBIDDEN_CALL_NAMES:
                    findings.append(f"{path}: call {name}")
    assert findings == []


def test_research_candidate_api_exposes_no_execution_authorization_override():
    artifact = build_candidate(
        hypothesis=_qualified_hypothesis(),
        novelty={"status": "novel"},
        placebo={"status": "complete", "passed": True},
        walk_forward={"passed": True},
        dataset_hash="a" * 64,
        known_failure_modes=("source_stale",),
        rollback_conditions=("walk_forward_sign_breaks",),
    )
    assert artifact["integration_ready"] is True
    assert artifact["execution_authorized"] is False


def test_hypothesis_constructor_rejects_execution_authorization():
    values = dict(
        hypothesis_id="d" * 64,
        kind="latent_gap",
        asset="NQ",
        target="x",
        mechanism="test",
        expected_lag_seconds=0,
        horizon_seconds=0,
        required_variables=("x",),
        evidence_ids=("e" * 64,),
        falsification_rules=("reject_execution",),
        eligible_regimes=("all",),
        decision_at=100,
        execution_authorized=True,
    )

    try:
        Hypothesis(**values)
    except ValueError as error:
        assert "never authorize execution" in str(error)
    else:
        raise AssertionError("Hypothesis accepted execution authorization")
