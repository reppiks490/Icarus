# Grok (xAI) — 2026-09-20. Whole package. Local paper-trading plant: data dir, drop ingest, supervisor.
"""Icarus plant — the engine's local infrastructure (stdlib only).

Not a CME feed. Not Docker. A data directory + process supervisor so the
engine (and optional bridge) stay up, pick up Supercharts exports dropped
into ``history/drop/``, and can run offline on those bars via FileFeed.
"""
__version__ = "0.1.0"
