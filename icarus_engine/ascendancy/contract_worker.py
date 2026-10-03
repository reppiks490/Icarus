"""Fixed, read-only structural validator; never executes a candidate mechanism."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from .foundry import normalize_candidate

MAX_INPUT_BYTES = 262144


def implementation_hash() -> str:
    digest = hashlib.sha256()
    root = Path(__file__).parent
    for name in ("contract_worker.py", "native_validation.py", "foundry.py", "evaluator.py"):
        digest.update(name.encode())
        digest.update((root / name).read_bytes())
    return digest.hexdigest()


def validate(payload: dict) -> dict:
    candidate = normalize_candidate(payload["candidate"])
    identity = candidate["candidate_id"] == payload["candidate"]["candidate_id"]
    source = payload["source_check"]
    unavailable = sum(row["evidence_class"] == "unavailable" for row in candidate["required_observations"])
    code_matches = implementation_hash() == payload["implementation_sha256"]
    outcome = "PASS" if identity and code_matches and all(source.values()) and not unavailable else "INCONCLUSIVE"
    if not identity:
        outcome = "FAIL"
    return {
        "run_id": payload["run_id"],
        "candidate_id": candidate["candidate_id"],
        "evaluation_contract_hash": candidate["evaluation_contract"]["contract_hash"],
        "stage": "CONTRACT_VALIDATION",
        "outcome": outcome,
        "metrics": {
            "candidate_identity_valid": identity,
            "worker_implementation_matches": code_matches,
            "source_check": source,
            "unavailable_observation_count": unavailable,
            "observation_declaration_count": len(candidate["required_observations"]),
            "falsifier_count": len(candidate["falsifiers"]),
            "scientific_performance_evaluated": False,
            "observation_availability_verified": False,
            "source_authorship_attested": False,
        },
        "execution_authorized": False,
        "production_decision_authorized": False,
    }


def main() -> None:
    raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
    if len(raw) > MAX_INPUT_BYTES:
        raise ValueError("native validation input exceeds bound")
    print(json.dumps(validate(json.loads(raw)), sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
