"""OMNIGENESIS: isolated, research-only mathematical discovery laboratory.

No broker, production routing, strategy mutation, network access, or automatic
model promotion. This package deliberately has no imports from execution code.
"""
from .arithmetic import next_prime, first_event_offset
from .foundry import evaluate_dataset
from .ledger import ResearchLedger

SCHEMA_VERSION = "icarus-omnigenesis-v1"
AUTHORITY = {"research_only": True, "execution_authorized": False,
             "production_decision_authorized": False, "auto_promote": False}

__all__ = ["next_prime", "first_event_offset", "evaluate_dataset",
           "ResearchLedger", "SCHEMA_VERSION", "AUTHORITY"]
