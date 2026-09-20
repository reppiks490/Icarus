# Grok (xAI) — 2026-09-20. Whole file. ICARUS_HOME layout.
"""Plant directory contract.

``ICARUS_HOME`` (else cwd) holds history, journals, logs, pids. The Python
package still lives in the git checkout so ``python -m icarus_engine.cli``
resolves without an editable install.
"""
from __future__ import annotations

import os
from typing import Dict, Optional

DIRS = ("history", "history/drop", "history/drop/done", "presets", "pine", "logs", "run")


def repo_root(start: Optional[str] = None) -> str:
    """Directory that contains the ``icarus_engine`` package."""
    here = os.path.abspath(start or os.path.dirname(os.path.dirname(__file__)))
    if os.path.isdir(os.path.join(here, "icarus_engine")):
        return here
    cwd = os.path.abspath(os.getcwd())
    if os.path.isdir(os.path.join(cwd, "icarus_engine")):
        return cwd
    return here


def plant_root(explicit: Optional[str] = None) -> str:
    return os.path.abspath(explicit or os.environ.get("ICARUS_HOME") or os.getcwd())


def ensure(root: Optional[str] = None) -> Dict[str, str]:
    root = plant_root(root)
    paths = {"root": root}
    for rel in DIRS:
        p = os.path.join(root, rel)
        os.makedirs(p, exist_ok=True)
        paths[rel] = p
    return paths
