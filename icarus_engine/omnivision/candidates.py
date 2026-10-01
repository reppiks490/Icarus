"""Research-only integration candidate artifacts for OMNIVISION."""
from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
import re
from typing import Mapping, Sequence

from .hypotheses import Hypothesis

_HASH = re.compile(r"^[0-9a-f]{64}$")


def _canon(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value) -> str:
    return hashlib.sha256(_canon(value).encode("utf-8")).hexdigest()


def _strings(values: Sequence[str], name: str) -> list[str]:
    if not isinstance(values, (tuple, list)) or not values:
        raise ValueError(f"{name} must be a non-empty sequence")
    out = []
    for value in values:
        if type(value) is not str or not value.strip():
            raise ValueError(f"{name} entries must be non-empty strings")
        out.append(value)
    return out


def build_candidate(*, hypothesis: Hypothesis, novelty: Mapping, placebo: Mapping,
                    walk_forward: Mapping, dataset_hash: str,
                    known_failure_modes: Sequence[str],
                    rollback_conditions: Sequence[str]) -> dict:
    if not isinstance(hypothesis, Hypothesis):
        raise TypeError("hypothesis must be Hypothesis")
    if type(dataset_hash) is not str or not _HASH.fullmatch(dataset_hash):
        raise ValueError("dataset_hash must be lowercase SHA-256")
    for name, value in (("novelty", novelty), ("placebo", placebo), ("walk_forward", walk_forward)):
        if not isinstance(value, Mapping):
            raise ValueError(f"{name} must be a mapping")

    failures = _strings(known_failure_modes, "known_failure_modes")
    rollbacks = _strings(rollback_conditions, "rollback_conditions")

    integration_ready = (
        novelty.get("status") == "novel"
        and placebo.get("status") == "complete"
        and placebo.get("passed") is True
        and walk_forward.get("passed") is True
        and bool(hypothesis.evidence_ids)
        and bool(failures)
        and bool(rollbacks)
    )

    body = {
        "schema_version": 1,
        "artifact_type": "omnivision_research_candidate",
        "hypothesis": asdict(hypothesis),
        "evidence_ids": list(hypothesis.evidence_ids),
        "dataset_hash": dataset_hash,
        "validation": {
            "novelty": dict(novelty),
            "placebo": dict(placebo),
            "walk_forward": dict(walk_forward),
        },
        "known_failure_modes": failures,
        "rollback_conditions": rollbacks,
        "integration_ready": integration_ready,
        "execution_authorized": False,
    }
    return {"candidate_hash": _digest(body), **body}
