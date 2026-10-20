"""Validation for privately persisted paper-workspace configuration records."""
from __future__ import annotations

import copy

from .assets import REGISTRY, validate_chart_config
from .runtime import preset_path, validate_values
from .strategy.inputs import Inputs


SCHEMA_VERSION = 2
_FIELDS = {"id", "name", "description", "assets", "chart", "inputs",
           "schema_version", "config_revision", "asset_overrides"}


def _inputs(value):
    if not isinstance(value, dict):
        raise ValueError("workspace inputs must be an object")
    unknown = set(value) - set(Inputs.__dataclass_fields__)
    if unknown:
        raise ValueError(f"unknown workspace input names {sorted(unknown)}")
    result = copy.deepcopy(value)
    validate_values(result)
    return result


def normalize_workspace(profile: dict) -> dict:
    """Migrate a defensive copy; never rewrite or silently discard settings."""
    if not isinstance(profile, dict) or set(profile) - _FIELDS:
        raise ValueError("unknown workspace configuration fields")
    version = profile.get("schema_version", 1)
    if type(version) is not int or version not in (1, SCHEMA_VERSION):
        raise ValueError("unsupported workspace configuration schema")
    revision = profile.get("config_revision", 0)
    if type(revision) is not int or revision < 0:
        raise ValueError("workspace config_revision must be a nonnegative integer")
    result = copy.deepcopy(profile)
    result.update(schema_version=SCHEMA_VERSION, config_revision=revision)
    result["inputs"] = _inputs(result["inputs"])
    result["chart"] = validate_chart_config(result["chart"])
    overrides = result.get("asset_overrides", {})
    if not isinstance(overrides, dict):
        raise ValueError("asset_overrides must be an object")
    result["asset_overrides"] = {}
    for symbol, override in overrides.items():
        if symbol not in REGISTRY:
            raise ValueError("asset_overrides require canonical asset symbols")
        if not isinstance(override, dict) or set(override) - {"inputs", "chart", "preset"}:
            raise ValueError("unknown per-asset workspace settings")
        entry = {}
        if "inputs" in override:
            entry["inputs"] = _inputs(override["inputs"])
        if "chart" in override:
            entry["chart"] = validate_chart_config(override["chart"])
        if "preset" in override:
            name = override["preset"]
            if name is not None:
                if not isinstance(name, str) or not name:
                    raise ValueError("workspace preset must be a name or null")
                preset_path("", name)
            entry["preset"] = name
        result["asset_overrides"][symbol] = entry
    return result
