"""ICARUS control-plane receipt verification.

This package verifies evidence-chain structure only. It never authorizes execution,
trading, merge, deployment, publication, or scientific claim promotion.
"""

from .canonical import canonical_bytes, canonical_json, receipt_digest, sha256_digest
from .validation import (
    HANDOFF_SCHEMA_VERSION,
    PIPELINE_POLICY_VERSION,
    validate_cycle,
    validate_receipt,
)

__all__ = [
    "HANDOFF_SCHEMA_VERSION",
    "PIPELINE_POLICY_VERSION",
    "canonical_bytes",
    "canonical_json",
    "receipt_digest",
    "sha256_digest",
    "validate_cycle",
    "validate_receipt",
]
