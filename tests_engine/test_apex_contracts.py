from __future__ import annotations

from copy import deepcopy

import pytest


def _observed_body():
    return {
        "kind": "observed",
        "subject": "NQ:depth:best_bid",
        "value": {"price": 25000.25, "size": 17.0},
        "source": {
            "subsystem": "argus",
            "source_repo": "reppiks490/Icarus",
            "source_commit": "a" * 40,
            "source_record_id": "depth-0001",
        },
        "observed_at": "2026-10-01T14:00:00Z",
        "received_at": "2026-10-01T14:00:00.050000Z",
        "calculated_at": "2026-10-01T14:00:00.060000Z",
        "valid_from": "2026-10-01T14:00:00Z",
        "valid_until": None,
        "confidence": 0.91,
        "quality": 0.97,
        "dependencies": [],
        "contradictions": ["depth-feed-b"],
        "falsifiers": ["source correction"],
    }


def test_apex_evidence_normalizes_exact_authority_and_four_clocks():
    from icarus_engine.apex.contracts import EVIDENCE_KINDS, normalize_evidence

    body = _observed_body()
    out = normalize_evidence(body)

    assert EVIDENCE_KINDS == frozenset(
        {"observed", "derived", "reconstructed", "inferred", "unavailable"}
    )
    assert out["kind"] == "observed"
    assert out["observed_at"] == "2026-10-01T14:00:00Z"
    assert out["received_at"] == "2026-10-01T14:00:00.050000Z"
    assert out["calculated_at"] == "2026-10-01T14:00:00.060000Z"
    assert out["valid_from"] == "2026-10-01T14:00:00Z"
    assert out["valid_until"] is None
    assert out["execution_authorized"] is False
    assert out["production_decision_authorized"] is False


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("confidence", True),
        ("confidence", float("nan")),
        ("confidence", float("inf")),
        ("confidence", -0.01),
        ("confidence", 1.01),
        ("quality", False),
        ("quality", float("-inf")),
        ("quality", -0.01),
        ("quality", 1.01),
    ],
)
def test_apex_evidence_rejects_bool_nan_inf_and_out_of_range_confidence(field, value):
    from icarus_engine.apex.contracts import normalize_evidence

    body = _observed_body()
    body[field] = value
    with pytest.raises(ValueError):
        normalize_evidence(body)


def test_unavailable_evidence_cannot_carry_positive_confidence():
    from icarus_engine.apex.contracts import normalize_evidence

    body = _observed_body()
    body["kind"] = "unavailable"
    body["confidence"] = 0.01
    with pytest.raises(ValueError, match="unavailable"):
        normalize_evidence(body)

    body["confidence"] = 0.0
    out = normalize_evidence(body)
    assert out["confidence"] == 0.0


def test_observed_evidence_requires_concrete_source_record():
    from icarus_engine.apex.contracts import normalize_evidence

    body = _observed_body()
    body["source"]["source_record_id"] = ""
    with pytest.raises(ValueError, match="source_record_id"):
        normalize_evidence(body)


def test_evidence_identity_ignores_nonsemantic_recorded_at_but_binds_source_revision():
    from icarus_engine.apex.contracts import evidence_id, normalize_evidence

    body = _observed_body()
    body["recorded_at"] = "2026-10-01T14:01:00Z"
    first = normalize_evidence(body)

    later = deepcopy(body)
    later["recorded_at"] = "2026-10-01T15:01:00Z"
    second = normalize_evidence(later)
    assert evidence_id(first) == evidence_id(second)

    revised = deepcopy(body)
    revised["source"]["source_commit"] = "b" * 40
    third = normalize_evidence(revised)
    assert evidence_id(first) != evidence_id(third)


def test_evidence_rejects_naive_or_reversed_causal_clocks():
    from icarus_engine.apex.contracts import normalize_evidence

    naive = _observed_body()
    naive["observed_at"] = "2026-10-01T14:00:00"
    with pytest.raises(ValueError, match="timezone"):
        normalize_evidence(naive)

    reversed_receipt = _observed_body()
    reversed_receipt["received_at"] = "2026-10-01T13:59:59Z"
    with pytest.raises(ValueError, match="received_at"):
        normalize_evidence(reversed_receipt)

    reversed_calculation = _observed_body()
    reversed_calculation["calculated_at"] = "2026-10-01T13:59:59Z"
    with pytest.raises(ValueError, match="calculated_at"):
        normalize_evidence(reversed_calculation)


def test_evidence_rejects_nonfinite_nested_json_value():
    from icarus_engine.apex.contracts import normalize_evidence

    body = _observed_body()
    body["value"] = {"nested": [1.0, float("nan")]}
    with pytest.raises(ValueError, match="finite JSON"):
        normalize_evidence(body)
