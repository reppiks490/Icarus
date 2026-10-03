"""Capture exact local ICARUS code provenance without granting authority.

A research artifact may only become a Brain candidate when the code revision that
created it is known exactly. Dirty or non-Git installations remain useful as
research evidence, but candidate promotion fails closed.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
from typing import Any
from .process_launch import background_kwargs

REPOSITORY = "reppiks490/Icarus"


def _sha(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip().lower()
    if len(value) != 40 or any(c not in "0123456789abcdef" for c in value):
        return None
    return value


def local_code_provenance(repo_root: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    """Return a clean exact Git revision when it can be proven locally."""
    env_sha = _sha(os.environ.get("ICARUS_GIT_SHA"))
    if env_sha:
        return {
            "repository": REPOSITORY,
            "commit": env_sha,
            "status": "exact_env",
            "clean": None,
            "candidate_revision_eligible": True,
        }

    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parents[1]
    try:
        commit = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
            **background_kwargs(),
        ).stdout.strip()
        commit = _sha(commit)
        if commit is None:
            raise ValueError("git returned a non-SHA revision")
        dirty = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=no"],
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
            **background_kwargs(),
        ).stdout.strip()
        if dirty:
            return {
                "repository": REPOSITORY,
                "commit": commit,
                "status": "dirty_checkout",
                "clean": False,
                "candidate_revision_eligible": False,
            }
        return {
            "repository": REPOSITORY,
            "commit": commit,
            "status": "exact_clean_git",
            "clean": True,
            "candidate_revision_eligible": True,
        }
    except (OSError, subprocess.SubprocessError, ValueError):
        return {
            "repository": REPOSITORY,
            "commit": None,
            "status": "unavailable",
            "clean": None,
            "candidate_revision_eligible": False,
        }
