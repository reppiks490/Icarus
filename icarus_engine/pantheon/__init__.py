"""ICARUS PANTHEON / AETHER shadow research fabric."""
from .aether import AetherSwarm
from .contracts import FACULTIES, OBSERVATION_SCHEMA, SCHEMA_VERSION
from .bridge import subsystem_context
from .kernel import PantheonKernel

__all__ = ["AetherSwarm", "FACULTIES", "OBSERVATION_SCHEMA", "SCHEMA_VERSION", "PantheonKernel", "subsystem_context"]
