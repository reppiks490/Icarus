"""Read existing provider buffers without acquiring data or starting sessions.

Only the concrete Databento owner currently exposes locked diagnostic buffers.
Other providers remain explicitly unavailable: their public metadata methods can
fetch, and an unrelated request throttle is not a metadata ownership lock.
"""
import copy
import time
from dataclasses import asdict, is_dataclass
from itertools import islice

from .feeds.databento import Databento
from .paper_workspaces import SharedFeed


def snapshot(runner, resource, *, schema="mbp-10", limit=200, now=None):
    if resource not in {"capabilities", "ticks", "depth"}:
        raise ValueError("unknown cached market-data resource")
    if schema not in {"mbp-10", "mbo"}:
        raise ValueError("schema must be mbp-10 or mbo")
    if type(limit) is not int or not 1 <= limit <= 10000:
        raise ValueError("limit must be an integer from 1 to 10000")
    with runner.lock:
        owner = runner.feed
        seen = set()
        while isinstance(owner, SharedFeed):
            if id(owner) in seen:
                raise ValueError("cyclic shared feed ownership")
            seen.add(id(owner))
            owner = owner._feed
        key = runner.spec.ticker
        result = {"asset": runner.symbol, "provider_symbol": key,
                  "provider": type(owner).__name__.lower(), "cached_only": True,
                  "acquisition_requested": False, "available": False,
                  "as_of_ts": time.time() if now is None else now,
                  "capabilities": {}, "metadata": {}, "ticks": [], "events": [],
                  "reason": "LOCKED_PROVIDER_CACHE_UNAVAILABLE"}
        # No duck-typed feed methods: meta/trades/depth may perform network I/O.
        if type(owner) is not Databento:
            return result
        with owner._lock:
            metadata = copy.deepcopy(owner._meta.get(key, {}))
            errors = {kind: error for (symbol, kind), error in owner._depth_errors.items() if symbol == key}
            if errors:
                metadata["depth_errors"] = errors
                metadata["depth_error"] = "; ".join(f"{kind}: {error}" for kind, error in sorted(errors.items()))
            if owner._core_broken:
                metadata["core_session_ok"] = False
            if owner._core_error_code is not None:
                metadata["core_error_code"] = owner._core_error_code
            # Absence of a failure does not prove an observed healthy session.
            health = dict(metadata.get("depth_schema_health", {}))
            health.update({kind: False for kind in owner._depth_broken})
            if health:
                metadata["depth_schema_health"] = health
            if owner._depth_error_code:
                metadata["depth_error_codes"] = dict(owner._depth_error_code)
            result["metadata"] = metadata
            if resource == "capabilities":
                # This concrete implementation only reads static configuration;
                # bypass instance overrides that might initiate provider work.
                result["capabilities"] = {**Databento.capabilities(owner), "mbo_snapshot": False}
                result.update(available=True, reason="PROVIDER_CAPABILITIES_AND_CACHED_METADATA_ONLY")
            else:
                buffer = (owner._trades.get(key) if resource == "ticks"
                          else owner._depth.get((key, schema)))
                rows = list(islice(reversed(buffer), limit))[::-1] if buffer else []
                result["ticks" if resource == "ticks" else "events"] = [
                    asdict(row) if is_dataclass(row) else copy.deepcopy(row) for row in rows]
                result.update(available=bool(rows), reason="CACHED_EVENTS_ONLY" if rows else "NO_CACHED_EVENTS")
                if resource == "depth":
                    result["schema"] = schema
                    result["complete_book_snapshot"] = False
            return result
